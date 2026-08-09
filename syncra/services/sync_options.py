"""Everything a playlist sync needs to know that is not the playlist itself.

SyncThread used to read these three values live off its parent widget in the middle of
a run -- the M3U matching mode from a radio button, the ListenBrainz token from a line
edit, and the smart filters from four checkboxes. Resolving them up front into a plain
object is what makes the same sync runnable from a scheduled task with no GUI attached.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from syncra.services.match_filters import MatchFilters


@dataclass
class SyncOptions:
    use_smart_matching: bool = False
    listenbrainz_token: str = ""
    match_filters: MatchFilters = field(default_factory=MatchFilters)

    @classmethod
    def from_config(cls, config) -> "SyncOptions":
        """Build from a loaded app_config.json dict."""
        config = config if isinstance(config, dict) else {}
        return cls(
            use_smart_matching=bool(config.get("m3u_use_smart_matching", False)),
            listenbrainz_token=str(config.get("listenbrainz_token", "") or "").strip(),
            match_filters=MatchFilters.from_config(config),
        )

    @classmethod
    def from_widget(cls, widget) -> "SyncOptions":
        """Snapshot the live UI state at the moment a sync starts."""
        if widget is None:
            return cls()

        use_smart_matching = False
        radio = getattr(widget, "m3u_smart_matching_radio", None)
        if radio is not None and hasattr(radio, "isChecked"):
            try:
                use_smart_matching = bool(radio.isChecked())
            except Exception:
                use_smart_matching = False

        listenbrainz_token = ""
        token_input = getattr(widget, "listenbrainz_token_input", None)
        if token_input is not None and hasattr(token_input, "text"):
            try:
                listenbrainz_token = str(token_input.text() or "").strip()
            except Exception:
                listenbrainz_token = ""

        return cls(
            use_smart_matching=use_smart_matching,
            listenbrainz_token=listenbrainz_token,
            match_filters=MatchFilters.from_widget(widget),
        )
