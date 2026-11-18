# EPS to PDF PRO 2.0

Modern Windows desktop utility for batch conversion of EPS / EPSF files to PDF using Ghostscript.

## Features
- Drag and drop EPS files and folders
- Batch conversion and recursive folder scanning
- Selectable output folder
- PDF rendering quality: 150 / 300 / 600 DPI
- Page sizing: preserve EPS bounding box, A4, A3
- Color handling: preserve, RGB, CMYK, grayscale
- Per-file status, progress and conversion summary
- Arabic / English interface
- About tab with publisher information and website
- In-app update check and one-click EXE replacement from GitHub Releases
- Windows x64 executable built automatically by GitHub Actions

## Requirements
- Windows 10 or 11, 64-bit
- 64-bit Ghostscript installed
- Python 3.11+ for development

## Run from source
```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python src\main.py
```

## Build locally
Run `build.bat`. The executable is generated at `dist\EPS_to_PDF_PRO.exe`.

## GitHub Actions
Every push to main builds a Windows executable and uploads it as an Actions artifact. A push to `main` builds the Windows executable and publishes the `v2.1.0` GitHub Release asset used by the in-app updater.

## Ghostscript
Install Ghostscript x64 and make `gswin64c.exe` available on PATH, or set the `GHOSTSCRIPT_EXE` environment variable to its full path.

## Roadmap
- Installer and signed executable
- Installer and signed executable
- Persistent conversion history and exportable logs
- Advanced EPS compatibility tests
