from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
    QScrollArea,
    QMessageBox,
    QCheckBox,
    QDateEdit,
    QSizePolicy,
    QCalendarWidget,
    QTableView,
)
from PySide6.QtCore import Qt, QDate, Signal, QEvent, QTimer
from PySide6.QtGui import QPalette, QColor

from organizer_db import Database
from assignments_tab import (
    AssignmentDialog,
    KIND_LABELS,
    parity_for_date,
)


DAY_NAMES = {
    1: "Понедельник",
    2: "Вторник",
    3: "Среда",
    4: "Четверг",
    5: "Пятница",
    6: "Суббота",
    7: "Воскресенье",
}

FILTER_CHIPS = [
    ("all", "Все", "📋"),
    ("homework", "Домашние", "📝"),
    ("control", "Контрольные", "🧪"),
    ("test", "Тесты", "📋"),
    ("uncompleted", "Невыполненные", "⏳"),
    ("today", "Сегодня", "📅"),
    ("week", "Эта неделя", "🗓️"),
]

CHIP_STYLE_TEMPLATES = {
    "all": ("#F1F3F6", "#3C4043", "#C7D1DC", "#C7D1DC", "#1A1C1E", "#5F6368"),
    "homework": ("#E8F0FE", "#174EA6", "#AECBFA", "#AECBFA", "#0B3B7A", "#174EA6"),
    "control": ("#FCE8E6", "#C5221F", "#F5B8B4", "#F5B8B4", "#7A1410", "#C5221F"),
    "test": ("#E6F4EA", "#137333", "#A8DAB5", "#A8DAB5", "#0C5424", "#137333"),
    "uncompleted": ("#FEF7E0", "#B06000", "#F9D28E", "#F9D28E", "#7A4300", "#B06000"),
    "today": ("#F3E8FD", "#7627BB", "#D0B4F2", "#D0B4F2", "#4E1A80", "#7627BB"),
    "week": ("#E0F7FA", "#007B8A", "#80DEEA", "#80DEEA", "#004D57", "#007B8A"),
}


def chip_stylesheet(colors) -> str:
    bg, fg, border, checked_bg, checked_fg, checked_border = colors
    return (
        "QPushButton {"
        f" background-color: {bg};"
        f" color: {fg};"
        f" border: 2px solid {border};"
        " border-radius: 16px;"
        " min-height: 18px;"
        " padding: 8px 18px;"
        " font-weight: 700;"
        " font-size: 13px;"
        " }"
        f" QPushButton:hover {{ background-color: {checked_bg}; }}"
        f" QPushButton:checked {{ background-color: {checked_bg};"
        f" color: {checked_fg}; border: 2px solid {checked_border}; }}"
    )

SUBJECT_CHIP = ("📖", "#D3E3FD", "#041E49")
TEACHER_CHIP = ("👤", "#D5EFE9", "#0F6B5C")
ROOM_CHIP = ("📍", "#FDE7C8", "#9A5B00")
TIME_CHIP = ("🕒", "#F3E8FD", "#7627BB")
FILES_CHIP = ("📎", "#E0F7FA", "#007B8A")

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

DONE_CHIP_STYLE = ("✔", "#E6F4EA", "#137333")


def make_chip(icon: str, text: str, bg: str, fg: str) -> QLabel:
    chip = QLabel(f"{icon}  {text}" if icon else text)
    chip.setWordWrap(True)
    chip.setSizePolicy(
        QSizePolicy.Policy.Maximum,
        QSizePolicy.Policy.Minimum,
    )
    chip.setStyleSheet(
        f"background-color: {bg};"
        f"color: {fg};"
        "border-radius: 10px;"
        "padding: 4px 10px;"
        "font-weight: 700;"
        "font-size: 13px;"
    )
    return chip


class DaySeparator(QWidget):
    def __init__(self, day_text: str, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 14, 0, 6)
        layout.setSpacing(12)

        line_left = QFrame()
        line_left.setFrameShape(QFrame.Shape.HLine)
        line_left.setFrameShadow(QFrame.Shadow.Plain)
        line_left.setStyleSheet(
            "background-color: transparent;"
            "color: #DADCE0;"
            "max-height: 1px;"
            "border: none;"
            "border-top: 1px solid #C7D1DC;"
        )

        label = QLabel(day_text)
        label.setStyleSheet(
            "background-color: transparent;"
            "color: #0B3B7A;"
            "font-weight: 800;"
            "font-size: 15px;"
            "padding: 0 4px;"
        )
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        line_right = QFrame()
        line_right.setFrameShape(QFrame.Shape.HLine)
        line_right.setFrameShadow(QFrame.Shadow.Plain)
        line_right.setStyleSheet(
            "background-color: transparent;"
            "color: #DADCE0;"
            "max-height: 1px;"
            "border: none;"
            "border-top: 1px solid #C7D1DC;"
        )

        layout.addWidget(line_left, 1)
        layout.addWidget(label)
        layout.addWidget(line_right, 1)


