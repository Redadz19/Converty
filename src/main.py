import os
import sys
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QProgressBar, QLineEdit, QMessageBox, QFrame
)

APP_VERSION = "2.0.0"


def locate_ghostscript():
    candidates = [
        os.environ.get("GHOSTSCRIPT_EXE"),
        shutil.which("gswin64c"),
        shutil.which("gswin32c"),
        shutil.which("gs"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


class FileTable(QTableWidget):
    dropped = Signal(list)

    def __init__(self):
        super().__init__(0, 4)
        self.setHorizontalHeaderLabels(["EPS file", "Size", "Status", "PDF output"])
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.setAcceptDrops(True)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.verticalHeader().hide()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        self.dropped.emit([url.toLocalFile() for url in event.mimeData().urls()])
        event.acceptProposedAction()


class ConversionWorker(QThread):
    file_status = Signal(int, str, str)
    progress_changed = Signal(int)
    completed = Signal()

    def __init__(self, jobs, gs, dpi, page_mode, color_mode):
        super().__init__()
        self.jobs = jobs
        self.gs = gs
        self.dpi = dpi
        self.page_mode = page_mode
        self.color_mode = color_mode

    def run(self):
        total = len(self.jobs)
        for index, (source, target) in enumerate(self.jobs):
            self.file_status.emit(index, "Converting", "")
            command = [
                self.gs, "-dSAFER", "-dBATCH", "-dNOPAUSE",
                "-sDEVICE=pdfwrite", f"-r{self.dpi}",
                "-dEPSCrop", "-dEmbedAllFonts=true", "-dSubsetFonts=true",
                "-dAutoRotatePages=/None", f"-sOutputFile={target}",
            ]
            if self.page_mode in ("A4", "A3"):
                command += ["-dFIXEDMEDIA", "-dPDFFitPage", f"-sPAPERSIZE={self.page_mode.lower()}"]
            if self.color_mode in ("RGB", "CMYK"):
                command.append(f"-sColorConversionStrategy={self.color_mode}")
                command.append("-dProcessColorModel=/DeviceRGB" if self.color_mode == "RGB" else "-dProcessColorModel=/DeviceCMYK")
            elif self.color_mode == "Grayscale":
                command += ["-sColorConversionStrategy=Gray", "-dProcessColorModel=/DeviceGray"]
            command.append(str(source))
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=300)
                if result.returncode == 0 and target.exists() and target.stat().st_size > 0:
                    self.file_status.emit(index, "Completed", str(target))
                else:
                    detail = (result.stderr or result.stdout or "Ghostscript returned an error").strip()
                    self.file_status.emit(index, "Failed", detail[-350:])
            except subprocess.TimeoutExpired:
                self.file_status.emit(index, "Failed", "Timed out after 5 minutes")
            except Exception as exc:
                self.file_status.emit(index, "Failed", str(exc))
            self.progress_changed.emit(round((index + 1) * 100 / total))
        self.completed.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"EPS to PDF PRO  {APP_VERSION}")
        self.resize(1120, 760)
        self.files = []
        self.worker = None
        self.ghostscript = locate_ghostscript()
        self.output_dir = Path.home() / "Documents" / "EPS-PDF-Output"
        self.language = "en"
        self._build_ui()
        self._apply_theme()
        self._translate()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(15)

        header = QHBoxLayout()
        brand = QVBoxLayout()
        self.title = QLabel("EPS to PDF PRO")
        self.title.setObjectName("title")
        self.subtitle = QLabel("Professional EPS conversion workspace")
        self.subtitle.setObjectName("muted")
        brand.addWidget(self.title)
        brand.addWidget(self.subtitle)
        header.addLayout(brand)
        header.addStretch()
        self.language_button = QPushButton("العربية")
        self.language_button.clicked.connect(self.toggle_language)
        header.addWidget(self.language_button)
        root.addLayout(header)

        self.drop_panel = QFrame()
        self.drop_panel.setObjectName("dropPanel")
        drop = QVBoxLayout(self.drop_panel)
        drop.setContentsMargins(22, 22, 22, 22)
        self.drop_title = QLabel()
        self.drop_title.setObjectName("dropTitle")
        self.drop_title.setAlignment(Qt.AlignCenter)
        self.drop_hint = QLabel()
        self.drop_hint.setObjectName("muted")
        self.drop_hint.setAlignment(Qt.AlignCenter)
        actions = QHBoxLayout()
        actions.addStretch()
        self.add_files_button = QPushButton()
        self.add_files_button.clicked.connect(self.add_files)
        self.add_folder_button = QPushButton()
        self.add_folder_button.clicked.connect(self.add_folder)
        actions.addWidget(self.add_files_button)
        actions.addWidget(self.add_folder_button)
        actions.addStretch()
        drop.addWidget(self.drop_title)
        drop.addWidget(self.drop_hint)
        drop.addSpacing(8)
        drop.addLayout(actions)
        root.addWidget(self.drop_panel)

        self.table = FileTable()
        self.table.dropped.connect(self.add_paths)
        root.addWidget(self.table, 1)

        settings = QFrame()
        settings.setObjectName("settings")
        settings_layout = QHBoxLayout(settings)
        settings_layout.setContentsMargins(14, 10, 14, 10)
        self.quality = QComboBox()
        self.quality.addItems(["150 DPI", "300 DPI", "600 DPI"])
        self.quality.setCurrentText("300 DPI")
        self.page = QComboBox()
        self.page.addItems(["EPS original size", "A4", "A3"])
        self.color = QComboBox()
        self.color.addItems(["Preserve", "RGB", "CMYK", "Grayscale"])
        for caption, widget in (("Quality", self.quality), ("Page size", self.page), ("Color mode", self.color)):
            column = QVBoxLayout()
            label = QLabel(caption)
            label.setObjectName("muted")
            column.addWidget(label)
            column.addWidget(widget)
            settings_layout.addLayout(column)
        root.addWidget(settings)

        output_row = QHBoxLayout()
        self.output_label = QLabel("Output")
        self.output_path = QLineEdit(str(self.output_dir))
        self.output_path.setReadOnly(True)
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.choose_output)
        output_row.addWidget(self.output_label)
        output_row.addWidget(self.output_path, 1)
        output_row.addWidget(self.browse_button)
        root.addLayout(output_row)

        footer = QHBoxLayout()
        self.status = QLabel("Ready")
        self.status.setObjectName("muted")
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.clear_button = QPushButton("Clear list")
        self.clear_button.clicked.connect(self.clear_list)
        self.convert_button = QPushButton("Convert to PDF  →")
        self.convert_button.setObjectName("primary")
        self.convert_button.clicked.connect(self.start_conversion)
        footer.addWidget(self.status)
        footer.addStretch()
        footer.addWidget(self.clear_button)
        footer.addWidget(self.convert_button)
        root.addLayout(footer)
        root.addWidget(self.progress)

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background:#0b1220; color:#e8eef8; font-family:'Segoe UI'; font-size:10pt; }
            QLabel#title { font-size:25pt; font-weight:700; color:#f8fbff; }
            QLabel#muted { color:#91a2bb; }
            QLabel#dropTitle { font-size:17pt; font-weight:650; color:#f1f6ff; }
            QFrame#dropPanel { background:#111d31; border:2px dashed #365a86; border-radius:18px; }
            QFrame#settings { background:#111d31; border:1px solid #263b59; border-radius:14px; }
            QTableWidget { background:#101a2b; alternate-background-color:#142238; border:1px solid #263b59; border-radius:12px; gridline-color:#263b59; }
            QHeaderView::section { background:#1a2a42; color:#a9bdd8; padding:10px; border:0; font-weight:600; }
            QLineEdit, QComboBox { background:#17263c; border:1px solid #304766; border-radius:8px; padding:9px; color:#edf4ff; }
            QPushButton { background:#1b2d47; border:1px solid #385477; border-radius:9px; padding:10px 16px; color:#edf4ff; font-weight:600; }
            QPushButton:hover { background:#294365; }
            QPushButton#primary { background:#3478f6; border:0; color:white; padding:12px 22px; }
            QPushButton#primary:hover { background:#4b8aff; }
            QProgressBar { background:#17263c; border:0; border-radius:6px; height:10px; text-align:center; }
            QProgressBar::chunk { background:#3478f6; border-radius:6px; }
        """)

    def _translate(self):
        arabic = self.language == "ar"
        self.setLayoutDirection(Qt.RightToLeft if arabic else Qt.LeftToRight)
        if arabic:
            self.subtitle.setText("مساحة احترافية لتحويل ملفات EPS")
            self.drop_title.setText("أفلت ملفات EPS أو المجلدات هنا")
            self.drop_hint.setText("يمكنك إضافة ملفات منفردة أو فحص المجلدات الفرعية")
            self.add_files_button.setText("＋ إضافة ملفات")
            self.add_folder_button.setText("▣ إضافة مجلد")
            self.language_button.setText("English")
            self.output_label.setText("مجلد الإخراج")
            self.browse_button.setText("استعراض")
            self.clear_button.setText("مسح القائمة")
            self.convert_button.setText("تحويل إلى PDF  ←")
            self.status.setText("جاهز")
        else:
            self.subtitle.setText("Professional EPS conversion workspace")
            self.drop_title.setText("Drop EPS files or folders here")
            self.drop_hint.setText("Add individual files or scan folders including subfolders")
            self.add_files_button.setText("＋ Add files")
            self.add_folder_button.setText("▣ Add folder")
            self.language_button.setText("العربية")
            self.output_label.setText("Output")
            self.browse_button.setText("Browse")
            self.clear_button.setText("Clear list")
            self.convert_button.setText("Convert to PDF  →")
            self.status.setText("Ready")

    def toggle_language(self):
        self.language = "ar" if self.language == "en" else "en"
        self._translate()

    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select EPS files", "", "EPS files (*.eps *.epsf);;All files (*.*)")
        self.add_paths(paths)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select folder")
        if folder:
            self.add_paths([folder])

    def add_paths(self, paths):
        discovered = []
        for raw in paths:
            path = Path(raw)
            if path.is_dir():
                discovered.extend(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in (".eps", ".epsf"))
            elif path.is_file() and path.suffix.lower() in (".eps", ".epsf"):
                discovered.append(path)
        known = {str(p).casefold() for p in self.files}
        for path in discovered:
            if str(path).casefold() in known:
                continue
            self.files.append(path)
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(path.name))
            self.table.setItem(row, 1, QTableWidgetItem(f"{path.stat().st_size / 1024:.1f} KB"))
            self.table.setItem(row, 2, QTableWidgetItem("Queued"))
            self.table.setItem(row, 3, QTableWidgetItem(""))
            known.add(str(path).casefold())
        self.status.setText(f"{len(self.files)} EPS file(s) queued")

    def choose_output(self):
        selected = QFileDialog.getExistingDirectory(self, "Choose output folder", str(self.output_dir))
        if selected:
            self.output_dir = Path(selected)
            self.output_path.setText(selected)

    def clear_list(self):
        if self.worker and self.worker.isRunning():
            return
        self.files.clear()
        self.table.setRowCount(0)
        self.progress.setValue(0)
        self.status.setText("Ready")

    def start_conversion(self):
        if not self.files:
            QMessageBox.information(self, "EPS to PDF PRO", "Add at least one EPS file first.")
            return
        if not self.ghostscript:
            QMessageBox.critical(
                self, "Ghostscript required",
                "Ghostscript was not found. Install 64-bit Ghostscript and add gswin64c.exe to PATH, or set GHOSTSCRIPT_EXE."
            )
            return
        self.output_dir.mkdir(parents=True, exist_ok=True)
        jobs = []
        for source in self.files:
            target = self.output_dir / f"{source.stem}.pdf"
            suffix = 1
            while target.exists():
                target = self.output_dir / f"{source.stem}_{suffix}.pdf"
                suffix += 1
            jobs.append((source, target))
        dpi = self.quality.currentText().split()[0]
        page_mode = self.page.currentText()
        color_mode = self.color.currentText()
        self.convert_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.progress.setValue(0)
        self.worker = ConversionWorker(jobs, self.ghostscript, dpi, page_mode, color_mode)
        self.worker.file_status.connect(self.update_file_status)
        self.worker.progress_changed.connect(self.progress.setValue)
        self.worker.completed.connect(self.conversion_finished)
        self.worker.start()
        self.status.setText("Converting…")

    def update_file_status(self, row, state, detail):
        self.table.item(row, 2).setText(state)
        self.table.item(row, 3).setText(detail)

    def conversion_finished(self):
        self.convert_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        completed = sum(self.table.item(row, 2).text() == "Completed" for row in range(self.table.rowCount()))
        failed = sum(self.table.item(row, 2).text() == "Failed" for row in range(self.table.rowCount()))
        self.status.setText(f"Finished — {completed} completed, {failed} failed")
        QMessageBox.information(
            self, "Conversion finished",
            f"Completed: {completed}\nFailed: {failed}\n\nOutput folder:\n{self.output_dir}"
        )


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("EPS to PDF PRO")
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
