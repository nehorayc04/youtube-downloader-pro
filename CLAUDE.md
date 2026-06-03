# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture (native window + web UI, one engine)

The project is **a native-window web app sharing one download engine**:
- **`app.py` — the primary app (pywebview: native window via WebView2 + HTML/CSS/JS in `web/`).** This is what `פתיחה.bat` and the build launch. NOT Eel/Chrome anymore — pywebview gives a real native window (own title bar + icon, no browser chrome) using the Edge **WebView2** runtime built into Win11 (no external browser). Looks like the Game-translator web app: code-generated starfield (`web/starfield.js`), glassmorphism, neon. `app.py` exposes an `Api` class via `js_api=`; the download daemon thread pushes progress with `_window.evaluate_js("window.on_progress(...)")`. It **imports** `Config`/`Downloader`/`DLItem`/`detect_mode`/constants from `youtube_downloader.py`.
- **`youtube_downloader.py` — the legacy CustomTkinter UI + the shared engine library.** Still runnable standalone, but its real job is to hold `Config`/`Downloader`/`DLItem` + option constants that `app.py` reuses. Edit download logic HERE.

`web/`: `icons.js` (unified feather-style SVG set + `ic(name)` / `injectIcons()` — NO emojis anywhere; `data-icon="name"` on static HTML, `ic('name')` in dynamic JS), a custom glassmorphic dropdown (`.dd`/`ddHtml`/`wireDropdown`) replaces native `<select>` (which rendered white-on-white text in WebView2); `index.html` (shell, no `/eel.js`), `style.css` (glass; `body` MUST stay `background:transparent` or starfield is hidden), `app.js` (UI logic; an `eel`→`window.pywebview.api` Proxy shim at the top maps the old `eel.fn()()` calls — init runs on the `pywebviewready` event, not DOMContentLoaded), `starfield.js` (animated bg, mouse removed, FPS-adaptive `quality` scalar so it stays smooth — don't reintroduce uncapped density or the loose `dt` clamp).

## Running the App

```bash
python app.py
# or via the batch launcher:
פתיחה.bat
```

The app auto-installs all missing Python packages on first run — no manual `pip install` needed before launch.

## Building the EXE + Installer

```bat
build_exe.bat          REM -> dist\YouTube Downloader Pro.exe  (onefile, self-contained)
build_installer.bat    REM -> installer_output\YouTubeDownloaderPro_Setup_v2.0.exe
```

`build_exe.bat` bundles **everything** into one exe: Python runtime, all libs, the app icon, and **ffmpeg** (auto-copied from `where ffmpeg` into `assets\ffmpeg.exe` if present). `build_installer.bat` wraps that exe in an Inno Setup installer (Hebrew+English, desktop/start-menu shortcuts); it auto-installs Inno Setup via winget if missing. Build artifacts: `YouTubeDownloaderPro.spec`, `assets\icon.ico`.

## Verifying a Change

```bash
python -c "import ast; ast.parse(open('youtube_downloader.py', encoding='utf-8').read()); print('syntax OK')"
```

There are no automated tests. Verification is done by launching the app and exercising the feature manually.

## Architecture — Single-File App

Everything lives in `youtube_downloader.py`. The execution order at the top of the file is intentional: dependency installation runs **before** any imports that require those packages.

### Class responsibilities

| Class | Role |
|---|---|
| `Config` | Persistent JSON settings in `~/.yt_downloader_pro/config.json`. Every `__setitem__` auto-saves. |
| `GDriveManager` | OAuth2 token lifecycle (pickle at `~/.yt_downloader_pro/gdrive_token.pkl`). `connect()` tries saved token first, then refreshes, then opens browser OAuth. |
| `DLItem` | Plain data object for one download job — status string drives UI card colour. |
| `Downloader` | Wraps yt-dlp in a daemon thread. `_build_opts()` assembles the yt-dlp dict; `_run()` executes it and optionally uploads to Drive. |
| `ProgressCard` | A `CTkFrame` that renders one `DLItem`. Updated from the main thread via `App._tick()`. |
| `App` | `ctk.CTk` root. Three pages (`_page_download`, `_page_queue`, `_page_settings`) are built once and shown/hidden with `.grid()` / `.grid_remove()`. |

### Thread safety model

Background threads (downloads, Drive upload, auto-connect) must **never** call Tk methods directly. They enqueue a `DLItem` reference onto `App._q` (a `queue.Queue`). `App._tick()` drains the queue every 80 ms via `self.after(80, self._tick)` and calls `ProgressCard.update()` on the main thread.

### Cookie fallback chain

`Downloader._run()` iterates through browsers when `cookiesfrombrowser` fails:

```
configured browser → all _BROWSER_FALLBACKS → None (no cookies)
```

Any exception whose message contains `"cookie"` is treated as a cookie error and triggers the next attempt. Non-cookie exceptions abort immediately.

### Google Drive "direct" mode

When `use_gdrive=True`, `_run()` redirects `outtmpl` to a `tempfile.mkdtemp()` directory instead of the user's Downloads folder. After upload the temp directory is deleted with `shutil.rmtree` — including on error paths. The user's disk is never permanently written to.

### yt-dlp format strings

`QUALITIES` (index 0–9) maps UI labels to yt-dlp format selectors. Indices 8–9 are audio-only (`is_audio = qi >= 8`). Tiers: 0=Best, 1=8K, 2=4K, 3=1440p, 4=1080p, 5=720p, 6=480p, 7=360p, 8=MP3, 9=M4A.

Format strings use bare `bv*+ba/b` with an optional `[height<=N]` cap — **no codec filter in the format string**. Codec preference lives in `_build_opts` as `format_sort = ["res", "fps", "vbr", "abr", "vcodec:av01:vp9:avc1"]` so resolution wins over codec; H.264 is only the tie-breaker. This is what lets "Best" actually pick 4K VP9 / 8K AV1 instead of silently capping at 1080p H.264.

`merge_output_format = "mp4/mkv"` — yt-dlp picks MP4 when codecs allow, falls back to MKV for VP9/AV1+Opus. Both are accepted by `_resolve_final_file` and the Drive uploader MIME map.

**`player_client` is set to `["default", "android"]` — additive, NOT a restriction.** `default` keeps the full format range (4K/8K verified). `android` is appended as a fallback so DRM-protected / region-or-age-limited videos that the default clients mark "This video is not available" / "Requested format is not available" / "DRM protected" still download (verified: yzTErcf5W3M failed on web/ios/tv but worked via android). Do NOT replace `default` with a fixed client list — that *would* cap formats. Only ever append clients.

## Known Constraints

- **Chrome/Edge cookies locked**: Chrome 127+ App-Bound Encryption prevents yt-dlp from reading the cookie DB while the browser is running. The reliable workaround is a `cookies.txt` file (export with "Get cookies.txt LOCALLY" extension). The path is stored in `cfg["cookies_file"]` and takes priority over browser cookies.
- **Google Drive OAuth**: The app is registered as `MyUploader2026`. Only accounts added as *Test users* in Google Cloud Console → OAuth consent screen can authenticate. The `client_secret_...json` file in the project root is the OAuth credential.
- **FFmpeg required** for all video merging (separate video+audio streams). FFmpeg is already installed via winget on this machine.
- **No playlist/channel progress counter**: `DLItem.video_num / video_total` fields exist but are not yet populated — yt-dlp playlist hooks are not wired up.
- **Config is portable across machines**: `Config._sanitize_paths()` runs on load. If `download_path` doesn't exist (e.g. an old config copied from another PC with a different username) it resets to `~/Downloads`; a missing `cookies_file` is cleared. `_build_opts` also `os.makedirs(out_path)` before downloading, falling back to `~/Downloads`. This prevents the "download fails silently" symptom when the JSON config carries a stale absolute path.

## Visual Style (glass / Game-translator look)

- **Palette** lives in the `C` dict: deep navy/purple canvas (`#050510`), glass panels (`#101024`), neon-yellow accent (`#FFF700`). Yellow buttons MUST use `text_color=C["on_accent"]` (dark) for contrast — applies to `_dl_btn` and the active nav item in `_show`.
- **Real blur**: `App._apply_glass()` applies Windows **Mica** (build ≥ 22000) / **Acrylic** via `pywinstyles`, plus a dark title bar. Called 120 ms after window draw to avoid flicker; fails silently off-Windows. The blur shows on the window frame/title bar, not behind the opaque content panels (CustomTkinter can't do per-widget alpha).
- **Font**: `ctk.ThemeManager.theme["CTkFont"]["family"] = "Segoe UI"` set once in `App.__init__` — changes every widget globally.

## 1080p לסרטונים מוגבלים — נפתר! (PO token + node + tv_embedded)

סרטונים מסוימים (תוכן ילדים מסחרי, למשל `5wF1G3ft-0U`) הוגבלו ל-360p. **נפתר 2026-06-04** — מורידים אותם במלואם ב-1080p, בדיוק כמו YTDLnis. המסקנה הישנה ("בלתי אפשרי ב-desktop / SABR") הייתה **שגויה**. שלושה רכיבים נדרשים יחד:

1. **PO Token** — נוצר ב-`pot_provider.py` דרך **WebView2** (Edge, ב-pywebview). Python מבצע את ה-HTTP (`youtubei/v1/att/get` → bgChallenge; `jnn-pa.googleapis.com/$rpc/.../GenerateIT` עם `["O43z0dpjhgX20SCx4KAo", botguardResponse]`), ו-WebView2 מריץ את ה-BotGuard JS (`runBotGuard`+`obtainPoToken` מתוך `po_token.html` של ה-APK). **קריטי: ה-WebView חייב לטעון origin אמיתי `https://www.youtube.com`** — ב-about:blank ה-attestation נכשל (integrityToken=null, webPoSignalOutput ריק). אין צורך ב-Node/npm ליצירה — ה-DOM של Edge עובר את ה-anti-bot. ה-token bound ל-visitor_data; מעבירים את אותו visitor_data ל-yt-dlp. cache ב-`~/.yt_downloader_pro/pot_cache.json` עם TTL.
2. **node + yt-dlp-ejs** — לפתרון ה-**n-signature challenge** (נפרד מ-PO token!). חובה `js_runtimes={'node':{'path':...}}` ב-opts. בלעדיו: "n challenge solving failed" → רק storyboards. `find_node()`/`ensure_node()` מאתרים/מורידים node portable אם חסר.
3. **client = `tv_embedded`** (לא web/mweb!). web נכפה ל-SABR (360p). mweb DASH מקבל 403 אחרי ~9.6MB (SABR throttling client-specific). tv_embedded → URLs יציבים → הורדה מלאה.

`_build_opts` מייצר: `player_client=['tv_embedded','web_embedded','mweb']`, `po_token=[f'{c}.gvs+{tok}' ...]`, `visitor_data=[...]`, `js_runtimes={'node':...}`. אם אין token → נופל ל-`['default','android']` (360p legacy). הוכח: הורדת 186MB מלאה ב-1920x1080 של הסרטון המוגבל, וגם רגיל (regression OK).

**מצב frozen exe:** `pot_provider` רץ כ-subprocess (`exe --pot-mode --out=...`) כי webview דורש main-thread משלו. תיקונים קריטיים שהתגלו: (א) `console=False` → `sys.stdout/stderr=None` → כל print מפיל; ממירים ל-devnull. (ב) לולאת התקנת התלויות חייבת לדלג ב-frozen — אחרת `_pip` מריץ `exe -m pip` שפותח UI ותוקע. (ג) **`bottle` חייב להיכלל** (webview.http מייבא אותו) — הוסר מ-`excludes` ונוסף ל-hiddenimports. (ד) `yt_dlp_ejs` ב-collect_all שב-spec.

## עדכון עצמי (updater.py) — לפי SHA-256, דרך GitHub

`updater.py`: בודק `update.json` ב-raw.githubusercontent (cache-busting), משווה SHA-256 של ה-exe הרץ מול ה-manifest (לא לפי מספר גרסה), מוריד+מאמת+מחליף דרך **VBScript trampoline** (עוקף נעילת exe בריצה). repo: `nehorayc04/youtube-downloader-pro`. `publish.py` מייצר את ה-manifest ומעלה release דרך gh.

## History

- 2026-06-04 — **1080p לסרטונים מוגבלים — נפתר (סותר את 2026-06-03)!** המסקנה "בלתי אפשרי/SABR" הייתה שגויה. הפתרון: PO token דרך WebView2 (`pot_provider.py`, BotGuard על origin youtube.com אמיתי) + node/yt-dlp-ejs ל-n-challenge + client `tv_embedded`. הוכח: הורדת 186MB מלאה ב-1920x1080. שולב ב-`_build_opts` (get_po_token/find_node/ensure_node). נוסף **עדכון עצמי** (`updater.py`, SHA-256 + VBScript trampoline, repo `nehorayc04/youtube-downloader-pro`) + UI בהגדרות + `publish.py`. נבנה exe (37MB); תוקנו באגי frozen: stdout=None→devnull, דילוג deps-loop ב-frozen, **bottle הוחזר ל-build** (webview.http), yt_dlp_ejs ב-collect. כל הרכיבים אומתו ב-frozen (_MEI). ראה section "1080p לסרטונים מוגבלים".
- 2026-06-03 — **PO Token / SABR investigation → removed.** User showed YTDLnis downloads restricted videos at 1080p; decompiled its APK (BotGuard PO token, not DRM), implemented + tested both bgutil providers (jim60105 Rust binary, Brainicism Node server). Token generates & is accepted, but yt-dlp 2026.03.17's web client returns SABR/storyboards-only even for normal videos — undownloadable. YTDLnis works only via real Android device attestation. Reverted to `player_client=['default','android']`. See "PO Token / SABR" section. UI redesign (dropdowns/icons/sidebar) from this session is kept.
- 2026-06-03 — **(superseded) PO Token support** for full-resolution downloads of attestation-gated videos (the YTDLnis 1080p behavior). Legitimate (BotGuard attestation, not DRM — verified by decompiling YTDLnis's APK). Added provider lifecycle + `pot_available()`-gated `web` client in `_build_opts`, bgutil plugin in `REQUIRED`, spec collect_submodules. Engine-only change → both UIs benefit. `assets/bgutil-pot.exe` downloaded separately by the user.
- 2026-06-03 — **Switched from Eel to pywebview** (native window) after the user said Eel's external-Chrome window "feels disjointed" and wanted it like the Game-translator launcher (which is PySide6+QtWebEngine). Chose pywebview over QtWebEngine — same native feel via the built-in WebView2 runtime, ~3-5× smaller bundle, no gevent/Qt event-loop fight. `app.py` rewritten: `Api` class + `evaluate_js` push; `web/index.html` drops `/eel.js`; `web/app.js` gets an `eel`→pywebview Proxy shim + `pywebviewready` init. Also fixed the "choppy" starfield (workflow-researched): capped densities, smoothed+clamped `dt`, FPS-adaptive `quality` scalar gating flares/elongation/nebula, time-gated nebula rebake, `desynchronized:true`. Verified: native window opens (title+icon, no browser chrome), smooth starfield, backend download start→done.
- 2026-06-03 — **Rewrote UI to Eel** (`app.py` + `web/`) for a Game-translator-grade look the user asked for: code-generated starfield bg (ported from `website/src/components/StarfieldBackground.tsx`, mouse steering removed), full glassmorphism, neon. Download engine stays in `youtube_downloader.py` (imported). Verified: app launches in Chrome app-mode, starfield renders, a real download runs start→done through the Eel API. Build (`.spec`, `build_exe.bat`) updated to bundle `web/` + eel. `body{background}` MUST stay transparent or the starfield canvas is hidden.
- 2026-06-03 — Pre-Eel feature work (all in `youtube_downloader.py`, still the engine): removed all Google Drive code; added video/audio mode with auto-detect (YT Music→audio), video-only, rich per-download options (thumbnail/chapters/subs/SponsorBlock/re-encode/live/filename-template/extra-args/trim/bitrate/split-chapters) shown both pre-download and in settings as defaults; pause/cancel via `threading.Event` in the progress hook; DRM warning when downloaded height ≪ requested.
- 2026-06-03 — Glass redesign + packaging: navy/neon palette, Windows Mica blur (`pywinstyles`), Segoe UI, neon play-button icon (`assets\icon.ico`), bundled-ffmpeg support (`find_ffmpeg()`), `resource_path()` for PyInstaller. Added `YouTubeDownloaderPro.spec`, `build_exe.bat` (onefile, self-contained), `installer.iss` + `build_installer.bat` (Inno Setup).
- 2026-06-03 — Fixed downloads failing: user's `config.json` had `download_path = C:\Users\nc528\Downloads` from a previous machine (current user is `Nehoray_Cohen`), so yt-dlp couldn't write the output. Added `Config._sanitize_paths()` + `os.makedirs` in `_build_opts` to make the app universal across machines. Verified yt-dlp 2026.03.17, ffmpeg, and a full download (chrome cookies locked → falls back to edge → MKV merge) all work.
