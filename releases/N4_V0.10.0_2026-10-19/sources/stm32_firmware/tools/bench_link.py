"""Single-channel bench controller. Requires pyserial; never flashes hardware."""
import argparse
import json
import struct
import time
import zlib


def encode(command, sequence, payload):
    body = struct.pack('<BBHHI', 1, 1, command, sequence, len(payload)) + payload
    return b'\xa5\x5a' + body + struct.pack('<I', zlib.crc32(body))


class Link:
    def __init__(self, port):
        import serial
        self.serial = serial.Serial(port, 115200, timeout=0.1, write_timeout=1)
        self.sequence = 0
        self.buffer = bytearray()

    def request(self, command, payload=None):
        self.sequence = (self.sequence + 1) & 65535
        encoded = json.dumps(payload or {}, separators=(',', ':')).encode()
        self.serial.write(encode(command, self.sequence, encoded))
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            self.buffer.extend(self.serial.read(256))
            while len(self.buffer) >= 16:
                start = self.buffer.find(b'\xa5\x5a')
                if start < 0:
                    self.buffer[:] = self.buffer[-1:]
                    break
                if start:
                    del self.buffer[:start]
                if len(self.buffer) < 16:
                    break
                version, flags, cmd, seq, length = struct.unpack_from('<BBHHI', self.buffer, 2)
                if length > 1024:
                    del self.buffer[:2]
                    continue
                if len(self.buffer) < 16 + length:
                    break
                frame = bytes(self.buffer[:16 + length])
                del self.buffer[:16 + length]
                if zlib.crc32(frame[2:-4]) != struct.unpack('<I', frame[-4:])[0]:
                    raise RuntimeError('Reply CRC mismatch')
                if version != 1 or cmd != command or seq != self.sequence or not flags & 2:
                    continue
                text = frame[12:-4].decode()
                if flags & 4:
                    raise RuntimeError(text)
                return json.loads(text)
        raise TimeoutError(f'No reply to command 0x{command:04x}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--baseline-code', type=int, default=16)
    parser.add_argument('--amp-code', type=int, default=224)
    parser.add_argument('--period-us', type=int, default=1000)
    parser.add_argument('--tau-us', type=float, default=12)
    parser.add_argument('--seconds', type=float, default=10)
    parser.add_argument('--probe-only', action='store_true')
    args = parser.parse_args()
    if not (0 <= args.baseline_code <= 255 and 0 <= args.amp_code <= 255 - args.baseline_code
            and 1 <= args.tau_us <= 100 and 128 <= args.period_us <= 10000
            and args.period_us >= 5 * args.tau_us and 0 < args.seconds <= 3600):
        parser.error('Invalid code range, period, tau or duration')
    link = Link(args.port)
    can_stop = False
    try:
        hello = link.request(1)
        print('HELLO:', hello)
        if hello.get('firmware') != 'F405-B2.0.0' or not hello.get('bench') or hello.get('channels') != 1:
            raise RuntimeError('This controller requires F405-B2.0.0 bench firmware')
        can_stop = True
        print('RECOVER:', link.request(0x70))
        print('STATUS:', link.request(2))
        if args.probe_only:
            return
        print('SET:', link.request(0x10, {'channel': 1, 'enabled': True,
              'dac_baseline_code': args.baseline_code, 'dac_amplitude_code': args.amp_code,
              'mean_interval_us': args.period_us, 'decay_us': args.tau_us}))
        print('COMMIT:', link.request(0x11))
        print('START:', link.request(0x30))
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            status = link.request(2)
            print('STATUS:', status)
            if status.get('state') != 'RUN' or not status.get('fpga'):
                raise RuntimeError('Device left RUN or FPGA link failed')
            time.sleep(0.25)
    finally:
        if can_stop:
            try:
                print('STOP:', link.request(0x31))
            except Exception as exc:
                print('STOP could not be confirmed:', exc)
        link.serial.close()


if __name__ == '__main__':
    main()
