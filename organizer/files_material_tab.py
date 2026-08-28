from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
    QScrollArea,
    QGridLayout,
    QPlainTextEdit,
    QFileDialog,
    QMessageBox,
    QLineEdit,
    QSplitter,
)
from PySide6.QtCore import Qt, QUrl, QFileInfo, QSize, Signal
from PySide6.QtGui import QDesktopServices, QPixmap, QIcon

try:
    from PySide6.QtPdfWidgets import QPdfView
    HAS_PDF = True
except Exception:
    HAS_PDF = False

from organizer_db import Database


FILE_ICONS = {
    ".pdf": "📄",
    ".docx": "📝",
    ".doc": "📝",
    ".odt": "📝",
    ".xlsx": "📊",
    ".xls": "📊",
    ".pptx": "📽️",
    ".ppt": "📽️",
    ".txt": "📃",
    ".md": "📃",
    ".py": "🐍",
    ".js": "⚡",
    ".html": "🌐",
    ".css": "🎨",
    ".json": "📋",
    ".xml": "📋",
    ".png": "🖼️",
    ".jpg": "🖼️",
    ".jpeg": "🖼️",
    ".gif": "🖼️",
    ".bmp": "🖼️",
    ".zip": "📦",
    ".rar": "📦",
    ".7z": "📦",
}

TEXT_EXTS = {
    ".txt", ".md", ".rst", ".py", ".js", ".ts", ".c", ".cpp",
    ".h", ".hpp", ".java", ".json", ".xml", ".html", ".htm",
    ".css", ".csv", ".tsv", ".ini", ".cfg", ".yaml", ".yml",
    ".sql", ".sh", ".bat", ".pro", ".ui",
}

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}

OFFICE_EXTS = {".docx", ".odt"}


def get_file_icon(path: Path) -> str:
    if path.is_dir():
        return "📁"
    return FILE_ICONS.get(path.suffix.lower(), "📄")


