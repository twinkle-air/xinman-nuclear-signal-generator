from __future__ import annotations

import queue
import threading

from PySide6.QtCore import QThread, Signal

from ..device import SerialDevice


class BenchWorker(QThread):
    """连接握手后唯一串口所有者：操作与200ms状态轮询串行执行。"""
    updated = Signal(object)
    completed = Signal(str)
    failed = Signal(str, str)
    closed = Signal(str)

    def __init__(self, device: SerialDevice, parent=None) -> None:
        super().__init__(parent)
        self.device = device
        self._requests: queue.PriorityQueue = queue.PriorityQueue()
        self._counter = 0
        self._shutdown = threading.Event()

    def request(self, name: str, config=None) -> None:
        self._counter += 1
        self._requests.put((0 if name == "stop" else 1, self._counter, name, config))

    def shutdown(self) -> None:
        self._shutdown.set()

    def run(self) -> None:
        try:
            while not self._shutdown.is_set():
                try:
                    _priority, _counter, name, config = self._requests.get(timeout=0.2)
                except queue.Empty:
                    name, config = "poll", None
                try:
                    if name == "recover":
                        status = self.device.bench_recover()
                    elif name == "submit":
                        status = self.device.bench_submit(config)
                    elif name == "start":
                        status = self.device.bench_start()
                    elif name == "stop":
                        status = self.device.bench_stop()
                    else:
                        status = self.device.read_bench_status()
                    status["verified"] = self.device._bench_verified is not None
                    self.updated.emit(status)
                    if name != "poll":
                        self.completed.emit(name)
                except Exception as error:
                    self.device._bench_verified = None
                    self.failed.emit(name, str(error))
        finally:
            message = "已确认停止并断开台架"
            try:
                self.device.bench_stop()
            except Exception as error:
                message = f"已断开，但停止未确认：{error}"
            finally:
                self.device.disconnect()
                self.closed.emit(message)