class AssignmentCard(QFrame):
    toggled = Signal(int)
    edited = Signal(int)
    deleted = Signal(int)

    def __init__(self, assignment: dict, parent=None):
        super().__init__(parent)

        self._assignment = assignment
        self.setObjectName("assignmentCard")
        self.setCursor(Qt.PointingHandCursor)

        self._build_ui()

    def _build_ui(self):
        a = self._assignment

        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(10)

        # Верхняя строка: тип + дата
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        kind = a["kind"]

        if a["done"]:
            icon, bg, fg = DONE_CHIP_STYLE
            kind_text = "Выполнено"
        else:
            icon, bg, fg = KIND_CHIP_STYLES.get(kind, KIND_CHIP_STYLES["other"])
            kind_text = KIND_LABELS.get(kind, kind)

        top_row.addWidget(make_chip(icon, kind_text, bg, fg))
        top_row.addStretch(1)

        date = QDate.fromString(a["date"], "yyyy-MM-dd")

        if date.isValid():
            day_name = DAY_NAMES.get(date.dayOfWeek(), "")
            date_text = f"{day_name}, {date.toString('dd.MM')}"
        else:
            date_text = a["date"]

        top_row.addWidget(make_chip("📅", date_text, "#F1F3F6", "#3C4043"))

        card_layout.addLayout(top_row)

        # Название
        title_label = QLabel(a["title"] or "Без названия")
        title_label.setObjectName("assignmentTitle")
        title_label.setWordWrap(True)
        card_layout.addWidget(title_label)

        # Описание
        if a["description"]:
            desc_label = QLabel(a["description"])
            desc_label.setObjectName("assignmentDescription")
            desc_label.setWordWrap(True)
            card_layout.addWidget(desc_label)

        # Цветные чипы с иконками
        meta_row = QHBoxLayout()
        meta_row.setSpacing(6)
        meta_row.setContentsMargins(0, 2, 0, 0)

        if a["subject_name"]:
            icon, bg, fg = SUBJECT_CHIP
            meta_row.addWidget(make_chip(icon, a["subject_name"], bg, fg))

        if a.get("lesson_no"):
            icon, bg, fg = TIME_CHIP
            time_text = f"{a['lesson_no']}. {a['start_time']}–{a['end_time']}"
            meta_row.addWidget(make_chip(icon, time_text, bg, fg))

        if a.get("teacher"):
            icon, bg, fg = TEACHER_CHIP
            meta_row.addWidget(make_chip(icon, a["teacher"], bg, fg))

        if a.get("room"):
            icon, bg, fg = ROOM_CHIP
            meta_row.addWidget(make_chip(icon, a["room"], bg, fg))

        if a.get("files_count"):
            icon, bg, fg = FILES_CHIP
            meta_row.addWidget(
                make_chip(icon, f"{a['files_count']} файл(ов)", bg, fg)
            )

        meta_row.addStretch(1)

        card_layout.addLayout(meta_row)

        # Нижний ряд
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(10)

        self.chk_done = QCheckBox("Выполнено")
        self.chk_done.setObjectName("doneCheckbox")
        self.chk_done.setChecked(bool(a["done"]))
        self.chk_done.stateChanged.connect(
            lambda state: self.toggled.emit(a["id"])
        )

        bottom_row.addWidget(self.chk_done)
        bottom_row.addStretch(1)

        edit_btn = QPushButton("Изменить")
        edit_btn.setObjectName("textButton")
        edit_btn.clicked.connect(
            lambda checked=False: self.edited.emit(a["id"])
        )

        delete_btn = QPushButton("Удалить")
        delete_btn.setObjectName("textButtonDanger")
        delete_btn.clicked.connect(
            lambda checked=False: self.deleted.emit(a["id"])
        )

        bottom_row.addWidget(edit_btn)
        bottom_row.addWidget(delete_btn)

        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #E8EDF5;
                color: #0061A4;
                border: 1px solid #8FA6C0;
                border-radius: 16px;
                min-height: 18px;
                padding: 8px 16px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #DDE3ED; }
        """)

        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #FCE8E6;
                color: #D93025;
                border: 1px solid #E0A9A5;
                border-radius: 16px;
                min-height: 18px;
                padding: 8px 16px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #F8D2CF; }
        """)

        card_layout.addLayout(bottom_row)

    def mouseDoubleClickEvent(self, event):
        self.toggled.emit(self._assignment["id"])
        super().mouseDoubleClickEvent(event)


