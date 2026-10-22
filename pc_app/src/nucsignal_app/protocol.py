from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from enum import IntEnum, IntFlag


SOF = b"\xA5\x5A"
HEADER = struct.Struct("<BBHHI")
CRC = struct.Struct("<I")
MAX_PAYLOAD = 1024


class Flags(IntFlag):
    NONE = 0
    ACK_REQ = 1
    ACK = 2
    ERROR = 4


class Command(IntEnum):
    HELLO = 0x0001
    GET_STATUS = 0x0002
    SET_PARAM = 0x0010
    COMMIT = 0x0011
    DATA_BEGIN = 0x0020
    DATA_CHUNK = 0x0021
    DATA_END = 0x0022
    START = 0x0030
    STOP = 0x0031
    SELECT_PRESET = 0x0040
    READ_HIST = 0x0050
    SAVE_PROFILE = 0x0060
    LOAD_PROFILE = 0x0061
    RECOVER = 0x0070


@dataclass(frozen=True, slots=True)
class Frame:
    version: int
    flags: Flags
    command: int
    sequence: int
    payload: bytes = b""

    def encode(self) -> bytes:
        if not 0 <= self.version <= 255:
            raise ValueError("协议版本必须在0–255范围内")
        if len(self.payload) > MAX_PAYLOAD:
            raise ValueError(f"单帧负载不能超过 {MAX_PAYLOAD} 字节")
        body = HEADER.pack(self.version, int(self.flags), int(self.command), self.sequence, len(self.payload)) + self.payload
        return SOF + body + CRC.pack(zlib.crc32(body) & 0xFFFFFFFF)

    @classmethod
    def decode(cls, data: bytes) -> "Frame":
        minimum = len(SOF) + HEADER.size + CRC.size
        if len(data) < minimum or data[:2] != SOF:
            raise ValueError("帧头无效或数据不完整")
        version, flags, command, sequence, length = HEADER.unpack_from(data, 2)
        expected = minimum + length
        if length > MAX_PAYLOAD or len(data) != expected:
            raise ValueError("负载长度不匹配")
        body = data[2:-CRC.size]
        expected_crc = CRC.unpack_from(data, len(data) - CRC.size)[0]
        if zlib.crc32(body) & 0xFFFFFFFF != expected_crc:
            raise ValueError("CRC32校验失败")
        return cls(version, Flags(flags), command, sequence, data[2 + HEADER.size : -CRC.size])


class FrameParser:
    """处理USB CDC可能发生的分片、粘包和SOF前垃圾字节。"""

    def __init__(self) -> None:
        self.buffer = bytearray()

    def feed(self, data: bytes) -> list[Frame]:
        self.buffer.extend(data)
        frames: list[Frame] = []
        minimum = len(SOF) + HEADER.size + CRC.size
        while len(self.buffer) >= minimum:
            start = self.buffer.find(SOF)
            if start < 0:
                del self.buffer[:-1]
                break
            if start:
                del self.buffer[:start]
            if len(self.buffer) < minimum:
                break
            length = HEADER.unpack_from(self.buffer, 2)[4]
            if length > MAX_PAYLOAD:
                del self.buffer[:2]
                continue
            frame_length = minimum + length
            if len(self.buffer) < frame_length:
                break
            packet = bytes(self.buffer[:frame_length])
            del self.buffer[:frame_length]
            frames.append(Frame.decode(packet))
        return frames

