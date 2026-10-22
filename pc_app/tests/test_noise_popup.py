import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from nucsignal_app.ui.main_window import MainWindow
from test_preview_responsiveness import wait_for


@pytest.mark.parametrize('size', [(1440, 900), (900, 600)])
def test_noise_popup_mouse_selection_in_scaled_view(size):
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    w.device.status.firmware = 'F405-N4.0.0'
    w._set_bench_mode(True)
    w.resize(*size)
    w.show()
    app.processEvents()
    view = w.centralWidget()
    view.fit_content()
    combo = w.bench_panel.noise_mode
    w.bench_panel.rms.setValue(5)
    try:
        stable_positions = None
        for index, expected in [(1, 'gaussian'), (0, 'uniform')]:
            local = combo.mapTo(view.content, QPoint(combo.width()-12, combo.height()//2))
            position = view.mapFromScene(view.proxy.mapToScene(QPointF(local)))
            QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=position)
            app.processEvents()
            menu = getattr(combo, '_popup_menu', None)
            assert menu is not None and menu.isVisible()
            assert menu.graphicsProxyWidget() is None
            assert [a.text() for a in menu.actions()] == ['均匀峰值码', '高斯 RMS %FS']
            QTest.mouseClick(menu, Qt.MouseButton.LeftButton,
                             pos=menu.actionGeometry(menu.actions()[index]).center())
            app.processEvents()
            assert combo.currentIndex() == index
            assert combo.currentText() == ['均匀峰值码', '高斯 RMS %FS'][index]
            config = w._current_bench_config()
            assert config.noise_mode == expected
            assert config.noise_rms_percent == (5 if index else 0)
            assert w.bench_panel.rms.isVisible() and w.bench_panel.rms.isEnabled() == bool(index)
            assert w.bench_panel.noise.isVisible() and w.bench_panel.noise.isEnabled() == (not index)
            assert w._bench_dirty and not w.start_button.isEnabled()
            app.processEvents()
            positions = [control.geometry().getRect() for control in (
                combo, w.bench_panel.noise, w.bench_panel.rms, w.bench_panel.seed)]
            if stable_positions is None:
                stable_positions = positions
            else:
                assert positions == stable_positions
    finally:
        w.close()
        wait_for(app, lambda: w._preview_thread is None)
        w.close()
