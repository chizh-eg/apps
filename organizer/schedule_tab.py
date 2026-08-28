from __future__ import annotations

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
    QSpinBox,
    QTimeEdit,
    QDialogButtonBox,
    QMessageBox,
    QAbstractItemView,
    QLabel,
    QSplitter,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
)
from PySide6.QtCore import Qt, QTime, Signal

from organizer_db import (
    Database,
    LESSON_TYPES,
    LESSON_TYPE_LABELS,
)
from week_grid_tab import RoundedCard, RoundedTable


WEEKDAYS = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]

PARITY_LABELS = {
    "all": "Каждая неделя",
    "numerator": "Числитель",
    "denominator": "Знаменатель",
}

TABLE_HEADERS = [
    "Предмет",
    "День",
    "№",
    "Начало",
    "Конец",
    "Преподаватель",
    "Аудитория",
    "Тип",
    "Подгруппа",
    "Неделя",
]


def make_item(text):
    item = QTableWidgetItem("" if text is None else str(text))
    item.setFlags(
        Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
    )
    return item


class ScheduleDialog(QDialog):
    """
    Диалог добавления/редактирования пары.
    """

    def __init__(self, db: Database, slot_id=None, parent=None):
        super().__init__(parent)

        self.db = db
        self.slot_id = slot_id

        self.setWindowTitle("Пара")
        self.resize(480, 420)

        self._build_ui()
        self.load_subjects()
        self.load_teachers()

        if self.slot_id is not None:
            self.load_slot()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

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

        # День недели
        self.cmb_weekday = QComboBox()
        for day in WEEKDAYS:
            self.cmb_weekday.addItem(day)
        form.addRow("День недели", self.cmb_weekday)

        # Номер пары
        self.spb_lesson = QSpinBox()
        self.spb_lesson.setMinimum(1)
        self.spb_lesson.setMaximum(12)
        self.spb_lesson.setValue(1)
        form.addRow("Номер пары", self.spb_lesson)

        # Время
        self.time_start = QTimeEdit(QTime(9, 0))
        self.time_start.setDisplayFormat("HH:mm")
        self.time_end = QTimeEdit(QTime(10, 30))
        self.time_end.setDisplayFormat("HH:mm")

        time_container = QWidget()
        time_row = QHBoxLayout(time_container)
        time_row.setContentsMargins(0, 0, 0, 0)
        time_row.addWidget(self.time_start)
        time_row.addWidget(QLabel("—"))
        time_row.addWidget(self.time_end)
        time_row.addStretch(1)

        form.addRow("Время", time_container)

        # Преподаватель: поиск по списку + сохранение в список
        self.cmb_teacher = QComboBox()
        self.cmb_teacher.setEditable(True)
        self.cmb_teacher.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

        self.btn_add_teacher = QPushButton("+")
        self.btn_add_teacher.setFixedWidth(32)
        self.btn_add_teacher.setToolTip("Сохранить преподавателя в список")

        teacher_container = QWidget()
        teacher_row = QHBoxLayout(teacher_container)
        teacher_row.setContentsMargins(0, 0, 0, 0)
        teacher_row.addWidget(self.cmb_teacher, 1)
        teacher_row.addWidget(self.btn_add_teacher)

        form.addRow("Преподаватель", teacher_container)

        # Аудитория
        self.edt_room = QLineEdit()
        self.edt_room.setPlaceholderText("Например: 204, корпус A")
        form.addRow("Аудитория", self.edt_room)

        # Тип пары
        self.cmb_type = QComboBox()
        for type_id, label, _ in LESSON_TYPES:
            self.cmb_type.addItem(label, type_id)
        form.addRow("Тип", self.cmb_type)

        # Подгруппа
        self.cmb_subgroup = QComboBox()
        self.cmb_subgroup.addItem("Вся группа", 0)
        for n in (1, 2, 3, 4):
            self.cmb_subgroup.addItem(f"Подгруппа {n}", n)
        form.addRow("Подгруппа", self.cmb_subgroup)

        # Числитель/знаменатель
        self.cmb_parity = QComboBox()
        self.cmb_parity.addItem("Каждая неделя", "all")
        self.cmb_parity.addItem("Числитель", "numerator")
        self.cmb_parity.addItem("Знаменатель", "denominator")
        form.addRow("Неделя", self.cmb_parity)

        layout.addLayout(form)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(self.button_box)

        self.button_box.accepted.connect(self.try_accept)
        self.button_box.rejected.connect(self.reject)
        self.btn_add_subject.clicked.connect(
            lambda checked=False: self.add_subject()
        )
        self.btn_add_teacher.clicked.connect(
            lambda checked=False: self.add_teacher()
        )

        self.spb_lesson.valueChanged.connect(self._apply_lesson_time)
        self._apply_lesson_time(self.spb_lesson.value())

    def _apply_lesson_time(self, lesson_no: int):
        rows = self.db.query(
            """
            SELECT start_time, end_time
            FROM lesson_times
            WHERE lesson_no = ?
            """,
            (lesson_no,),
        )

        if not rows:
            return

        start = QTime.fromString(rows[0]["start_time"], "HH:mm")
        end = QTime.fromString(rows[0]["end_time"], "HH:mm")

        if start.isValid():
            self.time_start.setTime(start)

        if end.isValid():
            self.time_end.setTime(end)

    def load_subjects(self, select_id=None):
        self.cmb_subject.clear()

        rows = self.db.query(
            "SELECT id, name FROM subjects ORDER BY name"
        )

        for row in rows:
            self.cmb_subject.addItem(row["name"], row["id"])

        if select_id is not None:
            for i in range(self.cmb_subject.count()):
                if self.cmb_subject.itemData(i) == select_id:
                    self.cmb_subject.setCurrentIndex(i)
                    break
        else:
            if self.cmb_subject.count() > 0:
                self.cmb_subject.setCurrentIndex(0)

    def load_teachers(self):
        self.cmb_teacher.clear()

        rows = self.db.query("SELECT name FROM teachers ORDER BY name")

        for row in rows:
            self.cmb_teacher.addItem(row["name"])

    def add_subject(self):
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

    def add_teacher(self):
        name = self.cmb_teacher.currentText().strip()

        if not name:
            return

        self.db.execute(
            "INSERT OR IGNORE INTO teachers (name) VALUES (?)",
            (name,),
        )

        self.load_teachers()
        self.cmb_teacher.setCurrentText(name)

    def load_slot(self):
        rows = self.db.query(
            "SELECT * FROM schedule_slots WHERE id = ?",
            (self.slot_id,),
        )

        if not rows:
            return

        slot = rows[0]

        self.load_subjects(select_id=slot["subject_id"])

        weekday_index = max(0, min(6, slot["weekday"] - 1))
        self.cmb_weekday.setCurrentIndex(weekday_index)

        self.spb_lesson.setValue(slot["lesson_no"])

        start = QTime.fromString(slot["start_time"], "HH:mm")
        end = QTime.fromString(slot["end_time"], "HH:mm")

        if start.isValid():
            self.time_start.setTime(start)

        if end.isValid():
            self.time_end.setTime(end)

        self.cmb_teacher.setCurrentText(slot["teacher"] or "")
        self.edt_room.setText(slot["room"] or "")

        type_index = self.cmb_type.findData(
            slot["lesson_type"] or "lecture"
        )
        if type_index >= 0:
            self.cmb_type.setCurrentIndex(type_index)

        sub_index = self.cmb_subgroup.findData(slot["subgroup"] or 0)
        if sub_index >= 0:
            self.cmb_subgroup.setCurrentIndex(sub_index)

        parity_index = self.cmb_parity.findData(slot["parity"] or "all")
        if parity_index >= 0:
            self.cmb_parity.setCurrentIndex(parity_index)

    def try_accept(self):
        subject_id = self.cmb_subject.currentData()

        if subject_id is None:
            QMessageBox.warning(
                self,
                "Нет предмета",
                "Сначала выбери или добавь предмет.",
            )
            return

        start = self.time_start.time()
        end = self.time_end.time()

        if start >= end:
            QMessageBox.warning(
                self,
                "Некорректное время",
                "Время окончания пары должно быть позже времени начала.",
            )
            return

        weekday = self.cmb_weekday.currentIndex() + 1
        lesson_no = self.spb_lesson.value()
        teacher = self.cmb_teacher.currentText().strip()
        room = self.edt_room.text().strip()
        parity = self.cmb_parity.currentData() or "all"
        lesson_type = self.cmb_type.currentData() or "lecture"
        subgroup = self.cmb_subgroup.currentData() or 0

        # Автоматически сохраняем преподавателя в словарь
        if teacher:
            self.db.execute(
                "INSERT OR IGNORE INTO teachers (name) VALUES (?)",
                (teacher,),
            )

        if self.slot_id is None:
            self.db.execute(
                """
                INSERT INTO schedule_slots (
                    subject_id,
                    weekday,
                    lesson_no,
                    start_time,
                    end_time,
                    teacher,
                    room,
                    parity,
                    lesson_type,
                    subgroup
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    subject_id,
                    weekday,
                    lesson_no,
                    start.toString("HH:mm"),
                    end.toString("HH:mm"),
                    teacher,
                    room,
                    parity,
                    lesson_type,
                    subgroup,
                ),
            )
        else:
            self.db.execute(
                """
                UPDATE schedule_slots
                SET
                    subject_id = ?,
                    weekday = ?,
                    lesson_no = ?,
                    start_time = ?,
                    end_time = ?,
                    teacher = ?,
                    room = ?,
                    parity = ?,
                    lesson_type = ?,
                    subgroup = ?
                WHERE id = ?
                """,
                (
                    subject_id,
                    weekday,
                    lesson_no,
                    start.toString("HH:mm"),
                    end.toString("HH:mm"),
                    teacher,
                    room,
                    parity,
                    lesson_type,
                    subgroup,
                    self.slot_id,
                ),
            )

        self.accept()


class LessonTimesDialog(QDialog):
    """
    Настройка времени пар (звонков): одинаково для всех дней.
    """

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)

        self.db = db
        self.setWindowTitle("Время пар (звонки)")
        self.resize(380, 460)

        self._rows = []

        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        for lesson_no in range(1, 9):
            start_edit = QTimeEdit()
            start_edit.setDisplayFormat("HH:mm")

            end_edit = QTimeEdit()
            end_edit.setDisplayFormat("HH:mm")

            time_container = QWidget()
            time_row = QHBoxLayout(time_container)
            time_row.setContentsMargins(0, 0, 0, 0)
            time_row.addWidget(start_edit)
            time_row.addWidget(QLabel("—"))
            time_row.addWidget(end_edit)
            time_row.addStretch(1)

            form.addRow(f"{lesson_no} пара", time_container)

            self._rows.append((lesson_no, start_edit, end_edit))

        layout.addLayout(form)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(button_box)

        button_box.accepted.connect(self._save)
        button_box.rejected.connect(self.reject)

    def _load(self):
        for lesson_no, start_edit, end_edit in self._rows:
            rows = self.db.query(
                """
                SELECT start_time, end_time
                FROM lesson_times
                WHERE lesson_no = ?
                """,
                (lesson_no,),
            )

            if rows:
                start = QTime.fromString(rows[0]["start_time"], "HH:mm")
                end = QTime.fromString(rows[0]["end_time"], "HH:mm")
            else:
                start = QTime(8, 30).addSecs((lesson_no - 1) * 6300)
                end = start.addSecs(5400)

            if start.isValid():
                start_edit.setTime(start)

            if end.isValid():
                end_edit.setTime(end)

    def _save(self):
        for lesson_no, start_edit, end_edit in self._rows:
            start = start_edit.time()
            end = end_edit.time()

            if start >= end:
                QMessageBox.warning(
                    self,
                    "Некорректное время",
                    f"У пары {lesson_no} окончание не позже начала.",
                )
                return

            self.db.execute(
                """
                INSERT INTO lesson_times (lesson_no, start_time, end_time)
                VALUES (?, ?, ?)
                ON CONFLICT(lesson_no) DO UPDATE SET
                    start_time = excluded.start_time,
                    end_time = excluded.end_time
                """,
                (
                    lesson_no,
                    start.toString("HH:mm"),
                    end.toString("HH:mm"),
                ),
            )

        self.accept()


class DictionaryDialog(QDialog):
    """
    Управление словарями: предметы и преподаватели.
    """

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)

        self.db = db
        self.setWindowTitle("Предметы и преподаватели")
        self.resize(560, 440)

        self._build_ui()
        self.refresh_lists()

    def _build_ui(self):
        layout = QHBoxLayout(self)

        # ===== Предметы =====
        left = QVBoxLayout()

        left.addWidget(QLabel("Предметы"))

        self.lst_subjects = QListWidget()
        left.addWidget(self.lst_subjects)

        btn_add_subject = QPushButton("Добавить предмет")
        btn_del_subject = QPushButton("Удалить предмет")

        left.addWidget(btn_add_subject)
        left.addWidget(btn_del_subject)

        layout.addLayout(left)

        # ===== Преподаватели =====
        right = QVBoxLayout()

        right.addWidget(QLabel("Преподаватели"))

        self.lst_teachers = QListWidget()
        right.addWidget(self.lst_teachers)

        btn_add_teacher = QPushButton("Добавить преподавателя")
        btn_del_teacher = QPushButton("Удалить преподавателя")

        right.addWidget(btn_add_teacher)
        right.addWidget(btn_del_teacher)

        layout.addLayout(right)

        btn_add_subject.clicked.connect(
            lambda checked=False: self.add_subject()
        )
        btn_del_subject.clicked.connect(
            lambda checked=False: self.delete_subject()
        )
        btn_add_teacher.clicked.connect(
            lambda checked=False: self.add_teacher()
        )
        btn_del_teacher.clicked.connect(
            lambda checked=False: self.delete_teacher()
        )

    def refresh_lists(self):
        self.lst_subjects.clear()

        for row in self.db.query(
            "SELECT id, name FROM subjects ORDER BY name"
        ):
            item = QListWidgetItem(row["name"])
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.lst_subjects.addItem(item)

        self.lst_teachers.clear()

        for row in self.db.query(
            "SELECT id, name FROM teachers ORDER BY name"
        ):
            item = QListWidgetItem(row["name"])
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.lst_teachers.addItem(item)

    def add_subject(self):
        name, ok = QInputDialog.getText(
            self,
            "Новый предмет",
            "Название предмета:",
        )

        if ok and name.strip():
            self.db.execute(
                """
                INSERT OR IGNORE INTO subjects (name, folder_name)
                VALUES (?, ?)
                """,
                (name.strip(), name.strip()),
            )
            self.refresh_lists()

    def delete_subject(self):
        item = self.lst_subjects.currentItem()

        if not item:
            return

        answer = QMessageBox.warning(
            self,
            "Удаление предмета",
            f"Предмет «{item.text()}» будет удалён ВМЕСТЕ со всеми "
            f"парами и заданиями. Продолжить?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.db.execute(
            "DELETE FROM subjects WHERE id = ?",
            (item.data(Qt.ItemDataRole.UserRole),),
        )

        self.refresh_lists()

    def add_teacher(self):
        name, ok = QInputDialog.getText(
            self,
            "Новый преподаватель",
            "ФИО преподавателя:",
        )

        if ok and name.strip():
            self.db.execute(
                "INSERT OR IGNORE INTO teachers (name) VALUES (?)",
                (name.strip(),),
            )
            self.refresh_lists()

    def delete_teacher(self):
        item = self.lst_teachers.currentItem()

        if not item:
            return

        self.db.execute(
            "DELETE FROM teachers WHERE id = ?",
            (item.data(Qt.ItemDataRole.UserRole),),
        )

        self.refresh_lists()


class ScheduleTab(QWidget):
    saved = Signal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)

        self.db = db

        self._build_ui()
        self._load_my_subgroup()
        self.load()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        top = QHBoxLayout()

        top.addWidget(QLabel("Режим недели:"))

        self.cmb_filter = QComboBox()
        self.cmb_filter.addItem("Числитель", "numerator")
        self.cmb_filter.addItem("Знаменатель", "denominator")
        self.cmb_filter.addItem("Все записи", "all")

        self.cmb_my_subgroup = QComboBox()
        self.cmb_my_subgroup.addItem("Все подгруппы", 0)
        for n in (1, 2, 3, 4):
            self.cmb_my_subgroup.addItem(f"Подгруппа {n}", n)

        self.btn_reload = QPushButton("Обновить")
        self.btn_times = QPushButton("Звонки")
        self.btn_dict = QPushButton("Словари")
        self.btn_add = QPushButton("Добавить пару")
        self.btn_edit = QPushButton("Редактировать")
        self.btn_delete = QPushButton("Удалить")

        top.addWidget(self.cmb_filter)
        top.addWidget(QLabel("Моя подгруппа:"))
        top.addWidget(self.cmb_my_subgroup)
        top.addWidget(self.btn_reload)
        top.addWidget(self.btn_dict)
        top.addStretch(1)
        top.addWidget(self.btn_add)
        top.addWidget(self.btn_edit)
        top.addWidget(self.btn_delete)

        layout.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # ===== Основная таблица пар =====
        self.table_card = RoundedCard(radius=18)
        table_card_layout = QVBoxLayout(self.table_card)
        table_card_layout.setContentsMargins(8, 8, 8, 8)

        self.table = RoundedTable(radius=12)
        self.table.setObjectName("schedTable")
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(TABLE_HEADERS)

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

        table_card_layout.addWidget(self.table)

        # ===== Недельный предпросмотр =====
        self.preview_card = RoundedCard(radius=18)
        preview_card_layout = QVBoxLayout(self.preview_card)
        preview_card_layout.setContentsMargins(8, 8, 8, 8)

        self.preview = RoundedTable(radius=12)
        self.preview.setObjectName("schedPreview")
        self.preview.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.preview.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.preview.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.preview.verticalHeader().setDefaultSectionSize(84)
        self.preview.setWordWrap(True)

        preview_card_layout.addWidget(self.preview)

        splitter.addWidget(self.table_card)
        splitter.addWidget(self.preview_card)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([480, 320])

        layout.addWidget(splitter)

        # ===== Сигналы =====
        self.cmb_filter.currentIndexChanged.connect(
            lambda index: self.load()
        )
        self.cmb_my_subgroup.currentIndexChanged.connect(
            lambda index: self.on_my_subgroup_changed()
        )

        self.btn_reload.clicked.connect(lambda checked=False: self.load())
        self.btn_times.clicked.connect(
            lambda checked=False: self.open_times_dialog()
        )
        self.btn_dict.clicked.connect(
            lambda checked=False: self.open_dictionary()
        )
        self.btn_add.clicked.connect(lambda checked=False: self.add_slot())
        self.btn_edit.clicked.connect(lambda checked=False: self.edit_slot())
        self.btn_delete.clicked.connect(
            lambda checked=False: self.delete_slot()
        )

        self.table.doubleClicked.connect(lambda index: self.edit_slot())

    def _load_my_subgroup(self):
        rows = self.db.query(
            "SELECT my_subgroup FROM settings WHERE id = 1"
        )

        my = 0

        if rows and rows[0]["my_subgroup"]:
            my = int(rows[0]["my_subgroup"])

        index = self.cmb_my_subgroup.findData(my)

        if index >= 0:
            self.cmb_my_subgroup.blockSignals(True)
            self.cmb_my_subgroup.setCurrentIndex(index)
            self.cmb_my_subgroup.blockSignals(False)

    def on_my_subgroup_changed(self):
        my = self.cmb_my_subgroup.currentData() or 0

        self.db.execute(
            "UPDATE settings SET my_subgroup = ? WHERE id = 1",
            (my,),
        )

        self.load()
        self.saved.emit()

    def open_times_dialog(self):
        dialog = LessonTimesDialog(self.db, self)

        if dialog.exec():
            self.load()
            self.saved.emit()

    def open_dictionary(self):
        dialog = DictionaryDialog(self.db, self)
        dialog.exec()

        self.load()
        self.saved.emit()

    def _subgroup_condition(self):
        my = self.cmb_my_subgroup.currentData() or 0

        if my:
            return "AND (s.subgroup = 0 OR s.subgroup = ?)", [my]

        return "", []

    def load(self):
        filter_parity = self.cmb_filter.currentData() or "numerator"

        if filter_parity == "numerator":
            where = "(s.parity = 'all' OR s.parity = 'numerator')"
        elif filter_parity == "denominator":
            where = "(s.parity = 'all' OR s.parity = 'denominator')"
        else:
            where = "1=1"

        sub_cond, sub_params = self._subgroup_condition()

        sql = f"""
            SELECT
                s.*,
                sub.name AS subject_name
            FROM schedule_slots s
            JOIN subjects sub ON sub.id = s.subject_id
            WHERE {where} {sub_cond}
            ORDER BY s.weekday, s.lesson_no, s.start_time
        """

        rows = self.db.query(sql, tuple(sub_params))

        self.table.clear()
        self.table.setRowCount(len(rows))
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(TABLE_HEADERS)

        for row_index, row in enumerate(rows):
            subject_item = make_item(row["subject_name"])
            subject_item.setData(Qt.ItemDataRole.UserRole, row["id"])

            self.table.setItem(row_index, 0, subject_item)
            self.table.setItem(
                row_index, 1, make_item(WEEKDAYS[row["weekday"] - 1])
            )
            self.table.setItem(row_index, 2, make_item(row["lesson_no"]))
            self.table.setItem(row_index, 3, make_item(row["start_time"]))
            self.table.setItem(row_index, 4, make_item(row["end_time"]))
            self.table.setItem(row_index, 5, make_item(row["teacher"]))
            self.table.setItem(row_index, 6, make_item(row["room"]))
            self.table.setItem(
                row_index,
                7,
                make_item(
                    LESSON_TYPE_LABELS.get(
                        row["lesson_type"], row["lesson_type"] or ""
                    )
                ),
            )
            self.table.setItem(
                row_index,
                8,
                make_item(
                    f"{row['subgroup']}" if row["subgroup"] else "—"
                ),
            )
            self.table.setItem(
                row_index,
                9,
                make_item(PARITY_LABELS.get(row["parity"], row["parity"])),
            )

        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, 200)
        self.table.setColumnWidth(5, 160)
        self.table.setColumnWidth(6, 140)

        self.build_preview(rows)

    def build_preview(self, rows):
        self.preview.clear()
        self.preview.clearSpans()

        if not rows:
            self.preview.setRowCount(1)
            self.preview.setColumnCount(7)
            self.preview.setHorizontalHeaderLabels(WEEKDAYS)
            self.preview.setVerticalHeaderLabels(["Пары"])

            item = make_item("Нет пар. Нажми «Добавить пару».")
            self.preview.setItem(0, 0, item)
            self.preview.setSpan(0, 0, 1, 7)
            return

        row_keys = []

        for row in rows:
            key = (
                row["lesson_no"],
                row["start_time"],
                row["end_time"],
            )

            if key not in row_keys:
                row_keys.append(key)

        row_keys.sort(key=lambda x: (x[0], x[1], x[2]))
        key_to_row = {key: i for i, key in enumerate(row_keys)}

        self.preview.setRowCount(len(row_keys))
        self.preview.setColumnCount(7)

        self.preview.setHorizontalHeaderLabels(WEEKDAYS)
        self.preview.setVerticalHeaderLabels(
            [
                f"{lesson}. {start}-{end}"
                for lesson, start, end in row_keys
            ]
        )

        cells = {}

        for row in rows:
            key = (
                row["lesson_no"],
                row["start_time"],
                row["end_time"],
            )

            table_row = key_to_row[key]
            table_col = row["weekday"] - 1

            text = row["subject_name"]

            type_label = LESSON_TYPE_LABELS.get(row["lesson_type"], "")

            if type_label:
                text += f"\n{type_label}"

            if row["teacher"]:
                text += f"\n{row['teacher']}"

            if row["room"]:
                text += f"\n{row['room']}"

            if row["subgroup"]:
                text += f"\nподгруппа {row['subgroup']}"

            if row["parity"] == "numerator":
                text += "\n(числитель)"
            elif row["parity"] == "denominator":
                text += "\n(знаменатель)"

            cells.setdefault((table_row, table_col), []).append(text)

        for (table_row, table_col), texts in cells.items():
            full_text = "\n".join(texts)

            item = make_item(full_text)
            item.setToolTip(full_text)

            self.preview.setItem(table_row, table_col, item)

    def selected_slot_id(self):
        row = self.table.currentRow()

        if row < 0:
            return None

        item = self.table.item(row, 0)

        if not item:
            return None

        return item.data(Qt.ItemDataRole.UserRole)

    def add_slot(self):
        dialog = ScheduleDialog(self.db, None, self)

        if dialog.exec():
            self.load()
            self.saved.emit()

    def edit_slot(self):
        slot_id = self.selected_slot_id()

        if slot_id is None:
            QMessageBox.information(
                self,
                "Не выбрана пара",
                "Сначала выбери пару в таблице.",
            )
            return

        dialog = ScheduleDialog(self.db, slot_id, self)

        if dialog.exec():
            self.load()
            self.saved.emit()

    def delete_slot(self):
        slot_id = self.selected_slot_id()

        if slot_id is None:
            QMessageBox.information(
                self,
                "Не выбрана пара",
                "Сначала выбери пару в таблице.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Удаление пары",
            "Удалить выбранную пару?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.db.execute(
            "DELETE FROM schedule_slots WHERE id = ?",
            (slot_id,),
        )

        self.load()
        self.saved.emit()
