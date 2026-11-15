@echo off
setlocal
pushd "%~dp0" || exit /b 1
where pyw.exe >nul 2>nul
if not errorlevel 1 (
    set "check=py -3"
    set "gui=pyw -3"
) else (
    where pythonw.exe >nul 2>nul
    if errorlevel 1 goto :setup
    set "check=python"
    set "gui=pythonw"
)
%check% -B -c "import tkinter" >nul 2>nul
if errorlevel 1 goto :setup
start "" %gui% -B "app\mvgl_tools_gui.py"
exit /b

:setup
echo Install Windows Python 3, then run this command from the Studio folder:
echo     py -m pip install -r dependencies\requirements.txt
pause
exit /b 1
