# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — YouTube Downloader Pro )חלון native: pywebview + WebView2(
# בונה exe יחיד עם ה-frontend )web/(, pywebview, מנוע ההורדה, האייקון, ו-ffmpeg.

from PyInstaller.utils.hooks import collect_all

datas = [("web", "web"), ("assets", "assets")]
binaries = []
hiddenimports = [
    "webview.platforms.edgechromium", "clr_loader", "pythonnet",
    "PIL._tkinter_finder",
    # מיובאים lazy )--pot-mode / מתודות API( — PyInstaller לא תופס אוטומטית
    "pot_provider", "updater", "youtube_downloader",
    "bottle",   # webview.http מייבא bottle ברמת המודול — חובה
]

# webview + yt_dlp מלאים; yt_dlp_ejs מכיל את סקריפטי פתרון ה-n-challenge
# )נדרשים ל-1080p(; customtkinter/pywinstyles כי youtube_downloader מייבא.
for pkg in ["webview", "yt_dlp", "yt_dlp_ejs", "customtkinter", "pywinstyles"]:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["eel", "gevent", "greenlet"],   # Eel הוסר; bottle נחוץ ל-webview!
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="YouTube Downloader Pro",
    debug=False, bootloader_ignore_signals=False, strip=False,
    upx=True, upx_exclude=[], runtime_tmpdir=None,
    console=False, disable_windowed_traceback=False,
    argv_emulation=False, target_arch=None,
    codesign_identity=None, entitlements_file=None,
    icon="assets/icon.ico",
)
