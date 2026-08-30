from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMenu,
    QMessageBox,
    QDateEdit,
    QAbstractItemView,
    QFrame,
    QSizePolicy,
    QCalendarWidget,
    QTableView,
)
from PySide6.QtCore import Qt, QDate, Signal, QTimer, QRectF, QEvent
from PySide6.QtGui import (
    QBrush,
    QColor,
    QRegion,
    QPainter,
    QPen,
    QPalette,
    QPixmap,
    QPainterPath,
)

from organizer_db import (
    Database,
    LESSON_TYPE_LABELS,
    LESSON_TYPE_ICONS,
)
from assignments_tab import AssignmentDialog, parity_for_date, KIND_LABELS


WEEKDAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

SUBJECT_CHIP = ("📖", "#D3E3FD", "#041E49")
TEACHER_CHIP = ("👤", "#D5EFE9", "#0F6B5C")
ROOM_CHIP = ("📍", "#FDE7C8", "#9A5B00")

KIND_CHIP_STYLES = {
    "homework": ("📝", "#E8F0FE", "#174EA6"),
    "control": ("🧪", "#FCE8E6", "#C5221F"),
    "independent": ("✍️", "#FEF7E0", "#B06000"),
    "test": ("📋", "#E8F5E9", "#1B7340"),
    "presentation": ("🎤", "#F3E8FD", "#7627BB"),
    "exam": ("🎓", "#FDE7EF", "#B3186C"),
    "credit": ("✅", "#E6F4EA", "#137333"),
    "event": ("📅", "#E0F7FA", "#007B8A"),
    "other": ("📌", "#F1F3F6", "#3C4043"),
}

DONE_CHIP_STYLE = ("#E6F4EA", "#137333")

# Цвета типов пар в текстовом режиме
TEXT_TYPE_COLORS = {
    "lecture": "#137333",     # зелёный
    "practice": "#D93025",    # красный
    "lab": "#E8710A",         # оранжевый
    "other": "#1A73E8",       # синий
}

COLOR_EMPTY = "#FAFBFC"
COLOR_NORMAL = "#FFFFFF"

TODAY_BORDER_COLOR = "#0B3B7A"
TODAY_BORDER_WIDTH = 3.0


def make_chip(icon: str, text: str, bg: str, fg: str) -> QLabel:
    chip = QLabel(f"{icon} {text}" if icon else text)
    chip.setObjectName("cellChip")
    chip.setWordWrap(True)
    chip.setAlignment(
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )
    chip.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Minimum,
    )
    chip.setStyleSheet(
        f"background-color: {bg};"
        f"color: {fg};"
        "border-radius: 12px;"
        "padding: 6px 10px;"
        "font-weight: 700;"
        "font-size: 14px;"
    )
    return chip


def save_chevron_png(path: Path):
    pm = QPixmap(48, 48)
    pm.fill(Qt.GlobalColor.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor("#0B3B7A"))
    pen.setWidthF(4.5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    chevron = QPainterPath()
    chevron.moveTo(12, 18)
    chevron.lineTo(24, 30)
    chevron.lineTo(36, 18)

    p.drawPath(chevron)
    p.end()

    pm.save(str(path))


class BorderOverlay(QWidget):
    def __init__(
        self,
        radius: int = 18,
        width: float = 2.0,
        color: str = "#0B3B7A",
        parent=None,
    ):
        super().__init__(parent)

        self._radius = radius
        self._width = width
        self._color = QColor(color)

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(self._color)
        pen.setWidthF(self._width)

        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        margin = self._width / 2 + 0.5

        rect = QRectF(self.rect()).adjusted(margin, margin, -margin, -margin)

        p.drawRoundedRect(
            rect, max(self._radius - 2, 4), max(self._radius - 2, 4)
        )


class ColumnBorderOverlay(QWidget):
    def __init__(self, table: QTableWidget, parent=None):
        super().__init__(parent)

        self.table = table
        self.col = -1

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        if self.col < 0:
            return

        width = self.table.columnWidth(self.col)

        if width <= 0:
            return

        x = self.table.columnViewportPosition(self.col)

        if x + width < 0 or x > self.width():
            return

        content_height = 0

        for r in range(self.table.rowCount()):
            content_height += self.table.rowHeight(r)

        if content_height <= 0:
            return

        height = min(content_height, self.height())

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor(TODAY_BORDER_COLOR))
        pen.setWidthF(TODAY_BORDER_WIDTH)

        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        rect = QRectF(
            x + TODAY_BORDER_WIDTH / 2,
            TODAY_BORDER_WIDTH / 2,
            width - TODAY_BORDER_WIDTH,
            height - TODAY_BORDER_WIDTH,
        )

        p.drawRoundedRect(rect, 12, 12)


