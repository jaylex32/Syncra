"""Centralized design system and QSS theme for Syncra.

Palette is unchanged from the original theme -- every colour value here already existed
in the app, either in the TOKENS dict or hardcoded inline in the QSS. What changed is
that they are now all named, and everything else (spacing, radii, type scale, states)
is derived from a small set of constants instead of being chosen per widget.

Layout code should import SPACE_*, RADIUS_* and FONT_* rather than hardcoding numbers,
so Python-side margins stay in sync with the QSS.
"""

# ---------------------------------------------------------------------------
# Colour tokens - deep navy surfaces, neon cyan accent. Values preserved exactly.
# ---------------------------------------------------------------------------

TOKENS = {
    # Surfaces, darkest to lightest
    "bg_0": "#111a28",   # window canvas
    "bg_1": "#1a2537",   # inputs, lists, tables
    "bg_2": "#25344b",   # buttons, combos, header sections
    "bg_3": "#314664",   # hover / selected

    # Text
    "txt_0": "#f5f7fb",  # primary
    "txt_1": "#c9d1df",  # secondary

    # Brand
    "accent": "#2fb8ff",     # neon cyan - active elements and primary actions only
    "accent_ok": "#2ed27a",  # success green - matches the Connected badge

    "border": "#3f516f",
}

# Named versions of colours that were previously inline in the QSS string.
SURFACE_SIDEBAR = "#121722"
SURFACE_GRADIENT_END = "#0f1b30"
SURFACE_HEADER_A = "#1f2a3b"
SURFACE_HEADER_B = "#1a2232"
SURFACE_HERO_A = "#1d2f47"
SURFACE_HERO_B = "#1b2335"
SURFACE_SECTION_A = "#1e2b3f"
SURFACE_SECTION_B = "#1a2231"
SURFACE_CARD = "#202d43"

BORDER_SOFT = "#44516c"
BORDER_SECTION = "#42506a"
BORDER_SCROLL = "#2f4360"
BORDER_SCROLL_HANDLE = "#49648b"

SCROLL_HANDLE = "#2a3f5e"
SCROLL_HANDLE_HOVER = "#35527a"
SCROLL_HANDLE_ACTIVE = "#3f6291"

TXT_TITLE = "#f8fbff"
TXT_MUTED = "#a8b9cf"
TXT_SUBTLE = "#b9c8dc"
TXT_METRIC = "#d9e7ff"
TXT_HERO = "#c7d4e8"
TXT_SIDEBAR_GROUP = "#8fa1ba"

# Sidebar rules. The section rule is quieter than the block divider so the two read
# as different weights of separation rather than the same line repeated.
SIDEBAR_RULE = "#232f42"
SIDEBAR_DIVIDER = "#2b3a52"

# Status families. Each is (background, border, foreground).
STATUS_OK = ("#1f3a2a", "#2ed27a", "#90f3c1")
STATUS_WARN = ("#3a2b1f", "#f9a93b", "#ffd399")
STATUS_DANGER = ("#3a1d22", "#7a3b44", "#ffd9d9")
STATUS_NEUTRAL = ("#243047", "#486089", "#cfe0ff")
STATUS_ACCENT = ("#1f2f40", TOKENS["accent"], "#8ad8ff")

DISABLED_BG = "#1b2434"
DISABLED_FG = "#6d7c93"
DISABLED_BORDER = "#2c3a52"

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


def _chip(name, family):
    """Build the QSS block for a status chip / badge."""
    bg, border, fg = family
    return f"""
#{name} {{
    background-color: {bg};
    border: 1px solid {border};
    color: {fg};
}}"""


