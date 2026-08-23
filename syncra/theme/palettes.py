"""Colour palettes.

Every colour the interface uses lives here, named for the job it does rather than for
the colour it happens to be -- `bg_1` is "the surface inputs and lists sit on", not
"dark navy". That is what lets a light theme work: the roles stay the same and only the
values invert.

`midnight` reproduces the original palette exactly, so the default look is unchanged.

Adding a theme means filling in every key; `tests/test_themes.py` fails if one is
missing, because a missing key is an invisible hole that only shows up on whichever
screen happens to use it.
"""

from __future__ import annotations

# Keys every palette must define. Grouped by role for readability.
PALETTE_KEYS = (
    # Surfaces, darkest to lightest in a dark theme (reversed in a light one)
    "bg_0", "bg_1", "bg_2", "bg_3",
    "sidebar", "gradient_end", "card",
    "header_a", "header_b", "hero_a", "hero_b", "section_a", "section_b",
    # Text
    "txt_0", "txt_1", "txt_title", "txt_muted", "txt_subtle",
    "txt_metric", "txt_hero", "txt_sidebar_group", "on_accent",
    # Brand
    "accent", "accent_hover", "accent_pressed", "accent_ok",
    # Lines
    "border", "border_soft", "border_section",
    "border_scroll", "border_scroll_handle",
    "sidebar_rule", "sidebar_divider",
    # Scrollbars
    "scroll_handle", "scroll_handle_hover", "scroll_handle_active",
    # Status families: background / border / foreground
    "ok_bg", "ok_border", "ok_fg",
    "warn_bg", "warn_border", "warn_fg",
    "danger_bg", "danger_border", "danger_fg",
    "neutral_bg", "neutral_border", "neutral_fg",
    "chip_accent_bg", "chip_accent_border", "chip_accent_fg",
    # Destructive / positive button hovers
    "danger_hover", "success_hover",
    # Disabled controls
    "disabled_bg", "disabled_fg", "disabled_border",
    # Generated playlist tiles: eight gradient pairs, "top,bottom"
    "tile_1", "tile_2", "tile_3", "tile_4", "tile_5", "tile_6", "tile_7", "tile_8",
)


MIDNIGHT = {
    "name": "Midnight",
    "description": "Deep navy with a neon cyan accent. Syncra's original look.",
    "dark": True,

    "bg_0": "#111a28", "bg_1": "#1a2537", "bg_2": "#25344b", "bg_3": "#314664",
    "sidebar": "#121722", "gradient_end": "#0f1b30", "card": "#202d43",
    "header_a": "#1f2a3b", "header_b": "#1a2232",
    "hero_a": "#1d2f47", "hero_b": "#1b2335",
    "section_a": "#1e2b3f", "section_b": "#1a2231",

    "txt_0": "#f5f7fb", "txt_1": "#c9d1df", "txt_title": "#f8fbff",
    "txt_muted": "#a8b9cf", "txt_subtle": "#b9c8dc", "txt_metric": "#d9e7ff",
    "txt_hero": "#c7d4e8", "txt_sidebar_group": "#8fa1ba", "on_accent": "#111a28",

    "accent": "#2fb8ff", "accent_hover": "#57c7ff", "accent_pressed": "#1a9fe0",
    "accent_ok": "#2ed27a",

    "border": "#3f516f", "border_soft": "#44516c", "border_section": "#42506a",
    "border_scroll": "#2f4360", "border_scroll_handle": "#49648b",
    "sidebar_rule": "#232f42", "sidebar_divider": "#2b3a52",

    "scroll_handle": "#2a3f5e", "scroll_handle_hover": "#35527a",
    "scroll_handle_active": "#3f6291",

    "ok_bg": "#1f3a2a", "ok_border": "#2ed27a", "ok_fg": "#90f3c1",
    "warn_bg": "#3a2b1f", "warn_border": "#f9a93b", "warn_fg": "#ffd399",
    "danger_bg": "#3a1d22", "danger_border": "#7a3b44", "danger_fg": "#ffd9d9",
    "neutral_bg": "#243047", "neutral_border": "#486089", "neutral_fg": "#cfe0ff",
    "chip_accent_bg": "#1f2f40", "chip_accent_border": "#2fb8ff",
    "chip_accent_fg": "#8ad8ff",

    "danger_hover": "#4a262c", "success_hover": "#26482f",
    "disabled_bg": "#1b2434", "disabled_fg": "#6d7c93", "disabled_border": "#2c3a52",

    "tile_1": "#243a57,#16233a", "tile_2": "#1f3f4d,#152833",
    "tile_3": "#2b3350,#181d31", "tile_4": "#1d4450,#122a33",
    "tile_5": "#333350,#1d1d31", "tile_6": "#204a48,#122b2a",
    "tile_7": "#2a3a60,#171f38", "tile_8": "#3a2f4f,#211a2e",
}


