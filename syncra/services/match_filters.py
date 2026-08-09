"""Track-matching preferences, decoupled from the widgets that used to hold them.

The smart-filter options lived only as QCheckBox state, which meant two things: the
scoring functions had to be handed a live widget to consult, and the user's choices
were lost on every restart because nothing persisted them. Both block running a sync
without a GUI, so the settings are a plain value object that the UI and the CLI can
each produce.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

# Album-title keywords and the penalty each subtracts from a candidate's score.
_LIVE_KEYWORDS = ("live", "concert", "tour")
_COMPILATION_KEYWORDS = ("best of", "greatest hits", "collection", "anthology")
_REMASTER_KEYWORDS = ("remaster", "remastered")
_DELUXE_KEYWORDS = ("deluxe", "special", "extended", "expanded", "anniversary")

_LIVE_PENALTY = 15
_COMPILATION_PENALTY = 12
_REMASTER_PENALTY = 8
_DELUXE_PENALTY = 6


@dataclass(frozen=True)
class MatchFilters:
    """Which album variants to deprioritise when several candidates tie."""

    enabled: bool = True
    avoid_live: bool = True
    avoid_compilation: bool = True
    deprioritize_remaster: bool = False
    deprioritize_deluxe: bool = False

    # ------------------------------------------------------------------ inputs

    @classmethod
    def from_config(cls, config) -> "MatchFilters":
        """Build from an app_config.json dict, falling back to the defaults."""
        section = {}
        if isinstance(config, dict):
            candidate = config.get("match_filters")
            if isinstance(candidate, dict):
                section = candidate
        defaults = cls()
        return cls(
            enabled=bool(section.get("enabled", defaults.enabled)),
            avoid_live=bool(section.get("avoid_live", defaults.avoid_live)),
            avoid_compilation=bool(section.get("avoid_compilation", defaults.avoid_compilation)),
            deprioritize_remaster=bool(
                section.get("deprioritize_remaster", defaults.deprioritize_remaster)
            ),
            deprioritize_deluxe=bool(
                section.get("deprioritize_deluxe", defaults.deprioritize_deluxe)
            ),
        )

    @classmethod
    def from_widget(cls, widget) -> "MatchFilters":
        """Read the live checkbox state off the settings page."""
        if widget is None:
            return cls()

        def checked(name, fallback):
            box = getattr(widget, name, None)
            if box is None or not hasattr(box, "isChecked"):
                return fallback
            try:
                return bool(box.isChecked())
            except Exception:
                return fallback

        defaults = cls()
        return cls(
            enabled=checked("enable_filters_checkbox", defaults.enabled),
            avoid_live=checked("filter_live_checkbox", defaults.avoid_live),
            avoid_compilation=checked("filter_compilation_checkbox", defaults.avoid_compilation),
            deprioritize_remaster=checked("filter_remaster_checkbox", defaults.deprioritize_remaster),
            deprioritize_deluxe=checked("filter_deluxe_checkbox", defaults.deprioritize_deluxe),
        )

    @classmethod
    def coerce(cls, source) -> "MatchFilters":
        """Accept whatever a caller has: filters, a dict, a widget, or nothing."""
        if isinstance(source, cls):
            return source
        if isinstance(source, dict):
            # Both a bare filter dict and a full app config are acceptable.
            if "match_filters" in source:
                return cls.from_config(source)
            return cls.from_config({"match_filters": source})
        if source is None:
            return cls()
        return cls.from_widget(source)

    # ----------------------------------------------------------------- outputs

    def to_config(self) -> dict:
        return asdict(self)

    # ------------------------------------------------------------------ scoring

    def penalty_for_album(self, album_title) -> int:
        """Total score penalty this album title earns under these settings."""
        if not self.enabled:
            return 0
        lowered = str(album_title or "").lower()
        if not lowered:
            return 0
        penalty = 0
        if self.avoid_live and any(word in lowered for word in _LIVE_KEYWORDS):
            penalty += _LIVE_PENALTY
        if self.avoid_compilation and any(word in lowered for word in _COMPILATION_KEYWORDS):
            penalty += _COMPILATION_PENALTY
        if self.deprioritize_remaster and any(word in lowered for word in _REMASTER_KEYWORDS):
            penalty += _REMASTER_PENALTY
        if self.deprioritize_deluxe and any(word in lowered for word in _DELUXE_KEYWORDS):
            penalty += _DELUXE_PENALTY
        return penalty

    def apply(self, score, album_title) -> float:
        """Return `score` reduced by this album's penalty, floored at zero."""
        try:
            return max(0.0, float(score) - self.penalty_for_album(album_title))
        except (TypeError, ValueError):
            return score
