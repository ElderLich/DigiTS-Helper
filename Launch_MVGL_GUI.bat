@echo off
cd /d "%~dp0"
title MVGL Tools GUI Launcher
echo Starting MVGL Tools GUI...
echo.

REM Try to run with python
python MVGL_Tools_GUI.py

REM If python command fails, try py
if errorlevel 1 (
    py MVGL_Tools_GUI.py
)

REM If both fail, show error
if errorlevel 1 (
    echo.
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.6 or higher from python.org
    echo.
    pause
)
