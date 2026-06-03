#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Downloader Pro
גרסה 2.0 - מוריד YouTube מקצועי
"""

import sys
import os
import subprocess
import threading
import json
import re
import time
import queue
import shutil
from pathlib import Path
from typing import Optional, Callable, Dict

# ══════════════════════════════════════════════════════════════════
#  ניהול תלויות — התקנה אוטומטית
# ══════════════════════════════════════════════════════════════════

REQUIRED = [
    ("customtkinter", "customtkinter>=5.2.0"),
    ("yt_dlp", "yt-dlp"),
    ("yt_dlp_ejs", "yt-dlp-ejs"),   # פתרון n-challenge )עם node( — נדרש ל-1080p
    ("PIL", "Pillow"),
]

# אפקט זכוכית מטושטשת )Mica/Acrylic( — Windows בלבד
if sys.platform == "win32":
    REQUIRED.append(("pywinstyles", "pywinstyles"))

def _pip(pkg: str) -> bool:
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg, "-q",
             "--disable-pip-version-check"],
            capture_output=True, timeout=180
        )
        return r.returncode == 0
    except Exception:
        return False

def _ensure_deps():
    missing = []
    for imp, pkg in REQUIRED:
        try:
            __import__(imp)
        except ImportError:
            print(f"[YT-Pro] מתקין {pkg} ...")
            if not _pip(pkg):
                missing.append(pkg)
            else:
                print(f"[YT-Pro] ✓ {pkg} הותקן")
    if missing:
        print(f"[YT-Pro] שגיאה: לא ניתן להתקין: {', '.join(missing)}")
        print("הרץ ידנית: pip install " + " ".join(missing))
        sys.exit(1)

_ensure_deps()

# עכשיו בטוח לייבא
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import yt_dlp

# אפקט זכוכית מטושטשת — אופציונלי, נכשל בשקט אם לא זמין
try:
    import pywinstyles
    PYWINSTYLES_AVAILABLE = True
except Exception:
    PYWINSTYLES_AVAILABLE = False

# ══════════════════════════════════════════════════════════════════
#  קבועים
# ══════════════════════════════════════════════════════════════════

APP_NAME    = "YouTube Downloader Pro"
APP_VER     = "2.1"
CONFIG_DIR  = Path.home() / ".yt_downloader_pro"
CONFIG_FILE = CONFIG_DIR / "config.json"

def resource_path(rel: str) -> str:
    """נתיב למשאב מוטמע — עובד גם בהרצה רגילה וגם כ-exe של PyInstaller."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)

ICON_PATH = resource_path(os.path.join("assets", "icon.ico"))

def find_ffmpeg() -> Optional[str]:
    """ffmpeg מוטמע )assets( קודם, אחרת מה-PATH של המערכת."""
    bundled = resource_path(os.path.join("assets", "ffmpeg.exe"))
    if os.path.exists(bundled):
        return bundled
    return shutil.which("ffmpeg")

# ══════════════════════════════════════════════════════════════════
#  PO Token + JS runtime — מאפשרים 1080p לסרטונים "מוגבלים" )כמו YTDLnis(
# ══════════════════════════════════════════════════════════════════
# שלושה רכיבים נדרשים יחד )מתועד ב-CLAUDE.md(:
#   1. PO Token — נוצר ב-WebView2 דרך pot_provider )BotGuard, כמו YTDLnis(.
#   2. node + yt-dlp-ejs — פותרים את ה-n-challenge; בלעדיהם רק storyboards.
#   3. client=tv_embedded — URLs יציבים שלא נחסמים ע"י SABR )שלא כמו web/mweb(.

APP_DIR   = Path.home() / ".yt_downloader_pro"
POT_CACHE = APP_DIR / "pot_cache.json"
# clients שעובדים עם PO token )לפי סדר עדיפות(. web מודר — נחסם ע"י SABR.
POT_CLIENTS = ["tv_embedded", "web_embedded", "mweb"]


NODE_VERSION = "v22.11.0"   # LTS — ל-bootstrap אם node חסר במחשב

def find_node() -> Optional[str]:
    """מאתר node.exe )נדרש לפתרון n-challenge דרך yt-dlp-ejs(."""
    n = shutil.which("node")
    if n:
        return n
    cands = [str(APP_DIR / "node" / "node.exe"),            # bootstrap
             r"C:\Program Files\nodejs\node.exe",
             r"C:\Program Files (x86)\nodejs\node.exe",
             os.path.expandvars(r"%LOCALAPPDATA%\Programs\nodejs\node.exe"),
             resource_path(os.path.join("assets", "node", "node.exe"))]
    for p in cands:
        if p and os.path.exists(p):
            return p
    return None


def ensure_node(on_status: Optional[Callable] = None) -> Optional[str]:
    """מחזיר נתיב node; אם חסר — מוריד node portable )פעם אחת( ל-APP_DIR.
    כך ה-exe המופץ נשאר קטן וה-1080p עובד גם ללא node מותקן מראש."""
    p = find_node()
    if p:
        return p
    exe = APP_DIR / "node" / "node.exe"
    if exe.exists():
        return str(exe)
    try:
        if on_status:
            on_status("מתקין רכיב נדרש )Node.js — פעם אחת(...")
        import urllib.request, zipfile, io
        arch = "x64" if sys.maxsize > 2**32 else "x86"
        url = (f"https://nodejs.org/dist/{NODE_VERSION}/"
               f"node-{NODE_VERSION}-win-{arch}.zip")
        APP_DIR.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=180) as r:
            blob = r.read()
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            member = next((n for n in z.namelist()
                           if n.endswith("/node.exe")), None)
            if member:
                (APP_DIR / "node").mkdir(parents=True, exist_ok=True)
                with z.open(member) as src, open(exe, "wb") as out:
                    shutil.copyfileobj(src, out)
        return str(exe) if exe.exists() else None
    except Exception:
        return None


