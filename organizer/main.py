import sys
import subprocess
from pathlib import Path

from schedule_tab import ScheduleTab
from library_tab import LibraryTab
from week_overview_tab import WeekOverviewTab
from assignments_material_tab import AssignmentsMaterialTab
from files_material_tab import FilesMaterialTab
from week_grid_tab import WeekGridTab
from icons import make_icon

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QPlainTextEdit,
    QLabel,
    QPushButton,
    QLineEdit,
    QMessageBox,
    QStackedWidget,
    QStyle,
    QListView,
    QAbstractItemView,
    QFileIconProvider,
    QCalendarWidget,
    QDateEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMenu,
    QFrame,
    QStackedWidget,
)
from PySide6.QtCore import Qt, QUrl, QFileInfo, QSize, Signal, QDate, QPropertyAnimation, QEasingCurve, QVariantAnimation
from PySide6.QtGui import QDesktopServices, QPixmap, QColor, QBrush, QPainter, QPen, QPainterPath

try:
    from PySide6.QtPdfWidgets import QPdfView
    HAS_PDF = True
except Exception:
    HAS_PDF = False

from organizer_db import Database
from pathlib import Path

db = Database(Path.home() / ".semester_organizer" / "organizer.db")
db.execute(
    """
    UPDATE settings
    SET semester_start = '2026-08-31',
        semester_end = '2027-01-30',
        numerator_reference = '2026-08-31'
    WHERE id = 1
    """
)

