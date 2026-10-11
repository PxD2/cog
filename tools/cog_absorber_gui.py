#!/usr/bin/env python3
"""COG Absorber — the window. Library of Congress -> COG numbered meanings -> GitHub (PxD2/cog), only when you press the button.

The Library of Congress is a taxpayer trust: held in trust for the people who paid for it, not a government organization or entity.

    pythonw cog_absorber_gui.py        (or double-click "COG Absorber.bat")

No timers. Nothing runs at night. On first open it cancels the old timed runs on base1
(PXD2 Studio Autopilot at 11 PM, the Digital Alexandria nightly task and its start-with-Windows entry);
the Schedules box shows what is left and has "Run now" buttons for when you want them.
"""
from __future__ import annotations

import json, os, re, subprocess, sys, threading, webbrowser
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                             QInputDialog, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
                             QProgressBar, QPushButton, QSpinBox, QSplitter, QVBoxLayout, QWidget)

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cog_absorber as A        # noqa: E402

SETTINGS = HERE / "cog_absorber_gui.json"
LOG = HERE / "cog_absorber_log.txt"
SITE = "https://pxd2.github.io/cog/"
WIN = sys.platform.startswith("win")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
STUDIO = Path.home() / "PxD2" / "pxd2-studio"
STARTUP_VBS = Path(os.environ.get("APPDATA", str(Path.home()))) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "Digital Alexandria.vbs"

PRESETS = [
    # (kind, value, label, section)
    ("collection", "century-of-lawmaking", "A Century of Lawmaking for a New Nation", "law"),
    ("collection", "united-states-reports", "United States Reports (Supreme Court)", "law"),
    ("query", "Samuel Rutherford", "Samuel Rutherford (Lex Rex)", "reformers"),
    ("query", "John Knox", "John Knox", "reformers"),
    ("query", "John Witherspoon", "John Witherspoon", "reformers"),
    ("query", "John Calvin", "John Calvin", "reformers"),
    ("query", "Martin Luther", "Martin Luther", "reformers"),
    ("query", "Theodore Beza", "Theodore Beza", "reformers"),
    ("query", "George Buchanan", "George Buchanan (De Jure Regni)", "reformers"),
]
# Library sections: how documents are grouped and where each group is stored ("core" = a folder in PxD2/cog,
# or "owner/repo" = its own repository). Meaning-ids are global either way.
SECTIONS = {"law": {"title": "Law", "store": "core"}, "reformers": {"title": "The Reformers", "store": "core"},
            "general": {"title": "General", "store": "core"}}
# The timed runs this window replaces. (kind, name, label)
TIMED = [
    ("task", "PXD2 Studio Autopilot", "PXD2 Studio Autopilot — every night 11 PM"),
    ("task", "Digital Alexandria", "Digital Alexandria nightly pull"),
    ("startup", str(STARTUP_VBS), "Digital Alexandria — starts with Windows"),
]

STYLE = """
* { font-family: 'Segoe UI', system-ui, sans-serif; font-size: 10pt; color: #e6e8ec; }
QMainWindow, QWidget#root { background: #0c0e12; }
QGroupBox { background: #161a22; border: 1px solid #252a33; border-radius: 8px; margin-top: 14px; padding: 10px 8px 8px 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #8b929a; font-size: 8pt; letter-spacing: 1px; }
QLineEdit, QSpinBox, QComboBox, QListWidget, QPlainTextEdit { background: #0f1218; border: 1px solid #252a33; border-radius: 5px; padding: 4px; selection-background-color: #2b4a7a; }
QListWidget::item { padding: 3px; }
QListWidget::indicator { width: 14px; height: 14px; border: 1px solid #4a5260; border-radius: 3px; background: #0c0e12; }
QListWidget::indicator:checked { background: #6ea8fe; border-color: #6ea8fe; }
QPushButton { background: #1e232c; border: 1px solid #2c323d; border-radius: 6px; padding: 6px 12px; }
QPushButton:hover { border-color: #6ea8fe; color: #6ea8fe; }
QPushButton:disabled { color: #555c66; border-color: #20252d; }
QPushButton#go { background: #c9a227; color: #0c0e12; font-weight: 700; font-size: 12pt; padding: 12px; border: none; }
QPushButton#go:hover { background: #e0b93a; color: #0c0e12; }
QPushButton#go:disabled { background: #3a3424; color: #6f6650; }
QPushButton#stop { color: #ff8a80; }
QProgressBar { background: #0f1218; border: 1px solid #252a33; border-radius: 5px; text-align: center; height: 16px; }
QProgressBar::chunk { background: #6ea8fe; border-radius: 4px; }
QLabel#big { font-size: 17pt; font-weight: 600; color: #7dcea0; font-family: Consolas, ui-monospace, monospace; }
QLabel#cap { color: #8b929a; font-size: 8pt; }
QLabel#title { font-size: 14pt; font-weight: 600; }
QLabel#sub { color: #8b929a; font-size: 9pt; }
QCheckBox::indicator { width: 15px; height: 15px; }
"""