def get_po_token(force: bool = False, peek: bool = False) -> Optional[dict]:
    """{po_token, visitor_data} טרי עם cache. נוצר ב-subprocess )WebView2(.
    מחזיר None אם נכשל )אז נופלים ל-clients הישנים ללא token(.
    peek=True — בודק cache בלבד ולא מייצר )לבדיקה מהירה לפני המתנה ארוכה(."""
    if not force:
        try:
            d = json.loads(POT_CACHE.read_text(encoding="utf-8"))
            if d.get("po_token") and d.get("expiry", 0) > time.time() + 180:
                return {"po_token": d["po_token"], "visitor_data": d["visitor_data"]}
        except Exception:
            pass
    if peek:
        return None
    APP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = APP_DIR / "pot_tmp.json"
    try:
        tmp.unlink()
    except Exception:
        pass
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--pot-mode", f"--out={tmp}"]
    else:
        prov = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pot_provider.py")
        if not os.path.exists(prov):
            return None
        cmd = [sys.executable, prov, f"--out={tmp}", "-q"]
    try:
        subprocess.run(cmd, capture_output=True, timeout=120)
        d = json.loads(tmp.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not d.get("po_token"):
        return None
    d["expiry"] = time.time() + max(int(d.get("ttl", 0)) - 600, 1800)
    try:
        POT_CACHE.write_text(json.dumps(d), encoding="utf-8")
    except Exception:
        pass
    return {"po_token": d["po_token"], "visitor_data": d["visitor_data"]}


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % rgb

def make_gradient(w: int, h: int, stops, horizontal: bool = True):
    """תמונת gradient חלקה בין כמה צבעים )stops = list of (r,g,b)(."""
    from PIL import Image
    length = max((w if horizontal else h), 2)
    strip = Image.new("RGB", (length, 1))
    px = strip.load()
    segs = len(stops) - 1
    for i in range(length):
        t = i / (length - 1) * segs
        seg = min(int(t), segs - 1)
        f = t - seg
        a, b = stops[seg], stops[seg + 1]
        px[i, 0] = (int(a[0] + (b[0] - a[0]) * f),
                    int(a[1] + (b[1] - a[1]) * f),
                    int(a[2] + (b[2] - a[2]) * f))
    if not horizontal:
        strip = strip.rotate(-90, expand=True)
    return strip.resize((w, h))

# פלטת ניאון ל-gradient ראשי )צהוב → ורוד → סגול → כחול(
GRAD_NEON = [(255, 247, 0), (255, 86, 120), (150, 60, 255), (40, 130, 245)]
GRAD_GLASS = [(20, 20, 46), (16, 16, 36), (10, 10, 24)]   # זכוכית כהה לעומק

C = {
    # ── סגנון Game translator — קנבס navy/purple כהה + הדגשת ניאון צהובה ──
    "bg":        "#050510",   # קנבס עמוק )מאחורי הטשטוש(
    "sidebar":   "#0A0A19",   # זכוכית כהה
    "card":      "#101024",   # פאנל זכוכית
    "card2":     "#14142C",   # פאנל מוגבה
    "input":     "#1A1A32",
    "border":    "#2A2A48",
    "accent":    "#FFF700",   # ניאון צהוב — הדגשה ראשית
    "accent_h":  "#D8D200",   # hover כהה יותר
    "on_accent": "#0A0A19",   # טקסט כהה על רקע ניאון
    "blue":      "#3B6FF5",
    "blue_h":    "#2E58C4",
    "green":     "#00E08A",
    "orange":    "#FFB020",
    "error":     "#FF5577",
    "txt":       "#F0F0FF",
    "txt2":      "#9B9BC4",
    "txt3":      "#5C5C84",
    "progress":  "#FFF700",
}

# ── מצב הורדה: וידאו או שמע ─────────────────────────────────────
MODE_VIDEO = "video"
MODE_AUDIO = "audio"

# בורר מצב למשתמש )label, value( — ללא אימוג'ים; ה-frontend מוסיף אייקוני SVG
MODE_CHOICES = [
    ("אוטומטי", "auto"),
    ("וידאו",   MODE_VIDEO),
    ("שמע",     MODE_AUDIO),
]

# רזולוציות וידאו — הערך הוא תקרת גובה )"best" = ללא תקרה(.
# ללא סינון codec — format_sort ב-_build_opts בוחר את הזרם הגבוה ביותר
# (4K VP9 / 8K AV1 מנצחים 1080p H.264 בדירוג)
VIDEO_QUALITIES = [
    ("הטוב ביותר",   "best"),
    ("8K · 4320p",   "4320"),
    ("4K · 2160p",   "2160"),
    ("1440p QHD",    "1440"),
    ("1080p Full HD","1080"),
    ("720p HD",      "720"),
    ("480p",         "480"),
    ("360p",         "360"),
]

# פורמטי שמע )preferredcodec של FFmpegExtractAudio(
AUDIO_FORMATS = [
    ("MP3",  "mp3"),
    ("M4A",  "m4a"),
    ("Opus", "opus"),
    ("WAV",  "wav"),
    ("FLAC", "flac"),
]

# קצב סיביות לשמע )"0" = הטוב ביותר/מקור(
AUDIO_BITRATES = [
    ("הטוב ביותר", "0"),
    ("320 kbps",   "320"),
    ("256 kbps",   "256"),
    ("192 kbps",   "192"),
    ("128 kbps",   "128"),
]

# קידוד וידאו מחדש לפורמט קבוע )"" = ללא(
REENCODE_CHOICES = [
    ("ללא", ""),
    ("MP4", "mp4"),
    ("MKV", "mkv"),
]

SUBTITLES = [
    ("ללא כתוביות",           ""),
    ("כל השפות הזמינות",      "all"),
    ("עברית",                 "he"),
    ("English",               "en"),
    ("العربية",               "ar"),
    ("Español",               "es"),
    ("Français",              "fr"),
    ("Deutsch",               "de"),
    ("Русский",               "ru"),
    ("日本語",                "ja"),
    ("中文",                  "zh"),
    ("Português",             "pt"),
    ("Italiano",              "it"),
    ("한국어",                "ko"),
    ("Türkçe",                "tr"),
]

BROWSERS = ["chrome", "firefox", "edge", "chromium", "opera", "safari", "brave"]

# קטגוריות SponsorBlock לדילוג )חוסם ספונסרים(
SPONSORBLOCK_CATS = ["sponsor", "selfpromo", "interaction",
                     "intro", "outro", "preview", "music_offtopic"]

def detect_mode(url: str) -> str:
    """זיהוי אוטומטי: YouTube Music → שמע, כל השאר → וידאו."""
    u = (url or "").lower()
    if "music.youtube.com" in u:
        return MODE_AUDIO
    return MODE_VIDEO

# ══════════════════════════════════════════════════════════════════
#  הגדרות
# ══════════════════════════════════════════════════════════════════

class Config:
    _DEFAULTS = {
        "download_path":       str(Path.home() / "Downloads"),
        "use_cookies":         True,
        "browser":             "chrome",
        "cookies_file":        "",
        # ── ברירות מחדל להורדה ──
        "mode_auto":           True,         # זיהוי אוטומטי וידאו/שמע לפי הקישור
        "default_mode":        MODE_VIDEO,   # המצב כשהזיהוי האוטומטי כבוי
        "video_quality":       "best",
        "video_only":          False,        # וידאו ללא שמע
        "audio_format":        "mp3",
        "audio_bitrate":       "0",
        "default_subtitle":    0,
        # ── אפשרויות מתקדמות )התאמה אישית( ──
        "embed_thumbnail":     False,
        "embed_chapters":      False,
        "embed_subs":          False,
        "split_chapters":      False,
        "sponsorblock":        False,
        "reencode":            "",           # "" / "mp4" / "mkv"
        "live_from_start":     False,
        "filename_template":   "",           # "" = %(title)s
        "extra_args":          "",
        "trim_start":          "",
        "trim_end":            "",
    }

    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._d: dict = dict(self._DEFAULTS)
        self._load()

    def _load(self):
        if CONFIG_FILE.exists():
            try:
                self._d.update(json.loads(CONFIG_FILE.read_text("utf-8")))
            except Exception:
                pass
        self._sanitize_paths()

    def _sanitize_paths(self):
        """אוניברסלי בין מחשבים: נתיב שמירה ממחשב אחר שלא קיים — חזרה ל-Downloads.
        קובץ cookies שלא קיים — איפוס כדי שלא ייתקע על ניסיון יחיד."""
        dp = self._d.get("download_path", "")
        try:
            ok = bool(dp) and Path(dp).exists()
        except Exception:
            ok = False
        if not ok:
            self._d["download_path"] = str(Path.home() / "Downloads")
            self.save()
        ck = self._d.get("cookies_file", "")
        if ck and not Path(ck).exists():
            self._d["cookies_file"] = ""
            self.save()

    def save(self):
        CONFIG_FILE.write_text(json.dumps(self._d, indent=2, ensure_ascii=False), "utf-8")

    def __getitem__(self, k):   return self._d.get(k, self._DEFAULTS.get(k))
    def __setitem__(self, k, v):
        self._d[k] = v
        self.save()

# ══════════════════════════════════════════════════════════════════
#  פריט הורדה
# ══════════════════════════════════════════════════════════════════

class _Cancelled(Exception):
    """מורם מתוך ה-progress hook כשהמשתמש מבטל הורדה."""
    pass

class DLItem:
    def __init__(self, url: str, opts: dict):
        self.url             = url
        self.opts            = opts
        self.status          = "pending"   # pending/downloading/paused/merging/done/error/cancelled
        self.progress        = 0.0
        self.speed           = 0.0
        self.eta             = 0
        self.dl_bytes        = 0
        self.total_bytes     = 0
        self.filename        = ""
        self.error           = ""
        self.video_num       = 0
        self.video_total     = 0
        self.actual_height   = 0    # גובה הווידאו שירד בפועל )לאיתור DRM(
        self.note            = ""   # הערה/אזהרה למשתמש
        # שליטת הורדה — ביטול והשהיה
        self.cancel_event    = threading.Event()
        self.pause_event     = threading.Event()

# ══════════════════════════════════════════════════════════════════
#  מנוע הורדה
# ══════════════════════════════════════════════════════════════════

class Downloader:
    def __init__(self, cfg: Config):
        self.cfg    = cfg

    def start(self, item: DLItem,
              on_progress: Callable,
              on_done:     Callable,
              on_error:    Callable):
        t = threading.Thread(target=self._run,
                             args=(item, on_progress, on_done, on_error),
                             daemon=True)
        t.start()

    # סדר ניסיון דפדפנים לעוגיות — Windows מעדיף Edge כי פחות נועל
    _BROWSER_FALLBACKS = ["edge", "chrome", "firefox", "chromium", "opera", "brave"]

    @staticmethod
    def _parse_time(s: str) -> Optional[float]:
        """ממיר 'SS' / 'MM:SS' / 'HH:MM:SS' לשניות. ריק → None."""
        s = (s or "").strip()
        if not s:
            return None
        try:
            sec = 0.0
            for part in s.split(":"):
                sec = sec * 60 + float(part)
            return sec
        except ValueError:
            return None

    def _build_opts(self, item: DLItem, hook: Callable,
                    cookie_browser: Optional[str] = None) -> dict:
        o        = item.opts
        mode     = o.get("mode", MODE_VIDEO)
        is_audio = (mode == MODE_AUDIO)
        out_path = o.get("path") or self.cfg["download_path"]
        # אוניברסלי: ודא שתיקיית היעד קיימת, אחרת חזרה ל-Downloads
        try:
            os.makedirs(out_path, exist_ok=True)
        except Exception:
            out_path = str(Path.home() / "Downloads")
            os.makedirs(out_path, exist_ok=True)
        sub_lang = o.get("sub_lang", "")

        ffmpeg_path = find_ffmpeg()

        # תבנית שם קובץ )אם ריק — ברירת מחדל %(title)s(
        tmpl = (o.get("filename_template") or "").strip() or "%(title)s"

        ydl: dict = {
            "outtmpl":   os.path.join(out_path, tmpl + ".%(ext)s"),
            "progress_hooks": [hook],
            "quiet":     True,
            "no_warnings": True,
            "ignoreerrors": False,
            "concurrent_fragment_downloads": 8,
        }

        if ffmpeg_path:
            ydl["ffmpeg_location"] = os.path.dirname(ffmpeg_path)

        pps: list = []   # postprocessors

        if is_audio:
            # ── שמע ──
            ydl["format"] = "bestaudio/best"
            abr = o.get("audio_bitrate", "0")
            pps.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": o.get("audio_format", "mp3"),
                "preferredquality": abr if abr and abr != "0" else "0",
            })
        else:
            # ── וידאו ──
            vq = o.get("video_quality", "best")
            cap = "" if vq == "best" else f"[height<={vq}]"
            if o.get("video_only"):
                # וידאו ללא שמע
                ydl["format"] = f"bv*{cap}/b{cap}"
            else:
                ydl["format"] = f"bv*{cap}+ba/b{cap}"
            ydl["merge_output_format"] = "mp4/mkv"
            # דירוג: רזולוציה → fps → bitrate → codec (av1 > vp9 > avc1 כ-tiebreak)
            ydl["format_sort"] = ["res", "fps", "vbr", "abr",
                                  "vcodec:av01:vp9:avc1"]
            # קידוד וידאו מחדש לפורמט קבוע
            if o.get("reencode"):
                pps.append({"key": "FFmpegVideoConvertor",
                            "preferedformat": o["reencode"]})

        # ── מטא-נתונים + פרקים מוטמעים ──
        meta_pp = {"key": "FFmpegMetadata", "add_metadata": True}
        if o.get("embed_chapters"):
            meta_pp["add_chapters"] = True
        pps.append(meta_pp)

        # ── תמונה ממוזערת מוטמעת ──
        if o.get("embed_thumbnail"):
            ydl["writethumbnail"] = True
            pps.append({"key": "EmbedThumbnail"})

        # ── כתוביות ──
        if sub_lang:
            ydl["writesubtitles"]    = True
            ydl["writeautomaticsub"] = True
            ydl["subtitlesformat"]   = "srt"
            if sub_lang == "all":
                ydl["allsubtitles"] = True
            else:
                ydl["subtitleslangs"] = [sub_lang]
            # הטמעת כתוביות בקובץ הווידאו
            if o.get("embed_subs") and not is_audio:
                pps.append({"key": "FFmpegEmbedSubtitle"})

        # ── חוסם ספונסרים )SponsorBlock( ──
        if o.get("sponsorblock"):
            pps.append({"key": "SponsorBlock",
                        "categories": SPONSORBLOCK_CATS, "when": "after_filter"})
            pps.append({"key": "ModifyChapters",
                        "remove_sponsor_segments": SPONSORBLOCK_CATS})

        # ── פיצול לפי פרקים )לקבצים נפרדים( ──
        if o.get("split_chapters"):
            pps.append({"key": "FFmpegSplitChapters"})

        ydl["postprocessors"] = pps

        # ── שידור חי מההתחלה ──
        if o.get("live_from_start"):
            ydl["live_from_start"] = True

        # ── חיתוך )הורדת קטע בלבד( ──
        ts = self._parse_time(o.get("trim_start", ""))
        te = self._parse_time(o.get("trim_end", ""))
        if ts is not None or te is not None:
            rng = (ts or 0.0, te if te is not None else float("inf"))
            ydl["download_ranges"] = yt_dlp.utils.download_range_func(None, [rng])
            ydl["force_keyframes_at_cuts"] = True

        # ── עוגיות ──────────────────────────────────────────────────
        # עדיפות: קובץ cookies.txt > דפדפן מפורש > דפדפן ברירת מחדל
        cookies_file = self.cfg["cookies_file"]
        if cookies_file and Path(cookies_file).exists():
            ydl["cookiefile"] = cookies_file
        elif cookie_browser:
            ydl["cookiesfrombrowser"] = (cookie_browser,)
        elif self.cfg["use_cookies"]:
            ydl["cookiesfrombrowser"] = (self.cfg["browser"],)

        ydl["http_headers"] = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9,he;q=0.8",
        }
        # ── PO Token + client + JS runtime )ל-1080p בסרטונים מוגבלים( ──
        # עם PO token: tv_embedded/web_embedded/mweb נותנים URLs יציבים ל-1080p
        # )לא נחסם ע"י SABR(. בלי token: נופלים ל-default/android )360p legacy(.
        pot = get_po_token()
        if pot and pot.get("po_token"):
            tok = pot["po_token"]
            ydl["extractor_args"] = {"youtube": {
                "player_client":  list(POT_CLIENTS),
                "visitor_data":   [pot["visitor_data"]],
                "po_token":       [f"{c}.gvs+{tok}" for c in POT_CLIENTS],
            }}
        else:
            ydl["extractor_args"] = {"youtube": {"player_client": ["default", "android"]}}

        # node )+ yt-dlp-ejs( פותר את ה-n-challenge — חובה ל-DASH formats
        node = find_node()
        if node:
            ydl["js_runtimes"] = {"node": {"path": None if shutil.which("node") else node}}

        ydl["sleep_interval"]     = 1
        ydl["max_sleep_interval"] = 3

        # ── פקודות נוספות )אפשרויות yt-dlp CLI חופשיות( ──
        # parse_options מחזיר את כל ברירות המחדל — קח רק את מה שהמשתמש שינה,
        # אחרת ידרוס outtmpl/format/postprocessors שכבר הגדרנו.
        extra = (o.get("extra_args") or "").strip()
        if extra:
            try:
                import shlex
                base   = yt_dlp.parse_options([]).ydl_opts
                parsed = yt_dlp.parse_options(shlex.split(extra)).ydl_opts
                diff = {k: v for k, v in parsed.items()
                        if k not in base or base[k] != v}
                diff.pop("progress_hooks", None)   # אל תדרוס את ה-hook של ה-UI
                ydl.update(diff)
                ydl["progress_hooks"] = [hook]
            except Exception:
                pass

        return ydl

    def _run(self, item: DLItem,
             on_progress: Callable,
             on_done: Callable,
             on_error: Callable):

        downloaded_files: list[str] = []
        item.status = "downloading"

        # ── הכנת תלויות לסרטוני YouTube )node ל-n-challenge, PO token( ──
        u = item.url.lower()
        if "youtube.com" in u or "youtu.be" in u:
            if find_node() is None:
                def _st(msg):
                    item.note = msg; on_progress(item)
                ensure_node(on_status=_st)      # מוריד node פעם אחת אם חסר
                item.note = ""
            if get_po_token(peek=True) is None:
                # מונע מראית-עין של "תקוע" כשפותחים WebView2 לאימות מול YouTube
                item.note = "מאמת מול YouTube )פעם ראשונה — עד דקה(..."
                on_progress(item)
                get_po_token()    # מייצר ושומר ב-cache; _build_opts ישתמש ממנו
                item.note = ""

        def hook(d: dict):
            # ── ביטול ──
            if item.cancel_event.is_set():
                raise _Cancelled()
            # ── השהיה — תקוע ב-hook עד שמסירים את ההשהיה ──
            while item.pause_event.is_set() and not item.cancel_event.is_set():
                if item.status != "paused":
                    item.status = "paused"
                    on_progress(item)
                time.sleep(0.3)
            if item.cancel_event.is_set():
                raise _Cancelled()
            if item.status == "paused":
                item.status = "downloading"
                on_progress(item)

            if d["status"] == "downloading":
                item.dl_bytes    = d.get("downloaded_bytes") or 0
                item.total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                item.speed       = d.get("speed") or 0
                item.eta         = d.get("eta") or 0
                item.filename    = Path(d.get("filename", "")).name
                h = (d.get("info_dict") or {}).get("height") or 0
                if h:
                    item.actual_height = max(item.actual_height, h)
                if item.total_bytes > 0:
                    item.progress = (item.dl_bytes / item.total_bytes) * 100
                else:
                    raw = d.get("_percent_str", "0%").strip().rstrip("%")
                    try:
                        item.progress = float(raw)
                    except ValueError:
                        pass
                on_progress(item)

            elif d["status"] == "finished":
                item.status   = "merging"
                item.progress = 99
                fn = d.get("filename", "")
                if fn:
                    downloaded_files.append(fn)
                on_progress(item)

        try:
            def _do_download(opts):
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.download([item.url])

            def _is_cookie_err(exc: Exception) -> bool:
                """כל שגיאה הקשורה לעוגיות דפדפן — נעילה, לא נמצא, הצפנה"""
                s = self._strip_ansi(str(exc)).lower()
                return "cookie" in s

            # ── שרשרת ניסיונות עוגיות ─────────────────────────────────
            # אם יש cookies.txt — ניסיון יחיד, אחרת: כל הדפדפנים → ללא
            browsers_to_try: list[Optional[str]] = []
            if self.cfg["cookies_file"] and Path(self.cfg["cookies_file"]).exists():
                browsers_to_try = [None]   # _build_opts כבר מכניס את הקובץ
            elif self.cfg["use_cookies"]:
                primary = self.cfg["browser"]
                # נסה את כל הדפדפנים הידועים — yt-dlp יודע למצוא אותם
                all_browsers = [primary] + [b for b in self._BROWSER_FALLBACKS
                                            if b != primary]
                browsers_to_try = all_browsers + [None]
            else:
                browsers_to_try = [None]

            err = None
            last_exc: Optional[Exception] = None
            for i, browser in enumerate(browsers_to_try):
                try:
                    opts = self._build_opts(item, hook, cookie_browser=browser)
                    err  = _do_download(opts)
                    last_exc = None
                    item.error = ""
                    break
                except Exception as exc:
                    last_exc = exc
                    if browser is not None and _is_cookie_err(exc):
                        # cookie שגיאה — עבור לניסיון הבא
                        nxt = browsers_to_try[i + 1] if i + 1 < len(browsers_to_try) else None
                        item.error = (f"⚠ עוגיות {browser} לא נגישות — "
                                      f"מנסה {'ללא עוגיות' if nxt is None else nxt}...")
                        on_progress(item)
                        continue
                    # שגיאה אחרת (לא cookie) — זרוק
                    raise

            if last_exc:
                raise last_exc
            if err:
                raise RuntimeError(f"yt-dlp error code {err}")

            # ── מצא את הקובץ שהורד (yt-dlp עשוי לשנות סיומת) ──
            local_file = self._resolve_final_file(downloaded_files,
                                                  item.opts.get("path", ""))
            item.progress = 100
            item.filename = Path(local_file).name if local_file else item.filename

            # ── אזהרה: ביקש איכות גבוהה אך ירד נמוך ──
            if item.opts.get("mode") == MODE_VIDEO and item.actual_height:
                vq = item.opts.get("video_quality", "best")
                want = 99999 if vq == "best" else int(vq)
                if item.actual_height <= 480 and want >= 720:
                    if not find_node():
                        item.note = (f"ירד ב-{item.actual_height}p — חסר Node.js לפתרון "
                                     f"הצפנת YouTube. התקן Node מ-nodejs.org לקבלת 1080p")
                    else:
                        item.note = (f"ירד ב-{item.actual_height}p — לא הושג PO Token "
                                     f")בעיית רשת(. נסה שוב; אם נמשך — בדוק חיבור")

            item.status = "done"
            on_done(item)

        except _Cancelled:
            item.status = "cancelled"
            item.error  = "ההורדה בוטלה"
            on_error(item)
        except yt_dlp.utils.DownloadError as e:
            if item.cancel_event.is_set():
                item.status = "cancelled"; item.error = "ההורדה בוטלה"
            else:
                item.status = "error"; item.error = self._friendly(str(e))
            on_error(item)
        except Exception as e:
            if item.cancel_event.is_set():
                item.status = "cancelled"; item.error = "ההורדה בוטלה"
            else:
                item.status = "error"; item.error = self._friendly(str(e))
            on_error(item)

    @staticmethod
    def _resolve_final_file(candidates: list[str], folder: str) -> Optional[str]:
        """מצא את קובץ הווידאו הסופי — yt-dlp משנה סיומות לאחר מיזוג"""
        for path in candidates:
            p = Path(path)
            # נסה את הנתיב המקורי
            if p.exists():
                return str(p)
            # נסה mp4 (לאחר מיזוג)
            mp4 = p.with_suffix(".mp4")
            if mp4.exists():
                return str(mp4)
        # אם לא נמצא בניסויים — חפש בתיקייה
        if folder and Path(folder).exists():
            video_exts = {".mp4", ".mkv", ".webm", ".m4v", ".mp3", ".m4a"}
            files = sorted(
                [f for f in Path(folder).iterdir()
                 if f.suffix.lower() in video_exts],
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
            if files:
                return str(files[0])
        return ""

    @staticmethod
    def _strip_ansi(s: str) -> str:
        return re.sub(r'\x1b\[[0-9;]*[A-Za-z]|\x1b\[[0-9;]*m', '', s)

    @classmethod
    def _friendly(cls, raw: str) -> str:
        raw = cls._strip_ansi(raw)
        s = raw.lower()
        if any(x in s for x in ("could not copy", "unable to copy", "cookie")) and \
                any(x in s for x in ("chrome", "chromium", "browser")):
            return ("🍪 לא ניתן לגשת לעוגיות הדפדפן — Chrome כנראה פתוח ונועל את הקובץ.\n\n"
                    "פתרונות:\n"
                    "1. סגור את Chrome לגמרי ונסה שוב\n"
                    "2. עבור להגדרות → שנה דפדפן ל-Firefox/Edge\n"
                    "3. כבה 'שימוש בעוגיות דפדפן' בהגדרות (פחות יעיל נגד חסימות)")
        if any(x in s for x in ("sign in", "login", "age-restricted")):
            return ("🔒 הסרטון דורש כניסה לחשבון.\n"
                    "פתרון: הפעל 'שימוש בעוגיות דפדפן' בהגדרות, "
                    "וודא שאתה מחובר ליוטיוב בדפדפן שלך.")
        if "private" in s:
            return "🔒 זהו סרטון פרטי. אין לך גישה אליו."
        if any(x in s for x in ("unavailable", "not available", "removed")):
            return ("❌ הסרטון אינו זמין.\n"
                    "ייתכן שהוסר, חסום לפי מיקום גיאוגרפי, או מוגבל לגיל.\n"
                    "נסה: הפעל עוגיות דפדפן, או השתמש ב-VPN.")
        if any(x in s for x in ("bot", "automated", "403")):
            return ("🤖 יוטיוב זיהה גישה אוטומטית.\n"
                    "פתרונות:\n"
                    "1. הפעל 'שימוש בעוגיות דפדפן' בהגדרות\n"
                    "2. וודא שאתה מחובר ליוטיוב בדפדפן\n"
                    "3. המתן מספר דקות ונסה שוב")
        if "format" in s and "not available" in s:
            return "📺 הפורמט המבוקש אינו זמין לסרטון זה. נסה איכות שונה."
        if "ffmpeg" in s:
            return ("🔧 FFmpeg לא נמצא.\n"
                    "הורד והתקן מ: https://ffmpeg.org/download.html\n"
                    "ואז הוסף לנתיב המערכת (PATH).")
        if any(x in s for x in ("network", "connection", "timeout")):
            return "🌐 שגיאת רשת. בדוק את חיבור האינטרנט שלך ונסה שוב."
        if any(x in s for x in ("copyright", "blocked")):
            return "🚫 תוכן חסום עקב זכויות יוצרים. נסה VPN או רשת אחרת."
        return raw.replace("ERROR: ", "").strip()[:600]

    @staticmethod
    def detect_type(url: str) -> str:
        if not url:
            return "empty"
        if "list=" in url and "watch?v=" in url:
            return "video_in_playlist"
        if "list=" in url:
            return "playlist"
        if re.search(r"/(channel|c|user)/|/@", url):
            return "channel"
        if "watch?v=" in url or "youtu.be/" in url:
            return "video"
        return "unknown"

    @staticmethod
    def fetch_info(url: str) -> tuple[bool, dict]:
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True}) as ydl:
                info = ydl.extract_info(url, download=False)
            return True, info or {}
        except Exception as e:
            return False, {"error": str(e)}

