"""Configuration defaults and merge helpers for Syncra."""

from __future__ import annotations

from copy import deepcopy

APP_CONFIG_DEFAULTS = {
    "plex_username": "",
    "server_ip": "127.0.0.1",
    "server_port": "32400",
    "token": "",
    "listenbrainz_token": "",
    "listenbrainz_user": "",
    "plex_server_profiles": [],
    "server_sync_policy": "keep_extras",
    "server_sync_jobs": [],
    "apple_music_xml_path": "",
    "apple_music_import_ratings": True,
    "last_section": None,
    "playlist_view_mode": "grid",
    "theme": "midnight",
    "auto_backup": True,
    "backup_interval": 24,
    "features": {
        "metadata_fixer": False,
        "ui_refresh_v2": False,
        "auto_fetch_playlists_on_startup": False,
    },
    "match_filters": {
        "enabled": True,
        "avoid_live": True,
        "avoid_compilation": True,
        "deprioritize_remaster": False,
        "deprioritize_deluxe": False,
    },
    "smart_match": {
        "persist_cache": True,
        "preload_on_connect": True,
        "cache_db": "smart_match_cache.sqlite",
    },
    "metadata": {
        "user_agent": "Syncra/2.20.3 (metadata-fixer; contact: github.com/jaylex32/syncra)",
        "rate_limit_rps": 1.0,
        "cache_ttl_hours": 168,
        "auto_apply_threshold": 95,
        "review_threshold": 80,
    },
}

SYNC_CONFIG_DEFAULTS = {
    "sync_playlists": {},
    "auto_sync": False,
    "sync_interval": 60,
    "scheduled_sync_enabled": False,
    "scheduled_sync_datetime": "",
    "scheduled_sync_repeat": "once",
}

CACHE_DEFAULTS = {
    "playlists": {},
    "last_updated": {},
    "version": "1.0",
}


def deep_merge(base: dict, override: dict) -> dict:
    """Return a deep-merged dict where override keys take precedence."""
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
