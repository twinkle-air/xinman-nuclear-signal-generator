from dataclasses import replace
import json
import math

import numpy as np
import pytest

from nucsignal_app.bench import BenchConfig
from nucsignal_app.measurement import Calibration, read_scope, analyze_scope, fit_fixed_pulses, export_measurement
from nucsignal_app.nuclear import reference, GAUSSIAN_Q8
from nucsignal_app.protocol import Frame, Command, Flags
from test_nuclear import NuclearSerial
from test_bench import connected


class CompetitionSerial(NuclearSerial):
    def __init__(self):
        super().__init__()
        self.hello.update(firmware="F405-N4.0.0",fpga="FPGA-4.0.0")
        self.ext.update(noise_mode="uniform",noise_rms_percent=0,allow_pileup=0)


def test_n4_transaction_and_old_version_gates():
    config = BenchConfig(128,0,10,1,nuclear=True,competition=True,noise_mode="gaussian",noise_rms_percent=20)
    device,serial = connected(CompetitionSerial())
    result = device.bench_submit(config)
    assert config.matches(result)
    assert result["noise_peak_codes"] == 0 and result["noise_rms_percent"] == 20
    device.bench_start(); device.bench_stop()
    old,_ = connected(NuclearSerial())
    with pytest.raises(RuntimeError,match="N4"):
        old.bench_submit(config)
    serial.ext.pop("allow_pileup")
    with pytest.raises(ValueError,match="N4"):
        device.read_bench_status()


def test_short_period_width_and_explicit_pileup():
    config = BenchConfig(96,84,20,2,nuclear=True,competition=True)
    codes,events,_,clips = reference(config,2000)
    assert len(events) == 100 and np.all(np.diff(events)==20) and clips == 0
    replace(config,period_us=10,tau_us=1).validate()
    replace(config,period_us=1000,tau_us=100/math.log(2)).validate()
    for change in ({"competition":False},{"period_us":9},{"period_us":20,"tau_us":100},
                   {"random_events":True,"period_us":20},{"tau_us":146}):
        with pytest.raises(ValueError): replace(config,**change).validate()
    replace(config,period_us=20,tau_us=100,allow_pileup=True).validate()


def test_gaussian_distribution_rms_clipping_seed_and_stop_contract():
    config = BenchConfig(128,0,1000,12,nuclear=True,competition=True,noise_mode="gaussian",noise_rms_percent=5)
    values,_,_,clips = reference(config,100000)
    noise = values.astype(float)-128
    assert abs(noise.mean()) < .2 and abs(noise.std()-255*.05) < .25
    assert abs(np.corrcoef(noise[:-1],noise[1:])[0,1]) < .02
    assert np.mean(np.abs(noise)<=12.75) > .65
    assert clips == 0
    assert np.array_equal(values[:100],reference(config,100)[0])
    assert not np.array_equal(values[:100],reference(replace(config,seed=2),100)[0])
    assert np.std(np.asarray(GAUSSIAN_Q8)/256) == pytest.approx(1,abs=.002)
    assert reference(replace(config,noise_rms_percent=20),100000)[3] > 0
    assert np.all(reference(replace(config,noise_rms_percent=0),1000)[0]==128)


def test_monotone_calibration_no_extrapolation_and_nearest_code(tmp_path):
    c = Calibration((0,128,255),(3.0,-.2,-3.375),"test scope","1Mohm","x1","2026-10-19")
    code,prediction = c.amplitude_code(96,1.0)
    assert code == 40 and prediction == pytest.approx(1)
    with pytest.raises(ValueError): c.voltage(256)
    with pytest.raises(ValueError): c.amplitude_code(254,1)
    with pytest.raises(ValueError): replace(c,volts=(0,1,.5)).validate()
    with pytest.raises(ValueError): replace(c,instrument="").validate()
    path=tmp_path/"cal.json";c.save(path);assert Calibration.load(path)==c


