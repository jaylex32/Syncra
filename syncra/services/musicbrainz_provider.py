"""MusicBrainz + Cover Art Archive metadata provider."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote_plus

from syncra.models.metadata import MetadataCandidate, TrackIdentity
from syncra.services.http_client import HttpClient, RateLimiter
from syncra.services.metadata_provider import MetadataProvider


class MusicBrainzProvider(MetadataProvider):
    MB_BASE = "https://musicbrainz.org/ws/2"
    CAA_BASE = "https://coverartarchive.org/release"

    def __init__(self, user_agent: str, rate_limit_rps: float = 1.0, cache_ttl_hours: int = 168):
        self.http = HttpClient(user_agent=user_agent, retries=3, backoff=0.5)
        self.limiter = RateLimiter(rate_per_second=rate_limit_rps)
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self.cache_file = os.path.join("temp", "metadata_cache.json")
        self.cache = self._load_cache()

    def _load_cache(self) -> dict:
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "r", encoding="utf-8") as fh:
                    return json.load(fh)
        except Exception as exc:
            logging.warning(f"Failed to load metadata cache: {exc}")
        return {}

    def _save_cache(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as fh:
                json.dump(self.cache, fh, indent=2)
        except Exception as exc:
            logging.warning(f"Failed to save metadata cache: {exc}")

    def _cache_get(self, key: str):
        entry = self.cache.get(key)
        if not entry:
            return None
        try:
            ts = datetime.fromisoformat(entry["cached_at"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            else:
                ts = ts.astimezone(timezone.utc)
            if datetime.now(timezone.utc) - ts > self.cache_ttl:
                return None
            return entry["payload"]
        except Exception:
            return None

    def _cache_set(self, key: str, payload: dict) -> None:
        self.cache[key] = {
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        self._save_cache()

    def search_track(self, track: TrackIdentity) -> Optional[MetadataCandidate]:
        title = (track.title or "").strip()
        artist = (track.artist or "").strip()
        if not title:
            return None

        cache_key = f"search::{title.lower()}::{artist.lower()}"
        data = self._cache_get(cache_key)
        if data is None:
            query = f'recording:"{title}"'
            if artist:
                query += f' AND artist:"{artist}"'

            params = {
                "query": query,
                "fmt": "json",
                "limit": 5,
            }
            self.limiter.wait()
            resp = self.http.get(f"{self.MB_BASE}/recording", params=params, timeout=20)
            if resp.status_code != 200:
                logging.warning(
                    "MusicBrainz search failed for title=%s artist=%s status=%s",
                    title,
                    artist,
                    resp.status_code,
                )
                return None
            data = resp.json()
            self._cache_set(cache_key, data)

        recordings = data.get("recordings", [])
        if not recordings:
            return None

        top = recordings[0]
        credit = top.get("artist-credit", [])
        mb_artist = credit[0]["name"] if credit else artist
        releases = top.get("releases", [])
        rel = releases[0] if releases else {}
        release_title = rel.get("title", track.album)
        release_mbid = rel.get("id")
        first_release_date = rel.get("date") or top.get("first-release-date")
        year = None
        if first_release_date and len(first_release_date) >= 4 and first_release_date[:4].isdigit():
            year = int(first_release_date[:4])

        ext_score = top.get("score", 0)
        try:
            score = float(ext_score)
        except (TypeError, ValueError):
            score = 0.0

        candidate = MetadataCandidate(
            source="musicbrainz",
            title=top.get("title") or track.title,
            artist=mb_artist or track.artist,
            album=release_title or track.album,
            year=year,
            recording_mbid=top.get("id"),
            release_mbid=release_mbid,
            score=score,
        )

        if release_mbid:
            release_details = self.get_release_details(release_mbid)
            candidate.cover_art_url = release_details.get("cover_art_url")

        return candidate

    def validate_recording_mbid(self, recording_mbid: str) -> bool:
        """Return True if MBID exists as a MusicBrainz recording."""
        mbid = (recording_mbid or "").strip().lower()
        if not mbid:
            return False

        cache_key = f"recording_exists::{mbid}"
        cached = self._cache_get(cache_key)
        if isinstance(cached, dict) and "exists" in cached:
            return bool(cached["exists"])

        self.limiter.wait()
        resp = self.http.get(f"{self.MB_BASE}/recording/{quote_plus(mbid)}", params={"fmt": "json"}, timeout=20)
        exists = resp.status_code == 200
        self._cache_set(cache_key, {"exists": exists})
        return exists

    def get_release_details(self, release_mbid: str) -> dict:
        cache_key = f"release::{release_mbid}"
        payload = self._cache_get(cache_key)
        if payload is not None:
            return payload

        result = {"cover_art_url": None}
        if not release_mbid:
            return result

        self.limiter.wait()
        resp = self.http.get(f"{self.CAA_BASE}/{quote_plus(release_mbid)}", timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            images = data.get("images", [])
            if images:
                result["cover_art_url"] = images[0].get("image")

        self._cache_set(cache_key, result)
        return result