class CellBorderOverlay(QWidget):
    def __init__(self, table: QTableWidget, parent=None):
        super().__init__(parent)

        self.table = table
        self.cell = None

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        if not self.cell:
            return

        row, col = self.cell

        if row >= self.table.rowCount() or col >= self.table.columnCount():
            return

        x = self.table.columnViewportPosition(col)
        y = self.table.rowViewportPosition(row)

        w = self.table.columnWidth(col)
        h = self.table.rowHeight(row)

        if w <= 0 or h <= 0:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor("#4A7FD4"))
        pen.setWidthF(2.0)

        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        rect = QRectF(x + 2.5, y + 2.5, w - 5, h - 5)

        p.drawRoundedRect(rect, 10, 10)


class RoundedCard(QFrame):
    def __init__(self, radius: int = 18, parent=None):
        super().__init__(parent)

        self._radius = radius

        self._border_overlay = BorderOverlay(
            radius=radius,
            width=2.0,
            color="#0B3B7A",
            parent=self,
        )

    def resizeEvent(self, event):
        self._border_overlay.setGeometry(self.rect())
        self._border_overlay.raise_()

        super().resizeEvent(event)


class RoundedTable(QTableWidget):
    def __init__(self, radius: int = 12, parent=None):
        super().__init__(parent)
        self._radius = radius

    def resizeEvent(self, event):
        self._apply_mask()
        super().resizeEvent(event)

    def _apply_mask(self):
        w = self.width()
        h = self.height()
        r = self._radius

        if w <= 0 or h <= 0:
            return

        d = 2 * r

        region = QRegion(r, 0, w - d, h)
        region += QRegion(0, r, w, h - d)
        region += QRegion(0, 0, d, d, QRegion.RegionType.Ellipse)
        region += QRegion(w - d, 0, d, d, QRegion.RegionType.Ellipse)
        region += QRegion(0, h - d, d, d, QRegion.RegionType.Ellipse)
        region += QRegion(w - d, h - d, d, d, QRegion.RegionType.Ellipse)

        self.setMask(region)