# ══════════════════════════════════════════════════════════════════
#  רכיבי UI
# ══════════════════════════════════════════════════════════════════

def card(master, hover=True, **kw) -> ctk.CTkFrame:
    f = ctk.CTkFrame(master, fg_color=C["card"], corner_radius=14,
                     border_width=1, border_color=C["border"], **kw)
    if hover:
        # זוהר ניאון בריחוף — בודק שהעכבר באמת יצא )מונע ריצוד מהילדים(
        def _enter(_):
            f.configure(border_color=C["accent"])
        def _leave(_):
            try:
                px, py = f.winfo_pointerxy()
                fx, fy = f.winfo_rootx(), f.winfo_rooty()
                if not (fx <= px < fx + f.winfo_width()
                        and fy <= py < fy + f.winfo_height()):
                    f.configure(border_color=C["border"])
            except Exception:
                f.configure(border_color=C["border"])
        f.bind("<Enter>", _enter)
        f.bind("<Leave>", _leave)
    return f

def label(master, text, size=12, bold=False, color=None, **kw) -> ctk.CTkLabel:
    return ctk.CTkLabel(
        master, text=text,
        font=ctk.CTkFont(size=size, weight="bold" if bold else "normal"),
        text_color=color or C["txt"], **kw
    )

def btn(master, text, cmd, width=None, height=38, color=None, hover=None,
        ghost=False, **kw) -> ctk.CTkButton:
    fc = "transparent" if ghost else (color or C["blue"])
    hc = C["border"] if ghost else (hover or C["blue_h"])
    bw = 1 if ghost else 0
    bc = C["border"]
    return ctk.CTkButton(
        master, text=text, command=cmd,
        width=width or 0, height=height,
        font=ctk.CTkFont(size=12, weight="bold"),
        fg_color=fc, hover_color=hc,
        border_width=bw, border_color=bc,
        corner_radius=8, **kw
    )