def test_scope_csv_time_interpretation_pulses_and_report_escaping(tmp_path):
    t=np.arange(5000)*1e-6
    signal=np.zeros(len(t))
    for start in range(200,4800,200):
        signal[start:]+=np.exp(-(np.arange(len(t)-start))*1e-6/12e-6)
    v=.8-signal
    path=tmp_path/"scope.csv"
    path.write_text('Time [s],CH2 [V]\n'+''.join(f'1e-6,{x},\n' for x in v),encoding="utf-8")
    actual_t,actual_v,meta=read_scope(path)
    assert meta["dt_s"]==1e-6 and np.allclose(actual_t,t)
    result=analyze_scope(actual_t,actual_v,threshold_v=.2,dead_time_us=20)
    assert result["detected_pulses"]==23 and result["mean_interval_us"]==pytest.approx(200)
    assert result["mean_amplitude_v"]==pytest.approx(1,abs=.001)
    assert result["median_tau_us"]==pytest.approx(12,abs=.01)
    report=tmp_path/'report.html'
    export_measurement(report,{"source":meta,"result":result},{"label":"<script>bad</script>"})
    assert '<script>bad</script>' not in report.read_text(encoding='utf-8')
    assert 'exponential_expected' in report.read_text(encoding='utf-8')
    path.write_text('Time,V\n'+''.join(f'{x},{y}\n' for x,y in zip(t,v)),encoding='utf-8')
    assert read_scope(path)[2]["interpretation"]=="递增时间列"
    path.write_text('Time,V\n'+''.join(f'0,{y}\n' for y in v),encoding='utf-8')
    with pytest.raises(ValueError):read_scope(path)


def test_n4_ui_capability_noise_width_and_calibration_apply():
    from PySide6.QtWidgets import QApplication
    from nucsignal_app.ui.main_window import MainWindow
    from nucsignal_app.ui.measurement_dialog import MeasurementDialog
    app=QApplication.instance() or QApplication([])
    window=MainWindow();window.device,_=connected(CompetitionSerial());window._set_bench_mode(True)
    panel=window.bench_panel
    assert panel.competition and panel.period.minimum()==10
    panel.period.setValue(20);panel.tau.setValue(2);panel.noise_mode.setCurrentIndex(1);panel.rms.setValue(5)
    assert window._current_bench_config().noise_rms_percent==5
    panel.fwhm.setValue(100)
    assert panel.tau.value()==pytest.approx(100/math.log(2),abs=.01)
    panel.period.setValue(1000)
    panel.random.setChecked(True);assert panel.period.minimum()==128
    dialog=MeasurementDialog(window)
    dialog.points.setPlainText("0,3\n128,-.2\n255,-3.375")
    dialog.instrument.setText("scope");dialog.load.setText("1Mohm");dialog.probe.setText("x1")
    dialog.target.setValue(1);panel.baseline.setValue(96)
    dialog.apply_calibration()
    assert panel.amplitude.value()==40 and "预测" in dialog.output.toPlainText()
    dialog.spectrum_preview();assert "量化" in dialog.output.toPlainText()
    dialog.close();window.device.disconnect();window.close()


def test_profile_save_load_keeps_custom_source_and_no_start(tmp_path,monkeypatch):
    from PySide6.QtWidgets import QApplication,QFileDialog
    from nucsignal_app.ui.main_window import MainWindow
    from nucsignal_app.ui.measurement_dialog import MeasurementDialog
    app=QApplication.instance() or QApplication([])
    window=MainWindow();window.device,serial=connected(CompetitionSerial());window._set_bench_mode(True)
    panel=window.bench_panel;panel.noise_mode.setCurrentIndex(1);panel.rms.setValue(2)
    panel.spectrum.setChecked(True)
    path=tmp_path/'profile.json'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args:(str(path),''))
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *args:(str(path),''))
    dialog=MeasurementDialog(window);dialog.save_profile()
    expected=window._current_bench_config();panel.rms.setValue(7)
    before=len(serial.received);dialog.load_profile()
    assert window._current_bench_config()==expected and len(serial.received)==before
    dialog.close();window.device.disconnect();window.close()


def test_fixed_fit_preserves_zero_low_amplitude_cycles():
    dt=4e-6;period=64;t=np.arange(period*10)*dt
    amplitudes=np.array([2.,.7,.1,0.,1.,2.,.05,0.,1.5,.8])
    signal=np.concatenate([.8-a*np.exp(-np.arange(period)*dt/48e-6) for a in amplitudes])
    fit=fit_fixed_pulses(t,signal,polarity=-1,period_us=256,tau_us=48)
    assert fit['phase_sample']==0
    assert np.allclose(fit['amplitudes_v'],amplitudes,atol=1e-10)
    assert fit['complete_cycles']==10
