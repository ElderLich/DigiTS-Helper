@echo off
cd /d "%~dp0"
title Lua Decompiler - Time Stranger Mod Studio
python Lua_Decompiler_GUI.py
if errorlevel 1 (
    echo.
    echo Press any key to exit...
    pause >nul
)
