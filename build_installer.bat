@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo    YouTube Downloader Pro  -  Build Installer
echo ============================================
echo.

REM --- make sure the exe exists (build it if missing) ---
if not exist "dist\YouTube Downloader Pro.exe" (
    echo exe not found - running build_exe.bat first...
    call build_exe.bat
)

REM --- locate the Inno Setup compiler ---
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"

if not defined ISCC (
    echo Inno Setup not found - installing via winget...
    winget install -e --id JRSoftware.InnoSetup --accept-source-agreements --accept-package-agreements
    if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
    if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
)

if not defined ISCC (
    echo.
    echo Could not find ISCC.exe. Install Inno Setup manually:
    echo   https://jrsoftware.org/isdl.php
    pause
    exit /b 1
)

echo Compiling installer with: "%ISCC%"
"%ISCC%" installer.iss
if errorlevel 1 (
    echo INSTALLER BUILD FAILED.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Installer ready in:  installer_output\
echo ============================================
endlocal
pause
