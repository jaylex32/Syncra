"""Centralized design system and QSS theme for Syncra.

Colours come from a palette in `palettes.py` rather than being fixed here, so the whole
interface can be re-themed. `TOKENS` holds the *active* palette and is updated in place
by `set_theme()` -- in place matters, because modules that painted with these values
imported the dict once at start-up and would otherwise keep the old colours forever.

Everything else (spacing, radii, type scale, states) is derived from a small set of
constants instead of being chosen per widget. Layout code should import SPACE_*,
RADIUS_* and FONT_* rather than hardcoding numbers, so Python-side margins stay in
sync with the QSS.
"""

from .palettes import DEFAULT_THEME, THEMES, get_palette, theme_names, tile_gradients

# The live palette. Mutated in place by set_theme(); never rebound.
TOKENS = get_palette(DEFAULT_THEME)

_active_theme = DEFAULT_THEME


def current_theme() -> str:
    """Key of the palette currently applied."""
    return _active_theme


def is_dark() -> bool:
    return bool(TOKENS.get("dark", True))


def available_themes() -> list:
    """[(key, display name, description), ...] for the settings picker."""
    return [
        (key, palette.get("name", key.title()), palette.get("description", ""))
        for key, palette in THEMES.items()
    ]


def set_theme(name) -> str:
    """Switch the active palette and return the stylesheet for it.

    TOKENS is updated in place so painting code that captured the dict at import time
    sees the new colours without being reloaded.
    """
    global _active_theme
    palette = get_palette(name)
    TOKENS.clear()
    TOKENS.update(palette)
    _active_theme = str(name or DEFAULT_THEME).strip().lower()
    if _active_theme not in THEMES:
        _active_theme = DEFAULT_THEME
    return build_stylesheet(TOKENS)


def build_qpalette(p=None):
    """A QPalette matching the active theme.

    The stylesheet covers everything Syncra styles by name, but any widget that falls
    back to Qt's own painting -- scroll-area viewports, native dialogs, message boxes,
    item-view backgrounds -- uses the palette instead. Leaving it on the dark default
    is why a light theme showed black panels behind styled content.
    """
    from PyQt6.QtGui import QColor, QPalette

    p = p or TOKENS
    palette = QPalette()
    R = QPalette.ColorRole
    G = QPalette.ColorGroup

    pairs = {
        R.Window: p["bg_0"],
        R.WindowText: p["txt_0"],
        R.Base: p["bg_1"],
        R.AlternateBase: p["bg_2"],
        R.Text: p["txt_0"],
        R.Button: p["bg_2"],
        R.ButtonText: p["txt_0"],
        R.BrightText: p["txt_title"],
        R.Highlight: p["accent"],
        R.HighlightedText: p["on_accent"],
        R.ToolTipBase: p["header_a"],
        R.ToolTipText: p["txt_0"],
        R.PlaceholderText: p["txt_muted"],
        R.Link: p["accent"],
        R.LinkVisited: p["accent_pressed"],
        R.Light: p["bg_3"],
        R.Midlight: p["bg_2"],
        R.Mid: p["border"],
        R.Dark: p["bg_0"],
        R.Shadow: p["gradient_end"],
    }
    for role, value in pairs.items():
        palette.setColor(role, QColor(value))

    for role, value in (
        (R.WindowText, p["disabled_fg"]),
        (R.Text, p["disabled_fg"]),
        (R.ButtonText, p["disabled_fg"]),
        (R.Base, p["disabled_bg"]),
        (R.Button, p["disabled_bg"]),
    ):
        palette.setColor(G.Disabled, role, QColor(value))

    return palette


def tile_palette() -> tuple:
    """Gradient pairs for generated playlist tiles under the active palette."""
    return tile_gradients(TOKENS)


# ---------------------------------------------------------------------------
# Spacing - strict 4px grid. Import these in layout code.
# ---------------------------------------------------------------------------

SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24

