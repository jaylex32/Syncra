"""Metadata fixer model types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TrackIdentity:
    rating_key: str
    title: str
    artist: str
    album: str
    year: Optional[int] = None
    plex_track: Any = None


@dataclass
class MetadataCandidate:
    source: str
    title: str
    artist: str
    album: str
    year: Optional[int] = None
    genre: Optional[str] = None
    recording_mbid: Optional[str] = None
    release_mbid: Optional[str] = None
    cover_art_url: Optional[str] = None
    score: float = 0.0


@dataclass
class MetadataProposal:
    track: TrackIdentity
    candidate: MetadataCandidate
    confidence: float
    changes: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class MetadataApplyResult:
    rating_key: str
    success: bool
    applied_fields: List[str] = field(default_factory=list)
    error: str = ""
    timestamp: str = ""