MAIN_STYLESHEET = f"""
/* ---------------------------------------------------------------- base ---- */
QMainWindow, QMessageBox, QMenu, QDialog {{
    background-color: {TOKENS['bg_0']};
    color: {TOKENS['txt_0']};
}}
QWidget {{
    color: {TOKENS['txt_0']};
    font-family: {FONT_STACK};
    font-size: {FS_BODY}px;
}}
QLabel {{
    background: transparent;
}}
QToolTip {{
    background-color: {SURFACE_HEADER_A};
    color: {TOKENS['txt_0']};
    border: 1px solid {TOKENS['border']};
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_XS}px {SPACE_SM}px;
    font-size: {FS_SECONDARY}px;
}}

/* ------------------------------------------------------------- shell ------ */
#leftSidebar {{
    background-color: {SURFACE_SIDEBAR};
    border-right: 1px solid {TOKENS['border']};
}}
#mainContentSurface {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {SURFACE_SIDEBAR}, stop:1 {SURFACE_GRADIENT_END});
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
    color: {TXT_SIDEBAR_GROUP};
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
    color: {TXT_SIDEBAR_GROUP};
    font-size: 10px;
    font-weight: {W_BOLD};
    letter-spacing: 0.14em;
    background: transparent;
}}
#sidebarSectionRule {{
    background-color: {SIDEBAR_RULE};
    border: none;
}}
#sidebarDivider {{
    background-color: {SIDEBAR_DIVIDER};
    border: none;
}}
#sidebarFooterText {{
    color: {TXT_SIDEBAR_GROUP};
    font-size: {FS_MICRO}px;
    font-weight: {W_MEDIUM};
    background: transparent;
}}
#sidebarStatusDot {{
    color: {DISABLED_FG};
    font-size: {FS_BODY}px;
    background: transparent;
}}
#sidebarStatusDot[state="connected"] {{
    color: {TOKENS['accent_ok']};
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
    color: {TOKENS['txt_1']};
    /* ~40px rows. The previous 34px min-height plus 8px padding produced 54px items,
       which spread nine entries over the full column height. */
    min-height: 32px;
}}
#sidebarNavButton:hover {{
    background-color: {TOKENS['bg_1']};
    color: {TOKENS['txt_0']};
    border-left-color: {TOKENS['border']};
}}
#sidebarNavButton:pressed {{
    background-color: {TOKENS['bg_2']};
}}
#sidebarNavButton[active="true"] {{
    background-color: {STATUS_ACCENT[0]};
    color: {STATUS_ACCENT[2]};
    border-left: 3px solid {TOKENS['accent']};
    font-weight: {W_SEMIBOLD};
}}
#sidebarNavButton:focus {{
    border-color: {TOKENS['accent']};
}}

/* -------------------------------------------------------- page header ----- */
#topHeaderCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {SURFACE_HEADER_A}, stop:1 {SURFACE_HEADER_B});
    border: 1px solid {TOKENS['border']};
    border-radius: {RADIUS_PANEL}px;
}}
#pageTitle {{
    font-size: {FS_TITLE}px;
    font-weight: {W_BOLD};
    color: {TXT_TITLE};
    letter-spacing: -0.01em;
}}
#pageSubtitle {{
    font-size: {FS_SECONDARY}px;
    font-weight: {W_REGULAR};
    color: {TXT_MUTED};
}}
#sectionHeaderCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {SURFACE_SECTION_A}, stop:1 {SURFACE_SECTION_B});
    border: 1px solid {BORDER_SECTION};
    border-radius: {RADIUS_PANEL}px;
}}
#sectionHeaderTitle {{
    font-size: {FS_SECTION}px;
    font-weight: {W_BOLD};
    color: {TXT_TITLE};
    letter-spacing: -0.01em;
}}
#sectionHeaderSubtitle {{
    font-size: {FS_SECONDARY}px;
    color: {TXT_SUBTLE};
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
{_chip("headerChipOk", STATUS_OK)}
{_chip("headerChipWarn", STATUS_WARN)}
{_chip("headerChipNeutral", STATUS_NEUTRAL)}
{_chip("headerChipAccent", STATUS_ACCENT)}
{_chip("headerChipDanger", STATUS_DANGER)}

/* Inline status banners share the chip palette at card scale. */
#connectionBanner, #statusBannerDanger {{
    background-color: {STATUS_DANGER[0]};
    border: 1px solid {STATUS_DANGER[1]};
    color: {STATUS_DANGER[2]};
    border-radius: {RADIUS_CARD}px;
    padding: {SPACE_MD}px;
    font-size: {FS_SECONDARY}px;
}}
#statusBannerOk {{
    background-color: {STATUS_OK[0]};
    border: 1px solid {STATUS_OK[1]};
    color: {STATUS_OK[2]};
    border-radius: {RADIUS_CARD}px;
    padding: {SPACE_MD}px;
    font-size: {FS_SECONDARY}px;
}}
#statusBannerInfo, #infoNote {{
    background-color: {STATUS_ACCENT[0]};
    border: 1px solid {TOKENS['border']};
    color: {STATUS_ACCENT[2]};
    border-radius: {RADIUS_CARD}px;
    padding: {SPACE_MD}px;
    font-size: {FS_SECONDARY}px;
}}
#helperText {{
    color: {TXT_SUBTLE};
    font-size: {FS_SECONDARY}px;
}}
#mutedText {{
    color: {TXT_MUTED};
    font-size: {FS_SECONDARY}px;
}}

/* --------------------------------------------------------- dashboard ------ */
#dashboardHeroCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {SURFACE_HERO_A}, stop:1 {SURFACE_HERO_B});
    border: 1px solid {BORDER_SOFT};
    border-radius: {RADIUS_PANEL}px;
}}
#dashboardHeroTitle {{
    font-size: {FS_DISPLAY}px;
    font-weight: {W_HEAVY};
    color: {TXT_TITLE};
    letter-spacing: -0.02em;
}}
#dashboardHeroSubtitle {{
    font-size: {FS_BODY}px;
    color: {TXT_HERO};
}}
#dashboardMetricCard {{
    background-color: rgba(17, 26, 40, 0.55);
    border: 1px solid {BORDER_SOFT};
    border-radius: {RADIUS_CARD}px;
}}
#metricCaption {{
    color: {TXT_MUTED};
    font-size: {FS_MICRO}px;
    font-weight: {W_SEMIBOLD};
    letter-spacing: 0.08em;
    text-transform: uppercase;
}}
#metricValue {{
    color: {TXT_TITLE};
    font-size: {FS_TITLE}px;
    font-weight: {W_BOLD};
    letter-spacing: -0.01em;
}}

/* ----------------------------------------------------------- buttons ------ */
/* No margin here: spacing belongs to the layout, not the widget. */
QPushButton {{
    background-color: {TOKENS['bg_2']};
    border: 1px solid {TOKENS['border']};
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_SM}px {SPACE_LG}px;
    min-height: {CONTROL_HEIGHT - 18}px;
    color: {TOKENS['txt_0']};
    font-size: {FS_BODY}px;
    font-weight: {W_MEDIUM};
}}
QPushButton:hover {{
    background-color: {TOKENS['bg_3']};
    border-color: {BORDER_SCROLL_HANDLE};
}}
QPushButton:pressed {{
    background-color: {TOKENS['bg_1']};
    border-color: {TOKENS['border']};
}}
QPushButton:focus {{
    border: 1px solid {TOKENS['accent']};
}}
QPushButton:disabled {{
    background-color: {DISABLED_BG};
    border-color: {DISABLED_BORDER};
    color: {DISABLED_FG};
}}
QPushButton:checked {{
    background-color: {STATUS_ACCENT[0]};
    border-color: {TOKENS['accent']};
    color: {STATUS_ACCENT[2]};
}}
/* Primary action: the only filled cyan control on a page. */
QPushButton[variant="primary"] {{
    background-color: {TOKENS['accent']};
    border: 1px solid {TOKENS['accent']};
    color: {TOKENS['bg_0']};
    font-weight: {W_SEMIBOLD};
}}
QPushButton[variant="primary"]:hover {{
    background-color: #57c7ff;
    border-color: #57c7ff;
}}
QPushButton[variant="primary"]:pressed {{
    background-color: #1a9fe0;
    border-color: #1a9fe0;
}}
QPushButton[variant="primary"]:disabled {{
    background-color: {DISABLED_BG};
    border-color: {DISABLED_BORDER};
    color: {DISABLED_FG};
}}
QPushButton[variant="danger"] {{
    background-color: {STATUS_DANGER[0]};
    border: 1px solid {STATUS_DANGER[1]};
    color: {STATUS_DANGER[2]};
}}
QPushButton[variant="danger"]:hover {{
    background-color: #4a262c;
}}
QPushButton[variant="success"] {{
    background-color: {STATUS_OK[0]};
    border: 1px solid {STATUS_OK[1]};
    color: {STATUS_OK[2]};
}}
QPushButton[variant="success"]:hover {{
    background-color: #26482f;
}}
QPushButton[variant="ghost"] {{
    background: transparent;
    border: 1px solid transparent;
    color: {TOKENS['txt_1']};
}}
QPushButton[variant="ghost"]:hover {{
    background-color: {TOKENS['bg_1']};
    color: {TOKENS['txt_0']};
}}

/* ------------------------------------------------------------ inputs ------ */
QLineEdit, QTextEdit, QPlainTextEdit, QDateTimeEdit,
QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {TOKENS['bg_1']};
    border: 1px solid {TOKENS['border']};
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_SM}px {SPACE_MD}px;
    color: {TOKENS['txt_0']};
    font-size: {FS_BODY}px;
    selection-background-color: {TOKENS['bg_3']};
    selection-color: {TOKENS['txt_0']};
}}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QDateTimeEdit:hover,
QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{
    border-color: {BORDER_SCROLL_HANDLE};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QDateTimeEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {TOKENS['accent']};
    background-color: {TOKENS['bg_0']};
}}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled,
QDateTimeEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
QComboBox:disabled {{
    background-color: {DISABLED_BG};
    border-color: {DISABLED_BORDER};
    color: {DISABLED_FG};
}}
QLineEdit:read-only {{
    background-color: {TOKENS['bg_0']};
    color: {TOKENS['txt_1']};
}}
QLineEdit[hasError="true"] {{
    border: 1px solid {STATUS_DANGER[1]};
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
    background-color: {TOKENS['bg_1']};
    border: 1px solid {TOKENS['border']};
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_XS}px;
    outline: none;
    selection-background-color: {TOKENS['bg_3']};
    selection-color: {TOKENS['txt_0']};
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
    color: {TOKENS['txt_0']};
    font-size: {FS_BODY}px;
    padding: {SPACE_XS}px 0;
    background: transparent;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    background-color: {TOKENS['bg_1']};
    border: 1px solid {TOKENS['border']};
}}
QCheckBox::indicator {{
    border-radius: {RADIUS_CONTROL - 2}px;
}}
QRadioButton::indicator {{
    border-radius: 9px;
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {TOKENS['accent']};
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {TOKENS['accent']};
    border-color: {TOKENS['accent']};
}}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    background-color: {DISABLED_BG};
    border-color: {DISABLED_BORDER};
}}
QCheckBox:disabled, QRadioButton:disabled {{
    color: {DISABLED_FG};
}}
/* A checkbox that leads a settings section reads as a heading. */
#groupLeadCheckbox {{
    font-size: {FS_BODY}px;
    font-weight: {W_SEMIBOLD};
    color: {STATUS_ACCENT[2]};
    padding: {SPACE_XS}px 0 {SPACE_SM}px 0;
}}

/* Connection identity line: neutral when offline, green when connected. */
#connectionIdentity {{
    color: {TOKENS['txt_1']};
    font-size: {FS_SECONDARY}px;
    padding: {SPACE_SM}px;
}}
#connectionIdentity[state="connected"] {{
    color: {STATUS_OK[2]};
    font-weight: {W_SEMIBOLD};
}}

/* ------------------------------------------------------------ groups ------ */
/* Cards, not fieldsets. The title sits inside the card as a real section heading
   rather than in a notch cut out of the top border, which is the single thing that
   made the whole app read as a 2005 settings dialog. */
QGroupBox {{
    background-color: {SURFACE_CARD};
    border: 1px solid {BORDER_SOFT};
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
    color: {TOKENS['txt_0']};
    font-size: {FS_SECTION - 1}px;
    font-weight: {W_SEMIBOLD};
    letter-spacing: -0.01em;
}}

QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    background-color: {TOKENS['border']};
    border: none;
    max-height: 1px;
}}

/* ----------------------------------------------- lists, trees, tables ----- */
QListWidget, QTreeWidget, QTableWidget, QTableView {{
    background-color: {TOKENS['bg_1']};
    border: 1px solid {TOKENS['border']};
    border-radius: {RADIUS_CARD}px;
    color: {TOKENS['txt_0']};
    outline: none;
    gridline-color: {TOKENS['bg_2']};
    alternate-background-color: {TOKENS['bg_0']};
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
    background-color: {TOKENS['bg_2']};
}}
QListWidget::item:selected, QTreeWidget::item:selected,
QTableWidget::item:selected, QTableView::item:selected {{
    background-color: {TOKENS['bg_3']};
    color: {TOKENS['txt_0']};
}}

/* Item-view check indicators. Styling QCheckBox::indicator above makes Qt hand all
   indicator painting to the stylesheet, and with no rule matching item views their
   checked state was drawn as nothing at all -- a ticked playlist looked identical to
   an unticked one. These mirror the QCheckBox rules so the two read the same. */
QListWidget::indicator, QTreeWidget::indicator, QTableWidget::indicator {{
    width: 16px;
    height: 16px;
    border-radius: {RADIUS_CONTROL - 2}px;
    background-color: {TOKENS['bg_1']};
    border: 1px solid {TOKENS['border']};
}}
QListWidget::indicator:hover, QTreeWidget::indicator:hover,
QTableWidget::indicator:hover {{
    border-color: {TOKENS['accent']};
}}
QListWidget::indicator:checked, QTreeWidget::indicator:checked,
QTableWidget::indicator:checked {{
    background-color: {TOKENS['accent']};
    border-color: {TOKENS['accent']};
}}
QListWidget::indicator:disabled, QTreeWidget::indicator:disabled,
QTableWidget::indicator:disabled {{
    background-color: {DISABLED_BG};
    border-color: {DISABLED_BORDER};
}}

/* -------------------------------------------------- playlist cover wall ----- */
/* The grid sits on the darkest surface so each card reads as a lifted tile
   rather than a panel drawn on a panel. In grid mode the delegate paints the
   whole card, so the generic ::item background and padding above have to be
   neutralised or Qt would draw a second highlight behind every cover. */
QListWidget#playlistGrid {{
    background-color: {TOKENS['bg_0']};
    border: 1px solid {TOKENS['border']};
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
    background-color: {TOKENS['bg_1']};
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
    background-color: {TOKENS['bg_2']};
    border-radius: {RADIUS_CONTROL - 2}px;
}}
QHeaderView {{
    background-color: {TOKENS['bg_2']};
    border: none;
}}
QHeaderView::section {{
    background-color: {TOKENS['bg_2']};
    color: {TOKENS['txt_1']};
    font-size: {FS_MICRO}px;
    font-weight: {W_BOLD};
    letter-spacing: 0.06em;
    padding: {SPACE_SM}px {SPACE_MD}px;
    min-height: 22px;
    border: none;
    border-right: 1px solid {TOKENS['border']};
    border-bottom: 1px solid {TOKENS['border']};
}}
QHeaderView::section:hover {{
    background-color: {TOKENS['bg_3']};
    color: {TOKENS['txt_0']};
}}
QTableCornerButton::section {{
    background-color: {TOKENS['bg_2']};
    border: none;
    border-bottom: 1px solid {TOKENS['border']};
}}

/* --------------------------------------------------------- progress ------- */
QProgressBar {{
    background-color: {TOKENS['bg_1']};
    border: 1px solid {TOKENS['border']};
    border-radius: {RADIUS_CONTROL}px;
    text-align: center;
    color: {TOKENS['txt_0']};
    font-size: {FS_MICRO}px;
    font-weight: {W_SEMIBOLD};
    min-height: 18px;
}}
QProgressBar::chunk {{
    background-color: {TOKENS['accent']};
    border-radius: {RADIUS_CONTROL - 1}px;
    margin: 1px;
}}

/* ------------------------------------------------------------- tabs ------- */
QTabWidget::pane {{
    border: 1px solid {TOKENS['border']};
    border-radius: {RADIUS_CARD}px;
    background-color: {TOKENS['bg_1']};
    top: -1px;
    padding: {SPACE_XS}px;
}}
QTabBar::tab {{
    background-color: transparent;
    color: {TOKENS['txt_1']};
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
    background-color: {TOKENS['bg_1']};
    color: {TOKENS['txt_0']};
}}
QTabBar::tab:selected {{
    background-color: {TOKENS['bg_1']};
    color: {TOKENS['txt_0']};
    border-color: {TOKENS['border']};
    border-bottom: 2px solid {TOKENS['accent']};
    font-weight: {W_SEMIBOLD};
}}

/* ------------------------------------------------------------- menus ------ */
QMenu {{
    background-color: {TOKENS['bg_1']};
    border: 1px solid {TOKENS['border']};
    border-radius: {RADIUS_CARD}px;
    padding: {SPACE_XS}px;
}}
QMenu::item {{
    padding: {SPACE_SM}px {SPACE_LG}px;
    border-radius: {RADIUS_CONTROL - 2}px;
    color: {TOKENS['txt_0']};
    min-height: 22px;
}}
QMenu::item:selected {{
    background-color: {TOKENS['bg_3']};
}}
QMenu::item:disabled {{
    color: {DISABLED_FG};
}}
QMenu::separator {{
    height: 1px;
    background: {TOKENS['border']};
    margin: {SPACE_XS}px {SPACE_SM}px;
}}

/* --------------------------------------------------------- statusbar ------ */
QStatusBar {{
    background-color: {TOKENS['bg_0']};
    border-top: 1px solid {TOKENS['border']};
    color: {TOKENS['txt_1']};
    font-size: {FS_SECONDARY}px;
    padding: 0 {SPACE_MD}px;
    min-height: 26px;
}}
QStatusBar::item {{
    border: none;
}}

/* ------------------------------------------------------------ splitter ---- */
QSplitter::handle {{
    background-color: {TOKENS['border']};
}}
QSplitter::handle:horizontal {{
    width: 1px;
}}
QSplitter::handle:vertical {{
    height: 1px;
}}

/* ------------------------------------------------------------ scrollbars -- */
QScrollBar:vertical {{
    background: {SURFACE_GRADIENT_END};
    width: 12px;
    margin: 2px;
    border: 1px solid {BORDER_SCROLL};
    border-radius: {RADIUS_CONTROL}px;
}}
QScrollBar::handle:vertical {{
    background: {SCROLL_HANDLE};
    min-height: 28px;
    border: 1px solid {BORDER_SCROLL_HANDLE};
    border-radius: {RADIUS_CONTROL}px;
}}
QScrollBar::handle:vertical:hover {{
    background: {SCROLL_HANDLE_HOVER};
}}
QScrollBar::handle:vertical:pressed {{
    background: {SCROLL_HANDLE_ACTIVE};
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
    background: {SURFACE_GRADIENT_END};
    height: 12px;
    margin: 2px;
    border: 1px solid {BORDER_SCROLL};
    border-radius: {RADIUS_CONTROL}px;
}}
QScrollBar::handle:horizontal {{
    background: {SCROLL_HANDLE};
    min-width: 28px;
    border: 1px solid {BORDER_SCROLL_HANDLE};
    border-radius: {RADIUS_CONTROL}px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {SCROLL_HANDLE_HOVER};
}}
QScrollBar::handle:horizontal:pressed {{
    background: {SCROLL_HANDLE_ACTIVE};
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
