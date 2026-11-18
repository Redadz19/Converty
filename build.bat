@echo off
setlocal
cd /d "%~dp0"
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
pyinstaller --noconfirm --clean --windowed --name EPS_to_PDF_PRO src\main.py
echo.
echo Build finished. Output: dist\EPS_to_PDF_PRO.exe
pause