CARBON = {
    "name": "Carbon",
    "description": "Near-black greys for OLED screens and dark rooms.",
    "dark": True,

    "bg_0": "#0b0b0d", "bg_1": "#141416", "bg_2": "#1e1e21", "bg_3": "#2c2c31",
    "sidebar": "#000000", "gradient_end": "#0b0b0d", "card": "#1a1a1d",
    "header_a": "#1a1a1d", "header_b": "#141416",
    "hero_a": "#1f1f23", "hero_b": "#151517",
    "section_a": "#1a1a1d", "section_b": "#141416",

    "txt_0": "#f2f2f4", "txt_1": "#c4c4c9", "txt_title": "#ffffff",
    "txt_muted": "#9a9aa2", "txt_subtle": "#b0b0b8", "txt_metric": "#e6e6ea",
    "txt_hero": "#c0c0c8", "txt_sidebar_group": "#7d7d86", "on_accent": "#0b0b0d",

    "accent": "#2fb8ff", "accent_hover": "#5cc8ff", "accent_pressed": "#1d9ade",
    "accent_ok": "#3ad07f",

    "border": "#33333a", "border_soft": "#3d3d45", "border_section": "#33333a",
    "border_scroll": "#2a2a30", "border_scroll_handle": "#4a4a53",
    "sidebar_rule": "#1c1c20", "sidebar_divider": "#26262b",

    "scroll_handle": "#2e2e34", "scroll_handle_hover": "#3d3d45",
    "scroll_handle_active": "#4c4c56",

    "ok_bg": "#122b1c", "ok_border": "#3ad07f", "ok_fg": "#8fecb9",
    "warn_bg": "#31240f", "warn_border": "#f0a836", "warn_fg": "#ffd28f",
    "danger_bg": "#301418", "danger_border": "#7c3b43", "danger_fg": "#ffd2d2",
    "neutral_bg": "#212127", "neutral_border": "#4a4a53", "neutral_fg": "#d2d2da",
    "chip_accent_bg": "#12232e", "chip_accent_border": "#2fb8ff",
    "chip_accent_fg": "#8ad8ff",

    "danger_hover": "#3d1a20", "success_hover": "#173a24",
    "disabled_bg": "#161619", "disabled_fg": "#6a6a72", "disabled_border": "#2a2a30",

    "tile_1": "#2a2a30,#141416", "tile_2": "#1f3038,#121a1e",
    "tile_3": "#2c2836,#17151d", "tile_4": "#16333a,#0e1e22",
    "tile_5": "#332c2c,#1c1818", "tile_6": "#1c3a33,#10201d",
    "tile_7": "#242c3d,#131722", "tile_8": "#33263a,#1b1420",
}


