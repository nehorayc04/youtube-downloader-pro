@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo    YouTube Downloader Pro  -  Build EXE
echo ============================================
echo.

REM --- 1. install build dependencies ---
echo [1/4] Installing build dependencies...
python -m pip install --upgrade pyinstaller -q --disable-pip-version-check
python -m pip install pywebview yt-dlp Pillow customtkinter pywinstyles -q --disable-pip-version-check

REM --- 2. bundle ffmpeg + ffprobe (so the exe is fully self-contained) ---
REM    BOTH are required: EmbedThumbnail / SponsorBlock / chapter-split need ffprobe.
echo [2/4] Bundling ffmpeg + ffprobe...
for /f "delims=" %%i in ('python -c "import shutil;print(shutil.which('ffmpeg') or '')"') do set "FFPATH=%%i"
for /f "delims=" %%i in ('python -c "import shutil;print(shutil.which('ffprobe') or '')"') do set "FPPATH=%%i"
if defined FFPATH (
    copy /y "!FFPATH!" "assets\ffmpeg.exe" >nul
    echo     bundled ffmpeg from: !FFPATH!
) else (
    echo     ffmpeg NOT found - exe will fall back to system ffmpeg at runtime.
    echo     install with:  winget install Gyan.FFmpeg
)
if defined FPPATH (
    copy /y "!FPPATH!" "assets\ffprobe.exe" >nul
    echo     bundled ffprobe from: !FPPATH!
) else (
    echo     ffprobe NOT found - thumbnail/sponsorblock features need it.
)

REM --- 3. build onefile exe ---
echo [3/4] Building exe with PyInstaller...
pyinstaller --noconfirm --clean "YouTubeDownloaderPro.spec"
if errorlevel 1 (
    echo.
    echo BUILD FAILED.
    pause
    exit /b 1
)

REM --- 4. done ---
echo [4/4] Done.
echo.
echo ============================================
echo   EXE ready:  dist\YouTube Downloader Pro.exe
echo ============================================
endlocal
pause