class ChipToggle(ctk.CTkButton):
    """כפתור toggle בסגנון התמונות — פעיל = ניאון צהוב, כבוי = כהה.
    מקושר ל-tk.BooleanVar; קורא ל-on_change בכל החלפה."""
    def __init__(self, master, text, variable, on_change=None, **kw):
        self._var = variable
        self._on_change = on_change
        super().__init__(master, text=text, command=self._toggle,
                         height=42, corner_radius=12,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         anchor="center", **kw)
        self._refresh()

    def _toggle(self):
        self._var.set(not self._var.get())
        self._refresh()
        if self._on_change:
            self._on_change()

    def refresh(self):
        self._refresh()

    def _refresh(self):
        if self._var.get():
            self.configure(fg_color=C["accent"], text_color=C["on_accent"],
                           hover_color=C["accent_h"], border_width=0)
        else:
            self.configure(fg_color=C["card2"], text_color=C["txt2"],
                           hover_color=C["input"], border_width=1,
                           border_color=C["border"])


def seg_button(master, options, variable, on_change=None, **kw):
    """בורר מקטעים )segmented( — בחירה יחידה מתוך כמה אפשרויות."""
    sb = ctk.CTkSegmentedButton(
        master, values=[o[0] for o in options],
        font=ctk.CTkFont(size=12, weight="bold"),
        fg_color=C["card2"], selected_color=C["accent"],
        selected_hover_color=C["accent_h"], unselected_color=C["card2"],
        unselected_hover_color=C["input"], text_color=C["txt"],
        height=40, corner_radius=10, **kw)
    return sb

# ══════════════════════════════════════════════════════════════════
#  כרטיס התקדמות
# ══════════════════════════════════════════════════════════════════

