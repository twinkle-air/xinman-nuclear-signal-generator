"""Single-channel evidence tools; no direct serial access or automatic output."""
from dataclasses import asdict, fields
from datetime import date
import hashlib
import html
import json
import re
from pathlib import Path

import numpy as np
from PySide6.QtCore import QSignalBlocker, QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QTabWidget, QWidget,
    QPushButton, QPlainTextEdit, QLineEdit, QDoubleSpinBox, QComboBox, QCheckBox,
    QTextBrowser, QFileDialog, QMessageBox, QLabel)

from .. import __version__
from ..bench import BenchConfig
from ..measurement import Calibration, read_scope, analyze_scope, fit_fixed_pulses, export_measurement, _hist_svg
from ..models import SignalSource
from ..nuclear import spectrum_quantiles


class MeasurementDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.measurement = None
        self.original_source = window.source
        self.setWindowTitle("单通道 · 校准、实测与配置")
        self.resize(970, 760)
        outer = QVBoxLayout(self); tabs = QTabWidget(); outer.addWidget(tabs)
        self.output = QTextBrowser(); self.output.setMinimumHeight(210)
        self._calibration_tab(tabs)
        self._scope_tab(tabs)
        self._spectrum_tab(tabs)
        self._profile_tab(tabs)
        outer.addWidget(self.output, 1)
        self.output.setText("校准需要外部测量；分析不会启动或停止设备。配置更改后须重新提交并回读。")

    def _tab(self, tabs, title):
        widget = QWidget(); form = QFormLayout(widget); tabs.addTab(widget, title)
        return form

    def _button(self, form, title, callback):
        button = QPushButton(title); button.clicked.connect(lambda: self._guard(callback)); form.addRow(button)

    def _guard(self, callback):
        try:
            callback()
        except Exception as error:
            QMessageBox.warning(self, "操作未完成", str(error))

    def _require_stopped(self):
        if self.window._bench_busy or self.window._bench_status.get("state") == "RUN":
            raise ValueError("请先停止输出，再修改配置或应用校准")

    def _set_html(self, body):
        # QTextDocument does not render inline <svg>; convert only the embedded
        # charts to PNG images. The external HTML report retains vector SVG.
        def convert(match):
            renderer=QSvgRenderer(QByteArray(match.group(0).encode("utf-8")))
            size=renderer.defaultSize()
            image=QImage(size,QImage.Format_ARGB32);image.fill(0xffffffff)
            painter=QPainter(image);renderer.render(painter);painter.end()
            data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.WriteOnly)
            image.save(buffer,"PNG");buffer.close()
            return '<p><img src="data:image/png;base64,'+bytes(data.toBase64()).decode('ascii')+'"></p>'
        self.output.setHtml(re.sub(r'<svg\b.*?</svg>',convert,body,flags=re.S))

    def _calibration_tab(self, tabs):
        form = self._tab(tabs, "电压校准")
        self.points = QPlainTextEdit(); self.points.setPlaceholderText("每行：DAC码,实测电压V；至少3点，递增码值、单调电压。不得用模型值代替实测。")
        self.points.setMaximumHeight(110); form.addRow("实测传输点", self.points)
        self.instrument = QLineEdit(); self.load = QLineEdit(); self.probe = QLineEdit(); self.cal_date = QLineEdit(date.today().isoformat())
        for name, control in (("仪器",self.instrument),("负载/端接",self.load),("探头倍率",self.probe),("日期",self.cal_date)):
            form.addRow(name, control)
        self.target = QDoubleSpinBox(); self.target.setRange(.001, 20); self.target.setDecimals(3); self.target.setSingleStep(.1); self.target.setValue(1); self.target.setSuffix(" V，相对基线")
        form.addRow("目标幅度", self.target)
        self._button(form, "应用到当前幅度码（不下发设备）", self.apply_calibration)
        self._button(form, "保存校准文件", self.save_calibration)
        self._button(form, "加载校准文件", self.load_calibration)
        if getattr(self.window, "_calibration", None):
            self._show_calibration(self.window._calibration)

    def _calibration(self):
        pairs = [line.split(",") for line in self.points.toPlainText().splitlines() if line.strip()]
        obj = Calibration(tuple(int(p[0]) for p in pairs), tuple(float(p[1]) for p in pairs),
                          self.instrument.text(),self.load.text(),self.probe.text(),self.cal_date.text())
        obj.validate(); return obj

    def _show_calibration(self, obj):
        self.points.setPlainText('\n'.join(f'{c},{v:.9g}' for c,v in zip(obj.codes,obj.volts)))
        for control, value in ((self.instrument,obj.instrument),(self.load,obj.load_condition),(self.probe,obj.probe),(self.cal_date,obj.date)):
            control.setText(value)

    def apply_calibration(self):
        self._require_stopped(); obj = self._calibration()
        code, actual = obj.amplitude_code(self.window.bench_panel.baseline.value(), self.target.value())
        self.window.bench_panel.amplitude.setValue(code)
        self.window._calibration = obj
        self.window._bench_parameters_changed()
        error = (actual / self.target.value() - 1) * 100
        self.output.setText(f"已设置幅度码差{code}；校准插值预测幅度{actual:.6g}V，量化偏差{error:+.2f}%。\n"
                            "这是预测，仍需示波器独立验证±5%；不自动启动。高斯%FS定义为255码，部分区间校准不能证明全量程RMS。")

    def save_calibration(self):
        obj = self._calibration()
        path,_ = QFileDialog.getSaveFileName(self,"保存校准","calibration.json","JSON (*.json)")
        if path: obj.save(path); self.window._calibration = obj

    def load_calibration(self):
        path,_ = QFileDialog.getOpenFileName(self,"加载校准","","JSON (*.json)")
        if path:
            obj = Calibration.load(path); self._show_calibration(obj); self.window._calibration = obj

    def _scope_tab(self, tabs):
        form = self._tab(tabs, "示波器CSV")
        self.time_unit = QComboBox(); self.time_unit.addItems(["秒 s", "微秒 μs"])
        self.voltage_unit = QComboBox(); self.voltage_unit.addItems(["伏 V", "毫伏 mV"])
        self.probe_factor = QDoubleSpinBox(); self.probe_factor.setRange(.001,10000); self.probe_factor.setValue(1)
        self.polarity = QComboBox(); self.polarity.addItems(["负向", "正向"])
        self.threshold = QDoubleSpinBox(); self.threshold.setRange(.000001,100); self.threshold.setDecimals(6); self.threshold.setValue(.1)
        self.dead_time = QDoubleSpinBox(); self.dead_time.setRange(.001,1000000); self.dead_time.setValue(20); self.dead_time.setSuffix(" μs")
        self.noise_only = QCheckBox("本段为无脉冲基线，计算噪声RMS/相关性")
        self.fixed_fit = QCheckBox("已确认采集周期和τ：附加固定周期指数拟合（保留零/低幅周期）")
        self.fit_period = QDoubleSpinBox();self.fit_period.setRange(1,1000000);self.fit_period.setValue(self.window.bench_panel.period.value());self.fit_period.setSuffix(" μs")
        self.fit_tau = QDoubleSpinBox();self.fit_tau.setRange(.1,100000);self.fit_tau.setValue(self.window.bench_panel.tau.value());self.fit_tau.setSuffix(" μs")
        self.bandwidth = QLineEdit(); self.bandwidth.setPlaceholderText("填写示波器带宽/限带设置；未知则填未知")
        for name, control in (("CSV时间单位",self.time_unit),("CSV电压单位",self.voltage_unit),
            ("附加探头倍率（CSV已折算则为1）",self.probe_factor),("脉冲极性",self.polarity),
            ("检出阈值 V",self.threshold),("最小分辨间隔",self.dead_time),("测量带宽",self.bandwidth)):
            form.addRow(name,control)
        form.addRow(self.noise_only)
        form.addRow(self.fixed_fit);form.addRow("采集时固定周期",self.fit_period);form.addRow("采集时τ",self.fit_tau)
        self._button(form,"导入并分析Hantek两列CSV",self.import_scope)
        self._button(form,"导出单通道实测HTML报告",self.export_report)

    def import_scope(self):
        path,_ = QFileDialog.getOpenFileName(self,"导入示波器CSV","","CSV (*.csv)")
        if not path: return
        t,v,meta = read_scope(path,time_scale=1e-6 if self.time_unit.currentIndex() else 1,
                             voltage_scale=.001 if self.voltage_unit.currentIndex() else 1,probe=self.probe_factor.value())
        result = analyze_scope(t,v,polarity=1 if self.polarity.currentIndex() else -1,
                               threshold_v=self.threshold.value(),dead_time_us=self.dead_time.value(),noise_only=self.noise_only.isChecked())
        meta["bandwidth"] = self.bandwidth.text() or "未知"
        if self.fixed_fit.isChecked():
            result["fixed_fit"] = fit_fixed_pulses(t,v,polarity=1 if self.polarity.currentIndex() else -1,
                period_us=self.fit_period.value(),tau_us=self.fit_tau.value())
        context = self.context()
        self.measurement = {"source":meta,"result":result}
        # Capture context now: later configuration edits must not relabel this record.
        self.measurement_context = context
        self.raw_scope = Path(path).read_bytes()
        self._set_html(_hist_svg(result["amplitude_hist"],"实测采样峰值幅度 / V") +
            _hist_svg(result["interval_hist"],"检出间隔 / μs（红线为指数期望）") +
            '<pre>'+html.escape(json.dumps(result,ensure_ascii=False,indent=2))+'</pre>')

    def context(self):
        config = self.window._current_bench_config()
        d = asdict(config); table = d.pop("spectrum_table")
        return {"pc_version":__version__,"firmware":self.window.device.status.firmware,
            "fpga":self.window.device.status.fpga,"device_status_at_import":dict(self.window._bench_status),
            "requested_config_at_import":d,"spectrum_table_sha256":hashlib.sha256(table).hexdigest() if table else None,
            "spectrum_name":self.window.source.name,"spectrum_sha256":self.window.source.sha256,
            "calibration":asdict(self.window._calibration) if getattr(self.window,"_calibration",None) else None,
            "note":"导入时回读和配置不自动证明它们就是CSV采集时条件；请核对。"}

    def export_report(self):
        if not self.measurement: raise ValueError("请先导入实际示波器CSV")
        path,_ = QFileDialog.getSaveFileName(self,"导出实测报告","single_channel_measurement.html","HTML (*.html)")
        if path:
            raw_path=Path(path).with_name(Path(path).stem+".source_"+self.measurement["source"]["sha256"][:12]+".csv")
            if raw_path.exists():
                if raw_path.read_bytes()!=self.raw_scope: raise ValueError("原始数据副本目标已存在且内容不同")
            else:
                with raw_path.open("xb") as stream: stream.write(self.raw_scope)
            context={**self.measurement_context,"raw_csv_copy":raw_path.name}
            export_measurement(path,self.measurement,context)

    def _spectrum_tab(self, tabs):
        form = self._tab(tabs,"能谱量程")
        self.full_scale = QDoubleSpinBox(); self.full_scale.setRange(.001,1e7); self.full_scale.setDecimals(3); self.full_scale.setValue(self.window.source.full_scale_x or max(self.window.source.x));
        form.addRow("满量程（沿用输入轴单位）",self.full_scale)
        form.addRow(QLabel("内置谱单位keV：Am-241可评估300；Cs-137为1000；Co-60为1600。窗口外计数须明确确认。"))
        self._button(form,"预览输入与量化后幅度分布",self.spectrum_preview)
        self._button(form,"应用量程（不下发设备）",self.apply_spectrum_scale)

    def spectrum_preview(self):
        config = self.window._current_bench_config()
        table = np.frombuffer(spectrum_quantiles(self.window.source),dtype=np.uint8).astype(int)
        codes = (config.amplitude_code*table+127)//255
        observed = np.bincount(codes,minlength=256)/len(codes)
        src = self.window.source
        ideal_codes = np.floor(src.x/src.full_scale_x*config.amplitude_code+.5).astype(int)
        original = np.bincount(ideal_codes,weights=src.y/src.y.sum(),minlength=256)
        self._set_html(_hist_svg({"counts":original.tolist(),"edges":list(range(257))},"输入谱映射到实际幅度码的概率")+
            _hist_svg({"counts":observed.tolist(),"edges":list(range(257))},"256项分位表量化后的预期概率（模型，非实测）")+
            '<p>实测分布在示波器CSV页查看；二者单位分别为码和伏，需校准后比较。</p>')

    def apply_spectrum_scale(self):
        self._require_stopped(); src = self.original_source; scale = self.full_scale.value()
        keep = src.x <= scale
        mass = float(src.y[~keep].sum()/src.y.sum())
        if np.count_nonzero(keep)<2 or src.y[keep].sum()<=0: raise ValueError("窗口内没有足够有效能谱")
        if mass > 0 and QMessageBox.question(self,"确认能谱窗口",f"窗口外计数概率{mass:.4%}，将裁剪并重新归一化。是否应用？") != QMessageBox.Yes: return
        self.window.source = SignalSource(src.name+f" [FS={scale:g};裁剪{mass:.4%}]","spectrum",
            src.x[keep].copy(),src.y[keep]/src.y[keep].sum(),src.source_path,src.sha256,scale,tuple(p for p in src.reference_peaks if p<=scale))
        self.window._bench_parameters_changed(); self.spectrum_preview()

    def _profile_tab(self, tabs):
        form = self._tab(tabs,"配置与运行记录")
        form.addRow(QLabel("配置文件含源谱和参数，加载不会下发或启动。运行记录为设备数字计数，不能替代示波器。"))
        self.preset = QComboBox();self.preset.addItems(["50 kHz固定短脉冲", "Am-241低计数率", "Cs-137低计数率", "Co-60双峰演示", "无脉冲高斯噪声5%FS"])
        form.addRow("N4演示预设",self.preset)
        self._button(form,"应用预设（不下发、不启动）",self.apply_preset)
        self._button(form,"保存当前配置",self.save_profile)
        self._button(form,"加载配置（仅同固件模式）",self.load_profile)
        self._button(form,"查看运行趋势",self.show_trend)
        self._button(form,"导出运行记录JSON",self.export_trend)

    def apply_preset(self):
        self._require_stopped();panel=self.window.bench_panel
        if not panel.competition: raise ValueError("此组演示预设需要N4固件；旧版可使用手动配置")
        which=self.preset.currentIndex()
        panel.random.setChecked(False);panel.pileup.setChecked(False)
        panel.baseline.setValue(128 if which==4 else 96)
        panel.amplitude.setValue(0 if which==4 else 84)
        panel.spectrum.setChecked(False);panel.noise.setValue(0);panel.rms.setValue(0)
        panel.noise_mode.setCurrentIndex(1 if which==4 else 0)
        panel.period.setValue(1000 if which==4 else 2000)
        panel.tau.setValue(12 if which==4 else 24)
        if which==0:
            panel.tau.setValue(2);panel.period.setValue(20)
        elif which==4:
            panel.rms.setValue(5)
        else:
            name=("Am-241","Cs-137","Co-60")[which-1]
            self.window.select_builtin(name);self.original_source=self.window.source
            self.full_scale.setValue((300,1000,1600)[which-1])
            self.apply_spectrum_scale() # explicitly confirm any removed probability
            panel.spectrum.setChecked(True);panel.random.setChecked(True)
        self.window._bench_parameters_changed()
        self.output.setText("预设已应用，请检查配置并重新提交。未下发或启动；预设不是性能达标证明。")

    def save_profile(self):
        config = self.window._current_bench_config(); config.validate()
        data = asdict(config); data["spectrum_table"] = list(config.spectrum_table)
        src = self.window.source
        payload = {"schema":1,"config":data,"source":{"name":src.name,"x":src.x.tolist(),"y":src.y.tolist(),
            "full_scale_x":src.full_scale_x,"sha256":src.sha256}}
        path,_ = QFileDialog.getSaveFileName(self,"保存配置","bench_profile.json","JSON (*.json)")
        if path: Path(path).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")

    def load_profile(self):
        self._require_stopped()
        path,_ = QFileDialog.getOpenFileName(self,"加载配置","","JSON (*.json)")
        if not path: return
        if Path(path).stat().st_size > 2*1024*1024: raise ValueError("配置文件过大")
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        if payload.get("schema") != 1: raise ValueError("配置版本不支持")
        values = dict(payload["config"]); values["spectrum_table"] = bytes(values["spectrum_table"])
        if set(values) != {f.name for f in fields(BenchConfig)}: raise ValueError("配置字段不完整")
        config = BenchConfig(**values); config.validate(); panel = self.window.bench_panel
        if config.nuclear != panel.nuclear or config.competition != panel.competition: raise ValueError("固件模式不匹配，请连接对应版本")
        if config.seed > panel.seed.maximum(): raise ValueError("种子超出当前界面范围（1–2147483647）")
        src = payload["source"]
        source = SignalSource(str(src["name"]),"spectrum",np.asarray(src["x"],dtype=float),np.asarray(src["y"],dtype=float),
                              sha256=src.get("sha256"),full_scale_x=src["full_scale_x"])
        table = spectrum_quantiles(source)
        if config.spectrum_table and config.spectrum_table != table: raise ValueError("配置分位表与源谱不匹配")
        widgets = [panel.baseline,panel.amplitude,panel.period,panel.tau,panel.random,panel.spectrum,panel.noise,
                   panel.seed,panel.noise_mode,panel.rms,panel.pileup]
        blockers = [QSignalBlocker(w) for w in widgets]
        panel.random.setChecked(config.random_events); panel._period_range()
        for control, value in ((panel.baseline,config.baseline_code),(panel.amplitude,config.amplitude_code),
            (panel.period,config.period_us),(panel.tau,config.tau_us),(panel.noise,config.noise_peak_codes),
            (panel.seed,config.seed),(panel.rms,config.noise_rms_percent)): control.setValue(value)
        panel.noise_mode.setCurrentIndex(int(config.noise_mode=="gaussian")); panel.pileup.setChecked(config.allow_pileup)
        panel.spectrum.setChecked(bool(config.spectrum_table)); panel.table = config.spectrum_table
        self.window.source = source; self.original_source = source
        self.window.source_info.setText(source.name+" · 已加载配置源谱")
        del blockers
        panel._tau_changed(config.tau_us); panel._noise_visibility(); self.window._bench_parameters_changed()
        self.output.setText("配置已加载，请检查参数后重新提交并回读；尚未下发或启动。")

    def show_trend(self):
        rows = getattr(self.window,"_bench_history",[])
        body='<h3>设备数字计数趋势（非示波器）</h3>'
        for key,label in (("events_per_s","事件率 / s"),("clips_per_s","削顶样点率 / s")):
            values=[r[key] for r in rows if key in r][-600:]
            if len(values)>1:
                maximum=max(values) or 1
                points=' '.join(f'{40+i*540/(len(values)-1):.2f},{190-v*150/maximum:.2f}' for i,v in enumerate(values))
                body+=f'<h4>{label}，纵轴0—{maximum:.4g}</h4><svg viewBox="0 0 620 215" width="620"><polyline points="{points}" fill="none" stroke="#1764ad" stroke-width="2"/></svg>'
        self._set_html(body+'<pre>'+html.escape(json.dumps(rows[-10:],ensure_ascii=False,indent=2))+'</pre>')

    def export_trend(self):
        path,_ = QFileDialog.getSaveFileName(self,"导出设备运行记录","bench_history.json","JSON (*.json)")
        if path: Path(path).write_text(json.dumps({"kind":"device_readback_not_scope","rows":getattr(self.window,"_bench_history",[])},ensure_ascii=False,indent=2),encoding="utf-8")
