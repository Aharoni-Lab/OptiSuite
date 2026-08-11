from PyQt5.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout, QFileDialog, QComboBox, QPlainTextEdit, QSlider, QGroupBox, QApplication, QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPixmap
import os






class ProjectionSettingsDialog(QDialog):
    IMAGE_EXTENSIONS = (".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff")

    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Projection Settings")
        self.resize(720, 560)
        self.screens = QApplication.screens()

        self.microscope_display = QComboBox()
        self.plate_display = QComboBox()
        self.solid_display = QComboBox()
        self._populate_display_combo(self.microscope_display)
        self._populate_display_combo(self.plate_display)
        self._populate_display_combo(self.solid_display)

        self.microscope_patterns = QPlainTextEdit()
        self.plate_patterns = QPlainTextEdit()
        self.microscope_patterns.setPlaceholderText("One pattern per line, in projection order")
        self.plate_patterns.setPlaceholderText("One pattern per line, in projection order")

        self.solid_color = QComboBox()
        self.solid_color.addItem("Red", "red")
        self.solid_color.addItem("Green", "green")
        self.solid_color.addItem("Blue", "blue")
        self.solid_intensity = QSlider(Qt.Horizontal)
        self.solid_intensity.setRange(0, 100)
        self.solid_intensity.setValue(100)
        self.solid_intensity.setTickPosition(QSlider.TicksBelow)
        self.solid_intensity.setTickInterval(10)
        self.solid_intensity_label = QLabel("100%")
        self.solid_intensity_label.setFixedWidth(44)
        self.solid_live_running = False
        self.solid_active_display = None
        self.solid_start_btn = QPushButton("Start Solid Projection")
        self.solid_stop_btn = QPushButton("Stop")
        self.solid_stop_btn.setEnabled(False)
        self.solid_start_btn.clicked.connect(self._start_solid_projection)
        self.solid_stop_btn.clicked.connect(self._stop_solid_projection)
        self.solid_display.currentIndexChanged.connect(lambda _=None: self._update_solid_projection_if_running())
        self.solid_color.currentIndexChanged.connect(lambda _=None: self._update_solid_projection_if_running())
        self.solid_intensity.valueChanged.connect(self._on_solid_intensity_changed)

        if settings:
            self._restore_settings(settings)
        elif self.plate_display.count() > 1:
            self.plate_display.setCurrentIndex(1)
            self.solid_display.setCurrentIndex(1)

        hint = QLabel(
            "Detected displays are listed from Windows/Qt. Choose which display/projector is used for "
            "microscope projection and which is used for plate projection, then enter the pattern sequence for each."
        )
        hint.setWordWrap(True)
        display_status = QLabel(self._display_status_text())
        display_status.setWordWrap(True)
        display_status.setStyleSheet(
            "QLabel { background: #eef6ff; border: 1px solid #9cc9ff; border-radius: 4px; "
            "padding: 6px; color: #1f2937; font-weight: 600; }"
        )

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        grid.addWidget(QLabel("Microscope projection display:"), 0, 0)
        grid.addWidget(self.microscope_display, 0, 1)
        grid.addWidget(QLabel("Microscope pattern sequence:"), 1, 0, Qt.AlignTop)
        grid.addWidget(self.microscope_patterns, 1, 1)
        grid.addLayout(self._pattern_picker_row(self.microscope_patterns), 2, 1)
        grid.addWidget(QLabel("Plate projection display:"), 3, 0)
        grid.addWidget(self.plate_display, 3, 1)
        grid.addWidget(QLabel("Plate pattern sequence:"), 4, 0, Qt.AlignTop)
        grid.addWidget(self.plate_patterns, 4, 1)
        grid.addLayout(self._pattern_picker_row(self.plate_patterns), 5, 1)

        solid_box = QGroupBox("Live Solid Color Projection")
        solid_layout = QGridLayout(solid_box)
        solid_layout.setHorizontalSpacing(8)
        solid_layout.setVerticalSpacing(8)
        solid_layout.addWidget(QLabel("Projector/display:"), 0, 0)
        solid_layout.addWidget(self.solid_display, 0, 1, 1, 3)
        solid_layout.addWidget(QLabel("Color:"), 1, 0)
        solid_layout.addWidget(self.solid_color, 1, 1)
        solid_layout.addWidget(QLabel("Intensity:"), 1, 2)
        intensity_row = QHBoxLayout()
        intensity_row.addWidget(self.solid_intensity)
        intensity_row.addWidget(self.solid_intensity_label)
        solid_layout.addLayout(intensity_row, 1, 3)
        solid_actions = QHBoxLayout()
        solid_actions.addStretch(1)
        solid_actions.addWidget(self.solid_start_btn)
        solid_actions.addWidget(self.solid_stop_btn)
        solid_layout.addLayout(solid_actions, 2, 0, 1, 4)

        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(save_btn)
        actions.addWidget(cancel_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addWidget(display_status)
        layout.addLayout(grid)
        layout.addWidget(solid_box)
        layout.addLayout(actions)

    def get_settings(self):
        return {
            "microscope_display": self.microscope_display.currentData(),
            "plate_display": self.plate_display.currentData(),
            "microscope_patterns": self._pattern_lines(self.microscope_patterns),
            "plate_patterns": self._pattern_lines(self.plate_patterns),
            "solid_display": self.solid_display.currentData(),
            "solid_color": self.solid_color.currentData(),
            "solid_intensity": int(self.solid_intensity.value()),
        }

    def _populate_display_combo(self, combo):
        if not self.screens:
            combo.addItem("No displays detected", None)
            combo.setEnabled(False)
            return
        primary = QApplication.primaryScreen()
        for index, screen in enumerate(self.screens):
            geo = screen.geometry()
            primary_label = " primary" if screen == primary else " external/projector candidate"
            label = (
                f"Display {index + 1}: {screen.name()}{primary_label} "
                f"({geo.width()}x{geo.height()} at {geo.x()}, {geo.y()})"
            )
            combo.addItem(label, index)

    def _display_status_text(self):
        display_count = len(self.screens)
        if display_count == 0:
            return "Detected displays: 0. No display output is available for projection."
        if display_count == 1:
            return "Detected displays: 1. Only the primary display is visible; no external HDMI/projector candidate is currently detected."
        return f"Detected displays: {display_count}. External HDMI/projector candidate detected; choose the correct display below."

    def _restore_settings(self, settings):
        self._set_combo_by_data(self.microscope_display, settings.get("microscope_display"))
        self._set_combo_by_data(self.plate_display, settings.get("plate_display"))
        self._set_combo_by_data(self.solid_display, settings.get("solid_display"))
        self._set_combo_by_data(self.solid_color, settings.get("solid_color"))
        if "solid_intensity" in settings:
            self.solid_intensity.setValue(int(settings.get("solid_intensity", 100)))
        self.microscope_patterns.setPlainText("\n".join(settings.get("microscope_patterns", [])))
        self.plate_patterns.setPlainText("\n".join(settings.get("plate_patterns", [])))

    def _set_combo_by_data(self, combo, value):
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _pattern_lines(self, editor):
        return [line.strip() for line in editor.toPlainText().splitlines() if line.strip()]

    def _pattern_picker_row(self, editor):
        row = QHBoxLayout()
        add_files_btn = QPushButton("Add File(s)")
        add_folder_btn = QPushButton("Add Folder Images")
        add_files_btn.clicked.connect(lambda: self._add_pattern_files(editor))
        add_folder_btn.clicked.connect(lambda: self._add_pattern_folder(editor))
        row.addStretch(1)
        row.addWidget(add_files_btn)
        row.addWidget(add_folder_btn)
        return row

    def _add_pattern_files(self, editor):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Projection Image File(s)",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.gif);;All Files (*)",
        )
        self._append_patterns(editor, files)

    def _add_pattern_folder(self, editor):
        folder = QFileDialog.getExistingDirectory(self, "Select Projection Image Folder")
        if not folder:
            return
        files = [
            os.path.join(folder, name)
            for name in sorted(os.listdir(folder))
            if name.lower().endswith(self.IMAGE_EXTENSIONS)
        ]
        self._append_patterns(editor, files)

    def _append_patterns(self, editor, paths):
        if not paths:
            return
        current = editor.toPlainText().strip()
        addition = "\n".join(paths)
        editor.setPlainText(f"{current}\n{addition}".strip() if current else addition)

    def _on_solid_intensity_changed(self, value):
        self.solid_intensity_label.setText(f"{int(value)}%")
        self._update_solid_projection_if_running()

    def _solid_projection_color(self):
        value = int(round(255 * max(0, min(100, int(self.solid_intensity.value()))) / 100.0))
        color_name = self.solid_color.currentData()
        if color_name == "red":
            return QColor(value, 0, 0)
        if color_name == "green":
            return QColor(0, value, 0)
        return QColor(0, 0, value)

    def _start_solid_projection(self):
        self.solid_live_running = True
        self.solid_active_display = self.solid_display.currentData()
        self.solid_start_btn.setEnabled(False)
        self.solid_stop_btn.setEnabled(True)
        self._update_solid_projection_if_running()

    def _stop_solid_projection(self):
        self.solid_live_running = False
        self.solid_start_btn.setEnabled(True)
        self.solid_stop_btn.setEnabled(False)
        parent = self.parent()
        if parent is not None and hasattr(parent, "_stop_live_solid_projection"):
            parent._stop_live_solid_projection(self.solid_active_display)
        self.solid_active_display = None

    def _update_solid_projection_if_running(self):
        if not self.solid_live_running:
            return
        parent = self.parent()
        if parent is None or not hasattr(parent, "_show_live_solid_projection"):
            return
        current_display = self.solid_display.currentData()
        if current_display != self.solid_active_display and hasattr(parent, "_stop_live_solid_projection"):
            parent._stop_live_solid_projection(self.solid_active_display)
            self.solid_active_display = current_display
        parent._show_live_solid_projection(current_display, self._solid_projection_color())

    def accept(self):
        self._stop_solid_projection()
        super().accept()

    def reject(self):
        self._stop_solid_projection()
        super().reject()

    def closeEvent(self, event):
        self._stop_solid_projection()
        event.accept()


class ProjectionWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OptiSuite Projection")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setStyleSheet("background: black;")
        self._current_pixmap = QPixmap()
        self._solid_color = None
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background: black; color: white;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.image_label)

    def show_on_screen(self, screen):
        if screen is not None:
            self.setGeometry(screen.geometry())
        self.showFullScreen()
        if screen is not None and self.windowHandle() is not None:
            self.windowHandle().setScreen(screen)
        self.raise_()
        self.activateWindow()

    def display_image(self, path):
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.image_label.setText(f"Could not load projection image:\n{path}")
            self.image_label.setPixmap(QPixmap())
            self._current_pixmap = QPixmap()
            self._solid_color = None
            return False
        self._current_pixmap = pixmap
        self._solid_color = None
        self.setStyleSheet("background: black;")
        self.image_label.setStyleSheet("background: black; color: white;")
        scaled = self._current_pixmap.scaled(self.image_label.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        self.image_label.setText("")
        self.image_label.setPixmap(scaled)
        return True

    def display_solid_color(self, color: QColor):
        self._current_pixmap = QPixmap()
        self._solid_color = QColor(color)
        self.image_label.setText("")
        self.image_label.setPixmap(QPixmap())
        style = f"background: rgb({color.red()}, {color.green()}, {color.blue()});"
        self.setStyleSheet(style)
        self.image_label.setStyleSheet(style)

    def resizeEvent(self, event):
        if not self._current_pixmap.isNull():
            self.image_label.setPixmap(
                self._current_pixmap.scaled(self.image_label.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            )
        elif self._solid_color is not None:
            self.display_solid_color(self._solid_color)
        super().resizeEvent(event)
