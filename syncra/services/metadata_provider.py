"""Metadata provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from syncra.models.metadata import MetadataCandidate, TrackIdentity


class MetadataProvider(ABC):
    @abstractmethod
    def search_track(self, track: TrackIdentity) -> Optional[MetadataCandidate]:
        raise NotImplementedError

    @abstractmethod
    def get_release_details(self, release_mbid: str) -> dict:
        raise NotImplementedError
