from PySide6.QtGui import (
    QIcon,
    QPixmap,
    QPainter,
    QPen,
    QColor,
    QPainterPath,
)
from PySide6.QtCore import Qt, QRectF, QPointF


ICON_COLOR = "#0B3B7A"


def make_icon(name: str, color: str = ICON_COLOR, size: int = 64) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color))
    pen.setWidthF(size * 0.075)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    s = float(size)

    if name == "home":
        roof = QPainterPath()
        roof.moveTo(0.14 * s, 0.47 * s)
        roof.lineTo(0.50 * s, 0.15 * s)
        roof.lineTo(0.86 * s, 0.47 * s)
        p.drawPath(roof)

        p.drawRoundedRect(
            QRectF(0.24 * s, 0.40 * s, 0.52 * s, 0.44 * s),
            0.05 * s,
            0.05 * s,
        )

        p.drawLine(QPointF(0.50 * s, 0.84 * s), QPointF(0.50 * s, 0.68 * s))

    elif name == "tasks":
        p.drawRoundedRect(
            QRectF(0.26 * s, 0.12 * s, 0.48 * s, 0.76 * s),
            0.06 * s,
            0.06 * s,
        )

        for y in (0.32, 0.48, 0.64):
            p.drawLine(QPointF(0.36 * s, y * s), QPointF(0.64 * s, y * s))

    elif name == "clock":
        p.drawEllipse(QRectF(0.16 * s, 0.16 * s, 0.68 * s, 0.68 * s))
        p.drawLine(QPointF(0.50 * s, 0.50 * s), QPointF(0.50 * s, 0.30 * s))
        p.drawLine(QPointF(0.50 * s, 0.50 * s), QPointF(0.65 * s, 0.58 * s))

    elif name == "check":
        p.drawEllipse(QRectF(0.16 * s, 0.16 * s, 0.68 * s, 0.68 * s))

        check = QPainterPath()
        check.moveTo(0.32 * s, 0.51 * s)
        check.lineTo(0.45 * s, 0.63 * s)
        check.lineTo(0.68 * s, 0.37 * s)
        p.drawPath(check)

    elif name == "folder":
        folder = QPainterPath()
        folder.moveTo(0.14 * s, 0.78 * s)
        folder.lineTo(0.14 * s, 0.26 * s)
        folder.lineTo(0.38 * s, 0.26 * s)
        folder.lineTo(0.46 * s, 0.36 * s)
        folder.lineTo(0.86 * s, 0.36 * s)
        folder.lineTo(0.86 * s, 0.78 * s)
        folder.closeSubpath()
        p.drawPath(folder)

    elif name == "book":
        left = QPainterPath()
        left.moveTo(0.50 * s, 0.80 * s)
        left.cubicTo(0.40 * s, 0.72 * s, 0.24 * s, 0.70 * s, 0.14 * s, 0.74 * s)
        left.lineTo(0.14 * s, 0.28 * s)
        left.cubicTo(0.24 * s, 0.24 * s, 0.40 * s, 0.26 * s, 0.50 * s, 0.34 * s)
        p.drawPath(left)

        right = QPainterPath()
        right.moveTo(0.50 * s, 0.80 * s)
        right.cubicTo(0.60 * s, 0.72 * s, 0.76 * s, 0.70 * s, 0.86 * s, 0.74 * s)
        right.lineTo(0.86 * s, 0.28 * s)
        right.cubicTo(0.76 * s, 0.24 * s, 0.60 * s, 0.26 * s, 0.50 * s, 0.34 * s)
        p.drawPath(right)

        p.drawLine(QPointF(0.50 * s, 0.34 * s), QPointF(0.50 * s, 0.80 * s))

    elif name == "calendar":
        p.drawRoundedRect(
            QRectF(0.16 * s, 0.20 * s, 0.68 * s, 0.64 * s),
            0.07 * s,
            0.07 * s,
        )

        p.drawLine(QPointF(0.16 * s, 0.38 * s), QPointF(0.84 * s, 0.38 * s))
        p.drawLine(QPointF(0.34 * s, 0.12 * s), QPointF(0.34 * s, 0.26 * s))
        p.drawLine(QPointF(0.66 * s, 0.12 * s), QPointF(0.66 * s, 0.26 * s))

        dot_pen = QPen(pen)
        dot_pen.setWidthF(size * 0.10)
        p.setPen(dot_pen)

        dots = (
            (0.34, 0.54),
            (0.50, 0.54),
            (0.66, 0.54),
            (0.34, 0.68),
            (0.50, 0.68),
        )

        for x, y in dots:
            p.drawPoint(QPointF(x * s, y * s))

    elif name == "menu":
        for y in (0.30, 0.50, 0.70):
            p.drawLine(QPointF(0.22 * s, y * s), QPointF(0.78 * s, y * s))

    elif name == "chevron":
        chevron = QPainterPath()
        chevron.moveTo(0.24 * s, 0.38 * s)
        chevron.lineTo(0.50 * s, 0.64 * s)
        chevron.lineTo(0.76 * s, 0.38 * s)
        p.drawPath(chevron)

    p.end()

    return QIcon(pm)