LONGHORN_QSS = """
/* ===== База ===== */
* {
    background-color: #F5F7FA;
    color: #1A1C1E;
}

QMainWindow, QDialog, QWidget {
    background-color: #F5F7FA;
    color: #1A1C1E;
}

QFrame, QStackedWidget, QScrollArea, QSplitter {
    background-color: #F5F7FA;
}

QLabel {
    background-color: transparent;
    color: #1A1C1E;
}

/* ===== Поля ввода ===== */
QPlainTextEdit, QTextEdit, QLineEdit, QDateEdit, QSpinBox, QTimeEdit, QComboBox {
    background-color: #FFFFFF;
    color: #1A1C1E;
    border: 1px solid #DADCE0;
    border-radius: 14px;
    padding: 8px 12px;
    selection-background-color: #D3E3FD;
    selection-color: #001D35;
}

/* ===== Списки и таблицы ===== */
QListWidget, QTreeWidget, QTableWidget, QCalendarWidget {
    background-color: #FFFFFF;
    alternate-background-color: #F8F9FA;
    color: #1A1C1E;
    border: 1px solid #DADCE0;
    border-radius: 18px;
    gridline-color: #E8EAED;
}

QHeaderView::section {
    background-color: #F1F3F6;
    color: #5F6368;
    border: none;
    border-bottom: 1px solid #DADCE0;
    padding: 8px 10px;
    font-weight: 700;
}

/* ===== Кнопки ===== */
QPushButton {
    background-color: #E8EDF5;
    color: #1A1C1E;
    border: 1px solid #9FB2C8;
    border-radius: 16px;
    padding: 9px 18px;
    font-weight: 700;
}

QPushButton:hover {
    background-color: #DDE3ED;
}

QPushButton:pressed {
    background-color: #D0D7E2;
}

QPushButton:default {
    background-color: #0061A4;
    color: #FFFFFF;
    border: none;
}

/* ===== Меню, скроллбары, чекбоксы, тултипы ===== */
QMenu {
    background-color: #FFFFFF;
    border: 1px solid #DADCE0;
    border-radius: 16px;
    padding: 6px;
}

QMenu::item {
    padding: 8px 18px;
    border-radius: 12px;
    color: #1A1C1E;
}

QMenu::item:selected {
    background-color: #D3E3FD;
    color: #001D35;
}

QScrollBar:vertical, QScrollBar:horizontal {
    background-color: transparent;
}

QScrollBar::handle:vertical {
    background-color: #DADCE0;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:horizontal {
    background-color: #DADCE0;
    border-radius: 5px;
    min-width: 30px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #5F6368;
    border-radius: 6px;
    background-color: #FFFFFF;
}

QCheckBox::indicator:checked {
    background-color: #0061A4;
    border-color: #0061A4;
}

QToolTip {
    background-color: #D3E3FD;
    color: #001D35;
    border: none;
    padding: 6px 10px;
    border-radius: 10px;
}

/* ===== Навигация ===== */
QFrame#navRail {
    background-color: #EDF0F5;
    border-right: 1px solid #DADCE0;
}

QPushButton#navToggle {
    background-color: #E8EDF5;
    border: 2px solid #8FA6C0;
    border-radius: 12px;
}

QPushButton#navToggle:hover {
    background-color: #DDE3ED;
}

QPushButton#navItem {
    background-color: #E8EDF5;
    border: 2px solid #B9C8DC;
    border-radius: 24px;
    min-height: 48px;
    padding: 0px 16px;
    text-align: left;
    color: #1A1C1E;
    font-size: 14px;
    font-weight: 600;
}

QPushButton#navItem:hover {
    background-color: #DDE3ED;
}

QPushButton#navItem:checked {
    background-color: #D3E3FD;
    border: 2px solid #7FA7D9;
    color: #041E49;
}

QPushButton#navItem[collapsed="true"] {
    padding: 0px;
    text-align: center;
    font-size: 18px;
}

QLabel#appTitle {
    font-size: 20px;
    font-weight: 800;
    color: #0061A4;
}

QLabel#topAppBarTitle, QLabel#pageTitle, QLabel#weekTitle {
    font-size: 24px;
    font-weight: 800;
    color: #1A1C1E;
}

QLabel#weekSubtitle, QLabel#daySubtitle, QLabel#slotMeta,
QLabel#assignmentMeta, QLabel#assignmentDate, QLabel#pathLabel {
    color: #5F6368;
}

QWidget#contentArea, QStackedWidget#contentStack {
    background-color: #F5F7FA;
}

/* ===== Карточки ===== */
QFrame#dayCard, QFrame#assignmentCard, QFrame#fileCard,
QFrame#previewCard, QFrame#slotCard, QFrame#card {
    background-color: #FFFFFF;
    border: 1px solid #DADCE0;
    border-radius: 20px;
}

QFrame#dayCard[today="true"] {
    border: 2px solid #0061A4;
}

QFrame#slotCard:hover, QFrame#fileCard:hover, QFrame#assignmentCard:hover {
    border-color: #0061A4;
    background-color: #F8F9FA;
}

QLabel#slotTime, QLabel#assignmentKind, QLabel#assignmentFiles,
QPushButton#textButton {
    color: #0061A4;
}

QLabel#slotSubject, QLabel#dayTitle, QLabel#assignmentTitle,
QLabel#fileName, QLabel#previewTitle {
    color: #1A1C1E;
    font-weight: 700;
}

QPushButton#iconButton {
    background-color: #E8EDF5;
    border-radius: 24px;
    padding: 7px 14px;
}

QPushButton#fabButton {
    background-color: #0061A4;
    color: #FFFFFF;
    border: none;
    border-radius: 28px;
    font-size: 28px;
    font-weight: 700;
}

QPushButton#fabButton:hover {
    background-color: #1A73E8;
}

QPushButton#textButtonDanger {
    border: none;
    color: #D93025;
}

QPushButton#textButtonDanger:hover {
    background-color: #FCE8E6;
}

QPushButton#filterChip {
    background-color: #E8EDF5;
    border: 1px solid #DADCE0;
    border-radius: 24px;
    padding: 8px 18px;
    color: #5F6368;
    font-weight: 600;
}

QPushButton#filterChip:hover {
    background-color: #DDE3ED;
}

QPushButton#assignmentItem {
    background-color: #E8EDF5;
    border: none;
    border-radius: 14px;
    padding: 10px 12px;
    text-align: left;
    color: #1A1C1E;
    font-weight: 600;
}

QPushButton#assignmentItem:hover {
    background-color: #DDE3ED;
}

QPlainTextEdit#previewText {
    background-color: #F8F9FA;
    border: 1px solid #E8EAED;
    border-radius: 12px;
    font-family: monospace;
    font-size: 12px;
}

QLabel#emptyLabel {
    color: #9AA0A6;
    font-style: italic;
}

/* ===== Панель инструментов Обзора ===== */
QPushButton#toolbarButton {
    background-color: #FFFFFF;
    border: 1px solid #8FA6C0;
    border-radius: 20px;
    min-height: 38px;
    padding: 0 16px;
    font-weight: 700;
    color: #14324F;
}

QPushButton#toolbarButton:hover {
    background-color: #EAF2FE;
    border-color: #5B82B0;
}

QPushButton#toolbarButton:pressed {
    background-color: #DCE9FA;
}

QDateEdit#toolbarDate {
    background-color: #FFFFFF;
    border: 1px solid #8FA6C0;
    border-radius: 20px;
    min-height: 38px;
    padding: 0 34px 0 16px;
    font-weight: 700;
    color: #14324F;
}

QDateEdit#toolbarDate:focus {
    border-color: #3B6EA8;
}

/* ===== Таблица Обзора ===== */
QFrame#tableCard {
    background-color: #FFFFFF;
    border: none;
    border-radius: 18px;
}

QTableWidget#weekGrid {
    background: transparent;
    border: none;
    gridline-color: #E4E9F0;
}

QTableWidget#weekGrid::item {
    border: 1px solid #D3DCE8;
}

QTableWidget#weekGrid QHeaderView::section {
    background-color: #DCE9FA;
    color: #0B3B7A;
    font-size: 15px;
    font-weight: 800;
    padding: 10px 8px;
    border: none;
    border-right: 1px solid #C7D7EC;
    border-bottom: 1px solid #C7D7EC;
}

QFrame#cellCard {
    background: transparent;
    border: none;
}

QLabel#cellChip {
    background-color: #F1F3F6;
    color: #3C4043;
    border-radius: 10px;
    padding: 4px 8px;
    font-weight: 600;
    font-size: 12px;
}

/* ===== Всплывающий календарь ===== */
QCalendarWidget, QCalendarWidget QWidget {
    background-color: #FFFFFF;
}

QCalendarWidget QToolButton {
    background-color: #E8EDF5;
    color: #1A1C1E;
    border: 1px solid #9FB2C8;
    border-radius: 24px;
    padding: 6px 12px;
}

QCalendarWidget QToolButton:hover {
    background-color: #DDE3ED;
}

QCalendarWidget QSpinBox {
    background-color: #FFFFFF;
    border: 1px solid #DADCE0;
    border-radius: 8px;
}

QCalendarWidget QHeaderView,
QCalendarWidget QHeaderView::section {
    background-color: #DCE9FA;
    color: #0B3B7A;
    font-weight: 800;
    border: none;
    padding: 6px 4px;
}

QCalendarWidget QAbstractItemView {
    background-color: #FFFFFF;
    color: #1A1C1E;
    selection-background-color: #D3E3FD;
    selection-color: #001D35;
    font-size: 15px;
}

/* ===== Карточки заданий ===== */

QScrollArea#assignmentsScroll {
    background: transparent;
    border: none;
}

QWidget#assignmentsScrollContent {
    background: transparent;
}

QFrame#assignmentCard {
    background-color: #FFFFFF;
    border: 1px solid #DADCE0;
    border-radius: 20px;
}

QFrame#assignmentCard:hover {
    border-color: #7FA7D9;
}

QLabel#assignmentTitle {
    font-size: 16px;
    font-weight: 800;
    color: #1A1C1E;
    background-color: transparent;
    padding: 2px 0;
}

QLabel#assignmentDescription {
    font-size: 13px;
    color: #3C4043;
    background-color: transparent;
}

QLabel#emptyLabel {
    color: #9AA0A6;
    font-style: italic;
    padding: 20px;
}

/* ===== Чекбокс "Выполнено" — фон белый/прозрачный ===== */

QCheckBox#doneCheckbox {
    background-color: transparent;
    color: #1A1C1E;
    font-weight: 600;
    spacing: 8px;
}

QCheckBox#doneCheckbox::indicator {
    width: 20px;
    height: 20px;
    border: 2px solid #5F6368;
    border-radius: 6px;
    background-color: #FFFFFF;
}

QCheckBox#doneCheckbox::indicator:hover {
    border-color: #0061A4;
}

QCheckBox#doneCheckbox::indicator:checked {
    background-color: #0061A4;
    border-color: #0061A4;
}

/* ===== Основные кнопки (добавить работу) ===== */

QPushButton#primaryButton {
    background-color: #0061A4;
    color: #FFFFFF;
    border: none;
    border-radius: 24px;
    padding: 10px 22px;
    font-size: 14px;
    font-weight: 800;
    min-height: 40px;
}

QPushButton#primaryButton:hover {
    background-color: #1A73E8;
}

QPushButton#primaryButton:pressed {
    background-color: #004A7F;
}

/* ===== Цветные чипы категорий ===== */

/* Все */
QPushButton#filterChip_all {
    background-color: #F1F3F6;
    color: #3C4043;
    border: 2px solid #C7D1DC;
    border-radius: 24px;
    padding: 8px 18px;
    font-weight: 700;
    font-size: 13px;
}
QPushButton#filterChip_all:hover {
    background-color: #E8EAED;
}
QPushButton#filterChip_all:checked {
    background-color: #3C4043;
    color: #FFFFFF;
    border-color: #1A1C1E;
}

/* Домашние */
QPushButton#filterChip_homework {
    background-color: #E8F0FE;
    color: #174EA6;
    border: 2px solid #AECBFA;
    border-radius: 24px;
    padding: 8px 18px;
    font-weight: 700;
    font-size: 13px;
}
QPushButton#filterChip_homework:hover {
    background-color: #D2E3FC;
}
QPushButton#filterChip_homework:checked {
    background-color: #174EA6;
    color: #FFFFFF;
    border-color: #0B3B7A;
}

/* Контрольные */
QPushButton#filterChip_control {
    background-color: #FCE8E6;
    color: #C5221F;
    border: 2px solid #F5B8B4;
    border-radius: 24px;
    padding: 8px 18px;
    font-weight: 700;
    font-size: 13px;
}
QPushButton#filterChip_control:hover {
    background-color: #F8D2CF;
}
QPushButton#filterChip_control:checked {
    background-color: #C5221F;
    color: #FFFFFF;
    border-color: #8C1B18;
}

/* Тесты */
QPushButton#filterChip_test {
    background-color: #E6F4EA;
    color: #137333;
    border: 2px solid #A8DAB5;
    border-radius: 24px;
    padding: 8px 18px;
    font-weight: 700;
    font-size: 13px;
}
QPushButton#filterChip_test:hover {
    background-color: #CEEAD6;
}
QPushButton#filterChip_test:checked {
    background-color: #137333;
    color: #FFFFFF;
    border-color: #0C5424;
}

/* Невыполненные */
QPushButton#filterChip_uncompleted {
    background-color: #FEF7E0;
    color: #B06000;
    border: 2px solid #F9D28E;
    border-radius: 24px;
    padding: 8px 18px;
    font-weight: 700;
    font-size: 13px;
}
QPushButton#filterChip_uncompleted:hover {
    background-color: #FDEEB8;
}
QPushButton#filterChip_uncompleted:checked {
    background-color: #B06000;
    color: #FFFFFF;
    border-color: #7A4300;
}

/* Сегодня */
QPushButton#filterChip_today {
    background-color: #F3E8FD;
    color: #7627BB;
    border: 2px solid #D0B4F2;
    border-radius: 24px;
    padding: 8px 18px;
    font-weight: 700;
    font-size: 13px;
}
QPushButton#filterChip_today:hover {
    background-color: #E8D5F7;
}
QPushButton#filterChip_today:checked {
    background-color: #7627BB;
    color: #FFFFFF;
    border-color: #4E1A80;
}

/* Эта неделя */
QPushButton#filterChip_week {
    background-color: #E0F7FA;
    color: #007B8A;
    border: 2px solid #80DEEA;
    border-radius: 24px;
    padding: 8px 18px;
    font-weight: 700;
    font-size: 13px;
}
QPushButton#filterChip_week:hover {
    background-color: #B2EBF2;
}
QPushButton#filterChip_week:checked {
    background-color: #007B8A;
    color: #FFFFFF;
    border-color: #004D57;
}

/* ===== Расписание: стиль таблиц как в Обзоре ===== */

QTableWidget#schedTable,
QTableWidget#schedPreview {
    background: transparent;
    border: none;
    gridline-color: #E4E9F0;
}

QTableWidget#schedTable::item,
QTableWidget#schedPreview::item {
    border: none;
    padding: 6px;
}

/* Выделение строк — цветом, а не границей */
QTableWidget#schedTable::item:selected,
QTableWidget#schedPreview::item:selected {
    background-color: #D3E3FD;
    color: #041E49;
}

/* Слегка синеватые заголовки */
QTableWidget#schedTable QHeaderView::section,
QTableWidget#schedPreview QHeaderView::section {
    background-color: #DCE9FA;
    color: #0B3B7A;
    font-size: 15px;
    font-weight: 800;
    padding: 10px 8px;
    border: none;
    border-right: 1px solid #C7D7EC;
    border-bottom: 1px solid #C7D7EC;
}
"""

