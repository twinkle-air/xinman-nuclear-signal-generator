import pytest

from nucsignal_app.protocol import Command, Flags, Frame, FrameParser


def test_frame_round_trip() -> None:
    frame = Frame(1, Flags.ACK_REQ, Command.SET_PARAM, 42, b"payload")
    assert Frame.decode(frame.encode()) == frame


def test_frame_crc_rejects_corruption() -> None:
    data = bytearray(Frame(1, Flags.NONE, Command.HELLO, 1).encode())
    data[-1] ^= 0x80
    with pytest.raises(ValueError, match="CRC32"):
        Frame.decode(bytes(data))


def test_parser_handles_fragmentation_and_sticky_packets() -> None:
    first = Frame(1, Flags.NONE, Command.HELLO, 1).encode()
    second = Frame(1, Flags.ACK_REQ, Command.GET_STATUS, 2, b"x").encode()
    parser = FrameParser()
    assert parser.feed(b"noise" + first[:5]) == []
    frames = parser.feed(first[5:] + second)
    assert [frame.sequence for frame in frames] == [1, 2]

