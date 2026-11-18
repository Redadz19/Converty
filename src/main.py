import os
import sys
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QProgressBar, QLineEdit, QMessageBox, QFrame, QAbstractItemView
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
        self.setHorizontalHeaderLabels(["EPS File", "Size", "Status", "PDF Output"])
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.setAcceptDrops(True)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(46)
        self.setShowGrid(True)

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
        self.setWindowTitle(f"EPS to PDF PRO {APP_VERSION}")
        self.setMinimumSize(900, 650)
        self.resize(1180, 820)
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
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # Branded top banner
        self.header_panel = QFrame()
        self.header_panel.setObjectName("headerPanel")
        header = QHBoxLayout(self.header_panel)
        header.setContentsMargins(22, 16, 22, 16)
        self.brand_icon = QLabel()
        self.brand_icon.setObjectName("brandIcon")
        self.brand_icon.setFixedSize(66, 76)
        logo_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
        logo_path = logo_root / "assets" / "waraqa.svg"
        if logo_path.exists():
            renderer = QSvgRenderer(str(logo_path))
            logo_pixmap = QPixmap(66, 76)
            logo_pixmap.fill(Qt.transparent)
            painter = QPainter(logo_pixmap)
            renderer.render(painter)
            painter.end()
            self.brand_icon.setPixmap(logo_pixmap)
        header.addWidget(self.brand_icon)
        brand = QVBoxLayout()
        self.title = QLabel("EPS to PDF PRO")
        self.title.setObjectName("title")
        self.subtitle = QLabel("Professional EPS conversion workspace")
        self.subtitle.setObjectName("subtitle")
        brand.addWidget(self.title)
        brand.addWidget(self.subtitle)
        header.addLayout(brand)
        header.addStretch()
        self.version_badge = QLabel(APP_VERSION)
        self.version_badge.setObjectName("versionBadge")
        header.addWidget(self.version_badge)
        self.language_button = QPushButton("🌐  العربية")
        self.language_button.setObjectName("languageButton")
        self.language_button.clicked.connect(self.toggle_language)
        header.addWidget(self.language_button)
        root.addWidget(self.header_panel)

        # Drop zone
        self.drop_panel = QFrame()
        self.drop_panel.setObjectName("dropPanel")
        drop = QVBoxLayout(self.drop_panel)
        drop.setContentsMargins(20, 18, 20, 18)
        drop.setSpacing(8)
        self.drop_title = QLabel()
        self.drop_title.setObjectName("dropTitle")
        self.drop_title.setAlignment(Qt.AlignCenter)
        self.drop_hint = QLabel()
        self.drop_hint.setObjectName("dropHint")
        self.drop_hint.setAlignment(Qt.AlignCenter)
        actions = QHBoxLayout()
        actions.setSpacing(12)
        actions.addStretch()
        self.add_files_button = QPushButton()
        self.add_files_button.setObjectName("addFiles")
        self.add_files_button.clicked.connect(self.add_files)
        self.add_folder_button = QPushButton()
        self.add_folder_button.setObjectName("addFolder")
        self.add_folder_button.clicked.connect(self.add_folder)
        actions.addWidget(self.add_files_button)
        actions.addWidget(self.add_folder_button)
        actions.addStretch()
        drop.addWidget(self.drop_title)
        drop.addWidget(self.drop_hint)
        drop.addSpacing(4)
        drop.addLayout(actions)
        root.addWidget(self.drop_panel)

        # File queue
        self.table = FileTable()
        self.table.setObjectName("fileTable")
        self.table.dropped.connect(self.add_paths)
        root.addWidget(self.table, 1)

        # Settings panel
        self.settings_panel = QFrame()
        self.settings_panel.setObjectName("settingsPanel")
        settings_outer = QVBoxLayout(self.settings_panel)
        settings_outer.setContentsMargins(18, 12, 18, 14)
        settings_outer.setSpacing(10)
        self.settings_title = QLabel("⚙  Conversion Settings")
        self.settings_title.setObjectName("sectionTitle")
        settings_outer.addWidget(self.settings_title)
        settings_layout = QHBoxLayout()
        settings_layout.setSpacing(18)

        self.quality = QComboBox()
        self.quality.addItems(["150 DPI", "300 DPI", "600 DPI"])
        self.quality.setCurrentText("300 DPI")
        self.page = QComboBox()
        self.page.addItems(["EPS original size", "A4", "A3"])
        self.color = QComboBox()
        self.color.addItems(["Preserve", "RGB", "CMYK", "Grayscale"])

        self.quality_label = self._setting_column(settings_layout, "Quality", "▧", self.quality)
        self.page_label = self._setting_column(settings_layout, "Page Size", "▤", self.page)
        self.color_label = self._setting_column(settings_layout, "Color Mode", "◉", self.color)
        settings_layout.addSpacing(8)
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setObjectName("verticalSeparator")
        settings_layout.addWidget(separator)
        output_col = QVBoxLayout()
        self.output_label = QLabel("Output Folder")
        self.output_label.setObjectName("settingLabel")
        output_col.addWidget(self.output_label)
        output_row = QHBoxLayout()
        self.output_path = QLineEdit(str(self.output_dir))
        self.output_path.setReadOnly(True)
        self.browse_button = QPushButton("Browse…")
        self.browse_button.setObjectName("browseButton")
        self.browse_button.clicked.connect(self.choose_output)
        output_row.addWidget(self.output_path, 1)
        output_row.addWidget(self.browse_button)
        output_col.addLayout(output_row)
        settings_layout.addLayout(output_col, 2)
        settings_outer.addLayout(settings_layout)
        root.addWidget(self.settings_panel)

        # Footer actions and progress
        footer = QHBoxLayout()
        self.status = QLabel("●  Ready")
        self.status.setObjectName("status")
        footer.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setObjectName("progress")
        self.progress.setValue(0)
        self.progress.setFormat("%p%")
        footer.addWidget(self.progress, 1)
        self.clear_button = QPushButton("▤  Clear List")
        self.clear_button.setObjectName("clearButton")
        self.clear_button.clicked.connect(self.clear_list)
        self.convert_button = QPushButton("⚡  Convert to PDF  →")
        self.convert_button.setObjectName("primary")
        self.convert_button.clicked.connect(self.start_conversion)
        footer.addWidget(self.clear_button)
        footer.addWidget(self.convert_button)
        root.addLayout(footer)

    def _setting_column(self, parent, caption, glyph, widget):
        column = QVBoxLayout()
        label = QLabel(f"{glyph}   {caption}")
        label.setObjectName("settingLabel")
        column.addWidget(label)
        column.addWidget(widget)
        parent.addLayout(column, 1)
        return label

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background:#eef1f4; color:#263442;
                font-family:'Segoe UI','Arial'; font-size:10pt;
            }
            QFrame#headerPanel {
                background:#f8fafb; border:1px solid #d6dde4; border-radius:10px;
            }
            QLabel#title { font-size:22pt; font-weight:750; color:#263746; }
            QLabel#subtitle { color:#71808e; font-size:10pt; }
            QLabel#versionBadge {
                background:#e7edf2; color:#45596c; border-radius:7px;
                padding:6px 10px; font-size:10pt; font-weight:700;
            }
            QPushButton#languageButton {
                background:#edf1f4; border:1px solid #cbd4dc; border-radius:7px;
                padding:8px 13px; color:#35485a; font-weight:600;
            }
            QFrame#dropPanel {
                background:#f8fafb; border:2px dashed #aab8c5; border-radius:10px;
            }
            QLabel#dropTitle { font-size:16pt; font-weight:700; color:#34495b; }
            QLabel#dropHint { color:#788795; font-size:10pt; }
            QPushButton {
                background:#e8edf1; border:1px solid #cbd4dc; border-radius:7px;
                padding:9px 14px; color:#35485a; font-weight:600;
            }
            QPushButton:hover { background:#dce4ea; }
            QPushButton#addFiles { background:#526f89; color:white; border:0; padding:10px 18px; }
            QPushButton#addFolder { background:#687f75; color:white; border:0; padding:10px 18px; }
            QTableWidget#fileTable {
                background:#ffffff; alternate-background-color:#f4f6f8;
                border:1px solid #d5dde4; border-radius:8px;
                gridline-color:#e5e9ed; selection-background-color:#dce7f0;
                selection-color:#263442;
            }
            QHeaderView::section {
                background:#e9eef2; color:#435565; padding:10px;
                border:0; border-right:1px solid #d7dfe6; font-weight:700;
            }
            QTableWidget::item { padding:7px; }
            QFrame#settingsPanel {
                background:#f8fafb; border:1px solid #d6dde4; border-radius:9px;
            }
            QLabel#sectionTitle { font-size:12pt; font-weight:750; color:#34495b; }
            QLabel#settingLabel { color:#526475; font-weight:650; font-size:9pt; }
            QFrame#verticalSeparator { color:#d2dae1; }
            QLineEdit, QComboBox {
                background:#ffffff; border:1px solid #cbd4dc; border-radius:6px;
                padding:7px 9px; color:#2d3d4c; min-height:20px;
            }
            QComboBox QAbstractItemView {
                background:#ffffff; color:#2d3d4c; selection-background-color:#e3ebf1;
            }
            QPushButton#browseButton { background:#e4eaf0; border:1px solid #cbd4dc; }
            QLabel#status { color:#60786c; font-weight:700; font-size:10pt; min-width:130px; }
            QProgressBar {
                background:#e1e7ec; border:0; border-radius:6px;
                height:13px; color:#34495b; text-align:center; font-weight:650;
            }
            QProgressBar::chunk { background:#8298a9; border-radius:6px; }
            QPushButton#clearButton { padding:10px 15px; }
            QPushButton#primary {
                background:#526f89; border:0; border-radius:7px;
                color:white; padding:11px 17px; font-size:10pt; font-weight:700;
            }
            QPushButton#primary:hover { background:#435f78; }
            QPushButton:disabled { color:#98a4ae; background:#e4e8ec; }
        """)

    def _translate(self):
        arabic = self.language == "ar"
        self.setLayoutDirection(Qt.RightToLeft if arabic else Qt.LeftToRight)
        if arabic:
            self.title.setText("EPS to PDF PRO")
            self.subtitle.setText("مساحة احترافية لتحويل ملفات EPS")
            self.language_button.setText("🌐  English")
            self.drop_title.setText("أفلت ملفات EPS أو المجلدات هنا")
            self.drop_hint.setText("أضف ملفات منفردة أو افحص المجلدات بما فيها المجلدات الفرعية")
            self.add_files_button.setText("＋  إضافة ملفات")
            self.add_folder_button.setText("📁  إضافة مجلد")
            self.table.setHorizontalHeaderLabels(["ملف EPS", "الحجم", "الحالة", "ملف PDF الناتج"])
            self.settings_title.setText("⚙  إعدادات التحويل")
            self.quality_label.setText("▧   الجودة")
            self.page_label.setText("▤   حجم الصفحة")
            self.color_label.setText("◉   نمط الألوان")
            self.output_label.setText("مجلد الإخراج")
            self.browse_button.setText("استعراض…")
            self.clear_button.setText("مسح القائمة")
            self.convert_button.setText("⚡  تحويل إلى PDF  ←")
            self.status.setText("●  جاهز")
        else:
            self.subtitle.setText("Professional EPS conversion workspace")
            self.language_button.setText("🌐  العربية")
            self.drop_title.setText("Drop EPS files or folders here")
            self.drop_hint.setText("Add individual files or scan folders including subfolders")
            self.add_files_button.setText("＋  Add files")
            self.add_folder_button.setText("📁  Add folder")
            self.table.setHorizontalHeaderLabels(["EPS File", "Size", "Status", "PDF Output"])
            self.settings_title.setText("⚙  Conversion Settings")
            self.quality_label.setText("▧   Quality")
            self.page_label.setText("▤   Page Size")
            self.color_label.setText("◉   Color Mode")
            self.output_label.setText("Output Folder")
            self.browse_button.setText("Browse…")
            self.clear_button.setText("▤  Clear List")
            self.convert_button.setText("⚡  Convert to PDF  →")
            self.status.setText("●  Ready")

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
            self.table.setItem(row, 0, QTableWidgetItem("📄  " + path.name))
            self.table.setItem(row, 1, QTableWidgetItem(f"{path.stat().st_size / 1024:.1f} KB"))
            self.table.setItem(row, 2, QTableWidgetItem("Queued"))
            self.table.setItem(row, 3, QTableWidgetItem(path.stem + ".pdf"))
            known.add(str(path).casefold())
        self.status.setText(f"●  {len(self.files)} EPS file(s) queued")
        if discovered and not (self.worker and self.worker.isRunning()):
            self.start_conversion()

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
        self.status.setText("●  Ready" if self.language == "en" else "●  جاهز")

    def start_conversion(self):
        if self.worker and self.worker.isRunning():
            return
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
        for row_index, source in enumerate(self.files):
            if self.table.item(row_index, 2).text() != "Queued":
                continue
            target = self.output_dir / f"{source.stem}.pdf"
            suffix = 1
            while target.exists():
                target = self.output_dir / f"{source.stem}_{suffix}.pdf"
                suffix += 1
            jobs.append((source, target))
        if not jobs:
            return
        self.convert_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.progress.setValue(0)
        self.worker = ConversionWorker(
            jobs, self.ghostscript, self.quality.currentText().split()[0],
            self.page.currentText(), self.color.currentText()
        )
        self.worker.file_status.connect(self.update_file_status)
        self.worker.progress_changed.connect(self.progress.setValue)
        self.worker.completed.connect(self.conversion_finished)
        self.worker.start()
        self.status.setText("●  Converting…" if self.language == "en" else "●  جارٍ التحويل…")

    def update_file_status(self, row, state, detail):
        status_item = self.table.item(row, 2)
        output_item = self.table.item(row, 3)
        status_item.setText(state)
        if state == "Completed":
            status_item.setForeground(Qt.green)
            output_item.setText(Path(detail).name)
            output_item.setToolTip(detail)
        elif state == "Failed":
            status_item.setForeground(Qt.red)
            output_item.setText(detail)
            output_item.setToolTip(detail)
        elif state == "Converting":
            status_item.setForeground(Qt.cyan)

    def conversion_finished(self):
        self.convert_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        completed = sum(self.table.item(row, 2).text() == "Completed" for row in range(self.table.rowCount()))
        failed = sum(self.table.item(row, 2).text() == "Failed" for row in range(self.table.rowCount()))
        pending = any(self.table.item(row, 2).text() == "Queued" for row in range(self.table.rowCount()))
        if pending:
            self.status.setText("●  More files queued…" if self.language == "en" else "●  ملفات إضافية في الانتظار…")
            QTimer.singleShot(150, self.start_conversion)
            return
        self.status.setText(f"●  Finished — {completed} completed, {failed} failed")
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