class ProgressCard(ctk.CTkFrame):
    STATUS_LABELS = {
        "downloading": ("↓ מוריד מ-YouTube...",       C["blue"]),
        "paused":      ("⏸ מושהה",                    C["orange"]),
        "merging":     ("⚙ ממזג וידאו+שמע...",        C["orange"]),
        "done":        ("✓ הושלם",                    C["green"]),
        "error":       ("✗ שגיאה",                    C["error"]),
        "cancelled":   ("⨯ בוטל",                     C["txt3"]),
        "pending":     ("⏳ ממתין...",                 C["txt2"]),
    }

    def __init__(self, master, item: DLItem, on_pause=None, on_cancel=None, **kw):
        super().__init__(master, fg_color=C["card2"], corner_radius=12,
                         border_width=1, border_color=C["border"], **kw)
        self._item = item
        self._on_pause  = on_pause
        self._on_cancel = on_cancel
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        # שורת כותרת: שם קובץ + כפתורי שליטה
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, padx=16, pady=(12, 6), sticky="ew")
        top.grid_columnconfigure(0, weight=1)
        self._name = label(top, "מכין...", size=12, bold=True,
                           anchor="w", wraplength=440)
        self._name.grid(row=0, column=0, sticky="ew")

        self._btn_pause = ctk.CTkButton(
            top, text="⏸", width=34, height=30, corner_radius=8,
            font=ctk.CTkFont(size=14), fg_color=C["input"],
            hover_color=C["border"], text_color=C["txt"],
            command=self._pause_clicked)
        self._btn_pause.grid(row=0, column=1, padx=(6, 0))
        self._btn_cancel = ctk.CTkButton(
            top, text="✕", width=34, height=30, corner_radius=8,
            font=ctk.CTkFont(size=14), fg_color=C["input"],
            hover_color=C["error"], text_color=C["txt"],
            command=self._cancel_clicked)
        self._btn_cancel.grid(row=0, column=2, padx=(6, 0))

        # פס התקדמות
        self._bar = ctk.CTkProgressBar(
            self, height=10,
            fg_color=C["input"],
            progress_color=C["progress"],
            corner_radius=5,
        )
        self._bar.set(0)
        self._bar.grid(row=1, column=0, padx=16, sticky="ew", pady=(0, 8))

        # שורת מידע
        info = ctk.CTkFrame(self, fg_color="transparent")
        info.grid(row=2, column=0, padx=16, sticky="ew", pady=(0, 12))

        self._pct   = label(info, "0%",   size=15, bold=True, color=C["accent"])
        self._pct.pack(side="left")

        self._size  = label(info, "",     size=11, color=C["txt2"])
        self._size.pack(side="left", padx=(14, 0))

        self._spd   = label(info, "",     size=11, color=C["txt2"])
        self._spd.pack(side="left", padx=(14, 0))

        self._eta   = label(info, "",     size=11, color=C["txt2"])
        self._eta.pack(side="right")

        self._status = label(info, "ממתין...", size=11, bold=True, color=C["txt2"])
        self._status.pack(side="right", padx=(0, 16))

    def _pause_clicked(self):
        it = self._item
        if it.status in ("done", "error", "cancelled"):
            return
        if it.pause_event.is_set():
            it.pause_event.clear()          # המשך
        else:
            it.pause_event.set()            # השהה
        if self._on_pause:
            self._on_pause(it)

    def _cancel_clicked(self):
        it = self._item
        if it.status in ("done", "error", "cancelled"):
            return
        it.cancel_event.set()
        it.pause_event.clear()              # שחרר השהיה כדי שה-hook יזרוק מיד
        if self._on_cancel:
            self._on_cancel(it)

    def update(self, item: DLItem):
        self._item = item

        # שם
        name = item.filename or item.url[:60]
        if len(name) > 70:
            name = name[:67] + "..."
        self._name.configure(text=name)

        # כפתורי שליטה — אייקון pause/play + הסתרה בסיום
        if item.status in ("done", "error", "cancelled"):
            self._btn_pause.grid_remove()
            self._btn_cancel.grid_remove()
        else:
            self._btn_pause.configure(text="▶" if item.pause_event.is_set() else "⏸")

        # פס
        pv = min(item.progress / 100, 1.0)
        self._bar.set(pv)

        # %
        self._pct.configure(text=f"{item.progress:.1f}%")

        # גדלים
        if item.total_bytes > 0:
            dl  = item.dl_bytes    / 1_048_576
            tot = item.total_bytes / 1_048_576
            self._size.configure(text=f"{dl:.1f} MB / {tot:.1f} MB")

        # מהירות (רק בהורדה)
        if item.speed > 0 and item.status == "downloading":
            if item.speed >= 1_048_576:
                spd = f"{item.speed/1_048_576:.1f} MB/s"
            else:
                spd = f"{item.speed/1024:.0f} KB/s"
            self._spd.configure(text=f"⚡ {spd}")
        elif item.status in ("merging", "done", "paused", "cancelled"):
            self._spd.configure(text="")

        # ETA
        if item.eta > 0 and item.status == "downloading":
            if item.eta > 3600:
                es = f"{item.eta//3600}ש' {(item.eta%3600)//60}ד'"
            elif item.eta > 60:
                es = f"{item.eta//60}ד' {item.eta%60}ש\""
            else:
                es = f"{item.eta}ש\""
            self._eta.configure(text=f"ETA {es}")
        else:
            self._eta.configure(text="")

        # סטטוס + צבע פס
        lbl, col = self.STATUS_LABELS.get(item.status, ("", C["txt2"]))
        self._status.configure(text=lbl, text_color=col)

        bar_colors = {
            "downloading": C["blue"],
            "paused":      C["orange"],
            "merging":     C["orange"],
            "done":        C["green"],
            "error":       C["error"],
            "cancelled":   C["txt3"],
        }
        bar_col = bar_colors.get(item.status, C["blue"])
        self._bar.configure(progress_color=bar_col)
        self._pct.configure(
            text_color=col if item.status in ("done", "error", "cancelled") else bar_col)

        if item.status == "done":
            self._bar.set(1)

        # אזהרת DRM/איכות נמוכה
        if item.note and item.status == "done":
            self._name.configure(text=f"{name}\n{item.note}", text_color=C["orange"])

