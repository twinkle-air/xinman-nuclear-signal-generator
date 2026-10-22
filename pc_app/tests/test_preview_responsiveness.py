"""Interaction regressions: no hardware or serial port is opened."""
import threading
import time

import numpy as np
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from nucsignal_app.bench import BenchConfig
from nucsignal_app.ui.main_window import MainWindow


def wait_for(app, predicate, timeout=4):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        QTest.qWait(10)
    raise AssertionError('GUI operation timed out')


def test_short_period_preview_has_ten_cycles():
    config = BenchConfig(96, 84, 20, 2, nuclear=True, competition=True)
    t, codes = config.preview()
    assert len(t) == 200
    assert np.count_nonzero(codes == 180) == 10


def test_background_preview_coalesces_edits_and_drops_stale_results(monkeypatch):
    app = QApplication.instance() or QApplication([])
    calls = []
    release = threading.Event()
    entered = threading.Event()
    gui_thread = threading.get_ident()

    def slow_preview(config):
        calls.append((config.amplitude_code, threading.get_ident()))
        entered.set()
        assert release.wait(3)
        return np.arange(2, dtype=float), np.array([96., config.amplitude_code])

    monkeypatch.setattr(BenchConfig, 'preview', slow_preview)
    w = MainWindow()
    w._set_bench_mode(True)
    ticks = []
    timer = QTimer()
    timer.setInterval(10)
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start()
    try:
        wait_for(app, entered.is_set)
        for value in range(100, 130):
            w.bench_panel.amplitude.setValue(value)
        # The GUI continues processing events while a preview is deliberately blocked.
        QTest.qWait(240)
        assert len(ticks) >= 5
        assert len(calls) == 1
        release.set()
        wait_for(app, lambda: len(calls) == 2 and w._preview_thread is None)
        assert calls[-1][0] == 129
        assert all(thread != gui_thread for _, thread in calls)
        assert w.plot._signals[0][0][-1] == 129
        assert w._bench_dirty and not w.start_button.isEnabled()
    finally:
        release.set()
        timer.stop()
        w.close()
        wait_for(app, lambda: w._preview_thread is None)
        w.close()


def test_partial_numeric_input_and_close_remain_responsive(monkeypatch):
    app = QApplication.instance() or QApplication([])
    release = threading.Event()
    entered = threading.Event()

    def slow_preview(config):
        entered.set()
        assert release.wait(3)
        return np.arange(2, dtype=float), np.zeros(2)

    monkeypatch.setattr(BenchConfig, 'preview', slow_preview)
    w = MainWindow()
    w._set_bench_mode(True)
    try:
        wait_for(app, entered.is_set)
        box = w.bench_panel.tau
        old = box.value()
        box.lineEdit().selectAll()
        QTest.keyClick(box.lineEdit(), Qt.Key.Key_Backspace)
        assert box.value() == old
        assert w._bench_dirty
        assert not w._preview_timer.isActive()
        QTest.keyClicks(box.lineEdit(), '2')
        QTest.keyClick(box.lineEdit(), Qt.Key.Key_Return)
        assert box.value() == 2
        w.close()
        assert w._closing and w._preview_thread is not None
    finally:
        release.set()
        wait_for(app, lambda: w._preview_thread is None)
        w.close()
