from dataclasses import replace
import zlib

import numpy as np
import pytest

from nucsignal_app.bench import BenchConfig
from nucsignal_app.models import SignalSource
from nucsignal_app.nuclear import reference, spectrum_quantiles
from nucsignal_app.protocol import Command, Flags, Frame
from test_bench import BenchSerial, connected


class NuclearSerial(BenchSerial):
    def __init__(self):
        super().__init__()
        self.hello["firmware"] = "F405-N3.0.0"
        self.hello["fpga"] = "FPGA-3.0.0"
        self.table = bytearray()
        self.ext = {"random_events": 0, "noise_peak_codes": 0, "spectrum_enabled": 0, "seed": 1}
        self.upload_verified = False

    def write(self, data):
        req = Frame.decode(data)
        if req.command in (Command.DATA_BEGIN, Command.DATA_CHUNK, Command.DATA_END):
            self.received.append(req)
            import json
            if req.command == Command.DATA_BEGIN:
                self.table.clear()
                reply = {"offset": 0}
            elif req.command == Command.DATA_CHUNK:
                assert int.from_bytes(req.payload[:4], "little") == len(self.table)
                self.table.extend(req.payload[4:])
                reply = {"offset": len(self.table)}
            else:
                value = json.loads(req.payload)
                assert len(self.table) == value["bytes"] == 256
                assert zlib.crc32(self.table) == value["crc32"]
                self.upload_verified = True
                reply = {"verified": True}
            self._rx.extend(Frame(1, Flags.ACK, req.command, req.sequence, json.dumps(reply).encode()).encode())
            return len(data)
        if req.command == Command.SET_PARAM:
            import json
            value = json.loads(req.payload)
            self.ext = {k: value[k] for k in self.ext}
        result = super().write(data)
        if req.command == Command.GET_STATUS:
            import json
            frame = Frame.decode(bytes(self._rx))
            status = json.loads(frame.payload)
            status.update(self.ext, spectrum_crc32=zlib.crc32(self.table))
            self._rx[:] = Frame(1, Flags.ACK, req.command, req.sequence, json.dumps(status).encode()).encode()
        return result


def test_nuclear_upload_commit_readback_and_b2_refusal():
    config = BenchConfig(96, 84, 1000, 24, nuclear=True, random_events=True,
                         noise_peak_codes=4, spectrum_table=bytes(range(256)))
    device, serial = connected(NuclearSerial())
    device.bench_submit(config)
    assert serial.upload_verified and bytes(serial.table) == config.spectrum_table
    device.bench_start()
    device.bench_stop()
    old, transport = connected()
    before = len(transport.received)
    with pytest.raises(RuntimeError, match="不匹配"):
        old.bench_submit(config)
    assert len(transport.received) == before


def test_quantile_two_lines_and_invalid_spectrum():
    source = SignalSource("two-lines", "spectrum", np.array([0., 1., 2.]), np.array([0., 1., 3.]), full_scale_x=2.)
    table = np.frombuffer(spectrum_quantiles(source), dtype=np.uint8)
    assert np.sum(table == 128) == 64
    assert np.sum(table == 255) == 192
    source.y[0] = -1
    with pytest.raises(ValueError):
        spectrum_quantiles(source)


def test_reference_random_rate_intervals_noise_and_reproducibility():
    config = BenchConfig(96, 84, 1000, 24, nuclear=True, random_events=True, noise_peak_codes=4)
    codes, events, amplitudes, clips = reference(config, 1_000_000)
    gaps = np.diff(events)
    assert 850 < len(events) < 1150
    assert 0.85 < gaps.std()/gaps.mean() < 1.15
    assert np.array_equal(codes[:20000], reference(config, 20000)[0])
    assert set(amplitudes) == {84}
    quiet = reference(replace(config, amplitude_code=0), 100_000)[0].astype(int)-96
    assert quiet.min() == -4 and quiet.max() == 4
    assert abs(quiet.mean()) < 0.1
    assert 2.4 < quiet.std() < 2.8
    assert not np.array_equal(codes[:20000], reference(replace(config, seed=2), 20000)[0])


def test_nuclear_bounds_and_clipping():
    for config in [BenchConfig(nuclear=True, seed=0), BenchConfig(nuclear=True, noise_peak_codes=33),
                   BenchConfig(0, 100, nuclear=True, noise_peak_codes=1),
                   BenchConfig(nuclear=True, spectrum_table=b"bad")]:
        with pytest.raises(ValueError):
            config.validate()
    # Random mode permits overlap; the counter exposes saturating pileup.
    config = BenchConfig(96, 150, 128, 100, nuclear=True, random_events=True)
    assert reference(config, 100_000)[3] > 0


def test_nuclear_ui_uploads_selected_spectrum_and_preserves_single_channel():
    import time
    from PySide6.QtWidgets import QApplication
    from nucsignal_app.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    device, serial = connected(NuclearSerial())
    window.device = device
    window._connection_succeeded()

    def wait_for(predicate):
        end = time.monotonic()+4
        while time.monotonic()<end:
            app.processEvents()
            if predicate():
                return
            time.sleep(0.01)
        raise AssertionError("N3 UI operation timed out")

    try:
        wait_for(lambda: not window._bench_busy)
        assert window.bench_panel.nuclear
        assert not window.bench_tabs.isTabEnabled(1)
        assert window.source_controls[0].isEnabled()
        assert window.source_controls[1].isEnabled()
        assert not window.source_controls[2].isEnabled()
        window.bench_panel.baseline.setValue(96)
        window.bench_panel.amplitude.setValue(84)
        window.bench_panel.random.setChecked(True)
        window.bench_panel.noise.setValue(4)
        window.bench_panel.spectrum.setChecked(True)
        window.apply_config()
        wait_for(lambda: not window._bench_busy)
        assert serial.upload_verified
        assert len(serial.table) == 256
        assert window.start_button.isEnabled()
        window.start_output()
        wait_for(lambda: not window._bench_busy)
        assert serial.state == "RUN"
        window.stop_output()
        wait_for(lambda: not window._bench_busy)
        assert serial.state == "IDLE"
        assert not window.start_button.isEnabled()
    finally:
        window._shutdown_bench()
        wait_for(lambda: window._bench_worker is None)
        window.close()