# ══════════════════════════════════════════════════════════════════
#  האפליקציה הראשית
# ══════════════════════════════════════════════════════════════════

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        # פונט מערכת אחיד לכל הרכיבים )Segoe UI — נקי ומודרני(
        try:
            ctk.ThemeManager.theme["CTkFont"]["family"] = "Segoe UI"
        except Exception:
            pass

        self.cfg        = Config()
        self.dl         = Downloader(self.cfg)
        self._q:   queue.Queue   = queue.Queue()
        self._cards: Dict[int, ProgressCard] = {}
        self._card_row = 0

        self._setup_window()
        self._build_ui()
        self._tick()
        self._check_ffmpeg()

    # ── חלון ──────────────────────────────────────────────────────

    def _setup_window(self):
        self.title(f"{APP_NAME}  v{APP_VER}")
        self.geometry("960x720")
        self.minsize(820, 580)
        self.configure(fg_color=C["bg"])
        try:
            if os.path.exists(ICON_PATH):
                self.iconbitmap(ICON_PATH)
        except Exception:
            pass
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        ww, wh = 960, 720
        self.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")
        # אפקט זכוכית מטושטשת — לאחר שהחלון מצויר )מונע הבהוב(
        self.after(120, self._apply_glass)

    def _apply_glass(self):
        """זכוכית מטושטשת אמיתית של Windows — Mica )Win11( / Acrylic )Win10(.
        נכשל בשקט בכל סביבה שלא תומכת."""
        if not (PYWINSTYLES_AVAILABLE and sys.platform == "win32"):
            return
        try:
            build = sys.getwindowsversion().build
            style = "mica" if build >= 22000 else "acrylic"
            pywinstyles.apply_style(self, style)
            # כותרת כהה תואמת לסגנון הזכוכית
            try:
                pywinstyles.change_header_color(self, C["sidebar"])
                pywinstyles.change_title_color(self, C["txt"])
            except Exception:
                pass
            # רענון כדי שהאפקט יתפוס מיד )תיקון הבהוב ידוע ב-CTk(
            self.wm_attributes("-alpha", 0.99)
            self.after(60, lambda: self.wm_attributes("-alpha", 1.0))
        except Exception:
            pass

    # ── ממשק ──────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_content()
        self._show("download")

    # ─ Sidebar ────────────────────────────────────────────────────

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=200, fg_color=C["sidebar"],
                          corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)

        # לוגו
        logo = ctk.CTkFrame(sb, fg_color="transparent")
        logo.pack(padx=16, pady=(22, 4))
        ctk.CTkLabel(logo, text="▶", font=ctk.CTkFont(size=30),
                     text_color=C["accent"]).pack(side="left")
        ctk.CTkLabel(logo, text=" YT Pro", font=ctk.CTkFont(size=19, weight="bold"),
                     text_color=C["txt"]).pack(side="left")
        label(sb, f"v{APP_VER}", size=10, color=C["txt3"]).pack()

        ctk.CTkFrame(sb, height=1, fg_color=C["border"]).pack(
            fill="x", padx=16, pady=16)

        # ניווט
        self._nav: Dict[str, ctk.CTkButton] = {}
        for icon, txt, page in [
            ("⬇", "הורדה",    "download"),
            ("📋", "תור",      "queue"),
            ("⚙", "הגדרות",  "settings"),
        ]:
            b = ctk.CTkButton(
                sb, text=f"  {icon}  {txt}",
                anchor="w", height=42,
                font=ctk.CTkFont(size=13),
                fg_color="transparent",
                text_color=C["txt2"],
                hover_color=C["card"],
                corner_radius=10,
                command=lambda p=page: self._show(p),
            )
            b.pack(fill="x", padx=10, pady=2)
            self._nav[page] = b

        # סטטוס תחתי
        self._lbl_ytdlp = label(sb, "● yt-dlp מוכן", size=10, color=C["green"])
        self._lbl_ytdlp.pack(side="bottom", pady=(4, 16))

        self._lbl_ffmpeg = label(sb, "", size=10, color=C["txt3"])
        self._lbl_ffmpeg.pack(side="bottom", pady=2)

    # ─ Content ────────────────────────────────────────────────────

    def _build_content(self):
        self._content = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        self._content.grid(row=0, column=1, sticky="nsew")
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_rowconfigure(0, weight=1)

        self._pages: Dict[str, ctk.CTkFrame] = {
            "download": self._page_download(),
            "queue":    self._page_queue(),
            "settings": self._page_settings(),
        }

    def _show(self, page: str):
        for p, f in self._pages.items():
            f.grid_remove()
        self._pages[page].grid(row=0, column=0, sticky="nsew", padx=24, pady=20)
        for p, b in self._nav.items():
            if p == page:
                b.configure(fg_color=C["accent"], text_color=C["on_accent"])
            else:
                b.configure(fg_color="transparent", text_color=C["txt2"])

    # ══════════════════════════════════════════════════════════════
    #  מערכת אפשרויות — משותפת לעמוד הורדה ולהגדרות
    # ══════════════════════════════════════════════════════════════

    def _opt_combo(self, parent, choices, var, on_change):
        """ComboBox המקושר ל-StringVar שמחזיק value )לא label(."""
        labels = [c[0] for c in choices]
        l2v = {c[0]: c[1] for c in choices}
        v2l = {c[1]: c[0] for c in choices}
        def pick(lbl):
            var.set(l2v.get(lbl, choices[0][1]))
            if on_change:
                on_change()
        cb = ctk.CTkComboBox(
            parent, values=labels, state="readonly", height=36,
            font=ctk.CTkFont(size=12), fg_color=C["input"],
            border_color=C["border"], button_color=C["accent"],
            button_hover_color=C["accent_h"], dropdown_fg_color=C["card"],
            command=pick)
        cb.set(v2l.get(var.get(), labels[0]))
        return cb

    def _build_opts_ui(self, parent, persist: bool) -> dict:
        """בונה את כל מערכת האפשרויות. מחזיר W )dict של vars(.
           persist=True → כל שינוי נשמר ל-config )מצב הגדרות(."""
        c = self.cfg
        def save(k, v):
            if persist:
                self.cfg[k] = v

        si = c["default_subtitle"]
        sub_val = SUBTITLES[si][1] if 0 <= si < len(SUBTITLES) else ""
        W = {
            "persist":           persist,
            "mode":              tk.StringVar(value="auto" if c["mode_auto"] else c["default_mode"]),
            "video_quality":     tk.StringVar(value=c["video_quality"]),
            "video_only":        tk.BooleanVar(value=c["video_only"]),
            "audio_format":      tk.StringVar(value=c["audio_format"]),
            "audio_bitrate":     tk.StringVar(value=c["audio_bitrate"]),
            "reencode":          tk.StringVar(value=c["reencode"]),
            "sub_lang":          tk.StringVar(value=sub_val),
            "embed_thumbnail":   tk.BooleanVar(value=c["embed_thumbnail"]),
            "embed_chapters":    tk.BooleanVar(value=c["embed_chapters"]),
            "embed_subs":        tk.BooleanVar(value=c["embed_subs"]),
            "split_chapters":    tk.BooleanVar(value=c["split_chapters"]),
            "sponsorblock":      tk.BooleanVar(value=c["sponsorblock"]),
            "live_from_start":   tk.BooleanVar(value=c["live_from_start"]),
            "filename_template": tk.StringVar(value=c["filename_template"]),
            "extra_args":        tk.StringVar(value=c["extra_args"]),
            "trim_start":        tk.StringVar(value=c["trim_start"]),
            "trim_end":          tk.StringVar(value=c["trim_end"]),
        }

        parent.grid_columnconfigure(0, weight=1)
        r = 0

        # ── בורר מצב: אוטומטי / וידאו / שמע ──
        seg = ctk.CTkSegmentedButton(
            parent, values=[m[0] for m in MODE_CHOICES],
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=C["card2"], selected_color=C["accent"],
            selected_hover_color=C["accent_h"], unselected_color=C["card2"],
            unselected_hover_color=C["input"], text_color=C["txt"],
            height=40, command=lambda v: self._on_mode_pick(W, v, save))
        seg.set(next((m[0] for m in MODE_CHOICES if m[1] == W["mode"].get()),
                     MODE_CHOICES[0][0]))
        seg.grid(row=r, column=0, sticky="ew", pady=(0, 10)); r += 1
        W["seg"] = seg

        # ── אזור איכות מתחלף )וידאו / שמע( ──
        qhost = ctk.CTkFrame(parent, fg_color="transparent")
        qhost.grid(row=r, column=0, sticky="ew", pady=(0, 8)); r += 1
        qhost.grid_columnconfigure(0, weight=1)

        vf = ctk.CTkFrame(qhost, fg_color="transparent")
        vf.grid_columnconfigure((0, 1), weight=1)
        label(vf, "איכות וידאו", size=12, color=C["txt2"]).grid(
            row=0, column=0, sticky="w", padx=(0, 6))
        self._opt_combo(vf, VIDEO_QUALITIES, W["video_quality"],
                        lambda: save("video_quality", W["video_quality"].get())
                        ).grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=(2, 0))
        label(vf, "קידוד מחדש", size=12, color=C["txt2"]).grid(
            row=0, column=1, sticky="w", padx=(6, 0))
        self._opt_combo(vf, REENCODE_CHOICES, W["reencode"],
                        lambda: save("reencode", W["reencode"].get())
                        ).grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(2, 0))
        ChipToggle(vf, "🔇  וידאו ללא שמע", W["video_only"],
                   on_change=lambda: save("video_only", W["video_only"].get())
                   ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        W["vf"] = vf

        af = ctk.CTkFrame(qhost, fg_color="transparent")
        af.grid_columnconfigure((0, 1), weight=1)
        label(af, "פורמט שמע", size=12, color=C["txt2"]).grid(
            row=0, column=0, sticky="w", padx=(0, 6))
        self._opt_combo(af, AUDIO_FORMATS, W["audio_format"],
                        lambda: save("audio_format", W["audio_format"].get())
                        ).grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=(2, 0))
        label(af, "קצב סיביות", size=12, color=C["txt2"]).grid(
            row=0, column=1, sticky="w", padx=(6, 0))
        self._opt_combo(af, AUDIO_BITRATES, W["audio_bitrate"],
                        lambda: save("audio_bitrate", W["audio_bitrate"].get())
                        ).grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(2, 0))
        W["af"] = af

        # ── כתוביות ──
        label(parent, "כתוביות", size=12, color=C["txt2"]).grid(
            row=r, column=0, sticky="w", pady=(4, 2)); r += 1
        self._opt_combo(parent, SUBTITLES, W["sub_lang"],
                        lambda: save("default_subtitle",
                                     next((i for i, s in enumerate(SUBTITLES)
                                           if s[1] == W["sub_lang"].get()), 0))
                        ).grid(row=r, column=0, sticky="ew", pady=(0, 10)); r += 1

        # ── chips התאמה אישית ──
        label(parent, "התאמה אישית", size=12, color=C["txt2"]).grid(
            row=r, column=0, sticky="w", pady=(0, 4)); r += 1
        chips = ctk.CTkFrame(parent, fg_color="transparent")
        chips.grid(row=r, column=0, sticky="ew", pady=(0, 8)); r += 1
        chips.grid_columnconfigure((0, 1, 2), weight=1)
        chip_defs = [
            ("🖼  תמונה ממוזערת", "embed_thumbnail"),
            ("📑  פרקים",          "embed_chapters"),
            ("💬  הטמע כתוביות",   "embed_subs"),
            ("🛡  חוסם ספונסרים",  "sponsorblock"),
            ("📡  שידור חי",        "live_from_start"),
            ("✂  פיצול לפי פרקים", "split_chapters"),
        ]
        for i, (txt, key) in enumerate(chip_defs):
            ChipToggle(chips, txt, W[key],
                       on_change=lambda k=key: save(k, W[k].get())
                       ).grid(row=i // 3, column=i % 3, sticky="ew", padx=3, pady=3)

        # ── שדות טקסט ──
        flds = ctk.CTkFrame(parent, fg_color="transparent")
        flds.grid(row=r, column=0, sticky="ew"); r += 1
        flds.grid_columnconfigure((0, 1), weight=1)

        def field(col, row, ph, key, span=1):
            var = W[key]
            e = ctk.CTkEntry(flds, placeholder_text=ph, textvariable=var,
                             height=34, font=ctk.CTkFont(size=11),
                             fg_color=C["input"], border_color=C["border"])
            e.grid(row=row, column=col, columnspan=span, sticky="ew", padx=3, pady=3)
            if persist:
                e.bind("<FocusOut>",
                       lambda ev, k=key, v=var: self.cfg.__setitem__(k, v.get()))
            return e

        field(0, 0, "תבנית שם קובץ — ברירת מחדל %(title)s", "filename_template", span=2)
        field(0, 1, "חיתוך מ- )0:30(", "trim_start")
        field(1, 1, "חיתוך עד- )2:00(", "trim_end")
        field(0, 2, "פקודות yt-dlp נוספות — לדוגמה --no-mtime", "extra_args", span=2)

        self._sync_mode_view(W)
        return W

    def _on_mode_pick(self, W, label_txt, save):
        val = next((m[1] for m in MODE_CHOICES if m[0] == label_txt), "auto")
        W["mode"].set(val)
        save("mode_auto", val == "auto")
        if val != "auto":
            save("default_mode", val)
        self._sync_mode_view(W)

    def _sync_mode_view(self, W):
        """מציג את אזור הווידאו או השמע לפי המצב )ב-auto — לפי הקישור(."""
        m = W["mode"].get()
        if m == "auto":
            url = self._url.get().strip() if (not W["persist"] and hasattr(self, "_url")) else ""
            eff = detect_mode(url)
        else:
            eff = m
        W["vf"].grid_remove(); W["af"].grid_remove()
        if eff == MODE_AUDIO:
            W["af"].grid(row=0, column=0, sticky="ew")
        else:
            W["vf"].grid(row=0, column=0, sticky="ew")

    def _opts_from_W(self, W, url) -> dict:
        return {
            "mode":              (detect_mode(url) if W["mode"].get() == "auto"
                                  else W["mode"].get()),
            "video_quality":     W["video_quality"].get(),
            "video_only":        W["video_only"].get(),
            "audio_format":      W["audio_format"].get(),
            "audio_bitrate":     W["audio_bitrate"].get(),
            "reencode":          W["reencode"].get(),
            "sub_lang":          W["sub_lang"].get(),
            "embed_thumbnail":   W["embed_thumbnail"].get(),
            "embed_chapters":    W["embed_chapters"].get(),
            "embed_subs":        W["embed_subs"].get(),
            "split_chapters":    W["split_chapters"].get(),
            "sponsorblock":      W["sponsorblock"].get(),
            "live_from_start":   W["live_from_start"].get(),
            "filename_template": W["filename_template"].get(),
            "extra_args":        W["extra_args"].get(),
            "trim_start":        W["trim_start"].get(),
            "trim_end":          W["trim_end"].get(),
            "path":              self._path_entry.get() or self.cfg["download_path"],
        }

    # ══════════════════════════════════════════════════════════════
    #  עמוד הורדה
    # ══════════════════════════════════════════════════════════════

    def _page_download(self) -> ctk.CTkFrame:
        root = ctk.CTkScrollableFrame(self._content, fg_color="transparent",
                                      scrollbar_button_color=C["border"])
        root.grid_columnconfigure(0, weight=1)

        # כותרת + פס gradient דקורטיבי
        head = ctk.CTkFrame(root, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        head.grid_columnconfigure(0, weight=1)
        label(head, "הורדה מ-YouTube", size=24, bold=True).grid(
            row=0, column=0, sticky="w")
        label(head, "סרטונים  ·  פלייליסטים  ·  ערוצים שלמים",
              size=12, color=C["txt2"]).grid(row=1, column=0, sticky="w", pady=(0, 8))
        self._grad_line = ctk.CTkImage(make_gradient(1400, 3, GRAD_NEON), size=(1400, 3))
        ctk.CTkLabel(head, text="", image=self._grad_line).grid(
            row=2, column=0, sticky="ew")

        # כרטיס URL
        url_c = card(root)
        url_c.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        url_c.grid_columnconfigure(0, weight=1)

        label(url_c, "🔗  כתובת YouTube", size=13, bold=True).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 8))

        row_url = ctk.CTkFrame(url_c, fg_color="transparent")
        row_url.grid(row=1, column=0, padx=16, sticky="ew", pady=(0, 6))
        row_url.grid_columnconfigure(0, weight=1)

        self._url = ctk.CTkEntry(
            row_url, placeholder_text="הדבק כתובת YouTube כאן...",
            height=42, font=ctk.CTkFont(size=12),
            fg_color=C["input"], border_color=C["border"],
            text_color=C["txt"],
        )
        self._url.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._url.bind("<KeyRelease>", self._on_url_key)

        btn(row_url, "📋 הדבק", self._paste, width=90, height=42,
            ghost=True).grid(row=0, column=1, padx=(0, 8))
        btn(row_url, "🔍 זהה",  self._detect, width=90, height=42,
            color=C["blue"]).grid(row=0, column=2)

        self._url_badge = label(url_c, "", size=11, color=C["txt2"])
        self._url_badge.grid(row=2, column=0, sticky="w", padx=18, pady=(0, 14))

        # כרטיס אפשרויות — מערכת מלאה )מצב, איכות, התאמה אישית(
        opt_c = card(root)
        opt_c.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        opt_c.grid_columnconfigure(0, weight=1)

        label(opt_c, "⚙  אפשרויות הורדה", size=13, bold=True).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 10))

        opt_body = ctk.CTkFrame(opt_c, fg_color="transparent")
        opt_body.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 14))
        opt_body.grid_columnconfigure(0, weight=1)
        self._dlW = self._build_opts_ui(opt_body, persist=False)

        # כרטיס שמירה
        save_c = card(root)
        save_c.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        save_c.grid_columnconfigure(0, weight=1)

        label(save_c, "📁  תיקיית שמירה", size=13, bold=True).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 8))

        row_path = ctk.CTkFrame(save_c, fg_color="transparent")
        row_path.grid(row=1, column=0, padx=16, sticky="ew", pady=(0, 10))
        row_path.grid_columnconfigure(0, weight=1)

        self._path_entry = ctk.CTkEntry(
            row_path, height=38, font=ctk.CTkFont(size=12),
            fg_color=C["input"], border_color=C["border"],
        )
        self._path_entry.insert(0, self.cfg["download_path"])
        self._path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        btn(row_path, "בחר תיקייה", self._browse, width=110, height=38,
            ghost=True).grid(row=0, column=1, pady=(0, 4))

        # כפתור הורדה
        self._dl_grad_img = ctk.CTkImage(
            make_gradient(1600, 54, GRAD_NEON, horizontal=True), size=(1600, 54))
        self._dl_btn = ctk.CTkButton(
            root, text="  ↓  התחל הורדה  ",
            image=self._dl_grad_img, compound="center",
            height=54, font=ctk.CTkFont(size=17, weight="bold"),
            fg_color=C["accent"], hover_color=C["accent_h"],
            text_color="#FFFFFF",
            corner_radius=14, command=self._start,
        )
        self._dl_btn.grid(row=5, column=0, sticky="ew", pady=(6, 18))

        # אזור התקדמות
        label(root, "הורדות פעילות", size=15, bold=True).grid(
            row=6, column=0, sticky="w", pady=(0, 8))

        self._prog_area = ctk.CTkFrame(root, fg_color="transparent")
        self._prog_area.grid(row=7, column=0, sticky="ew")
        self._prog_area.grid_columnconfigure(0, weight=1)

        self._no_dl_lbl = label(self._prog_area, "אין הורדות פעילות",
                                size=12, color=C["txt3"])
        self._no_dl_lbl.grid(row=0, column=0, pady=20)

        return root

    # ══════════════════════════════════════════════════════════════
    #  עמוד תור
    # ══════════════════════════════════════════════════════════════

    def _page_queue(self) -> ctk.CTkFrame:
        f = ctk.CTkFrame(self._content, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(1, weight=1)
        label(f, "תור הורדות", size=22, bold=True).grid(
            row=0, column=0, sticky="w", pady=(0, 12))
        self._queue_scroll = ctk.CTkScrollableFrame(
            f, fg_color=C["card"], corner_radius=12)
        self._queue_scroll.grid(row=1, column=0, sticky="nsew")
        self._queue_scroll.grid_columnconfigure(0, weight=1)
        label(self._queue_scroll, "התור ריק", size=13,
              color=C["txt3"]).grid(row=0, column=0, pady=40)
        return f

    # ══════════════════════════════════════════════════════════════
    #  עמוד הגדרות
    # ══════════════════════════════════════════════════════════════

    def _page_settings(self) -> ctk.CTkFrame:
        root = ctk.CTkScrollableFrame(self._content, fg_color="transparent",
                                      scrollbar_button_color=C["border"])
        root.grid_columnconfigure(0, weight=1)
        r = 0

        label(root, "הגדרות", size=22, bold=True).grid(
            row=r, column=0, sticky="w", pady=(0, 18)); r += 1

        # ── ברירות מחדל להורדה )מערכת מלאה( ──
        c1 = card(root)
        c1.grid(row=r, column=0, sticky="ew", pady=(0, 10)); r += 1
        c1.grid_columnconfigure(0, weight=1)
        label(c1, "📺  ברירות מחדל להורדה", size=14, bold=True).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 2))
        label(c1, "הערכים שייבחרו אוטומטית בכל הורדה חדשה",
              size=11, color=C["txt2"]).grid(
            row=1, column=0, sticky="w", padx=16, pady=(0, 8))
        c1_body = ctk.CTkFrame(c1, fg_color="transparent")
        c1_body.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 14))
        c1_body.grid_columnconfigure(0, weight=1)
        self._setW = self._build_opts_ui(c1_body, persist=True)

        # ── עקיפת חסימות ──
        c2 = card(root)
        c2.grid(row=r, column=0, sticky="ew", pady=(0, 10)); r += 1
        c2.grid_columnconfigure(0, weight=1)
        label(c2, "🛡  עקיפת זיהוי בוטים", size=14, bold=True).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 4))
        label(c2, "שימוש בעוגיות הדפדפן כדי למנוע חסימות יוטיוב",
              size=11, color=C["txt2"]).grid(
            row=1, column=0, sticky="w", padx=16, pady=(0, 10))

        self._cookies_sw = ctk.CTkSwitch(
            c2, text="שימוש בעוגיות דפדפן",
            font=ctk.CTkFont(size=12), text_color=C["txt"],
            progress_color=C["green"], command=self._toggle_cookies)
        if self.cfg["use_cookies"]:
            self._cookies_sw.select()
        self._cookies_sw.grid(row=2, column=0, sticky="w", padx=16, pady=(0, 8))

        label(c2, "בחר דפדפן", size=12, color=C["txt2"]).grid(
            row=3, column=0, sticky="w", padx=16)
        self._browser_cb = ctk.CTkComboBox(
            c2, values=BROWSERS, height=36, font=ctk.CTkFont(size=12),
            fg_color=C["input"], border_color=C["border"],
            button_color=C["accent"], button_hover_color=C["accent_h"],
            dropdown_fg_color=C["card"], state="readonly",
            command=self._save_browser)
        self._browser_cb.set(self.cfg["browser"])
        self._browser_cb.grid(row=4, column=0, sticky="ew", padx=16, pady=(4, 8))

        # cookies.txt — חלופה לדפדפן נעול
        label(c2,
              "אם Chrome/Edge נעולים — ייצא cookies.txt מהדפדפן\n"
              "באמצעות תוסף \"Get cookies.txt LOCALLY\" והצבע לקובץ:",
              size=10, color=C["txt3"], justify="left").grid(
            row=5, column=0, sticky="w", padx=16, pady=(4, 4))

        row_ck = ctk.CTkFrame(c2, fg_color="transparent")
        row_ck.grid(row=6, column=0, padx=16, sticky="ew", pady=(0, 16))
        row_ck.grid_columnconfigure(0, weight=1)

        self._ck_entry = ctk.CTkEntry(
            row_ck, placeholder_text="נתיב לקובץ cookies.txt (אופציונלי)...",
            height=34, font=ctk.CTkFont(size=11),
            fg_color=C["input"], border_color=C["border"],
        )
        if self.cfg["cookies_file"]:
            self._ck_entry.insert(0, self.cfg["cookies_file"])
        self._ck_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._ck_entry.bind("<FocusOut>",
            lambda e: self.cfg.__setitem__("cookies_file", self._ck_entry.get().strip()))

        btn(row_ck, "בחר", self._browse_cookies, width=60, height=34,
            ghost=True).grid(row=0, column=1, padx=(0, 8))
        btn(row_ck, "נקה", lambda: (self._ck_entry.delete(0,"end"),
                                     self.cfg.__setitem__("cookies_file","")),
            width=60, height=34, ghost=True).grid(row=0, column=2)

        # ── אודות ──
        c4 = card(root)
        c4.grid(row=r, column=0, sticky="ew", pady=(0, 24)); r += 1
        c4.grid_columnconfigure(0, weight=1)
        label(c4, "ℹ  אודות", size=14, bold=True).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 4))
        label(c4,
              f"YouTube Downloader Pro  v{APP_VER}\n"
              f"yt-dlp: {yt_dlp.version.__version__}\n"
              f"Python: {sys.version.split()[0]}",
              size=11, color=C["txt2"], justify="left").grid(
            row=1, column=0, sticky="w", padx=16, pady=(0, 10))

        btn(c4, "🔄 עדכן yt-dlp", self._update_ytdlp,
            width=160, color=C["blue"]).grid(
            row=2, column=0, sticky="w", padx=16, pady=(0, 16))

        return root

    # ══════════════════════════════════════════════════════════════
    #  לוגיקה — עמוד הורדה
    # ══════════════════════════════════════════════════════════════

    def _paste(self):
        try:
            txt = self.clipboard_get().strip()
            self._url.delete(0, "end")
            self._url.insert(0, txt)
            self._on_url_key(None)
        except Exception:
            pass

    def _on_url_key(self, _):
        url  = self._url.get().strip()
        kind = self.dl.detect_type(url)
        icons = {
            "video":              ("🎬 סרטון",           C["green"]),
            "playlist":           ("📋 פלייליסט",        C["orange"]),
            "channel":            ("📺 ערוץ שלם",        "#9B59B6"),
            "video_in_playlist":  ("🎬 סרטון בפלייליסט", C["green"]),
            "unknown":            ("❓ לא זוהה",          C["txt3"]),
            "empty":              ("",                    C["txt3"]),
        }
        txt, col = icons.get(kind, ("", C["txt3"]))
        # סמן אם זוהה כשמע )YouTube Music( במצב אוטומטי
        if txt and self._dlW["mode"].get() == "auto" and detect_mode(url) == MODE_AUDIO:
            txt += "  ·  🎵 שמע"
        self._url_badge.configure(text=txt, text_color=col)
        # עדכן את תצוגת הווידאו/שמע לפי הזיהוי האוטומטי
        if hasattr(self, "_dlW"):
            self._sync_mode_view(self._dlW)

    def _detect(self):
        url = self._url.get().strip()
        if not url:
            messagebox.showwarning("אין כתובת", "הדבק כתובת YouTube קודם.")
            return
        self._url_badge.configure(text="🔍 טוען מידע...", text_color=C["orange"])
        self.update_idletasks()

        def fetch():
            ok, info = self.dl.fetch_info(url)
            if ok:
                title   = info.get("title", "לא ידוע")
                entries = info.get("entries")
                if entries:
                    cnt = len(list(entries)) if hasattr(entries, "__len__") else "?"
                    msg = f"📋 {cnt} סרטונים · {title}"
                else:
                    dur  = info.get("duration", 0) or 0
                    m, s = divmod(int(dur), 60)
                    msg  = f"🎬 {title}  ({m}:{s:02d})"
                self.after(0, lambda: self._url_badge.configure(
                    text=msg[:90], text_color=C["green"]))
            else:
                self.after(0, lambda: self._url_badge.configure(
                    text="❌ לא ניתן לטעון מידע", text_color=C["error"]))

        threading.Thread(target=fetch, daemon=True).start()

    def _browse(self):
        d = filedialog.askdirectory(title="בחר תיקיית שמירה",
                                    initialdir=self._path_entry.get())
        if d:
            self._path_entry.delete(0, "end")
            self._path_entry.insert(0, d)

    def _start(self):
        url = self._url.get().strip()
        if not url:
            messagebox.showwarning("אין כתובת", "הדבק כתובת YouTube.")
            return
        if not url.startswith("http"):
            messagebox.showwarning("כתובת לא תקינה", "יש להזין כתובת URL תקינה.")
            return

        opts = self._opts_from_W(self._dlW, url)
        item = DLItem(url, opts)

        self._no_dl_lbl.grid_remove()
        pc = ProgressCard(self._prog_area, item)
        pc.grid(row=self._card_row, column=0, sticky="ew", pady=(0, 8))
        self._card_row += 1
        self._cards[id(item)] = pc

        self.dl.start(item,
                      on_progress=lambda i: self._q.put(i),
                      on_done=lambda i: self._q.put(i),
                      on_error=lambda i: self._q.put(("err", i)))

    # ══════════════════════════════════════════════════════════════
    #  עמוד הגדרות — handlers
    # ══════════════════════════════════════════════════════════════

    def _toggle_cookies(self):
        self.cfg["use_cookies"] = self._cookies_sw.get() == 1

    def _save_browser(self, v):
        self.cfg["browser"] = v

    def _browse_cookies(self):
        p = filedialog.askopenfilename(
            title="בחר קובץ cookies.txt",
            filetypes=[("Cookies", "*.txt"), ("כל הקבצים", "*.*")])
        if p:
            self._ck_entry.delete(0, "end")
            self._ck_entry.insert(0, p)
            self.cfg["cookies_file"] = p

    def _update_ytdlp(self):
        def go():
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                capture_output=True, text=True)
            msg = ("yt-dlp עודכן בהצלחה!" if r.returncode == 0
                   else f"שגיאה:\n{r.stderr[:400]}")
            self.after(0, lambda: messagebox.showinfo("עדכון", msg))
        threading.Thread(target=go, daemon=True).start()

    # ══════════════════════════════════════════════════════════════
    #  לולאת UI
    # ══════════════════════════════════════════════════════════════

    def _tick(self):
        try:
            while not self._q.empty():
                data = self._q.get_nowait()
                if isinstance(data, tuple) and data[0] == "err":
                    item = data[1]
                    pc   = self._cards.get(id(item))
                    if pc:
                        pc.update(item)
                    self.after(50, lambda i=item: self._show_error(i))
                else:
                    item = data
                    pc   = self._cards.get(id(item))
                    if pc:
                        pc.update(item)
        except Exception:
            pass
        self.after(80, self._tick)

    def _show_error(self, item: DLItem):
        url_short = item.url[:55] + "..." if len(item.url) > 55 else item.url
        messagebox.showerror("שגיאת הורדה",
                             f"כתובת:\n{url_short}\n\n{item.error}")

    def _check_ffmpeg(self):
        fp = find_ffmpeg()
        if fp is None:
            self._lbl_ffmpeg.configure(text="⚠ FFmpeg לא נמצא", text_color=C["orange"])
        else:
            try:
                ver = subprocess.run(
                    [fp, "-version"], capture_output=True, text=True
                ).stdout.split("\n")[0].replace("ffmpeg version ", "ffmpeg ")
            except Exception:
                ver = "ffmpeg"
            self._lbl_ffmpeg.configure(
                text=f"● {ver[:30]}", text_color=C["green"])


# ══════════════════════════════════════════════════════════════════
#  נקודת כניסה
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = App()
    app.mainloop()
