import time
import pytest
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from nucsignal_app.ui.main_window import MainWindow
from nucsignal_app.ui.style import APP_STYLESHEET
from test_bench import connected
from test_competition import CompetitionSerial
from test_preview_responsiveness import wait_for


@pytest.mark.parametrize('size', [(1440, 870), (900, 600)])
def test_dense_gaussian_render_edit_submit_and_stop(size):
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(APP_STYLESHEET)
    w = MainWindow()
    w.device, transport = connected(CompetitionSerial())
    w._connection_succeeded()
    w.resize(*size)
    w.show()
    ticks = []
    timer = QTimer()
    timer.setInterval(20)
    timer.timeout.connect(lambda: ticks.append(time.monotonic()))
    timer.start()
    try:
        wait_for(app, lambda: not w._bench_busy)
        p = w.bench_panel
        p.baseline.setValue(128); p.amplitude.setValue(0)
        p.period.setValue(2000); p.tau.setValue(24)
        p.noise_mode.setCurrentIndex(1)
        p.rms.lineEdit().selectAll()
        QTest.keyClicks(p.rms.lineEdit(), '5')
        QTest.keyClick(p.rms.lineEdit(), Qt.Key.Key_Return)
        wait_for(app, lambda: not w._preview_timer.isActive() and w._preview_thread is None)
        assert w.plot._signals[0][0].std() > 10
        for _ in range(3):
            start = time.perf_counter()
            pixmap = w.grab()  # Actual QWidget/QGraphicsView/QPainter rasterization.
            assert not pixmap.isNull()
            assert time.perf_counter() - start < .5
        for value in (10, 2, 5):
            p.rms.setValue(value)
        wait_for(app, lambda: not w._preview_timer.isActive() and w._preview_thread is None)
        w.apply_config()
        wait_for(app, lambda: not w._bench_busy)
        assert w._bench_status['noise_rms_percent'] == 5
        assert w.start_button.isEnabled()
        w.start_output()
        wait_for(app, lambda: not w._bench_busy)
        assert w._bench_status['state'] == 'RUN'
        start = time.monotonic()
        w.stop_output()
        wait_for(app, lambda: not w._bench_busy)
        assert time.monotonic() - start < 1
        assert w._bench_status['state'] == 'IDLE'
        assert p.isEnabled() and not w.start_button.isEnabled()
        assert len(ticks) >= 3
    finally:
        timer.stop()
        w.close()
        wait_for(app, lambda: w._bench_worker is None and w._preview_thread is None)
        w.close()
    assert not transport.is_open
