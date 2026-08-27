import sys, json, math, re, uuid, time, traceback, zipfile
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QDialog, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit, QTextEdit, QPushButton, QMenu, QFileDialog,
    QColorDialog, QMessageBox, QSlider, QSpinBox)
from PyQt5.QtCore import Qt, QRectF, QPointF, QTimer, QEvent
from PyQt5.QtGui import (QPainter, QPen, QBrush, QColor, QFont, QFontMetrics, QPainterPath,
    QImage, QCursor)

COLORS = ["#5C6BC0", "#FF8A65", "#AB47BC", "#26A69A",
          "#E53935", "#1E88E5", "#43A047", "#FB8C00"]
NOTE_HELP = ("Оформление:  # заголовок · ## подзаголовок · - пункт · "
             "**жирный** · *курсив* · > вправо · = по центру")

def rich_lines(text):
    for raw in str(text).split("\n"):
        align, mul, lbold, bullet, line = "left", 1.0, False, False, raw
        if line.startswith("## "):   mul, lbold, line = 1.15, True, line[3:]
        elif line.startswith("# "):  mul, lbold, line = 1.3, True, line[2:]
        elif line.startswith("- "):  bullet, line = True, line[2:]
        if line.startswith("> "):    align, line = "right", line[2:]
        elif line.startswith("= "):  align, line = "center", line[2:]
        yield align, mul, lbold, bullet, line

def inline_segments(line):
    segs, pos = [], 0
    for m in re.finditer(r"(\*\*\*.+?\*\*\*|\*\*.+?\*\*|\*.+?\*)", line):
        if m.start() > pos: segs.append((line[pos:m.start()], False, False))
        t = m.group(0)
        if t.startswith("***"):   segs.append((t[3:-3], True, True))
        elif t.startswith("**"):  segs.append((t[2:-2], True, False))
        else:                     segs.append((t[1:-1], False, True))
        pos = m.end()
    if pos < len(line): segs.append((line[pos:], False, False))
    return segs or [("", False, False)]

def esc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def dist_seg(px, py, ax, ay, bx, by):
    vx, vy = bx-ax, by-ay
    L = vx*vx + vy*vy
    t = 0 if L == 0 else max(0, min(1, ((px-ax)*vx + (py-ay)*vy) / L))
    return math.hypot(px-(ax+t*vx), py-(ay+t*vy))

