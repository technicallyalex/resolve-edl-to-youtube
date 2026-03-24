@echo off
setlocal

cd /d "%~dp0"

python -m pip install --upgrade pyinstaller
if errorlevel 1 goto :error

set "PYTHON_DIR=%LOCALAPPDATA%\Programs\Python\Python314"
set "TCL_DIR=%PYTHON_DIR%\tcl\tcl8.6"
set "TK_DIR=%PYTHON_DIR%\tcl\tk8.6"
set "HOOK_DIR=%~dp0hooks"

python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name ResolveEdlToYouTubeChapters ^
  --additional-hooks-dir "%HOOK_DIR%" ^
  --runtime-hook "%~dp0runtime_tkinter.py" ^
  --hidden-import tkinter ^
  --hidden-import tkinter.ttk ^
  --hidden-import tkinter.filedialog ^
  --hidden-import tkinter.messagebox ^
  --hidden-import _tkinter ^
  --add-data "%TCL_DIR%;_tcl_data" ^
  --add-data "%TK_DIR%;_tk_data" ^
  resolve_edl_to_youtube_gui.py
if errorlevel 1 goto :error

echo.
echo Build complete:
echo %~dp0dist\ResolveEdlToYouTubeChapters.exe
exit /b 0

:error
echo.
echo Build failed.
exit /b 1
