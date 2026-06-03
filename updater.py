# -*- coding: utf-8 -*-
"""
עדכון עצמי דרך GitHub — לפי מזהה חבילה )SHA-256( ולא לפי מספר גרסה.
מבוסס על המנגנון של "מנהל התרגומים", מפושט ל-GitHub בלבד:
  • manifest ב-raw.githubusercontent )update.json( עם sha256 + download_url
  • השוואת ה-sha256 של ה-exe הרץ מול ה-manifest — שונה = עדכון זמין
  • הורדה → אימות sha256 → החלפת ה-exe דרך VBScript trampoline )עוקף נעילת
    הקובץ בזמן ריצה(. ה-app יוצא, ה-VBS מחליף ומריץ מחדש.
"""
import os
import sys
import json
import time
import hashlib
import tempfile
import subprocess
import urllib.request
from pathlib import Path
from typing import Callable, Optional

# מאגר ה-עדכונים )ציבורי(. ניתן לעדכון אם משנים repo.
UPDATE_OWNER = "nehorayc04"
UPDATE_REPO  = "youtube-downloader-pro"
MANIFEST_URL = (f"https://raw.githubusercontent.com/"
                f"{UPDATE_OWNER}/{UPDATE_REPO}/main/update.json")


def _self_exe() -> Optional[str]:
    """נתיב ה-exe הרץ — רק כשמורצים כ-frozen )PyInstaller(."""
    return sys.executable if getattr(sys, "frozen", False) else None


def _sha256(path: str, cb: Optional[Callable] = None) -> str:
    h = hashlib.sha256()
    total = os.path.getsize(path) or 1
    done = 0
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1048576), b""):
            h.update(blk)
            done += len(blk)
            if cb:
                cb(done / total * 100)
    return h.hexdigest()


def check_update() -> dict:
    """בודק עדכון מול ה-manifest. לעולם לא זורק — שגיאות חוזרות כ-error רך."""
    info = {"available": False, "error": None, "notes": "", "url": None,
            "size": 0, "version": "", "current_sha": None, "latest_sha": None}
    exe = _self_exe()
    if not exe:
        info["error"] = "dev"     # לא frozen — אין מה לעדכן
        return info
    try:
        # cache-busting — raw.githubusercontent מוגש דרך CDN )עד ~5 דק' עיכוב(
        url = MANIFEST_URL + "?t=" + str(int(time.time()))
        req = urllib.request.Request(url, headers={
            "Cache-Control": "no-cache, no-store",
            "Pragma": "no-cache",
            "User-Agent": "ytpro-updater",
        })
        with urllib.request.urlopen(req, timeout=10) as r:
            m = json.loads(r.read().decode("utf-8"))
        cur = _sha256(exe).lower()
        latest = (m.get("sha256") or "").lower()
        info.update(current_sha=cur, latest_sha=latest,
                    notes=m.get("notes", ""), url=m.get("download_url"),
                    size=int(m.get("size_bytes") or 0),
                    version=m.get("version", ""))
        info["available"] = bool(latest and info["url"] and latest != cur)
    except Exception as e:
        info["error"] = str(e)
    return info


def download_and_apply(url: str, expected_sha: str,
                       progress_cb: Optional[Callable] = None) -> tuple:
    """מוריד את ה-exe החדש, מאמת sha256, ומחליף את הקובץ הרץ. ה-app חייב
    לצאת מיד אחרי קריאה מוצלחת )ה-VBS ממתין שה-exe ישוחרר(."""
    exe = _self_exe()
    if not exe:
        return False, "לא ניתן לעדכן בהרצת פיתוח"
    tmp = Path(tempfile.gettempdir()) / "ytpro_update_new.exe"
    try:
        if progress_cb:
            progress_cb("download", 0.0)
        with urllib.request.urlopen(url, timeout=60) as r:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            last = 0.0
            with open(tmp, "wb") as f:
                while True:
                    chunk = r.read(262144)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    now = time.time()
                    if progress_cb and now - last >= 0.2:
                        last = now
                        progress_cb("download", (done / total * 100) if total else 0.0)
        if expected_sha:
            if progress_cb:
                progress_cb("verify", 0.0)
            if _sha256(str(tmp)).lower() != expected_sha.lower():
                try:
                    tmp.unlink()
                except OSError:
                    pass
                return False, "אימות הקובץ נכשל — ההורדה פגומה. נסה שוב."
            if progress_cb:
                progress_cb("verify", 100.0)
        _apply_via_vbscript(exe, str(tmp))
        return True, "ok"
    except Exception as e:
        return False, str(e)


def _apply_via_vbscript(old_exe: str, new_exe: str):
    """כותב VBScript שממתין לסגירת ה-app, מחליף את ה-exe, ומריץ מחדש.
    VBScript הוא parent נפרד — עוקף נעילת קובץ ושומר על הרצה ללא חלון."""
    d = Path(tempfile.gettempdir()) / "ytpro-update"
    d.mkdir(parents=True, exist_ok=True)
    vbs = d / "apply.vbs"
    o = old_exe.replace('"', '""')
    n = new_exe.replace('"', '""')
    script = (
        "Option Explicit\r\n"
        "Dim fso, shell, i\r\n"
        "Set fso = CreateObject(\"Scripting.FileSystemObject\")\r\n"
        "Set shell = CreateObject(\"WScript.Shell\")\r\n"
        "WScript.Sleep 1500\r\n"
        "For i = 1 To 40\r\n"
        "  On Error Resume Next\r\n"
        f"  fso.DeleteFile \"{o}\", True\r\n"
        f"  If Not fso.FileExists(\"{o}\") Then Exit For\r\n"
        "  Err.Clear\r\n"
        "  WScript.Sleep 500\r\n"
        "Next\r\n"
        "On Error Resume Next\r\n"
        f"fso.MoveFile \"{n}\", \"{o}\"\r\n"
        f"shell.Run \"\"\"{o}\"\"\", 1, False\r\n"
    )
    vbs.write_bytes(script.encode("ascii", "replace"))
    DETACHED, NEWGROUP, NOWINDOW = 0x00000008, 0x00000200, 0x08000000
    subprocess.Popen(["wscript.exe", str(vbs)],
                     creationflags=DETACHED | NEWGROUP | NOWINDOW,
                     close_fds=True, cwd=str(d))
