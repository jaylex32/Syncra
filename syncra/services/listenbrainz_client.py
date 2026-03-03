"""ListenBrainz API client helpers for playlist import/export."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import requests


class ListenBrainzClient:
    BASE_URL = "https://api.listenbrainz.org/1"
    PLAYLIST_ID_RE = re.compile(
        r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
    )

    def __init__(self, token: Optional[str] = None, timeout: int = 30) -> None:
        self.token = token.strip() if token else None
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Syncra/2.20.1 (+https://github.com/jaylex32/syncra)",
            }
        )
        if self.token:
            self.session.headers.update({"Authorization": f"Token {self.token}"})

    @classmethod
    def normalize_playlist_id(cls, url_or_id: str) -> str:
        if not url_or_id:
            raise ValueError("ListenBrainz playlist ID/URL is required")
        value = url_or_id.strip()
        match = cls.PLAYLIST_ID_RE.search(value)
        if not match:
            raise ValueError("Could not extract ListenBrainz playlist ID from URL/value")
        return match.group(1).lower()

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        response = self.session.get(f"{self.BASE_URL}{path}", params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self.session.post(f"{self.BASE_URL}{path}", json=payload, timeout=self.timeout)
        if not response.ok:
            detail = ""
            try:
                data = response.json()
                if isinstance(data, dict):
                    detail = (
                        data.get("error")
                        or data.get("message")
                        or data.get("details")
                        or ""
                    )
            except Exception:
                detail = ""
            if not detail:
                detail = (response.text or "").strip()
            message = (
                f"{response.status_code} {response.reason} for url: {response.url}"
                + (f" | {detail}" if detail else "")
            )
            raise requests.HTTPError(message, response=response)
        return response.json()

    def _unwrap(self, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("payload"), dict):
            return data["payload"]
        return data

    def get_playlist(self, playlist_url_or_id: str) -> Dict[str, Any]:
        playlist_id = self.normalize_playlist_id(playlist_url_or_id)
        raw = self._get(f"/playlist/{playlist_id}")
        payload = self._unwrap(raw)
        if isinstance(payload, dict):
            if isinstance(payload.get("playlist"), dict):
                return payload["playlist"]
            if isinstance(payload.get("data"), dict) and isinstance(payload["data"].get("playlist"), dict):
                return payload["data"]["playlist"]
        raise ValueError("Unexpected ListenBrainz playlist response shape")

    def list_user_playlists(self, username: str, count: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        if not username:
            raise ValueError("ListenBrainz username is required")
        raw = self._get(f"/user/{username}/playlists", params={"count": count, "offset": offset})
        payload = self._unwrap(raw)

        playlists: List[Dict[str, Any]] = []
        if isinstance(payload, dict):
            playlist_items = payload.get("playlists") or payload.get("playlist") or []
            if isinstance(playlist_items, list):
                for item in playlist_items:
                    if not isinstance(item, dict):
                        continue
                    playlist_obj = item.get("playlist") if isinstance(item.get("playlist"), dict) else {}
                    playlist_id = (
                        playlist_obj.get("identifier")
                        or playlist_obj.get("playlist_mbid")
                        or playlist_obj.get("id")
                        or playlist_obj.get("playlist_id")
                        or item.get("identifier")
                        or item.get("playlist_mbid")
                        or item.get("id")
                        or item.get("playlist_id")
                    )
                    title = (
                        playlist_obj.get("title")
                        or playlist_obj.get("name")
                        or item.get("title")
                        or item.get("name")
                        or "Untitled"
                    )
                    track_count = (
                        item.get("track_count")
                        or playlist_obj.get("track_count")
                    )
                    if isinstance(track_count, dict):
                        track_count = track_count.get("count")
                    if playlist_id:
                        try:
                            playlist_id = self.normalize_playlist_id(str(playlist_id))
                        except ValueError:
                            # Keep raw id if it is not URL/UUID-like
                            playlist_id = str(playlist_id)
                    playlists.append(
                        {
                            "playlist_id": playlist_id,
                            "title": title,
                            "track_count": track_count if isinstance(track_count, int) else None,
                        }
                    )
        return playlists

    def get_playlist_track_count(self, playlist_url_or_id: str) -> Optional[int]:
        playlist = self.get_playlist(playlist_url_or_id)
        tracks = playlist.get("track") if isinstance(playlist, dict) else None
        if isinstance(tracks, list):
            return len(tracks)
        return None

    def create_playlist(self, playlist_jspf: Dict[str, Any]) -> Dict[str, Any]:
        raw = self._post("/playlist/create", {"playlist": playlist_jspf})
        payload = self._unwrap(raw)
        if not isinstance(payload, dict):
            return {"raw": payload}

        playlist_data = payload.get("playlist") if isinstance(payload.get("playlist"), dict) else payload
        playlist_id = (
            playlist_data.get("identifier")
            or playlist_data.get("playlist_mbid")
            or playlist_data.get("id")
            or payload.get("playlist_mbid")
            or payload.get("identifier")
        )
        try:
            playlist_id = self.normalize_playlist_id(str(playlist_id)) if playlist_id else None
        except ValueError:
            playlist_id = str(playlist_id) if playlist_id else None

        return {
            "playlist_id": playlist_id,
            "title": playlist_data.get("title") or playlist_jspf.get("title"),
            "raw": raw,
        }