SLATE = {
    "name": "Slate",
    "description": "Neutral grey with a teal accent; softer contrast than Midnight.",
    "dark": True,

    "bg_0": "#181b1f", "bg_1": "#212529", "bg_2": "#2b3036", "bg_3": "#3a4149",
    "sidebar": "#15181b", "gradient_end": "#15181b", "card": "#252a30",
    "header_a": "#272c33", "header_b": "#212529",
    "hero_a": "#2a3138", "hero_b": "#222629",
    "section_a": "#252a30", "section_b": "#1f2327",

    "txt_0": "#eef1f4", "txt_1": "#c2c9d1", "txt_title": "#ffffff",
    "txt_muted": "#98a2ad", "txt_subtle": "#adb6c0", "txt_metric": "#dfe6ed",
    "txt_hero": "#bcc5cf", "txt_sidebar_group": "#7e8894", "on_accent": "#10221f",

    "accent": "#33c9b6", "accent_hover": "#57d8c8", "accent_pressed": "#26a898",
    "accent_ok": "#5bc98a",

    "border": "#3b434c", "border_soft": "#454e58", "border_section": "#3b434c",
    "border_scroll": "#2f363d", "border_scroll_handle": "#4d5761",
    "sidebar_rule": "#22262b", "sidebar_divider": "#2c3238",

    "scroll_handle": "#333a42", "scroll_handle_hover": "#414a54",
    "scroll_handle_active": "#4f5964",

    "ok_bg": "#1c3327", "ok_border": "#5bc98a", "ok_fg": "#a5e8c1",
    "warn_bg": "#352a19", "warn_border": "#e0a44a", "warn_fg": "#f5d6a3",
    "danger_bg": "#33201f", "danger_border": "#7d4340", "danger_fg": "#f2cfcd",
    "neutral_bg": "#282e34", "neutral_border": "#4d5761", "neutral_fg": "#ccd4dc",
    "chip_accent_bg": "#16302d", "chip_accent_border": "#33c9b6",
    "chip_accent_fg": "#8fe4d8",

    "danger_hover": "#402725", "success_hover": "#22412f",
    "disabled_bg": "#1e2226", "disabled_fg": "#6b747d", "disabled_border": "#31383f",

    "tile_1": "#2f3a44,#1c2228", "tile_2": "#26403f,#161f1f",
    "tile_3": "#333244,#1e1d28", "tile_4": "#1f4243,#132728",
    "tile_5": "#3b3340,#221e26", "tile_6": "#24443a,#152722",
    "tile_7": "#2b3648,#191f2a", "tile_8": "#3d3140,#241d27",
}


AURORA = {
    "name": "Aurora",
    "description": "Deep indigo with a magenta accent.",
    "dark": True,

    "bg_0": "#15132a", "bg_1": "#1e1b3a", "bg_2": "#2a2550", "bg_3": "#3a3370",
    "sidebar": "#120f24", "gradient_end": "#120f24", "card": "#241f47",
    "header_a": "#241f47", "header_b": "#1c1936",
    "hero_a": "#2b2352", "hero_b": "#1d1a38",
    "section_a": "#241f47", "section_b": "#1c1936",

    "txt_0": "#f4f1fb", "txt_1": "#cfc7e6", "txt_title": "#ffffff",
    "txt_muted": "#a79ec6", "txt_subtle": "#bcb3d6", "txt_metric": "#e2daf7",
    "txt_hero": "#c8bfe2", "txt_sidebar_group": "#8f85b0", "on_accent": "#1a0f22",

    "accent": "#e05fc4", "accent_hover": "#ec81d3", "accent_pressed": "#c14aa6",
    "accent_ok": "#4fd6a0",

    "border": "#453d78", "border_soft": "#4f4685", "border_section": "#453d78",
    "border_scroll": "#332d5c", "border_scroll_handle": "#584f92",
    "sidebar_rule": "#221e40", "sidebar_divider": "#2c2751",

    "scroll_handle": "#332d5c", "scroll_handle_hover": "#443c76",
    "scroll_handle_active": "#554b90",

    "ok_bg": "#16342a", "ok_border": "#4fd6a0", "ok_fg": "#9df0cd",
    "warn_bg": "#3a2c1c", "warn_border": "#f0ad4a", "warn_fg": "#ffd9a0",
    "danger_bg": "#3a1c2c", "danger_border": "#8a3d5e", "danger_fg": "#ffd3e2",
    "neutral_bg": "#282350", "neutral_border": "#584f92", "neutral_fg": "#d5cdf0",
    "chip_accent_bg": "#341c33", "chip_accent_border": "#e05fc4",
    "chip_accent_fg": "#f2a9e0",

    "danger_hover": "#4a2438", "success_hover": "#1d4436",
    "disabled_bg": "#1f1b3a", "disabled_fg": "#736a95", "disabled_border": "#332d5c",

    "tile_1": "#3a2f66,#1f1a3c", "tile_2": "#4a2a5e,#261634",
    "tile_3": "#2c3570,#171d3e", "tile_4": "#5a2a52,#30162c",
    "tile_5": "#33306e,#1b1a3d", "tile_6": "#24406a,#13223a",
    "tile_7": "#4a2f70,#28193e", "tile_8": "#602f52,#33192c",
}