PAGE_MARGIN = SPACE_LG      # outer padding of every page
PAGE_SPACING = SPACE_MD     # gap between cards on a page
GROUP_MARGIN = SPACE_LG     # inner padding of a QGroupBox
GROUP_SPACING = SPACE_SM    # gap between rows inside a group
FIELD_SPACING = SPACE_SM    # gap between controls in a form row

CONTROL_HEIGHT = 34         # single height for buttons, inputs, combos
ROW_HEIGHT = 40             # table rows
LABEL_COLUMN = 148          # shared width of the right-aligned form label column,
                            # so fields start on the same x across stacked cards
ACTION_BUTTON_WIDTH = 300   # cap for grid action buttons so they never span the pane
FIELD_MAX_WIDTH = 620       # cap for single-line inputs. Pages fill the window -- a
                            # desktop app with a dead column on the right looks broken
                            # -- so the measure is enforced on the fields that would
                            # otherwise become unreadably long, not on the page.
# Narrower equivalents for fields living inside a side column rather than spanning a
# page. FIELD_MIN_WIDTH would give a two-column page a minimum wider than the column.
SIDE_FIELD_MIN = 180
SIDE_LABEL_COLUMN = 104

FIELD_MIN_WIDTH = 440       # keeps a capped field from collapsing to a QLineEdit's
                            # very small default size hint inside a grid cell

# ---------------------------------------------------------------------------
# Radii - 6px on interactive controls, larger on containers.
# ---------------------------------------------------------------------------

RADIUS_CONTROL = 6
RADIUS_CARD = 10
RADIUS_PANEL = 12
RADIUS_PILL = 999

# ---------------------------------------------------------------------------
# Typography. No fonts are bundled, so this is a system stack that degrades
# predictably: Segoe UI on Windows, then common cross-platform fallbacks.
# ---------------------------------------------------------------------------

FONT_STACK = "'Segoe UI', 'Inter', 'Helvetica Neue', Arial, sans-serif"

FS_DISPLAY = 24    # dashboard hero
FS_TITLE = 20      # page title
FS_SECTION = 16    # section header card
FS_GROUP = 12      # group box titles (uppercase, tracked)
FS_BODY = 13       # default
FS_SECONDARY = 12  # helper text, subtitles
FS_MICRO = 11      # chips, status, timestamps

W_REGULAR = 400
W_MEDIUM = 500
W_SEMIBOLD = 600
W_BOLD = 700
W_HEAVY = 800


def _chip(name, bg, border, fg):
    """Build the QSS block for a status chip / badge."""
    return f"""
#{name} {{
    background-color: {bg};
    border: 1px solid {border};
    color: {fg};
}}"""


