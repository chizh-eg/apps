from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QStackedWidget,
    QPlainTextEdit,
    QFileDialog,
    QMessageBox,
    QInputDialog,
    QComboBox,
    QLineEdit,
    QDialog,
    QFormLayout,
    QDialogButtonBox,
    QMenu,
    QListView,
    QSizePolicy,
    QApplication,
)
from PySide6.QtCore import Qt, QUrl, QFileInfo, QSize, Signal, QEvent, QTimer
from PySide6.QtGui import QDesktopServices, QPixmap

try:
    from PySide6.QtPdfWidgets import QPdfView
    from PySide6.QtPdf import QPdfDocument
    HAS_PDF = True
except Exception:
    HAS_PDF = False

from organizer_db import Database
from week_grid_tab import RoundedCard
from icons import make_file_icon, file_kind


class AddExternalFolderDialog(QDialog):
    """Имя и предмет для сторонней папки (без переименования на диске)."""

    def __init__(self, default_name: str, subjects, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Добавить стороннюю папку")
        self.resize(440, 180)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.edt_name = QLineEdit(default_name)
        self.cmb_subject = QComboBox()
        self.cmb_subject.addItem("Без предмета", 0)

        for sid, name in subjects:
            self.cmb_subject.addItem(name, sid)

        form.addRow("Отображаемое имя", self.edt_name)
        form.addRow("Предмет", self.cmb_subject)

        layout.addLayout(form)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)

        layout.addWidget(bb)

    def result_data(self):
        return (
            self.edt_name.text().strip() or "Папка",
            self.cmb_subject.currentData() or None,
        )