DAYLIGHT = {
    "name": "Daylight",
    "description": "Light theme for bright rooms.",
    "dark": False,

    "bg_0": "#eef1f6", "bg_1": "#ffffff", "bg_2": "#e4e9f1", "bg_3": "#d2dcea",
    "sidebar": "#ffffff", "gradient_end": "#e6ebf3", "card": "#ffffff",
    "header_a": "#ffffff", "header_b": "#f4f7fb",
    "hero_a": "#e8eef8", "hero_b": "#f6f8fc",
    "section_a": "#ffffff", "section_b": "#f6f8fc",

    "txt_0": "#16202f", "txt_1": "#44546e", "txt_title": "#0d1521",
    "txt_muted": "#5f6f88", "txt_subtle": "#51617a", "txt_metric": "#16202f",
    "txt_hero": "#3c4c66", "txt_sidebar_group": "#75849c", "on_accent": "#ffffff",

    "accent": "#0b76b8", "accent_hover": "#1189d2", "accent_pressed": "#095f95",
    "accent_ok": "#127a45",

    "border": "#c3cede", "border_soft": "#b3c0d3", "border_section": "#c3cede",
    "border_scroll": "#d4dce8", "border_scroll_handle": "#a8b6ca",
    "sidebar_rule": "#e2e8f1", "sidebar_divider": "#d3dbe7",

    "scroll_handle": "#c2ccdb", "scroll_handle_hover": "#aab7ca",
    "scroll_handle_active": "#93a3ba",

    "ok_bg": "#dff4e7", "ok_border": "#127a45", "ok_fg": "#0c5c33",
    "warn_bg": "#fdf0d8", "warn_border": "#b57611", "warn_fg": "#7d5109",
    "danger_bg": "#fbe0e2", "danger_border": "#b13d47", "danger_fg": "#8a2731",
    "neutral_bg": "#e7edf6", "neutral_border": "#9fb0c8", "neutral_fg": "#33445e",
    "chip_accent_bg": "#ddeefb", "chip_accent_border": "#0b76b8",
    "chip_accent_fg": "#07496f",

    "danger_hover": "#f6ccd0", "success_hover": "#cceedb",
    "disabled_bg": "#eaeef5", "disabled_fg": "#93a0b4", "disabled_border": "#ced7e4",

    "tile_1": "#c9d8ec,#a9bedb", "tile_2": "#c6e4e2,#a3ccca",
    "tile_3": "#d4d2ee,#b4b1dd", "tile_4": "#bfe2ea,#9cc9d4",
    "tile_5": "#e0d3e8,#c4b0d3", "tile_6": "#c9e8d8,#a5d2bd",
    "tile_7": "#cdd6ef,#adbade", "tile_8": "#eed6df,#d8b0c1",
}


THEMES = {
    "midnight": MIDNIGHT,
    "carbon": CARBON,
    "slate": SLATE,
    "aurora": AURORA,
    "daylight": DAYLIGHT,
}

DEFAULT_THEME = "midnight"


def get_palette(name) -> dict:
    """Return a copy of a palette, falling back to the default for unknown names."""
    key = str(name or "").strip().lower()
    return dict(THEMES.get(key, THEMES[DEFAULT_THEME]))


def theme_names() -> list:
    return list(THEMES.keys())


def tile_gradients(palette) -> tuple:
    """The eight generated-cover gradients as (top, bottom) pairs."""
    pairs = []
    for index in range(1, 9):
        value = str(palette.get(f"tile_{index}", "") or "")
        top, _, bottom = value.partition(",")
        if top and bottom:
            pairs.append((top.strip(), bottom.strip()))
    return tuple(pairs)
