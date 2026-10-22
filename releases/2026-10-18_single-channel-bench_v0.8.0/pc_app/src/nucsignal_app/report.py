from __future__ import annotations

import csv
import html
import os
import tempfile
from datetime import datetime
from pathlib import Path

from .models import ChannelConfig, SignalSource, SimulationResult
from .signal_engine import pulse_fwhm_us


def _interval_metrics(result: SimulationResult) -> tuple[str, str]:
    if result.event_times_us.size < 4:
        return "样本不足", "样本不足"
    import numpy as np

    intervals = np.diff(result.event_times_us)
    mean = float(np.mean(intervals))
    cv = float(np.std(intervals, ddof=1) / mean) if mean > 0 else 0.0
    ordered = np.sort(intervals)
    empirical = np.arange(1, ordered.size + 1) / ordered.size
    theoretical = 1.0 - np.exp(-ordered / mean)
    ks_d = float(np.max(np.abs(empirical - theoretical)))
    return f"{cv:.3f}", f"{ks_d:.3f}"


def export_csv(path: str | Path, result: SimulationResult) -> None:
    with Path(path).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["time_us", "voltage_v", "ideal_v"])
        writer.writerows(zip(result.time_us, result.voltage_v, result.ideal_v, strict=True))


def export_waveforms_csv(path: str | Path, results: list[SimulationResult]) -> None:
    """原子写入双通道波形；失败时不破坏已有目标文件。"""
    if len(results) != 2:
        raise ValueError("双通道CSV导出需要恰好两个通道结果")
    if results[0].time_us.size != results[1].time_us.size:
        raise ValueError("CH1与CH2采样点数不一致，无法合并导出")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.stem}-", suffix=".tmp", dir=target.parent
        )
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        with temporary_path.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.writer(stream)
            writer.writerow([
                "time_us", "ch1_voltage_v", "ch1_ideal_v",
                "ch2_voltage_v", "ch2_ideal_v",
            ])
            writer.writerows(zip(
                results[0].time_us,
                results[0].voltage_v,
                results[0].ideal_v,
                results[1].voltage_v,
                results[1].ideal_v,
                strict=True,
            ))
        temporary_path.replace(target)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def export_html(
    path: str | Path,
    configs: list[ChannelConfig],
    source: SignalSource,
    results: list[SimulationResult],
) -> None:
    rows = []
    for index, (config, result) in enumerate(zip(configs, results, strict=True), start=1):
        interval_cv, ks_d = _interval_metrics(result)
        rate_khz = 1000.0 / config.mean_interval_us
        rows.append(
            f"<tr><td>CH{index}</td><td>{config.pulse_shape.value}</td>"
            f"<td>{config.arrival_mode.value}</td><td>{config.pileup_mode.value}</td>"
            f"<td>{pulse_fwhm_us(config):.2f} μs</td><td>{rate_khz:.2f} kHz</td>"
            f"<td>{config.noise_rms_percent:.1f}%FS</td><td>{result.rms_noise_v:.4f} V</td>"
            f"<td>{interval_cv}</td><td>{ks_d}</td>"
            f"<td>{result.event_times_us.size}</td><td>{result.pileup_count}</td>"
            f"<td>{result.clip_count}</td></tr>"
        )
    source_hash = source.sha256 or "内置模板"
    document = f"""<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><title>核信号工作台验证报告</title>
<style>body{{font:15px/1.6 system-ui;margin:40px;color:#172033}}h1{{color:#1565c0}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #d8e1ec;padding:9px;text-align:left}}
th{{background:#edf5ff}}.note{{padding:12px;background:#fff8e1;border-left:4px solid #f9a825}}</style>
<h1>核信号工作台验证报告</h1>
<p>生成时间：{datetime.now().isoformat(timespec='seconds')}</p>
<p>信号源：{html.escape(source.name)}；类型：{source.kind}；SHA-256：{source_hash}</p>
<p class="note">本报告来自软件模型。幅度精度±5%、波形失真、抖动、额外谐波和长时间稳定性必须使用示波器/频谱仪实测，不能由本报告替代。</p>
<table><thead><tr><th>通道</th><th>脉冲</th><th>到达</th><th>堆积</th>
<th>FWHM</th><th>配置频率</th><th>设定噪声</th><th>模拟RMS</th><th>间隔CV</th><th>指数CDF KS-D</th>
<th>事件数</th><th>堆积数</th><th>削顶点</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></html>"""
    Path(path).write_text(document, encoding="utf-8")
