import pytest
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from nucsignal_app.ui.main_window import MainWindow
from nucsignal_app.signal_engine import pulse_fwhm_us
from nucsignal_app.device import DeviceState, SimulatedDevice, SerialDevice
from test_bench import BenchSerial


def test_main_window_builds_and_previews() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    app.processEvents()
    assert window.windowTitle().startswith("核信号工作台")
    assert len(window.results) == 2
    assert window.results[0].time_us.size == 10_000
    assert "661.7 keV" in window.channel_panels[0].peak_voltage.text()
    assert "0.50 V" in window.channel_panels[0].peak_voltage.text()
    assert window.device_mode.count() == 4
    assert window.device_mode.modes() == ["模拟", "单通道台架", "USB CDC", "ST-Link VCP"]
    assert window.transfer_button.text() == "下发波形与参数"
    assert window.transfer_button.objectName() == "transfer"
    window.device_mode.setCurrentText("ST-Link VCP")
    app.processEvents()
    assert window.port_combo.isVisible()
    assert window.refresh_ports_button.isVisible()
    assert window.connect_button.text() == "连接ST-Link"
    assert window.baud_combo.isVisible()
    assert "V0.9.0" in window.subtitle.text()
    assert window.source_combo.count() == 9
    assert window.channel_panels[0].amplitude.minimum() == 0.1
    assert window.channel_panels[0].interval.minimum() == 10.0
    assert window.channel_panels[0].fwhm.minimum() == 1.0
    assert window.channel_panels[0].fwhm.maximum() == 100.0
    window.channel_panels[0].fwhm.setValue(100.0)
    assert pulse_fwhm_us(window.channel_panels[0].config()) == pytest.approx(100.0, abs=0.1)
    assert window.port_combo.isEditable()
    assert window.export_csv_button.text() == "导出双通道 CSV"
    assert [color.name() for _values, color, _label in window.plot._signals] == ["#d62828", "#0057b8"]
    full_view = window.plot.view_range()
    assert full_view[3] < 2.0
    window.full_scale_button.click()
    assert window.plot.view_range()[2:] == (0.0, 5.0)
    window.reset_zoom_button.click()
    assert window.plot.view_range() == full_view
    window.plot.zoom_at(0.5)
    zoomed_view = window.plot.view_range()
    assert zoomed_view[1] - zoomed_view[0] < full_view[1] - full_view[0]
    assert zoomed_view[3] - zoomed_view[2] < full_view[3] - full_view[2]
    window.reset_zoom_button.click()
    assert window.plot.view_range() == full_view
    assert window.workflow.STEPS == ("选择信号源", "设置参数", "连接设备", "下发配置", "启动输出")

    window.device = SimulatedDevice()
    window.device.connect()
    window.device.commit(window._configs())
    window.device.start()
    window._on_status(window.device.status)
    window.stop_output()
    assert window.device.status.state == DeviceState.IDLE
    assert window.state_badge.text() == DeviceState.IDLE.value
    assert "安全停止" in window.device_message.text()
    assert window.tutorial_button.text() == "使用教程"
    window.show_tutorial()
    app.processEvents()
    assert window.tutorial_dialog.isVisible()
    assert window.tutorial_dialog.tabs.count() == 8
    assert "硬件连接" in window.tutorial_dialog.section_titles()
    window.tutorial_dialog.close()
    window.channel_panels[0].enabled.setChecked(False)
    assert [label for _values, _color, label in window.plot._signals] == ["CH2"]
    window.channel_panels[1].enabled.setChecked(False)
    assert window.plot._signals == []
    assert window.metrics.text() == "两路通道均未启用"
    window.channel_panels[0].enabled.setChecked(True)
    assert [label for _values, _color, label in window.plot._signals] == ["CH1"]
    window.channel_panels[1].enabled.setChecked(True)
    assert [label for _values, _color, label in window.plot._signals] == ["CH1", "CH2"]
    window.port_combo.clear()
    window.port_combo.addItem("COM9 · USB Serial Port (COM9)", "COM9")
    window.port_combo.addItem("COM3 · USB-SERIAL CH340 (COM3)", "COM3")
    window.port_combo.setEditText("com3")
    assert window._selected_port() == "COM3"
    window.port_combo.setCurrentIndex(0)
    window.port_combo.showPopup()
    app.processEvents()
    menu = window.port_combo._popup_menu
    assert menu is not None and menu.isVisible()
    assert menu.graphicsProxyWidget() is None
    QTest.mouseClick(menu, Qt.MouseButton.LeftButton, pos=menu.actionGeometry(menu.actions()[1]).center())
    app.processEvents()
    assert window.port_combo.currentData() == "COM3"
    assert window._selected_port() == "COM3"
    window.device_mode.setCurrentText("单通道台架")
    assert window.parameter_stack.currentIndex() == 1
    assert not window.bench_tabs.isTabEnabled(1)
    assert window.plot.unit == "码"
    assert window.plot.full_scale == 255
    assert "非实测" in window.preview_title.text()
    assert not window.source_combo.isEnabled()
    assert not window.export_csv_button.isEnabled()
    assert not window.start_button.isEnabled()
    assert len(window.plot._signals) == 1
    window.device_mode.setCurrentText("模拟")
    assert window.parameter_stack.currentIndex() == 0
    assert window.source_combo.isEnabled()
    assert window.plot.unit == "V"
    assert len(window.plot._signals) == 2
    # 在同一窗口验证异步自动识别、轮询、提交、启停和安全断开。
    transport = BenchSerial()
    transport.hello["fpga"] = "FPGA-OFFLINE"
    device = SerialDevice("COM_TEST", serial_factory=lambda *a, **kw: transport, timeout_s=0.01)
    device.connect()
    window.device = device
    window._connection_succeeded()

    def wait_for(predicate):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            app.processEvents()
            if predicate():
                return
            time.sleep(0.01)
        raise AssertionError("台架界面等待超时")

    try:
        wait_for(lambda: not window._bench_busy)
        assert window._bench_mode
        assert "generation" in window.bench_status_label.text()
        assert "FPGA 在线" in window.device_message.text()
        assert "FPGA-OFFLINE" not in window.device_message.text()
        transport.online = False
        wait_for(lambda: "FPGA 离线" in window.device_message.text())
        assert "FPGA 离线" in window.bench_status_label.text()
        transport.online = True
        wait_for(lambda: "FPGA 在线" in window.device_message.text())
        window._on_bench_error("poll", "测试回读失败")
        assert "FPGA状态未确认" in window.device_message.text()
        assert "RUN" not in window.device_message.text()
        wait_for(lambda: "FPGA 在线" in window.device_message.text())
        window.apply_config()
        wait_for(lambda: not window._bench_busy)
        assert window.start_button.isEnabled()
        window.start_output()
        wait_for(lambda: not window._bench_busy)
        assert window.state_badge.text() == DeviceState.RUNNING.value
        window.stop_output()
        wait_for(lambda: not window._bench_busy)
        assert window.state_badge.text() == DeviceState.IDLE.value
        assert not window.start_button.isEnabled()
    finally:
        window._shutdown_bench()
        wait_for(lambda: window._bench_worker is None)
    assert not transport.is_open
    window.close()
