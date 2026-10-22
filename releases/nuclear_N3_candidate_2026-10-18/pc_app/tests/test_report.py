import csv

from nucsignal_app.importers import builtin_spectrum
from nucsignal_app.models import ChannelConfig
from nucsignal_app.report import export_html, export_waveforms_csv
from nucsignal_app.signal_engine import simulate_channel


def test_export_waveforms_csv_contains_both_channels(tmp_path) -> None:
    source = builtin_spectrum("Cs-137")
    results = [
        simulate_channel(ChannelConfig(seed=1), source),
        simulate_channel(ChannelConfig(seed=2), source),
    ]
    target = tmp_path / "waveforms.csv"
    export_waveforms_csv(target, results)
    with target.open(newline="", encoding="utf-8-sig") as stream:
        rows = csv.reader(stream)
        assert next(rows) == [
            "time_us", "ch1_voltage_v", "ch1_ideal_v",
            "ch2_voltage_v", "ch2_ideal_v",
        ]
        assert len(next(rows)) == 5
    assert not list(tmp_path.glob("*.tmp"))


def test_validation_report_contains_competition_metrics(tmp_path) -> None:
    source = builtin_spectrum("Cs-137")
    configs = [ChannelConfig(seed=1), ChannelConfig(seed=2)]
    results = [simulate_channel(config, source, duration_us=2000) for config in configs]
    target = tmp_path / "report.html"
    export_html(target, configs, source, results)
    content = target.read_text(encoding="utf-8")
    assert "配置频率" in content
    assert "指数CDF KS-D" in content
    assert "示波器/频谱仪实测" in content
