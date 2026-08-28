from __future__ import annotations

import sqlite3
from pathlib import Path

LESSON_TYPES = [
    ("lecture", "Лекция", "🎓"),
    ("practice", "Практика", "📚"),
    ("lab", "Лабораторная", "🔬"),
    ("other", "Другое", "📌"),
]

LESSON_TYPE_LABELS = {k: label for k, label, _ in LESSON_TYPES}
LESSON_TYPE_ICONS = {k: icon for k, _, icon in LESSON_TYPES}

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    semester_start TEXT,
    semester_end TEXT,
    numerator_reference TEXT,
    my_subgroup INTEGER NOT NULL DEFAULT 0
);

INSERT OR IGNORE INTO settings (id) VALUES (1);

CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    folder_name TEXT
);

CREATE TABLE IF NOT EXISTS schedule_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    weekday INTEGER NOT NULL CHECK (weekday BETWEEN 1 AND 7),
    lesson_no INTEGER NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    teacher TEXT,
    room TEXT,
    parity TEXT NOT NULL DEFAULT 'all'
        CHECK (parity IN ('all', 'numerator', 'denominator')),
    lesson_type TEXT NOT NULL DEFAULT 'lecture',
    subgroup INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS lesson_times (
    lesson_no INTEGER PRIMARY KEY,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attendance_marks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    slot_id INTEGER REFERENCES schedule_slots(id) ON DELETE SET NULL,
    status TEXT NOT NULL
        CHECK (status IN ('attended', 'missed', 'canceled', 'transferred', 'extra')),
    note TEXT
);

CREATE TABLE IF NOT EXISTS assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    slot_id INTEGER REFERENCES schedule_slots(id) ON DELETE SET NULL,
    kind TEXT NOT NULL,
    title TEXT,
    description TEXT,
    done INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS assignment_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    note TEXT
);

CREATE TABLE IF NOT EXISTS library_folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER REFERENCES library_folders(id) ON DELETE CASCADE,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS library_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_id INTEGER NOT NULL REFERENCES library_folders(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    note TEXT
);

CREATE INDEX IF NOT EXISTS idx_schedule_slots_weekday
    ON schedule_slots(weekday, parity);

CREATE INDEX IF NOT EXISTS idx_attendance_date
    ON attendance_marks(date, subject_id);

CREATE INDEX IF NOT EXISTS idx_assignments_date
    ON assignments(date, subject_id);

CREATE TABLE IF NOT EXISTS teachers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

        self._ensure_default_library_folder()

    def _ensure_default_library_folder(self):
        row = self.conn.execute(
            "SELECT COUNT(*) AS c FROM library_folders"
        ).fetchone()

        if row["c"] == 0:
            self.conn.execute(
                "INSERT INTO library_folders (parent_id, name) VALUES (NULL, ?)",
                ("Библиотека",),
            )
            self.conn.commit()

    def execute(self, sql: str, params: tuple = ()):
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    def query(self, sql: str, params: tuple = ()):
        return self.conn.execute(sql, params).fetchall()

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

    def _migrate(self):
        slot_cols = [
            r["name"]
            for r in self.conn.execute("PRAGMA table_info(schedule_slots)")
        ]

        if "lesson_type" not in slot_cols:
            self.conn.execute(
                "ALTER TABLE schedule_slots "
                "ADD COLUMN lesson_type TEXT NOT NULL DEFAULT 'lecture'"
            )

        if "subgroup" not in slot_cols:
            self.conn.execute(
                "ALTER TABLE schedule_slots "
                "ADD COLUMN subgroup INTEGER NOT NULL DEFAULT 0"
            )

        set_cols = [
            r["name"]
            for r in self.conn.execute("PRAGMA table_info(settings)")
        ]

        if "my_subgroup" not in set_cols:
            self.conn.execute(
                "ALTER TABLE settings "
                "ADD COLUMN my_subgroup INTEGER NOT NULL DEFAULT 0"
            )

        if "att_start" not in set_cols:
            self.conn.execute(
                "ALTER TABLE settings ADD COLUMN att_start TEXT"
            )

        if "att_end" not in set_cols:
            self.conn.execute(
                "ALTER TABLE settings ADD COLUMN att_end TEXT"
            )

        self.conn.commit()
