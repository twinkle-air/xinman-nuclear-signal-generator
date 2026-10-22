from __future__ import annotations

import json
import logging
import struct
import time
import zlib
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol

import numpy as np
import serial
from serial.tools import list_ports

from .models import ChannelConfig, SignalSource
from .protocol import Command, Flags, Frame, FrameParser
from .bench import BenchConfig


ProgressCallback = Callable[[int, str], None]


class SerialLike(Protocol):
    is_open: bool

    def write(self, data: bytes) -> int: ...
    def read(self, size: int = 1) -> bytes: ...
    def close(self) -> None: ...
    def reset_input_buffer(self) -> None: ...
    def reset_output_buffer(self) -> None: ...


class DeviceState(str, Enum):
    DISCONNECTED = "未连接"
    IDLE = "空闲"
    CONFIGURED = "已配置"
    RUNNING = "运行中"
    ERROR = "错误"


@dataclass(slots=True)
class DeviceStatus:
    state: DeviceState = DeviceState.DISCONNECTED
    firmware: str = "SIM-0.1.0"
    fpga: str = "SIM-RTL"
    calibration: str = "SIM-CAL"
    message: str = "等待连接"


class SimulatedDevice:
    """无硬件阶段使用的确定性设备替身，不冒充实机。"""

    def __init__(self, on_status: Callable[[DeviceStatus], None] | None = None) -> None:
        self.status = DeviceStatus()
        self.channels: list[ChannelConfig] = []
        self._on_status = on_status

    def _publish(self) -> None:
        if self._on_status:
            self._on_status(self.status)

    def connect(self) -> None:
        self.status = DeviceStatus(DeviceState.IDLE, message="模拟设备连接正常")
        self._publish()

    def disconnect(self) -> None:
        self.status = DeviceStatus(DeviceState.DISCONNECTED, message="设备已断开")
        self._publish()

    def commit(self, channels: list[ChannelConfig]) -> None:
        if self.status.state == DeviceState.DISCONNECTED:
            raise RuntimeError("请先连接设备")
        for channel in channels:
            channel.validate()
        self.channels = channels
        self.status.state = DeviceState.CONFIGURED
        self.status.message = "参数已原子提交（模拟）"
        self._publish()

    def transfer(
        self,
        channels: list[ChannelConfig],
        source: SignalSource,
        progress: ProgressCallback | None = None,
    ) -> None:
        if progress:
            progress(20, "校验数据")
        self.commit(channels)
        if progress:
            progress(100, "模拟下发完成")

    def start(self) -> None:
        if self.status.state != DeviceState.CONFIGURED:
            raise RuntimeError("请先下发有效参数")
        self.status.state = DeviceState.RUNNING
        self.status.message = "双通道输出运行中（模拟）"
        self._publish()

    def stop(self) -> None:
        if self.status.state != DeviceState.DISCONNECTED:
            self.status.state = DeviceState.IDLE
            self.status.message = "输出已安全停止"
            self._publish()


def available_serial_ports(
    stlink_only: bool = False,
    prefer_stlink: bool = False,
) -> list[tuple[str, str]]:
    ports: list[tuple[str, str, bool]] = []
    for port in list_ports.comports():
        description = getattr(port, "description", None) or "USB串口"
        manufacturer = getattr(port, "manufacturer", None) or ""
        product = getattr(port, "product", None) or ""
        identity = f"{description} {manufacturer} {product}".lower()
        is_stlink = "stlink" in identity or "st-link" in identity or "stmicroelectronics" in identity
        if stlink_only and not is_stlink:
            continue
        ports.append((port.device, description, is_stlink))
    if prefer_stlink:
        ports.sort(key=lambda item: (not item[2], item[0]))
    return [(device, description) for device, description, _is_stlink in ports]