class WeekGridTab(QWidget):
    saved = Signal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)

        self.db = db
        self.selected_date = QDate.currentDate()

        self.today_highlight = False
        self._current_dates = []

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(14)

        # ===== Верхняя панель =====
        top = QHBoxLayout()
        top.setSpacing(8)

        self.btn_prev = QPushButton("←")
        self.btn_prev.setObjectName("toolbarButton")
        self.btn_prev.setFixedWidth(44)

        self.btn_next = QPushButton("→")
        self.btn_next.setObjectName("toolbarButton")
        self.btn_next.setFixedWidth(44)

        self.btn_today = QPushButton("Сегодня")
        self.btn_today.setObjectName("toolbarButton")

        self.date_edit = QDateEdit(self.selected_date)
        self.date_edit.setObjectName("toolbarDate")
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_edit.setFixedWidth(200)

        self._apply_date_arrow_style()
        self.date_edit.installEventFilter(self)

        self.lbl_week = QLabel("")
        self.lbl_week.setObjectName("weekTitle")

        self.lbl_parity = QLabel("")
        self.lbl_parity.setObjectName("weekSubtitle")

        top.addWidget(self.btn_prev)
        top.addWidget(self.btn_next)
        top.addWidget(self.btn_today)
        top.addWidget(QLabel("Дата:"))
        top.addWidget(self.date_edit)
        top.addStretch(1)
        top.addWidget(self.lbl_week)
        top.addWidget(self.lbl_parity)

        layout.addLayout(top)

        # ===== Панель вида =====
        opts = QHBoxLayout()
        opts.setSpacing(8)

        self.btn_text_view = QPushButton("📄 Текстовый вид")
        self.btn_text_view.setObjectName("toolbarButton")
        self.btn_text_view.setCheckable(True)
        self.btn_text_view.setToolTip(
            "Переключение между текстовым видом и цветными чипами"
        )

        self.btn_sunday = QPushButton("📆 Воскресенье")
        self.btn_sunday.setObjectName("toolbarButton")
        self.btn_sunday.setCheckable(True)
        self.btn_sunday.setChecked(True)
        self.btn_sunday.setToolTip("Показать / скрыть воскресенье")

        opts.addWidget(self.btn_text_view)
        opts.addWidget(self.btn_sunday)
        opts.addStretch(1)

        layout.addLayout(opts)

        # Восстанавливаем сохранённые настройки вида
        rows = self.db.query(
            """
            SELECT overview_text_view, overview_show_sunday
            FROM settings
            WHERE id = 1
            """
        )

        if rows:
            self.btn_text_view.setChecked(
                bool(rows[0]["overview_text_view"])
            )
            self.btn_sunday.setChecked(
                bool(rows[0]["overview_show_sunday"])
            )

        # ===== Таблица в скруглённой карточке =====
        self.table_card = RoundedCard(radius=18)
        self.table_card.setObjectName("tableCard")

        card_layout = QVBoxLayout(self.table_card)
        card_layout.setContentsMargins(8, 8, 8, 8)

        self.table = RoundedTable(radius=12)
        self.table.setObjectName("weekGrid")
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectItems
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        vh = self.table.verticalHeader()
        vh.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        vh.setDefaultSectionSize(112)
        vh.setFixedWidth(116)
        vh.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

        self.table.setShowGrid(True)

        card_layout.addWidget(self.table)
        layout.addWidget(self.table_card, 1)

        # ===== Оверлеи =====
        self._today_overlay = ColumnBorderOverlay(
            self.table,
            self.table.viewport(),
        )

        self._cell_overlay = CellBorderOverlay(
            self.table,
            self.table.viewport(),
        )

        self.table.horizontalScrollBar().valueChanged.connect(
            lambda value: self._update_overlays_geometry()
        )
        self.table.verticalScrollBar().valueChanged.connect(
            lambda value: self._update_overlays_geometry()
        )

        self.table.cellClicked.connect(self._on_cell_clicked)

        # ===== Сигналы =====
        self.btn_prev.clicked.connect(
            lambda checked=False: self.shift_days(-7)
        )
        self.btn_next.clicked.connect(
            lambda checked=False: self.shift_days(7)
        )
        self.btn_today.clicked.connect(
            lambda checked=False: self.go_today()
        )
        self.date_edit.dateChanged.connect(
            lambda d: self.on_date_changed(d)
        )

        self.btn_text_view.toggled.connect(self._on_text_view_toggled)
        self.btn_sunday.toggled.connect(self._on_sunday_toggled)

        # Применяем синий стиль кнопки, если текстовый вид был сохранён
        self._apply_text_view_button_style(
            self.btn_text_view.isChecked()
        )

        self.table.doubleClicked.connect(
            lambda index: self.on_double_click(index)
        )
        self.table.customContextMenuRequested.connect(
            lambda pos: self.show_context_menu(pos)
        )

    # ===== Переключатель текстового вида =====

    def _on_text_view_toggled(self, checked: bool):
        self._apply_text_view_button_style(checked)
        self._save_view_settings()
        self.refresh()

    def _apply_text_view_button_style(self, checked: bool):
        if checked:
            # Включён: синий фон, белый текст
            self.btn_text_view.setStyleSheet(
                "QPushButton {"
                " background-color: #0061A4;"
                " color: #FFFFFF;"
                " border: 1px solid #004A7F;"
                "}"
                "QPushButton:hover { background-color: #1A73E8; }"
            )
        else:
            # Выключен: обычный стиль toolbarButton
            self.btn_text_view.setStyleSheet("")

    def _on_sunday_toggled(self, checked: bool):
        self._save_view_settings()
        self.refresh()

    def _save_view_settings(self):
        self.db.execute(
            """
            UPDATE settings
            SET overview_text_view = ?, overview_show_sunday = ?
            WHERE id = 1
            """,
            (
                1 if self.btn_text_view.isChecked() else 0,
                1 if self.btn_sunday.isChecked() else 0,
            ),
        )

    # ===== Стрелка у даты =====

    def _apply_date_arrow_style(self):
        icon_dir = Path.home() / ".semester_organizer" / "icons"
        icon_dir.mkdir(parents=True, exist_ok=True)

        chevron_path = icon_dir / "chevron_dark.png"

        if not chevron_path.exists():
            save_chevron_png(chevron_path)

        self.date_edit.setStyleSheet(
            f"""
            QDateEdit::drop-down {{
                border: none;
                width: 30px;
                background: #E3EDFB;
                border-radius: 13px;
                margin: 5px 6px;
            }}
            QDateEdit::down-arrow {{
                border: none;
                image: url({chevron_path});
                width: 18px;
                height: 18px;
            }}
            """
        )

    # ===== Календарь =====

    def eventFilter(self, obj, event):
        if (
            obj is self.date_edit
            and event.type() == QEvent.Type.MouseButtonPress
        ):
            QTimer.singleShot(0, self._patch_calendar_popup)

        return super().eventFilter(obj, event)

    def _patch_calendar_popup(self):
        cal = self.date_edit.findChild(QCalendarWidget)

        if cal is None:
            return

        pal = cal.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor("#FFFFFF"))
        pal.setColor(QPalette.ColorRole.WindowText, QColor("#1A1C1E"))
        pal.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
        pal.setColor(QPalette.ColorRole.Text, QColor("#1A1C1E"))
        pal.setColor(QPalette.ColorRole.Button, QColor("#E8EDF5"))
        pal.setColor(QPalette.ColorRole.ButtonText, QColor("#1A1C1E"))
        pal.setColor(QPalette.ColorRole.Highlight, QColor("#D3E3FD"))
        pal.setColor(
            QPalette.ColorRole.HighlightedText, QColor("#001D35")
        )
        pal.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
        cal.setPalette(pal)

        view = cal.findChild(QTableView)

        if view is not None:
            view.setPalette(pal)
            view.verticalHeader().setDefaultSectionSize(38)

            hh = view.horizontalHeader()
            hh.setPalette(pal)

    # ===== Оверлеи и выделение =====

    def _update_overlays_geometry(self):
        for overlay in (self._today_overlay, self._cell_overlay):
            overlay.setGeometry(self.table.viewport().rect())
            overlay.raise_()
            overlay.update()

    def _update_today_overlay(self):
        col = -1

        if self.today_highlight and self._current_dates:
            today = QDate.currentDate()

            for i, d in enumerate(self._current_dates):
                if d == today:
                    col = i
                    break

        self._today_overlay.col = col
        self._update_overlays_geometry()

    def _on_cell_clicked(self, row: int, col: int):
        self._cell_overlay.cell = (row, col)
        self._update_overlays_geometry()

    def go_today(self):
        self._cell_overlay.cell = None
        self.today_highlight = True

        today = QDate.currentDate()

        if self.date_edit.date() != today:
            self.date_edit.setDate(today)
        else:
            self._update_today_overlay()

    # ===== Основное =====

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._adjust_row_heights)

    def refresh(self):
        monday = self.selected_date.addDays(
            -(self.selected_date.dayOfWeek() - 1)
        )
        sunday = monday.addDays(6)

        self.lbl_week.setText(
            f"{monday.toString('dd.MM.yyyy')} — "
            f"{sunday.toString('dd.MM.yyyy')}"
        )

        week_parity = parity_for_date(self.db, monday)

        if week_parity == "numerator":
            self.lbl_parity.setText("Числитель")
        else:
            self.lbl_parity.setText("Знаменатель")

        self.build_grid(monday)

    def on_date_changed(self, date: QDate):
        self.selected_date = date
        self.refresh()

    def shift_days(self, days: int):
        self.date_edit.setDate(self.date_edit.date().addDays(days))

    def build_grid(self, monday: QDate):
        days_count = 7 if self.btn_sunday.isChecked() else 6
        dates = [monday.addDays(i) for i in range(days_count)]
        self._current_dates = dates

        text_mode = self.btn_text_view.isChecked()

        row_keys = []
        added_keys = set()
        slots_by_date = {}

        my_sub = self._get_my_subgroup()

        if my_sub:
            sub_cond = "AND (s.subgroup = 0 OR s.subgroup = ?)"
            sub_params = [my_sub]
        else:
            sub_cond = ""
            sub_params = []

        for col, date in enumerate(dates):
            parity = parity_for_date(self.db, date)

            slots = self.db.query(
                f"""
                SELECT
                    s.*,
                    sub.name AS subject_name
                FROM schedule_slots s
                JOIN subjects sub ON sub.id = s.subject_id
                WHERE s.weekday = ?
                  AND (s.parity = 'all' OR s.parity = ?)
                  {sub_cond}
                ORDER BY s.lesson_no, s.start_time
                """,
                (date.dayOfWeek(), parity) + tuple(sub_params),
            )

            slots_by_date[col] = list(slots)

            for slot in slots_by_date[col]:
                key = (
                    slot["lesson_no"],
                    slot["start_time"],
                    slot["end_time"],
                )

                if key not in added_keys:
                    added_keys.add(key)
                    row_keys.append(key)

        # Перенесённые пары из заданий
        for col, date in enumerate(dates):
            date_iso = date.toString("yyyy-MM-dd")

            assigned_slots = self.db.query(
                """
                SELECT DISTINCT slot_id
                FROM assignments
                WHERE date = ?
                  AND slot_id IS NOT NULL
                """,
                (date_iso,),
            )

            existing_ids = {slot["id"] for slot in slots_by_date[col]}

            for assigned_slot in assigned_slots:
                slot_id = assigned_slot["slot_id"]

                if slot_id in existing_ids:
                    continue

                extra_slots = self.db.query(
                    """
                    SELECT
                        s.*,
                        sub.name AS subject_name
                    FROM schedule_slots s
                    JOIN subjects sub ON sub.id = s.subject_id
                    WHERE s.id = ?
                    """,
                    (slot_id,),
                )

                if extra_slots:
                    slot = extra_slots[0]

                    if my_sub and slot["subgroup"] not in (0, my_sub):
                        continue

                    slots_by_date[col].append(slot)
                    existing_ids.add(slot["id"])

                    key = (
                        slot["lesson_no"],
                        slot["start_time"],
                        slot["end_time"],
                    )

                    if key not in added_keys:
                        added_keys.add(key)
                        row_keys.append(key)

        row_keys.sort(key=lambda x: (x[0], x[1], x[2]))

        horizontal_labels = [
            f"{WEEKDAYS_SHORT[i]} {dates[i].toString('dd.MM')}"
            for i in range(len(dates))
        ]

        vertical_labels = [
            f"{lesson} пара\n{start}\n—\n{end}"
            for lesson, start, end in row_keys
        ]

        self.table.clear()
        self.table.setRowCount(len(row_keys))
        self.table.setColumnCount(len(dates))

        self.table.setHorizontalHeaderLabels(horizontal_labels)
        self.table.setVerticalHeaderLabels(vertical_labels)

        for col, date in enumerate(dates):
            date_iso = date.toString("yyyy-MM-dd")

            slots_by_key = {}

            for slot in slots_by_date[col]:
                key = (
                    slot["lesson_no"],
                    slot["start_time"],
                    slot["end_time"],
                )
                slots_by_key.setdefault(key, []).append(slot)

            for row, key in enumerate(row_keys):
                item = QTableWidgetItem()
                item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                item.setData(Qt.ItemDataRole.UserRole, date_iso)

                cell_slots = slots_by_key.get(key, [])

                slot_ids = [str(slot["id"]) for slot in cell_slots]
                item.setData(
                    Qt.ItemDataRole.UserRole + 1,
                    ",".join(slot_ids),
                )

                widget = None
                assignment_ids = []

                if cell_slots:
                    if text_mode:
                        widget, assignment_ids = self._make_text_cell(
                            date_iso, cell_slots
                        )
                    else:
                        widget, assignment_ids = self._make_chip_cell(
                            date_iso, cell_slots
                        )

                item.setData(
                    Qt.ItemDataRole.UserRole + 2,
                    ",".join(str(x) for x in assignment_ids),
                )

                if cell_slots:
                    bg_color = COLOR_NORMAL
                else:
                    bg_color = COLOR_EMPTY

                item.setBackground(QBrush(QColor(bg_color)))

                self.table.setItem(row, col, item)

                if widget is not None:
                    self.table.setCellWidget(row, col, widget)

        QTimer.singleShot(0, self._adjust_row_heights)
        QTimer.singleShot(0, self._update_today_overlay)

    # ===== Ячейка с цветными чипами (старый вид) =====

    def _make_chip_cell(self, date_iso, cell_slots):
        assignment_ids = []
        tooltips = []

        card = QFrame()
        card.setObjectName("cellCard")
        card.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(6, 6, 6, 6)
        card_layout.setSpacing(4)

        for slot in cell_slots:
            icon, bg, fg = SUBJECT_CHIP
            card_layout.addWidget(
                make_chip(icon, slot["subject_name"], bg, fg)
            )

            type_label = LESSON_TYPE_LABELS.get(slot["lesson_type"], "")

            if type_label:
                type_icon = LESSON_TYPE_ICONS.get(
                    slot["lesson_type"], "📌"
                )
                card_layout.addWidget(
                    make_chip(type_icon, type_label, "#E8F0FE", "#174EA6")
                )

            if slot["subgroup"]:
                card_layout.addWidget(
                    make_chip(
                        "👥",
                        f"подгруппа {slot['subgroup']}",
                        "#F1F3F6",
                        "#3C4043",
                    )
                )

            if slot["teacher"]:
                icon, bg, fg = TEACHER_CHIP
                card_layout.addWidget(
                    make_chip(icon, slot["teacher"], bg, fg)
                )

            if slot["room"]:
                icon, bg, fg = ROOM_CHIP
                card_layout.addWidget(
                    make_chip(icon, slot["room"], bg, fg)
                )

            assignments = self.db.query(
                """
                SELECT
                    a.*,
                    (
                        SELECT COUNT(*)
                        FROM assignment_files f
                        WHERE f.assignment_id = a.id
                    ) AS files_count
                FROM assignments a
                WHERE a.date = ?
                  AND a.slot_id = ?
                ORDER BY a.kind, a.title
                """,
                (date_iso, slot["id"]),
            )

            for assignment in assignments:
                assignment_ids.append(assignment["id"])

                kind = assignment["kind"]

                icon, bg, fg = KIND_CHIP_STYLES.get(
                    kind, KIND_CHIP_STYLES["other"]
                )

                if assignment["done"]:
                    bg, fg = DONE_CHIP_STYLE
                    icon = "✔"

                title = (
                    assignment["title"] or KIND_LABELS.get(kind, kind)
                )

                if assignment["files_count"]:
                    title += f" 📎{assignment['files_count']}"

                card_layout.addWidget(make_chip(icon, title, bg, fg))

                if assignment["description"]:
                    tooltips.append(
                        f"{KIND_LABELS.get(kind, kind)}: "
                        f"{assignment['title']}\n"
                        f"{assignment['description']}"
                    )

        card_layout.addStretch(1)

        if tooltips:
            card.setToolTip("\n".join(tooltips))

        return card, assignment_ids

    # ===== Текстовая ячейка =====

    def _make_text_cell(self, date_iso, cell_slots):
        assignment_ids = []
        blocks = []

        for slot in cell_slots:
            lines = []

            type_label = LESSON_TYPE_LABELS.get(slot["lesson_type"], "")
            type_color = TEXT_TYPE_COLORS.get(
                slot["lesson_type"], "#1A1C1E"
            )

            if type_label:
                lines.append(
                    f'<div style="color:{type_color}; font-weight:800;">'
                    f"{type_label.upper()}"
                    "</div>"
                )

            lines.append(
                f'<div style="color:#1A1C1E;">{slot["subject_name"]}'
                "</div>"
            )

            teacher_line = slot["teacher"] or ""

            if slot["subgroup"]:
                teacher_line += f" ({slot['subgroup']} подгруппа)"

            if teacher_line.strip():
                lines.append(
                    f'<div style="color:#137333;">'
                    f"{teacher_line.strip()}"
                    "</div>"
                )

            if slot["room"]:
                lines.append(
                    f'<div style="color:#2A5BD7;">{slot["room"]}</div>'
                )

            assignments = self.db.query(
                """
                SELECT a.*
                FROM assignments a
                WHERE a.date = ?
                  AND a.slot_id = ?
                ORDER BY a.kind, a.title
                """,
                (date_iso, slot["id"]),
            )

            if assignments:
                for a in assignments:
                    assignment_ids.append(a["id"])

                if all(a["done"] for a in assignments):
                    lines.append(
                        '<div style="color:#137333;">'
                        "<u>ДЗ выполнено ✔</u></div>"
                    )
                else:
                    lines.append(
                        '<div style="color:#E8710A;">'
                        "<u>Есть домашнее задание!</u></div>"
                    )

            blocks.append("".join(lines))

        label = QLabel("<br>".join(blocks))
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        label.setStyleSheet(
            "background: transparent; padding: 4px; font-size: 13px;"
        )

        return label, assignment_ids

    # ===== Высота строк (всегда авто) =====

    def _adjust_row_heights(self):
        cols = self.table.columnCount()

        for row in range(self.table.rowCount()):
            needed = 72

            for col in range(cols):
                widget = self.table.cellWidget(row, col)

                if widget is None:
                    continue

                width = self.table.columnWidth(col)

                if width <= 0:
                    width = max(
                        self.table.viewport().width() // max(cols, 1), 120
                    )

                usable = max(width - 16, 60)

                lay = widget.layout()

                if lay is None:
                    # Текстовая ячейка (QLabel)
                    if hasattr(widget, "heightForWidth"):
                        hh = widget.heightForWidth(usable)
                    else:
                        hh = widget.sizeHint().height()

                    needed = max(needed, hh + 8)
                    continue

                lay.activate()

                h = 12
                count = 0

                for i in range(lay.count()):
                    lay_item = lay.itemAt(i)
                    w = lay_item.widget()

                    if w is None:
                        continue

                    count += 1

                    if hasattr(w, "wordWrap") and w.wordWrap():
                        h += w.heightForWidth(usable)
                    else:
                        h += w.sizeHint().height()

                h += lay.spacing() * max(count - 1, 0)

                needed = max(needed, h)

            self.table.setRowHeight(row, needed + 10)

        self._update_overlays_geometry()

    def _get_my_subgroup(self) -> int:
        rows = self.db.query(
            "SELECT my_subgroup FROM settings WHERE id = 1"
        )

        if rows and rows[0]["my_subgroup"]:
            return int(rows[0]["my_subgroup"])

        return 0

    # ===== Действия с заданиями =====

    def on_double_click(self, index):
        item = self.table.itemFromIndex(index)

        if not item:
            return

        date_iso = item.data(Qt.ItemDataRole.UserRole)

        if not date_iso:
            return

        assignment_ids_str = item.data(Qt.ItemDataRole.UserRole + 2) or ""

        if assignment_ids_str:
            first_id = assignment_ids_str.split(",")[0]

            if first_id.strip().isdigit():
                self.edit_assignment(int(first_id))
                return

        slot_ids_str = item.data(Qt.ItemDataRole.UserRole + 1) or ""
        slot_id = None

        if slot_ids_str:
            first_slot = slot_ids_str.split(",")[0]

            if first_slot.strip().isdigit():
                slot_id = int(first_slot)

        self.add_assignment(date_iso, slot_id)

    def show_context_menu(self, pos):
        item = self.table.itemAt(pos)

        if not item:
            return

        date_iso = item.data(Qt.ItemDataRole.UserRole)

        if not date_iso:
            return

        slot_ids_str = item.data(Qt.ItemDataRole.UserRole + 1) or ""
        assignment_ids_str = item.data(Qt.ItemDataRole.UserRole + 2) or ""

        slot_ids = [
            int(x)
            for x in slot_ids_str.split(",")
            if x.strip().isdigit()
        ]

        assignment_ids = [
            int(x)
            for x in assignment_ids_str.split(",")
            if x.strip().isdigit()
        ]

        menu = QMenu(self)

        if slot_ids:
            if len(slot_ids) == 1:
                menu.addAction(
                    "Добавить задание к паре",
                    lambda checked=False, d=date_iso, s=slot_ids[0]:
                        self.add_assignment(d, s),
                )
            else:
                for slot_id in slot_ids:
                    menu.addAction(
                        f"Добавить к паре {slot_id}",
                        lambda checked=False, d=date_iso, s=slot_id:
                            self.add_assignment(d, s),
                    )

        menu.addAction(
            "Добавить задание без пары",
            lambda checked=False, d=date_iso:
                self.add_assignment(d, None),
        )

        if assignment_ids:
            menu.addSeparator()

            for assignment_id in assignment_ids:
                rows = self.db.query(
                    """
                    SELECT id, kind, title, done
                    FROM assignments
                    WHERE id = ?
                    """,
                    (assignment_id,),
                )

                if not rows:
                    continue

                assignment = rows[0]

                kind_label = KIND_LABELS.get(
                    assignment["kind"], assignment["kind"]
                )

                title = assignment["title"] or kind_label
                mark = "✔" if assignment["done"] else "○"

                submenu = menu.addMenu(f"{mark} {kind_label}: {title}")

                submenu.addAction(
                    "Редактировать",
                    lambda checked=False, aid=assignment_id:
                        self.edit_assignment(aid),
                )

                submenu.addAction(
                    "Выполнено / не выполнено",
                    lambda checked=False, aid=assignment_id:
                        self.toggle_assignment(aid),
                )

                submenu.addAction(
                    "Удалить",
                    lambda checked=False, aid=assignment_id:
                        self.delete_assignment(aid),
                )

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def add_assignment(self, date_iso: str, slot_id):
        date = QDate.fromString(date_iso, "yyyy-MM-dd")

        if not date.isValid():
            date = QDate.currentDate()

        dialog = AssignmentDialog(
            self.db,
            assignment_id=None,
            default_date=date,
            default_slot_id=slot_id,
            parent=self,
        )

        if dialog.exec():
            self.refresh()
            self.saved.emit()

    def edit_assignment(self, assignment_id: int):
        dialog = AssignmentDialog(
            self.db,
            assignment_id=assignment_id,
            parent=self,
        )

        if dialog.exec():
            self.refresh()
            self.saved.emit()

    def toggle_assignment(self, assignment_id: int):
        rows = self.db.query(
            "SELECT done FROM assignments WHERE id = ?",
            (assignment_id,),
        )

        if not rows:
            return

        new_done = 0 if rows[0]["done"] else 1

        self.db.execute(
            "UPDATE assignments SET done = ? WHERE id = ?",
            (new_done, assignment_id),
        )

        self.refresh()
        self.saved.emit()

    def delete_assignment(self, assignment_id: int):
        answer = QMessageBox.question(
            self,
            "Удаление задания",
            "Удалить выбранное задание?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.db.execute(
            "DELETE FROM assignments WHERE id = ?",
            (assignment_id,),
        )

        self.refresh()
        self.saved.emit()