class Board(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(400, 300)
        # ---------- пользователи ----------
        self.users_file = Path.home() / "board_users.json"
        if not self.users_file.exists():
            self.users = [{"id": "user1", "name": "user1"}]
            self.current_user = "user1"
            try: self.users_file.write_text(json.dumps({"users": self.users,
                "current": "user1"}, ensure_ascii=False), encoding="utf-8")
            except Exception: pass
            old = Path.home() / "board_data.json"
            new = Path.home() / "board_data_user1.json"
            if old.exists() and not new.exists():
                try: new.write_text(old.read_text(encoding="utf-8"), encoding="utf-8")
                except Exception: pass
        else:
            try:
                d = json.loads(self.users_file.read_text(encoding="utf-8"))
                self.users = d.get("users", [{"id": "user1", "name": "user1"}])
                self.current_user = d.get("current", self.users[0]["name"])
            except Exception:
                self.users = [{"id": "user1", "name": "user1"}]; self.current_user = "user1"
        self.data_file = Path.home() / ("board_data_%s.json" % self.current_user)
        # ---------- состояние ----------
        self.items, self.connections, self.bg_drawings, self.board_content = [], [], [], []
        self.tabs, self.tab = [], None
        self.zoom, self.cam_x, self.cam_y = 1.0, 0.0, 0.0
        self.ui_scale = 1.0
        self.dark = False
        self.perf = False
        self.tool = "pan"
        self.brush_color, self.brush_width = "#000000", 3
        self.cur_path, self.drawing = [], False
        self.selected_id, self.conn_start = None, None
        self.pan_start, self.drag, self.resize = None, None, None
        self.opened = None
        self.imm_tool, self.imm_color, self.imm_width = "draw", "#000000", 2
        self.imm_cam = [0.0, 0.0]
        self.imm_path, self.imm_drawing = [], False
        self.imm_tb_scroll = 0
        self._tabs_scroll = 0
        self._tabs_content_w = 0
        self._tb_content_w = 0
        self._top_off = 0
        self._bar_h = 0
        self._tab_bar_visible = False
        self._tab_bar_anim = None
        self._tab_anim = {}
        self._tab_btns = []
        self._plus_hover = False
        self._plus_geom = None
        self._settings_open = False
        self._settings_anim = None
        self._users_open = False
        self._users_anim = None
        self._user_btns = []
        self._user_rect = None
        self._need_anim = False
        self._fonts = {}
        self._buttons, self._imm_btns = [], []
        self._down_btn = None
        self._anim = {}
        self._open_anim = None
        self._close_anim = None
        self._undo = []
        self._editor = None
        self._menu_open = False
        self._redo = []
        self._tab_close_arm = None
        self._tab_close_t = 0.0
        self._search_open = False
        self._search_btns = []
        self._search_edit = None
        self._search_geom = None
        self._search_results = []
        self._cam_anim = None
        self.settings_file = Path.home() / "board_settings.json"
        try:
            sd = json.loads(self.settings_file.read_text(encoding="utf-8"))
            self.dark = bool(sd.get("dark", False))
            self.ui_scale = float(sd.get("ui_scale", 1.0))
            self.cam_x = float(sd.get("cam_x", 0.0))
            self.cam_y = float(sd.get("cam_y", 0.0))
            self.zoom = float(sd.get("zoom", 1.0))
            self.perf = bool(sd.get("perf", False))
        except Exception:
            pass
        self.P = self._pal()
        self._save_timer = QTimer(); self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._save)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self._load_board()

    # ================= палитра / шрифты =================
    def _pal(self):
        if self.dark:
            return {"bg": "#1E1F2A", "grid": "#4A4C5E", "panel": "#2A2C3A", "panel_out": "#40425A",
                    "text": "#E8E8F0", "label": "#B8BAC8", "shadow": "#12131B",
                    "body": "#2E3040", "area": "#262836", "toolbar": "#2A2C3A",
                    "cell_out": "#4A4C5E", "prev": "#343648", "prev_out": "#4A4C5E",
                    "note_bg": "#4A4630", "note_out": "#8A7D3A", "note_text": "#F0E8C8",
                    "imm_bg": "#23243A", "ring": "#FFD54F"}
        return {"bg": "#FAFAFA", "grid": "#9E9E9E", "panel": "#FFFFFF", "panel_out": "#C9CBD6",
                "text": "#212121", "label": "#555555", "shadow": "#C9CBD6",
                "body": "#FFFFFF", "area": "#FFFFFF", "toolbar": "#FFFFFF",
                "cell_out": "#9E9E9E", "prev": "#F5F5F5", "prev_out": "#D0D0D0",
                "note_bg": "#FFF8E1", "note_out": "#E6C84A", "note_text": "#424242",
                "imm_bg": "#5A5C7A", "ring": "#1A237E"}

    def font(self, size, bold=False, italic=False):
        key = (int(size), bold, italic)
        f = self._fonts.get(key)
        if not f:
            f = QFont("DejaVu Sans", int(size)); f.setBold(bold); f.setItalic(italic)
            self._fonts[key] = f
        return f

    def mw(self, text, size, bold=False, italic=False):
        return QFontMetrics(self.font(size, bold, italic)).horizontalAdvance(str(text))

    def trunc(self, text, max_w, size, bold=False):
        s = str(text)
        if self.mw(s, size, bold) <= max_w: return s
        while len(s) > 1 and self.mw(s + "…", size, bold) > max_w: s = s[:-1]
        return s + "…"

    def s2b(self, sx, sy): return ((sx-self.cam_x)/self.zoom, (sy-self.cam_y)/self.zoom)
    def b2s(self, bx, by): return (bx*self.zoom+self.cam_x, by*self.zoom+self.cam_y)
    def _schedule_save(self): self._save_timer.start(600)
    def _save(self):
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump({"tabs": self.tabs, "active": self.tab["id"]}, f, ensure_ascii=False)
    def closeEvent(self, e):
        self._close_editor(True)
        self._save(); self._save_settings(); e.accept()
    def _save_settings(self):
        try:
            self.settings_file.write_text(
                json.dumps({"dark": self.dark, "ui_scale": self.ui_scale, "perf": self.perf,
                            "cam_x": self.cam_x, "cam_y": self.cam_y, "zoom": self.zoom}),
                encoding="utf-8")
        except Exception: pass
    def _dump(self):
        return {"items": self.items, "connections": self.connections,
                "background_drawings": self.bg_drawings, "board_content": self.board_content}
    def _snap(self):
        self._undo.append(json.dumps(self._dump(), ensure_ascii=False))
        if len(self._undo) > 30: self._undo.pop(0)
        self._redo.clear()
    def _undo_do(self):
        if not self._undo: return
        self._close_editor(False)
        self._redo.append(json.dumps(self._dump(), ensure_ascii=False))
        self._apply_state(json.loads(self._undo.pop()))
    def _redo_do(self):
        if not self._redo: return
        self._close_editor(False)
        self._undo.append(json.dumps(self._dump(), ensure_ascii=False))
        self._apply_state(json.loads(self._redo.pop()))
    def _apply_state(self, d):
        self.items = d["items"]; self.connections = d["connections"]
        self.bg_drawings = d["background_drawings"]; self.board_content = d["board_content"]
        if self.tab is not None:
            self.tab["items"] = self.items; self.tab["connections"] = self.connections
            self.tab["background_drawings"] = self.bg_drawings
            self.tab["board_content"] = self.board_content
        oid = self.opened["id"] if self.opened else None
        self.opened = next((i for i in self.items if i["id"] == oid), None) if oid else None
        self._open_anim = None; self._close_anim = None
        self._schedule_save(); self.update()
    def showEvent(self, e):
        super().showEvent(e)
        self.setFocus()

    # ================= пользователи =================
    def _save_users(self):
        try:
            self.users_file.write_text(json.dumps({"users": self.users,
                "current": self.current_user}, ensure_ascii=False), encoding="utf-8")
        except Exception: pass
    def _switch_user(self, name):
        if name == self.current_user: return
        self._save()
        self.current_user = name
        self.data_file = Path.home() / ("board_data_%s.json" % name)
        self._save_users()
        self.opened = None; self._open_anim = None; self._close_anim = None
        self._undo = []
        self._load_board()
        self._close_users()
        self.update()
    def _new_user(self):
        v = self._text_dialog("Новый пользователь", "user%d" % (len(self.users)+1))
        if not v or not v.strip(): return
        name = v.strip(); base = name; i = 2
        while any(u["name"] == name for u in self.users):
            name = "%s_%d" % (base, i); i += 1
        self.users.append({"id": str(uuid.uuid4()), "name": name})
        self._switch_user(name)
    def _rename_user(self):
        old = self.current_user
        v = self._text_dialog("Имя пользователя", old)
        if not v or not v.strip() or v.strip() == old: return
        name = v.strip()
        if any(u["name"] == name for u in self.users):
            QMessageBox.warning(self, "Ошибка", "Такое имя уже есть"); return
        self._save()
        oldf = Path.home() / ("board_data_%s.json" % old)
        newf = Path.home() / ("board_data_%s.json" % name)
        try:
            if oldf.exists(): oldf.replace(newf)
        except Exception: pass
        for u in self.users:
            if u["name"] == old: u["name"] = name
        self.current_user = name
        self.data_file = newf
        self._save_users(); self.update()
    def _delete_user(self, name):
        if len(self.users) <= 1:
            QMessageBox.information(self, "Внимание", "Нельзя удалить последнего пользователя"); return
        if name == self.current_user:
            QMessageBox.warning(self, "Ошибка", "Нельзя удалить текущего пользователя"); return
        msg = QMessageBox(self)
        msg.setWindowTitle("Удаление пользователя")
        msg.setText("Удалить пользователя '%s' и все его доски?" % name)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        if msg.exec_() != QMessageBox.Yes: return
        df = Path.home() / ("board_data_%s.json" % name)
        try:
            if df.exists(): df.unlink()
        except Exception: pass
        self.users = [u for u in self.users if u["name"] != name]
        self._save_users(); self.update()
    def _open_users(self):
        self._users_open = True
        self._users_anim = {"t0": time.time(), "opening": True}
        self.update()
    def _close_users(self):
        if not self._users_open: return
        self._users_open = False
        self._users_anim = None
        self.update()

    # ================= вкладки =================
    def _load_board(self):
        d = {}
        if self.data_file.exists():
            try: d = json.loads(self.data_file.read_text(encoding="utf-8"))
            except Exception as ex: print("load error", ex)
        if "tabs" not in d:
            tab = {"id": str(uuid.uuid4()), "title": "Доска",
                   "items": d.get("items", []), "connections": d.get("connections", []),
                   "background_drawings": d.get("background_drawings", []),
                   "board_content": d.get("board_content", [])}
            d = {"tabs": [tab], "active": tab["id"]}
        self.tabs = d["tabs"]
        for t in self.tabs:
            t.setdefault("items", []); t.setdefault("connections", [])
            t.setdefault("background_drawings", []); t.setdefault("board_content", [])
        self.tab = next((t for t in self.tabs if t["id"] == d.get("active")), self.tabs[0])
        self._bind_tab()
    def _bind_tab(self):
        self.items = self.tab["items"]
        self.connections = self.tab["connections"]
        self.bg_drawings = self.tab["background_drawings"]
        self.board_content = self.tab["board_content"]
    def _new_tab(self):
        t = {"id": str(uuid.uuid4()), "title": "Вкладка %d" % (len(self.tabs)+1),
             "items": [], "connections": [], "background_drawings": [], "board_content": []}
        self.tabs.append(t)
        self._tab_anim[t["id"]] = time.time()
        self._save()
        self.tab = t; self._bind_tab()
        self.opened = None; self._open_anim = None; self._close_anim = None
        self.selected_id = None; self._undo = []
        self._schedule_save(); self.update()
    def _switch_tab(self, t):
        if t is self.tab: return
        self._save()
        self.tab = t; self._bind_tab()
        self.opened = None; self._open_anim = None; self._close_anim = None
        self.selected_id = None; self._undo = []
        self._schedule_save(); self.update()
    def _close_tab(self, t):
        if len(self.tabs) <= 1: return
        self.tabs.remove(t)
        if self.tab is t: self._switch_tab(self.tabs[0])
        else: self._schedule_save(); self.update()

    # ================= настройки =================
    def _toggle_settings(self):
        if self._settings_open:
            self._settings_open = False; self._settings_anim = None
        else:
            self._settings_open = True
            self._settings_anim = {"t0": time.time(), "opening": True}
        self.update()

    # ================= инлайн-редактор =================
    def _inline_edit(self, kind, ref, bx, by, bw, bh, initial, multi, fs, imm, fixed=False):
        self._close_editor(False)
        w = QTextEdit(self) if multi else QLineEdit(initial, self)
        if multi: w.setPlainText(initial)
        w.setStyleSheet("background:%s; color:%s; border:2px solid #1E88E5; border-radius:6px; padding:4px;"
                        % (self.P["body"], self.P["text"]))
        if not multi:
            w.returnPressed.connect(lambda: self._close_editor(True))
        w.installEventFilter(self)
        w.setContextMenuPolicy(Qt.CustomContextMenu)
        w.customContextMenuRequested.connect(lambda pos, w=w: self._editor_menu(w, pos))
        zf = 1 if imm else self.zoom
        self._editor = {"w": w, "kind": kind, "ref": ref, "bx": bx, "by": by,
                        "bw": bw, "bh": bh, "fs": fs, "multi": multi, "imm": imm,
                        "zf": zf, "fixed": fixed}
        if kind == "note":
            hint = QLabel(NOTE_HELP, self)
            hint.setWordWrap(True)
            hint.setStyleSheet("background:#FFFDE7; color:#757575; border:1px solid #E6C84A; border-radius:6px; padding:4px; font-size:%dpx;" % max(10, int(10*self.ui_scale)))
            hint.show()
            self._editor["hint"] = hint
        w.show(); w.setFocus()
        self.update()
    def _close_editor(self, commit=False):
        ed = self._editor
        if not ed: return
        self._editor = None
        w = ed["w"]
        txt = w.toPlainText() if ed["multi"] else w.text()
        w.hide(); w.deleteLater()
        if ed.get("hint"):
            ed["hint"].hide(); ed["hint"].deleteLater()
        if commit:
            k, ref = ed["kind"], ed["ref"]
            if k == "note": ref["text"] = txt
            elif k == "cell": ref[0][ref[1]][ref[2]] = txt
            elif k == "item": ref["text"] = txt
            elif k == "title": ref["title"] = txt or ref["title"]
            elif k == "tab": ref["title"] = txt or ref["title"]
            self._schedule_save()
        self.update()
    def eventFilter(self, obj, ev):
        ed = self._editor
        if ed and obj is ed["w"]:
            if ev.type() == QEvent.FocusOut:
                if not self._menu_open:
                    QTimer.singleShot(0, lambda: self._close_editor(True))
            elif ev.type() == QEvent.Wheel:
                self._close_editor(True)
                return True
            elif ev.type() == QEvent.KeyPress:
                if ev.key() == Qt.Key_Escape:
                    self._close_editor(False); return True
                if ed["multi"] and ev.key() == Qt.Key_Return and ev.modifiers() & Qt.ControlModifier:
                    self._close_editor(True); return True
        se = self._search_edit
        if se and obj is se and ev.type() == QEvent.KeyPress and ev.key() == Qt.Key_Escape:
            self._close_search(); return True
        return super().eventFilter(obj, ev)
    def _editor_menu(self, w, pos):
        def has_sel():
            try: return w.textCursor().hasSelection()
            except Exception: return w.hasSelectedText()
        m = self._styled_menu()
        if has_sel():
            m.addAction("Вырезать", w.cut)
            m.addAction("Копировать", w.copy)
        m.addAction("Вставить", w.paste)
        m.addAction("Выбрать всё", w.selectAll)
        def clear_sel():
            try:
                c = w.textCursor(); c.removeSelectedText(); w.setTextCursor(c)
            except Exception: w.clear()
        m.addAction("Очистить", clear_sel if has_sel() else w.clear)
        self._menu_open = True
        m.exec_(w.mapToGlobal(pos))
        self._menu_open = False
        w.setFocus()

    # ================= переносы / списки =================
    def _wrap_segs(self, segs, fs, max_w):
        lines = []; cur = []; curw = 0.0
        def push():
            nonlocal cur, curw
            if cur: lines.append(cur); cur = []; curw = 0.0
        for t, b, i in segs:
            if not t: continue
            words = t.split(" ")
            for wi, wd in enumerate(words):
                piece = wd if wi == len(words)-1 else wd + " "
                if not piece: continue
                w_ = self.mw(piece, fs, b, i)
                if w_ > max_w:
                    push(); tt = piece
                    while self.mw(tt, fs, b, i) > max_w and len(tt) > 1:
                        lo, hi = 1, len(tt)
                        while lo < hi:
                            mid = (lo+hi+1)//2
                            if self.mw(tt[:mid], fs, b, i) <= max_w: lo = mid
                            else: hi = mid-1
                        lines.append([(tt[:lo], b, i)]); tt = tt[lo:]
                    cur = [(tt, b, i)]; curw = self.mw(tt, fs, b, i)
                elif curw + w_ <= max_w:
                    if cur and cur[-1][1] == b and cur[-1][2] == i:
                        cur[-1] = (cur[-1][0] + piece, b, i)
                    else:
                        cur.append((piece, b, i))
                    curw += w_
                else:
                    push(); cur = [(piece, b, i)]; curw = w_
        push()
        return lines or [[("", False, False)]]
    def _list_layout(self, c):
        lfs = max(7, int(c.get("fontSize", 13)*0.9))
        rows = []; y = 24.0
        for it in c.get("items", []):
            lines = self._wrap_segs([(it.get("text", ""), False, False)], lfs, c["w"]-32)
            n = min(2, len(lines))
            h = max(34.0, 8.0 + n*lfs*1.2)
            rows.append({"y": y, "h": h, "lines": lines[:2]})
            y += h
        return rows, y, lfs
    def _list_index(self, c, ly):
        rows, total, lfs = self._list_layout(c)
        for i, R in enumerate(rows):
            if R["y"] <= ly < R["y"] + R["h"]: return i
        return None

    # ================= примитивы =================
    def _rpath(self, x, y, w, h, r):
        path = QPainterPath()
        if self.perf: r = 0
        path.addRoundedRect(QRectF(x, y, w, h), r, r); return path
    def _fill(self, p, path, color):
        p.setPen(Qt.NoPen); p.setBrush(QBrush(QColor(color))); p.drawPath(path)
    def _outline(self, p, path, color, width=1):
        p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(color), width)); p.drawPath(path)
    def _line(self, p, x1, y1, x2, y2, color, width=1):
        p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(color), width))
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    def _rrect(self, p, x, y, w, h, r, fill=None, outline=None, width=1):
        path = self._rpath(x, y, w, h, r)
        if fill: self._fill(p, path, fill)
        if outline: self._outline(p, path, outline, width)
    def _stroke(self, p, pts, color, width, clip, board_space):
        screen_pts = []
        for q in pts:
            sx, sy = self.b2s(q[0], q[1]) if board_space else (q[0], q[1])
            if clip and not (clip[0]-2 <= sx <= clip[2]+2 and clip[1]-2 <= sy <= clip[3]+2):
                continue
            screen_pts.append(QPointF(sx, sy))
        if len(screen_pts) < 2: return
        path = QPainterPath()
        path.moveTo(screen_pts[0])
        if len(screen_pts) == 2:
            path.lineTo(screen_pts[1])
        else:
            for i in range(len(screen_pts) - 1):
                p0 = screen_pts[max(0, i-1)]; p1 = screen_pts[i]
                p2 = screen_pts[i+1]; p3 = screen_pts[min(len(screen_pts)-1, i+2)]
                c1 = QPointF(p1.x() + (p2.x()-p0.x())/6, p1.y() + (p2.y()-p0.y())/6)
                c2 = QPointF(p2.x() - (p3.x()-p1.x())/6, p2.y() - (p3.y()-p1.y())/6)
                path.cubicTo(c1, c2, p2)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(color), max(1, width), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)
    def _anim_draw(self, p, cx, cy, key, fn):
        if self.perf:
            fn(); return
        t0 = self._anim.get(key)
        if t0 is None:
            fn(); return
        k = (time.time() - t0) / 0.3
        if k >= 1:
            self._anim.pop(key, None); fn(); return
        e = 1 - (1-k)**3
        self._need_anim = True
        p.save(); p.setOpacity(max(0.05, e))
        p.translate(cx, cy); p.scale(0.6+0.4*e, 0.6+0.4*e); p.translate(-cx, -cy)
        fn(); p.restore()

    # ================= иконки =================
    def _icon(self, p, kind, x, y, sz, col):
        p.setPen(QPen(QColor(col), max(1.0, sz*0.08), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        cx, cy = x+sz/2, y+sz/2
        r = sz*0.30; a = sz*0.13
        if kind == "pan":
            p.drawLine(QPointF(cx-r, cy), QPointF(cx+r, cy)); p.drawLine(QPointF(cx, cy-r), QPointF(cx, cy+r))
            p.drawLine(QPointF(cx-r, cy), QPointF(cx-r+a, cy-a)); p.drawLine(QPointF(cx-r, cy), QPointF(cx-r+a, cy+a))
            p.drawLine(QPointF(cx+r, cy), QPointF(cx+r-a, cy-a)); p.drawLine(QPointF(cx+r, cy), QPointF(cx+r-a, cy+a))
            p.drawLine(QPointF(cx, cy-r), QPointF(cx-a, cy-r+a)); p.drawLine(QPointF(cx, cy-r), QPointF(cx+a, cy-r+a))
            p.drawLine(QPointF(cx, cy+r), QPointF(cx-a, cy+r-a)); p.drawLine(QPointF(cx, cy+r), QPointF(cx+a, cy+r-a))
        elif kind == "draw":
            p.drawLine(QPointF(cx-r, cy+r), QPointF(cx+r*0.5, cy-r*0.5))
            p.drawLine(QPointF(cx+r*0.5, cy-r*0.5), QPointF(cx+r, cy-r))
            p.setBrush(QBrush(QColor(col))); p.drawEllipse(QPointF(cx-r, cy+r), sz*0.08, sz*0.08); p.setBrush(Qt.NoBrush)
        elif kind == "erase":
            path = QPainterPath()
            path.moveTo(cx-r, cy+r*0.5); path.lineTo(cx-r*0.3, cy-r*0.7); path.lineTo(cx+r, cy+r*0.1)
            path.lineTo(cx+r*0.3, cy+r*0.9); path.closeSubpath()
            p.drawPath(path)
        elif kind == "connect":
            p.drawEllipse(QPointF(cx-r, cy), sz*0.10, sz*0.10); p.drawEllipse(QPointF(cx+r, cy), sz*0.10, sz*0.10)
            p.drawLine(QPointF(cx-r+sz*0.10, cy), QPointF(cx+r-sz*0.10, cy))
        elif kind == "color":
            p.drawEllipse(QPointF(cx, cy), r, r)
            p.save(); p.setClipRect(QRectF(cx-r, cy-r, r, 2*r)); p.setBrush(QBrush(QColor(col)))
            p.drawEllipse(QPointF(cx, cy), r, r); p.restore(); p.setBrush(Qt.NoBrush)
        elif kind == "export":
            p.drawLine(QPointF(cx-r, cy), QPointF(cx+r*0.5, cy))
            p.drawLine(QPointF(cx+r*0.1, cy-r*0.5), QPointF(cx+r*0.6, cy)); p.drawLine(QPointF(cx+r*0.1, cy+r*0.5), QPointF(cx+r*0.6, cy))
            p.drawLine(QPointF(cx+r, cy-r*0.7), QPointF(cx+r, cy+r*0.7))
        elif kind == "import":
            p.drawLine(QPointF(cx+r, cy), QPointF(cx-r*0.5, cy))
            p.drawLine(QPointF(cx-r*0.1, cy-r*0.5), QPointF(cx-r*0.6, cy)); p.drawLine(QPointF(cx-r*0.1, cy+r*0.5), QPointF(cx-r*0.6, cy))
            p.drawLine(QPointF(cx-r, cy-r*0.7), QPointF(cx-r, cy+r*0.7))
        elif kind == "minus":
            p.drawLine(QPointF(cx-r*0.7, cy), QPointF(cx+r*0.7, cy))
        elif kind == "plus":
            p.drawLine(QPointF(cx-r*0.7, cy), QPointF(cx+r*0.7, cy)); p.drawLine(QPointF(cx, cy-r*0.7), QPointF(cx, cy+r*0.7))
        elif kind == "ui":
            for i, yy in enumerate([cy-r*0.6, cy, cy+r*0.6]):
                p.drawLine(QPointF(cx-r, yy), QPointF(cx+r, yy))
                p.setBrush(QBrush(QColor(col))); p.drawEllipse(QPointF(cx+(-0.4+0.4*i)*r, yy), sz*0.08, sz*0.08); p.setBrush(Qt.NoBrush)
        elif kind == "theme":
            p.drawEllipse(QPointF(cx, cy), r, r)
            p.save(); p.setClipRect(QRectF(cx, cy-r, r, 2*r)); p.setBrush(QBrush(QColor(col)))
            p.drawEllipse(QPointF(cx, cy), r, r); p.restore(); p.setBrush(Qt.NoBrush)
        elif kind == "user":
            p.drawEllipse(QPointF(cx, cy-r*0.4), r*0.45, r*0.45)
            p.drawArc(QRectF(cx-r*0.8, cy-r*0.1, 1.6*r, 1.3*r), 0, 180*16)
        elif kind == "gear":
            p.drawEllipse(QPointF(cx, cy), r*0.55, r*0.55)
            for ang in range(0, 360, 45):
                dx, dy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
                p.drawLine(QPointF(cx+dx*r*0.75, cy+dy*r*0.75), QPointF(cx+dx*r, cy+dy*r))
        elif kind == "lightning":
            p.setBrush(QBrush(QColor(col)))
            path = QPainterPath()
            path.moveTo(cx+r*0.2, cy-r); path.lineTo(cx-r*0.6, cy+r*0.1); path.lineTo(cx-r*0.1, cy+r*0.1)
            path.lineTo(cx-r*0.3, cy+r); path.lineTo(cx+r*0.7, cy-r*0.2); path.lineTo(cx+r*0.1, cy-r*0.2)
            path.closeSubpath()
            p.drawPath(path); p.setBrush(Qt.NoBrush)
        elif kind == "tab":
            p.drawRoundedRect(QRectF(cx-r, cy-r*0.7, 2*r, 1.4*r), 3, 3)
            p.drawLine(QPointF(cx, cy-r*0.35), QPointF(cx, cy+r*0.35)); p.drawLine(QPointF(cx-r*0.35, cy), QPointF(cx+r*0.35, cy))
        elif kind == "block":
            p.drawRoundedRect(QRectF(cx-r, cy-r*0.8, 2*r, 1.6*r), 3, 3)
            p.drawLine(QPointF(cx-r, cy-r*0.3), QPointF(cx+r, cy-r*0.3))
        elif kind == "note":
            p.drawRoundedRect(QRectF(cx-r*0.8, cy-r, 1.6*r, 2*r), 2, 2)
            p.drawLine(QPointF(cx-r*0.5, cy-r*0.4), QPointF(cx+r*0.5, cy-r*0.4))
            p.drawLine(QPointF(cx-r*0.5, cy), QPointF(cx+r*0.5, cy))
            p.drawLine(QPointF(cx-r*0.5, cy+r*0.4), QPointF(cx+r*0.2, cy+r*0.4))
        elif kind == "table":
            p.drawRect(QRectF(cx-r, cy-r*0.8, 2*r, 1.6*r))
            p.drawLine(QPointF(cx-r, cy-r*0.2), QPointF(cx+r, cy-r*0.2)); p.drawLine(QPointF(cx-r, cy+r*0.4), QPointF(cx+r, cy+r*0.4))
            p.drawLine(QPointF(cx-r*0.3, cy-r*0.8), QPointF(cx-r*0.3, cy+r*0.8)); p.drawLine(QPointF(cx+r*0.3, cy-r*0.8), QPointF(cx+r*0.3, cy+r*0.8))
        elif kind == "list":
            for yy in [cy-r*0.6, cy+r*0.1, cy+r*0.8]:
                p.drawRect(QRectF(cx-r, yy-sz*0.06, sz*0.12, sz*0.12))
                p.drawLine(QPointF(cx-r*0.4, yy), QPointF(cx+r, yy))
        elif kind == "clear":
            p.drawLine(QPointF(cx-r*0.7, cy-r*0.7), QPointF(cx+r*0.7, cy+r*0.7))
            p.drawLine(QPointF(cx-r*0.7, cy+r*0.7), QPointF(cx+r*0.7, cy-r*0.7))

    # ================= анимации блока =================
    def _open_block(self, it):
        self._close_editor(True)
        if self.perf:
            self.opened = it; self.imm_cam = [0.0, 0.0]; self.update(); return
        z = self.zoom
        sx, sy = self.b2s(it["x"], it["y"])
        sw, sh = it["w"]*z, it["h"]*z
        self.opened = it
        self.imm_cam = [0.0, 0.0]
        self.imm_tb_scroll = 0
        self._close_anim = None
        self._open_anim = {"t0": time.time(), "from": (sx, sy, sw, sh)}
        self.update()
    def _close_block(self):
        if not self.opened: return
        self._close_editor(True)
        if self.perf:
            self.opened = None; self.update(); return
        it = self.opened
        z = self.zoom
        sx, sy = self.b2s(it["x"], it["y"])
        sw, sh = it["w"]*z, it["h"]*z
        self._open_anim = None
        self._close_anim = {"t0": time.time(), "to": (sx, sy, sw, sh)}
        self.update()

    # ================= диалоги =================
    def _text_dialog(self, title, initial, multiline=False, help_text=None):
        dlg = QDialog(self); dlg.setWindowTitle(title)
        dlg.setStyleSheet("QDialog{background:%s} QLabel{color:%s;background:transparent}" % (self.P["panel"], self.P["text"]))
        lay = QVBoxLayout(dlg)
        if help_text:
            hl = QLabel(help_text); hl.setWordWrap(True)
            hl.setStyleSheet("background:#FFFDE7;color:#757575;font-size:9px;padding:4px")
            lay.addWidget(hl)
        if multiline:
            e = QTextEdit(); e.setPlainText(initial); e.setMinimumHeight(int(140*self.ui_scale))
            e.setContextMenuPolicy(Qt.CustomContextMenu)
            e.customContextMenuRequested.connect(lambda pos: self._fmt_menu(e))
        else:
            e = QLineEdit(initial)
        lay.addWidget(e)
        row = QHBoxLayout()
        cancel = QPushButton("Отмена"); ok = QPushButton("ОК")
        cancel.clicked.connect(dlg.reject); ok.clicked.connect(dlg.accept)
        row.addWidget(cancel); row.addWidget(ok); lay.addLayout(row)
        result = None
        if dlg.exec_() == QDialog.Accepted:
            result = e.toPlainText() if multiline else e.text()
        self.setFocus()
        return result
    def _fmt_menu(self, te):
        m = self._styled_menu()
        def wrap(pre, post=None):
            post = post if post is not None else pre
            c = te.textCursor(); s = c.selectedText().replace("\u2029", "\n")
            c.insertText(pre + s + post)
        def prefix(pre):
            c = te.textCursor(); s = c.selectedText().replace("\u2029", "\n")
            c.insertText("\n".join(pre + ln for ln in s.split("\n")))
        m.addAction("Жирный", lambda: wrap("**"))
        m.addAction("Курсив", lambda: wrap("*"))
        m.addAction("Жирный+курсив", lambda: wrap("***"))
        m.addSeparator()
        m.addAction("Заголовок", lambda: prefix("# "))
        m.addAction("Подзаголовок", lambda: prefix("## "))
        m.addAction("Пункт", lambda: prefix("- "))
        m.addSeparator()
        m.addAction("Вправо", lambda: prefix("> "))
        m.addAction("По центру", lambda: prefix("= "))
        m.exec_(QCursor.pos())
    def _add_block_dialog(self):
        dlg = QDialog(self); dlg.setWindowTitle("Новый блок")
        dlg.setStyleSheet("QDialog{background:%s} QLabel{color:%s;background:transparent}" % (self.P["panel"], self.P["text"]))
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Название:"))
        name = QLineEdit("Новый блок"); lay.addWidget(name)
        lay.addWidget(QLabel("Цвет:"))
        row = QHBoxLayout(); chosen = [COLORS[0]]; swatches = []
        def select(col, btn):
            chosen[0] = col
            for b in swatches: b.setStyleSheet("background:%s;border:1px solid #ccc" % b.property("col"))
            btn.setStyleSheet("background:%s;border:2px solid #333" % col)
        for c in COLORS:
            b = QPushButton(); b.setFixedSize(30, 24); b.setProperty("col", c)
            b.setStyleSheet("background:%s;border:1px solid #ccc" % c)
            b.clicked.connect(lambda _, col=c, btn=b: select(col, btn))
            row.addWidget(b); swatches.append(b)
        lay.addLayout(row)
        brow = QHBoxLayout()
        cancel = QPushButton("Отмена"); ok = QPushButton("Создать")
        cancel.clicked.connect(dlg.reject); ok.clicked.connect(dlg.accept)
        brow.addWidget(cancel); brow.addWidget(ok); lay.addLayout(brow)
        if dlg.exec_() == QDialog.Accepted:
            bx, by = self.s2b(self.width()/2, self.height()/2)
            nid = str(uuid.uuid4())
            self._snap()
            self.items.append({"id": nid, "x": bx-110, "y": by-80,
                               "title": name.text().strip() or "Новый блок", "color": chosen[0],
                               "w": 220, "h": 160, "drawings": [], "content": []})
            self._anim["b:"+nid] = time.time()
            self._schedule_save(); self.update()
        self.setFocus()
    def _ui_scale_dialog(self):
        dlg = QDialog(self); dlg.setWindowTitle("Масштаб интерфейса")
        dlg.setStyleSheet("QDialog{background:%s} QLabel{color:%s;background:transparent}" % (self.P["panel"], self.P["text"]))
        lay = QVBoxLayout(dlg)
        lbl = QLabel("%d%%" % int(self.ui_scale*100)); lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("font-size:16px;font-weight:bold")
        lay.addWidget(lbl)
        sl = QSlider(Qt.Horizontal); sl.setRange(60, 160); sl.setSingleStep(5); sl.setPageStep(10)
        sl.setTickInterval(10); sl.setTickPosition(QSlider.TicksBelow); sl.setValue(int(self.ui_scale*100))
        def onv(v):
            lbl.setText("%d%%" % v); self.ui_scale = v/100.0; self.update(); self._save_settings()
        sl.valueChanged.connect(onv); lay.addWidget(sl)
        ok = QPushButton("ОК"); ok.clicked.connect(dlg.accept); lay.addWidget(ok)
        dlg.exec_()
        self.setFocus()
    # ================= контент =================
    def _content_h(self, c):
        if c["type"] == "note": return c.get("h", 80)
        if c["type"] == "table": return c.get("h", 24 + len(c.get("rows", []))*26)
        rows, total, lfs = self._list_layout(c)
        return max(c.get("h", 0), total)

    def _hit_content(self, lst, x, y):
        for i in reversed(range(len(lst))):
            c = lst[i]
            if c["x"] <= x <= c["x"]+c["w"] and c["y"] <= y <= c["y"]+self._content_h(c):
                return i, c
        return None, None

    def _hit_block(self, bx, by):
        for it in reversed(self.items):
            if it["x"] <= bx <= it["x"]+it["w"] and it["y"] <= by <= it["y"]+it["h"]:
                return it
        return None

    def _hit_connection(self, bx, by):
        r = 8 / self.zoom
        for cn in self.connections:
            a = next((i for i in self.items if i["id"] == cn["from"]), None)
            b = next((i for i in self.items if i["id"] == cn["to"]), None)
            if not a or not b: continue
            ax, ay = a["x"]+a["w"]/2, a["y"]+a["h"]/2
            bx2, by2 = b["x"]+b["w"]/2, b["y"]+b["h"]/2
            if dist_seg(bx, by, ax, ay, bx2, by2) < r: return cn
        return None

    def _add_content(self, target, kind, cx=None, cy=None):
        if cx is None: cx, cy = self.s2b(self.width()/2, self.height()/2)
        if kind == "note":
            d = {"type": "note", "x": cx, "y": cy, "w": 160, "h": 90, "text": "", "fontSize": 13, "title": "Заметка"}
        elif kind == "table":
            d = {"type": "table", "x": cx, "y": cy, "w": 230, "h": 76, "fontSize": 12,
                 "title": "Таблица", "rows": [["", "", ""], ["", "", ""]]}
        else:
            d = {"type": "list", "x": cx, "y": cy, "w": 220, "h": 72, "fontSize": 13,
                 "title": "Список",
                 "items": [{"text": "", "done": False}, {"text": "", "done": False}]}
        d["aid"] = str(uuid.uuid4())
        self._snap(); target.append(d)
        self._anim["c:"+d["aid"]] = time.time()
        self._schedule_save(); self.update()

    def _edit_content(self, lst, idx, c, lx, ly, imm=False):
        if c["type"] == "note":
            self._inline_edit("note", c, c["x"], c["y"], c["w"], self._content_h(c),
                              c.get("text", ""), True, c.get("fontSize", 13), imm)
        elif c["type"] == "table":
            rows = c.get("rows", [])
            if not rows or not rows[0]: return
            cols = len(rows[0]); cw = c["w"]/cols
            ch = (self._content_h(c)-24)/len(rows)
            r = int((ly-24)//ch); cc = int(lx//cw)
            if 0 <= r < len(rows) and 0 <= cc < cols:
                self._inline_edit("cell", (rows, r, cc), c["x"]+cc*cw, c["y"]+24+r*ch,
                                  cw, ch, rows[r][cc], False, c.get("fontSize", 12)*0.9, imm)
        elif c["type"] == "list":
            items = c.get("items", [])
            i = self._list_index(c, ly)
            if i is not None:
                R = self._list_layout(c)[0][i]
                self._inline_edit("item", items[i], c["x"]+24, c["y"]+R["y"],
                                  c["w"]-30, R["h"], items[i]["text"], False,
                                  c.get("fontSize", 13)*0.9, imm)

    def _rename_block(self, it, imm=False):
        self._inline_edit("title", it, it["x"], it["y"], it["w"], 30, it["title"], False, 13, imm)

    def _hit_btn(self, x, y, lst):
        for b in reversed(lst):
            if b["x"] <= x <= b["x"]+b["w"] and b["y"] <= y <= b["y"]+b["h"]:
                return b
        return None

    # ================= события =================
    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            if self._search_open: self._close_search(); return
            if self.opened: self._close_block(); return
        if e.modifiers() & Qt.ControlModifier:
            if e.key() == Qt.Key_Z:
                self._redo_do() if (e.modifiers() & Qt.ShiftModifier) else self._undo_do(); return
            if e.key() == Qt.Key_Y: self._redo_do(); return
            if e.key() == Qt.Key_0: self._fit_all(); return
            if e.key() == Qt.Key_F: self._toggle_search(); return
        k = e.text().lower()
        if k in ("1", "h", "п"): self.tool = "pan"
        elif k in ("2", "b", "и"): self.tool = "draw"
        elif k in ("3", "e", "л"): self.tool = "erase"
        elif k in ("4", "c", "с"): self.tool = "connect"
        elif k == "t": self.dark = not self.dark; self._save_settings()
        elif k == "+": self._zoom_by(1.2); return
        elif k == "-": self._zoom_by(1/1.2); return
        else: return
        self.conn_start = None; self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MiddleButton:
            self.pan_start = (e.x(), e.y()); return
        if e.button() != Qt.LeftButton: return
        x, y = e.x(), e.y()
        # закрыть док настроек при постороннем клике
        if self._settings_open:
            hb = self._hit_btn(x, y, self._buttons)
            keep = hb and (hb["id"] == "settings" or hb["id"] in ("user","theme","import","export","ui"))
            if not keep:
                self._settings_open = False; self._settings_anim = None
        # окно пользователей поверх
        if self._users_open:
            if not self._users_anim:
                for b in reversed(self._user_btns):
                    if b["x"] <= x <= b["x"]+b["w"] and b["y"] <= y <= b["y"]+b["h"]:
                        if b["id"] == "close": self._close_users()
                        elif b["id"] == "new": self._new_user()
                        elif b["id"] == "rename": self._rename_user()
                        elif b["id"] == "deluser": self._delete_user(b["name"])
                        elif b["id"] == "switch": self._switch_user(b["name"])
                        return
                if self._user_rect and not (self._user_rect[0] <= x <= self._user_rect[2]
                                            and self._user_rect[1] <= y <= self._user_rect[3]):
                    self._close_users()
            return
        # поиск: кнопка-лупа и результаты
        sg = self._search_geom
        if sg and (x-sg[0])**2 + (y-sg[1])**2 <= (sg[2]+4)**2:
            self._toggle_search(); return
        if self._search_open:
            for b in self._search_btns:
                if b["x"] <= x <= b["x"]+b["w"] and b["y"] <= y <= b["y"]+b["h"]:
                    self._goto(b["r"]); return
            self._close_search(); return
        # вкладки
        if self._tab_btns:
            for tb in self._tab_btns:
                if tb.get("plus"):
                    dx, dy = x-tb["cx"], y-tb["cy"]
                    if dx*dx + dy*dy <= tb["r"]*tb["r"]:
                        self._new_tab(); return
                elif tb["x"] <= x <= tb["x"]+tb["w"] and tb["y"] <= y <= tb["y"]+tb["h"]:
                    if (x-tb["cx"])**2 + (y-tb["cy"])**2 <= tb["cr"]**2:
                        self._tab_close_t = time.time()
                        if self._tab_close_arm == tb["tab"]["id"]:
                            self._tab_close_arm = None
                            self._close_tab(tb["tab"])
                        else:
                            self._tab_close_arm = tb["tab"]["id"]
                            self.update()
                        return
                    self._tab_close_arm = None
                    self._switch_tab(tb["tab"]); return
            if self._bar_h and y < self._bar_h: return
        b = self._hit_btn(x, y, self._buttons)
        if not b and self.opened:
            b = self._hit_btn(x, y, self._imm_btns)
        if b:
            self._down_btn = b["id"]; self.update()
            self._run_btn(b["id"]); return
        if self.opened:
            self._imm_press(x, y); return
        bx, by = self.s2b(x, y)
        if self.tool == "draw":
            self.drawing = True; self.cur_path = [(bx, by)]; return
        if self.tool == "erase":
            self._snap(); self._erase(self.bg_drawings, bx, by, 15/self.zoom); self.update(); return
        if self.tool == "connect":
            it = self._hit_block(bx, by)
            if it:
                if self.conn_start and self.conn_start != it["id"]:
                    self._snap()
                    self.connections.append({"id": str(uuid.uuid4()), "from": self.conn_start, "to": it["id"]})
                    self.conn_start = None; self.tool = "pan"
                else: self.conn_start = it["id"]
                self._schedule_save(); self.update()
            else: self.conn_start = None; self.update()
            return
        if self.selected_id:
            it = next((i for i in self.items if i["id"] == self.selected_id), None)
            if it:
                sx, sy = self.b2s(it["x"]+it["w"], it["y"]+it["h"])
                if abs(x-sx) < 12 and abs(y-sy) < 12:
                    self.resize = {"kind": "block", "id": it["id"]}; return
        it = self._hit_block(bx, by)
        if it:
            self.drag = {"kind": "block", "id": it["id"], "moved": False,
                         "ox": bx-it["x"], "oy": by-it["y"], "was": self.selected_id == it["id"]}
            return
        hi, c = self._hit_content(self.board_content, bx, by)
        if c:
            lx, ly = bx-c["x"], by-c["y"]
            if c["type"] == "list" and lx < 26:
                i = self._list_index(c, ly)
                if i is not None:
                    c["items"][i]["done"] = not c["items"][i]["done"]
                    self._schedule_save(); self.update(); return
            hx, hy = self.b2s(c["x"]+c["w"], c["y"]+self._content_h(c))
            if abs(x-hx) < 10 and abs(y-hy) < 10:
                self.resize = {"kind": "board", "index": hi}
            else:
                self.drag = {"kind": "board", "index": hi, "moved": False, "ox": lx, "oy": ly}
            return
        self.selected_id = None
        self.pan_start = (x, y)
        self.update()

    def mouseMoveEvent(self, e):
        x, y = e.x(), e.y()
        # hover на плюс вкладки
        if not self.opened and self._plus_geom:
            cx0, cy0, r = self._plus_geom
            in_c = (x-cx0)**2 + (y-cy0)**2 <= (r+4)**2
            in_p = self._plus_hover and (cx0-r <= x <= cx0+r+120) and abs(y-cy0) <= r+4
            hov = in_c or in_p
            if hov != self._plus_hover:
                self._plus_hover = hov; self.update()
        if self.opened: return self._imm_move(x, y)
        bx, by = self.s2b(x, y)
        if self.drawing:
            self.cur_path.append((bx, by)); self.update(); return
        if self.tool == "erase" and e.buttons() & Qt.LeftButton:
            self._erase(self.bg_drawings, bx, by, 15/self.zoom); self.update(); return
        if self.resize:
            if self.resize["kind"] == "block":
                it = next(i for i in self.items if i["id"] == self.resize["id"])
                it["w"] = max(140, bx-it["x"]); it["h"] = max(100, by-it["y"])
            else:
                c = self.board_content[self.resize["index"]]
                c["w"] = max(100, bx-c["x"]); c["h"] = max(50, by-c["y"])
            self._schedule_save(); self.update(); return
        if self.drag:
            self.drag["moved"] = True
            if self.drag["kind"] == "block":
                it = next(i for i in self.items if i["id"] == self.drag["id"])
                it["x"], it["y"] = bx-self.drag["ox"], by-self.drag["oy"]
            else:
                c = self.board_content[self.drag["index"]]
                c["x"], c["y"] = bx-self.drag["ox"], by-self.drag["oy"]
            self._schedule_save(); self.update(); return
        if self.pan_start:
            self.cam_x += x-self.pan_start[0]; self.cam_y += y-self.pan_start[1]
            self.pan_start = (x, y); self.update()

    def mouseReleaseEvent(self, e):
        if self._down_btn is not None:
            self._down_btn = None; self.update()
        if self.opened:
            self._imm_release(e)
            self.drawing = False; self.cur_path = []
            return
        if self.drawing and len(self.cur_path) > 1:
            self._snap()
            self.bg_drawings.append({"points": self.cur_path, "color": self.brush_color, "width": self.brush_width})
            self._schedule_save()
        self.drawing = False; self.cur_path = []
        if self.drag and not self.drag["moved"] and self.drag["kind"] == "block":
            it = next((i for i in self.items if i["id"] == self.drag["id"]), None)
            if it:
                sx, sy = self.b2s(it["x"], it["y"])
                if self.drag["was"] and e.y() > sy + 30*self.zoom:
                    self._open_block(it)
                else:
                    self.selected_id = it["id"]
                self.update()
        self.drag = self.resize = self.pan_start = None
        self._save_settings()
        self._schedule_save(); self.update()

    def mouseDoubleClickEvent(self, e):
        x, y = e.x(), e.y()
        if self._tab_btns and time.time() - self._tab_close_t >= 0.5:
            for tb in self._tab_btns:
                if not tb.get("plus") and tb["tab"] in self.tabs and \
                   tb["x"] <= x <= tb["x"]+tb["w"] and tb["y"] <= y <= tb["y"]+tb["h"]:
                    self._inline_edit("tab", tb["tab"], tb["x"]+4, tb["y"]+3, tb["w"]-20, tb["h"]-6,
                                      tb["tab"]["title"], False, 10*self.ui_scale, False, fixed=True)
                    return
        if self._hit_btn(x, y, self._buttons) or self._hit_btn(x, y, self._imm_btns): return
        if self.opened: return self._imm_double(x, y)
        bx, by = self.s2b(x, y)
        it = self._hit_block(bx, by)
        if it:
            sx, sy = self.b2s(it["x"], it["y"])
            if e.y() <= sy + 30*self.zoom:
                self._rename_block(it, False)
            else:
                self._open_block(it)
            return
        hi, c = self._hit_content(self.board_content, bx, by)
        if c: self._edit_content(self.board_content, hi, c, bx-c["x"], by-c["y"])

    def wheelEvent(self, e):
        x, y = e.x(), e.y()
        if self._users_open: return
        if self._editor:
            self._close_editor(True)
            return
        if self.opened:
            pr, hdr, tb, area = self._imm_rects()
            if tb[1] <= y <= tb[3]:
                maxs = max(0, self._tb_content_w - (tb[2]-tb[0]-20*self.ui_scale))
                step = 30 if e.angleDelta().y() < 0 else -30
                self.imm_tb_scroll = max(0, min(maxs, self.imm_tb_scroll + step))
                self.update(); return
        if not self.opened and self._tab_bar_visible and y < self._bar_h:
            step = 30 if e.angleDelta().y() < 0 else -30
            self._tabs_scroll = max(0, self._tabs_scroll + step)
            self.update(); return
        f = 1.1 if e.angleDelta().y() > 0 else 1/1.1
        bx, by = self.s2b(x, y)
        self.zoom = max(0.1, min(5.0, self.zoom*f))
        self.cam_x, self.cam_y = x-bx*self.zoom, y-by*self.zoom
        self._save_settings()
        self.update()

    def _fit_all(self):
        xs = []; ys = []
        for it in self.items:
            xs += [it["x"], it["x"]+it["w"]]; ys += [it["y"], it["y"]+it["h"]]
        for c in self.board_content:
            xs += [c["x"], c["x"]+c["w"]]; ys += [c["y"], c["y"]+self._content_h(c)]
        for d in self.bg_drawings:
            for q in d["points"]: xs.append(q[0]); ys.append(q[1])
        if not xs: return
        m = 80
        minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
        W, H = self.width(), self.height()
        self.zoom = max(0.1, min(2.0, min(W/(maxx-minx+2*m), H/(maxy-miny+2*m))))
        self.cam_x = W/2 - (minx+maxx)/2*self.zoom
        self.cam_y = H/2 - (miny+maxy)/2*self.zoom
        self._save_settings(); self.update()

    def _dup_block(self, it):
        import copy
        self._snap()
        nd = copy.deepcopy(it); nd["id"] = str(uuid.uuid4()); nd["x"] += 40; nd["y"] += 40
        self.items.append(nd)
        self._anim["b:"+nd["id"]] = time.time()
        self._schedule_save(); self.update()

    # ================= меню =================
    def _styled_menu(self):
        m = QMenu(self)
        s = self.ui_scale
        m.setStyleSheet("""
        QMenu {background: %s; border: 1px solid %s; padding: 3px;}
        QMenu::item {background: transparent; color: %s; padding: 3px %dpx; margin: 0px %dpx; font-size: %dpx;}
        QMenu::item:selected {background: %s;}
        QMenu::separator {height: 1px; background: %s; margin: 2px 4px;}
        """ % (self.P["panel"], self.P["panel_out"], self.P["text"], int(16*s), int(6*s),
               int(10*s), self.P["grid"], self.P["panel_out"]))
        return m

    def _exec_menu(self, m, pos):
        acts = m.actions()
        for i in range(len(acts)-1, 0, -1):
            m.insertSeparator(acts[i])
        m.exec_(pos)

    def contextMenuEvent(self, e):
        x, y = e.x(), e.y()
        if self._users_open: return
        if self._tab_btns:
            for tb in self._tab_btns:
                if not tb.get("plus") and tb["x"] <= x <= tb["x"]+tb["w"] and tb["y"] <= y <= tb["y"]+tb["h"]:
                    m = self._styled_menu()
                    m.addAction("Переименовать", lambda t=tb["tab"]: self._inline_edit("tab", t, tb["x"]+4, tb["y"]+3, tb["w"]-20, tb["h"]-6, t["title"], False, 10*self.ui_scale, False, fixed=True))
                    m.addAction("Закрыть", lambda t=tb["tab"]: self._close_tab(t))
                    self._exec_menu(m, e.globalPos())
                    return
        if self._hit_btn(x, y, self._buttons) or self._hit_btn(x, y, self._imm_btns): return
        m = self._styled_menu()
        if self.opened:
            p, hdr, tb, area = self._imm_rects()
            if area[1] <= y <= area[3]:
                lx, ly = x-area[0]-self.imm_cam[0], y-area[1]-self.imm_cam[1]
                hi, c = self._hit_content(self.opened["content"], lx, ly)
                if c: self._content_menu(m, c, hi, self.opened["content"], lx, ly)
            self._exec_menu(m, e.globalPos()); return
        bx, by = self.s2b(x, y)
        it = self._hit_block(bx, by)
        if it:
            m.addAction("Открыть", lambda: self._open_block(it))
            m.addAction("Переименовать", lambda: self._rename_block(it, False))
            m.addAction("Связать", lambda: (setattr(self, "tool", "connect"), setattr(self, "conn_start", it["id"]), self.update()))
            m.addAction("Дублировать", lambda: self._dup_block(it))
            m.addAction("Удалить", lambda: self._del_block(it))
            self._exec_menu(m, e.globalPos()); return
        hi, c = self._hit_content(self.board_content, bx, by)
        if c:
            lx, ly = bx-c["x"], by-c["y"]
            self._content_menu(m, c, hi, self.board_content, lx, ly)
            self._exec_menu(m, e.globalPos()); return
        cn = self._hit_connection(bx, by)
        if cn:
            m.addAction("Удалить связь", lambda: (self._snap(), self.connections.remove(cn), self._schedule_save(), self.update()))
            self._exec_menu(m, e.globalPos()); return
        m2 = self._styled_menu()
        m2.addAction("Вместить всё", self._fit_all)
        self._exec_menu(m2, e.globalPos())

    def _del_block(self, it):
        self._snap()
        self.items.remove(it)
        self.connections = [c for c in self.connections if c["from"] != it["id"] and c["to"] != it["id"]]
        if self.opened is it: self.opened = None
        self._schedule_save(); self.update()

    def _content_menu(self, m, c, idx, lst, lx=None, ly=None):
        m.addAction("Переименовать", lambda: self._rename_content(c))
        m.addAction("Шрифт +", lambda: (c.__setitem__("fontSize", min(30, c.get("fontSize",13)+1)), self._schedule_save(), self.update()))
        m.addAction("Шрифт −", lambda: (c.__setitem__("fontSize", max(8, c.get("fontSize",13)-1)), self._schedule_save(), self.update()))
        if c["type"] == "list":
            items = c.get("items", [])
            m.addAction("Добавить пункт", lambda: (self._snap(), items.append({"text":"","done":False}), self._schedule_save(), self.update()))
            if lx is not None:
                i = self._list_index(c, ly)
                if i is not None:
                    m.addAction("Удалить пункт", lambda i=i: (self._snap(), items.pop(i), self._schedule_save(), self.update()))
        if c["type"] == "table":
            rows = c.get("rows", [])
            if rows:
                cols = len(rows[0]); cw = c["w"]/max(1, cols); ch = (self._content_h(c)-24)/max(1, len(rows))
                r = int((ly-24)//ch) if ly is not None else 0
                cc = int(lx//cw) if lx is not None else 0
                def add_row():
                    self._snap(); rows.append([""]*len(rows[0])); c["h"] = self._content_h(c)+26
                    self._schedule_save(); self.update()
                def del_row():
                    if len(rows) > 1:
                        self._snap(); rows.pop(min(max(0, r), len(rows)-1)); c["h"] = max(50, self._content_h(c)-26)
                        self._schedule_save(); self.update()
                def add_col():
                    self._snap()
                    for row in rows: row.append("")
                    c["w"] = c["w"]+70; self._schedule_save(); self.update()
                def del_col():
                    if len(rows[0]) > 1:
                        self._snap(); j = min(max(0, cc), len(rows[0])-1)
                        for row in rows: row.pop(j)
                        c["w"] = max(150, c["w"]-70); self._schedule_save(); self.update()
                m.addAction("Добавить строку", add_row)
                m.addAction("Удалить строку", del_row)
                m.addAction("Добавить столбец", add_col)
                m.addAction("Удалить столбец", del_col)
                m.addAction("Свойства таблицы…", lambda: self._table_props(c))
        m.addAction("Удалить", lambda: (self._snap(), lst.pop(idx), self._schedule_save(), self.update()))

    def _table_props(self, c):
        dlg = QDialog(self); dlg.setWindowTitle("Свойства таблицы")
        dlg.setStyleSheet("QDialog{background:%s} QLabel{color:%s;background:transparent}" % (self.P["panel"], self.P["text"]))
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Название:"))
        te = QLineEdit(c.get("title", "")); lay.addWidget(te)
        rows = c.get("rows", [])
        nr = QSpinBox(); nr.setRange(1, 60); nr.setValue(len(rows))
        nc = QSpinBox(); nc.setRange(1, 26); nc.setValue(len(rows[0]) if rows else 3)
        h1 = QHBoxLayout(); h1.addWidget(QLabel("Строк:")); h1.addWidget(nr)
        h1.addWidget(QLabel("Столбцов:")); h1.addWidget(nc); lay.addLayout(h1)
        bf = QHBoxLayout()
        cancel = QPushButton("Отмена"); ok = QPushButton("ОК")
        cancel.clicked.connect(dlg.reject); ok.clicked.connect(dlg.accept)
        bf.addWidget(cancel); bf.addWidget(ok); lay.addLayout(bf)
        if dlg.exec_() == QDialog.Accepted:
            self._snap()
            c["title"] = te.text()
            R, C = nr.value(), nc.value()
            while len(rows) < R: rows.append([""]*len(rows[0]) if rows else [""]*C)
            del rows[R:]
            for r in rows:
                while len(r) < C: r.append("")
                del r[C:]
            c["h"] = 24 + R*26
            c["w"] = max(150, C*70)
            self._schedule_save(); self.update()

    def _rename_content(self, c):
        v = self._text_dialog("Название", c.get("title", ""))
        if v is not None: c["title"] = v.strip(); self._schedule_save(); self.update()

    def _erase(self, lst, x, y, r):
        lst[:] = [p for p in lst if not any(math.hypot(q[0]-x, q[1]-y) < r for q in p["points"])]
        self._schedule_save()

    def _run_btn(self, bid):
        if bid == "pan": self.tool = "pan"; self.conn_start = None
        elif bid == "draw": self.tool = "draw"; self.conn_start = None
        elif bid == "erase": self.tool = "erase"; self.conn_start = None
        elif bid == "connect": self.tool = "connect"
        elif bid == "color":
            c = QColorDialog.getColor(QColor(self.brush_color), self)
            if c.isValid(): self.brush_color = c.name()
        elif bid == "bw-": self.brush_width = max(1, self.brush_width-1)
        elif bid == "bw+": self.brush_width = min(14, self.brush_width+1)
        elif bid == "settings": self._toggle_settings()
        elif bid == "user": self._open_users()
        elif bid == "import": self._import_board()
        elif bid == "export": self._show_export_menu()
        elif bid == "ui": self._ui_scale_dialog()
        elif bid == "theme": self.dark = not self.dark; self._save_settings()
        elif bid == "perf": self.perf = not self.perf; self._save_settings()
        elif bid == "z-": self._zoom_by(1/1.2)
        elif bid == "z+": self._zoom_by(1.2)
        elif bid == "block": self._add_block_dialog()
        elif bid == "note": self._add_content(self.board_content, "note")
        elif bid == "table": self._add_content(self.board_content, "table")
        elif bid == "list": self._add_content(self.board_content, "list")
        elif bid == "clear": self._clear_drawings()
        elif bid == "ipan": self.imm_tool = "pan"
        elif bid == "idraw": self.imm_tool = "draw"
        elif bid == "ierase": self.imm_tool = "erase"
        elif bid == "icolor":
            c = QColorDialog.getColor(QColor(self.imm_color), self)
            if c.isValid(): self.imm_color = c.name()
        elif bid == "inote": self._add_content(self.opened["content"], "note", 20, 20)
        elif bid == "itable": self._add_content(self.opened["content"], "table", 20, 20)
        elif bid == "ilist": self._add_content(self.opened["content"], "list", 20, 20)
        elif bid == "ibw-": self.imm_width = max(1, self.imm_width-1)
        elif bid == "ibw+": self.imm_width = min(12, self.imm_width+1)
        elif bid == "edit": self._rename_block(self.opened, True)
        elif bid == "del": self._del_block(self.opened)
        elif bid == "close": self._close_block()
        self.update()

    def _zoom_by(self, f):
        cx, cy = self.width()/2, self.height()/2
        bx, by = self.s2b(cx, cy)
        self.zoom = max(0.1, min(5.0, self.zoom*f))
        self.cam_x, self.cam_y = cx-bx*self.zoom, cy-by*self.zoom
        self._save_settings()
        self.update()

    # ================= импорт / экспорт =================
    def _import_board(self):
        p, _ = QFileDialog.getOpenFileName(self, "Импорт доски", "", "JSON (*.json)")
        if not p: return
        try:
            d = json.loads(Path(p).read_text(encoding="utf-8"))
        except Exception:
            QMessageBox.warning(self, "Ошибка", "Не удалось прочитать файл"); return
        msg = QMessageBox(self)
        msg.setWindowTitle("Импорт"); msg.setText("Что сделать с импортированной доской?")
        b_over = msg.addButton("Переписать мою доску", QMessageBox.AcceptRole)
        b_user = msg.addButton("Создать пользователя", QMessageBox.ActionRole)
        msg.addButton("Отмена", QMessageBox.RejectRole)
        msg.exec_()
        cb = msg.clickedButton()
        if cb == b_over:
            self._snap()
            if "tabs" in d:
                src = next((t for t in d["tabs"] if t["id"] == d.get("active")), d["tabs"][0])
            else:
                src = d
            self.tab["items"] = src.get("items", [])
            self.tab["connections"] = src.get("connections", [])
            self.tab["background_drawings"] = src.get("background_drawings", [])
            self.tab["board_content"] = src.get("board_content", [])
            self._bind_tab()
            self.opened = None
            self._schedule_save(); self.update()
        elif cb == b_user:
            name = Path(p).stem or "import"
            base = name; i = 2
            while any(u["name"] == name for u in self.users):
                name = "%s_%d" % (base, i); i += 1
            self.users.append({"id": str(uuid.uuid4()), "name": name})
            self._save()
            self.current_user = name
            self.data_file = Path.home() / ("board_data_%s.json" % name)
            self._save_users()
            if "tabs" not in d:
                tab = {"id": str(uuid.uuid4()), "title": "Доска",
                       "items": d.get("items", []), "connections": d.get("connections", []),
                       "background_drawings": d.get("background_drawings", []),
                       "board_content": d.get("board_content", [])}
                d = {"tabs": [tab], "active": tab["id"]}
            self.data_file.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            self.opened = None; self._undo = []
            self._load_board(); self.update()

    def _show_export_menu(self):
        m = self._styled_menu()
        m.addAction("Экспорт JSON", lambda: self._export("json"))
        m.addAction("Экспорт XML", lambda: self._export("xml"))
        m.addAction("Экспорт ODS", self._export_ods)
        m.addAction("Экспорт PNG", self._export_png)
        self._exec_menu(m, QCursor.pos())

    def _export(self, fmt):
        p, _ = QFileDialog.getSaveFileName(self, "Экспорт", "board_data." + fmt, fmt.upper() + " (*." + fmt + ")")
        if not p: return
        if fmt == "xml":
            L = ['<?xml version="1.0" encoding="UTF-8"?>', "<board>"]
            for it in self.items:
                L.append('  <item id="%s" x="%s" y="%s">' % (it["id"], it["x"], it["y"]))
                L.append("    <title>%s</title>" % esc(it["title"]))
                for c in it.get("content", []):
                    L.append("    <content>%s</content>" % esc(json.dumps(c, ensure_ascii=False)))
                L.append("  </item>")
            for cn in self.connections:
                L.append('  <connection from="%s" to="%s"/>' % (cn["from"], cn["to"]))
            L.append("</board>")
            Path(p).write_text("\n".join(L), encoding="utf-8")
        else:
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"tabs": self.tabs, "active": self.tab["id"]}, f, ensure_ascii=False, indent=2)
        QMessageBox.information(self, "Готово", "Сохранено:\n" + p)

    def _export_ods(self):
        p, _ = QFileDialog.getSaveFileName(self, "Экспорт ODS", "board.ods", "ODS (*.ods)")
        if not p: return
        sheets = []
        def add_rows(rows, cl):
            if cl["type"] == "note":
                rows.append([cl.get("title", ""), cl.get("text", "").replace("\n", " | ")])
            elif cl["type"] == "list":
                rows.append([cl.get("title", "")])
                for it in cl.get("items", []):
                    rows.append(["[x]" if it.get("done") else "[ ]", it.get("text", "")])
            elif cl["type"] == "table":
                rows.append([cl.get("title", "")])
                rows += [list(r) for r in cl.get("rows", [])]
            rows.append([])
        rows = [["Доска (общие элементы)"], []]
        for cl in self.board_content: add_rows(rows, cl)
        sheets.append(("Доска", rows))
        for it in self.items:
            rows = [[it["title"]], []]
            for cl in it.get("content", []): add_rows(rows, cl)
            sheets.append((it["title"][:28] or it["id"][:8], rows))
        xml = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
               'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
               'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
               'office:version="1.2"><office:body><office:spreadsheet>']
        for name, rows in sheets:
            xml.append('<table:table table:name="%s">' % esc(name))
            xml.append('<table:table-column table:number-columns-repeated="6"/>')
            for r in rows:
                xml.append("<table:table-row>")
                for cell in r:
                    paras = "".join("<text:p>%s</text:p>" % esc(str(t)) for t in str(cell).split("\n")) or "<text:p/>"
                    xml.append('<table:table-cell office:value-type="string">%s</table:table-cell>' % paras)
                xml.append("</table:table-row>")
            xml.append("</table:table>")
        xml.append("</office:spreadsheet></office:body></office:document-content>")
        manifest = ('<?xml version="1.0" encoding="UTF-8"?>'
                    '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">'
                    '<manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.spreadsheet"/>'
                    '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/></manifest:manifest>')
        try:
            with zipfile.ZipFile(p, "w") as z:
                z.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.oasis.opendocument.spreadsheet", zipfile.ZIP_STORED)
                z.writestr("content.xml", "\n".join(xml))
                z.writestr("META-INF/manifest.xml", manifest)
            QMessageBox.information(self, "Готово", "Сохранено:\n" + p)
        except Exception as ex:
            QMessageBox.warning(self, "Ошибка", str(ex))

    def _export_png(self):
        p, _ = QFileDialog.getSaveFileName(self, "Экспорт PNG", "board.png", "PNG (*.png)")
        if not p: return
        img = QImage(self.width(), self.height(), QImage.Format_ARGB32)
        img.fill(QColor(self.P["bg"]))
        pa = QPainter(img)
        pa.setRenderHint(QPainter.Antialiasing)
        self._draw_world(pa)
        pa.end()
        img.save(p, "PNG")
        QMessageBox.information(self, "Готово", "Сохранено:\n" + p)

    def _clear_drawings(self):
        self._snap()
        self.bg_drawings.clear()
        for it in self.items: it["drawings"].clear()
        self._schedule_save(); self.update()

    # ================= иммерсив =================
    def _imm_rects(self):
        W, H = self.width(), self.height()
        m = 60; s = self.ui_scale
        top = m  # размер открытого блока НЕ зависит от панели вкладок
        p = (m, top, W-m, H-m)
        if self._close_anim:
            dt = time.time() - self._close_anim["t0"]
            tx, ty, tw, th = self._close_anim["to"]
            fx, fy, fw, fh = m, top, W-2*m, H-m-top
            if dt < 0.12:
                p = (fx, fy, fx+fw, fy+fh)
            else:
                k = (dt - 0.12) / 0.3
                if k >= 1:
                    self._close_anim = None
                    self.opened = None
                    p = (fx, fy, fx+fw, fy+fh)
                else:
                    e2 = 1 - (1-k)**3
                    x = fx + (tx-fx)*e2; y = fy + (ty-fy)*e2
                    w = fw + (tw-fw)*e2; h = fh + (th-fh)*e2
                    p = (x, y, x+w, y+h)
        elif self._open_anim:
            k = (time.time() - self._open_anim["t0"]) / 0.4
            if k >= 1:
                self._open_anim = None
            else:
                e2 = 1 - (1-k)**3
                fx, fy, fw, fh = self._open_anim["from"]
                x = fx + (m - fx)*e2
                y = fy + (top - fy)*e2
                w = fw + ((W-2*m) - fw)*e2
                h = fh + ((H-m-top) - fh)*e2
                p = (x, y, x+w, y+h)
        hdr = (p[0], p[1], p[2], p[1]+48*s)
        tb = (p[0], hdr[3], p[2], hdr[3]+42*s)
        area = (p[0], tb[3], p[2], p[3])
        return p, hdr, tb, area

    def _imm_press(self, x, y):
        p, hdr, tb, area = self._imm_rects()
        if not (area[1] <= y <= area[3] and area[0] <= x <= area[2]): return
        lx, ly = x-area[0]-self.imm_cam[0], y-area[1]-self.imm_cam[1]
        for i in reversed(range(len(self.opened["content"]))):
            c = self.opened["content"][i]
            hx, hy = c["x"]+c["w"], c["y"]+self._content_h(c)
            if abs(lx-hx) < 10 and abs(ly-hy) < 10:
                self.resize = {"kind": "imm", "index": i}; return
        hi, c = self._hit_content(self.opened["content"], lx, ly)
        if c:
            if c["type"] == "list" and lx-c["x"] < 26:
                i = self._list_index(c, ly-c["y"])
                if i is not None:
                    c["items"][i]["done"] = not c["items"][i]["done"]
                    self._schedule_save(); self.update(); return
            self.drag = {"kind": "imm", "index": hi, "moved": False, "ox": lx-c["x"], "oy": ly-c["y"]}; return
        if self.imm_tool == "draw":
            self.imm_drawing = True; self.imm_path = [(lx, ly)]; return
        if self.imm_tool == "erase":
            self._snap(); self._erase(self.opened["drawings"], lx, ly, 15); self.update(); return
        self.pan_start = (x, y)

    def _imm_move(self, x, y):
        p, hdr, tb, area = self._imm_rects()
        lx, ly = x-area[0]-self.imm_cam[0], y-area[1]-self.imm_cam[1]
        if self.imm_drawing:
            self.imm_path.append((lx, ly)); self.update(); return
        if self.imm_tool == "erase":
            self._erase(self.opened["drawings"], lx, ly, 15); self.update(); return
        if self.resize and self.resize["kind"] == "imm":
            c = self.opened["content"][self.resize["index"]]
            c["w"] = max(100, lx-c["x"]); c["h"] = max(50, ly-c["y"])
            self._schedule_save(); self.update(); return
        if self.drag and self.drag["kind"] == "imm":
            c = self.opened["content"][self.drag["index"]]
            aw, ah = area[2]-area[0], area[3]-area[1]
            c["x"] = max(0, min(lx-self.drag["ox"], max(0, aw-c["w"])))
            c["y"] = max(0, min(ly-self.drag["oy"], max(0, ah-self._content_h(c))))
            self.drag["moved"] = True
            self._schedule_save(); self.update(); return
        if self.pan_start:
            self.imm_cam[0] += x-self.pan_start[0]; self.imm_cam[1] += y-self.pan_start[1]
            self._clamp_imm_cam(area)
            self.pan_start = (x, y); self.update()

    def _imm_release(self, e=None):
        if self.imm_drawing and len(self.imm_path) > 1:
            self._snap()
            self.opened["drawings"].append({"points": self.imm_path, "color": self.imm_color, "width": self.imm_width})
            self._schedule_save()
        self.imm_drawing = False; self.imm_path = []
        self.drag = self.resize = self.pan_start = None
        self.update()

    def _imm_double(self, x, y):
        p, hdr, tb, area = self._imm_rects()
        if not (area[1] <= y <= area[3] and area[0] <= x <= area[2]): return
        lx, ly = x-area[0]-self.imm_cam[0], y-area[1]-self.imm_cam[1]
        hi, c = self._hit_content(self.opened["content"], lx, ly)
        if c: self._edit_content(self.opened["content"], hi, c, lx-c["x"], ly-c["y"], True)

    def _clamp_imm_cam(self, area):
        aw, ah = area[2]-area[0], area[3]-area[1]
        M = 600.0
        minX, minY, maxX, maxY = -M, -M, aw+M, ah+M
        for pth in self.opened["drawings"]:
            for q in pth["points"]:
                minX, minY = min(minX, q[0]), min(minY, q[1])
                maxX, maxY = max(maxX, q[0]), max(maxY, q[1])
        for c in self.opened["content"]:
            minX, minY = min(minX, c["x"]), min(minY, c["y"])
            maxX, maxY = max(maxX, c["x"]+c["w"]), max(maxY, c["y"]+self._content_h(c))
        if maxX - minX <= aw: loX, hiX = -minX, aw-maxX
        else: loX, hiX = min(0.0, aw-maxX), max(0.0, -minX)
        if maxY - minY <= ah: loY, hiY = -minY, ah-maxY
        else: loY, hiY = min(0.0, ah-maxY), max(0.0, -minY)
        self.imm_cam[0] = max(loX, min(hiX, self.imm_cam[0]))
        self.imm_cam[1] = max(loY, min(hiY, self.imm_cam[1]))
    # ================= отрисовка =================
    def paintEvent(self, ev):
        try:
            self._paint()
        except Exception:
            traceback.print_exc()

    def _paint(self):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self.P = self._pal()
        self._need_anim = False
        self._buttons, self._imm_btns, self._tab_btns, self._user_btns = [], [], [], []
        W, H = self.width(), self.height()
        s = self.ui_scale; z = self.zoom
        if self._search_open and self._search_edit:
            sw = min(int(420*s), int(W*0.6))
            self._search_edit.setGeometry(int(W/2 - sw/2), int(self._bar_h + 8), sw, int(28*s))
        ca = self._cam_anim
        if ca:
            k = min(1, (time.time()-ca["t0"])/0.3)
            e = 1-(1-k)**3
            self.zoom = ca["fz"] + (ca["tz"]-ca["fz"])*e
            self.cam_x = ca["fx"] + (ca["tx"]-ca["fx"])*e
            self.cam_y = ca["fy"] + (ca["ty"]-ca["fy"])*e
            if k >= 1:
                self._cam_anim = None; self._save_settings()
            else:
                self._need_anim = True
            z = self.zoom
        # панель вкладок: слайд, прижата к кромке
        bar_want = len(self.tabs) > 1
        if self.perf:
            self._tab_bar_visible = bar_want
            self._tab_bar_anim = None
        else:
            if bar_want and not self._tab_bar_visible:
                self._tab_bar_visible = True
                self._tab_bar_anim = {"t0": time.time(), "opening": True}
            if not bar_want and self._tab_bar_visible and not self._tab_bar_anim:
                self._tab_bar_anim = {"t0": time.time(), "opening": False}
        slide = 1.0
        if self._tab_bar_anim:
            k = min(1, (time.time()-self._tab_bar_anim["t0"])/0.25)
            e = 1-(1-k)**3
            slide = e if self._tab_bar_anim["opening"] else 1-e
            if k >= 1:
                if not self._tab_bar_anim["opening"]:
                    self._tab_bar_visible = False
                self._tab_bar_anim = None
            else:
                self._need_anim = True
        bar_show = bar_want or self._tab_bar_visible
        self._bar_h = 30*s if bar_show else 0
        self._top_off = self._bar_h * slide
        self._draw_world(p)
        if self.opened:
            try: self._draw_imm(p)
            except Exception: traceback.print_exc()
        if not self.opened:
            try: self._draw_tabs(p, W, s, -self._bar_h*(1-slide), slide)
            except Exception: traceback.print_exc()
            try:
                self._draw_panels(p, W, H, s, z, self._top_off)
                if self._search_open:
                    self._draw_search(p, W, s)
            except Exception: traceback.print_exc()
        if self._users_open or self._users_anim:
            try: self._draw_users(p, W, H, s)
            except Exception: traceback.print_exc()
        p.end()
        # инлайн-редактор
        ed = self._editor
        if ed:
            if ed["imm"] and not self.opened:
                self._close_editor(False)
            elif self._open_anim or self._close_anim:
                ed["w"].hide()
                if ed.get("hint"): ed["hint"].hide()
            else:
                if ed.get("fixed"):
                    sx, sy, swd, shd = ed["bx"], ed["by"], ed["bw"], ed["bh"]
                    fsize = max(8, int(ed["fs"]*self.ui_scale)); zf = 1
                elif ed["kind"] == "title" and ed["imm"] and self.opened:
                    pr, hdr, tb, area = self._imm_rects()
                    sx, sy = pr[0]+8, pr[1]+5
                    swd = max(120, (pr[2]-pr[0]) - 300*self.ui_scale)
                    shd = max(24, hdr[3]-pr[1]-10)
                    fsize = max(9, int(14*self.ui_scale)); zf = 1
                elif ed["kind"] == "title":
                    sx, sy = self.b2s(ed["ref"]["x"], ed["ref"]["y"])
                    swd = max(60, ed["ref"]["w"]*self.zoom); shd = max(22, 30*self.zoom)
                    fsize = max(8, int(13*self.zoom)); zf = self.zoom
                elif ed["imm"]:
                    pr, hdr, tb, area = self._imm_rects()
                    ox, oy = area[0]+self.imm_cam[0], area[1]+self.imm_cam[1]
                    sx, sy = ox+ed["bx"], oy+ed["by"]; zf = 1
                    swd = max(60, ed["bw"]*zf); shd = max(26, ed["bh"]*zf)
                    fsize = max(8, int(ed["fs"]*zf))
                else:
                    sx, sy = self.b2s(ed["bx"], ed["by"]); zf = ed["zf"]
                    swd = max(60, ed["bw"]*zf); shd = max(26, ed["bh"]*zf)
                    fsize = max(8, int(ed["fs"]*zf))
                ed["w"].show()
                ed["w"].setGeometry(int(sx), int(sy), int(swd), int(shd))
                ed["w"].setFont(self.font(fsize))
                if ed.get("hint"):
                    hw = max(180, int(240*zf))
                    ed["hint"].setFixedWidth(hw); ed["hint"].adjustSize()
                    hx2 = sx + swd + 8; hy2 = sy
                    if hx2 + hw > W - 8:
                        hx2 = sx; hy2 = sy + shd + 8
                    ed["hint"].move(int(hx2), int(hy2)); ed["hint"].show()
        if self._need_anim or self._anim or self._open_anim or self._close_anim or self._cam_anim:
            self.update()

    def _draw_world(self, p):
        W, H = self.width(), self.height()
        z = self.zoom
        p.setPen(Qt.NoPen); p.setBrush(QColor(self.P["bg"]))
        p.drawRect(QRectF(0, 0, W, H))
        sp = 32*z
        if sp > 12:
            p.setPen(Qt.NoPen); p.setBrush(QColor(self.P["grid"]))
            yy = self.cam_y % sp
            while yy < H:
                xx = self.cam_x % sp
                while xx < W:
                    p.drawEllipse(QPointF(xx, yy), 1.6, 1.6)
                    xx += sp
                yy += sp
        for d in self.bg_drawings: self._stroke(p, d["points"], d["color"], d["width"]*z, None, True)
        if self.cur_path: self._stroke(p, self.cur_path, self.brush_color, self.brush_width*z, None, True)
        for cn in self.connections:
            a = next((i for i in self.items if i["id"] == cn["from"]), None)
            b = next((i for i in self.items if i["id"] == cn["to"]), None)
            if not a or not b: continue
            ax, ay = self.b2s(a["x"]+a["w"]/2, a["y"]+a["h"]/2)
            bx, by = self.b2s(b["x"]+b["w"]/2, b["y"]+b["h"]/2)
            self._line(p, ax, ay, bx, by, "#757575", 4)
            p.setPen(Qt.NoPen); p.setBrush(QColor("#616161"))
            p.drawEllipse(QPointF(ax, ay), 7, 7); p.drawEllipse(QPointF(bx, by), 7, 7)
        for c in self.board_content:
            sx, sy = self.b2s(c["x"], c["y"])
            cx, cy = self.b2s(c["x"]+c["w"]/2, c["y"]+self._content_h(c)/2)
            self._anim_draw(p, cx, cy, "c:"+str(c.get("aid", "")),
                            lambda c=c, sx=sx, sy=sy: self._draw_content(p, c, sx, sy, z))
            hx, hy = self.b2s(c["x"]+c["w"], c["y"]+self._content_h(c))
            self._line(p, hx-10, hy, hx, hy, "#9E9E9E", 2)
            self._line(p, hx, hy-10, hx, hy, "#9E9E9E", 2)
        for it in self.items:
            cx, cy = self.b2s(it["x"]+it["w"]/2, it["y"]+it["h"]/2)
            self._anim_draw(p, cx, cy, "b:"+it["id"], lambda it=it: self._draw_block(p, it))

    def _draw_tabs(self, p, W, s, off, slide):
        bar_h = 30*s
        self._tab_btns = []
        if self.perf:
            slide = 1.0; self._tab_bar_anim = None; self._tab_anim = {}
        # ---------- режим без панели: поиск ПОД плюсом ----------
        if not self._tab_bar_visible:
            cx0, cy0 = 12*s + 68*s + 20*s, 16*s
            self._plus_geom = (cx0, cy0, 11*s)
            self._tab_btns.append({"plus": True, "cx": cx0, "cy": cy0, "r": 11*s})
            self._draw_plus(p, cx0, cy0, 11*s, s)
            sx0, sy0 = cx0, cy0 + 24*s
            self._search_geom = (sx0, sy0, 11*s)
            self._draw_search_btn(p, sx0, sy0, 11*s, s)
            return
        # ---------- панель видима: поиск СПРАВА от плюса ----------
        p.setPen(Qt.NoPen); p.setBrush(QColor(self.P["panel_out"]))
        p.drawRect(QRectF(0, off, W, bar_h))
        plus_w = 26*s
        sx0 = W - plus_w/2 - 6*s      # поиск — крайний справа
        cx0 = sx0 - 24*s              # плюс — слева от поиска
        cy0 = off + bar_h/2
        clip_x0 = 8*s
        clip_x1 = cx0 - 12*s
        p.save()
        p.setClipRect(QRectF(clip_x0, off, clip_x1-clip_x0, bar_h))
        x = clip_x0 - self._tabs_scroll
        end_x = clip_x0
        for t in self.tabs:
            e = 1.0
            if t["id"] in self._tab_anim:
                k = min(1, (time.time()-self._tab_anim[t["id"]])/0.25)
                e = 1-(1-k)**3
                if k >= 1: del self._tab_anim[t["id"]]
                else: self._need_anim = True
            tw_full = min(170*s, max(80*s, 16*s + self.mw(t["title"], 10*s) + 36*s))
            tw = tw_full * e
            armed = self._tab_close_arm == t["id"]
            active = t is self.tab
            fill = "#1E88E5" if armed else (self.P["panel"] if active else self.P["body"])
            tcol = "#FFFFFF" if armed else (self.P["text"] if active else self.P["label"])
            path = QPainterPath()
            path.moveTo(x, off + bar_h + 2)
            path.lineTo(x, off + 3*s + 8*s)
            path.arcTo(x, off + 3*s, 16*s, 16*s, 180, -90)
            path.lineTo(x + tw - 8*s, off + 3*s)
            path.arcTo(x + tw - 16*s, off + 3*s, 16*s, 16*s, 90, -90)
            path.lineTo(x + tw, off + bar_h + 2)
            path.closeSubpath()
            p.setBrush(QColor(fill)); p.setPen(Qt.NoPen); p.drawPath(path)
            p.save(); p.setClipRect(QRectF(0, off, W, bar_h-1))
            p.setPen(QPen(QColor(self.P["panel_out"]), 1)); p.setBrush(Qt.NoBrush)
            p.drawPath(path); p.restore()
            if tw > 40*s:
                p.setFont(self.font(10*s)); p.setPen(QColor(tcol)); p.setBrush(Qt.NoBrush)
                p.drawText(QRectF(x+8*s, off+3*s, tw-16*s-20*s, bar_h-3*s), Qt.AlignLeft|Qt.AlignVCenter,
                           self.trunc(t["title"], tw-36*s, 10*s))
                cxx = x + tw - 12*s
                p.setPen(QPen(QColor(tcol), max(1, 1.2*s), Qt.SolidLine, Qt.RoundCap))
                p.drawLine(QPointF(cxx-3*s, off+bar_h/2-3*s), QPointF(cxx+3*s, off+bar_h/2+3*s))
                p.drawLine(QPointF(cxx-3*s, off+bar_h/2+3*s), QPointF(cxx+3*s, off+bar_h/2-3*s))
                self._tab_btns.append({"tab": t, "x": x, "y": off, "w": tw, "h": bar_h,
                                       "cx": cxx, "cy": off+bar_h/2, "cr": 7*s})
            x += tw + 4*s
            end_x = x
        p.restore()
        self._tabs_content_w = (end_x + self._tabs_scroll) - clip_x0
        maxs = max(0, self._tabs_content_w - (clip_x1 - clip_x0))
        if self._tabs_scroll > maxs: self._tabs_scroll = maxs
        self._plus_geom = (cx0, cy0, 9*s)
        self._tab_btns.append({"plus": True, "cx": cx0, "cy": cy0, "r": 9*s})
        self._search_geom = (sx0, cy0, 9*s)
        self._draw_search_btn(p, sx0, cy0, 9*s, s)
        self._draw_plus(p, cx0, cy0, 9*s, s, True)

    def _draw_plus(self, p, cx0, cy0, r, s, left=False):
        label = "вкладка"
        lw = self.mw(label, 10*s)
        if self._plus_hover:
            pill_w = 2*r + 8*s + lw + 8*s
            x0 = (cx0 + r - pill_w) if left else (cx0 - r)
            p.setBrush(QColor(self.P["panel"]))
            p.setPen(QPen(QColor(self.P["panel_out"]), 1))
            p.drawRoundedRect(QRectF(x0, cy0-r, pill_w, 2*r), r, r)
            p.setPen(QPen(QColor(self.P["text"]), max(1, 1.4*s), Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(cx0-3.5*s, cy0), QPointF(cx0+3.5*s, cy0))
            p.drawLine(QPointF(cx0, cy0-3.5*s), QPointF(cx0, cy0+3.5*s))
            p.setFont(self.font(10*s)); p.setBrush(Qt.NoBrush)
            tx = (x0 + 6*s) if left else (cx0 + r + 2*s)
            p.drawText(QRectF(tx, cy0-r, lw+8*s, 2*r), Qt.AlignLeft|Qt.AlignVCenter, label)
        else:
            p.setBrush(QColor(self.P["panel"]))
            p.setPen(QPen(QColor(self.P["panel_out"]), 1))
            p.drawEllipse(QPointF(cx0, cy0), r, r)
            p.setPen(QPen(QColor(self.P["text"]), max(1, 1.4*s), Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(cx0-3.5*s, cy0), QPointF(cx0+3.5*s, cy0))
            p.drawLine(QPointF(cx0, cy0-3.5*s), QPointF(cx0, cy0+3.5*s))

    def _draw_block(self, p, it):
        z = self.zoom
        sx, sy = self.b2s(it["x"], it["y"])
        sw, sh = it["w"]*z, it["h"]*z
        self._rrect(p, sx+3*z, sy+5*z, sw, sh, 16*z, fill=self.P["shadow"])
        self._rrect(p, sx, sy, sw, sh, 16*z, fill=self.P["body"], outline=it["color"], width=max(1, 3*z))
        hh = 30*z
        path = self._rpath(sx, sy, sw, hh, 16*z)
        path.addRect(QRectF(sx, sy+hh-8*z, sw, 8*z))
        path.setFillRule(Qt.WindingFill)
        self._fill(p, path, it["color"])
        tfs = max(8, int(13*z))
        p.setFont(self.font(tfs, True)); p.setPen(QColor("#FFFFFF")); p.setBrush(Qt.NoBrush)
        p.drawText(QRectF(sx+10*z, sy, sw-20*z, hh), Qt.AlignLeft|Qt.AlignVCenter,
                   self.trunc(it["title"], sw-20*z, tfs, True))
        y = sy + hh + 8*z
        pfs = max(7, int(11*z))
        for c in [c for c in it.get("content", []) if c["type"] == "note"][:3]:
            self._rrect(p, sx+8*z, y, sw-16*z, 20*z, 6*z, fill=self.P["prev"], outline=self.P["prev_out"])
            p.setFont(self.font(pfs)); p.setPen(QColor(self.P["text"]))
            p.drawText(QRectF(sx+14*z, y, sw-28*z, 20*z), Qt.AlignLeft|Qt.AlignVCenter,
                       self.trunc((c.get("text","") or "").split("\n")[0], sw-28*z, pfs))
            y += 24*z
        n = len(it.get("content", []))
        p.setFont(self.font(max(7, int(9*z)))); p.setPen(QColor(self.P["label"]))
        p.drawText(QRectF(sx+8*z, sy+sh-16*z, sw-16*z, 12*z), Qt.AlignLeft|Qt.AlignVCenter,
                   "Элементов: %d" % n)
        if self.selected_id == it["id"] or self.conn_start == it["id"]:
            col = "#E53935" if self.conn_start == it["id"] else it["color"]
            p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(col), 2, Qt.DashLine))
            p.drawRect(QRectF(sx-7, sy-7, sw+14, sh+14))
            self._line(p, sx+sw-12, sy+sh, sx+sw, sy+sh, "#757575", 2)
            self._line(p, sx+sw, sy+sh-12, sx+sw, sy+sh, "#757575", 2)

    def _draw_content(self, p, c, sx, sy, sc):
        w = c["w"]*sc; h = self._content_h(c)*sc
        fs = c.get("fontSize", 13)*sc
        self._rrect(p, sx+3*sc, sy+4*sc, w, h, 10*sc, fill=self.P["shadow"])
        if c["type"] == "note":
            self._rrect(p, sx, sy, w, h, 10*sc, fill=self.P["note_bg"], outline=self.P["note_out"], width=2)
            t_h = 0
            if c.get("title"):
                tfs2 = max(7, int(10*sc)); t_h = 16*sc
                p.setFont(self.font(tfs2, True)); p.setPen(QColor(self.P["note_text"]))
                p.drawText(QRectF(sx+6*sc, sy+2*sc, w-12*sc, t_h), Qt.AlignLeft|Qt.AlignVCenter,
                           self.trunc(c.get("title", ""), w-12*sc, tfs2, True))
            self._draw_rich(p, sx+8*sc, sy+4*sc+t_h, w-16*sc, h-8*sc-t_h, c.get("text", ""), fs, self.P["note_text"])
        elif c["type"] == "table":
            rows = c.get("rows", [])
            cols = len(rows[0]) if rows else 3
            cw = w/max(1, cols); ch = (h-24*sc)/max(1, len(rows))
            self._rrect(p, sx, sy, w, h, 10*sc, fill=self.P["body"], outline="#4CAF50", width=2)
            p.setFont(self.font(max(7, int(9*sc)))); p.setPen(QColor(self.P["label"]))
            p.drawText(QRectF(sx+6*sc, sy+2*sc, w-12*sc, 18*sc), Qt.AlignLeft|Qt.AlignVCenter,
                       self.trunc(c.get("title", "Таблица"), w-12*sc, 9*sc))
            cfs = max(7, int(fs*0.9))
            for r, row in enumerate(rows):
                for cc, cell in enumerate(row):
                    x1, y1 = sx+cc*cw, sy+(24*sc+r*ch)
                    p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(self.P["cell_out"]), 1))
                    p.drawRect(QRectF(x1, y1, cw, ch))
                    p.setFont(self.font(cfs)); p.setPen(QColor(self.P["text"]))
                    lines = self._wrap_segs([(str(cell), False, False)], cfs, cw-8*sc)
                    maxl = max(1, int(ch/(cfs*1.2)))
                    for li, ln in enumerate(lines[:maxl]):
                        p.drawText(QRectF(x1+4*sc, y1+2*sc+li*cfs*1.2, cw-8*sc, cfs*1.2),
                                   Qt.AlignLeft|Qt.AlignVCenter, "".join(t for t,_,_ in ln))
        else:
            rows, total, lfs = self._list_layout(c)
            self._rrect(p, sx, sy, w, h, 10*sc, fill=self.P["body"], outline="#2196F3", width=2)
            p.setFont(self.font(max(7, int(9*sc)))); p.setPen(QColor(self.P["label"]))
            p.drawText(QRectF(sx+6*sc, sy+2*sc, w-12*sc, 18*sc), Qt.AlignLeft|Qt.AlignVCenter,
                       self.trunc(c.get("title", "Список"), w-12*sc, 9*sc))
            lhpx = lfs*1.2*sc
            for i, it in enumerate(c.get("items", [])):
                if i >= len(rows): break
                R = rows[i]
                y1 = sy + R["y"]*sc
                rh = R["h"]*sc
                if y1 >= sy + h: break
                box = max(5, min(14*sc, rh-6*sc))
                p.setPen(QPen(QColor(self.P["cell_out"]), 1))
                p.setBrush(QColor("#43A047") if it.get("done") else QBrush(Qt.NoBrush))
                p.drawRect(QRectF(sx+6*sc, y1+(rh-box)/2, box, box))
                if it.get("done"):
                    p.setPen(QPen(QColor("#FFFFFF"), max(1, 2*sc), Qt.SolidLine, Qt.RoundCap))
                    cx0, cy0 = sx+6*sc, y1+(rh-box)/2
                    p.drawLine(QPointF(cx0+box*0.2, cy0+box*0.55), QPointF(cx0+box*0.42, cy0+box*0.78))
                    p.drawLine(QPointF(cx0+box*0.42, cy0+box*0.78), QPointF(cx0+box*0.82, cy0+box*0.25))
                p.setFont(self.font(lfs*sc))
                p.setPen(QColor(self.P["label"]) if it.get("done") else QColor(self.P["text"]))
                if len(R["lines"]) == 1:
                    ys = [y1 + (rh - lhpx)/2]
                else:
                    ys = [y1 + 4*sc, y1 + 4*sc + lhpx]
                for li, ln in enumerate(R["lines"]):
                    p.drawText(QRectF(sx+26*sc, ys[li], w-32*sc, lhpx),
                               Qt.AlignLeft|Qt.AlignVCenter, "".join(t for t,_,_ in ln))
                self._line(p, sx+6*sc, y1+rh-1, sx+w-6*sc, y1+rh-1, self.P["cell_out"], 1)

    def _draw_rich(self, p, x, y, max_w, max_h, text, base_fs, tcol):
        p.setBrush(Qt.NoBrush)
        cy = y
        for align, mul, lbold, bullet, line in rich_lines(text):
            fs = max(7, int(base_fs*mul))
            lh = fs*1.35
            segs = [(t, b or lbold, i) for t, b, i in inline_segments(line)]
            off = fs if bullet else 0
            vlines = self._wrap_segs(segs, fs, max(20, max_w - off))
            for vi, vl in enumerate(vlines):
                if cy + lh > y + max_h: break
                widths = [self.mw(t, fs, b, i) for t, b, i in vl]
                tot = sum(widths)
                if bullet and vi == 0:
                    p.setFont(self.font(fs)); p.setPen(QColor(tcol))
                    p.drawText(QRectF(x, cy, fs, lh), Qt.AlignLeft|Qt.AlignVCenter, "•")
                if align == "right":   sxx = x + max_w - tot - off
                elif align == "center": sxx = x + off + (max_w - tot)/2
                else:                  sxx = x + off
                cx = sxx
                for (t, b, i), w_ in zip(vl, widths):
                    if t.strip():
                        p.setFont(self.font(fs, b or lbold, i)); p.setPen(QColor(tcol))
                        p.drawText(QRectF(cx, cy, w_+2, lh), Qt.AlignLeft|Qt.AlignVCenter, t)
                    cx += w_
                cy += lh

    def _btn(self, p, lst, bid, x, y, w, h, text, cmd, fill="#FFFFFF", outline=None, fg="#212121",
             bold=False, active=False, ow=1, icon=None):
        lst.append({"id": bid, "x": x, "y": y, "w": w, "h": h, "cmd": cmd})
        r = 10*self.ui_scale
        self._rrect(p, x, y, w, h, r, fill=fill, outline=outline or self.P["panel_out"], width=ow)
        if active:
            self._outline(p, self._rpath(x+2, y+2, w-4, h-4, max(2, r-2)), "#FFFFFF", 2)
        elif self._down_btn == bid:
            self._outline(p, self._rpath(x+2, y+2, w-4, h-4, max(2, r-2)), self.P["ring"], 2)
        icol = fg
        if icon and text:
            isz = h*0.55
            self._icon(p, icon, x+6, y+(h-isz)/2, isz, icol)
            f = self.font(10*self.ui_scale, bold)
            txt = QFontMetrics(f).elidedText(text, Qt.ElideRight, int(w-10-isz))
            p.setFont(f); p.setPen(QColor(fg)); p.setBrush(Qt.NoBrush)
            p.drawText(QRectF(x+8+isz, y, w-10-isz, h), Qt.AlignLeft|Qt.AlignVCenter, txt)
        elif icon:
            isz = h*0.6
            self._icon(p, icon, x+(w-isz)/2, y+(h-isz)/2, isz, icol)
        elif text:
            f = self.font(10*self.ui_scale, bold)
            txt = QFontMetrics(f).elidedText(text, Qt.ElideRight, int(w-6))
            p.setFont(f); p.setPen(QColor(fg)); p.setBrush(Qt.NoBrush)
            p.drawText(QRectF(x, y, w, h), Qt.AlignCenter, txt)

    def _label(self, p, x, y, w, h, text, size):
        f = self.font(size)
        txt = QFontMetrics(f).elidedText(text, Qt.ElideRight, int(w-2))
        p.setFont(f); p.setPen(QColor(self.P["label"])); p.setBrush(Qt.NoBrush)
        p.drawText(QRectF(x, y, w, h), Qt.AlignCenter, txt)

    def _draw_panels(self, p, W, H, s, z, top_off=0):
        bs = 44*s; pad = 8*s; label_h = 12*s; gap = 4*s
        row = bs + label_h + gap
        # левая
        try:
            lx, ly = 12*s, 12*s + top_off
            bw = 52*s
            ph = 2*pad + 5*row + (bs//2 + gap) + (16*s + label_h)
            self._rrect(p, lx, ly, bw+2*pad, ph, 14*s, fill=self.P["panel"], outline=self.P["panel_out"])
            yy = ly + pad
            tools = [("pan", "pan", "Холст", "#BBDEFB"), ("draw", "draw", "Кисть", "#FFE082"),
                     ("erase", "erase", "Ластик", "#F8BBD0"), ("connect", "connect", "Связь", "#C8E6C9"),
                     ("color", "color", "Цвет", "#E1BEE7")]
            for tid, ic, lab, col in tools:
                active = (tid == self.tool)
                if tid == "color": cmd = self._pick_color
                else: cmd = (lambda t=tid: (setattr(self, "tool", t), setattr(self, "conn_start", None), self.update()))
                self._btn(p, self._buttons, tid, lx+pad, yy, bw, bs, None, cmd,
                          fill="#3F51B5" if active else col,
                          outline="#283593" if active else None,
                          fg="#FFFFFF" if active else "#212121", active=active, icon=ic)
                self._label(p, lx+pad, yy+bs, bw, label_h, lab, 8*s)
                yy += row
            self._btn(p, self._buttons, "bw-", lx+pad, yy, bw//2-2, bs//2, "−",
                      lambda: (setattr(self, "brush_width", max(1, self.brush_width-1)), self.update()))
            self._btn(p, self._buttons, "bw+", lx+pad+bw//2+2, yy, bw//2-2, bs//2, "+",
                      lambda: (setattr(self, "brush_width", min(14, self.brush_width+1)), self.update()))
            yy += bs//2 + gap
            d = min(16*s, 4 + self.brush_width*1.2*s)
            p.setPen(Qt.NoPen); p.setBrush(QColor(self.brush_color))
            p.drawEllipse(QPointF(lx+pad+bw/2, yy+8*s), d/2, d/2)
            self._label(p, lx+pad, yy+16*s, bw, label_h, "Толщ.", 8*s)
        except Exception:
            traceback.print_exc()
        # правая
        try:
            rw = 60*s
            rx = W - (rw + 2*pad) - 12*s
            ry = 12*s + top_off
            rbtns = [("settings", "gear", "Настройки", "#CFD8DC"), ("z-", "minus", "Меньше", "#DCEDC8"),
                     ("z+", "plus", "Больше", "#DCEDC8"), ("perf", "lightning", "Скорость", "#FFECB3")]
            rh = 2*pad + len(rbtns)*row + 14*s
            self._rrect(p, rx, ry, rw+2*pad, rh, 14*s, fill=self.P["panel"], outline=self.P["panel_out"])
            yy = ry + pad
            for bid, ic, lab, col in rbtns:
                if bid == "settings": cmd = self._toggle_settings
                elif bid == "z-": cmd = lambda: self._zoom_by(1/1.2)
                elif bid == "z+": cmd = lambda: self._zoom_by(1.2)
                else: cmd = lambda: (setattr(self, "perf", not self.perf), self._save_settings(), self.update())
                self._btn(p, self._buttons, bid, rx+pad, yy, rw, bs, None, cmd, fill=col, icon=ic,
                          active=(bid == "settings" and self._settings_open) or (bid == "perf" and self.perf))
                self._label(p, rx+pad, yy+bs, rw, label_h, lab, 8*s)
                yy += row
            self._label(p, rx+pad, yy, rw, 14*s, "%d%%" % int(z*100), 9*s)
            self._draw_settings(p, rx, ry, s, bs, pad, row, label_h)
        except Exception:
            traceback.print_exc()
        # нижний док
        try:
            items_b = [("block", "block", "Блок", 80, "#9FA8DA"),
                       ("note", "note", "Заметка", 92, "#FFE082"),
                       ("table", "table", "Таблица", 96, "#80CBC4"),
                       ("list", "list", "Список", 86, "#81D4FA"),
                       ("clear", "clear", "Очистить", 100, "#EF9A9A")]
            widths = [w*s for _, _, _, w, _ in items_b]
            gapb = 6*s
            total = pad*2 + sum(widths) + gapb*(len(items_b)-1)
            bx0 = (W - total)/2
            by0 = H - (bs + pad*2) - 12*s
            self._rrect(p, bx0, by0, total, bs+pad*2, 14*s, fill=self.P["panel"], outline=self.P["panel_out"])
            xx = bx0 + pad
            for i, (bid, ic, label, w, col) in enumerate(items_b):
                w = widths[i]
                if bid == "block": cmd = self._add_block_dialog
                elif bid == "clear": cmd = self._clear_drawings
                else: cmd = (lambda k=bid: self._add_content(self.board_content, k))
                self._btn(p, self._buttons, bid, xx, by0+pad, w, bs, label, cmd, fill=col, icon=ic)
                xx += w + (gapb if i < len(items_b)-1 else 0)
        except Exception:
            traceback.print_exc()

    def _draw_settings(self, p, rx, ry, s, bs, pad, row, label_h):
        if not self._settings_open: return
        we = 1.0; bo = 1.0
        anim = self._settings_anim
        if anim and not self.perf:
            k = min(1, (time.time()-anim["t0"])/0.4)
            if k >= 1:
                self._settings_anim = None
            else:
                we = 1-(1-min(1, k/0.6))**3
                bo = max(0.0, min(1.0, (k-0.6)/0.4))
                self._need_anim = True
        elif anim:
            self._settings_anim = None
        show_btns = bo > 0
        sbtns = [("user", "user", "Польз.", "#B0BEC5"), ("theme", "theme", "Тема", "#FFE0B2"),
                 ("import", "import", "Импорт", "#D1C4E9"), ("export", "export", "Экспорт", "#D1C4E9"),
                 ("ui", "ui", "Масштаб", "#CFD8DC")]
        sbw = 64*s; gap_s = 6*s
        full_w = len(sbtns)*(sbw+gap_s) - gap_s + 2*pad
        w_cur = max(20*s, full_w * we)
        x0 = rx - 8*s - w_cur
        y0 = ry
        h0 = 2*pad + row
        self._rrect(p, x0, y0, w_cur, h0, 14*s, fill=self.P["panel"], outline=self.P["panel_out"])
        if show_btns:
            p.save(); p.setOpacity(bo)
            xx = x0 + pad
            for bid, ic, lab, col in sbtns:
                if bid == "user": cmd = self._open_users
                elif bid == "theme": cmd = lambda: (setattr(self, "dark", not self.dark), self._save_settings(), self.update())
                elif bid == "import": cmd = self._import_board
                elif bid == "export": cmd = self._show_export_menu
                else: cmd = self._ui_scale_dialog
                self._btn(p, self._buttons, bid, xx, y0+pad, sbw, bs, None, cmd, fill=col, icon=ic)
                self._label(p, xx, y0+pad+bs, sbw, label_h, lab, 8*s)
                xx += sbw + gap_s
            p.restore()

    def _draw_users(self, p, W, H, s):
        if not self._users_open:
            self._users_anim = None
            return
        be = 1.0; bo = 1.0
        anim = self._users_anim
        if anim:
            if self.perf:
                self._users_anim = None
            else:
                k = min(1, (time.time()-anim["t0"])/0.4)
                if k >= 1:
                    self._users_anim = None
                else:
                    be = 1-(1-min(1, k/0.6))**3
                    bo = max(0.0, min(1.0, (k-0.6)/0.4))
                    self._need_anim = True
        show_btns = bo > 0
        p.setPen(Qt.NoPen); p.setBrush(QColor(0, 0, 0, int(140*be)))
        p.drawRect(QRectF(0, 0, W, H))
        w_u = min(460*s, W-140); h_u = min(340*s, H-140)
        wc, hc = w_u*(0.7+0.3*be), h_u*(0.7+0.3*be)
        x0, y0 = (W-wc)/2, (H-hc)/2
        self._user_rect = (x0, y0, x0+wc, y0+hc)
        p.save(); p.setOpacity(max(0.1, be))
        self._rrect(p, x0, y0, wc, hc, 16*s, fill=self.P["panel"])
        self._outline(p, self._rpath(x0, y0, wc, hc, 16*s), self.P["panel_out"], 1)
        if show_btns:
            p.save(); p.setOpacity(bo)
            p.setFont(self.font(14*s, True)); p.setPen(QColor(self.P["text"]))
            p.drawText(QRectF(x0+16*s, y0+8*s, wc-80*s, 28*s), Qt.AlignLeft|Qt.AlignVCenter, "Пользователи")
            self._user_btns.append({"id": "close", "x": x0+wc-40*s, "y": y0+10*s, "w": 28*s, "h": 24*s})
            self._btn(p, [], "uclose", x0+wc-40*s, y0+10*s, 28*s, 24*s, "X", lambda: None,
                      fill=self.P["panel"], outline=self.P["panel_out"], fg=self.P["text"])
            yy = y0 + 44*s
            for u in self.users:
                if yy + 34*s > y0 + hc - 44*s: break
                cur = u["name"] == self.current_user
                self._rrect(p, x0+16*s, yy, wc-32*s, 30*s, 10*s, fill=self.P["body"],
                            outline=self.P["ring"] if cur else self.P["panel_out"],
                            width=2 if cur else 1)
                p.setFont(self.font(11*s)); p.setPen(QColor(self.P["text"]))
                p.drawText(QRectF(x0+28*s, yy, wc-80*s, 30*s), Qt.AlignLeft|Qt.AlignVCenter, u["name"])
                self._user_btns.append({"id": "switch", "name": u["name"],
                                        "x": x0+16*s, "y": yy, "w": wc-32*s, "h": 30*s})
                if not cur:
                    dx = x0+wc-16*s-20*s
                    p.setPen(QPen(QColor(self.P["text"]), max(1, 1.4*s), Qt.SolidLine, Qt.RoundCap))
                    p.drawLine(QPointF(dx-4*s, yy+11*s), QPointF(dx+4*s, yy+19*s))
                    p.drawLine(QPointF(dx-4*s, yy+19*s), QPointF(dx+4*s, yy+11*s))
                    self._user_btns.append({"id": "deluser", "name": u["name"],
                                            "x": dx-8*s, "y": yy, "w": 16*s, "h": 30*s})
                yy += 36*s
            byy = y0 + hc - 36*s
            self._user_btns.append({"id": "new", "x": x0+16*s, "y": byy, "w": 110*s, "h": 26*s})
            self._btn(p, [], "unew", x0+16*s, byy, 110*s, 26*s, "+ Новый", lambda: None,
                      fill=self.P["body"], outline=self.P["panel_out"], fg=self.P["text"])
            self._user_btns.append({"id": "rename", "x": x0+134*s, "y": byy, "w": 140*s, "h": 26*s})
            self._btn(p, [], "urename", x0+134*s, byy, 140*s, 26*s, "Переименовать", lambda: None,
                      fill=self.P["body"], outline=self.P["panel_out"], fg=self.P["text"])
            p.restore()
        p.restore()

    # ---------- поиск ----------
    def _draw_search_btn(self, p, cx, cy, r, s):
        p.setBrush(QColor(self.P["panel"]))
        p.setPen(QPen(QColor(self.P["panel_out"]), 1))
        p.drawEllipse(QPointF(cx, cy), r, r)
        p.setPen(QPen(QColor(self.P["text"]), max(1, 1.3*s), Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx-1.5*s, cy-1.5*s), r*0.4, r*0.4)
        p.drawLine(QPointF(cx+1.5*s, cy+1.5*s), QPointF(cx+r*0.6, cy+r*0.6))

    def _toggle_search(self):
        if self._search_open:
            self._close_search(); return
        if self._search_edit is None:
            le = QLineEdit(self)
            le.setPlaceholderText("Поиск…")
            le.setStyleSheet("background:%s; color:%s; border:2px solid #1E88E5; border-radius:8px; padding:4px;" % (self.P["body"], self.P["text"]))
            le.textChanged.connect(self._on_search)
            le.installEventFilter(self)
            self._search_edit = le
        s = self.ui_scale
        w = 420*s
        self._search_edit.show(); self._search_edit.setFocus()
        self._search_open = True
        self.update()

    def _close_search(self):
        self._search_open = False
        if self._search_edit: self._search_edit.hide()
        self._search_btns = []
        self.setFocus(); self.update()

    def _on_search(self, text):
        t = text.strip().lower()
        res = []
        if t:
            for it in self.items:
                if t in it["title"].lower():
                    res.append({"label": "Блок: " + it["title"], "x": it["x"], "y": it["y"], "w": it["w"], "h": it["h"]})
            for c in self.board_content:
                title = c.get("title", "") or ""
                blob = title
                if c["type"] == "note": blob += " " + c.get("text", "")
                elif c["type"] == "list": blob += " " + " ".join(i.get("text","") for i in c.get("items", []))
                elif c["type"] == "table": blob += " " + " ".join(" ".join(r) for r in c.get("rows", []))
                if t in blob.lower():
                    res.append({"label": c["type"] + ": " + (title or "(без названия)"), "x": c["x"], "y": c["y"], "w": c["w"], "h": self._content_h(c)})
        self._search_results = res
        self.update()

    def _goto(self, r):
        W, H = self.width(), self.height()
        tz = max(0.5, min(1.5, min(W/(r["w"]+300), H/(r["h"]+300))))
        self._cam_anim = {"t0": time.time(), "fx": self.cam_x, "fy": self.cam_y, "fz": self.zoom,
                          "tx": W/2 - (r["x"]+r["w"]/2)*tz, "ty": H/2 - (r["y"]+r["h"]/2)*tz, "tz": tz}
        self._close_search()
        self.update()

    def _draw_search(self, p, W, s):
        if not self._search_edit: return
        txt = self._search_edit.text().strip().lower()
        self._search_btns = []
        if not txt or not self._search_results: return
        bw = 420*s
        bx = W/2 - bw/2
        by = self._search_edit.geometry().bottom() + 6
        n = min(8, len(self._search_results))
        rh = 26*s
        self._rrect(p, bx, by, bw, n*rh + 8*s, 10*s, fill=self.P["panel"], outline=self.P["panel_out"])
        for i in range(n):
            r = self._search_results[i]
            yy = by + 4*s + i*rh
            self._search_btns.append({"x": bx, "y": yy, "w": bw, "h": rh, "r": r})
            p.setFont(self.font(10*s)); p.setPen(QColor(self.P["text"])); p.setBrush(Qt.NoBrush)
            p.drawText(QRectF(bx+10*s, yy, bw-20*s, rh), Qt.AlignLeft|Qt.AlignVCenter,
                       self.trunc(r["label"], bw-20*s, 10*s))

    # ---------- иммерсив ----------
    def _draw_imm(self, p):
        pr, hdr, tb, area = self._imm_rects()
        it = self.opened
        if not it: return
        s = self.ui_scale
        W, H = self.width(), self.height()
        show_ui = (self._open_anim is None) and (self._close_anim is None)
        if self._open_anim:
            k = min(1.0, (time.time() - self._open_anim["t0"]) / 0.4)
            alpha = int(140 * (1-(1-k)**3))
            if k < 1: self._need_anim = True
        elif self._close_anim:
            dt = time.time() - self._close_anim["t0"]
            if dt < 0.12: alpha = 140; self._need_anim = True
            else:
                k = min(1.0, (dt-0.12)/0.3)
                alpha = int(140 * (1 - (1-(1-k)**3)))
                if k < 1: self._need_anim = True
        else:
            alpha = 140
        p.setPen(Qt.NoPen); p.setBrush(QColor(0, 0, 0, alpha))
        p.drawRect(QRectF(0, 0, W, H))
        self._rrect(p, pr[0], pr[1], pr[2]-pr[0], pr[3]-pr[1], 20, fill=self.P["body"])
        panel_path = self._rpath(pr[0], pr[1], pr[2]-pr[0], pr[3]-pr[1], 20)
        p.save()
        p.setClipPath(panel_path)
        p.setClipRect(QRectF(area[0], area[1], area[2]-area[0], area[3]-area[1]), Qt.IntersectClip)
        try:
            ox, oy = area[0]+self.imm_cam[0], area[1]+self.imm_cam[1]
            p.setPen(Qt.NoPen); p.setBrush(QColor(self.P["area"]))
            p.drawRect(QRectF(area[0], area[1], area[2]-area[0], area[3]-area[1]))
            if show_ui:
                p.setBrush(QColor(self.P["grid"]))
                for gy in range(int(area[1]), int(area[3]), 28):
                    for gx in range(int(area[0]), int(area[2]), 28):
                        p.drawEllipse(QPointF(gx+((ox-area[0])%28), gy+((oy-area[1])%28)), 1.5, 1.5)
                for dd in it["drawings"]:
                    self._stroke(p, [(q[0]+ox, q[1]+oy) for q in dd["points"]], dd["color"], dd["width"], None, False)
                if self.imm_path:
                    self._stroke(p, [(q[0]+ox, q[1]+oy) for q in self.imm_path], self.imm_color, self.imm_width, None, False)
                for c in it["content"]:
                    self._draw_content(p, c, c["x"]+ox, c["y"]+oy, 1)
                    hx, hy = c["x"]+ox+c["w"], c["y"]+oy+self._content_h(c)
                    self._line(p, hx-10, hy, hx, hy, "#9E9E9E", 2)
                    self._line(p, hx, hy-10, hx, hy, "#9E9E9E", 2)
        finally:
            p.restore()
        if show_ui:
            p.save()
            p.setClipRect(QRectF(tb[0], tb[1], tb[2]-tb[0], tb[3]-tb[1]))
            p.setPen(Qt.NoPen); p.setBrush(QColor(self.P["toolbar"]))
            p.drawRect(QRectF(tb[0], tb[1], tb[2]-tb[0], tb[3]-tb[1]))
            self._line(p, tb[0], tb[3], tb[2], tb[3], self.P["panel_out"])
            x = tb[0] + 10*s - self.imm_tb_scroll
            tbtns = [("ipan", "pan", "Рука", 70, "#BBDEFB"), ("idraw", "draw", "Кисть", 70, "#FFE082"),
                     ("ierase", "erase", "Ластик", 80, "#F8BBD0"), ("icolor", "color", "Цвет", 70, "#E1BEE7"),
                     ("inote", "note", "Заметка", 92, "#FFE082"), ("itable", "table", "Таблица", 96, "#80CBC4"),
                     ("ilist", "list", "Список", 84, "#81D4FA")]
            for bid, ic, label, w_btn, col in tbtns:
                w_btn = w_btn*s
                active = (bid == self.imm_tool)
                if bid in ("ipan", "idraw", "ierase"):
                    cmd = (lambda t=bid[1:]: (setattr(self, "imm_tool", t), self.update()))
                elif bid == "icolor": cmd = self._pick_imm_color
                elif bid == "inote": cmd = lambda: self._add_content(it["content"], "note", 20, 20)
                elif bid == "itable": cmd = lambda: self._add_content(it["content"], "table", 20, 20)
                else: cmd = lambda: self._add_content(it["content"], "list", 20, 20)
                self._btn(p, self._imm_btns, bid, x, tb[1]+6*s, w_btn, 30*s, label, cmd,
                          fill="#3F51B5" if active else col,
                          outline="#283593" if active else None,
                          fg="#FFFFFF" if active else "#212121", active=active, icon=ic)
                x += w_btn + 6*s
            self._btn(p, self._imm_btns, "ibw-", x, tb[1]+6*s, 26*s, 30*s, "−",
                      lambda: (setattr(self, "imm_width", max(1, self.imm_width-1)), self.update()))
            self._btn(p, self._imm_btns, "ibw+", x+30*s, tb[1]+6*s, 26*s, 30*s, "+",
                      lambda: (setattr(self, "imm_width", min(12, self.imm_width+1)), self.update()))
            d = min(24*s, 4 + self.imm_width*2*s)
            p.setPen(Qt.NoPen); p.setBrush(QColor(self.imm_color))
            p.drawEllipse(QPointF(x+70*s, (tb[1]+tb[3])/2), d/2, d/2)
            self._tb_content_w = (x + 100*s) - (tb[0] + 10*s) + self.imm_tb_scroll
            p.restore()
            path = self._rpath(pr[0]+2, pr[1]+2, pr[2]-pr[0]-4, hdr[3]-pr[1]-2, 16)
            path.addRect(QRectF(pr[0]+2, hdr[3]-16*s, pr[2]-pr[0]-4, 16*s))
            path.setFillRule(Qt.WindingFill)
            self._fill(p, path, it["color"])
            p.setFont(self.font(15*s, True)); p.setPen(QColor("#FFFFFF")); p.setBrush(Qt.NoBrush)
            p.drawText(QRectF(pr[0]+16, pr[1], (pr[2]-pr[0])-280*s, hdr[3]-pr[1]), Qt.AlignLeft|Qt.AlignVCenter,
                       self.trunc(it["title"], pr[2]-pr[0]-280*s, 15*s, True))
            w = pr[2]
            hb = [("edit", w-214*s, w-134*s, "Изм."), ("del", w-128*s, w-56*s, "Удал."), ("close", w-50*s, w-10*s, "X")]
            for bid, x1, x2, label in hb:
                if bid == "edit": cmd = lambda: self._rename_block(it, True)
                elif bid == "del": cmd = lambda: self._del_block(it)
                else: cmd = lambda: self._close_block()
                self._btn(p, self._imm_btns, bid, x1, pr[1]+9*s, x2-x1, 30*s, label, cmd,
                          fill=it["color"], outline="#FFFFFF", fg="#FFFFFF", bold=True, ow=2)
        self._outline(p, self._rpath(pr[0], pr[1], pr[2]-pr[0], pr[3]-pr[1], 20), it["color"], 4)

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self.brush_color), self)
        if c.isValid(): self.brush_color = c.name(); self.update()

    def _pick_imm_color(self):
        c = QColorDialog.getColor(QColor(self.imm_color), self)
        if c.isValid(): self.imm_color = c.name(); self.update()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Интерактивная доска")
        self.resize(1280, 820)
        self.setCentralWidget(Board())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