# ------------------------------------------------------------------------------------------- settings
def load_settings() -> dict:
    s = {"sources": [dict(kind=k, value=v, label=l, section=c, on=(i < 2)) for i, (k, v, l, c) in enumerate(PRESETS)],
         "sections": json.loads(json.dumps(SECTIONS)),
         "items": 25, "pages": 20, "books": True, "rights": True, "dry": False, "repo": A.REPO, "branch": A.BRANCH,
         "timed_cancelled": False}
    try:
        s.update(json.loads(SETTINGS.read_text(encoding="utf-8")))
    except Exception:
        pass
    for src in s["sources"]:                       # older settings: put each source in a section
        if "section" not in src:
            lab = src.get("label", "")
            src["section"] = "law" if lab.startswith("Law") else "reformers" if lab.startswith("Reformers") else "general"
            src["label"] = lab.split(" · ", 1)[-1]
    for k, v in SECTIONS.items():
        s["sections"].setdefault(k, v)
    return s


def save_settings(s: dict) -> None:
    try:
        SETTINGS.write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


# ------------------------------------------------------------------------------------------- Windows timed runs
def timed_state() -> list[tuple[str, str, str, bool]]:
    out = []
    for kind, name, label in TIMED:
        if kind == "task":
            on = False
            if WIN:
                r = subprocess.run(["schtasks", "/Query", "/TN", name], capture_output=True, text=True, creationflags=NOWIN)
                on = r.returncode == 0
        else:
            on = Path(name).exists()
        out.append((kind, name, label, on))
    return out


def cancel_timed() -> list[str]:
    msgs = []
    for kind, name, label, on in timed_state():
        if not on:
            continue
        if kind == "task":
            r = subprocess.run(["schtasks", "/Delete", "/TN", name, "/F"], capture_output=True, text=True, creationflags=NOWIN)
            msgs.append(f"Cancelled: {label}" if r.returncode == 0 else f"Could not cancel {label}: {(r.stderr or r.stdout).strip()}")
        else:
            try:
                Path(name).unlink()
                msgs.append(f"Cancelled: {label}")
            except Exception as e:
                msgs.append(f"Could not remove {label}: {e}")
    return msgs


def run_detached(bat: Path) -> bool:
    if not bat.exists():
        return False
    if WIN:
        subprocess.Popen(["cmd", "/c", "start", "", str(bat)], cwd=str(bat.parent), creationflags=NOWIN)
    else:
        subprocess.Popen(["bash", str(bat)], cwd=str(bat.parent))
    return True


# ------------------------------------------------------------------------------------------- worker
class Worker(QObject):
    log = pyqtSignal(str)
    progress = pyqtSignal(int, int, str)
    done = pyqtSignal(dict)

    def __init__(self, sources, items, pages, rights, dry, repo, branch):
        super().__init__()
        self.args = (sources, items, pages, rights, dry, repo, branch)
        self.stop = threading.Event()

    def run(self):
        sources, items, pages, rights, dry, repo, branch = self.args
        try:
            if dry:
                gh = A.GitHubStore(repo, branch)
                gh.refresh()
                store = A.MemStore({p: gh.get(p) for p in gh.tree if p.startswith(("loc/", "books/catalog", "books/loc-", "sections/"))})

                def store_for(r):                    # dry run: section repos are read, never written
                    g = A.GitHubStore(r, branch)
                    try:
                        g.refresh()
                        return A.MemStore({p: g.get(p) for p in g.tree if p.startswith("sections/")})
                    except Exception:
                        return A.MemStore()
                self.log.emit("Dry run: numbering in memory, nothing will be pushed.")
            else:
                store_for = None
                store = A.GitHubStore(repo, branch)
                if not store.token:
                    self.done.emit({"error": "No GitHub sign-in found. Run `gh auth login` once (or push once with Git), then press again."})
                    return
            ab = A.Absorber(store, log=self.log.emit, progress=lambda d, t, l: self.progress.emit(d, t, l),
                            stop=self.stop, rights_gate=rights, store_for=store_for)
            r = ab.run(sources, items, pages)
            if dry:
                for p, b in sorted(store.files.items()):
                    if p.startswith(("loc/", "books/", "sections/")):
                        self.log.emit(f"  would push {p}  ({len(b):,} bytes)")
            self.done.emit(r)
        except Exception as e:      # noqa: BLE001
            self.done.emit({"error": f"{type(e).__name__}: {e}"})


