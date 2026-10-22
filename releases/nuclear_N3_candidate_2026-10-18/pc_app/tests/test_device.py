import pytest

from nucsignal_app.device import DeviceState, SerialDevice, SimulatedDevice, available_serial_ports
from nucsignal_app.importers import builtin_spectrum
from nucsignal_app.models import ChannelConfig
from nucsignal_app.protocol import Command, Flags, Frame


def test_device_state_machine() -> None:
    device = SimulatedDevice()
    with pytest.raises(RuntimeError):
        device.start()
    device.connect()
    assert device.status.state == DeviceState.IDLE
    device.commit([ChannelConfig(), ChannelConfig(seed=2)])
    device.start()
    assert device.status.state == DeviceState.RUNNING
    device.stop()
    assert device.status.state == DeviceState.IDLE


class FakeSerial:
    def __init__(self) -> None:
        self.is_open = True
        self.received: list[Frame] = []
        self._rx = bytearray()

    def write(self, data: bytes) -> int:
        request = Frame.decode(data)
        self.received.append(request)
        payload = b'{"firmware":"TEST-FW","fpga":"TEST-RTL","calibration":"TEST-CAL"}' if request.command == Command.HELLO else b""
        response = Frame(1, Flags.ACK, request.command, request.sequence, payload)
        self._rx.extend(response.encode())
        return len(data)

    def read(self, size: int = 1) -> bytes:
        data = bytes(self._rx[:size])
        del self._rx[:size]
        return data

    def close(self) -> None:
        self.is_open = False

    def reset_input_buffer(self) -> None:
        self._rx.clear()

    def reset_output_buffer(self) -> None:
        pass


def test_serial_device_handshake_transfer_and_control() -> None:
    transport = FakeSerial()
    device = SerialDevice("COM_TEST", serial_factory=lambda *args, **kwargs: transport, timeout_s=0.01)
    device.connect()
    assert device.status.state == DeviceState.IDLE
    assert device.status.firmware == "TEST-FW"
    progress: list[int] = []
    device.transfer(
        [ChannelConfig(), ChannelConfig(seed=2)],
        builtin_spectrum("Cs-137"),
        lambda value, _message: progress.append(value),
    )
    commands = [frame.command for frame in transport.received]
    assert Command.DATA_BEGIN in commands
    assert Command.DATA_CHUNK in commands
    assert commands.count(Command.SET_PARAM) == 2
    assert progress[-1] == 100
    device.start()
    device.stop()
    assert device.status.state == DeviceState.IDLE


def test_stlink_vcp_uses_selected_uart_baudrate() -> None:
    transport = FakeSerial()
    captured: dict = {}

    def factory(*args, **kwargs):
        captured.update(kwargs)
        return transport

    device = SerialDevice(
        "COM_STLINK",
        serial_factory=factory,
        timeout_s=0.01,
        baudrate=921600,
        transport_name="ST-Link VCP",
    )
    device.connect()
    assert captured["baudrate"] == 921600
    hello = next(frame for frame in transport.received if frame.command == Command.HELLO)
    assert b"ST-Link VCP" in hello.payload
    device.disconnect()


def test_stlink_port_filter(monkeypatch) -> None:
    class Port:
        def __init__(self, device, description, manufacturer="", product=""):
            self.device = device
            self.description = description
            self.manufacturer = manufacturer
            self.product = product

    monkeypatch.setattr(
        "nucsignal_app.device.list_ports.comports",
        lambda: [
            Port("COM3", "USB Serial Device"),
            Port("COM8", "STMicroelectronics STLink Virtual COM Port", "STMicroelectronics"),
        ],
    )
    assert available_serial_ports(stlink_only=True) == [
        ("COM8", "STMicroelectronics STLink Virtual COM Port")
    ]
    assert available_serial_ports(prefer_stlink=True) == [
        ("COM8", "STMicroelectronics STLink Virtual COM Port"),
        ("COM3", "USB Serial Device"),
    ]


class SilentSerial(FakeSerial):
    def write(self, data: bytes) -> int:
        self.received.append(Frame.decode(data))
        return len(data)


class BootingSerial(FakeSerial):
    def write(self, data: bytes) -> int:
        if len(self.received) < 4:
            self.received.append(Frame.decode(data))
            return len(data)
        return super().write(data)


def test_handshake_retries_during_device_boot() -> None:
    transport = BootingSerial()
    device = SerialDevice("COM_TEST", serial_factory=lambda *args, **kwargs: transport, timeout_s=0.001)
    device.connect()
    assert len(transport.received) == 5
    assert device.status.firmware == "TEST-FW"


def test_handshake_timeout_distinguishes_open_port_from_missing_port() -> None:
    transport = SilentSerial()
    device = SerialDevice("COM7", serial_factory=lambda *args, **kwargs: transport, timeout_s=0.001)
    with pytest.raises(RuntimeError, match="已打开 COM7.*V1 HELLO"):
        device.connect()
    assert not transport.is_open
