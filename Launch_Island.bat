@echo off
title Zenith OS
cd /d "%~dp0"

echo ===================================================
echo   Zenith OS - Setup ^& Launch
echo ===================================================
echo.

:: 1. Auto-detect real Python executable (bypassing Microsoft Store stub)
set "PYTHON_EXE="

if exist "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
) else if exist "%LOCALAPPDATA%\Python\bin\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Python\bin\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
)

:: If not found in standard paths, look for py launcher or python in PATH
if "%PYTHON_EXE%"=="" (
    where py >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=py"
    ) else (
        set "PYTHON_EXE=python"
    )
)

echo Detected Python: "%PYTHON_EXE%"
echo.

:: Fast dependency check (only invokes pip if a core library is missing)
"%PYTHON_EXE%" -c "import PyQt6, psutil, groq, edge_tts, pygame, sounddevice" >nul 2>nul
if errorlevel 1 (
    echo [1/2] Installing missing requirements...
    "%PYTHON_EXE%" -m pip install -r requirements.txt
)

echo ===================================================
echo   Launching Zenith OS...
echo ===================================================
"%PYTHON_EXE%" main.py