class SerialDevice:
    """USB CDC二进制协议设备。

    MCU必须实现protocol_v1.md约定的ACK、payload和分块数据格式。
    """

    def __init__(
        self,
        port: str,
        on_status: Callable[[DeviceStatus], None] | None = None,
        serial_factory: Callable[..., SerialLike] | None = None,
        timeout_s: float = 0.5,
        baudrate: int = 115200,
        transport_name: str = "USB CDC",
    ) -> None:
        self.port = port
        self.status = DeviceStatus(firmware="未知", fpga="未知", calibration="未知")
        self._on_status = on_status
        self._serial_factory = serial_factory or serial.Serial
        self._serial: SerialLike | None = None
        self._parser = FrameParser()
        self._sequence = 0
        self._timeout_s = timeout_s
        self.baudrate = baudrate
        self.transport_name = transport_name
        self.metadata: dict = {}
        self.is_bench = False
        self.channel_count = 2
        self.last_status: dict = {}
        self._bench_verified: BenchConfig | None = None
        self._bench_generation: int | None = None

    def _publish(self) -> None:
        if self._on_status:
            self._on_status(self.status)

    def connect(self) -> None:
        try:
            try:
                self._serial = self._serial_factory(
                    self.port,
                    baudrate=self.baudrate,
                    timeout=0.05,
                    write_timeout=1.0,
                )
            except Exception as error:
                raise RuntimeError(
                    f"无法打开 {self.port}：{error}。请检查驱动、端口号，并确认串口未被其他软件占用"
                ) from error
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()
            try:
                response = self._transact(
                    Command.HELLO,
                    self._json_bytes(
                        {
                            "client": "nucsignal-studio",
                            "protocol": 1,
                            "transport": self.transport_name,
                            "baudrate": self.baudrate,
                        }
                    ),
                    attempts=10,
                )
            except TimeoutError as error:
                raise RuntimeError(
                    f"已打开 {self.port}，但设备未回应 V1 HELLO 握手。"
                    f"请检查STM32固件是否实现 protocol_v1.md、波特率是否为 {self.baudrate}，"
                    "以及TX/RX/GND接线"
                ) from error
            metadata = self._json_payload(response.payload)
            self.metadata = metadata
            firmware = str(metadata.get("firmware", "未知"))
            advertises_bench = metadata.get("bench") is True or firmware.startswith(("F405-B", "F405-N"))
            if advertises_bench:
                if not (metadata.get("bench") is True and type(metadata.get("channels")) is int
                        and metadata["channels"] == 1 and firmware in ("F405-B2.0.0", "F405-N3.0.0")):
                    raise RuntimeError("台架能力或固件版本不兼容；需要bench=true、channels=1、F405-B2.0.0")
                self.is_bench = True
            elif metadata.get("bench") not in (None, False):
                raise RuntimeError("HELLO中的bench能力字段无效")
            self.channel_count = int(metadata.get("channels", 2))
            if not self.is_bench and self.channel_count != 2:
                raise RuntimeError("当前通用流程仅支持双通道V1；该设备能力未适配，拒绝下发")
            self.status = DeviceStatus(
                state=DeviceState.IDLE,
                firmware=str(metadata.get("firmware", "未知")),
                fpga=str(metadata.get("fpga", "未知")),
                calibration=str(metadata.get("calibration", "未知")),
                message=f"{self.transport_name}已连接：{self.port}",
            )
            self._publish()
        except Exception:
            if self._serial:
                self._serial.close()
            self._serial = None
            raise

    def disconnect(self) -> None:
        if self._serial:
            self._serial.close()
        self._serial = None
        self.status.state = DeviceState.DISCONNECTED
        self.status.message = "硬件已断开"
        self._publish()

    def transfer(
        self,
        channels: list[ChannelConfig],
        source: SignalSource,
        progress: ProgressCallback | None = None,
    ) -> None:
        self._require_connection()
        if self.is_bench:
            raise RuntimeError("当前为单通道台架，禁止波形上传、伏特参数及CH2命令；请使用台架提交")
        if len(channels) > self.channel_count:
            raise RuntimeError(f"硬件只支持{self.channel_count}路，拒绝向不支持的通道下发")
        for channel in channels:
            channel.validate()
        values = np.column_stack((source.x, source.y)).astype("<f4", copy=False).tobytes()
        metadata = {
            "name": source.name,
            "kind": source.kind,
            "points": int(source.x.size),
            "encoding": "float32_le_xy",
            "bytes": len(values),
            "source_sha256": source.sha256,
        }
        self._transact(Command.DATA_BEGIN, self._json_bytes(metadata))
        if progress:
            progress(5, "开始传输信号源")
        chunk_size = 1000
        for offset in range(0, len(values), chunk_size):
            self._transact(Command.DATA_CHUNK, struct.pack("<I", offset) + values[offset : offset + chunk_size])
            if progress:
                progress(5 + int(70 * min(offset + chunk_size, len(values)) / max(len(values), 1)), "传输信号源")
        self._transact(
            Command.DATA_END,
            self._json_bytes({"crc32": zlib.crc32(values) & 0xFFFFFFFF, "bytes": len(values)}),
        )
        for channel_index, channel in enumerate(channels, start=1):
            payload = {"channel": channel_index, **channel.to_dict()}
            self._transact(Command.SET_PARAM, self._json_bytes(payload))
            if progress:
                progress(75 + channel_index * 8, f"写入CH{channel_index}参数")
        self._transact(Command.COMMIT)
        self.status.state = DeviceState.CONFIGURED
        self.status.message = "波形与参数已写入硬件并原子提交"
        self._publish()
        if progress:
            progress(100, "硬件下发完成")

    def start(self) -> None:
        self._require_connection()
        if self.is_bench:
            raise RuntimeError("台架必须使用带状态回读的启动流程")
        if self.status.state != DeviceState.CONFIGURED:
            raise RuntimeError("请先下发波形与参数")
        self._transact(Command.START)
        self.status.state = DeviceState.RUNNING
        self.status.message = "硬件输出运行中"
        self._publish()

    def stop(self) -> None:
        if self.is_bench:
            self.bench_stop()
            return
        if self._serial and self._serial.is_open:
            self._transact(Command.STOP)
            self.status.state = DeviceState.IDLE
            self.status.message = "硬件输出已安全停止"
            self._publish()

    def _require_connection(self) -> None:
        if not self._serial or not self._serial.is_open:
            raise RuntimeError("请先连接硬件串口")

    def _transact(self, command: Command, payload: bytes = b"", *, attempts: int = 3) -> Frame:
        self._require_connection()
        self._sequence = (self._sequence + 1) & 0xFFFF
        request = Frame(1, Flags.ACK_REQ, command, self._sequence, payload)
        for _attempt in range(attempts):
            self._serial.write(request.encode())
            deadline = time.monotonic() + self._timeout_s
            while time.monotonic() < deadline:
                for response in self._parser.feed(self._serial.read(256)):
                    if response.sequence != request.sequence or response.command != request.command or response.version != 1:
                        continue
                    if response.flags & Flags.ERROR:
                        message = response.payload.decode("utf-8", errors="replace") or "设备返回错误"
                        raise RuntimeError(message)
                    if response.flags & Flags.ACK:
                        if _attempt:
                            logging.getLogger(__name__).warning("%s seq=%s recovered on attempt %s", command.name, request.sequence, _attempt + 1)
                        return response
            logging.getLogger(__name__).warning("%s seq=%s timeout attempt=%s/%s buffered=%s", command.name, request.sequence, _attempt + 1, attempts, len(self._parser.buffer))
        raise TimeoutError(f"{command.name} 等待ACK超时（已发送{attempts}次）")

    def read_bench_status(self) -> dict:
        if not self.is_bench:
            raise RuntimeError("当前设备不是已支持的台架固件")
        # Read-only request: retry once using the same sequence (MCU reply cache).
        # Exhaustion still revokes the worker's start permission; never retry START here.
        status = self._json_payload(self._transact(Command.GET_STATUS, attempts=2).payload)
        states = {"IDLE": DeviceState.IDLE, "CONFIG": DeviceState.CONFIGURED,
                  "RUN": DeviceState.RUNNING, "ERROR": DeviceState.ERROR}
        if status.get("state") not in states or type(status.get("fpga")) is not bool:
            raise ValueError("设备状态回读不完整或状态未知")
        if type(status.get("generation")) is not int or status["generation"] < 0:
            raise ValueError("设备未返回有效generation")
        nuclear = self.status.firmware == "F405-N3.0.0"
        if nuclear and (type(status.get("random_events")) is not int or status["random_events"] not in (0, 1)
                        or type(status.get("spectrum_enabled")) is not int or status["spectrum_enabled"] not in (0, 1)
                        or type(status.get("spectrum_crc32")) is not int or not 0 <= status["spectrum_crc32"] <= 0xffffffff):
            raise ValueError("N3扩展状态回读无效")
        BenchConfig(status.get("dac_baseline_code"), status.get("dac_amplitude_code"),
                    status.get("period_us"), status.get("decay_us", float("nan")),
                    nuclear=nuclear, random_events=bool(status.get("random_events")) if nuclear else False,
                    noise_peak_codes=status.get("noise_peak_codes",0) if nuclear else 0,
                    seed=status.get("seed",1) if nuclear else 1).validate()
        if not isinstance(status.get("error"), str):
            raise ValueError("设备未返回错误状态")
        self.last_status = status
        self.status.state = states[status["state"]]
        if not status["fpga"] or status["error"] != "OK":
            self.status.state = DeviceState.ERROR
        if (self._bench_verified is not None and
                (not self._bench_verified.matches(status) or status["generation"] != self._bench_generation)):
            self._bench_verified = None
        if self.status.state in (DeviceState.IDLE, DeviceState.ERROR):
            self._bench_verified = None
        self.status.message = f"台架 {status['state']} / {status['error']} · FPGA {'在线' if status['fpga'] else '离线'}"
        return dict(status)

    def bench_recover(self) -> dict:
        if not self.is_bench:
            raise RuntimeError("禁止向非台架设备发送RECOVER")
        self._bench_verified = None
        response = self._json_payload(self._transact(Command.RECOVER).payload)
        if response.get("recovered") is not True:
            raise RuntimeError("RECOVER未确认恢复成功")
        status = self.read_bench_status()
        if self.status.state != DeviceState.IDLE:
            raise RuntimeError("RECOVER后未回到IDLE/OK，禁止提交或启动")
        return status

    def bench_submit(self, config: BenchConfig) -> dict:
        config.validate()
        if config.nuclear != (self.status.firmware == "F405-N3.0.0"):
            raise RuntimeError("参数模式与台架固件不匹配；N3功能不可发送给B2")
        previous = self.bench_recover()
        if config.spectrum_table:
            table = config.spectrum_table
            begin = self._json_payload(self._transact(Command.DATA_BEGIN, self._json_bytes({"bytes": 256, "name": "quantile-256"})).payload)
            if begin.get("offset") != 0:
                raise RuntimeError("能谱上传起点未确认")
            for offset in range(0, 256, 32):
                reply = self._json_payload(self._transact(Command.DATA_CHUNK, struct.pack("<I", offset)+table[offset:offset+32]).payload)
                if reply.get("offset") != offset+32:
                    raise RuntimeError("能谱上传偏移回读不符")
            end = self._json_payload(self._transact(Command.DATA_END, self._json_bytes({"bytes": 256, "crc32": zlib.crc32(table)})).payload)
            if end.get("verified") is not True:
                raise RuntimeError("能谱上传校验未确认")
        accepted = self._json_payload(self._transact(Command.SET_PARAM, self._json_bytes(config.payload())).payload)
        if accepted.get("accepted") is not True:
            raise RuntimeError("SET未确认接收参数")
        committed = self._json_payload(self._transact(Command.COMMIT).payload)
        if committed.get("committed") is not True:
            raise RuntimeError("COMMIT未确认提交")
        status = self.read_bench_status()
        if (self.status.state != DeviceState.CONFIGURED or not config.matches(status)
                or status["generation"] != previous["generation"] + 1):
            raise RuntimeError("提交回读不符：状态、generation或活动参数与下发不一致")
        self._bench_verified = config
        self._bench_generation = status["generation"]
        return status

    def bench_start(self) -> dict:
        self.read_bench_status()
        if self._bench_verified is None or self.status.state != DeviceState.CONFIGURED:
            raise RuntimeError("请先重新提交台架参数并确认回读，STOP后不能直接START")
        response = self._json_payload(self._transact(Command.START).payload)
        if response.get("running") is not True:
            raise RuntimeError("START未确认启动")
        status = self.read_bench_status()
        if self.status.state != DeviceState.RUNNING:
            raise RuntimeError("START后未回读到RUN/OK")
        return status

    def bench_stop(self) -> dict:
        self._bench_verified = None
        response = self._json_payload(self._transact(Command.STOP).payload)
        if response.get("running") is not False:
            raise RuntimeError("STOP未确认停止")
        status = self.read_bench_status()
        if self.status.state != DeviceState.IDLE:
            raise RuntimeError("停止未确认：设备未回读到IDLE/OK")
        return status

    @staticmethod
    def _json_bytes(value: dict) -> bytes:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def _json_payload(payload: bytes) -> dict:
        if not payload:
            return {}
        try:
            value = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("设备返回的JSON payload无效") from error
        return value if isinstance(value, dict) else {}
