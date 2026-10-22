from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase


def configure_chinese_font(app) -> str:
    """选择可显示中文的字体；离屏渲染时显式载入系统字体。"""
    families = set(QFontDatabase.families())
    preferred = ("Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "SimSun")
    family = next((name for name in preferred if name in families), None)
    if family is None:
        for font_path in (Path("C:/Windows/Fonts/simhei.ttf"), Path("C:/Windows/Fonts/simsun.ttc")):
            if not font_path.exists():
                continue
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            loaded = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
            if loaded:
                family = loaded[0]
                break
    family = family or app.font().family()
    app.setFont(QFont(family, 10))
    return family


APP_STYLESHEET = """
QMainWindow, QWidget { background: #f4f7fb; color: #172033; font-size: 13px; }
QFrame#card { background: white; border: 1px solid #dfe7f0; border-radius: 10px; }
QLabel#title { font-size: 21px; font-weight: 700; color: #102a43; }
QLabel#subtitle { color: #60758a; }
QLabel#section { font-size: 14px; font-weight: 700; color: #234e70; }
QLabel#stateBadge { background: #e8f3ff; color: #1565c0; border-radius: 9px; padding: 5px 10px; font-weight: 700; }
QPushButton { background: #edf3f9; border: 1px solid #d4e0ec; border-radius: 7px; padding: 8px 13px; }
QPushButton:hover { background: #dcecff; border-color: #87baf0; }
QPushButton#primary { background: #1565c0; color: white; border-color: #1565c0; font-weight: 700; }
QPushButton#primary:hover { background: #0d57aa; }
QPushButton#stop { background: #fff1f0; color: #b42318; border-color: #f5b7b1; font-weight: 700; }
QPushButton#transfer { background: #e76f00; color: white; border-color: #e76f00; font-weight: 700; padding: 9px 16px; }
QPushButton#transfer:hover { background: #c95f00; }
QPushButton#modeButton { padding: 7px 10px; }
QPushButton#modeButton:checked { background: #1565c0; color: white; border-color: #1565c0; font-weight: 700; }
QPushButton#tutorial { background: #e8f3ff; color: #155fa0; border-color: #9bc3e8; font-weight: 700; }
QPushButton#tutorial:hover { background: #d5eaff; }
QComboBox, QDoubleSpinBox, QSpinBox { background: white; border: 1px solid #cfdbe7; border-radius: 6px; padding: 5px; min-height: 23px; }
QProgressBar { background: #edf3f9; border: 1px solid #d4e0ec; border-radius: 6px; text-align: center; min-height: 24px; }
QProgressBar::chunk { background: #2f80c9; border-radius: 5px; }
QTabWidget::pane { border: 0; }
QTabBar::tab { background: #e9eff5; border-radius: 6px; padding: 8px 18px; margin-right: 4px; }
QTabBar::tab:selected { background: #1565c0; color: white; }
QStatusBar { background: white; border-top: 1px solid #dfe7f0; }
QPushButton:disabled, QPushButton#primary:disabled, QPushButton#transfer:disabled, QPushButton#stop:disabled {
    color: #8b96a5; background: #f0f2f5; border-color: #e0e5eb;
}
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled { color: #8b96a5; background: #f0f2f5; }
"""
