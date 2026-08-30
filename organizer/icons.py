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

def file_kind(path) -> str:
    """Определяет тип файла для иконки."""
    from pathlib import Path as _Path

    p = _Path(path)

    if p.is_dir():
        return "folder"

    ext = p.suffix.lower()

    if ext in {".txt", ".md", ".rst", ".log", ".ini", ".cfg",
               ".csv", ".tsv", ".doc", ".docx", ".odt"}:
        return "text"
    if ext in {".py", ".js", ".ts", ".c", ".cpp", ".h", ".hpp",
               ".java", ".sql", ".sh", ".bat", ".json", ".xml",
               ".html", ".htm", ".css", ".yml", ".yaml", ".pro", ".ui"}:
        return "code"
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp"}:
        return "image"
    if ext == ".pdf":
        return "pdf"
    if ext in {".xls", ".xlsx", ".ods"}:
        return "sheet"
    if ext in {".ppt", ".pptx", ".odp"}:
        return "slides"
    if ext in {".zip", ".rar", ".7z", ".tar", ".gz"}:
        return "archive"
    if ext in {".mp3", ".wav", ".mp4", ".mkv", ".avi", ".mov", ".flac", ".opus", ".ogg"}:
        return "media"

    # Универсальная иконка для нечитаемых/неизвестных документов
    return "unknown"


def make_file_icon(kind: str, size: int = 64):
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    s = float(size)
    stroke = QColor("#0B3B7A")

    pen = QPen(stroke)
    pen.setWidthF(s * 0.05)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    # ===== Папка с заливкой =====
    if kind == "folder":
        tab = QPainterPath()
        tab.moveTo(0.10 * s, 0.32 * s)
        tab.lineTo(0.10 * s, 0.22 * s)
        tab.lineTo(0.38 * s, 0.22 * s)
        tab.lineTo(0.46 * s, 0.32 * s)
        tab.closeSubpath()

        p.fillPath(tab, QColor("#5B92E8"))
        p.drawPath(tab)

        p.setBrush(QColor("#8AB4F8"))
        p.drawRoundedRect(
            QRectF(0.10 * s, 0.30 * s, 0.80 * s, 0.50 * s),
            0.06 * s, 0.06 * s,
        )
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.end()
        return QIcon(pm)

    # ===== Страница с загнутым углом =====
    fills = {
        "text": "#AECBFA",
        "code": "#A8DAB5",
        "image": "#F9D28E",
        "pdf": "#F5B8B4",
        "sheet": "#A8DAB5",
        "slides": "#F9D28E",
        "archive": "#CFD8DC",
        "media": "#D0B4F2",
        "unknown": "#CFD8DC",
    }
    fill = fills.get(kind, "#CFD8DC")

    left, top, bottom = 0.20 * s, 0.10 * s, 0.90 * s
    right = 0.80 * s
    fold = 0.20 * s

    page = QPainterPath()
    page.moveTo(left, top)
    page.lineTo(right - fold, top)
    page.lineTo(right, top + fold)
    page.lineTo(right, bottom)
    page.lineTo(left, bottom)
    page.closeSubpath()

    p.fillPath(page, QColor(fill))
    p.drawPath(page)

    p.drawLine(QPointF(right - fold, top), QPointF(right - fold, top + fold))
    p.drawLine(QPointF(right - fold, top + fold), QPointF(right, top + fold))

    # ===== Символ типа =====
    if kind == "text":
        for y in (0.45, 0.58, 0.71):
            p.drawLine(QPointF(0.30 * s, y * s), QPointF(0.70 * s, y * s))

    elif kind == "code":
        ch = QPainterPath()
        ch.moveTo(0.40 * s, 0.45 * s)
        ch.lineTo(0.30 * s, 0.57 * s)
        ch.lineTo(0.40 * s, 0.69 * s)
        ch.moveTo(0.60 * s, 0.45 * s)
        ch.lineTo(0.70 * s, 0.57 * s)
        ch.lineTo(0.60 * s, 0.69 * s)
        p.drawPath(ch)

    elif kind == "image":
        p.drawEllipse(QPointF(0.38 * s, 0.45 * s), 0.05 * s, 0.05 * s)
        m = QPainterPath()
        m.moveTo(0.28 * s, 0.72 * s)
        m.lineTo(0.45 * s, 0.55 * s)
        m.lineTo(0.58 * s, 0.68 * s)
        m.lineTo(0.66 * s, 0.60 * s)
        m.lineTo(0.72 * s, 0.72 * s)
        p.drawPath(m)

    elif kind == "pdf":
        font = p.font()
        font.setPixelSize(int(s * 0.18))
        font.setBold(True)
        p.setFont(font)
        p.drawText(
            QRectF(0.22 * s, 0.52 * s, 0.56 * s, 0.28 * s),
            Qt.AlignmentFlag.AlignCenter,
            "PDF",
        )

    elif kind == "sheet":
        for x in (0.42, 0.56):
            p.drawLine(QPointF(x * s, 0.42 * s), QPointF(x * s, 0.76 * s))
        for y in (0.53, 0.64):
            p.drawLine(QPointF(0.30 * s, y * s), QPointF(0.70 * s, y * s))

    elif kind == "slides":
        p.setBrush(QColor("#0B3B7A"))
        p.drawRoundedRect(
            QRectF(0.32 * s, 0.46 * s, 0.36 * s, 0.24 * s),
            0.03 * s, 0.03 * s,
        )
        p.setBrush(Qt.BrushStyle.NoBrush)

    elif kind == "archive":
        zip_pen = QPen(stroke)
        zip_pen.setWidthF(s * 0.04)
        zip_pen.setDashPattern([1.5, 1.5])
        p.setPen(zip_pen)
        p.drawLine(QPointF(0.50 * s, 0.14 * s), QPointF(0.50 * s, 0.58 * s))
        p.setPen(pen)
        p.drawRoundedRect(
            QRectF(0.44 * s, 0.58 * s, 0.12 * s, 0.16 * s),
            0.02 * s, 0.02 * s,
        )

    elif kind == "media":
        t = QPainterPath()
        t.moveTo(0.42 * s, 0.45 * s)
        t.lineTo(0.62 * s, 0.57 * s)
        t.lineTo(0.42 * s, 0.69 * s)
        t.closeSubpath()
        p.fillPath(t, stroke)

    elif kind == "unknown":
        font = p.font()
        font.setPixelSize(int(s * 0.30))
        font.setBold(True)
        p.setFont(font)
        p.drawText(
            QRectF(0.20 * s, 0.42 * s, 0.60 * s, 0.40 * s),
            Qt.AlignmentFlag.AlignCenter,
            "?",
        )

    p.end()
    return QIcon(pm)