class FilesMaterialTab(QWidget):
    """
    Material You-версия файлового менеджера:
    - карточки папок и файлов;
    - боковая панель предпросмотра;
    - кнопки навигации.
    """

    subjectAdded = Signal(str)

    def __init__(self, root: Path, parent=None):
        super().__init__(parent)

        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.current_path = self.root

        self._build_ui()
        self.navigate(self.root)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(14)

        # Заголовок
        header = QHBoxLayout()

        title = QLabel("Файлы")
        title.setObjectName("pageTitle")

        header.addWidget(title)
        header.addStretch(1)

        layout.addLayout(header)

        # Панель навигации
        nav_bar = QHBoxLayout()
        nav_bar.setSpacing(8)

        self.btn_up = QPushButton("← Вверх")
        self.btn_up.setObjectName("iconButton")

        self.btn_refresh = QPushButton("⟳ Обновить")
        self.btn_refresh.setObjectName("iconButton")

        self.btn_open_fm = QPushButton("📂 Открыть в Thunar")
        self.btn_open_fm.setObjectName("iconButton")

        nav_bar.addWidget(self.btn_up)
        nav_bar.addWidget(self.btn_refresh)
        nav_bar.addWidget(self.btn_open_fm)
        nav_bar.addStretch(1)

        # Поле добавления предмета
        self.edit_subject = QLineEdit()
        self.edit_subject.setPlaceholderText("Имя нового предмета")
        self.edit_subject.setFixedWidth(200)

        self.btn_add_subject = QPushButton("+ Добавить предмет")
        self.btn_add_subject.setObjectName("textButton")

        nav_bar.addWidget(self.edit_subject)
        nav_bar.addWidget(self.btn_add_subject)

        layout.addLayout(nav_bar)

        # Текущий путь
        self.lbl_path = QLabel("")
        self.lbl_path.setObjectName("pathLabel")
        self.lbl_path.setTextInteractionFlags(Qt.TextSelectableByMouse)

        layout.addWidget(self.lbl_path)

        # Основная область: контент + предпросмотр
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Левая часть: карточки файлов
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("filesScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("filesScrollContent")

        self.grid_layout = QGridLayout(self.scroll_content)
        self.grid_layout.setContentsMargins(0, 0, 12, 0)
        self.grid_layout.setSpacing(12)

        self.scroll.setWidget(self.scroll_content)

        left_layout.addWidget(self.scroll)

        # Правая часть: предпросмотр
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.preview_card = QFrame()
        self.preview_card.setObjectName("previewCard")

        preview_layout = QVBoxLayout(self.preview_card)
        preview_layout.setContentsMargins(16, 16, 16, 16)

        self.preview_title = QLabel("Предпросмотр")
        self.preview_title.setObjectName("previewTitle")

        self.preview_content = QPlainTextEdit()
        self.preview_content.setReadOnly(True)
        self.preview_content.setObjectName("previewText")

        self.preview_image = QLabel()
        self.preview_image.setObjectName("previewImage")
        self.preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image.setMinimumSize(200, 200)

        self.preview_pdf = None

        preview_layout.addWidget(self.preview_title)
        preview_layout.addWidget(self.preview_content)
        preview_layout.addWidget(self.preview_image)

        if HAS_PDF:
            self.preview_pdf = QPdfView()
            preview_layout.addWidget(self.preview_pdf)

        right_layout.addWidget(self.preview_card)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([600, 400])

        layout.addWidget(splitter, 1)

        # Сигналы
        self.btn_up.clicked.connect(self.go_up)
        self.btn_refresh.clicked.connect(lambda: self.navigate(self.current_path))
        self.btn_open_fm.clicked.connect(
            lambda: self.open_in_file_manager(self.current_path)
        )
        self.btn_add_subject.clicked.connect(self.add_subject_folder)
        self.edit_subject.returnPressed.connect(self.add_subject_folder)

    def navigate(self, path: Path):
        path = Path(path).resolve()

        if path.is_file():
            path = path.parent

        try:
            path.relative_to(self.root)
        except ValueError:
            if path != self.root and self.root not in path.parents:
                path = self.root

        self.current_path = path
        self.lbl_path.setText(str(path))

        self.clear_grid()

        entries = sorted(
            [p for p in path.iterdir() if not p.name.startswith(".")],
            key=lambda p: (p.is_file(), p.name.lower()),
        )

        row = 0
        col = 0
        max_cols = 4

        for entry in entries:
            card = self.create_file_card(entry)
            self.grid_layout.addWidget(card, row, col)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        # Добавляем растяжку в конец
        self.grid_layout.setRowStretch(row + 1, 1)

    def clear_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

    def create_file_card(self, path: Path) -> QFrame:
        card = QFrame()
        card.setObjectName("fileCard")
        card.setCursor(Qt.PointingHandCursor)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(8)

        # Иконка
        icon = QLabel(get_file_icon(path))
        icon.setObjectName("fileIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Название
        name = QLabel(path.name)
        name.setObjectName("fileName")
        name.setWordWrap(True)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card_layout.addWidget(icon)
        card_layout.addWidget(name)

        # Клик для открытия/предпросмотра
        card.mousePressEvent = lambda event, p=path: self.on_card_click(p)
        card.mouseDoubleClickEvent = lambda event, p=path: self.on_card_double_click(p)

        return card

    def on_card_click(self, path: Path):
        if path.is_dir():
            self.preview_folder(path)
        else:
            self.preview_file(path)

    def on_card_double_click(self, path: Path):
        if path.is_dir():
            self.navigate(path)
        else:
            self.open_external(path)

    def go_up(self):
        if self.current_path == self.root:
            return

        parent = self.current_path.parent

        try:
            parent.relative_to(self.root)
        except ValueError:
            parent = self.root

        self.navigate(parent)

    def preview_folder(self, path: Path):
        files = [p for p in path.iterdir() if p.is_file()]
        dirs = [p for p in path.iterdir() if p.is_dir()]

        text = (
            f"Папка: {path.name}\n"
            f"Путь: {path}\n\n"
            f"Файлов: {len(files)}\n"
            f"Подпапок: {len(dirs)}\n"
        )

        self.preview_title.setText(f"📁 {path.name}")
        self.preview_content.setPlainText(text)
        self.preview_content.setVisible(True)
        self.preview_image.setVisible(False)

        if self.preview_pdf:
            self.preview_pdf.setVisible(False)

    def preview_file(self, path: Path):
        suffix = path.suffix.lower()

        self.preview_title.setText(f"{get_file_icon(path)} {path.name}")

        if suffix == ".pdf" and self.preview_pdf is not None:
            try:
                self.preview_pdf.load(str(path))
                self.preview_pdf.setVisible(True)
                self.preview_content.setVisible(False)
                self.preview_image.setVisible(False)
                return
            except Exception as e:
                self.preview_content.setPlainText(f"Не удалось открыть PDF:\n{e}")
                self.preview_content.setVisible(True)
                self.preview_image.setVisible(False)
                self.preview_pdf.setVisible(False)
                return

        if suffix in IMAGE_EXTS:
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self.preview_image.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.preview_image.setPixmap(scaled)
                self.preview_image.setVisible(True)
                self.preview_content.setVisible(False)
                if self.preview_pdf:
                    self.preview_pdf.setVisible(False)
                return

        if self.is_text_like(path):
            text = self.read_text(path)
            self.preview_content.setPlainText(text)
            self.preview_content.setVisible(True)
            self.preview_image.setVisible(False)
            if self.preview_pdf:
                self.preview_pdf.setVisible(False)
            return

        info = QFileInfo(str(path))
        text = (
            f"Файл: {info.fileName()}\n"
            f"Путь: {info.absoluteFilePath()}\n"
            f"Размер: {info.size()} байт\n\n"
            "Предпросмотр для этого типа пока не поддерживается.\n"
            "Двойной клик откроет файл в приложении по умолчанию."
        )
        self.preview_content.setPlainText(text)
        self.preview_content.setVisible(True)
        self.preview_image.setVisible(False)
        if self.preview_pdf:
            self.preview_pdf.setVisible(False)

    def is_text_like(self, path: Path) -> bool:
        suffix = path.suffix.lower()
        return suffix in TEXT_EXTS or suffix in OFFICE_EXTS

    def read_text(self, path: Path) -> str:
        suffix = path.suffix.lower()

        if suffix in OFFICE_EXTS:
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
        target = path if path.is_dir() else path.parent

        try:
            subprocess.Popen(["thunar", str(target)])
        except Exception:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def add_subject_folder(self):
        name = self.edit_subject.text().strip()
        name = name.replace("/", "_").replace("\\", "_")

        if not name:
            return

        target = self.root / name

        try:
            if target.exists():
                QMessageBox.information(
                    self,
                    "Папка уже существует",
                    f"Папка уже существует:\n{target}",
                )
            else:
                target.mkdir(parents=False)
                QMessageBox.information(
                    self,
                    "Папка создана",
                    f"Создана папка предмета:\n{target}",
                )
                self.subjectAdded.emit(name)

            self.edit_subject.clear()
            self.navigate(self.root)

        except Exception as e:
            QMessageBox.warning(self, "Ошибка", str(e))
