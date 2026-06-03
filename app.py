#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Downloader Pro — חלון אפליקציה native )pywebview + WebView2(.
לא פותח דפדפן חיצוני: WebView2 מובנה ב-Windows 11. חלון אמיתי עם כותרת ואייקון.
מנוע ההורדה )Config, Downloader, כל האפשרויות, ביטול/השהיה, DRM, auto-detect(
מיובא מ-youtube_downloader.py — כאן רק שכבת ה-UI native וה-API ל-frontend.
"""

import sys
import os
import json
import time
import threading
import subprocess

# חלון native )console=False( → sys.stdout/stderr הם None ב-exe; כל print
# )כולל --pot-mode והלוגים( היה מפיל את התהליך מיד. ממירים ל-devnull.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")


def _pip(pkg: str) -> bool:
    try:
        r = subprocess.run([sys.executable, "-m", "pip", "install", pkg, "-q",
                            "--disable-pip-version-check"],
                           capture_output=True, timeout=300)
        return r.returncode == 0
    except Exception:
        return False


# בהרצת exe )frozen( כל החבילות מוטמעות — אסור להריץ את לולאת ההתקנה: אם
# __import__ ייכשל, _pip ירוץ כ-`exe -m pip` )ה-exe עצמו ללא --pot-mode( →
# ייפתח UI נוסף ויתקע. מתקינים רק בהרצת מקור.
if not getattr(sys, "frozen", False):
    for _imp, _pkg in [("webview", "pywebview"), ("yt_dlp", "yt-dlp"),
                       ("yt_dlp_ejs", "yt-dlp-ejs"), ("PIL", "Pillow")]:
        try:
            __import__(_imp)
        except ImportError:
            print(f"[YT-Pro] מתקין {_pkg} ...")
            _pip(_pkg)

# ── מצב PO Token: ה-engine מריץ את ה-exe/סקריפט הזה כ-subprocess כדי לייצר
# PO token דרך WebView2 )דורש main-thread משלו(. חייב לרוץ לפני יצירת ה-UI.
if "--pot-mode" in sys.argv:
    _of = None
    for _a in sys.argv:
        if _a.startswith("--out="):
            _of = _a[6:]
    if _of:
        try:
            with open(_of + ".log", "w", encoding="utf-8") as _f:
                _f.write("[app] --pot-mode entered, frozen=%s\n"
                         % getattr(sys, "frozen", False))
        except Exception:
            pass
    import pot_provider
    if _of:
        pot_provider._OUT_FILE = _of
        pot_provider._LOG_FILE = _of + ".log"   # דיבוג frozen ללא console
    pot_provider.VERBOSE = False
    _r = pot_provider.mint()
    try:
        print(json.dumps(_r))
    except Exception:
        pass
    sys.exit(0)

import webview   # pywebview — חלון native דרך WebView2 )ללא דפדפן חיצוני(

# מנוע ההורדה והקבועים — מיובאים מהגרסה הקיימת )ללא ה-GUI של CTk(
from youtube_downloader import (
    Config, Downloader, DLItem, detect_mode, find_ffmpeg,
    VIDEO_QUALITIES, AUDIO_FORMATS, AUDIO_BITRATES, SUBTITLES,
    REENCODE_CHOICES, MODE_CHOICES, BROWSERS, APP_NAME, APP_VER,
)
import yt_dlp

cfg = Config()
dl  = Downloader(cfg)
_items: dict = {}
_last_push: dict = {}
_window = None   # נקבע אחרי create_window; ערוץ ה-push מ-thread ההורדה


def _resource(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def _item_dict(it: DLItem) -> dict:
    return {
        "id": id(it), "status": it.status, "progress": round(it.progress, 1),
        "speed": it.speed, "eta": it.eta, "dl_bytes": it.dl_bytes,
        "total_bytes": it.total_bytes, "filename": it.filename or it.url,
        "error": it.error, "note": it.note,
    }


def _push(it: DLItem, force: bool = False):
    """רץ על thread הדמון של yt-dlp. evaluate_js thread-safe ב-pywebview."""
    iid, now = id(it), time.monotonic()
    if not force and it.status == "downloading":
        if now - _last_push.get(iid, 0) < 0.12:
            return
    _last_push[iid] = now
    if _window is None:
        return
    try:
        _window.evaluate_js(f"window.on_progress({json.dumps(_item_dict(it))})")
    except Exception:
        pass   # החלון נסגר / ה-JS עוד לא מוכן


class Api:
    """ה-JS קורא לאלה: await window.pywebview.api.<method>(...)."""

    def get_init(self):
        return {
            "app_name": APP_NAME, "app_ver": APP_VER,
            "yt_dlp_ver": yt_dlp.version.__version__, "ffmpeg": bool(find_ffmpeg()),
            "config": dict(cfg._d), "video_qualities": VIDEO_QUALITIES,
            "audio_formats": AUDIO_FORMATS, "audio_bitrates": AUDIO_BITRATES,
            "subtitles": SUBTITLES, "reencode": REENCODE_CHOICES,
            "modes": MODE_CHOICES, "browsers": BROWSERS,
        }

    def save_setting(self, key, value):
        cfg[key] = value
        return True

    def detect_url_mode(self, url):
        return detect_mode(url or "")

    def fetch_info(self, url):
        ok, info = Downloader.fetch_info(url)
        if not ok:
            return {"ok": False, "error": info.get("error", "")}
        if info.get("entries"):
            try:
                cnt = len(list(info["entries"]))
            except Exception:
                cnt = "?"
            return {"ok": True, "title": info.get("title", ""), "count": cnt, "playlist": True}
        return {"ok": True, "title": info.get("title", ""),
                "duration": info.get("duration", 0) or 0, "playlist": False}

    def start_download(self, url, opts):
        if opts.get("mode", "auto") == "auto":
            opts["mode"] = detect_mode(url)
        if not opts.get("path"):
            opts["path"] = cfg["download_path"]
        it = DLItem(url, opts)
        _items[id(it)] = it
        dl.start(it,
                 on_progress=lambda i: _push(i),
                 on_done=lambda i: _push(i, force=True),
                 on_error=lambda i: _push(i, force=True))
        return _item_dict(it)

    def pause_download(self, iid):
        it = _items.get(iid)
        if not it or it.status in ("done", "error", "cancelled"):
            return False
        if it.pause_event.is_set():
            it.pause_event.clear()
        else:
            it.pause_event.set()
        return it.pause_event.is_set()

    def cancel_download(self, iid):
        it = _items.get(iid)
        if not it:
            return False
        it.cancel_event.set()
        it.pause_event.clear()
        return True

    def pick_folder(self, current=""):
        r = _window.create_file_dialog(webview.FOLDER_DIALOG,
                                       directory=current or os.path.expanduser("~"))
        return (r[0] if r else "")

    def pick_cookies(self):
        r = _window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("Cookies (*.txt)", "All files (*.*)"))
        return (r[0] if r else "")

    def update_ytdlp(self):
        r = subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                           capture_output=True, text=True)
        return {"ok": r.returncode == 0, "msg": (r.stderr or r.stdout)[-300:]}

    # ── עדכון עצמי של האפליקציה )לפי SHA-256, דרך GitHub( ──
    def check_app_update(self):
        import updater
        return updater.check_update()

    def do_app_update(self, url, sha):
        import updater
        def prog(phase, pct):
            try:
                _window.evaluate_js(
                    "window.on_update_progress&&window.on_update_progress(%s,%s)"
                    % (json.dumps(phase), round(float(pct), 1)))
            except Exception:
                pass
        ok, msg = updater.download_and_apply(url, sha, progress_cb=prog)
        if ok:
            # יוצאים כדי לשחרר את ה-exe; ה-VBScript מחליף ומפעיל מחדש
            def _quit():
                time.sleep(0.5)
                try:
                    _window.destroy()
                except Exception:
                    pass
                os._exit(0)
            threading.Thread(target=_quit, daemon=True).start()
        return {"ok": ok, "msg": msg}

    def open_folder(self, path):
        try:
            os.startfile(path if os.path.isdir(path) else os.path.dirname(path))
            return True
        except Exception:
            return False


def main():
    global _window
    icon = _resource(os.path.join("assets", "icon.ico"))
    _window = webview.create_window(
        f"{APP_NAME} {APP_VER}",
        _resource(os.path.join("web", "index.html")),
        js_api=Api(), width=1080, height=760, min_size=(900, 640),
        background_color="#02030a",
    )
    kw = {}
    if os.path.exists(icon):
        kw["icon"] = icon
    try:
        webview.start(**kw)
    except TypeError:
        # גרסאות pywebview ישנות שלא תומכות ב-icon=
        webview.start()


if __name__ == "__main__":
    main()
