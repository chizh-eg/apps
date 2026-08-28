from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QDialog,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QComboBox,
    QDialogButtonBox,
    QMessageBox,
    QFileDialog,
    QAbstractItemView,
    QSplitter,
    QInputDialog,
)
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices

from organizer_db import Database


def make_item(text):
    item = QTableWidgetItem("" if text is None else str(text))
    item.setFlags(
        Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
    )
    return item


class LibraryLinkDialog(QDialog):
    """
    Диалог добавления/редактирования гиперссылки на файл.
    """

    def __init__(
        self,
        db: Database,
        folder_id: int,
        link_id=None,
        parent=None,
    ):
        super().__init__(parent)

        self.db = db
        self.folder_id = folder_id
        self.link_id = link_id

        self.setWindowTitle("Гиперссылка на файл")
        self.resize(640, 420)

        self._build_ui()
        self.load_subjects()

        if self.link_id is not None:
            self.load_link()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        # Название
        self.edt_name = QLineEdit()
        self.edt_name.setPlaceholderText(
            "Например: Лекция 01 — пределы"
        )
        form.addRow("Название", self.edt_name)

        # Файл
        self.edt_file = QLineEdit()
        self.edt_file.setPlaceholderText(
            "Абсолютный путь к файлу"
        )
        self.btn_browse = QPushButton("Обзор...")

        file_container = QWidget()
        file_row = QHBoxLayout(file_container)
        file_row.setContentsMargins(0, 0, 0, 0)
        file_row.addWidget(self.edt_file, 1)
        file_row.addWidget(self.btn_browse)

        form.addRow("Файл", file_container)

        # Предмет (опционально)
        self.cmb_subject = QComboBox()
        self.cmb_subject.addItem("Без привязки", 0)

        form.addRow("Предмет", self.cmb_subject)

        # Описание
        self.txt_note = QPlainTextEdit()
        self.txt_note.setPlaceholderText(
            "Описание, примечания, теги..."
        )
        form.addRow("Описание", self.txt_note)

        layout.addLayout(form)

        # OK / Cancel
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )

        layout.addWidget(self.button_box)

        self.btn_browse.clicked.connect(
            lambda checked=False: self.browse_file()
        )
        self.button_box.accepted.connect(self.try_accept)
        self.button_box.rejected.connect(self.reject)

    def load_subjects(self, select_id=None):
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
            self.cmb_subject.setCurrentIndex(0)

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выбрать файл",
            str(Path.home()),
        )

        if file_path:
            self.edt_file.setText(file_path)

    def load_link(self):
        rows = self.db.query(
            "SELECT * FROM library_links WHERE id = ?",
            (self.link_id,),
        )

        if not rows:
            return

        link = rows[0]

        self.edt_name.setText(link["name"] or "")
        self.edt_file.setText(link["file_path"] or "")
        self.txt_note.setPlainText(link["note"] or "")

        # Пытаемся угадать предмет по пути файла
        subject_id = self.guess_subject_from_path(link["file_path"])
        if subject_id:
            self.load_subjects(select_id=subject_id)

    def guess_subject_from_path(self, file_path: str):
        if not file_path:
            return None

        path = Path(file_path)

        for parent in path.parents:
            rows = self.db.query(
                "SELECT id FROM subjects WHERE folder_name = ?",
                (parent.name,),
            )

            if rows:
                return rows[0]["id"]

        return None

    def try_accept(self):
        name = self.edt_name.text().strip()
        file_path = self.edt_file.text().strip()
        note = self.txt_note.toPlainText().strip()

        if not name:
            QMessageBox.warning(
                self,
                "Нет названия",
                "Введи название для гиперссылки.",
            )
            return

        if not file_path:
            QMessageBox.warning(
                self,
                "Нет файла",
                "Выбери файл или введи путь к нему.",
            )
            return

        subject_id = self.cmb_subject.currentData() or None

        if self.link_id is None:
            self.db.execute(
                """
                INSERT INTO library_links (
                    folder_id,
                    name,
                    file_path,
                    note
                )
                VALUES (?, ?, ?, ?)
                """,
                (self.folder_id, name, file_path, note),
            )
        else:
            self.db.execute(
                """
                UPDATE library_links
                SET
                    name = ?,
                    file_path = ?,
                    note = ?
                WHERE id = ?
                """,
                (name, file_path, note, self.link_id),
            )

        self.accept()


