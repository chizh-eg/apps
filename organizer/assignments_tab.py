from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QDialog,
    QFormLayout,
    QLineEdit,
    QDateEdit,
    QCheckBox,
    QPlainTextEdit,
    QListWidget,
    QListWidgetItem,
    QDialogButtonBox,
    QMessageBox,
    QFileDialog,
    QAbstractItemView,
    QLabel,
)
from PySide6.QtCore import Qt, QDate, Signal

from organizer_db import Database


ASSIGNMENT_KINDS = [
    ("homework", "Домашняя работа"),
    ("control", "Контрольная"),
    ("independent", "Самостоятельная"),
    ("test", "Тест"),
    ("presentation", "Выступление"),
    ("exam", "Экзамен"),
    ("credit", "Зачёт"),
    ("event", "Мероприятие"),
    ("other", "Другое"),
]

KIND_LABELS = dict(ASSIGNMENT_KINDS)


def make_item(text):
    item = QTableWidgetItem("" if text is None else str(text))
    item.setFlags(
        Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
    )
    return item


def parity_for_date(db: Database, date: QDate) -> str:
    """
    Возвращает 'numerator' или 'denominator' для конкретной даты.

    Если в settings не задана опорная дата числителя,
    временно считаем все недели числителем.
    """
    rows = db.query(
        "SELECT numerator_reference FROM settings WHERE id = 1"
    )

    ref_str = None

    if rows and rows[0]["numerator_reference"]:
        ref_str = rows[0]["numerator_reference"]

    if ref_str:
        ref = QDate.fromString(ref_str, "yyyy-MM-dd")

        if ref.isValid():
            monday = date.addDays(-(date.dayOfWeek() - 1))
            ref_monday = ref.addDays(-(ref.dayOfWeek() - 1))

            days = ref_monday.daysTo(monday)
            weeks = days // 7

            return "numerator" if weeks % 2 == 0 else "denominator"

    return "numerator"


