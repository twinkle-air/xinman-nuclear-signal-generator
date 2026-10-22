"""仅负责把原界面适配到窗口可用尺寸，不改变业务控件或连接。"""
from PySide6.QtCore import QEvent, QRectF, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QTransform
from PySide6.QtWidgets import QFrame, QGraphicsScene, QGraphicsView, QSizePolicy, QWidget


class ResponsiveView(QGraphicsView):
    def __init__(self, content: QWidget, parent=None) -> None:
        super().__init__(parent)
        self.content = content
        self._fit_pending = False
        scene = QGraphicsScene(self)
        self.setScene(scene)
        self.proxy = scene.addWidget(content)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setBackgroundBrush(QColor("#f4f7fb"))
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        content.installEventFilter(self)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._schedule_fit()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched is self.content and event.type() == QEvent.Type.LayoutRequest:
            self._schedule_fit()
        return super().eventFilter(watched, event)

    def _schedule_fit(self) -> None:
        if not self._fit_pending:
            self._fit_pending = True
            QTimer.singleShot(0, self.fit_content)

    def fit_content(self) -> None:
        self._fit_pending = False
        width, height = self.viewport().width(), self.viewport().height()
        if width <= 0 or height <= 0:
            return
        minimum = self.content.minimumSizeHint().expandedTo(QSize(1100, 840))
        scale = min(1.0, width / minimum.width(), height / minimum.height())
        # 大窗口使用原布局伸展，小窗口等比缩放控件/字体/图表，始终完整显示。
        self.proxy.resize(width / scale, height / scale)
        self.setSceneRect(QRectF(0, 0, width / scale, height / scale))
        self.setTransform(QTransform.fromScale(scale, scale))
