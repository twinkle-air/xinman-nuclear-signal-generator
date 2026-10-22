from __future__ import annotations

import json
import logging
import os
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow
from .ui.style import APP_STYLESHEET, configure_chinese_font
from . import __version__
from .ui.tutorial import TUTORIAL_SECTIONS
from .importers import BUILTIN_NUCLIDES


def main() -> int:
    try:
        log_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Nucsignal" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(log_dir / "serial.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logging.getLogger("nucsignal_app").addHandler(handler)
        logging.getLogger("nucsignal_app").setLevel(logging.WARNING)
    except OSError:
        pass  # A read-only log directory must not prevent STOP/control from opening.
    app = QApplication(sys.argv)
    app.setApplicationName("核信号工作台")
    configure_chinese_font(app)
    app.setStyleSheet(APP_STYLESHEET)
    window = MainWindow()
    window.show()

    # 打包验收专用：创建真实主窗口、完成预览后记录结果并自动退出。
    # 普通双击启动时没有该参数，不影响用户操作。
    if "--smoke-test" in sys.argv:
        index = sys.argv.index("--smoke-test")
        if index + 1 >= len(sys.argv):
            raise ValueError("--smoke-test 后必须提供结果文件路径")
        result_path = Path(sys.argv[index + 1])

        def finish_smoke_test() -> None:
            result_path.write_text(
                json.dumps(
                    {
                        "window_title": window.windowTitle(),
                        "channels": len(window.results),
                        "samples_per_channel": int(window.results[0].time_us.size),
                        "source": window.source.name,
                        "app_version": __version__,
                        "device_modes": window.device_mode.modes(),
                        "tutorial_available": window.tutorial_button.text() == "使用教程",
                        "tutorial_sections": list(TUTORIAL_SECTIONS),
                        "manual_port_entry": window.port_combo.isEditable(),
                        "csv_export": window.export_csv_button.text(),
                        "background_transfer": window._operation is None,
                        "builtin_nuclides": list(BUILTIN_NUCLIDES),
                        "fwhm_direct_control": window.channel_panels[0].fwhm.minimum() == 1.0,
                        "plot_interactive": "滚轮缩放" in window.plot.toolTip(),
                        "plot_view_range": list(window.plot.view_range()),
                        "plot_colors": [color.name() for _values, color, _label in window.plot._signals],
                        "workflow_steps": list(window.workflow.STEPS),
                        "bench_panel_available": window.bench_tabs.count() == 2 and not window.bench_tabs.isTabEnabled(1),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            window.close()
            app.quit()

        QTimer.singleShot(1200, finish_smoke_test)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
