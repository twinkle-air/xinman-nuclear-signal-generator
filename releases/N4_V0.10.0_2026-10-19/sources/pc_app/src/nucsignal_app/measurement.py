"""External oscilloscope measurements, kept separate from digital predictions."""
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import html
import json
import math
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class Calibration:
    codes: tuple[int, ...]
    volts: tuple[float, ...]
    instrument: str
    load_condition: str
    probe: str
    date: str

    def validate(self):
        if len(self.codes) != len(self.volts) or len(self.codes) < 3:
            raise ValueError("校准至少需要3个对应的码值/电压点")
        if (any(type(c) is not int or not 0 <= c <= 255 for c in self.codes)
                or any(b <= a for a, b in zip(self.codes, self.codes[1:]))
                or not np.isfinite(self.volts).all()):
            raise ValueError("校准码值必须递增，电压必须有限")
        dv = np.diff(self.volts)
        if not (np.all(dv > 0) or np.all(dv < 0)):
            raise ValueError("校准电压必须严格单调")
        if not all(str(x).strip() for x in (self.instrument, self.load_condition, self.probe, self.date)):
            raise ValueError("请填写仪器、负载、探头倍率和日期")

    def voltage(self, code):
        self.validate()
        if not self.codes[0] <= code <= self.codes[-1]:
            raise ValueError("码值超出实际校准区间，禁止外推")
        return float(np.interp(code, self.codes, self.volts))

    def amplitude_code(self, baseline: int, requested_v: float):
        """Return nearest realizable code and predicted (not measured) amplitude."""
        base_v = self.voltage(baseline)
        if not math.isfinite(requested_v) or requested_v <= 0:
            raise ValueError("目标幅度必须大于0V")
        candidates = np.arange(baseline, self.codes[-1] + 1)
        amplitudes = np.abs(np.interp(candidates, self.codes, self.volts) - base_v)
        if requested_v > amplitudes[-1]:
            raise ValueError("目标超过当前基线下的校准可达幅度")
        i = int(np.argmin(np.abs(amplitudes - requested_v)))
        return int(candidates[i] - baseline), float(amplitudes[i])

    def save(self, path):
        self.validate()
        Path(path).write_text(json.dumps({"schema": 1, **asdict(self)}, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        if data.pop("schema", None) != 1:
            raise ValueError("不支持的校准文件版本")
        obj = cls(tuple(data.pop("codes")), tuple(data.pop("volts")), **data)
        obj.validate()
        return obj


def read_scope(path, *, time_scale=1.0, voltage_scale=1.0, probe=1.0):
    """Hantek two-column CSV: increasing time, or repeated positive dt per row."""
    if any(not math.isfinite(x) or x <= 0 for x in (time_scale, voltage_scale, probe)):
        raise ValueError("时间/电压倍率和探头倍率必须为正有限值")
    p = Path(path)
    raw = p.read_bytes()
    if len(raw) > 64 * 1024 * 1024:
        raise ValueError("单文件超过64MB，请分段导入")
    rows = []
    for n, line in enumerate(raw.decode("utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        fields = line.rstrip(",").split(",")
        try:
            rows.append((float(fields[0]), float(fields[1])))
        except (IndexError, ValueError):
            if not rows and n == 1:
                continue
            raise ValueError(f"第{n}行不是两列有效数值") from None
    a = np.asarray(rows, dtype=float)
    if a.ndim != 2 or len(a) < 16 or not np.isfinite(a).all():
        raise ValueError("至少需要16个有限采样点")
    t = a[:, 0] * time_scale
    if np.all(t == t[0]):
        if t[0] <= 0:
            raise ValueError("重复时间列必须为正采样间隔")
        dt = float(t[0]); t = np.arange(len(t)) * dt
        interpretation = "重复正数时间列按采样间隔解释（请核对示波器采样率）"
    else:
        gaps = np.diff(t)
        dt = float(np.median(gaps))
        if dt <= 0 or not np.allclose(gaps, dt, rtol=.005, atol=dt * .0001):
            raise ValueError("时间列须递增且等间隔")
        t = t - t[0]
        interpretation = "递增时间列"
    return t, a[:, 1] * voltage_scale * probe, {
        "file": p.name, "sha256": hashlib.sha256(raw).hexdigest(), "samples": len(t),
        "dt_s": dt, "sample_rate_hz": 1 / dt, "interpretation": interpretation,
        "time_scale": time_scale, "voltage_scale": voltage_scale, "probe": probe,
    }


def analyze_scope(t, voltage, *, polarity=-1, threshold_v=.1, dead_time_us=20, noise_only=False):
    t, voltage = np.asarray(t,dtype=float), np.asarray(voltage,dtype=float)
    if (t.ndim!=1 or t.shape!=voltage.shape or len(t)<16 or
            not np.isfinite(t).all() or not np.isfinite(voltage).all() or (np.diff(t)<=0).any()):
        raise ValueError("需要等长、有限且时间递增的采样数据")
    if polarity not in (-1, 1) or not math.isfinite(threshold_v) or threshold_v <= 0:
        raise ValueError("极性或检出阈值无效")
    if not math.isfinite(dead_time_us) or dead_time_us <= 0:
        raise ValueError("最小分辨间隔必须为正")
    dt = float(np.median(np.diff(t)))
    baseline = float(np.median(voltage))
    signal = (voltage - baseline) * polarity
    # Threshold segments avoid counting noise extrema several times inside a pulse.
    active = signal >= threshold_v
    starts = np.flatnonzero(active & ~np.r_[False, active[:-1]])
    ends = np.flatnonzero(active & ~np.r_[active[1:], False])
    if noise_only:
        starts,ends=np.array([],dtype=int),np.array([],dtype=int)
    distance = max(1, math.ceil(dead_time_us * 1e-6 / dt))
    peaks = []
    for lo, hi in zip(starts, ends):
        if lo == 0 or hi == len(signal) - 1:
            continue  # partial boundary pulses
        peak = lo + int(np.argmax(signal[lo:hi + 1]))
        if peaks and peak - peaks[-1] < distance:
            if signal[peak] > signal[peaks[-1]]:
                peaks[-1] = peak
        else:
            peaks.append(peak)
    peaks = np.asarray(peaks, dtype=int)
    amps = signal[peaks]
    intervals = np.diff(t[peaks]) * 1e6
    widths, taus = [], []
    for i, peak in enumerate(peaks):
        stop = int(peaks[i + 1]) if i + 1 < len(peaks) else len(signal)
        tail = signal[peak:stop]
        below = np.flatnonzero(tail <= signal[peak] / 2)
        if below.size:
            widths.append(float(below[0] * dt * 1e6))
        use = np.flatnonzero((tail > signal[peak] * .2) & (tail < signal[peak] * .8))
        if len(use) >= 4:
            slope = np.polyfit(use * dt, np.log(tail[use]), 1)[0]
            if slope < 0:
                taus.append(float(-1e6 / slope))
    def histogram(values, bins=20):
        if not len(values):
            return {"edges": [], "counts": []}
        counts, edges = np.histogram(values, bins=bins)
        return {"edges": edges.tolist(), "counts": counts.tolist()}
    result = {
        "baseline_v": baseline, "detected_pulses": len(peaks),
        "threshold_v": threshold_v, "dead_time_us": dead_time_us, "polarity": polarity,
        "duration_s": float(t[-1] - t[0]), "amplitudes_v": amps.tolist(),
        "intervals_us": intervals.tolist(), "amplitude_hist": histogram(amps),
        "interval_hist": histogram(intervals), "mean_amplitude_v": float(amps.mean()) if len(amps) else None,
        "mean_interval_us": float(intervals.mean()) if len(intervals) else None,
        "interval_cv": float(intervals.std(ddof=1) / intervals.mean()) if len(intervals) > 1 else None,
        "median_halfwidth_us": float(np.median(widths)) if widths else None,
        "median_tau_us": float(np.median(taus)) if taus else None,
        "whole_record_ac_rms_v": float(np.std(voltage)),
        "noise_rms_v": float(np.std(voltage)) if noise_only else None,
        "warnings": ["阈值、采样相位、基线占空比与堆积会影响检出；不足以单独证明能谱精度。",
                     "半高宽为采样网格估计；低幅/高占空比时请使用专门拟合。",
                     "间隔按检出的脉冲计算，漏检和最小分辨间隔会改变分布；不自动给出卡方通过结论。"],
    }
    if noise_only:
        centered = voltage - np.mean(voltage)
        variance = float(np.dot(centered, centered))
        result["noise_hist"] = histogram(centered, 32)
        result["lag1_correlation"] = float(np.dot(centered[:-1], centered[1:]) / variance) if variance else None
        result["warnings"].append("噪声RMS仅因用户声明本段为无脉冲基线而报告；须核对采样带宽、倍率和饱和。")
    if len(intervals) >= 2:
        edges = np.asarray(result["interval_hist"]["edges"])
        mean = float(intervals.mean())
        result["interval_hist"]["exponential_expected"] = (
            len(intervals) * (np.exp(-edges[:-1] / mean) - np.exp(-edges[1:] / mean))).tolist()
    # Fixed time-window counts are diagnostic only; no finite-sample pass/fail.
    if t[-1] > 0 and len(peaks):
        result["count_windows"] = np.histogram(t[peaks], bins=np.linspace(0, t[-1], 11))[0].tolist()
    return result


def fit_fixed_pulses(t, voltage, *, polarity, period_us, tau_us):
    """OLS fit baseline + exponential, including low/zero amplitudes, no threshold censor."""
    dt = float(np.median(np.diff(t)))
    if not all(math.isfinite(x) and x>0 for x in (period_us,tau_us,dt)):
        raise ValueError("固定拟合周期和τ必须为正有限数")
    points = int(round(period_us*1e-6/dt))
    if points<8 or points>len(t)//2 or abs(points*dt*1e6-period_us)>period_us*.005:
        raise ValueError("固定拟合至少每周期8点、2周期，周期须与采样网格一致")
    signal=np.asarray(voltage)*polarity
    edge=np.diff(signal,prepend=signal[0])
    scores=np.bincount(np.arange(len(edge))%points,weights=np.maximum(edge,0),minlength=points)
    phase=int(np.argmax(scores))
    cycles=[signal[i:i+points] for i in range(phase,len(signal)-points+1,points)]
    cycles=np.asarray(cycles)
    k=np.arange(2,points) # exclude first two edge samples
    kernel=np.exp(-k*dt/(tau_us*1e-6))
    design=np.column_stack((np.ones(len(k)),kernel))
    coefficients=np.linalg.lstsq(design,cycles[:,2:].T,rcond=None)[0]
    residual=cycles[:,2:].T-design@coefficients
    return {"method":"fixed_period_known_tau_OLS","assumed_period_us":period_us,"assumed_tau_us":tau_us,
            "phase_sample":phase,"complete_cycles":len(cycles),"amplitudes_v":coefficients[1].tolist(),
            "mean_amplitude_v":float(coefficients[1].mean()),
            "median_residual_rms_v":float(np.median(np.sqrt(np.mean(residual**2,axis=0)))),
            "warning":"拟合依赖人工确认的周期和τ；不适用于随机间隔、非指数或截顶数据。"}


def _hist_svg(hist, title):
    counts, edges = hist.get("counts", []), hist.get("edges", [])
    if not counts:
        return "<p>无足够数据：" + html.escape(title) + "</p>"
    maximum = max(counts) or 1
    bars = ''.join(f'<rect x="{40+i*540/len(counts):.2f}" y="{190-c*150/maximum:.2f}" width="{max(1,540/len(counts)-1):.2f}" height="{c*150/maximum:.2f}" fill="#1764ad"/>' for i,c in enumerate(counts))
    expected = hist.get("exponential_expected")
    line = ''
    if expected:
        points = ' '.join(f'{40+(i+.5)*540/len(counts):.2f},{190-c*150/maximum:.2f}' for i,c in enumerate(expected))
        line = f'<polyline points="{points}" fill="none" stroke="#c33" stroke-width="2"/>'
    return f'<h3>{html.escape(title)}</h3><svg viewBox="0 0 620 225" width="620">{bars}{line}<text x="40" y="215">{edges[0]:.4g}</text><text x="520" y="215">{edges[-1]:.4g}</text></svg>'


def export_measurement(path, measurement, context):
    """One inspectable HTML file with the full JSON evidence payload embedded as text."""
    payload = {"schema": 1, "created": datetime.now().astimezone().isoformat(),
               "kind": "external_scope_measurement", "measurement": measurement, "context": context}
    raw = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
    body = '<h1>单通道外部实测分析</h1><p>设备回读、模型预测和示波器数据分别保存；未自动判定比赛全指标通过。</p>'
    body += _hist_svg(measurement["result"]["amplitude_hist"], "实测采样峰值幅度 / V")
    body += _hist_svg(measurement["result"]["interval_hist"], "实测检出间隔 / μs（红线为样本均值拟合的指数期望）")
    if "noise_hist" in measurement["result"]:
        body += _hist_svg(measurement["result"]["noise_hist"], "无脉冲基线幅度分布 / V")
    if "fixed_fit" in measurement["result"]:
        values=measurement["result"]["fixed_fit"]["amplitudes_v"]
        counts,edges=np.histogram(values,bins=24)
        body+=_hist_svg({"counts":counts.tolist(),"edges":edges.tolist()},"固定周期指数拟合幅度 / V（含低/零幅周期）")
    body += '<h2>数据与限制</h2><pre>' + html.escape(raw) + '</pre>'
    Path(path).write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>单通道实测报告</title><style>body{font:16px sans-serif;max-width:1000px;margin:30px auto}pre{white-space:pre-wrap;overflow-wrap:anywhere}svg{max-width:100%}</style>' + body + '</html>', encoding="utf-8")
