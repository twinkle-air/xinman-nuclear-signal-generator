import numpy as np
import pytest

from nucsignal_app.importers import builtin_spectrum
from nucsignal_app.models import ArrivalMode, ChannelConfig, NoiseType, PileupMode, PulseShape
from nucsignal_app.models import SignalSource
from nucsignal_app.signal_engine import pulse_fwhm_us, simulate_channel


def test_simulation_is_repeatable_and_bounded() -> None:
    config = ChannelConfig(seed=7, noise_rms_percent=3.0)
    source = builtin_spectrum("Cs-137")
    first = simulate_channel(config, source, duration_us=200)
    second = simulate_channel(config, source, duration_us=200)
    assert np.array_equal(first.voltage_v, second.voltage_v)
    assert np.all((first.voltage_v >= 0) & (first.voltage_v <= 5))
    assert first.rms_noise_v == pytest.approx(0.15, rel=1e-6)


def test_pileup_occurs_at_high_periodic_rate() -> None:
    config = ChannelConfig(
        pulse_shape=PulseShape.SINGLE,
        arrival_mode=ArrivalMode.PERIODIC,
        pileup_mode=PileupMode.PILEUP,
        mean_interval_us=2,
        decay_us=20,
        noise_type=NoiseType.WHITE,
        noise_rms_percent=0,
    )
    result = simulate_channel(config, builtin_spectrum("Co-60"), duration_us=50)
    assert result.pileup_count > 0


def test_invalid_double_exponential_is_rejected() -> None:
    config = ChannelConfig(rise_us=10, decay_us=2)
    with pytest.raises(ValueError, match="上升时间常数"):
        simulate_channel(config, builtin_spectrum("Am-241"))


def test_imported_waveform_is_used_as_kernel() -> None:
    source = SignalSource("template", "waveform", np.array([0.0, 0.02, 0.04]), np.array([0.0, 1.0, 0.0]))
    config = ChannelConfig(
        amplitude_v=2.0, baseline_v=0, arrival_mode=ArrivalMode.PERIODIC,
        mean_interval_us=10, noise_rms_percent=0, drift_mv=0,
    )
    result = simulate_channel(config, source, duration_us=1)
    assert np.max(result.voltage_v) == pytest.approx(2.0)


def test_fwhm_is_reported_on_sample_grid() -> None:
    assert pulse_fwhm_us(ChannelConfig(pulse_shape=PulseShape.SINGLE, decay_us=10)) == pytest.approx(6.94, abs=0.04)
