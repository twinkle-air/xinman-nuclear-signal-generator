from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, QThread, Qt, Signal, Slot, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..device import DeviceState, DeviceStatus, SerialDevice, SimulatedDevice, available_serial_ports
from ..importers import BUILTIN_NUCLIDES, builtin_spectrum, load_spectrum, load_waveform
from ..models import ArrivalMode, ChannelConfig, NoiseType, PileupMode, PulseShape, SignalSource
from ..report import export_html, export_waveforms_csv
from ..signal_engine import pulse_fwhm_us, simulate_channel
from .widgets import WaveformPlot, WorkflowIndicator
from .tutorial import TUTORIAL_SECTIONS, TutorialDialog
from .bench_panel import BenchPanel
from .bench_worker import BenchWorker
from .responsive import ResponsiveView


def card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 14)
    return frame, layout


class OperationThread(QThread):
    progress = Signal(int, str)
    succeeded = Signal()
    failed = Signal(str)

    def __init__(self, task, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._task = task

    def run(self) -> None:
        try:
            self._task(self.progress.emit)
        except Exception as error:
            self.failed.emit(str(error))
        else:
            self.succeeded.emit()


class ConnectionModeSelector(QWidget):
    modeChanged = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._buttons: dict[str, QPushButton] = {}
        for mode in ("模拟", "单通道台架", "USB CDC", "ST-Link VCP"):
            button = QPushButton(mode)
            button.setObjectName("modeButton")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.clicked.connect(lambda checked, value=mode: self.modeChanged.emit(value) if checked else None)
            self._buttons[mode] = button
            layout.addWidget(button)
        self._buttons["模拟"].setChecked(True)

    def currentText(self) -> str:
        return next(mode for mode, button in self._buttons.items() if button.isChecked())

    def setCurrentText(self, mode: str) -> None:
        if mode not in self._buttons:
            return
        self._buttons[mode].setChecked(True)
        self.modeChanged.emit(mode)

    def count(self) -> int:
        return len(self._buttons)

    def modes(self) -> list[str]:
        return list(self._buttons)


class ChannelPanel(QWidget):
    def __init__(self, channel: int, source: SignalSource) -> None:
        super().__init__()
        self.channel = channel
        self._source = source
        form = QFormLayout(self)
        form.setContentsMargins(8, 12, 8, 8)
        form.setSpacing(9)
        self.enabled = QCheckBox("启用本通道")
        self.enabled.setChecked(True)
        self.shape = QComboBox(); self.shape.addItems([item.value for item in PulseShape])
        self.shape.setCurrentText(PulseShape.DOUBLE.value)
        self.amplitude = self._spin(0.1, 5, 1.5, 0.1, " V")
        self.peak_voltage = QLabel()
        self.peak_voltage.setObjectName("subtitle")
        self.rise = self._spin(0.02, 499, 1.0, 0.1, " μs")
        self.decay = self._spin(0.05, 500, 10.0, 1.0, " μs")
        self.fwhm = self._spin(1, 100, 10.0, 1.0, " μs")
        self.fwhm.setToolTip("题目要求：1–100 μs，步进不大于1 μs")
        self.interval = self._spin(10, 10000, 20.0, 10.0, " μs")
        self.rate = QLabel(); self.rate.setObjectName("subtitle")
        self.arrival = QComboBox(); self.arrival.addItems([item.value for item in ArrivalMode])
        self.arrival.setCurrentText(ArrivalMode.POISSON.value)
        self.pileup = QComboBox(); self.pileup.addItems([item.value for item in PileupMode])
        self.noise_type = QComboBox(); self.noise_type.addItems([item.value for item in NoiseType])
        self.noise_type.setCurrentText(NoiseType.BAND_LIMITED.value)
        self.noise = self._spin(0, 20, 2.0, 1.0, "%FS")
        self.baseline = self._spin(0, 5, 0.25, 0.05, " V")
        self.drift = self._spin(0, 100, 2.0, 1.0, " mV")
        for label, widget in [
            ("", self.enabled), ("脉冲形状", self.shape), ("满量程电压 E_FS", self.amplitude),
            ("预计主峰输出", self.peak_voltage),
            ("上升常数", self.rise), ("衰减常数", self.decay), ("周期/平均间隔", self.interval),
            ("脉冲宽度 FWHM", self.fwhm),
            ("事件到达", self.arrival), ("配置重复频率", self.rate),
            ("重叠处理", self.pileup), ("噪声模型", self.noise_type),
            ("噪声RMS", self.noise), ("直流基线", self.baseline), ("基线漂移", self.drift),
        ]:
            form.addRow(label, widget)
        self.shape.currentTextChanged.connect(self._sync_fwhm)
        self.rise.valueChanged.connect(self._sync_fwhm)
        self.decay.valueChanged.connect(self._sync_fwhm)
        self.fwhm.valueChanged.connect(self._apply_fwhm)
        self.interval.valueChanged.connect(self._update_rate)
        self.amplitude.valueChanged.connect(self._update_peak_voltage)
        self._sync_fwhm()
        self._update_rate()
        self._update_peak_voltage()

    @staticmethod
    def _spin(minimum: float, maximum: float, value: float, step: float, suffix: str) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(); spin.setRange(minimum, maximum); spin.setValue(value)
        spin.setSingleStep(step); spin.setSuffix(suffix); spin.setDecimals(2)
        return spin

    def config(self) -> ChannelConfig:
        return ChannelConfig(
            enabled=self.enabled.isChecked(), pulse_shape=PulseShape(self.shape.currentText()),
            amplitude_v=self.amplitude.value(), rise_us=self.rise.value(), decay_us=self.decay.value(),
            mean_interval_us=self.interval.value(), arrival_mode=ArrivalMode(self.arrival.currentText()),
            pileup_mode=PileupMode(self.pileup.currentText()), noise_type=NoiseType(self.noise_type.currentText()),
            noise_rms_percent=self.noise.value(), baseline_v=self.baseline.value(), drift_mv=self.drift.value(),
            seed=20260817 + self.channel,
        )

    def _sync_fwhm(self) -> None:
        try:
            value = min(100.0, max(1.0, pulse_fwhm_us(self.config())))
            blocker = QSignalBlocker(self.fwhm)
            self.fwhm.setValue(value)
            del blocker
        except ValueError:
            return

    def _apply_fwhm(self, target_us: float) -> None:
        try:
            current = pulse_fwhm_us(self.config())
        except ValueError:
            return
        if current <= 0:
            return
        scale = target_us / current
        rise_blocker = QSignalBlocker(self.rise)
        decay_blocker = QSignalBlocker(self.decay)
        self.rise.setValue(max(self.rise.minimum(), min(self.rise.maximum(), self.rise.value() * scale)))
        self.decay.setValue(max(self.decay.minimum(), min(self.decay.maximum(), self.decay.value() * scale)))
        del rise_blocker, decay_blocker
        self._sync_fwhm()

    def _update_rate(self) -> None:
        rate_hz = 1_000_000.0 / self.interval.value()
        self.rate.setText(f"{rate_hz / 1000:.1f} kHz（最大配置100 kHz）")

    def set_source(self, source: SignalSource) -> None:
        self._source = source
        self._update_peak_voltage()

    def _update_peak_voltage(self) -> None:
        if self._source.kind == "waveform":
            self.peak_voltage.setText(f"模板归一化峰值 → {self.amplitude.value():.2f} V")
            return
        full_scale = max(self._source.full_scale_x or float(self._source.x.max()), 1.0)
        unit = "keV" if self._source.full_scale_x == 2000.0 else "横轴单位"
        if self._source.reference_peaks:
            peaks = self._source.reference_peaks
        else:
            peaks = (float(self._source.x[int(self._source.y.argmax())]),)
        energy_text = "/".join(f"{peak:.1f}" for peak in peaks)
        voltage_text = "/".join(f"{self.amplitude.value() * peak / full_scale:.2f}" for peak in peaks)
        self.peak_voltage.setText(f"{energy_text} {unit} → {voltage_text} V")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("核信号工作台 · PC 上位机")
        self.resize(1440, 860)
        self.source: SignalSource = builtin_spectrum("Cs-137")
        self.results = []
        self.device = SimulatedDevice(self._on_status)
        self._operation: OperationThread | None = None
        self._bench_worker: BenchWorker | None = None
        self._bench_mode = False
        self._bench_busy = False
        self._bench_dirty = True
        self._bench_status: dict = {}
        self._closing = False
        self._disconnect_message = ""
        self.channel_panels = [ChannelPanel(1, self.source), ChannelPanel(2, self.source)]
        self.tutorial_dialog: TutorialDialog | None = None
        self._build_ui()
        # 小窗口同步缩放原有界面，不引入页面滚动条。
        self.setMinimumSize(720, 480)
        if self.screen() is not None:
            available = self.screen().availableGeometry()
            self.resize(min(1440, available.width() - 40), min(860, available.height() - 60))
        for panel in self.channel_panels:
            panel.enabled.toggled.connect(self.preview)
        for control in (self.bench_panel.baseline, self.bench_panel.amplitude, self.bench_panel.period, self.bench_panel.tau):
            control.valueChanged.connect(self._bench_parameters_changed)
        self.preview()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(ResponsiveView(root, self))
        outer = QVBoxLayout(root); outer.setContentsMargins(20, 15, 20, 16); outer.setSpacing(12)
        header = QHBoxLayout()
        titles = QVBoxLayout(); title = QLabel("核信号工作台"); title.setObjectName("title")
        self.subtitle = QLabel(f"双通道仿核信号生成 · V{__version__}"); self.subtitle.setObjectName("subtitle")
        titles.addWidget(title); titles.addWidget(self.subtitle); header.addLayout(titles); header.addStretch()
        self.state_badge = QLabel("未连接"); self.state_badge.setObjectName("stateBadge"); header.addWidget(self.state_badge)
        self.device_mode = ConnectionModeSelector()
        self.device_mode.modeChanged.connect(self.change_device_mode); header.addWidget(self.device_mode)
        self.port_combo = QComboBox(); self.port_combo.setMinimumWidth(190)
        self.port_combo.setEditable(True)
        self.port_combo.setInsertPolicy(QComboBox.NoInsert)
        self.port_combo.setToolTip("可选择自动发现的串口，也可手动输入 COM3 等端口号")
        header.addWidget(self.port_combo)
        self.baud_combo = QComboBox(); self.baud_combo.addItems(["115200", "460800", "921600"])
        self.baud_combo.setCurrentText("921600"); self.baud_combo.setToolTip("ST-Link VCP与STM32 UART必须设置相同波特率")
        header.addWidget(self.baud_combo)
        self.refresh_ports_button = QPushButton("刷新串口"); self.refresh_ports_button.clicked.connect(self.refresh_ports)
        header.addWidget(self.refresh_ports_button)
        self.connect_button = QPushButton("连接"); self.connect_button.clicked.connect(self.toggle_connection)
        header.addWidget(self.connect_button); outer.addLayout(header)
        self.bench_status_label = QLabel()
        self.bench_status_label.setWordWrap(True)
        self.bench_status_label.setVisible(False)
        outer.addWidget(self.bench_status_label)
        self.change_device_mode("模拟")

        content = QGridLayout(); content.setSpacing(12); content.setColumnStretch(0, 2); content.setColumnStretch(1, 5); content.setColumnStretch(2, 3)
        source_card, source_layout = card(); source_title = QLabel("信号源"); source_title.setObjectName("section"); source_layout.addWidget(source_title)
        self.source_combo = QComboBox(); self.source_combo.addItems(list(BUILTIN_NUCLIDES))
        self.source_combo.setCurrentText("Cs-137"); self.source_combo.currentTextChanged.connect(self.select_builtin)
        source_layout.addWidget(self.source_combo)
        import_spectrum = QPushButton("导入 256/1024 道能谱"); import_spectrum.clicked.connect(self.import_spectrum)
        import_wave = QPushButton("导入逐点波形"); import_wave.clicked.connect(self.import_waveform)
        source_layout.addWidget(import_spectrum); source_layout.addWidget(import_wave)
        self.source_controls = (self.source_combo, import_spectrum, import_wave)
        self.source_info = QLabel("内置理想模板 · 1024 道"); self.source_info.setWordWrap(True); self.source_info.setObjectName("subtitle")
        source_layout.addWidget(self.source_info)
        workflow_title = QLabel("操作流程"); workflow_title.setObjectName("section"); source_layout.addWidget(workflow_title)
        self.workflow = WorkflowIndicator(); source_layout.addWidget(self.workflow, 1)

        preview_card, preview_layout = card(); row = QHBoxLayout(); preview_title = QLabel("实时波形预览"); preview_title.setObjectName("section")
        self.preview_title = preview_title
        row.addWidget(preview_title); row.addStretch(); self.metrics = QLabel(); self.metrics.setObjectName("subtitle"); row.addWidget(self.metrics)
        preview_layout.addLayout(row); self.plot = WaveformPlot(); preview_layout.addWidget(self.plot)
        zoom_row = QHBoxLayout()
        zoom_help = QLabel("滚轮缩放 · 左键拖动 · 双击复位"); zoom_help.setObjectName("subtitle")
        self.reset_zoom_button = QPushButton("波形居中"); self.reset_zoom_button.clicked.connect(self.plot.reset_view)
        self.full_scale_button = QPushButton("0–5 V满量程"); self.full_scale_button.clicked.connect(self.plot.show_full_scale)
        zoom_row.addWidget(zoom_help); zoom_row.addStretch(); zoom_row.addWidget(self.reset_zoom_button)
        zoom_row.addWidget(self.full_scale_button)
        preview_layout.addLayout(zoom_row)
        note = QLabel("红色 CH1 · 蓝色 CH2；预览用于配置验证，不代替示波器实测。")
        self.preview_note = note
        note.setObjectName("subtitle"); preview_layout.addWidget(note)

        param_card, param_layout = card(); param_title = QLabel("通道参数"); param_title.setObjectName("section"); param_layout.addWidget(param_title)
        tabs = QTabWidget(); tabs.addTab(self.channel_panels[0], "CH1"); tabs.addTab(self.channel_panels[1], "CH2")
        self.parameter_stack = QStackedWidget(); self.parameter_stack.addWidget(tabs)
        self.bench_panel = BenchPanel()
        self.bench_tabs = QTabWidget(); self.bench_tabs.addTab(self.bench_panel, "CH1 · DAC码值")
        unsupported = QLabel("CH2：当前硬件不支持")
        self.bench_tabs.addTab(unsupported, "CH2 · 当前硬件不支持"); self.bench_tabs.setTabEnabled(1, False)
        self.parameter_stack.addWidget(self.bench_tabs); param_layout.addWidget(self.parameter_stack)
        preview_button = QPushButton("更新预览"); preview_button.setObjectName("primary"); preview_button.clicked.connect(self.preview); param_layout.addWidget(preview_button)

        content.addWidget(source_card, 0, 0); content.addWidget(preview_card, 0, 1); content.addWidget(param_card, 0, 2)
        outer.addLayout(content, 1)

        footer_card, footer = card(); controls = QHBoxLayout(); footer.addLayout(controls)
        self.tutorial_button = QPushButton("使用教程")
        self.tutorial_button.setObjectName("tutorial")
        self.tutorial_button.clicked.connect(self.show_tutorial)
        controls.addWidget(self.tutorial_button)
        self.device_message = QLabel("等待连接"); self.device_message.setObjectName("subtitle"); controls.addWidget(self.device_message); controls.addStretch()
        self.export_csv_button = QPushButton("导出双通道 CSV"); self.export_csv_button.clicked.connect(self.export_csv)
        report_button = QPushButton("生成验证报告"); report_button.clicked.connect(self.export_report)
        self.report_button = report_button
        self.recover_button = QPushButton("恢复台架")
        self.recover_button.clicked.connect(lambda: self._request_bench("recover")); self.recover_button.setVisible(False)
        self.transfer_progress = QProgressBar(); self.transfer_progress.setRange(0, 100); self.transfer_progress.setValue(0)
        self.transfer_progress.setFixedWidth(150); controls.addWidget(self.transfer_progress)
        self.transfer_button = QPushButton("下发波形与参数"); self.transfer_button.setObjectName("transfer"); self.transfer_button.clicked.connect(self.apply_config)
        self.start_button = QPushButton("启动输出"); self.start_button.setObjectName("primary"); self.start_button.clicked.connect(self.start_output)
        self.stop_button = QPushButton("安全停止"); self.stop_button.setObjectName("stop"); self.stop_button.clicked.connect(self.stop_output)
        controls.addWidget(self.export_csv_button); controls.addWidget(report_button); controls.addWidget(self.recover_button); controls.addWidget(self.transfer_button); controls.addWidget(self.start_button); controls.addWidget(self.stop_button)
        outer.addWidget(footer_card)
        self.statusBar().showMessage("模拟器已就绪")

    def _configs(self) -> list[ChannelConfig]:
        return [panel.config() for panel in self.channel_panels]

    def _set_bench_mode(self, enabled: bool) -> None:
        self._bench_mode = enabled
        self.workflow.set_steps(
            ("识别台架", "设置码值参数", "恢复连接", "提交并回读", "启动输出")
            if enabled else self.workflow.STEPS
        )
        self.parameter_stack.setCurrentIndex(1 if enabled else 0)
        self.plot.unit = "码" if enabled else "V"
        self.plot.full_scale = 255.0 if enabled else 5.0
        self.full_scale_button.setText("0–255码满量程" if enabled else "0–5 V满量程")
        self.preview_title.setText("台架参数模型 · 非实测" if enabled else "实时波形预览")
        self.preview_note.setText(
            "仅为DAC码序列模型；电压、极性和负载响应以示波器为准，未进行伏特校准。"
            if enabled else "红色 CH1 · 蓝色 CH2；预览用于配置验证，不代替示波器实测。"
        )
        reason = "台架固件仅支持固定周期单指数，未实现能谱/波形上传、随机事件及噪声"
        for control in self.source_controls:
            control.setEnabled(not enabled)
            control.setToolTip(reason if enabled else "")
        self.source_info.setText(reason if enabled else f"{self.source.name} · {self.source.kind}")
        for control in (self.export_csv_button, self.report_button):
            control.setEnabled(not enabled)
            control.setToolTip("台架码值模型不适用双通道伏特CSV/模拟验证报告" if enabled else "")
        self.recover_button.setVisible(enabled)
        self.bench_status_label.setVisible(enabled)
        self.transfer_button.setText("提交台架参数" if enabled else "下发波形与参数")
        if enabled:
            self._bench_dirty = True
            self.bench_status_label.setText("等待HELLO能力验证及真实设备状态回读；固定115200波特率")
            self._update_bench_buttons()
        elif self._bench_worker is None:
            self._set_busy(False)
        self.preview()

    def _bench_parameters_changed(self) -> None:
        self._bench_dirty = True
        if self._bench_mode:
            self._update_bench_buttons()
            try:
                self.bench_panel.config().validate()
            except ValueError as error:
                self.metrics.setText(str(error))
            else:
                self.preview()

    def _update_bench_buttons(self) -> None:
        online = self._bench_worker is not None and not self._disconnect_message
        ready = online and not self._bench_busy
        running = self._bench_status.get("state") == "RUN"
        self.transfer_button.setEnabled(ready and not running)
        self.recover_button.setEnabled(ready and not running)
        self.start_button.setEnabled(
            ready and not self._bench_dirty and self._bench_status.get("verified") is True
            and self._bench_status.get("state") == "CONFIG" and self._bench_status.get("fpga") is True
            and self._bench_status.get("error") == "OK"
        )
        self.stop_button.setEnabled(online)
        self.bench_panel.setEnabled(not self._bench_busy)

    def _request_bench(self, name: str) -> None:
        if self._bench_worker is None or (self._bench_busy and name != "stop"):
            return
        try:
            config = self.bench_panel.config() if name == "submit" else None
            if config is not None:
                config.validate()
        except ValueError as error:
            QMessageBox.warning(self, "台架参数无效", str(error))
            return
        self._bench_busy = True
        self._update_bench_buttons()
        self.statusBar().showMessage(f"正在执行台架{name}…")
        self._bench_worker.request(name, config)

    @Slot(object)
    def _on_bench_status(self, status: dict) -> None:
        self._bench_status = status
        self._on_status(self.device.status)
        self.bench_status_label.setText(
            f"单通道台架 · {self.device.status.firmware} · {status['state']} / {status['error']} · "
            f"FPGA {'在线' if status['fpga'] else '离线'} · generation {status['generation']} · "
            f"安全旁路：{'启用（A/B/PG未检测）' if status.get('safety_bypass') is True else '状态未提供'}"
        )
        self.bench_panel.readback.setText(
            f"基线 {status['dac_baseline_code']} 码 · 幅度差 {status['dac_amplitude_code']} 码\n"
            f"周期 {status['period_us']} μs · τ {status['decay_us']:.2f} μs\n"
            "以上为设备活动参数回读；非实测电压"
        )
        if status["state"] == "RUN" and status["error"] == "OK" and status["fpga"]:
            self.workflow.set_step(4, "设备回读：输出运行中")
        elif status["state"] == "CONFIG" and status.get("verified"):
            self.workflow.set_step(4, "参数回读一致，可以启动")
        else:
            self.workflow.set_step(3, "已停止或故障，需恢复/重新提交")
        self._update_bench_buttons()

    @Slot(str)
    def _on_bench_completed(self, name: str) -> None:
        self._bench_busy = False
        if name == "submit":
            self._bench_dirty = not self.bench_panel.config().matches(self._bench_status)
            self.transfer_progress.setValue(100)
        elif name in ("recover", "stop"):
            self._bench_dirty = True
            self.transfer_progress.setValue(0)
        self.statusBar().showMessage(f"台架{name}完成，设备状态已回读确认", 5000)
        self._update_bench_buttons()

    @Slot(str, str)
    def _on_bench_error(self, name: str, message: str) -> None:
        self._bench_busy = False
        self._bench_dirty = True
        self._bench_status = {}
        self.state_badge.setText("状态未知" if name == "poll" else "操作失败")
        self.bench_status_label.setText(f"台架{name}失败：{message}。状态未确认，请停止或恢复台架。")
        self.bench_panel.readback.setText("回读失效；不使用缓存状态判断设备仍在运行")
        self.workflow.set_step(3, "状态未确认，需恢复/重新提交")
        self.transfer_progress.setValue(0)
        self._update_bench_buttons()

    def _shutdown_bench(self) -> None:
        if self._bench_worker is None:
            return
        self._disconnect_message = "正在停止并断开…"
        self.connect_button.setEnabled(False)
        self._bench_busy = True
        self._update_bench_buttons()
        self.bench_status_label.setText(self._disconnect_message)
        self._bench_worker.shutdown()

    @Slot(str)
    def _on_bench_closed(self, message: str) -> None:
        self._disconnect_message = message

    @Slot()
    def _bench_thread_finished(self) -> None:
        worker = self._bench_worker
        self._bench_worker = None
        self._bench_busy = False
        self._bench_dirty = True
        self._bench_status = {}
        self._on_status(self.device.status)
        self.bench_status_label.setText(self._disconnect_message)
        self.statusBar().showMessage(self._disconnect_message)
        if "停止未确认" in self._disconnect_message:
            QMessageBox.warning(self, "台架停止未确认", self._disconnect_message)
        self._disconnect_message = ""
        self.device_mode.setEnabled(True)
        self.connect_button.setEnabled(True)
        self.port_combo.setEnabled(True)
        if worker is not None:
            worker.deleteLater()
        self._update_bench_buttons()
        if self._closing:
            QTimer.singleShot(0, self.close)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._bench_worker is not None:
            self._closing = True
            self._shutdown_bench()
            event.ignore()
            return
        if self._operation is not None:
            self._closing = True
            event.ignore()
            return
        if self._disconnect_message:
            self.statusBar().showMessage(self._disconnect_message)
        super().closeEvent(event)

    def show_tutorial(self) -> None:
        if self.tutorial_dialog is None:
            self.tutorial_dialog = TutorialDialog(self)
        self.tutorial_dialog.show()
        self.tutorial_dialog.raise_()
        self.tutorial_dialog.activateWindow()

    def preview(self) -> None:
        try:
            if self._bench_mode:
                time_us, codes = self.bench_panel.config().preview()
                self.plot.set_data(time_us, [(codes, QColor("#d62828"), "CH1 码值模型")])
                self.metrics.setText("固定周期 · 1 μs步进 · 参数模型，非实测")
                return
            configs = self._configs()
            self.results = [simulate_channel(config, self.source) for config in configs]
            colors = ("#d62828", "#0057b8")
            visible_results = [
                (index, result) for index, (config, result)
                in enumerate(zip(configs, self.results, strict=True)) if config.enabled
            ]
            self.plot.set_data(self.results[0].time_us, [
                (result.voltage_v, QColor(colors[index]), f"CH{index + 1}")
                for index, result in visible_results
            ])
            clips = sum(result.clip_count for _index, result in visible_results)
            pileups = sum(result.pileup_count for _index, result in visible_results)
            self.metrics.setText(
                f"堆积 {pileups} 次  ·  削顶 {clips} 点" if visible_results else "两路通道均未启用"
            )
            self.statusBar().showMessage("预览已更新", 3000)
        except Exception as error:
            QMessageBox.warning(self, "参数无效", str(error))

    def select_builtin(self, name: str) -> None:
        self.source = builtin_spectrum(name)
        for panel in self.channel_panels:
            panel.set_source(self.source)
        self.source_info.setText("内置理想模板 · 1024 道")
        self.workflow.set_step(1, "当前：设置通道参数")
        self.preview()

    def import_spectrum(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "导入能谱", "", "数据文件 (*.txt *.csv *.xlsx)")
        if path:
            self._load_source(lambda: load_spectrum(path))

    def import_waveform(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "导入波形", "", "数据文件 (*.txt *.csv *.xlsx)")
        if path:
            self._load_source(lambda: load_waveform(path))

    def _load_source(self, loader) -> None:
        try:
            self.source = loader()
            for panel in self.channel_panels:
                panel.set_source(self.source)
            self.source_info.setText(f"{self.source.name} · {self.source.kind}\nSHA-256 {self.source.sha256[:12]}…")
            self.workflow.set_step(1, "当前：设置通道参数")
            self.preview()
        except Exception as error:
            QMessageBox.critical(self, "导入失败", str(error))

    def toggle_connection(self) -> None:
        if self._bench_worker is not None:
            self._shutdown_bench()
            return
        if self._operation is not None:
            return
        if self.device.status.state == DeviceState.DISCONNECTED:
            try:
                mode = self.device_mode.currentText()
                if mode != "模拟":
                    port = self._selected_port()
                    if not port:
                        target = "ST-Link VCP" if mode == "ST-Link VCP" else "STM32 USB CDC"
                        raise RuntimeError(f"未选择{target}串口。可点击“刷新串口”或手动输入 COM3 等端口号")
                    baudrate = int(self.baud_combo.currentText()) if mode == "ST-Link VCP" else 115200
                    self.device = SerialDevice(
                        str(port),
                        baudrate=baudrate,
                        transport_name=mode,
                    )
                else:
                    self.device = SimulatedDevice()
                self._run_operation(
                    lambda _progress: self.device.connect(),
                    "正在打开串口并进行协议握手…" if mode != "模拟" else "正在连接模拟设备…",
                    self._connection_succeeded,
                    "连接失败",
                )
            except Exception as error:
                QMessageBox.critical(self, "连接失败", str(error))
        else:
            self.device.disconnect()
            self._on_status(self.device.status)
            self.workflow.set_step(2, "当前：连接设备")

    def _selected_port(self) -> str:
        data = self.port_combo.currentData()
        if data:
            return str(data).strip()
        text = self.port_combo.currentText().strip()
        if not text or text == "未发现串口，可手动输入 COM 端口":
            return ""
        return text.split(" · ", 1)[0].strip()

    def _connection_succeeded(self) -> None:
        bench = isinstance(self.device, SerialDevice) and self.device.is_bench
        if self.device_mode.currentText() == "单通道台架" and not bench:
            self.device.disconnect()
            self._on_status(self.device.status)
            QMessageBox.warning(self, "设备不匹配", "所选台架模式需要F405-B2.0.0、bench=true、channels=1")
            return
        self._set_bench_mode(bench)
        if bench:
            self._bench_worker = BenchWorker(self.device, self)
            self._bench_worker.updated.connect(self._on_bench_status)
            self._bench_worker.completed.connect(self._on_bench_completed)
            self._bench_worker.failed.connect(self._on_bench_error)
            self._bench_worker.closed.connect(self._on_bench_closed)
            self._bench_worker.finished.connect(self._bench_thread_finished)
            self._bench_worker.request("recover")
            self._bench_busy = True
            self._bench_worker.start()
        self._on_status(self.device.status)
        self.workflow.set_step(3, "连接成功，下一步：下发配置")
        self.statusBar().showMessage("串口已打开，V1协议握手成功", 5000)

    def change_device_mode(self, mode: str) -> None:
        if self._bench_worker is not None:
            return
        if self.device.status.state != DeviceState.DISCONNECTED:
            self.device.disconnect()
        hardware = mode != "模拟"
        stlink = mode == "ST-Link VCP"
        self.port_combo.setVisible(hardware)
        self.baud_combo.setVisible(stlink)
        self.refresh_ports_button.setVisible(hardware)
        if mode == "单通道台架":
            button_text = "连接台架"
            guidance = "单通道台架：CH340/USART1，115200，HELLO确认F405-B2.0.0"
        elif stlink:
            button_text = "连接ST-Link"
            guidance = "VCP模式：ST-Link TX/RX必须连接STM32 UART，不能只接SWDIO/SWCLK"
        elif hardware:
            button_text = "连接USB CDC"
            guidance = "请选择STM32 USB CDC串口并连接"
        else:
            button_text = "连接模拟设备"
            guidance = "模拟模式：不连接真实硬件"
        self.connect_button.setText(button_text)
        self.device_message.setText(guidance) if hasattr(self, "device_message") else None
        if hardware:
            self.refresh_ports()
        if hasattr(self, "workflow"):
            self.workflow.set_step(2, "当前：连接设备")
            self._set_bench_mode(mode == "单通道台架")

    def refresh_ports(self) -> None:
        current = self._selected_port()
        self.port_combo.clear()
        prefer_stlink = self.device_mode.currentText() == "ST-Link VCP"
        discovered = available_serial_ports(prefer_stlink=prefer_stlink)
        for port, description in discovered:
            self.port_combo.addItem(f"{port} · {description}", port)
        if current:
            index = self.port_combo.findData(current)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)
            else:
                self.port_combo.setEditText(current)
        if self.port_combo.count() == 0:
            self.port_combo.setEditText("未发现串口，可手动输入 COM 端口")
            self.device_message.setText("Windows未枚举到串口；请检查驱动/数据线，也可手动输入 COM3")
        else:
            self.statusBar().showMessage(f"Windows已发现 {len(discovered)} 个串口；连接后还需通过V1协议握手", 5000)

    def _on_status(self, status: DeviceStatus) -> None:
        self.state_badge.setText(status.state.value)
        self.device_message.setText(f"{status.message}  ·  FW {status.firmware}  ·  FPGA {status.fpga}")
        if status.state != DeviceState.DISCONNECTED:
            self.connect_button.setText("断开设备")
        else:
            mode = self.device_mode.currentText()
            if mode == "ST-Link VCP":
                self.connect_button.setText("连接ST-Link")
            elif mode == "USB CDC":
                self.connect_button.setText("连接USB CDC")
            elif mode == "单通道台架":
                self.connect_button.setText("连接台架")
            else:
                self.connect_button.setText("连接模拟设备")

    def apply_config(self) -> None:
        if self._bench_mode:
            self._request_bench("submit")
            return
        if self._operation is not None:
            return
        try:
            self.transfer_progress.setValue(0)
            configs = [replace(item) for item in self._configs()]
            source = self.source
            self._run_operation(
                lambda progress: self.device.transfer(configs, source, progress),
                "正在下发波形与参数…",
                self._transfer_succeeded,
                "下发失败",
            )
        except Exception as error:
            QMessageBox.warning(self, "下发失败", str(error))

    def _transfer_succeeded(self) -> None:
        self._on_status(self.device.status)
        self.workflow.set_step(4, "配置完成，下一步：启动输出")
        self.transfer_progress.setValue(100)
        self.statusBar().showMessage("波形与双通道参数已收到设备ACK并提交", 5000)
        self.preview()

    def _run_operation(self, task, message: str, on_success, error_title: str) -> None:
        self._set_busy(True)
        self.statusBar().showMessage(message)
        operation = OperationThread(task, self)
        self._operation = operation
        operation.progress.connect(self._on_transfer_progress)
        operation.succeeded.connect(on_success)
        operation.finished.connect(lambda: self._finish_operation(operation))
        operation.failed.connect(lambda error: self._operation_failed(operation, error_title, error))
        operation.start()

    def _finish_operation(self, operation: OperationThread) -> None:
        if self._operation is operation:
            self._operation = None
        self._set_busy(False)
        operation.deleteLater()
        if self._closing:
            QTimer.singleShot(0, self.close)

    def _operation_failed(self, operation: OperationThread, title: str, message: str) -> None:
        self.transfer_progress.setValue(0)
        self.statusBar().showMessage(f"{title}：{message}", 8000)
        QMessageBox.critical(self, title, message)

    def _set_busy(self, busy: bool) -> None:
        self.connect_button.setEnabled(not busy)
        self.refresh_ports_button.setEnabled(not busy)
        self.device_mode.setEnabled(not busy)
        self.port_combo.setEnabled(not busy)
        self.baud_combo.setEnabled(not busy)
        self.transfer_button.setEnabled(not busy)
        self.start_button.setEnabled(not busy)
        self.stop_button.setEnabled(not busy)
        if self._bench_worker is not None:
            self.device_mode.setEnabled(False)
            self.port_combo.setEnabled(False)
            self.baud_combo.setEnabled(False)
            self._update_bench_buttons()

    def _on_transfer_progress(self, value: int, message: str) -> None:
        self.transfer_progress.setValue(value)
        self.statusBar().showMessage(message)

    def start_output(self) -> None:
        if self._bench_mode:
            self._request_bench("start")
            return
        try:
            self.device.start()
            self._on_status(self.device.status)
            self.workflow.set_step(4, "当前：输出运行中")
        except Exception as error:
            QMessageBox.warning(self, "无法启动", str(error))

    def stop_output(self) -> None:
        if self._bench_mode:
            self._request_bench("stop")
            return
        try:
            self.device.stop()
            self._on_status(self.device.status)
            if self.device.status.state == DeviceState.DISCONNECTED:
                self.workflow.set_step(2, "设备未连接，无输出需要停止")
                self.statusBar().showMessage("设备未连接，无输出需要停止", 5000)
            else:
                self.workflow.set_step(4, "输出已安全停止，可重新启动")
                self.statusBar().showMessage("输出已安全停止", 5000)
        except Exception as error:
            QMessageBox.warning(self, "停止失败", str(error))

    def export_csv(self) -> None:
        if not self.results:
            self.preview()
        path, _ = QFileDialog.getSaveFileName(self, "导出双通道波形", "dual_channel_waveforms.csv", "CSV (*.csv)")
        if path:
            target = Path(path)
            if target.suffix.lower() != ".csv":
                target = target.with_suffix(".csv")
            try:
                export_waveforms_csv(target, self.results)
            except Exception as error:
                QMessageBox.critical(self, "CSV导出失败", f"无法写入 {target}\n\n{error}")
                return
            self.statusBar().showMessage(f"已导出双通道CSV：{target.name}", 5000)

    def export_report(self) -> None:
        if not self.results:
            self.preview()
        path, _ = QFileDialog.getSaveFileName(self, "生成验证报告", "simulation_report.html", "HTML (*.html)")
        if path:
            export_html(path, self._configs(), self.source, self.results)
            self.statusBar().showMessage(f"已生成 {Path(path).name}", 5000)
