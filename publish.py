# -*- coding: utf-8 -*-
"""
מפרסם גרסה: מחשב SHA-256 + גודל של ה-exe, יוצר update.json )ה-manifest
שה-updater קורא(, ומעלה את ה-exe ל-GitHub Release דרך gh CLI.

הרצה )אחרי build + gh auth login(:
    python publish.py
"""
import os
import sys
import json
import shutil
import hashlib
import subprocess

OWNER   = "nehorayc04"
REPO    = "youtube-downloader-pro"
VERSION = "2.1"
TAG     = f"v{VERSION}"
NOTES   = "גרסה 2.1 — הורדת 1080p לסרטונים מוגבלים )PO token + node( ועדכון עצמי"

EXE   = os.path.join("dist", "YouTube Downloader Pro.exe")
ASSET = "YouTubeDownloaderPro.exe"   # ללא רווחים — URL נקי ל-release
GH    = r"C:\Program Files\GitHub CLI\gh.exe"
if not os.path.exists(GH):
    GH = "gh"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def gh(*args, check=False):
    r = subprocess.run([GH, *args], capture_output=True, text=True, encoding="utf-8")
    if r.stdout: print(r.stdout.strip())
    if r.stderr: print(r.stderr.strip())
    if check and r.returncode != 0:
        sys.exit(f"gh {' '.join(args)} נכשל )code {r.returncode}(")
    return r


def main():
    if not os.path.exists(EXE):
        sys.exit(f"לא נמצא {EXE} — בנה קודם")
    digest = sha256(EXE)
    size = os.path.getsize(EXE)
    download_url = (f"https://github.com/{OWNER}/{REPO}/releases/download/"
                    f"{TAG}/{ASSET}")
    manifest = {
        "version":      VERSION,
        "sha256":       digest,
        "size_bytes":   size,
        "download_url": download_url,
        "notes":        NOTES,
    }
    with open("update.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("update.json נכתב:")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))

    # ── repo )אם לא קיים( ──
    if gh("repo", "view", f"{OWNER}/{REPO}").returncode != 0:
        print("יוצר repo ציבורי...")
        gh("repo", "create", f"{OWNER}/{REPO}", "--public",
           "--description", "YouTube Downloader Pro — הורדת יוטיוב 1080p עם עדכון עצמי",
           check=True)

    # ── release + העלאת ה-exe )שם ללא רווחים( ──
    shutil.copy(EXE, ASSET)
    gh("release", "delete", TAG, "--yes", "--cleanup-tag")   # אם קיים מקודם
    gh("release", "create", TAG, ASSET, "--title", f"v{VERSION}",
       "--notes", NOTES, check=True)
    os.remove(ASSET)
    print(f"\nשוחרר: {download_url}")


if __name__ == "__main__":
    main()