# ===== Генерация вспомогательных иконок =====
# ВАЖНО: вызывается только ПОСЛЕ создания QApplication.

def _save_icon_png(path: Path, draw_fn):
    pm = QPixmap(48, 48)
    pm.fill(Qt.GlobalColor.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    draw_fn(p, 48.0)
    p.end()

    pm.save(str(path))


def _draw_chevron(p, s):
    pen = QPen(QColor("#0B3B7A"))
    pen.setWidthF(s * 0.09)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    path = QPainterPath()
    path.moveTo(0.24 * s, 0.38 * s)
    path.lineTo(0.50 * s, 0.64 * s)
    path.lineTo(0.76 * s, 0.38 * s)
    p.drawPath(path)


def _draw_check(p, s):
    pen = QPen(QColor("#FFFFFF"))
    pen.setWidthF(s * 0.10)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    path = QPainterPath()
    path.moveTo(0.28 * s, 0.52 * s)
    path.lineTo(0.44 * s, 0.67 * s)
    path.lineTo(0.72 * s, 0.35 * s)
    p.drawPath(path)


def build_extra_qss() -> str:
    icons_dir = Path.home() / ".semester_organizer" / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    chevron_path = icons_dir / "chevron_dark.png"
    check_path = icons_dir / "check_white.png"

    if not chevron_path.exists():
        _save_icon_png(chevron_path, _draw_chevron)

    if not check_path.exists():
        _save_icon_png(check_path, _draw_check)

    extra = f"""
/* ===== Стрелка-шеврон вместо треугольника ===== */

QDateEdit::drop-down {{
    border: none;
    width: 34px;
    background: #E3EDFB;
    border-radius: 13px;
    margin: 5px 6px;
}}

QDateEdit::down-arrow {{
    border: none;
    width: 16px;
    height: 16px;
    image: url({chevron_path});
}}

QComboBox::drop-down {{
    border: none;
    width: 30px;
}}

QComboBox::down-arrow {{
    border: none;
    width: 16px;
    height: 16px;
    image: url({chevron_path});
}}

/* ===== Галочка в чекбоксах ===== */

QCheckBox::indicator:checked {{
    image: url({check_path});
}}
"""

    extra += """
/* ===== Категории: полные правила со скруглением ===== */

QPushButton#filterChip_all {
    background-color: #F1F3F6; color: #3C4043;
    border: 2px solid #C7D1DC; border-radius: 24px;
    padding: 8px 18px; font-weight: 700; font-size: 13px;
}
QPushButton#filterChip_all:checked {
    background-color: #C7D1DC; color: #1A1C1E; border-color: #5F6368;
}

QPushButton#filterChip_homework {
    background-color: #E8F0FE; color: #174EA6;
    border: 2px solid #AECBFA; border-radius: 24px;
    padding: 8px 18px; font-weight: 700; font-size: 13px;
}
QPushButton#filterChip_homework:checked {
    background-color: #AECBFA; color: #0B3B7A; border-color: #174EA6;
}

QPushButton#filterChip_control {
    background-color: #FCE8E6; color: #C5221F;
    border: 2px solid #F5B8B4; border-radius: 24px;
    padding: 8px 18px; font-weight: 700; font-size: 13px;
}
QPushButton#filterChip_control:checked {
    background-color: #F5B8B4; color: #7A1410; border-color: #C5221F;
}

QPushButton#filterChip_test {
    background-color: #E6F4EA; color: #137333;
    border: 2px solid #A8DAB5; border-radius: 24px;
    padding: 8px 18px; font-weight: 700; font-size: 13px;
}
QPushButton#filterChip_test:checked {
    background-color: #A8DAB5; color: #0C5424; border-color: #137333;
}

QPushButton#filterChip_uncompleted {
    background-color: #FEF7E0; color: #B06000;
    border: 2px solid #F9D28E; border-radius: 24px;
    padding: 8px 18px; font-weight: 700; font-size: 13px;
}
QPushButton#filterChip_uncompleted:checked {
    background-color: #F9D28E; color: #7A4300; border-color: #B06000;
}

QPushButton#filterChip_today {
    background-color: #F3E8FD; color: #7627BB;
    border: 2px solid #D0B4F2; border-radius: 24px;
    padding: 8px 18px; font-weight: 700; font-size: 13px;
}
QPushButton#filterChip_today:checked {
    background-color: #D0B4F2; color: #4E1A80; border-color: #7627BB;
}

QPushButton#filterChip_week {
    background-color: #E0F7FA; color: #007B8A;
    border: 2px solid #80DEEA; border-radius: 24px;
    padding: 8px 18px; font-weight: 700; font-size: 13px;
}
QPushButton#filterChip_week:checked {
    background-color: #80DEEA; color: #004D57; border-color: #007B8A;
}

/* ===== Кнопки действий с границами ===== */

QPushButton#textButton {
    border: 1px solid #8FA6C0;
    border-radius: 24px;
}

QPushButton#textButtonDanger {
    border: 1px solid #E0A9A5;
    border-radius: 24px;
}

/* ===== "Добавить работу": скруглённая, мягкая, заметная ===== */

QPushButton#primaryButton {
    background-color: #D3E3FD;
    color: #0B3B7A;
    border: 2px solid #7FA7D9;
    border-radius: 24px;
    padding: 10px 24px;
    font-size: 16px;
    font-weight: 800;
    min-height: 44px;
}

QPushButton#primaryButton:hover {
    background-color: #C9DCF9;
}

QPushButton#primaryButton:pressed {
    background-color: #BBD3F7;
}

/* ===== Всплывающий календарь (как в Обзоре) ===== */

QCalendarWidget, QCalendarWidget QWidget {
    background-color: #FFFFFF;
}

QCalendarWidget QToolButton {
    background-color: #E8EDF5;
    color: #1A1C1E;
    border: 1px solid #9FB2C8;
    border-radius: 24px;
    padding: 6px 12px;
}

QCalendarWidget QToolButton:hover {
    background-color: #DDE3ED;
}

QCalendarWidget QSpinBox {
    background-color: #FFFFFF;
    border: 1px solid #DADCE0;
    border-radius: 8px;
}

QCalendarWidget QHeaderView,
QCalendarWidget QHeaderView::section {
    background-color: #DCE9FA;
    color: #0B3B7A;
    font-weight: 800;
    border: none;
    padding: 6px 4px;
}

QCalendarWidget QAbstractItemView {
    background-color: #FFFFFF;
    color: #1A1C1E;
    selection-background-color: #D3E3FD;
    selection-color: #001D35;
    font-size: 15px;
}
"""

    return extra

class PlaceholderTab(QWidget):
    def __init__(self, title: str, description: str, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 20px; font-weight: 700;")

        lbl_desc = QLabel(description)
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #AFCBEE; font-size: 13px;")

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_desc)
        layout.addStretch(1)


class FilesTab(QWidget):
    subjectAdded = Signal(str)

    TEXT_EXTS = {
        ".txt", ".md", ".rst", ".py", ".js", ".ts", ".c", ".cpp",
        ".h", ".hpp", ".java", ".json", ".xml", ".html", ".htm",
        ".css", ".csv", ".tsv", ".ini", ".cfg", ".yaml", ".yml",
        ".sql", ".sh", ".bat", ".pro", ".ui",
    }
    OFFICE_EXTS = {".docx", ".odt"}
    IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}

    def __init__(self, root: Path, parent=None):
        super().__init__(parent)

        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.current_path = self.root
        self.icon_provider = QFileIconProvider()

        self._build_ui()
        self.navigate(self.root)

    def _build_ui(self):
        outer = QVBoxLayout(self)

        top = QHBoxLayout()

        self.btn_up = QPushButton("Вверх")
        self.btn_refresh = QPushButton("Обновить")
        self.btn_open_fm = QPushButton("Открыть в Thunar")

        self.edit_subject = QLineEdit()
        self.edit_subject.setPlaceholderText("Имя новой папки предмета")

        self.btn_add_subject = QPushButton("Добавить предмет")

        top.addWidget(self.btn_up)
        top.addWidget(self.btn_refresh)
        top.addWidget(self.btn_open_fm)
        top.addStretch(1)
        top.addWidget(self.edit_subject)
        top.addWidget(self.btn_add_subject)

        self.lbl_path = QLabel("")
        self.lbl_path.setStyleSheet("color: #9FC4FF; padding: 2px;")
        self.lbl_path.setTextInteractionFlags(Qt.TextSelectableByMouse)

        outer.addLayout(top)
        outer.addWidget(self.lbl_path)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.file_list = QListWidget()
        self.file_list.setViewMode(QListView.ViewMode.IconMode)
        self.file_list.setIconSize(QSize(64, 64))
        self.file_list.setGridSize(QSize(115, 105))
        self.file_list.setWordWrap(True)
        self.file_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.file_list.setSpacing(6)
        self.file_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        self.preview_stack = QStackedWidget()

        self.preview_placeholder = QLabel(
            "Выберите файл для предпросмотра.\n"
            "Двойной клик по файлу — открыть в приложении по умолчанию."
        )
        self.preview_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_placeholder.setWordWrap(True)

        self.preview_text = QPlainTextEdit()
        self.preview_text.setReadOnly(True)

        self.preview_image = QLabel()
        self.preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image.setMinimumSize(220, 220)

        self.preview_stack.addWidget(self.preview_placeholder)
        self.preview_stack.addWidget(self.preview_text)
        self.preview_stack.addWidget(self.preview_image)

        if HAS_PDF:
            self.preview_pdf = QPdfView()
            self.preview_stack.addWidget(self.preview_pdf)
        else:
            self.preview_pdf = None

        splitter.addWidget(self.file_list)
        splitter.addWidget(self.preview_stack)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([760, 420])

        outer.addWidget(splitter)

        self.btn_up.clicked.connect(self.go_up)
        self.btn_refresh.clicked.connect(lambda: self.navigate(self.current_path))
        self.btn_open_fm.clicked.connect(
            lambda: self.open_in_file_manager(self.current_path)
        )
        self.btn_add_subject.clicked.connect(self.add_subject_folder)
        self.edit_subject.returnPressed.connect(self.add_subject_folder)

        self.file_list.itemActivated.connect(self.on_item_activated)
        self.file_list.itemClicked.connect(self.on_item_clicked)

    def icon_for(self, path: Path):
        info = QFileInfo(str(path))
        icon = self.icon_provider.icon(info)

        if icon.isNull():
            if path.is_dir():
                icon = self.style().standardIcon(
                    QStyle.StandardPixmap.SP_DirIcon
                )
            else:
                icon = self.style().standardIcon(
                    QStyle.StandardPixmap.SP_FileIcon
                )

        return icon

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
        self.file_list.clear()

        if path != self.root:
            up_item = QListWidgetItem("..")
            up_item.setData(Qt.ItemDataRole.UserRole, str(path.parent))
            up_item.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp)
            )
            self.file_list.addItem(up_item)

        entries = sorted(
            [p for p in path.iterdir() if not p.name.startswith(".")],
            key=lambda p: (p.is_file(), p.name.lower()),
        )

        for entry in entries:
            item = QListWidgetItem(entry.name)
            item.setData(Qt.ItemDataRole.UserRole, str(entry))
            item.setIcon(self.icon_for(entry))
            item.setToolTip(str(entry))
            self.file_list.addItem(item)

    def go_up(self):
        if self.current_path == self.root:
            return

        parent = self.current_path.parent

        try:
            parent.relative_to(self.root)
        except ValueError:
            parent = self.root

        self.navigate(parent)

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

        if path.is_dir():
            self.preview_folder(path)
        else:
            self.preview_file(path)

    def preview_folder(self, path: Path):
        files = [p for p in path.iterdir() if p.is_file()]
        dirs = [p for p in path.iterdir() if p.is_dir()]

        text = (
            f"Папка: {path.name}\n"
            f"Путь: {path}\n\n"
            f"Файлов: {len(files)}\n"
            f"Подпапок: {len(dirs)}\n"
        )

        self.preview_text.setPlainText(text)
        self.preview_stack.setCurrentWidget(self.preview_text)

    def preview_file(self, path: Path):
        suffix = path.suffix.lower()

        if suffix == ".pdf" and self.preview_pdf is not None:
            try:
                self.preview_pdf.load(str(path))
                self.preview_stack.setCurrentWidget(self.preview_pdf)
                return
            except Exception as e:
                self.preview_text.setPlainText(f"Не удалось открыть PDF:\n{e}")
                self.preview_stack.setCurrentWidget(self.preview_text)
                return

        if suffix in self.IMAGE_EXTS:
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                self.preview_text.setPlainText("Не удалось загрузить изображение.")
                self.preview_stack.setCurrentWidget(self.preview_text)
            else:
                target_size = self.preview_image.size()
                if target_size.width() < 50 or target_size.height() < 50:
                    target_size = QSize(700, 500)

                scaled = pixmap.scaled(
                    target_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.preview_image.setPixmap(scaled)
                self.preview_stack.setCurrentWidget(self.preview_image)
            return

        if self.is_text_like(path):
            text = self.read_text(path)
            self.preview_text.setPlainText(text)
            self.preview_stack.setCurrentWidget(self.preview_text)
            return

        info = QFileInfo(str(path))
        text = (
            f"Файл: {info.fileName()}\n"
            f"Путь: {info.absoluteFilePath()}\n"
            f"Размер: {info.size()} байт\n\n"
            "Предпросмотр для этого типа пока не поддерживается.\n"
            "Двойной клик откроет файл в приложении по умолчанию."
        )
        self.preview_text.setPlainText(text)
        self.preview_stack.setCurrentWidget(self.preview_text)

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


class AttendanceTab(QWidget):
    def __init__(self, db: Database, parent=None):
        super().__init__(parent)

        self.db = db
        self._build_ui()
        self.rebuild()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        controls = QHBoxLayout()

        self.date_start = QDateEdit()
        self.date_end = QDateEdit()

        self.date_start.setCalendarPopup(True)
        self.date_end.setCalendarPopup(True)

        today = QDate.currentDate()
        self.date_start.setDate(today.addDays(-30))
        self.date_end.setDate(today.addDays(30))

        self.btn_build = QPushButton("Построить сетку")

        controls.addWidget(QLabel("Начало"))
        controls.addWidget(self.date_start)
        controls.addWidget(QLabel("Конец"))
        controls.addWidget(self.date_end)
        controls.addWidget(self.btn_build)
        controls.addStretch(1)

        self.lbl_info = QLabel(
            "По умолчанию все запланированные пары считаются посещёнными. "
            "Правый клик по ячейке — отметить пропуск, отмену, перенос или доп. пару."
        )
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setStyleSheet("color: #AFCBEE;")

        layout.addLayout(controls)
        layout.addWidget(self.lbl_info)

        self.table = QTableWidget()
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectItems
        )
        self.table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Fixed
        )
        self.table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Fixed
        )

        layout.addWidget(self.table)

        self.btn_build.clicked.connect(self.rebuild)

    def parity_for_date(self, date: QDate) -> str:
        rows = self.db.query(
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

        # Пока опорная дата числителя не задана, считаем все недели числителем.
        return "numerator"

    def rebuild(self):
        start = self.date_start.date()
        end = self.date_end.date()

        if start > end:
            start, end = end, start

        days_count = start.daysTo(end) + 1

        if days_count > 200:
            QMessageBox.information(
                self,
                "Слишком большой диапазон",
                "Для прототипа ограничьтесь 200 днями.",
            )
            return

        subjects = self.db.query(
            "SELECT id, name FROM subjects ORDER BY name"
        )

        dates = []
        d = start
        while d <= end:
            dates.append(d)
            d = d.addDays(1)

        self.table.clear()
        self.table.setRowCount(len(subjects))
        self.table.setColumnCount(len(dates))

        self.table.setHorizontalHeaderLabels(
            [dt.toString("dd.MM") for dt in dates]
        )
        self.table.setVerticalHeaderLabels([s["name"] for s in subjects])

        for row, subject in enumerate(subjects):
            for col, dt in enumerate(dates):
                date_iso = dt.toString("yyyy-MM-dd")
                parity = self.parity_for_date(dt)

                sched = self.db.query(
                    """
                    SELECT COUNT(*) AS c
                    FROM schedule_slots
                    WHERE subject_id = ?
                      AND weekday = ?
                      AND (parity = 'all' OR parity = ?)
                    """,
                    (subject["id"], dt.dayOfWeek(), parity),
                )

                scheduled = bool(sched and sched[0]["c"] > 0)

                marks = self.db.query(
                    """
                    SELECT status
                    FROM attendance_marks
                    WHERE date = ?
                      AND subject_id = ?
                      AND slot_id IS NULL
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (date_iso, subject["id"]),
                )

                if marks:
                    status = marks[0]["status"]
                else:
                    status = "attended" if scheduled else "none"

                item = QTableWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, date_iso)
                item.setData(Qt.ItemDataRole.UserRole + 1, subject["id"])
                item.setData(Qt.ItemDataRole.UserRole + 2, status)

                item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )

                color = self.color_for_status(status, scheduled)
                item.setBackground(QBrush(color))
                item.setForeground(QBrush(QColor(226, 235, 249)))

                if status == "missed":
                    item.setText("Н")
                elif status == "canceled":
                    item.setText("О")
                elif status == "transferred":
                    item.setText("П")
                elif status == "extra":
                    item.setText("Д")
                elif scheduled:
                    item.setText("+")

                self.table.setItem(row, col, item)

        for col in range(len(dates)):
            self.table.setColumnWidth(col, 38)

    def color_for_status(self, status: str, scheduled: bool) -> QColor:
        if status == "missed":
            return QColor(94, 39, 47)

        if status == "canceled":
            return QColor(56, 63, 76)

        if status == "transferred":
            return QColor(92, 80, 37)

        if status == "extra":
            return QColor(30, 76, 91)

        if status == "attended" or scheduled:
            return QColor(34, 67, 108)

        return QColor(21, 28, 41)

    def show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return

        date_iso = item.data(Qt.ItemDataRole.UserRole)
        subject_id = item.data(Qt.ItemDataRole.UserRole + 1)

        menu = QMenu(self)

        def add_action(title: str, status: str):
            action = menu.addAction(title)
            action.triggered.connect(
                lambda checked=False, s=status: self.set_status(
                    date_iso, subject_id, s
                )
            )

        add_action("По умолчанию (авто)", "default")
        add_action("Пропущено", "missed")
        add_action("Отмена", "canceled")
        add_action("Перенос", "transferred")
        add_action("Дополнительная пара", "extra")

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def set_status(self, date_iso: str, subject_id: int, status: str):
        self.db.execute(
            """
            DELETE FROM attendance_marks
            WHERE date = ?
              AND subject_id = ?
              AND slot_id IS NULL
            """,
            (date_iso, subject_id),
        )

        if status != "default":
            self.db.execute(
                """
                INSERT INTO attendance_marks
                    (date, subject_id, slot_id, status, note)
                VALUES (?, ?, NULL, ?, ?)
                """,
                (date_iso, subject_id, status, ""),
            )

        self.rebuild()


class CalendarTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        controls = QHBoxLayout()

        self.lbl_week = QLabel("")
        self.btn_today = QPushButton("Сегодня")

        controls.addWidget(self.lbl_week)
        controls.addStretch(1)
        controls.addWidget(self.btn_today)

        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)

        layout.addLayout(controls)
        layout.addWidget(self.calendar)

        self.calendar.selectionChanged.connect(self.update_week)
        self.btn_today.clicked.connect(
            lambda: self.calendar.setSelectedDate(QDate.currentDate())
        )

        self.update_week()

    def update_week(self):
        date = self.calendar.selectedDate()
        monday = date.addDays(-(date.dayOfWeek() - 1))
        sunday = monday.addDays(6)

        self.lbl_week.setText(
            f"Выбрана неделя: {monday.toString('dd.MM.yyyy')} — "
            f"{sunday.toString('dd.MM.yyyy')}"
        )


class MainWindow(QMainWindow):
    NAV_WIDTH_EXPANDED = 250
    NAV_WIDTH_COLLAPSED = 76

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Органайзер семестра")
        self.resize(1480, 900)
        self.setObjectName("appRoot")

        self.data_dir = Path.home() / ".semester_organizer"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.files_root = self.data_dir / "files"
        self.files_root.mkdir(exist_ok=True)

        self.db = Database(self.data_dir / "organizer.db")

        self.sync_subjects()

        # Страницы
        self.files_tab = FilesTab(self.files_root)

        self.attendance_tab = AttendanceTab(self.db)
        self.schedule_tab = ScheduleTab(self.db)
        self.assignments_tab = AssignmentsMaterialTab(self.db)
        self.week_view_tab = WeekGridTab(self.db)
        self.library_tab = LibraryTab(self.db)
        self.calendar_tab = CalendarTab()

        # Связи
        self.files_tab.subjectAdded.connect(
            lambda name: self.sync_subjects()
        )
        self.files_tab.subjectAdded.connect(
            lambda name: self.schedule_tab.load()
        )
        self.files_tab.subjectAdded.connect(
            lambda name: self.attendance_tab.rebuild()
        )
        self.files_tab.subjectAdded.connect(
            lambda name: self.assignments_tab.reload_subjects()
        )
        self.files_tab.subjectAdded.connect(
            lambda name: self.week_view_tab.refresh()
        )

        self.schedule_tab.saved.connect(lambda: self.sync_subjects())
        self.schedule_tab.saved.connect(
            lambda: self.attendance_tab.rebuild()
        )
        self.schedule_tab.saved.connect(
            lambda: self.assignments_tab.reload_subjects()
        )
        self.schedule_tab.saved.connect(
            lambda: self.week_view_tab.refresh()
        )

        self.assignments_tab.saved.connect(lambda: self.sync_subjects())
        self.assignments_tab.saved.connect(
            lambda: self.assignments_tab.load()
        )
        self.assignments_tab.saved.connect(
            lambda: self.week_view_tab.refresh()
        )

        self.week_view_tab.saved.connect(
            lambda: self.assignments_tab.load()
        )

        self.calendar_tab.calendar.selectionChanged.connect(
            lambda: self.week_view_tab.date_edit.setDate(
                self.calendar_tab.calendar.selectedDate()
            )
        )

        # Корневой виджет
        central = QWidget()
        central.setObjectName("appRoot")

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Левая навигация
        nav = QFrame()
        nav.setObjectName("navRail")
        nav.setFixedWidth(self.NAV_WIDTH_EXPANDED)

        self.nav = nav
        self.nav_collapsed = False
        self._nav_anim = None

        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(14, 20, 14, 20)
        nav_layout.setSpacing(6)

        nav_header = QHBoxLayout()

        self.nav_toggle = QPushButton()
        self.nav_toggle.setObjectName("navToggle")
        self.nav_toggle.setIcon(make_icon("menu"))
        self.nav_toggle.setIconSize(QSize(20, 20))
        self.nav_toggle.setFixedWidth(40)
        self.nav_toggle.setFixedHeight(40)
        self.nav_toggle.setCursor(Qt.PointingHandCursor)
        self.nav_toggle.setToolTip("Свернуть / развернуть панель")
        self.nav_toggle.clicked.connect(
            lambda checked=False: self.toggle_nav()
        )

        self.app_title = QLabel("Органайзер")
        self.app_title.setObjectName("appTitle")

        nav_header.addWidget(self.nav_toggle)
        nav_header.addWidget(self.app_title, 1)

        nav_layout.addLayout(nav_header)
        nav_layout.addSpacing(16)

        self.stack = QStackedWidget()
        self.stack.setObjectName("contentStack")

        self.nav_buttons = []
        self.nav_meta = []
        self.page_titles = []

        pages = [
            ("home", "Обзор", self.week_view_tab),
            ("tasks", "Задания", self.assignments_tab),
            ("clock", "Расписание", self.schedule_tab),
            ("check", "Посещаемость", self.attendance_tab),
            ("folder", "Файлы", self.files_tab),
            ("book", "Библиотека", self.library_tab),
            ("calendar", "Календарь", self.calendar_tab),
        ]

        for icon_name, title, widget in pages:
            self.stack.addWidget(widget)

            btn = QPushButton(title)
            btn.setObjectName("navItem")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(title)

            btn.setIcon(make_icon(icon_name))
            btn.setIconSize(QSize(22, 22))

            index = len(self.nav_buttons)

            btn.clicked.connect(
                lambda checked=False, idx=index: self.set_page(idx)
            )

            nav_layout.addWidget(btn)

            self.nav_buttons.append(btn)
            self.nav_meta.append((icon_name, title))
            self.page_titles.append(title)

        nav_layout.addStretch(1)

        # Правая часть
        right = QWidget()
        right.setObjectName("contentArea")

        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        top_bar = QFrame()
        top_bar.setObjectName("topAppBar")

        top_layout = QVBoxLayout(top_bar)
        top_layout.setContentsMargins(28, 20, 28, 8)

        self.page_title = QLabel("")
        self.page_title.setObjectName("topAppBarTitle")

        top_layout.addWidget(self.page_title)

        right_layout.addWidget(top_bar)
        right_layout.addWidget(self.stack, 1)

        root_layout.addWidget(nav)
        root_layout.addWidget(right, 1)

        self.setCentralWidget(central)

        self.set_page(0)

    def set_page(self, index: int):
        if index < 0 or index >= len(self.nav_buttons):
            return

        self.stack.setCurrentIndex(index)
        self.page_title.setText(self.page_titles[index])

        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

    def toggle_nav(self):
        if self._nav_anim is not None:
            self._nav_anim.stop()

        self.nav_collapsed = not self.nav_collapsed

        self.update_nav_mode()

        start = self.nav.width()

        target = (
            self.NAV_WIDTH_COLLAPSED
            if self.nav_collapsed
            else self.NAV_WIDTH_EXPANDED
        )

        anim = QVariantAnimation(self)
        anim.setDuration(180)
        anim.setStartValue(start)
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        anim.valueChanged.connect(
            lambda value: self.nav.setFixedWidth(int(value))
        )

        self._nav_anim = anim
        anim.start()

    def update_nav_mode(self):
        for i, btn in enumerate(self.nav_buttons):
            icon_name, label = self.nav_meta[i]

            if self.nav_collapsed:
                btn.setText("")
                btn.setToolTip(label)
            else:
                btn.setText(label)
                btn.setToolTip("")

            btn.setProperty(
                "collapsed",
                "true" if self.nav_collapsed else "false",
            )

            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self.app_title.setVisible(not self.nav_collapsed)

    def sync_subjects(self):
        for path in self.files_root.iterdir():
            if path.is_dir() and not path.name.startswith("."):
                self.db.execute(
                    """
                    INSERT OR IGNORE INTO subjects (name, folder_name)
                    VALUES (?, ?)
                    """,
                    (path.name, path.name),
                )

        self.db.commit()

    def closeEvent(self, event):
        self.db.close()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    base_font = app.font()
    base_font.setPointSize(10)
    app.setFont(base_font)

    # Добавочный QSS (иконки-стрелки, галочка, чипы) —
    # только после создания QApplication!
    LONGHORN_QSS = LONGHORN_QSS + build_extra_qss()

    app.setStyleSheet(LONGHORN_QSS)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