def build_stylesheet(p=None):
    """Render the full QSS for a palette (the active one by default)."""
    p = p or TOKENS
    return f"""
/* ---------------------------------------------------------------- base ---- */
QMainWindow, QMessageBox, QMenu, QDialog {{
    background-color: {p['bg_0']};
    color: {p['txt_0']};
}}
QWidget {{
    color: {p['txt_0']};
    font-family: {FONT_STACK};
    font-size: {FS_BODY}px;
}}
QLabel {{
    background: transparent;
}}
QToolTip {{
    background-color: {p['header_a']};
    color: {p['txt_0']};
    border: 1px solid {p['border']};
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_XS}px {SPACE_SM}px;
    font-size: {FS_SECONDARY}px;
}}

/* --------------------------------------------------- semantic label states --
   Set with the dynamic property `status`, so a label's colour follows the theme
   instead of being frozen by an inline stylesheet at construction time. */
QLabel[status="muted"] {{
    color: {p['txt_muted']};
}}
QLabel[status="info"] {{
    color: {p['accent']};
}}
QLabel[status="ok"] {{
    color: {p['ok_border']};
    font-weight: {W_SEMIBOLD};
}}
QLabel[status="warn"] {{
    color: {p['warn_border']};
    font-weight: {W_SEMIBOLD};
}}
QLabel[status="danger"] {{
    color: {p['danger_border']};
    font-weight: {W_SEMIBOLD};
}}
QWidget[surface="sunken"] {{
    background-color: {p['bg_1']};
    border-radius: {RADIUS_CONTROL}px;
}}
QLabel[status="notice"] {{
    color: {p['txt_subtle']};
    background-color: {p['bg_1']};
    border: 1px solid {p['border']};
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_SM}px {SPACE_MD}px;
}}

/* ------------------------------------------------------------- shell ------ */
#leftSidebar {{
    background-color: {p['sidebar']};
    border-right: 1px solid {p['border']};
}}
#mainContentSurface {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {p['sidebar']}, stop:1 {p['gradient_end']});
}}
#mainContentStack {{
    background: transparent;
    border: none;
}}
#pageScrollArea {{
    background: transparent;
    border: none;
}}
#contentPage {{
    background: transparent;
}}
#sidebarGroupLabel {{
    color: {p['txt_sidebar_group']};
    font-size: {FS_MICRO}px;
    font-weight: {W_BOLD};
    letter-spacing: 0.08em;
    padding: {SPACE_SM}px {SPACE_SM}px {SPACE_XS}px {SPACE_SM}px;
}}

/* Section captions sit below nav items in the hierarchy, so they are smaller and
   dimmer than an inactive item and are never mistaken for one. */
#sidebarSection {{
    background: transparent;
}}
#sidebarSectionLabel {{
    color: {p['txt_sidebar_group']};
    font-size: 10px;
    font-weight: {W_BOLD};
    letter-spacing: 0.14em;
    background: transparent;
}}
#sidebarSectionRule {{
    background-color: {p['sidebar_rule']};
    border: none;
}}
#sidebarDivider {{
    background-color: {p['sidebar_divider']};
    border: none;
}}
#sidebarFooterText {{
    color: {p['txt_sidebar_group']};
    font-size: {FS_MICRO}px;
    font-weight: {W_MEDIUM};
    background: transparent;
}}
#sidebarStatusDot {{
    color: {p['disabled_fg']};
    font-size: {FS_BODY}px;
    background: transparent;
}}
#sidebarStatusDot[state="connected"] {{
    color: {p['accent_ok']};
}}

/* Sidebar navigation: flat by default, cyan left rail when active. */
#sidebarNavButton {{
    background: transparent;
    border: 1px solid transparent;
    border-left: 3px solid transparent;
    border-radius: {RADIUS_CONTROL}px;
    /* Tighter right padding: 'Tools & Utilities' clipped against the sidebar edge. */
    padding: {SPACE_XS}px {SPACE_SM}px {SPACE_XS}px {SPACE_MD}px;
    margin: 0;
    text-align: left;
    font-size: {FS_BODY}px;
    font-weight: {W_MEDIUM};
    color: {p['txt_1']};
    /* ~40px rows. The previous 34px min-height plus 8px padding produced 54px items,
       which spread nine entries over the full column height. */
    min-height: 32px;
}}
#sidebarNavButton:hover {{
    background-color: {p['bg_1']};
    color: {p['txt_0']};
    border-left-color: {p['border']};
}}
#sidebarNavButton:pressed {{
    background-color: {p['bg_2']};
}}
#sidebarNavButton[active="true"] {{
    background-color: {p['chip_accent_bg']};
    color: {p['chip_accent_fg']};
    border-left: 3px solid {p['accent']};
    font-weight: {W_SEMIBOLD};
}}
#sidebarNavButton:focus {{
    border-color: {p['accent']};
}}

/* -------------------------------------------------------- page header ----- */
#topHeaderCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {p['header_a']}, stop:1 {p['header_b']});
    border: 1px solid {p['border']};
    border-radius: {RADIUS_PANEL}px;
}}
#pageTitle {{
    font-size: {FS_TITLE}px;
    font-weight: {W_BOLD};
    color: {p['txt_title']};
    letter-spacing: -0.01em;
}}
#pageSubtitle {{
    font-size: {FS_SECONDARY}px;
    font-weight: {W_REGULAR};
    color: {p['txt_muted']};
}}
#sectionHeaderCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {p['section_a']}, stop:1 {p['section_b']});
    border: 1px solid {p['border_section']};
    border-radius: {RADIUS_PANEL}px;
}}
#sectionHeaderTitle {{
    font-size: {FS_SECTION}px;
    font-weight: {W_BOLD};
    color: {p['txt_title']};
    letter-spacing: -0.01em;
}}
#sectionHeaderSubtitle {{
    font-size: {FS_SECONDARY}px;
    color: {p['txt_subtle']};
}}

/* ------------------------------------------------------------- chips ------ */
#headerChipOk, #headerChipWarn, #headerChipNeutral,
#headerChipAccent, #headerChipDanger {{
    border-radius: {RADIUS_PILL}px;
    padding: {SPACE_XS}px {SPACE_MD}px;
    font-size: {FS_MICRO}px;
    font-weight: {W_BOLD};
    letter-spacing: 0.04em;
    min-height: 18px;
}}
{_chip('headerChipOk', p['ok_bg'], p['ok_border'], p['ok_fg'])}
{_chip('headerChipWarn', p['warn_bg'], p['warn_border'], p['warn_fg'])}
{_chip('headerChipNeutral', p['neutral_bg'], p['neutral_border'], p['neutral_fg'])}
{_chip('headerChipAccent', p['chip_accent_bg'], p['chip_accent_border'], p['chip_accent_fg'])}
{_chip('headerChipDanger', p['danger_bg'], p['danger_border'], p['danger_fg'])}

/* Inline status banners share the chip palette at card scale. */
#connectionBanner, #statusBannerDanger {{
    background-color: {p['danger_bg']};
    border: 1px solid {p['danger_border']};
    color: {p['danger_fg']};
    border-radius: {RADIUS_CARD}px;
    padding: {SPACE_MD}px;
    font-size: {FS_SECONDARY}px;
}}
#statusBannerOk {{
    background-color: {p['ok_bg']};
    border: 1px solid {p['ok_border']};
    color: {p['ok_fg']};
    border-radius: {RADIUS_CARD}px;
    padding: {SPACE_MD}px;
    font-size: {FS_SECONDARY}px;
}}
#statusBannerInfo, #infoNote {{
    background-color: {p['chip_accent_bg']};
    border: 1px solid {p['border']};
    color: {p['chip_accent_fg']};
    border-radius: {RADIUS_CARD}px;
    padding: {SPACE_MD}px;
    font-size: {FS_SECONDARY}px;
}}
#helperText {{
    color: {p['txt_subtle']};
    font-size: {FS_SECONDARY}px;
}}
#mutedText {{
    color: {p['txt_muted']};
    font-size: {FS_SECONDARY}px;
}}

/* --------------------------------------------------------- dashboard ------ */
#dashboardHeroCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {p['hero_a']}, stop:1 {p['hero_b']});
    border: 1px solid {p['border_soft']};
    border-radius: {RADIUS_PANEL}px;
}}
#dashboardHeroTitle {{
    font-size: {FS_DISPLAY}px;
    font-weight: {W_HEAVY};
    color: {p['txt_title']};
    letter-spacing: -0.02em;
}}
#dashboardHeroSubtitle {{
    font-size: {FS_BODY}px;
    color: {p['txt_hero']};
}}
#dashboardMetricCard {{
    background-color: rgba(17, 26, 40, 0.55);
    border: 1px solid {p['border_soft']};
    border-radius: {RADIUS_CARD}px;
}}
#metricCaption {{
    color: {p['txt_muted']};
    font-size: {FS_MICRO}px;
    font-weight: {W_SEMIBOLD};
    letter-spacing: 0.08em;
    text-transform: uppercase;
}}
#metricValue {{
    color: {p['txt_title']};
    font-size: {FS_TITLE}px;
    font-weight: {W_BOLD};
    letter-spacing: -0.01em;
}}

/* ----------------------------------------------------------- buttons ------ */
/* No margin here: spacing belongs to the layout, not the widget. */
QPushButton {{
    background-color: {p['bg_2']};
    border: 1px solid {p['border']};
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_SM}px {SPACE_LG}px;
    min-height: {CONTROL_HEIGHT - 18}px;
    color: {p['txt_0']};
    font-size: {FS_BODY}px;
    font-weight: {W_MEDIUM};
}}
QPushButton:hover {{
    background-color: {p['bg_3']};
    border-color: {p['border_scroll_handle']};
}}
QPushButton:pressed {{
    background-color: {p['bg_1']};
    border-color: {p['border']};
}}
QPushButton:focus {{
    border: 1px solid {p['accent']};
}}
QPushButton:disabled {{
    background-color: {p['disabled_bg']};
    border-color: {p['disabled_border']};
    color: {p['disabled_fg']};
}}
QPushButton:checked {{
    background-color: {p['chip_accent_bg']};
    border-color: {p['accent']};
    color: {p['chip_accent_fg']};
}}
/* Primary action: the only filled cyan control on a page. */
QPushButton[variant="primary"] {{
    background-color: {p['accent']};
    border: 1px solid {p['accent']};
    color: {p['on_accent']};
    font-weight: {W_SEMIBOLD};
}}
QPushButton[variant="primary"]:hover {{
    background-color: {p['accent_hover']};
    border-color: {p['accent_hover']};
}}
QPushButton[variant="primary"]:pressed {{
    background-color: {p['accent_pressed']};
    border-color: {p['accent_pressed']};
}}
QPushButton[variant="primary"]:disabled {{
    background-color: {p['disabled_bg']};
    border-color: {p['disabled_border']};
    color: {p['disabled_fg']};
}}
QPushButton[variant="danger"] {{
    background-color: {p['danger_bg']};
    border: 1px solid {p['danger_border']};
    color: {p['danger_fg']};
}}
QPushButton[variant="danger"]:hover {{
    background-color: {p['danger_hover']};
}}
QPushButton[variant="success"] {{
    background-color: {p['ok_bg']};
    border: 1px solid {p['ok_border']};
    color: {p['ok_fg']};
}}
QPushButton[variant="success"]:hover {{
    background-color: {p['success_hover']};
}}
QPushButton[variant="ghost"] {{
    background: transparent;
    border: 1px solid transparent;
    color: {p['txt_1']};
}}
QPushButton[variant="ghost"]:hover {{
    background-color: {p['bg_1']};
    color: {p['txt_0']};
}}

/* ------------------------------------------------------------ inputs ------ */
QLineEdit, QTextEdit, QPlainTextEdit, QDateTimeEdit,
QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {p['bg_1']};
    border: 1px solid {p['border']};
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_SM}px {SPACE_MD}px;
    color: {p['txt_0']};
    font-size: {FS_BODY}px;
    selection-background-color: {p['bg_3']};
    selection-color: {p['txt_0']};
}}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QDateTimeEdit:hover,
QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{
    border-color: {p['border_scroll_handle']};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QDateTimeEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {p['accent']};
    background-color: {p['bg_0']};
}}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled,
QDateTimeEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
QComboBox:disabled {{
    background-color: {p['disabled_bg']};
    border-color: {p['disabled_border']};
    color: {p['disabled_fg']};
}}
QLineEdit:read-only {{
    background-color: {p['bg_0']};
    color: {p['txt_1']};
}}
QLineEdit[hasError="true"] {{
    border: 1px solid {p['danger_border']};
}}
QTextEdit, QPlainTextEdit {{
    padding: {SPACE_SM}px;
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: {SPACE_XL}px;
    border: none;
    background: transparent;
}}
QComboBox QAbstractItemView {{
    background-color: {p['bg_1']};
    border: 1px solid {p['border']};
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_XS}px;
    outline: none;
    selection-background-color: {p['bg_3']};
    selection-color: {p['txt_0']};
}}
QComboBox QAbstractItemView::item {{
    padding: {SPACE_SM}px {SPACE_MD}px;
    border-radius: {RADIUS_CONTROL - 2}px;
    min-height: 26px;
}}

QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QDateTimeEdit::up-button, QDateTimeEdit::down-button {{
    width: {SPACE_LG}px;
    border: none;
    background: transparent;
}}

/* --------------------------------------------- checkboxes / radios -------- */
QCheckBox, QRadioButton {{
    spacing: {SPACE_SM}px;
    color: {p['txt_0']};
    font-size: {FS_BODY}px;
    padding: {SPACE_XS}px 0;
    background: transparent;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    background-color: {p['bg_1']};
    border: 1px solid {p['border']};
}}
QCheckBox::indicator {{
    border-radius: {RADIUS_CONTROL - 2}px;
}}
QRadioButton::indicator {{
    border-radius: 9px;
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {p['accent']};
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {p['accent']};
    border-color: {p['accent']};
}}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    background-color: {p['disabled_bg']};
    border-color: {p['disabled_border']};
}}
QCheckBox:disabled, QRadioButton:disabled {{
    color: {p['disabled_fg']};
}}
/* A checkbox that leads a settings section reads as a heading. */
#groupLeadCheckbox {{
    font-size: {FS_BODY}px;
    font-weight: {W_SEMIBOLD};
    color: {p['chip_accent_fg']};
    padding: {SPACE_XS}px 0 {SPACE_SM}px 0;
}}

/* Connection identity line: neutral when offline, green when connected. */
#connectionIdentity {{
    color: {p['txt_1']};
    font-size: {FS_SECONDARY}px;
    padding: {SPACE_SM}px;
}}
#connectionIdentity[state="connected"] {{
    color: {p['ok_fg']};
    font-weight: {W_SEMIBOLD};
}}

/* ------------------------------------------------------------ groups ------ */
/* Cards, not fieldsets. The title sits inside the card as a real section heading
   rather than in a notch cut out of the top border, which is the single thing that
   made the whole app read as a 2005 settings dialog. */
QGroupBox {{
    background-color: {p['card']};
    border: 1px solid {p['border_soft']};
    border-radius: {RADIUS_CARD}px;
    margin-top: 0px;
    padding: {SPACE_XL + SPACE_SM}px {GROUP_MARGIN}px {GROUP_MARGIN}px {GROUP_MARGIN}px;
    font-size: {FS_BODY}px;
}}
QGroupBox::title {{
    subcontrol-origin: padding;
    subcontrol-position: top left;
    left: {GROUP_MARGIN}px;
    top: {SPACE_MD}px;
    padding: 0;
    background: transparent;
    border: none;
    color: {p['txt_0']};
    font-size: {FS_SECTION - 1}px;
    font-weight: {W_SEMIBOLD};
    letter-spacing: -0.01em;
}}

QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    background-color: {p['border']};
    border: none;
    max-height: 1px;
}}

/* ----------------------------------------------- lists, trees, tables ----- */
QListWidget, QTreeWidget, QTableWidget, QTableView {{
    background-color: {p['bg_1']};
    border: 1px solid {p['border']};
    border-radius: {RADIUS_CARD}px;
    color: {p['txt_0']};
    outline: none;
    gridline-color: {p['bg_2']};
    alternate-background-color: {p['bg_0']};
    font-size: {FS_BODY}px;
}}
QListWidget::item, QTreeWidget::item {{
    padding: {SPACE_SM}px {SPACE_MD}px;
    border-radius: {RADIUS_CONTROL - 2}px;
    min-height: 22px;
}}
QTableWidget::item, QTableView::item {{
    padding: {SPACE_XS}px {SPACE_SM}px;
}}
QListWidget::item:hover, QTreeWidget::item:hover {{
    background-color: {p['bg_2']};
}}
QListWidget::item:selected, QTreeWidget::item:selected,
QTableWidget::item:selected, QTableView::item:selected {{
    background-color: {p['bg_3']};
    color: {p['txt_0']};
}}

/* Item-view check indicators. Styling QCheckBox::indicator above makes Qt hand all
   indicator painting to the stylesheet, and with no rule matching item views their
   checked state was drawn as nothing at all -- a ticked playlist looked identical to
   an unticked one. These mirror the QCheckBox rules so the two read the same. */
QListWidget::indicator, QTreeWidget::indicator, QTableWidget::indicator {{
    width: 16px;
    height: 16px;
    border-radius: {RADIUS_CONTROL - 2}px;
    background-color: {p['bg_1']};
    border: 1px solid {p['border']};
}}
QListWidget::indicator:hover, QTreeWidget::indicator:hover,
QTableWidget::indicator:hover {{
    border-color: {p['accent']};
}}
QListWidget::indicator:checked, QTreeWidget::indicator:checked,
QTableWidget::indicator:checked {{
    background-color: {p['accent']};
    border-color: {p['accent']};
}}
QListWidget::indicator:disabled, QTreeWidget::indicator:disabled,
QTableWidget::indicator:disabled {{
    background-color: {p['disabled_bg']};
    border-color: {p['disabled_border']};
}}

/* -------------------------------------------------- playlist cover wall ----- */
/* The grid sits on the darkest surface so each card reads as a lifted tile
   rather than a panel drawn on a panel. In grid mode the delegate paints the
   whole card, so the generic ::item background and padding above have to be
   neutralised or Qt would draw a second highlight behind every cover. */
QListWidget#playlistGrid {{
    background-color: {p['bg_0']};
    border: 1px solid {p['border']};
    border-radius: {RADIUS_PANEL}px;
}}
QListWidget#playlistGrid[viewMode="grid"] {{
    padding: {SPACE_SM}px;
}}
QListWidget#playlistGrid[viewMode="grid"]::item {{
    padding: 0px;
    margin: 0px;
    border: none;
    background: transparent;
}}
QListWidget#playlistGrid[viewMode="grid"]::item:hover,
QListWidget#playlistGrid[viewMode="grid"]::item:selected {{
    background: transparent;
}}
QListWidget#playlistGrid[viewMode="list"] {{
    background-color: {p['bg_1']};
    padding: {SPACE_XS}px;
}}

/* Segmented Grid/List switch. Compact so the pair reads as one control next to
   the filter field, instead of two full-size page actions. */
#viewToggleButton {{
    min-width: 62px;
    max-width: 62px;
    padding: {SPACE_XS}px {SPACE_SM}px;
}}

/* Buttons living inside a table cell. The app-wide QPushButton padding would make
   these taller than the row they sit in. */
#rowActionButton {{
    padding: {SPACE_XS}px {SPACE_XS}px;
    min-width: 66px;
    max-width: 80px;
    min-height: 28px;
    max-height: 28px;
    font-size: {FS_MICRO}px;
}}

/* Sync Manager two-column splitter. The handle is a gutter, not a visible bar. */
#syncColumns::handle {{
    background: transparent;
}}
#syncColumns::handle:hover {{
    background-color: {p['bg_2']};
    border-radius: {RADIUS_CONTROL - 2}px;
}}
QHeaderView {{
    background-color: {p['bg_2']};
    border: none;
}}
QHeaderView::section {{
    background-color: {p['bg_2']};
    color: {p['txt_1']};
    font-size: {FS_MICRO}px;
    font-weight: {W_BOLD};
    letter-spacing: 0.06em;
    padding: {SPACE_SM}px {SPACE_MD}px;
    min-height: 22px;
    border: none;
    border-right: 1px solid {p['border']};
    border-bottom: 1px solid {p['border']};
}}
QHeaderView::section:hover {{
    background-color: {p['bg_3']};
    color: {p['txt_0']};
}}
QTableCornerButton::section {{
    background-color: {p['bg_2']};
    border: none;
    border-bottom: 1px solid {p['border']};
}}

/* --------------------------------------------------------- progress ------- */
QProgressBar {{
    background-color: {p['bg_1']};
    border: 1px solid {p['border']};
    border-radius: {RADIUS_CONTROL}px;
    text-align: center;
    color: {p['txt_0']};
    font-size: {FS_MICRO}px;
    font-weight: {W_SEMIBOLD};
    min-height: 18px;
}}
QProgressBar::chunk {{
    background-color: {p['accent']};
    border-radius: {RADIUS_CONTROL - 1}px;
    margin: 1px;
}}

/* ------------------------------------------------------------- tabs ------- */
QTabWidget::pane {{
    border: 1px solid {p['border']};
    border-radius: {RADIUS_CARD}px;
    background-color: {p['bg_1']};
    top: -1px;
    padding: {SPACE_XS}px;
}}
QTabBar::tab {{
    background-color: transparent;
    color: {p['txt_1']};
    padding: {SPACE_SM}px {SPACE_LG}px;
    margin-right: {SPACE_XS}px;
    border: 1px solid transparent;
    border-top-left-radius: {RADIUS_CONTROL}px;
    border-top-right-radius: {RADIUS_CONTROL}px;
    border-bottom: 2px solid transparent;
    font-size: {FS_BODY}px;
    font-weight: {W_MEDIUM};
    min-width: 80px;
}}
QTabBar::tab:hover:!selected {{
    background-color: {p['bg_1']};
    color: {p['txt_0']};
}}
QTabBar::tab:selected {{
    background-color: {p['bg_1']};
    color: {p['txt_0']};
    border-color: {p['border']};
    border-bottom: 2px solid {p['accent']};
    font-weight: {W_SEMIBOLD};
}}

/* ------------------------------------------------------------- menus ------ */
QMenu {{
    background-color: {p['bg_1']};
    border: 1px solid {p['border']};
    border-radius: {RADIUS_CARD}px;
    padding: {SPACE_XS}px;
}}
QMenu::item {{
    padding: {SPACE_SM}px {SPACE_LG}px;
    border-radius: {RADIUS_CONTROL - 2}px;
    color: {p['txt_0']};
    min-height: 22px;
}}
QMenu::item:selected {{
    background-color: {p['bg_3']};
}}
QMenu::item:disabled {{
    color: {p['disabled_fg']};
}}
QMenu::separator {{
    height: 1px;
    background: {p['border']};
    margin: {SPACE_XS}px {SPACE_SM}px;
}}

/* --------------------------------------------------------- statusbar ------ */
QStatusBar {{
    background-color: {p['bg_0']};
    border-top: 1px solid {p['border']};
    color: {p['txt_1']};
    font-size: {FS_SECONDARY}px;
    padding: 0 {SPACE_MD}px;
    min-height: 26px;
}}
QStatusBar::item {{
    border: none;
}}

/* ------------------------------------------------------------ splitter ---- */
QSplitter::handle {{
    background-color: {p['border']};
}}
QSplitter::handle:horizontal {{
    width: 1px;
}}
QSplitter::handle:vertical {{
    height: 1px;
}}

/* ------------------------------------------------------------ scrollbars -- */
QScrollBar:vertical {{
    background: {p['gradient_end']};
    width: 12px;
    margin: 2px;
    border: 1px solid {p['border_scroll']};
    border-radius: {RADIUS_CONTROL}px;
}}
QScrollBar::handle:vertical {{
    background: {p['scroll_handle']};
    min-height: 28px;
    border: 1px solid {p['border_scroll_handle']};
    border-radius: {RADIUS_CONTROL}px;
}}
QScrollBar::handle:vertical:hover {{
    background: {p['scroll_handle_hover']};
}}
QScrollBar::handle:vertical:pressed {{
    background: {p['scroll_handle_active']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    border: none;
    background: transparent;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QScrollBar:horizontal {{
    background: {p['gradient_end']};
    height: 12px;
    margin: 2px;
    border: 1px solid {p['border_scroll']};
    border-radius: {RADIUS_CONTROL}px;
}}
QScrollBar::handle:horizontal {{
    background: {p['scroll_handle']};
    min-width: 28px;
    border: 1px solid {p['border_scroll_handle']};
    border-radius: {RADIUS_CONTROL}px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {p['scroll_handle_hover']};
}}
QScrollBar::handle:horizontal:pressed {{
    background: {p['scroll_handle_active']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
    border: none;
    background: transparent;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
}}
"""


MAIN_STYLESHEET = build_stylesheet()