class LibraryTab(QWidget):
    """
    Вкладка библиотеки:
    - дерево папок слева;
    - таблица ссылок справа;
    - создание папок и ссылок;
    - открытие файлов.
    """

    saved = Signal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)

        self.db = db

        self._build_ui()
        self.load_tree()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        top = QHBoxLayout()

        self.btn_add_folder = QPushButton("Создать папку")
        self.btn_delete_folder = QPushButton("Удалить папку")

        top.addWidget(self.btn_add_folder)
        top.addWidget(self.btn_delete_folder)
        top.addStretch(1)

        layout.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Дерево папок
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(260)

        # Таблица ссылок
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        link_buttons = QHBoxLayout()

        self.btn_add_link = QPushButton("Добавить ссылку")
        self.btn_edit_link = QPushButton("Редактировать")
        self.btn_delete_link = QPushButton("Удалить")
        self.btn_open_file = QPushButton("Открыть файл")
        self.btn_show_in_fm = QPushButton("Показать в файловом менеджере")

        link_buttons.addWidget(self.btn_add_link)
        link_buttons.addWidget(self.btn_edit_link)
        link_buttons.addWidget(self.btn_delete_link)
        link_buttons.addWidget(self.btn_open_file)
        link_buttons.addWidget(self.btn_show_in_fm)
        link_buttons.addStretch(1)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            [
                "Название",
                "Файл",
                "Предмет",
                "Описание",
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

        right_layout.addLayout(link_buttons)
        right_layout.addWidget(self.table)

        splitter.addWidget(self.tree)
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([280, 800])

        layout.addWidget(splitter)

        # Сигналы
        self.tree.currentItemChanged.connect(
            lambda current, prev: self.load_links()
        )

        self.btn_add_folder.clicked.connect(
            lambda checked=False: self.add_folder()
        )
        self.btn_delete_folder.clicked.connect(
            lambda checked=False: self.delete_folder()
        )

        self.btn_add_link.clicked.connect(
            lambda checked=False: self.add_link()
        )
        self.btn_edit_link.clicked.connect(
            lambda checked=False: self.edit_link()
        )
        self.btn_delete_link.clicked.connect(
            lambda checked=False: self.delete_link()
        )
        self.btn_open_file.clicked.connect(
            lambda checked=False: self.open_selected_file()
        )
        self.btn_show_in_fm.clicked.connect(
            lambda checked=False: self.show_selected_in_fm()
        )

        self.table.doubleClicked.connect(
            lambda index: self.open_selected_file()
        )

    def load_tree(self, select_id=None):
        self.tree.clear()

        root_rows = self.db.query(
            """
            SELECT id, name
            FROM library_folders
            WHERE parent_id IS NULL
            ORDER BY name
            """
        )

        for row in root_rows:
            root_item = QTreeWidgetItem([row["name"]])
            root_item.setData(0, Qt.ItemDataRole.UserRole, row["id"])
            self.tree.addTopLevelItem(root_item)
            self.load_subfolders(root_item, row["id"])

            if select_id == row["id"]:
                self.tree.setCurrentItem(root_item)

        self.tree.expandAll()

        if not select_id and self.tree.topLevelItemCount() > 0:
            self.tree.setCurrentItem(self.tree.topLevelItem(0))

    def load_subfolders(self, parent_item: QTreeWidgetItem, parent_id: int):
        rows = self.db.query(
            """
            SELECT id, name
            FROM library_folders
            WHERE parent_id = ?
            ORDER BY name
            """,
            (parent_id,),
        )

        for row in rows:
            child_item = QTreeWidgetItem([row["name"]])
            child_item.setData(0, Qt.ItemDataRole.UserRole, row["id"])
            parent_item.addChild(child_item)
            self.load_subfolders(child_item, row["id"])

    def selected_folder_id(self):
        item = self.tree.currentItem()

        if not item:
            return None

        return item.data(0, Qt.ItemDataRole.UserRole)

    def add_folder(self):
        parent_id = self.selected_folder_id()

        name, ok = QInputDialog.getText(
            self,
            "Новая папка",
            "Название папки:",
        )

        if not ok or not name.strip():
            return

        name = name.strip()

        self.db.execute(
            """
            INSERT INTO library_folders (parent_id, name)
            VALUES (?, ?)
            """,
            (parent_id, name),
        )

        self.load_tree()
        self.saved.emit()

    def delete_folder(self):
        folder_id = self.selected_folder_id()

        if folder_id is None:
            QMessageBox.information(
                self,
                "Не выбрана папка",
                "Сначала выбери папку в дереве.",
            )
            return

        # Проверяем, не корневая ли это папка
        rows = self.db.query(
            "SELECT parent_id FROM library_folders WHERE id = ?",
            (folder_id,),
        )

        if rows and rows[0]["parent_id"] is None:
            # Проверяем, единственная ли это корневая папка
            count_rows = self.db.query(
                """
                SELECT COUNT(*) AS c
                FROM library_folders
                WHERE parent_id IS NULL
                """
            )

            if count_rows and count_rows[0]["c"] == 1:
                QMessageBox.warning(
                    self,
                    "Нельзя удалить",
                    "Нельзя удалить единственную корневую папку.",
                )
                return

        answer = QMessageBox.question(
            self,
            "Удаление папки",
            "Удалить папку со всеми вложенными папками и ссылками?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.db.execute(
            "DELETE FROM library_folders WHERE id = ?",
            (folder_id,),
        )

        self.load_tree()
        self.saved.emit()

    def load_links(self):
        folder_id = self.selected_folder_id()

        if folder_id is None:
            self.table.clear()
            self.table.setRowCount(0)
            return

        rows = self.db.query(
            """
            SELECT
                l.id,
                l.name,
                l.file_path,
                l.note,
                s.name AS subject_name
            FROM library_links l
            LEFT JOIN subjects s ON s.folder_name = ?
            WHERE l.folder_id = ?
            ORDER BY l.name
            """,
            (
                self.get_folder_name(folder_id),
                folder_id,
            ),
        )

        self.table.clear()
        self.table.setRowCount(len(rows))
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            [
                "Название",
                "Файл",
                "Предмет",
                "Описание",
            ]
        )

        for row_index, row in enumerate(rows):
            id_item = make_item(row["name"])
            id_item.setData(Qt.ItemDataRole.UserRole, row["id"])

            if row["note"]:
                id_item.setToolTip(row["note"])

            file_item = make_item(row["file_path"])
            file_item.setToolTip(row["file_path"])

            subject_item = make_item(row["subject_name"])
            note_item = make_item(row["note"])

            self.table.setItem(row_index, 0, id_item)
            self.table.setItem(row_index, 1, file_item)
            self.table.setItem(row_index, 2, subject_item)
            self.table.setItem(row_index, 3, note_item)

        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, 240)
        self.table.setColumnWidth(1, 360)
        self.table.setColumnWidth(2, 160)

    def get_folder_name(self, folder_id: int) -> str:
        rows = self.db.query(
            "SELECT name FROM library_folders WHERE id = ?",
            (folder_id,),
        )

        return rows[0]["name"] if rows else ""

    def selected_link_id(self):
        row = self.table.currentRow()

        if row < 0:
            return None

        item = self.table.item(row, 0)

        if not item:
            return None

        return item.data(Qt.ItemDataRole.UserRole)

    def add_link(self):
        folder_id = self.selected_folder_id()

        if folder_id is None:
            QMessageBox.information(
                self,
                "Не выбрана папка",
                "Сначала выбери папку в дереве.",
            )
            return

        dialog = LibraryLinkDialog(
            self.db,
            folder_id=folder_id,
            link_id=None,
            parent=self,
        )

        if dialog.exec():
            self.load_links()
            self.saved.emit()

    def edit_link(self):
        link_id = self.selected_link_id()

        if link_id is None:
            QMessageBox.information(
                self,
                "Не выбрана ссылка",
                "Сначала выбери ссылку в таблице.",
            )
            return

        folder_id = self.selected_folder_id()

        dialog = LibraryLinkDialog(
            self.db,
            folder_id=folder_id,
            link_id=link_id,
            parent=self,
        )

        if dialog.exec():
            self.load_links()
            self.saved.emit()

    def delete_link(self):
        link_id = self.selected_link_id()

        if link_id is None:
            QMessageBox.information(
                self,
                "Не выбрана ссылка",
                "Сначала выбери ссылку в таблице.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Удаление ссылки",
            "Удалить выбранную гиперссылку?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.db.execute(
            "DELETE FROM library_links WHERE id = ?",
            (link_id,),
        )

        self.load_links()
        self.saved.emit()

    def open_selected_file(self):
        link_id = self.selected_link_id()

        if link_id is None:
            QMessageBox.information(
                self,
                "Не выбрана ссылка",
                "Сначала выбери ссылку в таблице.",
            )
            return

        rows = self.db.query(
            "SELECT file_path FROM library_links WHERE id = ?",
            (link_id,),
        )

        if not rows:
            return

        file_path = rows[0]["file_path"]

        if not Path(file_path).exists():
            QMessageBox.warning(
                self,
                "Файл не найден",
                f"Файл не существует:\n{file_path}",
            )
            return

        QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))

    def show_selected_in_fm(self):
        import subprocess

        link_id = self.selected_link_id()

        if link_id is None:
            QMessageBox.information(
                self,
                "Не выбрана ссылка",
                "Сначала выбери ссылку в таблице.",
            )
            return

        rows = self.db.query(
            "SELECT file_path FROM library_links WHERE id = ?",
            (link_id,),
        )

        if not rows:
            return

        file_path = rows[0]["file_path"]
        target = Path(file_path).parent

        if not target.exists():
            QMessageBox.warning(
                self,
                "Папка не найдена",
                f"Папка не существует:\n{target}",
            )
            return

        try:
            subprocess.Popen(["thunar", str(target)])
        except Exception:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))