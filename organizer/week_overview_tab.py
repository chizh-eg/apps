from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
    QScrollArea,
    QMenu,
    QMessageBox,
    QDateEdit,
)
from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QCursor

from organizer_db import Database
from assignments_tab import AssignmentDialog, parity_for_date, KIND_LABELS


DAY_NAMES = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]


class WeekOverviewTab(QWidget):
    """
    Material You-страница недельного обзора.

    Вместо таблицы:
    - карточки дней;
    - карточки пар;
    - задания внутри карточек.
    """

    saved = Signal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)

        self.db = db
        self.selected_date = QDate.currentDate()

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(14)

        # Верхняя панель
        top = QHBoxLayout()
        top.setSpacing(8)

        self.btn_prev = QPushButton("←")
        self.btn_prev.setObjectName("iconButton")
        self.btn_prev.setFixedWidth(44)

        self.btn_next = QPushButton("→")
        self.btn_next.setObjectName("iconButton")
        self.btn_next.setFixedWidth(44)

        self.btn_today = QPushButton("Сегодня")
        self.btn_today.setObjectName("iconButton")

        self.date_edit = QDateEdit(self.selected_date)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_edit.setFixedWidth(150)

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

        # Прокручиваемая область с карточками дней
        self.scroll = QScrollArea()
        self.scroll.setObjectName("weekScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("weekScrollContent")

        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 12, 0)
        self.scroll_layout.setSpacing(14)

        self.scroll.setWidget(self.scroll_content)

        layout.addWidget(self.scroll, 1)

        # Сигналы
        self.btn_prev.clicked.connect(lambda checked=False: self.shift_days(-7))
        self.btn_next.clicked.connect(lambda checked=False: self.shift_days(7))
        self.btn_today.clicked.connect(
            lambda checked=False: self.date_edit.setDate(QDate.currentDate())
        )

        self.date_edit.dateChanged.connect(
            lambda d: self.on_date_changed(d)
        )

    def refresh(self):
        monday = self.selected_date.addDays(
            -(self.selected_date.dayOfWeek() - 1)
        )
        sunday = monday.addDays(6)

        self.lbl_week.setText(
            f"{monday.toString('dd.MM.yyyy')} — {sunday.toString('dd.MM.yyyy')}"
        )

        week_parity = parity_for_date(self.db, monday)

        if week_parity == "numerator":
            self.lbl_parity.setText("Числитель")
        else:
            self.lbl_parity.setText("Знаменатель")

        self.build_days(monday)

    def on_date_changed(self, date: QDate):
        self.selected_date = date
        self.refresh()

    def shift_days(self, days: int):
        self.date_edit.setDate(self.date_edit.date().addDays(days))

    def clear_content(self):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

    def build_days(self, monday: QDate):
        self.clear_content()

        for i in range(7):
            date = monday.addDays(i)
            day_card = self.create_day_card(date, i)
            self.scroll_layout.addWidget(day_card)

        self.scroll_layout.addStretch(1)

    def create_day_card(self, date: QDate, day_index: int) -> QFrame:
        card = QFrame()
        card.setObjectName("dayCard")

        if date == QDate.currentDate():
            card.setProperty("today", "true")
        else:
            card.setProperty("today", "false")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(12)

        parity = parity_for_date(self.db, date)

        header = QHBoxLayout()

        title = QLabel(f"{DAY_NAMES[day_index]}, {date.toString('dd.MM')}")
        title.setObjectName("dayTitle")

        subtitle = QLabel(
            "Числитель" if parity == "numerator" else "Знаменатель"
        )
        subtitle.setObjectName("daySubtitle")

        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(subtitle)

        card_layout.addLayout(header)

        date_iso = date.toString("yyyy-MM-dd")

        slots = self.get_slots_for_date(date, parity)

        if slots:
            for slot in slots:
                slot_card = self.create_slot_card(date, slot, parity)
                card_layout.addWidget(slot_card)
        else:
            empty_label = QLabel("Нет пар")
            empty_label.setObjectName("emptyLabel")
            card_layout.addWidget(empty_label)

        # Задания без привязки к паре
        no_slot_assignments = self.db.query(
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
              AND a.slot_id IS NULL
            ORDER BY a.kind, a.title
            """,
            (date_iso,),
        )

        if no_slot_assignments:
            extra_card = self.create_extra_card(date, no_slot_assignments)
            card_layout.addWidget(extra_card)

        add_btn = QPushButton("Добавить задание без пары")
        add_btn.setObjectName("textButton")
        add_btn.clicked.connect(
            lambda checked=False, d=date_iso: self.add_assignment(d, None)
        )

        card_layout.addWidget(add_btn)

        return card

    def get_slots_for_date(self, date: QDate, parity: str):
        slots = list(
            self.db.query(
                """
                SELECT
                    s.*,
                    sub.name AS subject_name
                FROM schedule_slots s
                JOIN subjects sub ON sub.id = s.subject_id
                WHERE s.weekday = ?
                  AND (s.parity = 'all' OR s.parity = ?)
                ORDER BY s.lesson_no, s.start_time
                """,
                (date.dayOfWeek(), parity),
            )
        )

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

        existing_ids = {slot["id"] for slot in slots}

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
                slots.append(extra_slots[0])
                existing_ids.add(slot_id)

        slots.sort(
            key=lambda s: (
                s["lesson_no"],
                s["start_time"],
                s["end_time"],
            )
        )

        return slots

    def create_slot_card(
        self,
        date: QDate,
        slot,
        parity: str,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("slotCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(8)

        time_label = QLabel(
            f"{slot['lesson_no']}. {slot['start_time']}–{slot['end_time']}"
        )
        time_label.setObjectName("slotTime")

        subject_label = QLabel(slot["subject_name"])
        subject_label.setObjectName("slotSubject")

        card_layout.addWidget(time_label)
        card_layout.addWidget(subject_label)

        meta_parts = []

        if slot["teacher"]:
            meta_parts.append(slot["teacher"])

        if slot["room"]:
            meta_parts.append(slot["room"])

        if slot["weekday"] != date.dayOfWeek():
            meta_parts.append("вне обычного дня")

        if slot["parity"] != "all" and slot["parity"] != parity:
            meta_parts.append("неделя не совпадает")

        if meta_parts:
            meta_label = QLabel(" · ".join(meta_parts))
            meta_label.setObjectName("slotMeta")
            card_layout.addWidget(meta_label)

        date_iso = date.toString("yyyy-MM-dd")

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
            assignment_button = self.create_assignment_button(assignment)
            card_layout.addWidget(assignment_button)

        add_btn = QPushButton("Добавить задание")
        add_btn.setObjectName("textButton")
        add_btn.clicked.connect(
            lambda checked=False, d=date_iso, s=slot["id"]:
                self.add_assignment(d, s)
        )

        card_layout.addWidget(add_btn)

        return card

    def create_extra_card(self, date: QDate, assignments) -> QFrame:
        card = QFrame()
        card.setObjectName("slotCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(8)

        title = QLabel("Дополнительно")
        title.setObjectName("slotSubject")

        subtitle = QLabel("Без привязки к паре")
        subtitle.setObjectName("slotMeta")

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)

        for assignment in assignments:
            assignment_button = self.create_assignment_button(assignment)
            card_layout.addWidget(assignment_button)

        date_iso = date.toString("yyyy-MM-dd")

        add_btn = QPushButton("Добавить задание")
        add_btn.setObjectName("textButton")
        add_btn.clicked.connect(
            lambda checked=False, d=date_iso: self.add_assignment(d, None)
        )

        card_layout.addWidget(add_btn)

        return card

    def create_assignment_button(self, assignment) -> QPushButton:
        mark = "✔" if assignment["done"] else "○"

        kind_label = KIND_LABELS.get(
            assignment["kind"],
            assignment["kind"],
        )

        title = assignment["title"] or kind_label

        files_text = ""

        if assignment["files_count"]:
            files_text = f"  📎{assignment['files_count']}"

        text = f"{mark} {kind_label}: {title}{files_text}"

        button = QPushButton(text)
        button.setObjectName("assignmentItem")
        button.setCursor(Qt.PointingHandCursor)

        if assignment["description"]:
            button.setToolTip(assignment["description"])

        assignment_id = assignment["id"]

        button.clicked.connect(
            lambda checked=False, aid=assignment_id:
                self.edit_assignment(aid)
        )

        button.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )

        button.customContextMenuRequested.connect(
            lambda pos, b=button, aid=assignment_id:
                self.show_assignment_menu(pos, b, aid)
        )

        return button

    def show_assignment_menu(self, pos, button: QPushButton, assignment_id: int):
        menu = QMenu(self)

        action_edit = menu.addAction("Редактировать")
        action_edit.triggered.connect(
            lambda checked=False, aid=assignment_id:
                self.edit_assignment(aid)
        )

        action_toggle = menu.addAction("Выполнено / не выполнено")
        action_toggle.triggered.connect(
            lambda checked=False, aid=assignment_id:
                self.toggle_assignment(aid)
        )

        action_delete = menu.addAction("Удалить")
        action_delete.triggered.connect(
            lambda checked=False, aid=assignment_id:
                self.delete_assignment(aid)
        )

        menu.exec(button.mapToGlobal(pos))

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
