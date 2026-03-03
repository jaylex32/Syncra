"""Centralized QSS theme for Syncra."""

TOKENS = {
    "bg_0": "#111a28",
    "bg_1": "#1a2537",
    "bg_2": "#25344b",
    "bg_3": "#314664",
    "txt_0": "#f5f7fb",
    "txt_1": "#c9d1df",
    "accent": "#2fb8ff",
    "accent_ok": "#2ed27a",
    "border": "#3f516f",
}

MAIN_STYLESHEET = f"""
QMainWindow, QMessageBox, QMenu, QDialog {{
    background-color: {TOKENS['bg_0']};
    color: {TOKENS['txt_0']};
}}
#leftSidebar {{
    background-color: #121722;
    border-right: 1px solid {TOKENS['border']};
}}
#mainContentSurface {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #121722, stop:1 #0f1b30);
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
QWidget {{
    color: {TOKENS['txt_0']};
    font-size: 13px;
}}
#topHeaderCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1f2a3b, stop:1 #1a2232);
    border: 1px solid {TOKENS['border']};
    border-radius: 12px;
}}
#pageTitle {{
    font-size: 22px;
    font-weight: 700;
    color: #f8fbff;
    margin: 0;
    padding: 0;
}}
#pageSubtitle {{
    font-size: 12px;
    color: #a8b9cf;
    margin: 0;
    padding: 0;
}}
#headerChipOk, #headerChipWarn, #headerChipNeutral, #headerChipAccent {{
    border-radius: 10px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 700;
}}
#headerChipOk {{
    background-color: #1f3a2a;
    border: 1px solid #2ed27a;
    color: #90f3c1;
}}
#headerChipWarn {{
    background-color: #3a2b1f;
    border: 1px solid #f9a93b;
    color: #ffd399;
}}
#headerChipNeutral {{
    background-color: #243047;
    border: 1px solid #486089;
    color: #cfe0ff;
}}
#headerChipAccent {{
    background-color: #1f2f40;
    border: 1px solid {TOKENS['accent']};
    color: #8ad8ff;
}}
#dashboardHeroCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1d2f47, stop:1 #1b2335);
    border: 1px solid #44516c;
    border-radius: 14px;
}}
#dashboardHeroTitle {{
    font-size: 24px;
    font-weight: 800;
    color: #f5f9ff;
}}
#dashboardHeroSubtitle {{
    font-size: 13px;
    color: #c7d4e8;
}}
#dashboardMetricCard {{
    background-color: #202d43;
    border: 1px solid #44516c;
    border-radius: 10px;
    padding: 10px 12px;
    font-size: 12px;
    font-weight: 700;
    color: #d9e7ff;
    min-height: 42px;
}}
#sectionHeaderCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e2b3f, stop:1 #1a2231);
    border: 1px solid #42506a;
    border-radius: 12px;
}}
#sectionHeaderTitle {{
    font-size: 18px;
    font-weight: 750;
    color: #f2f7ff;
}}
#sectionHeaderSubtitle {{
    font-size: 12px;
    color: #b9c8dc;
}}
QPushButton, QComboBox {{
    background-color: {TOKENS['bg_2']};
    border: 1px solid {TOKENS['border']};
    padding: 8px 14px;
    margin: 4px;
    border-radius: 8px;
    min-height: 20px;
    color: {TOKENS['txt_0']};
}}
QPushButton:hover, QComboBox:hover {{
    background-color: {TOKENS['bg_3']};
}}
QPushButton:pressed, QComboBox:on {{
    background-color: {TOKENS['bg_1']};
}}
QPushButton#importBrowseButton, QPushButton#importPlaylistButton {{
    margin-top: 0px;
    margin-bottom: 0px;
}}
QLineEdit, QTextEdit, QPlainTextEdit, QDateTimeEdit, QSpinBox {{
    background-color: {TOKENS['bg_1']};
    border: 1px solid {TOKENS['border']};
    padding: 6px;
    border-radius: 6px;
    color: {TOKENS['txt_0']};
}}
QDoubleSpinBox {{
    background-color: {TOKENS['bg_1']};
    border: 1px solid {TOKENS['border']};
    padding: 6px;
    border-radius: 6px;
    color: {TOKENS['txt_0']};
}}
QListWidget, QTreeWidget, QTableWidget {{
    background-color: {TOKENS['bg_1']};
    border: 1px solid {TOKENS['border']};
    border-radius: 8px;
    color: {TOKENS['txt_0']};
}}
QListWidget::item:selected, QTreeWidget::item:selected, QTableWidget::item:selected {{
    background-color: {TOKENS['bg_3']};
}}
QProgressBar {{
    border: 1px solid {TOKENS['border']};
    border-radius: 8px;
    text-align: center;
    color: {TOKENS['txt_0']};
}}
QProgressBar::chunk {{
    background-color: {TOKENS['accent']};
}}
QGroupBox {{
    border: 1px solid {TOKENS['border']};
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 10px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {TOKENS['txt_1']};
}}
QStatusBar {{
    background-color: {TOKENS['bg_0']};
    color: {TOKENS['txt_1']};
}}
QHeaderView::section {{
    background-color: {TOKENS['bg_2']};
    color: {TOKENS['txt_0']};
    padding: 5px;
    border: 1px solid {TOKENS['border']};
}}
QTabWidget::pane {{
    border: 1px solid {TOKENS['border']};
    background-color: {TOKENS['bg_1']};
}}
QTabBar::tab {{
    background-color: {TOKENS['bg_2']};
    color: {TOKENS['txt_0']};
    padding: 7px 12px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {TOKENS['bg_3']};
    border-bottom: 2px solid {TOKENS['accent']};
}}
QScrollBar:vertical {{
    background: #0f1b30;
    width: 12px;
    margin: 2px;
    border: 1px solid #2f4360;
    border-radius: 6px;
}}
QScrollBar::handle:vertical {{
    background: #2a3f5e;
    min-height: 28px;
    border: 1px solid #49648b;
    border-radius: 6px;
}}
QScrollBar::handle:vertical:hover {{
    background: #35527a;
}}
QScrollBar::handle:vertical:pressed {{
    background: #3f6291;
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
    background: #0f1b30;
    height: 12px;
    margin: 2px;
    border: 1px solid #2f4360;
    border-radius: 6px;
}}
QScrollBar::handle:horizontal {{
    background: #2a3f5e;
    min-width: 28px;
    border: 1px solid #49648b;
    border-radius: 6px;
}}
QScrollBar::handle:horizontal:hover {{
    background: #35527a;
}}
QScrollBar::handle:horizontal:pressed {{
    background: #3f6291;
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