class StatusWorker(QObject):
    done = pyqtSignal(dict, str)

    def __init__(self, repo, branch):
        super().__init__()
        self.repo, self.branch = repo, branch

    def run(self):
        try:
            store = A.GitHubStore(self.repo, self.branch)
            who = store.whoami()
            self.done.emit(A.status(store), who)
        except Exception as e:      # noqa: BLE001
            self.done.emit({"error": str(e)}, "")


# ------------------------------------------------------------------------------------------- window
class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.s = load_settings()
        self.setWindowTitle("COG Absorber — the People's Trust")
        self.resize(1180, 840)
        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(14, 12, 14, 12)

        # header
        head = QHBoxLayout()
        tl = QVBoxLayout()
        tl.addWidget(QLabel("COG Absorber", objectName="title"))
        tl.addWidget(QLabel("Library of Congress  →  (meaning-id, variant-index)  →  GitHub " + self.s["repo"] +
                            "  ·  runs only when you press the button", objectName="sub"))
        head.addLayout(tl, 1)
        self.who = QLabel("GitHub: checking…", objectName="sub")
        head.addWidget(self.who, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        outer.addLayout(head)

        split = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(split, 1)

        # ---- left column: what to absorb
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 6, 0)
        g = QGroupBox("WHAT TO ABSORB")
        gv = QVBoxLayout(g)
        self.list = QListWidget()
        self.list.setMinimumHeight(170)
        for src in self.s["sources"]:
            self._add_item(src)
        gv.addWidget(self.list, 1)
        addrow = QHBoxLayout()
        self.kind = QComboBox()
        self.kind.addItems(["Search words", "Collection"])
        self.new = QLineEdit(placeholderText="search words, a collection slug, or a loc.gov collection link")
        self.new.returnPressed.connect(self.add_source)
        b = QPushButton("Add")
        b.clicked.connect(self.add_source)
        self.secpick = QComboBox()
        self._fill_secpick()
        addrow.addWidget(self.kind)
        addrow.addWidget(self.new, 1)
        gv.addLayout(addrow)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("into section"))
        row2.addWidget(self.secpick, 1)
        row2.addWidget(b)
        rm = QPushButton("Remove selected")
        rm.clicked.connect(self.remove_source)
        row2.addWidget(rm)
        gv.addLayout(row2)
        lv.addWidget(g, 1)

        sg = QGroupBox("LIBRARY SECTIONS — groups, each with its own storage")
        sgv = QVBoxLayout(sg)
        self.seclist = QListWidget()
        self.seclist.setMaximumHeight(92)
        sgv.addWidget(self.seclist)
        sb2 = QHBoxLayout()
        nb = QPushButton("New section…")
        nb.clicked.connect(self.new_section)
        mvb = QPushButton("Move selected source to section…")
        mvb.clicked.connect(self.move_source)
        sb2.addWidget(nb)
        sb2.addWidget(mvb)
        sb2.addStretch(1)
        sgv.addLayout(sb2)
        lv.addWidget(sg)
        self._fill_seclist({})

        opt = QGroupBox("THIS RUN")
        og = QGridLayout(opt)
        self.items = QSpinBox(minimum=1, maximum=100000, value=int(self.s["items"]))
        self.pages = QSpinBox(minimum=1, maximum=10000, value=int(self.s["pages"]))
        og.addWidget(QLabel("Documents this run"), 0, 0)
        og.addWidget(self.items, 0, 1)
        og.addWidget(QLabel("Catalogue pages max"), 1, 0)
        og.addWidget(self.pages, 1, 1)
        self.books = QCheckBox("Searches: books / printed text only", checked=bool(self.s["books"]))
        self.rights = QCheckBox("Rights gate: only pre-1930 or open-rights items (the repo is public)", checked=bool(self.s["rights"]))
        self.dry = QCheckBox("Dry run — number it and show it, push nothing", checked=bool(self.s["dry"]))
        og.addWidget(self.books, 2, 0, 1, 2)
        og.addWidget(self.rights, 3, 0, 1, 2)
        og.addWidget(self.dry, 4, 0, 1, 2)
        lv.addWidget(opt)

        self.go = QPushButton("ABSORB NOW  →  GitHub", objectName="go")
        self.go.clicked.connect(self.start)
        self.stopb = QPushButton("STOP (keeps everything done so far)", objectName="stop", enabled=False)
        self.stopb.clicked.connect(self.halt)
        lv.addWidget(self.go)
        lv.addWidget(self.stopb)
        split.addWidget(left)

        # ---- right column: library + log + schedules
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(6, 0, 0, 0)
        lib = QGroupBox("THE LIBRARY ON GITHUB")
        lg = QGridLayout(lib)
        self.stat = {}
        for i, (k, cap) in enumerate([("next", "next free meaning-id"), ("meanings", "meanings"), ("variants", "exact sentences"),
                                      ("docs", "documents"), ("sentences", "sentences read")]):
            v = QLabel("—", objectName="big")
            c = QLabel(cap, objectName="cap")
            lg.addWidget(v, 0, i)
            lg.addWidget(c, 1, i)
            self.stat[k] = v
        self.srcinfo = QLabel("", objectName="sub")
        self.srcinfo.setWordWrap(True)
        lg.addWidget(self.srcinfo, 2, 0, 1, 5)
        btns = QHBoxLayout()
        for text, fn in [("Refresh", self.refresh), ("Open the library site", lambda: webbrowser.open(SITE)),
                         ("Open repo on GitHub", lambda: webbrowser.open(f"https://github.com/{self.s['repo']}")),
                         ("Open log file", self.open_log)]:
            bb = QPushButton(text)
            bb.clicked.connect(fn)
            btns.addWidget(bb)
        btns.addStretch(1)
        lg.addLayout(btns, 3, 0, 1, 5)
        rv.addWidget(lib)

        self.bar = QProgressBar()
        self.bar.setFormat("ready")
        self.bar.setValue(0)
        rv.addWidget(self.bar)
        self.out = QPlainTextEdit(readOnly=True)
        self.out.setFont(QFont("Consolas", 9))
        self.out.setMaximumBlockCount(5000)
        rv.addWidget(self.out, 1)

        sch = QGroupBox("SCHEDULES — everything runs only when you ask")
        sv = QVBoxLayout(sch)
        self.timed = QLabel("", objectName="sub")
        self.timed.setWordWrap(True)
        sv.addWidget(self.timed)
        sb = QHBoxLayout()
        c = QPushButton("Cancel all timed runs")
        c.clicked.connect(self.cancel_all)
        p = QPushButton("Run Studio Autopilot now")
        p.clicked.connect(lambda: self._run_bat(STUDIO / "PXD2 Work Now.bat", "Studio Autopilot"))
        n = QPushButton("Run old Alexandria pipeline now")
        n.clicked.connect(lambda: self._run_bat(HERE / "Alexandria Nightly.bat", "Alexandria pipeline"))
        for w in (c, p, n):
            sb.addWidget(w)
        sb.addStretch(1)
        sv.addLayout(sb)
        rv.addWidget(sch)
        split.addWidget(right)
        split.setSizes([430, 750])

        self.thread = None
        self.worker = None
        self.say(A.TRUST)
        if not self.s.get("timed_cancelled"):
            msgs = cancel_timed()
            for m in msgs:
                self.say(m)
            if WIN:
                self.s["timed_cancelled"] = True
                save_settings(self.s)
        self.show_timed()
        self.refresh()

    # sources
    def _add_item(self, src: dict):
        sec = self.s["sections"].get(src.get("section", "general"), {"title": src.get("section", "general")})
        it = QListWidgetItem(f"[{sec['title']}]  {src.get('label') or src['value']}")
        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        it.setCheckState(Qt.CheckState.Checked if src.get("on") else Qt.CheckState.Unchecked)
        it.setData(Qt.ItemDataRole.UserRole, src)
        it.setToolTip(("loc.gov collection: " if src["kind"] == "collection" else "loc.gov search: ") + src["value"])
        self.list.addItem(it)

    def add_source(self):
        t = self.new.text().strip()
        if not t:
            return
        m = re.search(r"loc\.gov/collections/([^/?#]+)", t)
        if m or self.kind.currentIndex() == 1:
            slug = m.group(1) if m else re.sub(r"\s+", "-", t.lower())
            src = dict(kind="collection", value=slug, label="Collection · " + slug, on=True)
        else:
            src = dict(kind="query", value=t, label="Search · " + t, on=True)
        src["section"] = self.secpick.currentData() or "general"
        self._add_item(src)
        self.new.clear()
        self._save()

    def remove_source(self):
        for it in self.list.selectedItems():
            self.list.takeItem(self.list.row(it))
        self._save()

    def _sources(self) -> list[dict]:
        out = []
        for i in range(self.list.count()):
            it = self.list.item(i)
            d = dict(it.data(Qt.ItemDataRole.UserRole))
            d["on"] = it.checkState() == Qt.CheckState.Checked
            out.append(d)
        return out

    def _save(self):
        self.s.update(sources=self._sources(), items=self.items.value(), pages=self.pages.value(), books=self.books.isChecked(),
                      rights=self.rights.isChecked(), dry=self.dry.isChecked())
        save_settings(self.s)

    # sections
    def _fill_secpick(self):
        self.secpick.clear()
        for k, v in self.s["sections"].items():
            self.secpick.addItem(v["title"], k)

    def _fill_seclist(self, live: dict):
        self.seclist.clear()
        for k, v in self.s["sections"].items():
            st = live.get(k, {})
            where = "core (PxD2/cog)" if v["store"] == "core" else v["store"]
            store = st.get("store", v["store"])
            if store != v["store"]:
                where = (("core (PxD2/cog)" if store == "core" else store) + "  — already holds documents, stays there")
            self.seclist.addItem(f"{v['title']}   ·   {st.get('docs', 0):,} documents   ·   stored in {where}")

    def new_section(self):
        title, ok = QInputDialog.getText(self, "New section", "Section name (e.g. Founders' Papers, Newspapers — Arizona):")
        if not ok or not title.strip():
            return
        store, ok = QInputDialog.getText(self, "Where is it stored?",
                                         "Leave as core to keep it in PxD2/cog (sections/<name>/),\n"
                                         "or give its own repository as owner/repo (create the repo on GitHub first).\n"
                                         "Note: the public library site can only read public repositories.", text="core")
        if not ok:
            return
        store = store.strip() or "core"
        if store != "core" and not re.fullmatch(r"[\w.-]+/[\w.-]+", store):
            QMessageBox.warning(self, "COG Absorber", "Storage must be core or owner/repo.")
            return
        sid = re.sub(r"[^a-z0-9-]+", "-", title.lower()).strip("-")
        self.s["sections"][sid] = {"title": title.strip(), "store": store}
        self._fill_secpick()
        self.secpick.setCurrentIndex(self.secpick.findData(sid))
        self._save()
        self._fill_seclist(getattr(self, "_live_sections", {}))
        self.say(f"Section added: {title.strip()} → {store}. Add sources into it, then press ABSORB NOW.")

    def move_source(self):
        items = self.list.selectedItems()
        if not items:
            return
        names = [v["title"] for v in self.s["sections"].values()]
        name, ok = QInputDialog.getItem(self, "Move to section", "Section:", names, 0, False)
        if not ok:
            return
        sid = [k for k, v in self.s["sections"].items() if v["title"] == name][0]
        for it in items:
            d = dict(it.data(Qt.ItemDataRole.UserRole))
            d["section"] = sid
            row = self.list.row(it)
            self.list.takeItem(row)
            self._add_item(d)
            self.list.insertItem(row, self.list.takeItem(self.list.count() - 1))
        self._save()
        self.say("Only new documents go to the new section; ones already absorbed stay where they are.")

    # log
    def say(self, line: str):
        self.out.appendPlainText(line)
        self.out.moveCursor(QTextCursor.MoveOperation.End)
        try:
            with LOG.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def open_log(self):
        if LOG.exists():
            (os.startfile(str(LOG)) if WIN else webbrowser.open(LOG.as_uri()))   # type: ignore[attr-defined]

    # run
    def start(self):
        self._save()
        on = [x for x in self._sources() if x["on"]]
        if not on:
            QMessageBox.information(self, "COG Absorber", "Tick at least one source.")
            return
        tag = A.L.BOOKS_TAG if self.books.isChecked() else ""
        sources = []
        for x in on:
            sec = self.s["sections"].get(x.get("section", "general"), {"title": "General", "store": "core"})
            sources.append({"src": ("q:" + x["value"] + tag) if x["kind"] == "query" else x["value"],
                            "section": x.get("section", "general"), "title": sec["title"], "store": sec["store"]})
        self.go.setEnabled(False)
        self.stopb.setEnabled(True)
        self.bar.setRange(0, self.items.value())
        self.bar.setValue(0)
        self.bar.setFormat("starting…")
        self.say("")
        self.say(f"=== Absorb: {', '.join(x['label'] for x in on)} · {self.items.value()} documents"
                 + (" · DRY RUN" if self.dry.isChecked() else ""))
        self.thread = QThread()
        self.worker = Worker(sources, self.items.value(), self.pages.value(), self.rights.isChecked(), self.dry.isChecked(),
                             self.s["repo"], self.s["branch"])
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self.say)
        self.worker.progress.connect(lambda d, t, l: (self.bar.setValue(d), self.bar.setFormat(f"{d}/{t}  ·  {l[:60]}")))
        self.worker.done.connect(self.finished)
        self.worker.done.connect(self.thread.quit)
        self.thread.start()

    def halt(self):
        if self.worker:
            self.worker.stop.set()
            self.stopb.setEnabled(False)
            self.say("Stopping after the current document — everything so far gets pushed…")

    def finished(self, r: dict):
        self.go.setEnabled(True)
        self.stopb.setEnabled(False)
        if r.get("error"):
            self.say("ERROR: " + r["error"])
            self.bar.setFormat("error — see log")
            return
        self.bar.setFormat(f"done · +{r.get('docs', 0)} documents · +{r.get('meanings', 0):,} meanings"
                           + (" (dry run)" if self.dry.isChecked() else ""))
        if r.get("commit") and not self.dry.isChecked():
            self.say(f"Commit: https://github.com/{self.s['repo']}/commit/{r['commit']}")
        if r.get("held_back"):
            self.say(f"{r['held_back']} item(s) held back by the rights gate (may still be under copyright).")
        if not self.dry.isChecked():
            self.refresh()

    # library status
    def refresh(self):
        self._st = QThread()
        self._sw = StatusWorker(self.s["repo"], self.s["branch"])
        self._sw.moveToThread(self._st)
        self._st.started.connect(self._sw.run)
        self._sw.done.connect(self.show_status)
        self._sw.done.connect(self._st.quit)
        self._st.start()

    def show_status(self, st: dict, who: str):
        self.who.setText(f"GitHub: signed in as {who}" if who else "GitHub: not signed in — run `gh auth login` once")
        if st.get("error"):
            self.srcinfo.setText("Could not read the library: " + st["error"])
            return
        t = st.get("totals", {})
        self.stat["next"].setText(str(st.get("next_meaning", A.FIRST_ABSORBED)))
        for k in ("meanings", "variants", "docs", "sentences"):
            self.stat[k].setText(f"{t.get(k, 0):,}")
        self._live_sections = st.get("sections") or {}
        self._fill_seclist(self._live_sections)
        rows = []
        for src, p in (st.get("sources") or {}).items():
            name = src[2:].replace(A.L.BOOKS_TAG, "") if src.startswith("q:") else src
            rows.append(f"{name}: {'complete' if p.get('done') else str(p.get('pages', 0)) + ' page(s) in'}")
        self.srcinfo.setText("Where each source left off — " + " · ".join(rows) if rows else
                             "Nothing absorbed yet. Absorbed meanings start at 1000.")

    # schedules
    def show_timed(self):
        rows = []
        for kind, name, label, on in timed_state():
            rows.append(("●  ON  " if on else "○  off  ") + label)
        if not WIN:
            rows.append("(Windows Task Scheduler is only checked on Windows.)")
        self.timed.setText("\n".join(rows))

    def cancel_all(self):
        msgs = cancel_timed() or ["No timed runs were on."]
        for m in msgs:
            self.say(m)
        self.show_timed()

    def _run_bat(self, bat: Path, label: str):
        if run_detached(bat):
            self.say(f"Started {label} now (its own window): {bat.name}")
        else:
            self.say(f"Not found: {bat}")

    def closeEvent(self, e):
        self._save()
        if self.worker and self.thread and self.thread.isRunning():
            self.worker.stop.set()
            self.thread.wait(30000)
        super().closeEvent(e)


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    w = Window()
    w.show()
    if "--shot" in sys.argv:                      # for testing: save a picture of the window and quit
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(4000, lambda: (w.grab().save(sys.argv[sys.argv.index("--shot") + 1]), app.quit()))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
