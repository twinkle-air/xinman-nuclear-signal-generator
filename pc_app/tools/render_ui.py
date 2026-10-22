from pathlib import Path

from PySide6.QtWidgets import QApplication

from nucsignal_app.ui.main_window import MainWindow
from nucsignal_app.ui.style import APP_STYLESHEET, configure_chinese_font


def main() -> None:
    app = QApplication([])
    configure_chinese_font(app)
    app.setStyleSheet(APP_STYLESHEET)
    window = MainWindow()
    window.show()
    app.processEvents()
    output = Path(__file__).resolve().parents[1] / "ui_preview.png"
    if not window.grab().save(str(output)):
        raise RuntimeError("界面截图保存失败")
    window.device_mode.setCurrentText("USB CDC")
    app.processEvents()
    cdc_output = Path(__file__).resolve().parents[1] / "ui_usb_cdc_preview.png"
    if not window.grab().save(str(cdc_output)):
        raise RuntimeError("USB CDC连接界面截图保存失败")
    window.device_mode.setCurrentText("ST-Link VCP")
    app.processEvents()
    stlink_output = Path(__file__).resolve().parents[1] / "ui_stlink_vcp_preview.png"
    if not window.grab().save(str(stlink_output)):
        raise RuntimeError("ST-Link VCP连接界面截图保存失败")
    window.show_tutorial()
    app.processEvents()
    tutorial_output = Path(__file__).resolve().parents[1] / "ui_tutorial_preview.png"
    if not window.tutorial_dialog.grab().save(str(tutorial_output)):
        raise RuntimeError("教程窗口截图保存失败")
    window.tutorial_dialog.close()
    window.close()
    print(output)
    print(cdc_output)
    print(stlink_output)
    print(tutorial_output)


if __name__ == "__main__":
    main()
