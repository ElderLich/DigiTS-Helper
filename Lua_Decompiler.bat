@echo off
cd /d "%~dp0"
title Lua Decompiler - DTS Creator
python Lua_Decompiler_GUI.py
if errorlevel 1 (
    echo.
    echo Press any key to exit...
    pause >nul
)
