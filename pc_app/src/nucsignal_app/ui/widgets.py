from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


def envelope_indices(values: np.ndarray, columns: int) -> np.ndarray:
    """Keep both extrema in each screen bucket, in time order, plus endpoints."""
    count = len(values)
    width = max(1, int(np.ceil(count / max(1, columns))))
    if width == 1:
        return np.arange(count)
    complete = count // width
    blocks = values[:complete * width].reshape(complete, width)
    offsets = np.arange(complete) * width
    indices = np.concatenate(([0], offsets + blocks.argmin(axis=1),
                              offsets + blocks.argmax(axis=1),
                              np.arange(complete * width, count), [count - 1]))
    return np.unique(indices)


class WaveformPlot(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(310)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._time = np.array([0.0, 1.0])
        self._signals: list[tuple[np.ndarray, QColor, str]] = []
        self._view_t = (0.0, 1.0)
        self._view_v = (0.0, 5.0)
        self._drag_position: QPointF | None = None
        self.unit = "V"
        self.full_scale = 5.0
        self.setMouseTracking(True)
        self.setToolTip("滚轮缩放；按住左键拖动；双击恢复完整视图")

    def set_data(self, time_us: np.ndarray, signals: list[tuple[np.ndarray, QColor, str]]) -> None:
        self._time = time_us
        self._signals = signals
        self.reset_view()

    def reset_view(self) -> None:
        if self._time.size >= 2:
            self._view_t = (float(self._time[0]), float(self._time[-1]))
        self._view_v = self._auto_voltage_range()
        self.update()

    def _auto_voltage_range(self) -> tuple[float, float]:
        limits = []
        for values, _color, _label in self._signals:
            finite = values[np.isfinite(values)]
            if finite.size:
                limits.append((float(finite.min()), float(finite.max())))
        if not limits:
            return (0.0, self.full_scale)
        low = min(item[0] for item in limits)
        high = max(item[1] for item in limits)
        span = max(high - low, 0.2)
        center = (low + high) / 2
        # 对称留白使波形居中；负刻度仅为视图边距，不改变输出数据。
        return center - span * 0.65, center + span * 0.65

    def show_full_scale(self) -> None:
        self.reset_view()
        self._view_v = (0.0, self.full_scale)
        self.update()

    def _voltage_bounds(self) -> tuple[float, float]:
        auto_low, auto_high = self._auto_voltage_range()
        return min(0.0, auto_low), max(self.full_scale, auto_high)

    def view_range(self) -> tuple[float, float, float, float]:
        return (*self._view_t, *self._view_v)

    def _plot_area(self) -> QRectF:
        return QRectF(54, 18, max(10, self.width() - 74), max(10, self.height() - 58))

    def wheelEvent(self, event) -> None:  # noqa: N802
        area = self._plot_area()
        position = event.position()
        if not area.contains(position):
            return super().wheelEvent(event)
        factor = 0.8 if event.angleDelta().y() > 0 else 1.25
        t_ratio = (position.x() - area.left()) / area.width()
        v_ratio_from_bottom = 1.0 - (position.y() - area.top()) / area.height()
        self.zoom_at(factor, t_ratio, v_ratio_from_bottom)
        event.accept()

    def zoom_at(self, factor: float, t_ratio: float = 0.5, v_ratio: float = 0.5) -> None:
        """围绕视图中的相对位置缩放，供鼠标交互和自动测试共同使用。"""
        if self._time.size < 2 or factor <= 0:
            return
        t_min, t_max = self._view_t
        v_min, v_max = self._view_v
        t_ratio = min(1.0, max(0.0, t_ratio))
        v_ratio = min(1.0, max(0.0, v_ratio))
        t_anchor = t_min + t_ratio * (t_max - t_min)
        v_anchor = v_min + v_ratio * (v_max - v_min)
        new_t_span = max(0.2, min(float(self._time[-1] - self._time[0]), (t_max - t_min) * factor))
        v_low, v_high = self._voltage_bounds()
        new_v_span = max(0.05, min(v_high - v_low, (v_max - v_min) * factor))
        new_t_min = t_anchor - t_ratio * new_t_span
        new_v_min = v_anchor - v_ratio * new_v_span
        self._view_t = self._bounded_range(new_t_min, new_t_span, float(self._time[0]), float(self._time[-1]))
        self._view_v = self._bounded_range(new_v_min, new_v_span, v_low, v_high)
        self.update()

    @staticmethod
    def _bounded_range(start: float, span: float, minimum: float, maximum: float) -> tuple[float, float]:
        if start < minimum:
            start = minimum
        if start + span > maximum:
            start = maximum - span
        return start, start + span

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._plot_area().contains(event.position()):
            self._drag_position = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_position is None:
            return super().mouseMoveEvent(event)
        area = self._plot_area()
        delta = event.position() - self._drag_position
        self._drag_position = event.position()
        t_min, t_max = self._view_t
        v_min, v_max = self._view_v
        t_span, v_span = t_max - t_min, v_max - v_min
        self._view_t = self._bounded_range(t_min - delta.x() / area.width() * t_span, t_span, float(self._time[0]), float(self._time[-1]))
        v_low, v_high = self._voltage_bounds()
        self._view_v = self._bounded_range(v_min + delta.y() / area.height() * v_span, v_span, v_low, v_high)
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._drag_position is not None:
            self._drag_position = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.reset_view()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        area = self._plot_area()
        t_min, t_max = self._view_t
        v_min, v_max = self._view_v
        painter.setPen(QPen(QColor("#e8eef5"), 1))
        for index in range(6):
            y = area.top() + area.height() * index / 5
            painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            painter.setPen(QPen(QColor("#71869b"), 1))
            voltage_tick = v_max - (v_max - v_min) * index / 5
            tick_text = f"{voltage_tick:.0f}" if self.unit == "码" else f"{voltage_tick:.2f}"
            painter.drawText(QRectF(2, y - 8, 47, 16), Qt.AlignmentFlag.AlignRight, f"{tick_text} {self.unit}")
            painter.setPen(QPen(QColor("#e8eef5"), 1))
        for index in range(6):
            x = area.left() + area.width() * index / 5
            painter.drawLine(QPointF(x, area.top()), QPointF(x, area.bottom()))
        if self._time.size < 2:
            return
        span = max(t_max - t_min, 1e-9)
        visible = (self._time >= t_min) & (self._time <= t_max)
        indices = np.flatnonzero(visible)
        if indices.size < 2:
            return
        first, last = int(indices[0]), int(indices[-1]) + 1
        step = max(1, (last - first) // max(1, int(area.width() * 1.5)))
        painter.save()
        painter.setClipRect(area)
        for values, color, _label in self._signals:
            path = QPainterPath()
            if self.unit == "码":
                # Noise can change every 1 us. Bound paint work by screen width
                # while retaining narrow pulse maxima/minima (no stride aliasing).
                selected = first + envelope_indices(values[first:last], max(1, int(area.width())))
                points_t, points_v = self._time[selected], values[selected]
            else:
                points_t = self._time[first:last:step]
                points_v = values[first:last:step]
            for point_index, (time_value, voltage) in enumerate(zip(points_t, points_v, strict=True)):
                x = area.left() + (float(time_value) - t_min) / span * area.width()
                y = area.bottom() - (float(voltage) - v_min) / max(v_max - v_min, 1e-9) * area.height()
                if point_index == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            if self.unit == "码":
                # Dense noise paths with a thick antialiased pen spend seconds
                # tessellating overlapping joins. A cosmetic one-pixel trace
                # retains the same extrema with bounded rasterization cost.
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                pen = QPen(color, 1)
                pen.setCosmetic(True)
                painter.setPen(pen)
            else:
                painter.setPen(QPen(color, 1.7))
            painter.drawPath(path)
        painter.restore()
        painter.setPen(QPen(QColor("#50677d"), 1))
        painter.drawText(QRectF(area.left(), area.bottom() + 8, area.width(), 22), Qt.AlignmentFlag.AlignCenter, f"时间 {t_min:.1f}–{t_max:.1f} μs")
        x = area.left()
        for _values, color, label in self._signals:
            painter.fillRect(QRectF(x, 2, 12, 4), color)
            painter.drawText(QRectF(x + 17, -5, 80, 18), Qt.AlignmentFlag.AlignVCenter, label)
            x += 105


class WorkflowIndicator(QWidget):
    STEPS = ("选择信号源", "设置参数", "连接设备", "下发配置", "启动输出")

    def __init__(self) -> None:
        super().__init__()
        self._current = 1
        self._detail = "当前：设置通道参数"
        self.steps = self.STEPS
        self.setMinimumHeight(300)

    def set_step(self, index: int, detail: str) -> None:
        self._current = max(0, min(index, len(self.STEPS) - 1))
        self._detail = detail
        self.update()

    def current_step(self) -> int:
        return self._current

    def set_steps(self, steps: tuple[str, ...]) -> None:
        self.steps = steps
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        x = 22.0
        top = 28.0
        spacing = 49.0
        painter.setPen(QPen(QColor("#cbd5e1"), 3))
        painter.drawLine(QPointF(x, top), QPointF(x, top + spacing * (len(self.steps) - 1)))
        for index, label in enumerate(self.steps):
            y = top + index * spacing
            if index < self._current:
                color, text = QColor("#16803c"), "✓"
            elif index == self._current:
                color, text = QColor("#e76f00"), str(index + 1)
            else:
                color, text = QColor("#94a3b8"), str(index + 1)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(x, y), 12, 12)
            painter.setPen(QPen(QColor("#ffffff"), 1))
            painter.drawText(QRectF(x - 10, y - 10, 20, 20), Qt.AlignmentFlag.AlignCenter, text)
            painter.setPen(QPen(QColor("#23384d" if index <= self._current else "#8291a2"), 1))
            painter.drawText(QRectF(x + 22, y - 12, max(100, self.width() - 50), 24), Qt.AlignmentFlag.AlignVCenter, label)
        painter.setPen(QPen(QColor("#e76f00"), 1))
        painter.drawText(QRectF(4, top + spacing * len(self.steps) + 2, self.width() - 8, 42), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self._detail)
