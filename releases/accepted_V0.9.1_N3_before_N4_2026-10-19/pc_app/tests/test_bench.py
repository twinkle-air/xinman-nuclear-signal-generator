import json
import threading
import time

import pytest
from PySide6.QtCore import Qt

from nucsignal_app.bench import BenchConfig
from nucsignal_app.device import DeviceState, SerialDevice
from nucsignal_app.importers import builtin_spectrum
from nucsignal_app.models import ChannelConfig
from nucsignal_app.protocol import Command, Flags, Frame
from nucsignal_app.ui.bench_worker import BenchWorker
from test_device import FakeSerial


class BenchSerial(FakeSerial):
    def __init__(self):
        super().__init__()
        self.hello = {"firmware": "F405-B2.0.0", "bench": True, "channels": 1,
                      "fpga": "FPGA-2.0.0", "calibration": "UNCALIBRATED-CODES"}
        self.state = "IDLE"
        self.config = BenchConfig()
        self.generation = 0
        self.online = True
        self.corrupt_readback = False
        self.owners = []
        self.drop_status = False

    def write(self, data):
        request = Frame.decode(data)
        self.received.append(request)
        self.owners.append(threading.get_ident())
        command = request.command
        error = False
        if command == Command.HELLO:
            reply = self.hello
        elif command == Command.RECOVER:
            self.state = "IDLE"
            reply = {"recovered": True}
        elif command == Command.GET_STATUS:
            if self.drop_status:
                return len(data)
            reply = {"state": self.state, "error": "OK", "fpga": self.online,
                     "generation": self.generation, "safety_bypass": True,
                     "board_a": None, "board_b": None, "power_good": None,
                     "dac_baseline_code": self.config.baseline_code,
                     "dac_amplitude_code": self.config.amplitude_code,
                     "period_us": self.config.period_us,
                     "decay_us": self.config.tau_us + (1 if self.corrupt_readback else 0)}
        elif command == Command.SET_PARAM:
            payload = json.loads(request.payload)
            assert payload["channel"] == 1
            assert "amplitude_v" not in payload and "baseline_v" not in payload
            self.config = BenchConfig(payload["dac_baseline_code"], payload["dac_amplitude_code"],
                                      payload["mean_interval_us"], payload["decay_us"])
            reply = {"accepted": True}
        elif command == Command.COMMIT:
            self.generation += 1
            self.state = "CONFIG"
            reply = {"committed": True}
        elif command == Command.START:
            self.state = "RUN"
            reply = {"running": True}
        elif command == Command.STOP:
            self.state = "IDLE"
            reply = {"running": False}
        else:
            error = True
            reply = "unsupported"
        payload = reply.encode() if isinstance(reply, str) else json.dumps(reply).encode()
        self._rx.extend(Frame(1, Flags.ACK | (Flags.ERROR if error else Flags.NONE), command,
                              request.sequence, payload).encode())
        return len(data)


def connected(transport=None):
    transport = transport or BenchSerial()
    device = SerialDevice("COM_TEST", serial_factory=lambda *a, **kw: transport, timeout_s=0.01)
    device.connect()
    return device, transport


@pytest.mark.parametrize("config", [BenchConfig(128, 128), BenchConfig(period_us=127),
                                     BenchConfig(period_us=128, tau_us=30), BenchConfig(tau_us=101)])
def test_invalid_bench_config_never_sends_a_command(config):
    device, transport = connected()
    before = len(transport.received)
    with pytest.raises(ValueError):
        device.bench_submit(config)
    assert len(transport.received) == before


def test_bench_contract_submit_start_stop_and_resubmit():
    device, transport = connected()
    device.bench_submit(BenchConfig())
    assert [r.command for r in transport.received] == [Command.HELLO, Command.RECOVER,
        Command.GET_STATUS, Command.SET_PARAM, Command.COMMIT, Command.GET_STATUS]
    device.bench_start()
    assert device.status.state == DeviceState.RUNNING
    device.bench_stop()
    assert device.status.state == DeviceState.IDLE
    with pytest.raises(RuntimeError, match="重新提交"):
        device.bench_start()
    device.bench_submit(BenchConfig(tau_us=24))
    device.bench_start()
    with pytest.raises(RuntimeError, match="禁止波形上传"):
        device.transfer([ChannelConfig(), ChannelConfig()], builtin_spectrum("Cs-137"))
    assert not any(r.command in (Command.DATA_BEGIN, Command.DATA_CHUNK, Command.DATA_END)
                   for r in transport.received)


@pytest.mark.parametrize("change", [{"channels": 2}, {"bench": False}, {"firmware": "F405-B3.0.0"}])
def test_unknown_bench_capabilities_rejected_before_writes(change):
    transport = BenchSerial()
    transport.hello.update(change)
    with pytest.raises(RuntimeError, match="不兼容"):
        connected(transport)
    assert [r.command for r in transport.received] == [Command.HELLO]
    assert not transport.is_open


def test_corrupt_readback_blocks_start_and_offline_invalidates_state():
    device, transport = connected()
    transport.corrupt_readback = True
    with pytest.raises(RuntimeError, match="回读不符"):
        device.bench_submit(BenchConfig())
    assert device._bench_verified is None
    transport.corrupt_readback = False
    device.bench_submit(BenchConfig())
    transport.online = False
    device.read_bench_status()
    assert device.status.state == DeviceState.ERROR
    assert device._bench_verified is None


def test_worker_serializes_commands_polls_and_stops_on_shutdown():
    device, transport = connected()
    transport.owners.clear()
    worker = BenchWorker(device)
    failures = []
    worker.failed.connect(lambda name, message: failures.append((name, message)), Qt.ConnectionType.DirectConnection)
    worker.request("submit", BenchConfig())
    worker.request("start")
    worker.start()
    try:
        time.sleep(0.75)
        assert worker.isRunning()
        assert len([r for r in transport.received if r.command == Command.GET_STATUS]) >= 5
        assert transport.state == "RUN"
        # 模拟外部停止，下一次轮询应取消已验证配置。
        transport.state = "IDLE"
        time.sleep(0.3)
        assert device._bench_verified is None
        assert device.status.state == DeviceState.IDLE
        worker.request("submit", BenchConfig())
        worker.request("start")
        time.sleep(0.3)
        assert transport.state == "RUN"
    finally:
        worker.shutdown()
        assert worker.wait(3000)
    assert not failures
    assert len(set(transport.owners)) == 1
    assert transport.received[-2].command == Command.STOP
    assert not transport.is_open


def test_poll_timeout_marks_failure_and_shutdown_reports_unconfirmed_stop():
    device, transport = connected()
    device.bench_submit(BenchConfig())
    device.bench_start()
    transport.drop_status = True
    worker = BenchWorker(device)
    failures, closed = [], []
    worker.failed.connect(lambda name, message: failures.append((name, message)), Qt.ConnectionType.DirectConnection)
    worker.closed.connect(closed.append, Qt.ConnectionType.DirectConnection)
    worker.start()
    try:
        time.sleep(0.5)
        assert failures and failures[0][0] == "poll"
        assert device._bench_verified is None
    finally:
        worker.shutdown()
        assert worker.wait(3000)
    assert closed and "停止未确认" in closed[0]
    assert not transport.is_open


def test_bench_model_is_in_codes_and_decays_to_baseline():
    time_us, codes = BenchConfig().preview()
    assert time_us[1] - time_us[0] == 1
    assert codes[0] == 240
    assert codes[500] == 16
    assert codes[1000] == 240