class AssignmentDialog(QDialog):
    """
    Диалог добавления/редактирования задания или мероприятия.
    """

    saved = Signal()

    def __init__(
        self,
        db: Database,
        assignment_id=None,
        default_date=None,
        default_slot_id=None,
        parent=None,
    ):
        super().__init__(parent)

        self.db = db
        self.assignment_id = assignment_id

        self.setWindowTitle("Задание / мероприятие")
        self.resize(680, 560)

        self._build_ui()
        self.load_kinds()
        self.load_subjects()

        if default_date is not None and self.assignment_id is None:
            self.date_edit.setDate(default_date)

        if self.assignment_id is not None:
            self.load_assignment()
        elif default_slot_id is not None:
            self.setup_from_slot(default_slot_id)
        else:
            self.load_slots()

        # Подключаем сигналы после первичной загрузки,
        # чтобы не было лишних перезагрузок.
        self.date_edit.dateChanged.connect(lambda d: self.load_slots())
        self.cmb_subject.currentIndexChanged.connect(
            lambda i: self.load_slots()
        )

    def _build_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        # Дата
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")

        form.addRow("Дата", self.date_edit)

        # Предмет
        self.cmb_subject = QComboBox()
        self.btn_add_subject = QPushButton("+")
        self.btn_add_subject.setFixedWidth(32)
        self.btn_add_subject.setToolTip("Добавить новый предмет в базу")

        subject_container = QWidget()
        subject_row = QHBoxLayout(subject_container)
        subject_row.setContentsMargins(0, 0, 0, 0)
        subject_row.addWidget(self.cmb_subject, 1)
        subject_row.addWidget(self.btn_add_subject)

        form.addRow("Предмет", subject_container)

        # Пара
        self.cmb_slot = QComboBox()
        form.addRow("Пара", self.cmb_slot)

        # Тип задания
        self.cmb_kind = QComboBox()
        form.addRow("Тип", self.cmb_kind)

        # Название
        self.edt_title = QLineEdit()
        self.edt_title.setPlaceholderText(
            "Например: Глава 3, задачи 12–18"
        )
        form.addRow("Название", self.edt_title)

        # Описание
        self.txt_description = QPlainTextEdit()
        self.txt_description.setPlaceholderText(
            "Описание задания, ссылки, примечания..."
        )
        form.addRow("Описание", self.txt_description)

        # Выполнено
        self.chk_done = QCheckBox("Выполнено")
        form.addRow("", self.chk_done)

        layout.addLayout(form)

        # Файлы
        layout.addWidget(QLabel("Файлы:"))

        self.list_files = QListWidget()
        self.list_files.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )

        self.btn_add_file = QPushButton("Добавить файл")
        self.btn_remove_file = QPushButton("Удалить файл")

        file_buttons = QHBoxLayout()
        file_buttons.addWidget(self.btn_add_file)
        file_buttons.addWidget(self.btn_remove_file)
        file_buttons.addStretch(1)

        layout.addWidget(self.list_files)
        layout.addLayout(file_buttons)

        # OK / Cancel
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )

        layout.addWidget(self.button_box)

        self.btn_add_subject.clicked.connect(
            lambda checked=False: self.add_subject()
        )
        self.btn_add_file.clicked.connect(
            lambda checked=False: self.add_files()
        )
        self.btn_remove_file.clicked.connect(
            lambda checked=False: self.remove_file()
        )

        self.button_box.accepted.connect(self.try_accept)
        self.button_box.rejected.connect(self.reject)

    def load_kinds(self):
        self.cmb_kind.clear()

        for kind_id, label in ASSIGNMENT_KINDS:
            self.cmb_kind.addItem(label, kind_id)

    def load_subjects(self, select_id=None):
        self.cmb_subject.clear()

        rows = self.db.query(
            "SELECT id, name FROM subjects ORDER BY name"
        )

        for row in rows:
            self.cmb_subject.addItem(row["name"], row["id"])

        if select_id is not None:
            index = self.cmb_subject.findData(select_id)
            if index >= 0:
                self.cmb_subject.setCurrentIndex(index)
        else:
            if self.cmb_subject.count() > 0:
                self.cmb_subject.setCurrentIndex(0)

    def add_subject(self):
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(
            self,
            "Новый предмет",
            "Название предмета:",
        )

        if not ok:
            return

        name = name.strip()

        if not name:
            return

        self.db.execute(
            """
            INSERT OR IGNORE INTO subjects (name, folder_name)
            VALUES (?, ?)
            """,
            (name, name),
        )

        rows = self.db.query(
            "SELECT id FROM subjects WHERE name = ?",
            (name,),
        )

        select_id = rows[0]["id"] if rows else None
        self.load_subjects(select_id=select_id)

    def setup_from_slot(self, slot_id):
        rows = self.db.query(
            "SELECT subject_id FROM schedule_slots WHERE id = ?",
            (slot_id,),
        )

        if rows:
            self.load_subjects(select_id=rows[0]["subject_id"])
            self.load_slots(
                select_slot_id=slot_id,
                include_slot_id=slot_id,
            )
        else:
            self.load_slots()

    def slot_label(self, row):
        label = f"{row['lesson_no']}. {row['start_time']}–{row['end_time']}"

        if row["teacher"]:
            label += f" — {row['teacher']}"

        if row["room"]:
            label += f", {row['room']}"

        if row["parity"] == "numerator":
            label += " (числитель)"
        elif row["parity"] == "denominator":
            label += " (знаменатель)"

        return label

    def load_slots(self, select_slot_id=None, include_slot_id=None):
        self.cmb_slot.blockSignals(True)
        self.cmb_slot.clear()

        # 0 означает "без привязки к паре"
        self.cmb_slot.addItem("Без привязки к паре", 0)

        subject_id = self.cmb_subject.currentData()

        if subject_id:
            date = self.date_edit.date()
            weekday = date.dayOfWeek()
            parity = parity_for_date(self.db, date)

            rows = self.db.query(
                """
                SELECT *
                FROM schedule_slots
                WHERE subject_id = ?
                  AND weekday = ?
                  AND (parity = 'all' OR parity = ?)
                ORDER BY lesson_no, start_time
                """,
                (subject_id, weekday, parity),
            )

            added_ids = set()

            for row in rows:
                self.cmb_slot.addItem(self.slot_label(row), row["id"])
                added_ids.add(row["id"])

            if include_slot_id is not None and include_slot_id not in added_ids:
                extra = self.db.query(
                    "SELECT * FROM schedule_slots WHERE id = ?",
                    (include_slot_id,),
                )

                if extra:
                    self.cmb_slot.addItem(
                        self.slot_label(extra[0]) + " (вне даты)",
                        extra[0]["id"],
                    )

        if select_slot_id is not None:
            index = self.cmb_slot.findData(select_slot_id)
            if index >= 0:
                self.cmb_slot.setCurrentIndex(index)
            else:
                self.cmb_slot.setCurrentIndex(0)
        else:
            self.cmb_slot.setCurrentIndex(0)

        self.cmb_slot.blockSignals(False)

    def load_assignment(self):
        rows = self.db.query(
            "SELECT * FROM assignments WHERE id = ?",
            (self.assignment_id,),
        )

        if not rows:
            return

        assignment = rows[0]

        date = QDate.fromString(assignment["date"], "yyyy-MM-dd")

        if date.isValid():
            self.date_edit.setDate(date)

        self.load_subjects(select_id=assignment["subject_id"])

        kind_index = self.cmb_kind.findData(assignment["kind"])
        if kind_index >= 0:
            self.cmb_kind.setCurrentIndex(kind_index)

        self.edt_title.setText(assignment["title"] or "")
        self.txt_description.setPlainText(assignment["description"] or "")
        self.chk_done.setChecked(bool(assignment["done"]))

        self.load_slots(
            select_slot_id=assignment["slot_id"],
            include_slot_id=assignment["slot_id"],
        )

        self.load_files()

    def load_files(self):
        self.list_files.clear()

        if self.assignment_id is None:
            return

        rows = self.db.query(
            "SELECT file_path FROM assignment_files WHERE assignment_id = ?",
            (self.assignment_id,),
        )

        for row in rows:
            self.add_file_item(row["file_path"])

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выбрать файлы",
            str(Path.home()),
        )

        for file_path in files:
            self.add_file_item(file_path)

    def add_file_item(self, file_path: str):
        file_path = str(file_path)

        for i in range(self.list_files.count()):
            item = self.list_files.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == file_path:
                return

        item = QListWidgetItem(Path(file_path).name)
        item.setData(Qt.ItemDataRole.UserRole, file_path)
        item.setToolTip(file_path)

        self.list_files.addItem(item)

    def remove_file(self):
        for item in self.list_files.selectedItems():
            self.list_files.takeItem(self.list_files.row(item))

    def try_accept(self):
        subject_id = self.cmb_subject.currentData()

        if not subject_id:
            QMessageBox.warning(
                self,
                "Нет предмета",
                "Сначала выбери или добавь предмет.",
            )
            return

        slot_data = self.cmb_slot.currentData()
        slot_id = slot_data if slot_data else None

        kind = self.cmb_kind.currentData() or "homework"
        title = self.edt_title.text().strip()
        description = self.txt_description.toPlainText().strip()
        done = 1 if self.chk_done.isChecked() else 0
        date_iso = self.date_edit.date().toString("yyyy-MM-dd")

        if self.assignment_id is None:
            cur = self.db.execute(
                """
                INSERT INTO assignments (
                    date,
                    subject_id,
                    slot_id,
                    kind,
                    title,
                    description,
                    done
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    date_iso,
                    subject_id,
                    slot_id,
                    kind,
                    title,
                    description,
                    done,
                ),
            )

            self.assignment_id = cur.lastrowid
        else:
            self.db.execute(
                """
                UPDATE assignments
                SET
                    date = ?,
                    subject_id = ?,
                    slot_id = ?,
                    kind = ?,
                    title = ?,
                    description = ?,
                    done = ?
                WHERE id = ?
                """,
                (
                    date_iso,
                    subject_id,
                    slot_id,
                    kind,
                    title,
                    description,
                    done,
                    self.assignment_id,
                ),
            )

        # Пересохраняем файлы.
        self.db.execute(
            "DELETE FROM assignment_files WHERE assignment_id = ?",
            (self.assignment_id,),
        )

        for i in range(self.list_files.count()):
            item = self.list_files.item(i)
            file_path = item.data(Qt.ItemDataRole.UserRole)

            self.db.execute(
                """
                INSERT INTO assignment_files (
                    assignment_id,
                    file_path,
                    note
                )
                VALUES (?, ?, ?)
                """,
                (self.assignment_id, file_path, ""),
            )

        self.saved.emit()
        self.accept()


class AssignmentsTab(QWidget):
    """
    Вкладка со списком заданий и мероприятий.
    """

    saved = Signal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)

        self.db = db

        self._build_ui()
        self.reload_subjects()
        self.load()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Первый ряд фильтров: период
        filters_1 = QHBoxLayout()

        today = QDate.currentDate()

        self.date_start = QDateEdit(today.addDays(-30))
        self.date_start.setCalendarPopup(True)
        self.date_start.setDisplayFormat("dd.MM.yyyy")

        self.date_end = QDateEdit(today.addDays(30))
        self.date_end.setCalendarPopup(True)
        self.date_end.setDisplayFormat("dd.MM.yyyy")

        filters_1.addWidget(QLabel("Период с"))
        filters_1.addWidget(self.date_start)
        filters_1.addWidget(QLabel("по"))
        filters_1.addWidget(self.date_end)
        filters_1.addStretch(1)

        layout.addLayout(filters_1)

        # Второй ряд фильтров и кнопки
        filters_2 = QHBoxLayout()

        self.cmb_subject_filter = QComboBox()
        self.cmb_kind_filter = QComboBox()

        self.btn_reload = QPushButton("Обновить")
        self.btn_add = QPushButton("Добавить задание")
        self.btn_edit = QPushButton("Редактировать")
        self.btn_delete = QPushButton("Удалить")
        self.btn_toggle_done = QPushButton("Выполнено / не выполнено")

        self.cmb_kind_filter.addItem("Все типы", "all")

        for kind_id, label in ASSIGNMENT_KINDS:
            self.cmb_kind_filter.addItem(label, kind_id)

        filters_2.addWidget(QLabel("Предмет:"))
        filters_2.addWidget(self.cmb_subject_filter)

        filters_2.addWidget(QLabel("Тип:"))
        filters_2.addWidget(self.cmb_kind_filter)

        filters_2.addStretch(1)

        filters_2.addWidget(self.btn_reload)
        filters_2.addWidget(self.btn_add)
        filters_2.addWidget(self.btn_edit)
        filters_2.addWidget(self.btn_delete)
        filters_2.addWidget(self.btn_toggle_done)

        layout.addLayout(filters_2)

        # Таблица заданий
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            [
                "Дата",
                "Предмет",
                "Пара",
                "Тип",
                "Название",
                "Файлы",
                "Выполнено",
            ]
        )

        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)

        layout.addWidget(self.table)

        # Сигналы
        self.date_start.dateChanged.connect(lambda d: self.load())
        self.date_end.dateChanged.connect(lambda d: self.load())

        self.cmb_subject_filter.currentIndexChanged.connect(
            lambda i: self.load()
        )
        self.cmb_kind_filter.currentIndexChanged.connect(
            lambda i: self.load()
        )

        self.btn_reload.clicked.connect(lambda checked=False: self.load())
        self.btn_add.clicked.connect(
            lambda checked=False: self.add_assignment()
        )
        self.btn_edit.clicked.connect(
            lambda checked=False: self.edit_assignment()
        )
        self.btn_delete.clicked.connect(
            lambda checked=False: self.delete_assignment()
        )
        self.btn_toggle_done.clicked.connect(
            lambda checked=False: self.toggle_done()
        )

        self.table.doubleClicked.connect(
            lambda index: self.edit_assignment()
        )

    def reload_subjects(self):
        current = self.cmb_subject_filter.currentData()

        self.cmb_subject_filter.clear()
        self.cmb_subject_filter.addItem("Все предметы", 0)

        rows = self.db.query(
            "SELECT id, name FROM subjects ORDER BY name"
        )

        for row in rows:
            self.cmb_subject_filter.addItem(row["name"], row["id"])

        if current:
            index = self.cmb_subject_filter.findData(current)
            if index >= 0:
                self.cmb_subject_filter.setCurrentIndex(index)

    def load(self):
        start = self.date_start.date()
        end = self.date_end.date()

        if start > end:
            start, end = end, start

        where_parts = ["a.date BETWEEN ? AND ?"]
        params = [
            start.toString("yyyy-MM-dd"),
            end.toString("yyyy-MM-dd"),
        ]

        subject_id = self.cmb_subject_filter.currentData()

        if subject_id:
            where_parts.append("a.subject_id = ?")
            params.append(subject_id)

        kind = self.cmb_kind_filter.currentData()

        if kind and kind != "all":
            where_parts.append("a.kind = ?")
            params.append(kind)

        sql = f"""
            SELECT
                a.id,
                a.date,
                a.kind,
                a.title,
                a.description,
                a.done,
                sub.name AS subject_name,
                s.lesson_no,
                s.start_time,
                s.end_time,
                (
                    SELECT COUNT(*)
                    FROM assignment_files f
                    WHERE f.assignment_id = a.id
                ) AS files_count
            FROM assignments a
            JOIN subjects sub ON sub.id = a.subject_id
            LEFT JOIN schedule_slots s ON s.id = a.slot_id
            WHERE {' AND '.join(where_parts)}
            ORDER BY a.date, s.lesson_no, a.id
        """

        rows = self.db.query(sql, tuple(params))

        self.table.clear()
        self.table.setRowCount(len(rows))
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            [
                "Дата",
                "Предмет",
                "Пара",
                "Тип",
                "Название",
                "Файлы",
                "Выполнено",
            ]
        )

        for row_index, row in enumerate(rows):
            date = QDate.fromString(row["date"], "yyyy-MM-dd")
            date_text = date.toString("dd.MM.yyyy")

            if row["lesson_no"] is None:
                slot_text = "—"
            else:
                slot_text = (
                    f"{row['lesson_no']}. "
                    f"{row['start_time']}–{row['end_time']}"
                )

            kind_text = KIND_LABELS.get(row["kind"], row["kind"])
            title_text = row["title"] or kind_text
            done_text = "Да" if row["done"] else "Нет"

            id_item = make_item(date_text)
            id_item.setData(Qt.ItemDataRole.UserRole, row["id"])

            tooltip_parts = []

            if row["description"]:
                tooltip_parts.append(row["description"])

            if row["files_count"]:
                tooltip_parts.append(f"Файлов: {row['files_count']}")

            if tooltip_parts:
                id_item.setToolTip("\n\n".join(tooltip_parts))

            subject_item = make_item(row["subject_name"])
            slot_item = make_item(slot_text)
            kind_item = make_item(kind_text)

            title_item = make_item(title_text)
            if tooltip_parts:
                title_item.setToolTip("\n\n".join(tooltip_parts))

            files_item = make_item(row["files_count"])
            done_item = make_item(done_text)

            self.table.setItem(row_index, 0, id_item)
            self.table.setItem(row_index, 1, subject_item)
            self.table.setItem(row_index, 2, slot_item)
            self.table.setItem(row_index, 3, kind_item)
            self.table.setItem(row_index, 4, title_item)
            self.table.setItem(row_index, 5, files_item)
            self.table.setItem(row_index, 6, done_item)

        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, 110)
        self.table.setColumnWidth(1, 180)
        self.table.setColumnWidth(2, 140)
        self.table.setColumnWidth(3, 150)
        self.table.setColumnWidth(4, 260)

    def selected_assignment_id(self):
        row = self.table.currentRow()

        if row < 0:
            return None

        item = self.table.item(row, 0)

        if not item:
            return None

        return item.data(Qt.ItemDataRole.UserRole)

    def add_assignment(self):
        dialog = AssignmentDialog(
            self.db,
            assignment_id=None,
            default_date=QDate.currentDate(),
            default_slot_id=None,
            parent=self,
        )

        if dialog.exec():
            self.load()
            self.saved.emit()

    def edit_assignment(self):
        assignment_id = self.selected_assignment_id()

        if assignment_id is None:
            QMessageBox.information(
                self,
                "Не выбрано задание",
                "Сначала выбери задание в таблице.",
            )
            return

        dialog = AssignmentDialog(
            self.db,
            assignment_id=assignment_id,
            parent=self,
        )

        if dialog.exec():
            self.load()
            self.saved.emit()

    def delete_assignment(self):
        assignment_id = self.selected_assignment_id()

        if assignment_id is None:
            QMessageBox.information(
                self,
                "Не выбрано задание",
                "Сначала выбери задание в таблице.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Удаление задания",
            "Удалить выбранное задание вместе с привязанными файлами?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.db.execute(
            "DELETE FROM assignments WHERE id = ?",
            (assignment_id,),
        )

        self.load()
        self.saved.emit()

    def toggle_done(self):
        assignment_id = self.selected_assignment_id()

        if assignment_id is None:
            QMessageBox.information(
                self,
                "Не выбрано задание",
                "Сначала выбери задание в таблице.",
            )
            return

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

        self.load()
        self.saved.emit()