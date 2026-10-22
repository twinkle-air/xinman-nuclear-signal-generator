from pathlib import Path

import numpy as np

from nucsignal_app.importers import BUILTIN_NUCLIDES, builtin_spectrum, load_spectrum, load_waveform


def test_builtin_spectra_are_normalized() -> None:
    assert len(BUILTIN_NUCLIDES) == 9
    for name in BUILTIN_NUCLIDES:
        source = builtin_spectrum(name)
        assert source.y.size == 1024
        assert np.isclose(source.y.sum(), 1.0)
        assert source.reference_peaks


def test_na22_and_co60_keep_expected_double_peaks() -> None:
    assert builtin_spectrum("Na-22").reference_peaks == (511.0, 1274.537)
    assert builtin_spectrum("Co-60").reference_peaks == (1173.228, 1332.492)


def test_load_256_channel_spectrum(tmp_path: Path) -> None:
    path = tmp_path / "spectrum.csv"
    path.write_text("channel,count\n" + "\n".join(f"{i},{i + 1}" for i in range(256)), encoding="utf-8")
    source = load_spectrum(path)
    assert source.y.size == 256
    assert np.isclose(source.y.sum(), 1.0)
    assert source.sha256


def test_waveform_resamples_to_50_msps(tmp_path: Path) -> None:
    path = tmp_path / "wave.txt"
    path.write_text("time_us value\n0 0\n1 1\n2 0\n", encoding="utf-8")
    source = load_waveform(path)
    assert source.y.size == 101
    assert np.max(source.y) == 1.0