class FilesMaterialTab(QWidget):
    subjectAdded = Signal(str)

    TEXT_EXTS = {
        ".txt", ".md", ".rst", ".py", ".js", ".ts", ".c", ".cpp",
        ".h", ".hpp", ".java", ".json", ".xml", ".html", ".htm",
        ".css", ".csv", ".tsv", ".ini", ".cfg", ".yaml", ".yml",
        ".sql", ".sh", ".bat", ".pro", ".ui",
    }
    OFFICE_EXTS = {".docx", ".odt"}
    IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}

    def __init__(self, db: Database, root: Path, parent=None):
        super().__init__(parent)

        self.db = db
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.current_path = self.root
        self.linked_roots = set()

        self._build_ui()
        self.navigate(self.root)

    # ===== Интерфейс =====

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(12)

        # ===== Корневая папка =====
        root_row = QHBoxLayout()
        root_row.setSpacing(8)

        self.lbl_root = QLabel("")
        self.lbl_root.setObjectName("rootPathChip")
        self.lbl_root.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.btn_change_root = QPushButton("📁 Сменить папку")
        self.btn_change_root.setObjectName("toolbarButton")

        root_row.addWidget(self.lbl_root, 1)
        root_row.addWidget(self.btn_change_root)

        layout.addLayout(root_row)

        # ===== Действия =====
        top = QHBoxLayout()
        top.setSpacing(8)

        self.btn_up = QPushButton("← Вверх")
        self.btn_up.setObjectName("toolbarButton")

        self.btn_refresh = QPushButton("⟳ Обновить")
        self.btn_refresh.setObjectName("toolbarButton")

        self.btn_open_fm = QPushButton("Открыть в проводнике")
        self.btn_open_fm.setObjectName("toolbarButton")

        self.btn_add_subject = QPushButton("+ Предмет")
        self.btn_add_subject.setObjectName("toolbarButton")
        self.btn_add_subject.setToolTip(
            "Добавить папку существующего предмета"
        )

        self.btn_add_folder = QPushButton("+ Папка")
        self.btn_add_folder.setObjectName("toolbarButton")
        self.btn_add_folder.setToolTip(
            "Добавить стороннюю папку со своим именем"
        )

        top.addWidget(self.btn_up)
        top.addWidget(self.btn_refresh)
        top.addWidget(self.btn_open_fm)
        top.addStretch(1)
        top.addWidget(self.btn_add_subject)
        top.addWidget(self.btn_add_folder)

        layout.addLayout(top)

        # ===== Обзор + предпросмотр =====
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.browse_card = RoundedCard(radius=18)
        browse_layout = QVBoxLayout(self.browse_card)
        browse_layout.setContentsMargins(12, 12, 12, 12)

        self.file_list = QListWidget()
        self.file_list.setObjectName("filesList")
        self.file_list.setViewMode(QListView.ViewMode.IconMode)
        self.file_list.setIconSize(QSize(64, 64))
        self.file_list.setGridSize(QSize(115, 105))
        self.file_list.setWordWrap(True)
        self.file_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.file_list.setSpacing(6)
        self.file_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )

        browse_layout.addWidget(self.file_list)

        self.preview_card = RoundedCard(radius=18)
        preview_layout = QVBoxLayout(self.preview_card)
        preview_layout.setContentsMargins(12, 12, 12, 12)

        self.preview_title = QLabel("Предпросмотр")
        self.preview_title.setObjectName("previewTitle")
        # Длинные имена не растягивают область предпросмотра
        self.preview_title.setWordWrap(False)
        self.preview_title.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )

        self.preview_stack = QStackedWidget()

        self.preview_placeholder = QLabel(
            "Выберите файл для предпросмотра.\n"
            "Двойной клик — открыть в приложении по умолчанию."
        )
        self.preview_placeholder.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.preview_placeholder.setWordWrap(True)

        self.preview_text = QPlainTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setObjectName("previewText")

        self.preview_image = QLabel()
        self.preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image.setMinimumSize(220, 220)
        # Размер задаёт только layout, а не пиксмап —
        # картинка больше не растягивает область предпросмотра
        self.preview_image.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Ignored,
        )
        self.preview_image.installEventFilter(self)

        self._current_pixmap = None

        self.preview_stack.addWidget(self.preview_placeholder)
        self.preview_stack.addWidget(self.preview_text)
        self.preview_stack.addWidget(self.preview_image)

        if HAS_PDF:
            self.preview_pdf = QPdfView()
            # Документ НЕ ребёнок вью — чтобы корректно
            # освободить его перед выходом без segfault
            self._pdf_doc = QPdfDocument(self)
            # Сразу назначаем документ, чтобы вью никогда
            # не жило с nullptr-документом (убирает warning)
            self.preview_pdf.setDocument(self._pdf_doc)
            self.preview_stack.addWidget(self.preview_pdf)
        else:
            self.preview_pdf = None
            self._pdf_doc = None

        preview_layout.addWidget(self.preview_title)
        preview_layout.addWidget(self.preview_stack, 1)

        splitter.addWidget(self.browse_card)
        splitter.addWidget(self.preview_card)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([820, 440])

        layout.addWidget(splitter, 1)

        # ===== Нижняя панель информации =====
        self.info_card = RoundedCard(radius=18)
        info_layout = QHBoxLayout(self.info_card)
        info_layout.setContentsMargins(14, 10, 14, 10)
        info_layout.setSpacing(12)

        self.lbl_info_icon = QLabel()
        self.lbl_info_icon.setFixedSize(48, 48)
        self.lbl_info_icon.setScaledContents(True)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        self.lbl_info_name = QLabel("")
        self.lbl_info_name.setObjectName("filesInfoName")

        self.lbl_info_details = QLabel("")
        self.lbl_info_details.setObjectName("filesInfoDetails")

        self.lbl_info_path = QLabel("")
        self.lbl_info_path.setObjectName("filesInfoPath")
        self.lbl_info_path.setWordWrap(True)

        text_col.addWidget(self.lbl_info_name)
        text_col.addWidget(self.lbl_info_details)
        text_col.addWidget(self.lbl_info_path)

        info_layout.addWidget(self.lbl_info_icon)
        info_layout.addLayout(text_col, 1)

        self.info_card.setMaximumHeight(120)
        layout.addWidget(self.info_card)

        # ===== Сигналы =====
        self.btn_up.clicked.connect(self.go_up)
        self.btn_refresh.clicked.connect(
            lambda: self.navigate(self.current_path)
        )
        self.btn_open_fm.clicked.connect(
            lambda: self.open_in_file_manager(self.current_path)
        )
        self.btn_change_root.clicked.connect(self.change_root)
        self.btn_add_subject.clicked.connect(self.add_subject_folder)
        self.btn_add_folder.clicked.connect(self.add_external_folder)

        self.file_list.itemActivated.connect(self.on_item_activated)
        self.file_list.itemClicked.connect(self.on_item_clicked)
        self.file_list.customContextMenuRequested.connect(
            self.show_context_menu
        )

    # ===== Ссылки папка↔предмет =====

    def _linked_rows(self):
        return self.db.query(
            """
            SELECT lf.path, lf.display_name, s.name AS subject_name
            FROM linked_folders lf
            LEFT JOIN subjects s ON s.id = lf.subject_id
            """
        )

    def _upsert_link(self, path: Path, display_name: str, subject_id):
        self.db.execute(
            """
            INSERT INTO linked_folders (path, display_name, subject_id)
            VALUES (?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                display_name = excluded.display_name,
                subject_id = excluded.subject_id
            """,
            (str(path), display_name, subject_id),
        )

    # ===== Корень =====

    def change_root(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Выбрать основную папку"
        )

        if not directory:
            return

        self.root = Path(directory).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

        self.db.execute(
            "UPDATE settings SET root_path = ? WHERE id = 1",
            (str(self.root),),
        )

        self.navigate(self.root)

    # ===== Навигация (с фиксом выхода из сторонних папок) =====

    def _is_inside(self, path: Path) -> bool:
        """True, если путь внутри корня или внутри любой связанной
        сторонней папки."""
        try:
            path.relative_to(self.root)
            return True
        except ValueError:
            pass

        for linked_root in self.linked_roots:
            try:
                path.relative_to(linked_root)
                return True
            except ValueError:
                continue

        return False

    def _up_target(self, path: Path) -> Path:
        """Куда ведёт «Вверх» из данного пути."""
        if path in self.linked_roots:
            return self.root

        parent = path.parent

        if self._is_inside(parent):
            return parent

        return self.root

    def navigate(self, path: Path):
        path = Path(path).resolve()

        if path.is_file():
            path = path.parent

        linked = self._linked_rows()

        self.linked_roots = set()
        linked_by_path = {}

        for row in linked:
            p = Path(row["path"])
            linked_by_path[str(p)] = row

            try:
                p.relative_to(self.root)
            except ValueError:
                self.linked_roots.add(p)

        # Не выпускаем за пределы корня и связанных папок
        if not self._is_inside(path):
            path = self.root

        self.current_path = path
        self.lbl_root.setText(str(self.root))
        self.file_list.clear()

        if path != self.root:
            up_item = QListWidgetItem("..")
            up_item.setData(
                Qt.ItemDataRole.UserRole, str(self._up_target(path))
            )
            up_item.setData(Qt.ItemDataRole.UserRole + 1, "up")
            up_item.setIcon(make_file_icon("folder"))
            self.file_list.addItem(up_item)

        entries = sorted(
            [p for p in path.iterdir() if not p.name.startswith(".")],
            key=lambda p: (p.is_file(), p.name.lower()),
        )

        for entry in entries:
            kind = "dir" if entry.is_dir() else "file"

            item = QListWidgetItem(entry.name)
            item.setData(Qt.ItemDataRole.UserRole, str(entry))
            item.setData(Qt.ItemDataRole.UserRole + 1, kind)

            link = linked_by_path.get(str(entry))
            subject_name = link["subject_name"] if link else None
            item.setData(Qt.ItemDataRole.UserRole + 2, subject_name)

            if subject_name:
                item.setToolTip(f"{entry}\nПредмет: {subject_name}")
            else:
                item.setToolTip(str(entry))

            item.setIcon(make_file_icon(file_kind(entry)))
            self.file_list.addItem(item)

        # Сторонние папки, видимые в корне
        if path == self.root:
            for row in linked:
                p = Path(row["path"])

                if not p.exists():
                    continue

                try:
                    p.relative_to(self.root)
                    continue  # уже показана как обычная папка
                except ValueError:
                    pass

                item = QListWidgetItem(row["display_name"])
                item.setData(Qt.ItemDataRole.UserRole, str(p))
                item.setData(Qt.ItemDataRole.UserRole + 1, "dir")
                item.setData(
                    Qt.ItemDataRole.UserRole + 2, row["subject_name"]
                )
                item.setToolTip(
                    f"{p}\nПредмет: {row['subject_name'] or '—'}"
                )
                item.setIcon(make_file_icon("folder"))
                self.file_list.addItem(item)

    def go_up(self):
        if self.current_path == self.root:
            return

        self.navigate(self._up_target(self.current_path))

    # ===== Действия с элементами =====

    def on_item_activated(self, item: QListWidgetItem):
        path = Path(item.data(Qt.ItemDataRole.UserRole))

        if not path.exists():
            self.navigate(self.current_path)
            return

        if path.is_dir():
            self.navigate(path)
        else:
            self.open_external(path)

    def on_item_clicked(self, item: QListWidgetItem):
        path = Path(item.data(Qt.ItemDataRole.UserRole))

        if not path.exists():
            self.navigate(self.current_path)
            return

        subject_name = item.data(Qt.ItemDataRole.UserRole + 2)

        if path.is_dir():
            # Для папки предпросмотр не дублирует нижнюю панель
            self.show_preview_placeholder()
        else:
            self.preview_file(path)

        self.update_info(path, subject_name)

    def show_preview_placeholder(self):
        self.preview_title.setText("Предпросмотр")
        self.preview_title.setToolTip("")
        self.preview_stack.setCurrentWidget(self.preview_placeholder)

    # ===== Нижняя панель информации =====

    def update_info(self, path: Path, subject_name=None):
        icon = make_file_icon(file_kind(path))
        self.lbl_info_icon.setPixmap(icon.pixmap(48, 48))

        if path.is_dir():
            try:
                children = list(path.iterdir())
            except OSError:
                children = []

            files = sum(1 for p in children if p.is_file())
            dirs = sum(1 for p in children if p.is_dir())

            self.lbl_info_name.setText(path.name)

            details = f"Папка. Файлов: {files}, подпапок: {dirs}."

            if subject_name:
                details += f" Предмет: {subject_name}."

            self.lbl_info_details.setText(details)
        else:
            info = QFileInfo(str(path))

            self.lbl_info_name.setText(info.fileName())

            # Размер и дата — следующей строкой после названия
            self.lbl_info_details.setText(
                f"{info.size()} байт. Изменён: "
                f"{info.lastModified().toString('dd.MM.yyyy hh:mm')}."
            )

        self.lbl_info_path.setText(str(path))

    # ===== Контекстное меню =====

    def show_context_menu(self, pos):
        item = self.file_list.itemAt(pos)

        if item is None:
            return

        path = Path(item.data(Qt.ItemDataRole.UserRole))
        kind = item.data(Qt.ItemDataRole.UserRole + 1)

        menu = QMenu(self)

        if kind == "dir":
            act_link = menu.addAction("Связать с предметом…")
            act_unlink = menu.addAction("Убрать связь с предметом")
            menu.addSeparator()
            act_fm = menu.addAction("Открыть в проводнике")

            chosen = menu.exec(
                self.file_list.viewport().mapToGlobal(pos)
            )

            if chosen == act_link:
                self.link_folder(path)
            elif chosen == act_unlink:
                self.unlink_folder(path)
            elif chosen == act_fm:
                self.open_in_file_manager(path)
        else:
            act_open = menu.addAction("Открыть")
            act_fm = menu.addAction("Показать в проводнике")

            chosen = menu.exec(
                self.file_list.viewport().mapToGlobal(pos)
            )

            if chosen == act_open:
                self.open_external(path)
            elif chosen == act_fm:
                self.open_in_file_manager(path)

    def _subjects_list(self):
        return [
            (row["id"], row["name"])
            for row in self.db.query(
                "SELECT id, name FROM subjects ORDER BY name"
            )
        ]

    def link_folder(self, path: Path):
        subjects = self._subjects_list()

        if not subjects:
            QMessageBox.information(
                self,
                "Нет предметов",
                "Сначала создай предметы (вкладка «Расписание» → «Словари»).",
            )
            return

        names = [name for _, name in subjects]

        name, ok = QInputDialog.getItem(
            self,
            "Связать с предметом",
            f"Предмет для папки «{path.name}»:",
            names,
            0,
            False,
        )

        if not ok:
            return

        subject_id = next(
            sid for sid, sname in subjects if sname == name
        )

        self._upsert_link(path, path.name, subject_id)
        self.navigate(self.current_path)
        self.subjectAdded.emit(name)

    def unlink_folder(self, path: Path):
        self.db.execute(
            "DELETE FROM linked_folders WHERE path = ?",
            (str(path),),
        )
        self.navigate(self.current_path)

    def add_subject_folder(self):
        subjects = self._subjects_list()

        if not subjects:
            QMessageBox.information(
                self,
                "Нет предметов",
                "Сначала создай предметы (вкладка «Расписание» → «Словари»).",
            )
            return

        names = [name for _, name in subjects]

        name, ok = QInputDialog.getItem(
            self,
            "Добавить предмет",
            "Предмет:",
            names,
            0,
            False,
        )

        if not ok:
            return

        subject_id = next(
            sid for sid, sname in subjects if sname == name
        )

        folder = self.root / name
        folder.mkdir(parents=True, exist_ok=True)

        self._upsert_link(folder, name, subject_id)

        self.navigate(self.root)
        self.subjectAdded.emit(name)

    def add_external_folder(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Выбрать стороннюю папку"
        )

        if not directory:
            return

        path = Path(directory).resolve()

        dialog = AddExternalFolderDialog(
            path.name, self._subjects_list(), self
        )

        if not dialog.exec():
            return

        display_name, subject_id = dialog.result_data()

        self._upsert_link(path, display_name, subject_id)

        self.navigate(self.root)

        if subject_id:
            rows = self.db.query(
                "SELECT name FROM subjects WHERE id = ?",
                (subject_id,),
            )
            if rows:
                self.subjectAdded.emit(rows[0]["name"])

    # ===== Предпросмотр =====

    def preview_file(self, path: Path):
        suffix = path.suffix.lower()

        self.preview_title.setText(path.name)
        self.preview_title.setToolTip(path.name)

        if suffix == ".pdf" and self.preview_pdf is not None:
            try:
                self._pdf_doc.load(str(path))
                self.preview_pdf.setDocument(self._pdf_doc)
                self.preview_stack.setCurrentWidget(self.preview_pdf)
                return
            except Exception as e:
                self.preview_text.setPlainText(
                    f"Не удалось открыть PDF:\n{e}"
                )
                self.preview_stack.setCurrentWidget(self.preview_text)
                return

        if suffix in self.IMAGE_EXTS:
            pixmap = QPixmap(str(path))

            if pixmap.isNull():
                self.preview_text.setPlainText(
                    "Не удалось загрузить изображение."
                )
                self.preview_stack.setCurrentWidget(self.preview_text)
            else:
                self._current_pixmap = pixmap
                self.preview_stack.setCurrentWidget(self.preview_image)
                # Сразу пробуем пересчитать и ещё раз —
                # после того, как layout раздаст реальные размеры
                self._rescale_image()
                QTimer.singleShot(0, self._rescale_image)
            return

        if self.is_text_like(path):
            self.preview_text.setPlainText(self.read_text(path))
            self.preview_stack.setCurrentWidget(self.preview_text)
            return

        info = QFileInfo(str(path))

        text = (
            f"Файл: {info.fileName()}\n"
            f"Путь: {info.absoluteFilePath()}\n"
            f"Размер: {info.size()} байт\n\n"
            "Предпросмотр для этого типа не поддерживается.\n"
            "Двойной клик откроет файл в приложении по умолчанию."
        )
        self.preview_text.setPlainText(text)
        self.preview_stack.setCurrentWidget(self.preview_text)

    def cleanup_pdf(self):
        """
        Безопасно освобождает PDF-объекты перед выходом:
        сначала уничтожается вью, затем документ.
        Без setDocument(None) — нет warning про nullptr,
        а порядок уничтожения исключает segfault.
        """
        if not HAS_PDF:
            return

        # 1) Убираем и уничтожаем вью
        try:
            if self.preview_pdf is not None:
                self.preview_stack.removeWidget(self.preview_pdf)
                self.preview_pdf.hide()
                self.preview_pdf.deleteLater()
                self.preview_pdf = None
        except RuntimeError:
            pass

        # Даём вью реально уничтожиться до документа
        QApplication.processEvents()

        # 2) Теперь уничтожаем документ
        try:
            if self._pdf_doc is not None:
                self._pdf_doc.deleteLater()
                self._pdf_doc = None
        except RuntimeError:
            pass

    def is_text_like(self, path: Path) -> bool:
        suffix = path.suffix.lower()
        return suffix in self.TEXT_EXTS or suffix in self.OFFICE_EXTS

    def read_text(self, path: Path) -> str:
        suffix = path.suffix.lower()

        if suffix in self.OFFICE_EXTS:
            return self.extract_office_text(path)

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                data = f.read(2_000_000)

            if len(data) == 2_000_000:
                data += "\n\n[Файл слишком большой, показаны первые 2 МБ]"

            return data
        except Exception as e:
            return f"Не удалось прочитать файл:\n{e}"

    def extract_office_text(self, path: Path) -> str:
        suffix = path.suffix.lower()

        try:
            import zipfile
            from xml.etree import ElementTree as ET

            if suffix == ".docx":
                with zipfile.ZipFile(path) as z:
                    data = z.read("word/document.xml")

                root = ET.fromstring(data)
                ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

                paragraphs = []

                for p in root.iter(f"{ns}p"):
                    texts = [t.text or "" for t in p.iter(f"{ns}t")]
                    paragraphs.append("".join(texts))

                return "\n".join(paragraphs)

            if suffix == ".odt":
                with zipfile.ZipFile(path) as z:
                    data = z.read("content.xml")

                root = ET.fromstring(data)
                texts = []

                for elem in root.iter():
                    if elem.text and elem.text.strip():
                        texts.append(elem.text.strip())
                    if elem.tail and elem.tail.strip():
                        texts.append(elem.tail.strip())

                return "\n".join(texts)

        except Exception as e:
            return f"Не удалось извлечь текст из офисного файла:\n{e}"

        return ""

    def open_external(self, path: Path):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def open_in_file_manager(self, path: Path):
        """Универсально: системный проводник по умолчанию
        (Проводник Windows, Finder, Nautilus/Thunar и т.д.)."""
        target = path if path.is_dir() else path.parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def eventFilter(self, obj, event):
        # При любом изменении размера области предпросмотра
        # пересчитываем картинку под новые границы
        if (
            obj is self.preview_image
            and event.type() == QEvent.Type.Resize
        ):
            self._rescale_image()

        return super().eventFilter(obj, event)

    def _rescale_image(self):
        if self._current_pixmap is None or self._current_pixmap.isNull():
            return

        target = self.preview_image.size()

        if target.width() < 50 or target.height() < 50:
            return

        scaled = self._current_pixmap.scaled(
            target - QSize(12, 12),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.preview_image.setPixmap(scaled)
