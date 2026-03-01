"""Metadata fixer scan/apply service."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Callable, Iterable, List, Optional

from syncra.models.metadata import (
    MetadataApplyResult,
    MetadataProposal,
    TrackIdentity,
)
from syncra.services.metadata_provider import MetadataProvider


class MetadataFixerService:
    def __init__(self, provider: MetadataProvider, review_threshold: int = 80):
        self.provider = provider
        self.review_threshold = review_threshold
        self.audit_file = os.path.join("temp", "metadata_audit_log.jsonl")
        self._last_batch: List[dict] = []

    def _track_identity(self, track) -> TrackIdentity:
        artist = ""
        album = ""
        try:
            if hasattr(track, "artist") and track.artist():
                artist = track.artist().title or ""
        except Exception:
            artist = getattr(track, "originalTitle", "") or ""
        if not artist:
            artist = getattr(track, "originalTitle", "") or ""

        try:
            if hasattr(track, "album") and track.album():
                album = track.album().title or ""
        except Exception:
            album = ""

        return TrackIdentity(
            rating_key=str(getattr(track, "ratingKey", "")),
            title=getattr(track, "title", "") or "",
            artist=artist,
            album=album,
            year=getattr(track, "year", None),
            plex_track=track,
        )

    def scan(self, tracks: Iterable, progress_cb: Optional[Callable[[int, int, str], None]] = None) -> List[MetadataProposal]:
        items = list(tracks)
        total = len(items)
        proposals: List[MetadataProposal] = []

        for idx, track in enumerate(items, 1):
            identity = self._track_identity(track)
            if progress_cb:
                progress_cb(idx, total, f"Scanning {identity.title} - {identity.artist}")

            try:
                candidate = self.provider.search_track(identity)
            except Exception as exc:
                logging.warning(f"Metadata search failed for {identity.title}: {exc}")
                continue

            if not candidate:
                continue

            confidence = float(candidate.score)
            changes = {}
            if candidate.title and candidate.title.strip() != identity.title.strip():
                changes["title"] = {"before": identity.title, "after": candidate.title}
            if candidate.artist and candidate.artist.strip() != identity.artist.strip():
                changes["artist"] = {"before": identity.artist, "after": candidate.artist}
            if candidate.album and candidate.album.strip() and candidate.album.strip() != identity.album.strip():
                changes["album"] = {"before": identity.album, "after": candidate.album}
            if candidate.year and candidate.year != identity.year:
                changes["year"] = {"before": identity.year, "after": candidate.year}

            if not changes:
                continue
            if confidence < self.review_threshold:
                continue

            proposals.append(
                MetadataProposal(
                    track=identity,
                    candidate=candidate,
                    confidence=confidence,
                    changes=changes,
                )
            )

        return proposals

    def _write_audit(self, record: dict) -> None:
        os.makedirs(os.path.dirname(self.audit_file), exist_ok=True)
        persisted = dict(record)
        persisted.pop("_track_ref", None)
        with open(self.audit_file, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(persisted, ensure_ascii=True) + "\n")

    def _resolve_track_file_path(self, track) -> Optional[str]:
        """Resolve the first writable local file path for a Plex track item."""
        try:
            if hasattr(track, "iterParts"):
                for part in track.iterParts():
                    file_path = getattr(part, "file", None)
                    if file_path and isinstance(file_path, str):
                        return file_path
        except Exception as exc:
            logging.debug(f"Failed to resolve file path from Plex parts: {exc}")
        return None

    def _load_mutagen_easy(self, file_path: str):
        try:
            import mutagen
        except Exception as exc:
            raise RuntimeError(
                "Mutagen is required for file metadata editing. Install dependency: mutagen"
            ) from exc

        tags = mutagen.File(file_path, easy=True)
        if tags is None:
            raise RuntimeError(f"Unsupported or unreadable audio format: {file_path}")
        if getattr(tags, "tags", None) is None:
            try:
                tags.add_tags()
            except Exception:
                # Some containers auto-create tags on assignment/save.
                pass
        return tags

    def _read_file_metadata(self, file_path: str) -> dict:
        tags = self._load_mutagen_easy(file_path)

        def _first(key: str) -> str:
            values = None
            try:
                values = tags.get(key)
            except Exception:
                values = None
            if isinstance(values, list) and values:
                return str(values[0]).strip()
            if isinstance(values, str):
                return values.strip()
            return ""

        raw_year = _first("date") or _first("year")
        year = None
        if raw_year[:4].isdigit():
            try:
                year = int(raw_year[:4])
            except Exception:
                year = None

        return {
            "title": _first("title"),
            "artist": _first("artist"),
            "album": _first("album"),
            "year": year,
        }

    def _write_file_metadata(self, file_path: str, changes: dict) -> List[str]:
        tags = self._load_mutagen_easy(file_path)
        attempted_fields: List[str] = []

        def _set_field(key: str, value: str):
            try:
                tags[key] = [str(value)]
                return True
            except Exception:
                return False

        if "title" in changes:
            if _set_field("title", changes["title"]["after"]):
                attempted_fields.append("title")
        if "artist" in changes:
            if _set_field("artist", changes["artist"]["after"]):
                attempted_fields.append("artist")
        if "album" in changes:
            if _set_field("album", changes["album"]["after"]):
                attempted_fields.append("album")
        if "year" in changes:
            year_val = str(changes["year"]["after"])
            set_date = _set_field("date", year_val)
            set_year = _set_field("year", year_val)
            if set_date or set_year:
                attempted_fields.append("year")

        if attempted_fields:
            tags.save()
        return attempted_fields

    def _apply_via_plex_fields(self, track, changes: dict) -> List[str]:
        """Compatibility fallback when file path is unavailable."""
        attempted_fields: List[str] = []
        use_batch = hasattr(track, "batchEdits") and hasattr(track, "saveEdits")
        if use_batch:
            track.batchEdits()
        if "title" in changes:
            track.editTitle(changes["title"]["after"], locked=True)
            attempted_fields.append("title")
        if "artist" in changes:
            track.editTrackArtist(changes["artist"]["after"], locked=True)
            attempted_fields.append("artist")
        if "album" in changes:
            track.editField("parentTitle", changes["album"]["after"], locked=True)
            attempted_fields.append("album")
        if "year" in changes:
            track.editField("year", changes["year"]["after"], locked=True)
            attempted_fields.append("year")
        if use_batch and attempted_fields:
            track.saveEdits()
        return attempted_fields

    def _verify_applied_fields(self, before_state: dict, after_state: dict, attempted_fields: List[str]) -> List[str]:
        applied_fields: List[str] = []
        for field in attempted_fields:
            if before_state.get(field) != after_state.get(field):
                applied_fields.append(field)
        return applied_fields

    def apply(
        self,
        proposals: Iterable[MetadataProposal],
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[MetadataApplyResult]:
        selected = list(proposals)
        total = len(selected)
        results: List[MetadataApplyResult] = []
        self._last_batch = []

        for idx, proposal in enumerate(selected, 1):
            track = proposal.track.plex_track
            rk = proposal.track.rating_key
            if progress_cb:
                progress_cb(idx, total, f"Applying metadata for {proposal.track.title}")

            applied_fields = []
            success = True
            err = ""
            before_state = {
                "title": proposal.track.title,
                "artist": proposal.track.artist,
                "album": proposal.track.album,
                "year": proposal.track.year,
            }
            attempted_fields = []
            file_path = self._resolve_track_file_path(track)

            try:
                if file_path:
                    # File-first mode: write local file tags, then refresh Plex metadata.
                    before_state = self._read_file_metadata(file_path)
                    attempted_fields = self._write_file_metadata(file_path, proposal.changes)
                    if attempted_fields:
                        try:
                            if hasattr(track, "refresh"):
                                track.refresh()
                            if hasattr(track, "reload"):
                                track.reload()
                        except Exception as refresh_exc:
                            logging.debug(f"Plex refresh/reload after file tag write failed for {rk}: {refresh_exc}")
                        after_file_state = self._read_file_metadata(file_path)
                        applied_fields = self._verify_applied_fields(before_state, after_file_state, attempted_fields)
                    else:
                        success = False
                        err = "No writable file tag fields selected for apply."
                else:
                    # Compatibility fallback for tracks without accessible local files.
                    attempted_fields = self._apply_via_plex_fields(track, proposal.changes)
                    if attempted_fields:
                        if hasattr(track, "reload"):
                            try:
                                track.reload()
                            except Exception as reload_exc:
                                logging.debug(f"Track reload after metadata edit failed for {rk}: {reload_exc}")
                        verified_after = self._track_identity(track)
                        after_plex_state = {
                            "title": verified_after.title,
                            "artist": verified_after.artist,
                            "album": verified_after.album,
                            "year": verified_after.year,
                        }
                        applied_fields = self._verify_applied_fields(before_state, after_plex_state, attempted_fields)
                    else:
                        success = False
                        err = "No supported metadata fields selected for apply."

                if success and not applied_fields:
                    success = False
                    err = (
                        "No metadata changes were persisted. "
                        "For local files, ensure tags are writable and Plex can refresh metadata."
                    )
            except Exception as exc:
                success = False
                err = str(exc)

            after_state = {
                "title": proposal.changes.get("title", {}).get("after", proposal.track.title),
                "artist": proposal.changes.get("artist", {}).get("after", proposal.track.artist),
                "album": proposal.changes.get("album", {}).get("after", proposal.track.album),
                "year": proposal.changes.get("year", {}).get("after", proposal.track.year),
            }

            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "rating_key": rk,
                "source": proposal.candidate.source,
                "confidence": proposal.confidence,
                "before": before_state,
                "after": after_state,
                "applied_fields": applied_fields,
                "success": success,
                "error": err,
                "file_path": file_path,
                "_track_ref": track,
            }
            self._last_batch.append(record)
            self._write_audit(record)

            results.append(
                MetadataApplyResult(
                    rating_key=rk,
                    success=success,
                    applied_fields=applied_fields,
                    error=err,
                    timestamp=record["timestamp"],
                )
            )

        return results

    def rollback_last_batch(self) -> List[MetadataApplyResult]:
        """Best-effort rollback for current process batch."""
        results: List[MetadataApplyResult] = []
        for entry in reversed(self._last_batch):
            track = entry.get("_track_ref")
            if not track:
                # We only persist audit externally; rollback is in-memory best effort.
                results.append(
                    MetadataApplyResult(
                        rating_key=entry.get("rating_key", ""),
                        success=False,
                        error="Rollback unavailable after app restart",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
                )
                continue
            try:
                before = entry.get("before", {})
                file_path = entry.get("file_path") or self._resolve_track_file_path(track)
                if file_path:
                    rollback_changes = {}
                    for field in ("title", "artist", "album", "year"):
                        if field in before and before.get(field) is not None:
                            rollback_changes[field] = {"after": before.get(field)}
                    self._write_file_metadata(file_path, rollback_changes)
                    if hasattr(track, "refresh"):
                        try:
                            track.refresh()
                        except Exception:
                            pass
                else:
                    self._apply_via_plex_fields(
                        track,
                        {
                            k: {"after": v}
                            for k, v in before.items()
                            if k in {"title", "artist", "album", "year"} and v is not None
                        },
                    )
                results.append(
                    MetadataApplyResult(
                        rating_key=entry.get("rating_key", ""),
                        success=True,
                        applied_fields=["title", "artist", "album", "year"],
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
                )
            except Exception as exc:
                results.append(
                    MetadataApplyResult(
                        rating_key=entry.get("rating_key", ""),
                        success=False,
                        error=str(exc),
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
                )
        return results