class AssignmentsMaterialTab(QWidget):
    saved = Signal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)

        self.db = db
        self.current_filter = "all"
        self.anchor_date = QDate.currentDate()

        self._build_ui()
        self.update_chips()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(14)

        # ===== Верхняя панель периода =====
        top = QHBoxLayout()
        top.setSpacing(8)

        self.btn_prev = QPushButton("←")
        self.btn_prev.setObjectName("toolbarButton")
        self.btn_prev.setFixedWidth(44)

        self.btn_next = QPushButton("→")
        self.btn_next.setObjectName("toolbarButton")
        self.btn_next.setFixedWidth(44)

        self.btn_current_week = QPushButton("Текущая неделя")
        self.btn_current_week.setObjectName("toolbarButton")

        self.date_edit = QDateEdit(self.anchor_date)
        self.date_edit.installEventFilter(self)
        self.date_edit.setObjectName("toolbarDate")
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_edit.setFixedWidth(200)

        self.lbl_week = QLabel("")
        self.lbl_week.setObjectName("weekTitle")

        self.lbl_parity = QLabel("")
        self.lbl_parity.setObjectName("weekSubtitle")

        top.addWidget(self.btn_prev)
        top.addWidget(self.btn_next)
        top.addWidget(self.btn_current_week)
        top.addWidget(QLabel("Дата:"))
        top.addWidget(self.date_edit)
        top.addStretch(1)
        top.addWidget(self.lbl_week)
        top.addWidget(self.lbl_parity)

        layout.addLayout(top)

        # ===== Чипы фильтров =====
        chips_row = QHBoxLayout()
        chips_row.setSpacing(8)

        self.chip_buttons = []

        for filter_id, label, icon in FILTER_CHIPS:
            chip = QPushButton(f"{icon}  {label}")
            chip.setObjectName(f"filterChip_{filter_id}")
            chip.setProperty("filterId", filter_id)
            chip.setCheckable(True)
            chip.setCursor(Qt.PointingHandCursor)

            # Локальный стиль — скругление применяется гарантированно
            chip.setStyleSheet(
                chip_stylesheet(CHIP_STYLE_TEMPLATES[filter_id])
            )

            chip.clicked.connect(
                lambda checked=False, fid=filter_id: self.set_filter(fid)
            )

            chips_row.addWidget(chip)
            self.chip_buttons.append(chip)

        chips_row.addStretch(1)

        layout.addLayout(chips_row)

        # ===== Прокрутка =====
        self.scroll = QScrollArea()
        self.scroll.setObjectName("assignmentsScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("assignmentsScrollContent")

        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 12, 0)
        self.scroll_layout.setSpacing(10)

        self.scroll.setWidget(self.scroll_content)

        layout.addWidget(self.scroll, 1)

        # ===== Низ: кнопка добавления =====
        bottom = QHBoxLayout()
        bottom.addStretch(1)

        self.btn_add = QPushButton("+ Добавить работу")
        self.btn_add.setObjectName("primaryButton")
        self.btn_add.setStyleSheet("""
            QPushButton {
                background-color: #D3E3FD;
                color: #0B3B7A;
                border: 2px solid #7FA7D9;
                border-radius: 24px;
                padding: 10px 24px;
                font-size: 16px;
                font-weight: 800;
                min-height: 44px;
            }
            QPushButton:hover { background-color: #C9DCF9; }
            QPushButton:pressed { background-color: #BBD3F7; }
        """)
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.clicked.connect(
            lambda checked=False: self.add_assignment()
        )

        bottom.addWidget(self.btn_add)

        layout.addLayout(bottom)

        # ===== Сигналы =====
        self.btn_prev.clicked.connect(
            lambda checked=False: self.shift_week(-7)
        )
        self.btn_next.clicked.connect(
            lambda checked=False: self.shift_week(7)
        )
        self.btn_current_week.clicked.connect(
            lambda checked=False: self.date_edit.setDate(QDate.currentDate())
        )
        self.date_edit.dateChanged.connect(
            lambda d: self.on_anchor_date_changed(d)
        )

    # ===== Период =====

    def shift_week(self, days: int):
        self.date_edit.setDate(self.date_edit.date().addDays(days))

    def on_anchor_date_changed(self, date: QDate):
        self.anchor_date = date
        self.refresh()

    # ===== Фильтры =====

    def set_filter(self, filter_id: str):
        self.current_filter = filter_id
        self.update_chips()
        self.refresh()

    def update_chips(self):
        for chip in self.chip_buttons:
            chip.setChecked(
                chip.property("filterId") == self.current_filter
            )

    # ===== Отрисовка =====

    def refresh(self):
        monday = self.anchor_date.addDays(
            -(self.anchor_date.dayOfWeek() - 1)
        )
        sunday = monday.addDays(6)

        self.lbl_week.setText(
            f"{monday.toString('dd.MM.yyyy')} — {sunday.toString('dd.MM.yyyy')}"
        )

        parity = parity_for_date(self.db, monday)

        if parity == "numerator":
            self.lbl_parity.setText("Числитель")
        else:
            self.lbl_parity.setText("Знаменатель")

        self.clear_content()

        assignments = self.get_filtered_assignments()

        if not assignments:
            empty_label = QLabel("Нет заданий для выбранного фильтра")
            empty_label.setObjectName("emptyLabel")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.scroll_layout.addWidget(empty_label)
        else:
            self.build_grouped_list(assignments)

        self.scroll_layout.addStretch(1)

    def clear_content(self):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def build_grouped_list(self, assignments):
        current_date_iso = None

        for a in assignments:
            if a["date"] != current_date_iso:
                current_date_iso = a["date"]

                date = QDate.fromString(a["date"], "yyyy-MM-dd")

                if date.isValid():
                    day_name = DAY_NAMES.get(date.dayOfWeek(), "")
                    sep_text = f"{day_name}, {date.toString('dd.MM.yyyy')}"
                else:
                    sep_text = a["date"]

                self.scroll_layout.addWidget(DaySeparator(sep_text))

            card = AssignmentCard(dict(a))
            card.toggled.connect(self.toggle_assignment)
            card.edited.connect(self.edit_assignment)
            card.deleted.connect(self.delete_assignment)

            self.scroll_layout.addWidget(card)

    # ===== Запрос с фильтром по выбранной неделе =====

    def get_filtered_assignments(self):
        today_iso = QDate.currentDate().toString("yyyy-MM-dd")

        monday = self.anchor_date.addDays(
            -(self.anchor_date.dayOfWeek() - 1)
        )
        sunday = monday.addDays(6)

        week_start = monday.toString("yyyy-MM-dd")
        week_end = sunday.toString("yyyy-MM-dd")

        base_query = """
            SELECT
                a.*,
                sub.name AS subject_name,
                s.lesson_no,
                s.start_time,
                s.end_time,
                s.teacher,
                s.room,
                (
                    SELECT COUNT(*)
                    FROM assignment_files f
                    WHERE f.assignment_id = a.id
                ) AS files_count
            FROM assignments a
            JOIN subjects sub ON sub.id = a.subject_id
            LEFT JOIN schedule_slots s ON s.id = a.slot_id
        """

        where = ["a.date BETWEEN ? AND ?"]
        params = [week_start, week_end]
        
        sub_rows = self.db.query(
            "SELECT my_subgroup FROM settings WHERE id = 1"
        )
        my_sub = int(sub_rows[0]["my_subgroup"] or 0) if sub_rows else 0

        if my_sub:
            where.append(
                "(s.id IS NULL OR s.subgroup = 0 OR s.subgroup = ?)"
            )
            params.append(my_sub)

        if self.current_filter == "today":
            where.append("a.date = ?")
            params.append(today_iso)
        elif self.current_filter == "homework":
            where.append("a.kind = 'homework'")
        elif self.current_filter == "control":
            where.append("a.kind = 'control'")
        elif self.current_filter == "test":
            where.append("a.kind = 'test'")
        elif self.current_filter == "uncompleted":
            where.append("a.done = 0")

        query = (
            base_query
            + " WHERE "
            + " AND ".join(where)
            + " ORDER BY a.date, s.lesson_no, a.id"
        )

        return self.db.query(query, tuple(params))

    # ===== Действия =====

    def add_assignment(self):
        dialog = AssignmentDialog(
            self.db,
            assignment_id=None,
            default_date=QDate.currentDate(),
            default_slot_id=None,
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

    def eventFilter(self, obj, event):
        if obj is self.date_edit and event.type() == QEvent.Type.MouseButtonPress:
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
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#001D35"))
        pal.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))

        cal.setPalette(pal)

        view = cal.findChild(QTableView)

        if view is not None:
            view.setPalette(pal)
            view.verticalHeader().setDefaultSectionSize(38)

            hh = view.horizontalHeader()
            hh.setPalette(pal)

    # ===== Совместимость =====

    def reload_subjects(self):
        pass

    def load(self):
        self.refresh()
