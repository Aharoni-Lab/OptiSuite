import sys
import os
import cv2
import numpy as np
import queue
import threading
import time
from ctypes import byref, c_double, c_int, c_void_p, cdll
from collections import deque
from datetime import datetime, timezone
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QComboBox, QHBoxLayout, QGridLayout, QLineEdit, QSpinBox, QSizePolicy
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QAction, QGroupBox, QMenu, QMessageBox
from PyQt5.QtWidgets import QAbstractItemView, QCheckBox, QDialog, QDoubleSpinBox, QListWidget, QListWidgetItem, QPlainTextEdit, QSlider
from PyQt5.QtCore import QEvent, QObject, QPoint, QTimer, Qt, pyqtSignal, QRectF
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QIcon
import gxipy as gx
import json #for sending run commands
import autofocus as af
from camera_manager_class_import_120425 import CameraManager #camera manager class
from camera_source_router import CharacterizationCameraRouter
from stage_routine_import_013026 import StageRoutine #stage routine class
from zmq_push_worker import ZMQWorker
from zmq_pull_listener import ZMQPullListener
from autofocus_routine import AutofocusRoutine
# from usaf_interface.resolution_app import main as resolution_app_main


#main pytHON gui FOR CAM, STAGE CONNECTION

BACKEND_NATIVE = "native"
BACKEND_PYCRO = "pycro"
BACKEND_LABELS = {
    BACKEND_NATIVE: "OptiSuite native",
    BACKEND_PYCRO: "Pycro-Manager",
}
MICROSCOPE_DEFAULT_EXPOSURE_US = 33333.33
PROJECTION_PATTERN_INTERVAL_MS = 1000

class StageEventBus(QObject):
    message = pyqtSignal(str)


class UiBus(QObject):
    log = pyqtSignal(str)
    autofocus_finished = pyqtSignal()


class PowerMeterBus(QObject):
    sample = pyqtSignal(float, float)
    status = pyqtSignal(str)
    error = pyqtSignal(str)


class SpectrometerBus(QObject):
    spectrum = pyqtSignal(object, object)
    status = pyqtSignal(str)
    error = pyqtSignal(str)




















class StageSequenceEditorDialog(QDialog):
    def __init__(self, stops=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Stage Sequence")
        self.resize(920, 420)
        self.property_options = ["Start", "imaging", "projection", "powermeter", "spectrometer", "image sensor"]
        self.screens = QApplication.screens()
        self._applying_offset = False

        self.stop_list = QListWidget()
        self.stop_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.stop_list.setDefaultDropAction(Qt.MoveAction)
        self.stop_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.stop_list.model().rowsMoved.connect(lambda *args: self._refresh_first_stop_constraint())

        add_btn = QPushButton("+")
        remove_btn = QPushButton("-")
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        add_btn.setFixedWidth(36)
        remove_btn.setFixedWidth(36)

        add_btn.clicked.connect(lambda: self.add_stop())
        remove_btn.clicked.connect(self.remove_selected_stop)
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

        hint = QLabel(
            "Drag stops up/down to change order. Enter X/Y start error as the current zeroed field of view "
            "offset from the intended start position; stop coordinates are corrected by adding that error. "
            f"Detected projectors/displays: {len(self.screens)}. For projection stops, select the projector/display to use."
        )
        hint.setWordWrap(True)

        self.start_offset_x_spin = self._offset_spin()
        self.start_offset_y_spin = self._offset_spin()
        self.start_offset_x_spin.valueChanged.connect(self._apply_start_offset_to_all_stops)
        self.start_offset_y_spin.valueChanged.connect(self._apply_start_offset_to_all_stops)
        self.global_z_check = QCheckBox("Global Z")
        self.global_z_spin = self._coordinate_spin(80.0)
        self.global_z_spin.setSuffix(" mm")
        self.global_z_spin.setEnabled(False)
        self.global_z_check.stateChanged.connect(self._apply_global_z_to_all_stops)
        self.global_z_spin.valueChanged.connect(self._apply_global_z_to_all_stops)

        edit_row = QHBoxLayout()
        edit_row.addWidget(QLabel("Stops:"))
        edit_row.addWidget(add_btn)
        edit_row.addWidget(remove_btn)
        edit_row.addSpacing(16)
        edit_row.addWidget(QLabel("Start error X:"))
        edit_row.addWidget(self.start_offset_x_spin)
        edit_row.addWidget(QLabel("Y:"))
        edit_row.addWidget(self.start_offset_y_spin)
        edit_row.addSpacing(16)
        edit_row.addWidget(self.global_z_check)
        edit_row.addWidget(self.global_z_spin)
        edit_row.addStretch(1)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        action_row.addWidget(save_btn)
        action_row.addWidget(cancel_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addLayout(edit_row)
        layout.addWidget(self.stop_list)
        layout.addLayout(action_row)

        initial_stops = stops if stops else [
            (0.0, 0.0, 80.0, "Start"),
            (12.145, 0.0, 80.0, "imaging"),
            (32.49, 0.0, 80.0, "imaging"),
            (32.49, 25.0, 80.0, "imaging"),
            (32.49, 50.0, 80.0, "imaging"),
            (59.12, 50.0, 80.0, "imaging"),
            (59.12, 25.0, 80.0, "imaging"),
            (59.12, 0.0, 80.0, "imaging"),
            (83.88, 5.0, 80.0, "imaging"),
            (85.88, 25.0, 80.0, "imaging"),
            (91.64, 55.0, 80.0, "imaging"),
            (0.0, 55.0, 80.0, "imaging"),
            (0.0, 15.0, 80.0, "imaging"),
        ]
        for stop in initial_stops:
            x, y, z, prop, projector = self._normalize_stop(stop)
            self.add_stop(x, y, z, prop, projector)
        self._refresh_first_stop_constraint()

    def add_stop(self, x=0.0, y=0.0, z=80.0, prop="imaging", projector=None):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(6, 4, 6, 4)
        row_layout.setSpacing(6)

        title = QLabel()
        title.setFixedWidth(54)
        x_spin = self._coordinate_spin(self._corrected_x(x))
        y_spin = self._coordinate_spin(self._corrected_y(y))
        z_spin = self._coordinate_spin(self._global_z() if self._global_z_enabled() else z)
        property_combo = QComboBox()
        property_combo.addItems(self.property_options)
        property_index = property_combo.findText(str(prop))
        property_combo.setCurrentIndex(max(0, property_index))
        property_combo.setFixedWidth(118)
        projector_combo = QComboBox()
        self._populate_projector_combo(projector_combo)
        projector_index = projector_combo.findData(projector)
        if projector_index < 0 and projector_combo.count() > 0:
            projector_index = 0
        projector_combo.setCurrentIndex(max(0, projector_index))
        projector_combo.setFixedWidth(220)
        property_combo.currentTextChanged.connect(
            lambda _text, widget=row_widget: self._refresh_projector_state(widget)
        )

        row_widget.title_label = title
        row_widget.nominal_x = float(x)
        row_widget.nominal_y = float(y)
        row_widget.x_spin = x_spin
        row_widget.y_spin = y_spin
        row_widget.z_spin = z_spin
        row_widget.property_combo = property_combo
        row_widget.projector_combo = projector_combo
        x_spin.valueChanged.connect(lambda _value, widget=row_widget: self._on_stop_xy_changed(widget, "x"))
        y_spin.valueChanged.connect(lambda _value, widget=row_widget: self._on_stop_xy_changed(widget, "y"))

        row_layout.addWidget(title)
        row_layout.addWidget(QLabel("X:"))
        row_layout.addWidget(x_spin)
        row_layout.addWidget(QLabel("Y:"))
        row_layout.addWidget(y_spin)
        row_layout.addWidget(QLabel("Z:"))
        row_layout.addWidget(z_spin)
        row_layout.addWidget(QLabel("Property:"))
        row_layout.addWidget(property_combo)
        row_layout.addWidget(QLabel("Projector:"))
        row_layout.addWidget(projector_combo)
        row_layout.addStretch(1)

        item = QListWidgetItem()
        item.setSizeHint(row_widget.sizeHint())
        self.stop_list.addItem(item)
        self.stop_list.setItemWidget(item, row_widget)
        self.stop_list.setCurrentItem(item)
        self._refresh_projector_state(row_widget)
        self._refresh_first_stop_constraint()

    def remove_selected_stop(self):
        row = self.stop_list.currentRow()
        if row >= 0:
            self.stop_list.takeItem(row)
        if self.stop_list.count() == 0:
            self.add_stop(0.0, 0.0, 80.0, "imaging")
        self._refresh_first_stop_constraint()

    def get_stops(self):
        stops = []
        for row in range(self.stop_list.count()):
            widget = self.stop_list.itemWidget(self.stop_list.item(row))
            if widget is None:
                continue
            stops.append(
                (
                    float(widget.x_spin.value()),
                    float(widget.y_spin.value()),
                    float(widget.z_spin.value()),
                    str(widget.property_combo.currentText()),
                    widget.projector_combo.currentData(),
                )
            )
        return stops

    def _normalize_stop(self, stop):
        projector = None
        if len(stop) >= 5:
            projector = stop[4]
        if len(stop) >= 4:
            return float(stop[0]), float(stop[1]), float(stop[2]), str(stop[3]), projector
        return float(stop[0]), float(stop[1]), float(stop[2]), "imaging", projector

    def _populate_projector_combo(self, combo):
        if not self.screens:
            combo.addItem("No projector/display detected", None)
            combo.setEnabled(False)
            return
        primary = QApplication.primaryScreen()
        for index, screen in enumerate(self.screens):
            geo = screen.geometry()
            primary_label = " primary" if screen == primary else " external/projector"
            combo.addItem(
                f"Display {index + 1}: {screen.name()}{primary_label} ({geo.width()}x{geo.height()})",
                index,
            )

    def _refresh_projector_state(self, widget):
        if widget is None:
            return
        enabled = widget.property_combo.currentText().lower() == "projection"
        widget.projector_combo.setEnabled(enabled and bool(self.screens))

    def _coordinate_spin(self, value):
        spin = QDoubleSpinBox()
        spin.setDecimals(4)
        spin.setRange(-50000.0, 50000.0)
        spin.setSingleStep(0.1)
        spin.setKeyboardTracking(False)
        spin.setValue(float(value))
        spin.setFixedWidth(92)
        return spin

    def _offset_spin(self):
        spin = self._coordinate_spin(0.0)
        spin.setSuffix(" mm")
        spin.setToolTip("Offset to add to each stop coordinate from the intended start position.")
        return spin

    def _global_z_enabled(self):
        return bool(self.global_z_check.isChecked())

    def _global_z(self):
        return float(self.global_z_spin.value())

    def _start_offset_x(self):
        return float(self.start_offset_x_spin.value())

    def _start_offset_y(self):
        return float(self.start_offset_y_spin.value())

    def _corrected_x(self, nominal_x):
        return float(nominal_x) + self._start_offset_x()

    def _corrected_y(self, nominal_y):
        return float(nominal_y) + self._start_offset_y()

    def _on_stop_xy_changed(self, widget, axis):
        if self._applying_offset or widget is None:
            return
        if axis == "x":
            widget.nominal_x = float(widget.x_spin.value()) - self._start_offset_x()
        elif axis == "y":
            widget.nominal_y = float(widget.y_spin.value()) - self._start_offset_y()

    def _set_corrected_xy(self, widget):
        if widget is None:
            return
        widget.x_spin.setValue(self._corrected_x(getattr(widget, "nominal_x", widget.x_spin.value())))
        widget.y_spin.setValue(self._corrected_y(getattr(widget, "nominal_y", widget.y_spin.value())))

    def _apply_start_offset_to_all_stops(self):
        self._applying_offset = True
        try:
            for row in range(self.stop_list.count()):
                widget = self.stop_list.itemWidget(self.stop_list.item(row))
                self._set_corrected_xy(widget)
        finally:
            self._applying_offset = False

    def _apply_global_z_to_all_stops(self):
        enabled = self._global_z_enabled()
        self.global_z_spin.setEnabled(enabled)
        for row in range(self.stop_list.count()):
            widget = self.stop_list.itemWidget(self.stop_list.item(row))
            if widget is None:
                continue
            if enabled:
                widget.z_spin.setValue(self._global_z())
            widget.z_spin.setEnabled(not enabled)

    def _refresh_first_stop_constraint(self):
        self._applying_offset = True
        try:
            for row in range(self.stop_list.count()):
                widget = self.stop_list.itemWidget(self.stop_list.item(row))
                if widget is None:
                    continue
                widget.title_label.setText(f"Stop {row + 1}")
                is_first = row == 0
                if is_first:
                    widget.nominal_x = 0.0
                    widget.nominal_y = 0.0
                    self._set_corrected_xy(widget)
                    start_index = widget.property_combo.findText("Start")
                    if start_index >= 0:
                        widget.property_combo.setCurrentIndex(start_index)
                widget.x_spin.setEnabled(not is_first)
                widget.y_spin.setEnabled(not is_first)
                widget.z_spin.setEnabled(not self._global_z_enabled())
                widget.property_combo.setEnabled(not is_first)
                self._refresh_projector_state(widget)
        finally:
            self._applying_offset = False
        self._apply_global_z_to_all_stops()
























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




































def make_gauge_icon(size: int = 72) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    pad = max(4, size // 14)
    rect = QRectF(pad, pad, size - 2 * pad, size - 2 * pad)

    # Dial arc
    arc_pen = QPen(QColor(35, 35, 35), max(2, size // 18))
    painter.setPen(arc_pen)
    painter.drawArc(rect, 245 * 16, 230 * 16)

    # Tick marks
    cx = size / 2.0
    cy = size / 2.0
    radius_outer = rect.width() * 0.42
    radius_inner = radius_outer - max(4, size * 0.08)
    for angle_deg in (-135, -90, -45, 0, 45, 90, 135):
        rad = np.deg2rad(float(angle_deg))
        x1 = cx + radius_inner * np.cos(rad)
        y1 = cy + radius_inner * np.sin(rad)
        x2 = cx + radius_outer * np.cos(rad)
        y2 = cy + radius_outer * np.sin(rad)
        painter.drawLine(int(x1), int(y1), int(x2), int(y2))

    # Needle
    needle_pen = QPen(QColor(220, 38, 38), max(2, size // 20))
    painter.setPen(needle_pen)
    needle_angle = np.deg2rad(-35.0)
    needle_len = rect.width() * 0.28
    nx = cx + needle_len * np.cos(needle_angle)
    ny = cy + needle_len * np.sin(needle_angle)
    painter.drawLine(int(cx), int(cy), int(nx), int(ny))

    # Hub
    painter.setPen(QPen(QColor(35, 35, 35), 1))
    painter.setBrush(QColor(35, 35, 35))
    hub_r = max(2, size // 14)
    painter.drawEllipse(int(cx - hub_r), int(cy - hub_r), hub_r * 2, hub_r * 2)

    painter.end()
    return QIcon(pixmap)


def format_power_watts(power_w: float) -> str:
    value = float(power_w)
    abs_value = abs(value)
    if abs_value >= 1.0:
        return f"{value:.6g} W"
    if abs_value >= 1e-3:
        return f"{value * 1e3:.6g} mW"
    if abs_value >= 1e-6:
        return f"{value * 1e6:.6g} uW"
    if abs_value >= 1e-9:
        return f"{value * 1e9:.6g} nW"
    return f"{value * 1e12:.6g} pW"




























class EmptyCameraManager:
    def __init__(self, save_dir="captures", reason="No camera backend available."):
        self.save_dir = save_dir
        os.makedirs(self.save_dir, exist_ok=True)
        self.reason = reason
        self.cameras = []
        self.camera_names = []
        self.num_cameras = 0
        self.recording = []
        self.video_writers = []
        print(f"[CameraManager] {reason}")

    def get_frame(self, cam_index):
        return None

    def get_exposure_range(self, cam_index):
        return None

    def get_gain_range(self, cam_index):
        return None

    def get_exposure(self, cam_index):
        return 0.0

    def get_gain(self, cam_index):
        return 0.0

    def set_exposure(self, cam_index, value):
        return False, 0.0

    def set_gain(self, cam_index, value):
        return False, 0.0

    def take_screenshot(self, *args, **kwargs):
        return None

    def start_recording(self, cam_index):
        return

    def stop_recording(self, cam_index):
        return

    def write_record_frame(self, cam_index):
        return

    def close(self):
        return





































class PowerTraceWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.samples = deque(maxlen=3000)
        self.setMinimumSize(720, 360)

    def clear(self):
        self.samples.clear()
        self.update()

    def add_sample(self, elapsed_s: float, power_w: float):
        self.samples.append((float(elapsed_s), float(power_w)))
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        margin_l = 72
        margin_r = 20
        margin_t = 20
        margin_b = 60
        plot_w = max(1, width - margin_l - margin_r)
        plot_h = max(1, height - margin_t - margin_b)

        painter.fillRect(self.rect(), QColor(250, 250, 250))
        painter.setPen(QPen(QColor(60, 60, 60), 1))
        painter.drawRect(margin_l, margin_t, plot_w, plot_h)

        if not self.samples:
            painter.drawText(margin_l + 12, margin_t + 28, "Waiting for power meter samples...")
            painter.end()
            return

        samples = list(self.samples)
        latest_t = samples[-1][0]
        x_min = max(0.0, latest_t - 60.0)
        visible = [(t, p) for t, p in samples if t >= x_min]
        if len(visible) < 2:
            visible = samples[-2:] if len(samples) >= 2 else samples

        x_max = max(latest_t, x_min + 1.0)
        powers = [p for _, p in visible]
        y_min = min(powers)
        y_max = max(powers)
        if abs(y_max - y_min) < 1e-15:
            pad = max(abs(y_max) * 0.05, 1e-12)
        else:
            pad = (y_max - y_min) * 0.08
        y_min -= pad
        y_max += pad

        def to_x(t):
            return margin_l + int((t - x_min) / (x_max - x_min) * plot_w)

        def to_y(p):
            return margin_t + plot_h - int((p - y_min) / (y_max - y_min) * plot_h)

        painter.setPen(QPen(QColor(225, 225, 225), 1))
        for n in range(1, 5):
            x = margin_l + int(plot_w * n / 5)
            y = margin_t + int(plot_h * n / 5)
            painter.drawLine(x, margin_t, x, margin_t + plot_h)
            painter.drawLine(margin_l, y, margin_l + plot_w, y)

        painter.setPen(QPen(QColor(70, 70, 70), 1))
        for n in range(0, 6):
            frac = n / 5.0
            tick_t = x_min + frac * (x_max - x_min)
            x = margin_l + int(plot_w * frac)
            painter.drawLine(x, margin_t + plot_h, x, margin_t + plot_h + 5)
            painter.drawText(x - 32, margin_t + plot_h + 8, 64, 18, Qt.AlignCenter, f"{tick_t:.1f}")

        painter.setPen(QPen(QColor(33, 102, 172), 2))
        prev = None
        for t, p in visible:
            point = (to_x(t), to_y(p))
            if prev is not None:
                painter.drawLine(prev[0], prev[1], point[0], point[1])
            prev = point

        painter.setPen(QPen(QColor(35, 35, 35), 1))
        painter.drawText(8, margin_t + 4, margin_l - 14, 20, Qt.AlignRight, format_power_watts(y_max))
        painter.drawText(8, margin_t + plot_h - 16, margin_l - 14, 20, Qt.AlignRight, format_power_watts(y_min))
        painter.drawText(margin_l, height - 24, plot_w, 20, Qt.AlignCenter, "Elapsed time (s)")
        painter.drawText(margin_l + 6, margin_t + 20, f"Latest: {format_power_watts(samples[-1][1])}")
        painter.end()






































class PowerMeterWindow(QWidget):
    closed = pyqtSignal()

    def __init__(self, start_callback, stop_callback, parent=None):
        super().__init__(parent)
        self.start_callback = start_callback
        self.stop_callback = stop_callback
        self.stream_running = False
        self.setWindowTitle("Thorlabs Power Meter Live Plot")

        self.status_label = QLabel("Connecting to power meter...")
        self.status_label.setWordWrap(True)
        self.latest_label = QLabel("Latest: --")
        self.latest_label.setStyleSheet("font-weight: 600;")
        self.plot = PowerTraceWidget()

        self.stream_btn = QPushButton("Stop")
        clear_btn = QPushButton("Clear")
        self.stream_btn.clicked.connect(self.toggle_stream)
        clear_btn.clicked.connect(self.plot.clear)

        controls = QHBoxLayout()
        controls.addWidget(self.stream_btn)
        controls.addWidget(clear_btn)
        controls.addStretch(1)

        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addWidget(self.latest_label)
        layout.addWidget(self.plot)
        layout.addLayout(controls)
        self.setLayout(layout)
        self.resize(820, 480)

    def add_sample(self, elapsed_s: float, power_w: float):
        self.latest_label.setText(f"Latest: {format_power_watts(power_w)}")
        self.plot.add_sample(elapsed_s, power_w)

    def set_status(self, text: str):
        self.status_label.setText(text)

    def set_stream_running(self, running: bool):
        self.stream_running = bool(running)
        self.stream_btn.setText("Stop" if self.stream_running else "Start")

    def toggle_stream(self):
        if self.stream_running:
            self.stop_callback()
        else:
            self.start_callback()

    def closeEvent(self, event):
        self.stop_callback()
        self.closed.emit()
        event.accept()



































class PowerMeterWorker(threading.Thread):
    POWER_METER_PRODUCT_IDS = {"0X8072", "0X8078", "0X807B"}

    def __init__(self, bus: PowerMeterBus, sample_interval_s: float = 0.2):
        super().__init__(daemon=True)
        self.bus = bus
        self.sample_interval_s = float(sample_interval_s)
        self.stop_event = threading.Event()
        self.rm = None
        self.instr = None
        self.connected = False
        self.resource_name = None

    def stop(self):
        self.stop_event.set()

    def run(self):
        try:
            pyvisa = __import__("pyvisa")
        except ImportError:
            self.bus.error.emit("PyVISA is not installed. Install it with: python -m pip install pyvisa")
            return

        try:
            self._connect_power_meter(pyvisa)

            start = time.monotonic()
            consecutive_errors = 0
            while not self.stop_event.is_set():
                try:
                    reading = self.instr.query("MEAS:POW?").strip()
                    power_w = float(reading.split(",")[0])
                    consecutive_errors = 0
                    self.bus.sample.emit(time.monotonic() - start, power_w)
                except Exception as e:
                    consecutive_errors += 1
                    if consecutive_errors == 1:
                        self.bus.status.emit(f"Power meter read paused: {e}")
                    if consecutive_errors >= 3:
                        self.bus.status.emit("Reconnecting power meter...")
                        self._connect_power_meter(pyvisa)
                        consecutive_errors = 0
                self.stop_event.wait(self.sample_interval_s)
        except Exception as e:
            self.bus.error.emit(f"Power meter error: {e}")
        finally:
            self._close_resources()
            if self.connected:
                self.bus.status.emit("Power meter disconnected.")

    def _connect_power_meter(self, pyvisa):
        self._close_resources()
        self.rm = pyvisa.ResourceManager()
        self.instr, resource_name, identity = self._open_power_meter()
        self.connected = True
        self.resource_name = resource_name
        self.bus.status.emit(f"Connected: {identity} ({resource_name})")

        self._write_ignore_errors("SENS:RANGE:AUTO ON")
        self._write_ignore_errors("SENS:POW:UNIT W")

    def _open_power_meter(self):
        resources = list(self.rm.list_resources())
        if not resources:
            raise RuntimeError("No VISA resources found.")

        errors = []
        for resource_name in resources:
            resource_upper = resource_name.upper()
            if "USB" not in resource_upper:
                continue
            if not any(pid in resource_upper for pid in self.POWER_METER_PRODUCT_IDS):
                continue
            instr = None
            try:
                instr = self.rm.open_resource(resource_name)
                instr.timeout = 2000
                instr.write_termination = "\n"
                instr.read_termination = "\n"
                identity = self._query_identity(instr)
                identity_upper = identity.upper()
                if "THORLABS" in identity_upper or "PM" in identity_upper:
                    return instr, resource_name, identity
                instr.close()
            except Exception as e:
                errors.append(f"{resource_name}: {e}")
                try:
                    if instr is not None:
                        instr.close()
                except Exception:
                    pass

        detail = "; ".join(errors[:3])
        if detail:
            raise RuntimeError(f"No Thorlabs USB power meter found. Tried: {detail}")
        raise RuntimeError(f"No Thorlabs USB power meter found. VISA resources: {resources}")

    def _query_identity(self, instr):
        for command in ("SYST:SENS:IDN?", "*IDN?"):
            try:
                text = instr.query(command).strip()
                if text:
                    return text
            except Exception:
                pass
        return "Unknown power meter"

    def _write_ignore_errors(self, command):
        try:
            self.instr.write(command)
        except Exception:
            pass

    def _close_resources(self):
        try:
            if self.instr is not None:
                self.instr.close()
        except Exception:
            pass
        self.instr = None

        try:
            if self.rm is not None:
                self.rm.close()
        except Exception:
            pass
        self.rm = None













































class SpectrumTraceWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.wavelengths = None
        self.intensities = None
        self.setMinimumSize(760, 420)

    def set_spectrum(self, wavelengths, intensities):
        self.wavelengths = np.asarray(wavelengths, dtype=np.float64)
        self.intensities = np.asarray(intensities, dtype=np.float64)
        self.update()

    def clear(self):
        self.wavelengths = None
        self.intensities = None
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        margin_l = 72
        margin_r = 22
        margin_t = 22
        margin_b = 64
        plot_w = max(1, width - margin_l - margin_r)
        plot_h = max(1, height - margin_t - margin_b)

        painter.fillRect(self.rect(), QColor(250, 250, 250))
        painter.setPen(QPen(QColor(60, 60, 60), 1))
        painter.drawRect(margin_l, margin_t, plot_w, plot_h)

        if self.wavelengths is None or self.intensities is None or len(self.wavelengths) < 2:
            painter.drawText(margin_l + 12, margin_t + 28, "Waiting for spectrometer samples...")
            painter.end()
            return

        wavelengths = self.wavelengths
        intensities = self.intensities
        finite = np.isfinite(wavelengths) & np.isfinite(intensities)
        wavelengths = wavelengths[finite]
        intensities = intensities[finite]
        if len(wavelengths) < 2:
            painter.drawText(margin_l + 12, margin_t + 28, "No valid spectrum data.")
            painter.end()
            return

        x_min = float(np.min(wavelengths))
        x_max = float(np.max(wavelengths))
        y_min = float(np.min(intensities))
        y_max = float(np.max(intensities))
        if abs(x_max - x_min) < 1e-12:
            x_max = x_min + 1.0
        if abs(y_max - y_min) < 1e-12:
            pad = max(abs(y_max) * 0.05, 1e-3)
        else:
            pad = (y_max - y_min) * 0.08
        y_min -= pad
        y_max += pad

        def to_x(x):
            return margin_l + int((float(x) - x_min) / (x_max - x_min) * plot_w)

        def to_y(y):
            return margin_t + plot_h - int((float(y) - y_min) / (y_max - y_min) * plot_h)

        painter.setPen(QPen(QColor(225, 225, 225), 1))
        for n in range(1, 5):
            x = margin_l + int(plot_w * n / 5)
            y = margin_t + int(plot_h * n / 5)
            painter.drawLine(x, margin_t, x, margin_t + plot_h)
            painter.drawLine(margin_l, y, margin_l + plot_w, y)

        painter.setPen(QPen(QColor(70, 70, 70), 1))
        for n in range(0, 6):
            frac = n / 5.0
            tick_nm = x_min + frac * (x_max - x_min)
            x = margin_l + int(plot_w * frac)
            painter.drawLine(x, margin_t + plot_h, x, margin_t + plot_h + 5)
            painter.drawText(x - 36, margin_t + plot_h + 8, 72, 18, Qt.AlignCenter, f"{tick_nm:.1f}")

        painter.setPen(QPen(QColor(35, 126, 77), 2))
        prev = None
        step = max(1, len(wavelengths) // max(1, plot_w * 2))
        for x, y in zip(wavelengths[::step], intensities[::step]):
            point = (to_x(x), to_y(y))
            if prev is not None:
                painter.drawLine(prev[0], prev[1], point[0], point[1])
            prev = point

        painter.setPen(QPen(QColor(35, 35, 35), 1))
        painter.drawText(8, margin_t + 4, margin_l - 14, 20, Qt.AlignRight, f"{y_max:.3g}")
        painter.drawText(8, margin_t + plot_h - 16, margin_l - 14, 20, Qt.AlignRight, f"{y_min:.3g}")
        painter.drawText(margin_l, height - 26, plot_w, 20, Qt.AlignCenter, "Wavelength (nm)")
        painter.drawText(margin_l + 6, margin_t + 20, f"Peak: {float(np.max(intensities)):.4g} a.u.")
        painter.end()










































class SpectrometerWindow(QWidget):
    closed = pyqtSignal()

    def __init__(self, start_callback, stop_callback, parent=None):
        super().__init__(parent)
        self.start_callback = start_callback
        self.stop_callback = stop_callback
        self.stream_running = False
        self.setWindowTitle("Thorlabs CCS100 Spectrometer Live Plot")

        self.status_label = QLabel("Connecting to spectrometer...")
        self.status_label.setWordWrap(True)
        self.latest_label = QLabel("Latest: --")
        self.latest_label.setStyleSheet("font-weight: 600;")
        self.plot = SpectrumTraceWidget()

        self.stream_btn = QPushButton("Stop")
        clear_btn = QPushButton("Clear")
        save_btn = QPushButton("Save CSV")
        save_btn.setMinimumWidth(80)
        self.stream_btn.clicked.connect(self.toggle_stream)
        clear_btn.clicked.connect(self.plot.clear)
        save_btn.clicked.connect(self.save_spectrum_csv)

        controls = QHBoxLayout()
        controls.addWidget(self.stream_btn)
        controls.addWidget(clear_btn)
        controls.addWidget(save_btn)
        controls.addStretch(1)

        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addWidget(self.latest_label)
        layout.addWidget(self.plot)
        layout.addLayout(controls)
        self.setLayout(layout)
        self.resize(860, 540)

    def set_spectrum(self, wavelengths, intensities):
        arr = np.asarray(intensities, dtype=np.float64)
        peak = float(np.nanmax(arr)) if arr.size else 0.0
        self.latest_label.setText(f"Latest peak: {peak:.6g} a.u.")
        self.plot.set_spectrum(wavelengths, intensities)

    def set_status(self, text: str):
        self.status_label.setText(text)

    def set_stream_running(self, running: bool):
        self.stream_running = bool(running)
        self.stream_btn.setText("Stop" if self.stream_running else "Start")

    def toggle_stream(self):
        if self.stream_running:
            self.stop_callback()
        else:
            self.start_callback()

    def save_spectrum_csv(self):
        if self.plot.wavelengths is None or self.plot.intensities is None:
            self.set_status("No spectrum data to save yet.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_path = os.path.join(os.getcwd(), f"spectrometer_{timestamp}.csv")
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Spectrometer Data",
            default_path,
            "CSV Files (*.csv);;All Files (*)",
        )
        if not filename:
            return
        if not filename.lower().endswith(".csv"):
            filename += ".csv"

        data = np.column_stack((self.plot.wavelengths, self.plot.intensities))
        np.savetxt(
            filename,
            data,
            delimiter=",",
            header="wavelength_nm,intensity_au",
            comments="",
        )
        self.set_status(f"Saved spectrum CSV: {filename}")

    def closeEvent(self, event):
        self.stop_callback()
        self.closed.emit()
        event.accept()






























class SpectrometerWorker(threading.Thread):
    CCS_PIXELS = 3648
    CCS_PRODUCT_IDS = {"0X8081", "0X8083", "0X8085", "0X8087", "0X8089"}

    def __init__(self, bus: SpectrometerBus, integration_time_s: float = 10.0e-3, plot_interval_s: float = 0.2):
        super().__init__(daemon=True)
        self.bus = bus
        self.integration_time_s = float(integration_time_s)
        self.plot_interval_s = float(plot_interval_s)
        self.stop_event = threading.Event()
        self.lib = None
        self.handle = c_int(0)
        self.connected = False

    def stop(self):
        self.stop_event.set()

    def run(self):
        try:
            self.bus.status.emit("Searching for Thorlabs CCS100 spectrometer...")
            self.lib = self._load_tlccs_library()
            resource_name = self._find_ccs_resource()
            # Do not reset the spectrometer on open; resets can disturb other VISA instruments already streaming.
            self._check(self.lib.tlccs_init(resource_name.encode("ascii"), 1, 0, byref(self.handle)), "tlccs_init")
            self.connected = True
            self.bus.status.emit(f"Connected: {resource_name}")

            self._check(
                self.lib.tlccs_setIntegrationTime(self.handle, c_double(self.integration_time_s)),
                "tlccs_setIntegrationTime",
            )

            wavelengths = (c_double * self.CCS_PIXELS)()
            self._check(
                self.lib.tlccs_getWavelengthData(self.handle, 0, byref(wavelengths), c_void_p(None), c_void_p(None)),
                "tlccs_getWavelengthData",
            )
            wavelength_array = np.array(list(wavelengths), dtype=np.float64)

            while not self.stop_event.is_set():
                self._check(self.lib.tlccs_startScan(self.handle), "tlccs_startScan")
                self._wait_for_scan()
                data_array = (c_double * self.CCS_PIXELS)()
                self._check(self.lib.tlccs_getScanData(self.handle, byref(data_array)), "tlccs_getScanData")
                intensities = np.array(list(data_array), dtype=np.float64)
                self.bus.spectrum.emit(wavelength_array, intensities)
                self.stop_event.wait(self.plot_interval_s)
        except Exception as e:
            self.bus.error.emit(f"Spectrometer error: {e}")
        finally:
            self._close_device()
            if self.connected:
                self.bus.status.emit("Spectrometer disconnected.")

    def _load_tlccs_library(self):
        candidates = [
            "TLCCS_64.dll",
            r"C:\Program Files\IVI Foundation\VISA\Win64\Bin\TLCCS_64.dll",
            r"C:\Program Files\IVI Foundation\VISA\Win64\TLCCS\Bin\TLCCS_64.dll",
            r"C:\Program Files\Thorlabs\Scientific Imaging\ThorSpectra\TLCCS_64.dll",
        ]
        errors = []
        for path in candidates:
            try:
                if os.path.isabs(path) and not os.path.exists(path):
                    continue
                return cdll.LoadLibrary(path)
            except Exception as e:
                errors.append(f"{path}: {e}")
        detail = "; ".join(errors[:2])
        raise RuntimeError(
            "Could not load TLCCS_64.dll. Install the Thorlabs CCS/ThorSpectra driver so the DLL is available."
            + (f" Details: {detail}" if detail else "")
        )

    def _find_ccs_resource(self):
        try:
            pyvisa = __import__("pyvisa")
        except ImportError:
            raise RuntimeError("PyVISA is not installed in this environment.")

        rm = pyvisa.ResourceManager()
        try:
            resources = list(rm.list_resources("?*"))
        finally:
            rm.close()

        ccs_resources = []
        preferred_aliases = [
            "Thorlabs CCS100 spectrumeter",
            "Thorlabs CCS100 spectrometer",
        ]
        for alias in preferred_aliases:
            if alias in resources:
                ccs_resources.append(alias)

        for resource in resources:
            resource_upper = str(resource).upper()
            if "CCS" in resource_upper or "SPECTROMETER" in resource_upper or "SPECTRUMETER" in resource_upper:
                ccs_resources.append(str(resource))
                continue
            if "USB" not in resource_upper or "0X1313" not in resource_upper:
                continue
            if any(pid in resource_upper for pid in self.CCS_PRODUCT_IDS):
                ccs_resources.append(str(resource))

        if ccs_resources:
            resource = ccs_resources[0]
            if resource.upper().endswith("::INSTR"):
                resource = resource[:-7] + "::RAW"
            return resource

        raise RuntimeError(f"No Thorlabs CCS spectrometer VISA resource found. Current resources: {resources}")

    def _wait_for_scan(self):
        status = c_int(0)
        deadline = time.monotonic() + max(2.0, self.integration_time_s * 5.0 + 1.0)
        while not self.stop_event.is_set():
            self._check(self.lib.tlccs_getDeviceStatus(self.handle, byref(status)), "tlccs_getDeviceStatus")
            if (status.value & 0x0010) != 0:
                return
            if time.monotonic() > deadline:
                raise TimeoutError("Timed out waiting for spectrometer scan")
            time.sleep(0.005)

    def _check(self, code, operation):
        if int(code) != 0:
            raise RuntimeError(f"{operation} failed with code {int(code)}")

    def _close_device(self):
        try:
            if self.lib is not None and self.handle.value:
                self.lib.tlccs_close(self.handle)
        except Exception:
            pass
        self.handle = c_int(0)









































#import the camera functinality from another file
# -------- Main GUI Application -------- #
class CameraApp(QWidget):
    def _stage_ports_for_backend(self, backend: str):
        if backend == BACKEND_PYCRO:
            return self.pycro_stage_host, self.pycro_stage_cmd_port, self.pycro_stage_event_port
        return self.native_stage_host, self.native_stage_cmd_port, self.native_stage_event_port

    def _stage_status_prefix(self):
        return "Pycro stage" if getattr(self, "hardware_backend", BACKEND_NATIVE) == BACKEND_PYCRO else "C# stage"

    def _create_camera_manager(self, backend: str):
        if backend == BACKEND_PYCRO:
            try:
                from pycro_camera_client import PycroManagerCameraManager

                manager = PycroManagerCameraManager(save_dir=self.save_dir)
                self._apply_microscope_default_exposure(manager)
                return manager
            except Exception as e:
                msg = f"Pycro-Manager camera unavailable: {e}"
                print(f"[Backend] {msg}")
                return EmptyCameraManager(save_dir=self.save_dir, reason=msg)

        try:
            base_manager = CameraManager(save_dir=self.save_dir)
            router = CharacterizationCameraRouter(base_manager, save_dir=self.save_dir)
            if getattr(self, "characterization_camera_source", "daheng") != "daheng":
                try:
                    router.set_characterization_source(self.characterization_camera_source)
                except Exception as e:
                    print(f"[Backend] Characterization camera fallback to Daheng/current: {e}")
                    self.characterization_camera_source = "daheng"
            self._apply_microscope_default_exposure(router)
            return router
        except Exception as e:
            msg = f"Native camera unavailable: {e}"
            print(f"[Backend] {msg}")
            return EmptyCameraManager(save_dir=self.save_dir, reason=msg)

    def _apply_microscope_default_exposure(self, manager):
        if getattr(manager, "num_cameras", 0) <= 0:
            return
        try:
            ok, applied = manager.set_exposure(0, MICROSCOPE_DEFAULT_EXPOSURE_US)
            print(f"[Camera] Microscope default exposure set to {applied:.2f} us (ok={ok})")
        except Exception as e:
            print(f"[Camera] Could not set microscope default exposure: {e}")

    def __init__(self):
        super().__init__()
        self.setWindowTitle("OptiSuite GUI interface")
        # We set a fixed size later after building the layout.

        # ZMQ Setup
        self.zmq_thread = None
        self.zmq_events = None
        self.native_stage_host = "localhost"
        self.native_stage_cmd_port = 5555
        self.native_stage_event_port = 5556
        self.pycro_stage_host = "127.0.0.1"
        self.pycro_stage_cmd_port = 5655
        self.pycro_stage_event_port = 5656
        self.hardware_backend = os.environ.get("OPTISUITE_BACKEND", BACKEND_NATIVE).strip().lower()
        if self.hardware_backend not in BACKEND_LABELS:
            self.hardware_backend = BACKEND_NATIVE
        self.characterization_camera_source = os.environ.get("OPTISUITE_CHAR_CAMERA", "dmk:0").strip().lower()
        self.stage_host, self.stage_cmd_port, self.stage_event_port = self._stage_ports_for_backend(self.hardware_backend)
        self.stage_event_queue = queue.Queue(maxsize=2000)
        self._stage_seq_lock = threading.Lock()
        self._stage_last_seq = 0

        # Stage status/event UI + thread-safe signal bridge
        self.stage_event_bus = StageEventBus()
        self.stage_event_bus.message.connect(self.on_stage_event)
        self.preview_status = QLabel("")
        self.preview_status.setStyleSheet("color: #b45309; font-weight: 600;")
        self.preview_status.setWordWrap(True)
        self.preview_status.hide()
        self.stage_status = QLabel(f"{self._stage_status_prefix()}: (no events)")
        self.stage_status.setWordWrap(True)
        self.stage_status.hide()
        self.stage_log = QPlainTextEdit()
        self.stage_log.setReadOnly(True)
        self.stage_log.setMaximumBlockCount(500)
        self.stage_log.setMinimumWidth(220)

        self.ui_bus = UiBus()
        self.ui_bus.log.connect(self.append_local_log)
        self.ui_bus.autofocus_finished.connect(self._on_autofocus_finished)
        self.af_cancel = threading.Event()
        self.af_thread = None

        self.power_meter_bus = PowerMeterBus()
        self.power_meter_bus.sample.connect(self._on_power_meter_sample)
        self.power_meter_bus.status.connect(self._on_power_meter_status)
        self.power_meter_bus.error.connect(self._on_power_meter_error)
        self.power_meter_thread = None
        self.power_meter_window = None

        self.spectrometer_bus = SpectrometerBus()
        self.spectrometer_bus.spectrum.connect(self._on_spectrometer_spectrum)
        self.spectrometer_bus.status.connect(self._on_spectrometer_status)
        self.spectrometer_bus.error.connect(self._on_spectrometer_error)
        self.spectrometer_thread = None
        self.spectrometer_window = None
        self.projection_settings = {}
        self.projection_windows = {}
        self.projection_sequence_running = False

        self.save_dir = r"C:\Users\stimscope1\Documents\OptiSuite\screenshots"
        #use the class instead
        self.cam_mgr = self._create_camera_manager(self.hardware_backend)
        self.camera_slot_count = max(2, self.cam_mgr.num_cameras)
        self.zoom_labels = [None] * self.camera_slot_count
        # Per-camera view state for software zoom/pan
        # zoom: >= 1.0, cx/cy are normalized [0..1] center coordinates in the source frame
        self.view_states = [{"zoom": 1.0, "cx": 0.5, "cy": 0.5} for _ in range(self.camera_slot_count)]
        # Track last mouse position in label coords (for button zoom anchoring)
        self.last_mouse_pos = [None] * self.camera_slot_count
        self.pan_active = [False] * self.camera_slot_count
        self.pan_last_pos = [None] * self.camera_slot_count
        # Track last seen frame sizes (w, h) per camera
        self.last_frame_sizes = [None] * self.camera_slot_count
        self.frame_fps = [0.0] * self.camera_slot_count
        self.frame_last_ts = [None] * self.camera_slot_count
        self.frame_last_ids = [None] * self.camera_slot_count
       
        # - -   -   -   -   -
        # for the dual camera layout
        #   -   --  -   -   -

        self.layout = QVBoxLayout()
        self.grid = QGridLayout()
        self.cam_labels = []
        self.cam_title_labels = []
        self.camera_control_widgets = []
        self.control_panels = []
        self.exposure_inputs = []
        self.gain_inputs = []

        # Layout is intentionally 1 camera per row (less cramped).
        cols = 1
        n_cams = self.camera_slot_count
        rows = (n_cams + cols - 1) // cols

        # Fit to screen so the bottom panel doesn't get pushed off-screen.
        screen = QApplication.primaryScreen().availableGeometry()
        max_win_w = int(screen.width() * 0.95)
        max_win_h = int(screen.height() * 0.95)

        stage_log_w = min(400, max(320, int(max_win_w * 0.32)))
        self.stage_log.setMinimumWidth(260)
        self.stage_log.resize(stage_log_w, self.stage_log.height())
        self.stage_log.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        # Reserve enough vertical space for stacked bottom control rows.
        # Keep the initial preview size modest; resizing can then grow it.
        bottom_panel_h = 320
        caption_h = 22
        control_h = 220
        preview_h = int((max_win_h - bottom_panel_h) / rows) - caption_h - control_h
        preview_h = max(140, min(260, preview_h))

        preview_w = min(520, max_win_w - stage_log_w - 80)
        preview_w = max(360, preview_w)

        def add_characterization_controls(control_stack):
            characterization_box = QGroupBox("Charactrization plate")
            characterization_box.setStyleSheet(
                "QGroupBox { font-weight: 600; border: 1px solid #8a8a8a; border-radius: 5px; "
                "margin-top: 12px; padding-top: 10px; background: #f7f7f7; } "
                "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
            )
            characterization_panel = QHBoxLayout(characterization_box)
            characterization_panel.setContentsMargins(12, 14, 12, 12)

            circular_btn_style = (
                "QPushButton { border: 2px solid #555; border-radius: 52px; background: #ffffff; "
                "font-weight: 600; padding: 4px; } "
                "QPushButton:hover { background: #e8f0ff; } "
                "QPushButton:pressed { background: #cfe0ff; } "
                "QPushButton:disabled { color: #777; background: #e5e5e5; }"
            )
            rainbow_btn_style = (
                "QPushButton { border: 2px solid #555; border-radius: 52px; color: #111; "
                "font-weight: 700; padding: 4px; "
                "background: qconicalgradient(cx:0.5, cy:0.5, angle:0, "
                "stop:0 #ff3b30, stop:0.16 #ff9500, stop:0.32 #ffcc00, "
                "stop:0.48 #34c759, stop:0.64 #007aff, stop:0.80 #5856d6, stop:1 #ff2d55); } "
                "QPushButton:hover { border: 3px solid #333; } "
                "QPushButton:pressed { background: qconicalgradient(cx:0.5, cy:0.5, angle:45, "
                "stop:0 #ff3b30, stop:0.16 #ff9500, stop:0.32 #ffcc00, "
                "stop:0.48 #34c759, stop:0.64 #007aff, stop:0.80 #5856d6, stop:1 #ff2d55); } "
                "QPushButton:disabled { color: #777; background: #e5e5e5; }"
            )
            slide_btn_style = (
                "QPushButton { border: 2px solid #6a6a6a; border-radius: 12px; "
                "background: #f9fbff; color: #1f2937; font-weight: 700; padding: 8px; } "
                "QPushButton:hover { background: #edf4ff; border-color: #3367d6; } "
                "QPushButton:pressed { background: #d8e8ff; } "
                "QPushButton:disabled { color: #777; background: #e5e5e5; }"
            )
            t_btn_style = (
                "QPushButton { border: 1px solid #d1d5db; border-radius: 5px; "
                "background: #ffffff; color: #9ca3af; font-weight: 700; } "
                "QPushButton:hover { background: #ffffff; border-color: #9ca3af; } "
                "QPushButton:pressed { background: #f9fafb; }"
            )
            plate_sensor_btn_style = (
                "QPushButton { border: 2px solid #6a6a6a; border-radius: 10px; "
                "background: #fffdf7; color: #1f2937; font-weight: 700; padding: 6px; } "
                "QPushButton:hover { background: #fff4d6; border-color: #b45309; } "
                "QPushButton:pressed { background: #fde68a; } "
                "QPushButton:disabled { color: #777; background: #e5e5e5; }"
            )
            fluorescence_btn_style = (
                "QPushButton { border: 2px solid #15803d; border-radius: 10px; "
                "background: #dcfce7; color: #14532d; font-weight: 700; padding: 6px; } "
                "QPushButton:hover { background: #bbf7d0; border-color: #166534; } "
                "QPushButton:pressed { background: #86efac; } "
                "QPushButton:disabled { color: #777; background: #e5e5e5; }"
            )

            self.slide_selections = getattr(self, "slide_selections", {"Slide 1": None, "Slide 2": None})
            slide_options = ["PSF", "Slices", "Resolution target", "Fluorescence slide", "PSFcheck", "MicroLED pannel"]

            def configure_slide_menu(button, slide_name):
                menu = QMenu(button)

                def set_slide_selection(selection):
                    self.slide_selections[slide_name] = selection
                    button.setText(f"{slide_name}\n{selection}")
                    button.setToolTip(f"{slide_name}: {selection}")

                for option in slide_options:
                    action = QAction(option, menu)
                    action.triggered.connect(lambda checked=False, value=option: set_slide_selection(value))
                    menu.addAction(action)

                button.setMenu(menu)

            def configure_plate_sensor_menu(button):
                menu = QMenu(button)

                def plate_sensor_label():
                    if not hasattr(self, "characterization_camera_select"):
                        return ""
                    source_id = self.characterization_camera_select.currentData()
                    if source_id == "dmk:0":
                        return "DMK 27BUP031"
                    if source_id == "daheng":
                        return "Daheng Cam 2"
                    return self.characterization_camera_select.currentText()

                def update_plate_sensor_text():
                    selection = plate_sensor_label()
                    button.setText(f"Plate Image\nSensor\n{selection}" if selection else "Plate Image\nSensor")
                    button.setToolTip(f"Plate image sensor: {selection}" if selection else "Plate image sensor")

                def update_plate_sensor_tooltip():
                    update_plate_sensor_text()

                def set_plate_sensor(source_id):
                    if not hasattr(self, "characterization_camera_select"):
                        return
                    index = self.characterization_camera_select.findData(source_id)
                    if index < 0:
                        return
                    self.characterization_camera_select.setCurrentIndex(index)
                    update_plate_sensor_tooltip()

                if hasattr(self, "characterization_camera_select"):
                    for index in range(self.characterization_camera_select.count()):
                        label = self.characterization_camera_select.itemText(index)
                        source_id = self.characterization_camera_select.itemData(index)
                        action = QAction(label, menu)
                        action.triggered.connect(lambda checked=False, value=source_id: set_plate_sensor(value))
                        menu.addAction(action)
                    self.characterization_camera_select.currentIndexChanged.connect(lambda _=None: update_plate_sensor_text())

                button.setMenu(menu)
                update_plate_sensor_text()

            self.resolution_slide_selection = getattr(self, "resolution_slide_selection", None)
            resolution_slide_options = ["R1S1L1N", "R1L1S1P"]

            def configure_resolution_slide_menu(button):
                menu = QMenu(button)

                def set_resolution_slide_selection(selection):
                    self.resolution_slide_selection = selection
                    button.setText(f"Resolution Test\nTarget: {selection}")
                    button.setToolTip(f"Resolution Test Target: {selection}")

                for option in resolution_slide_options:
                    action = QAction(option, menu)
                    action.triggered.connect(lambda checked=False, value=option: set_resolution_slide_selection(value))
                    menu.addAction(action)

                button.setMenu(menu)

            plate_sensor_btn = QPushButton("Plate Image\nSensor")
            plate_sensor_btn.setFixedSize(124, 110)
            plate_sensor_btn.setStyleSheet(plate_sensor_btn_style)
            plate_sensor_btn.setToolTip("Plate image sensor")
            configure_plate_sensor_menu(plate_sensor_btn)

            fluorescence_slide_btn = QPushButton("Fluorescence\nSlide")
            fluorescence_slide_btn.setFixedSize(124, 55)
            fluorescence_slide_btn.setStyleSheet(fluorescence_btn_style)
            fluorescence_slide_btn.setToolTip("Fluorescence Slide")

            resolution_slide_btn = QPushButton("Resolution\nTest Target")
            resolution_slide_btn.setFixedSize(124, 55)
            resolution_slide_btn.setStyleSheet(plate_sensor_btn_style)
            resolution_slide_btn.setToolTip("Resolution Test Target")
            configure_resolution_slide_menu(resolution_slide_btn)

            slide1_btn = QPushButton("Slide 1")
            slide1_btn.setFixedSize(92, 220)
            slide1_btn.setStyleSheet(slide_btn_style)
            slide1_btn.setToolTip("Slide 1")

            slide2_btn = QPushButton("Slide 2")
            slide2_btn.setFixedSize(92, 220)
            slide2_btn.setStyleSheet(slide_btn_style)
            slide2_btn.setToolTip("Slide 2")
            configure_slide_menu(slide1_btn, "Slide 1")
            configure_slide_menu(slide2_btn, "Slide 2")

            spectrometer_btn = QPushButton("Spectrometer")
            spectrometer_btn.setFixedSize(104, 104)
            spectrometer_btn.setStyleSheet(rainbow_btn_style)
            spectrometer_btn.clicked.connect(self.open_spectrometer_plot)

            power_btn = QPushButton("")
            power_btn.setFixedSize(104, 104)
            power_btn.setStyleSheet(circular_btn_style)
            power_btn.setIcon(make_gauge_icon(72))
            power_btn.setIconSize(power_btn.size() * 0.65)
            power_btn.setToolTip("Power Meter")
            power_btn.clicked.connect(self.open_power_meter_plot)

            t_btn = QPushButton("T")
            t_btn.setFixedSize(34, 34)
            t_btn.setStyleSheet(t_btn_style)
            t_btn.setToolTip("T")

            start_marker = QLabel("S", characterization_box)
            start_marker.setFixedSize(18, 18)
            start_marker.setAlignment(Qt.AlignCenter)
            start_marker.setToolTip("Starting point")
            start_marker.setStyleSheet(
                "QLabel { background: #111827; color: #ffffff; border: 2px solid #ffffff; "
                "border-radius: 9px; font-weight: 800; font-size: 10px; }"
            )
            start_marker.raise_()

            button_stack = QVBoxLayout()
            button_stack.addWidget(spectrometer_btn)
            button_stack.addSpacing(12)
            button_stack.addWidget(power_btn)

            t_button_stack = QVBoxLayout()
            t_button_stack.addStretch(1)
            t_button_stack.addWidget(t_btn)
            t_button_stack.addSpacing(8)

            plate_sensor_stack = QVBoxLayout()
            plate_sensor_stack.addWidget(plate_sensor_btn)
            plate_sensor_stack.addWidget(fluorescence_slide_btn)
            plate_sensor_stack.addWidget(resolution_slide_btn)

            characterization_panel.addStretch(1)
            characterization_panel.addLayout(plate_sensor_stack)
            characterization_panel.addSpacing(8)
            characterization_panel.addWidget(slide1_btn)
            characterization_panel.addSpacing(8)
            characterization_panel.addWidget(slide2_btn)
            characterization_panel.addSpacing(8)
            characterization_panel.addLayout(t_button_stack)
            characterization_panel.addSpacing(8)
            characterization_panel.addLayout(button_stack)
            control_stack.addWidget(characterization_box)

            def place_start_marker():
                t_pos = t_btn.mapTo(characterization_box, QPoint(0, 0))
                power_pos = power_btn.mapTo(characterization_box, QPoint(0, 0))
                x = int((t_pos.x() + t_btn.width() + power_pos.x()) / 2 - start_marker.width() / 2 + 6)
                y = int(t_pos.y() + t_btn.height() / 2 - start_marker.height() / 2 + 6)
                start_marker.move(x, y)
                start_marker.raise_()

            original_resize_event = characterization_box.resizeEvent

            def characterization_resize_event(event):
                original_resize_event(event)
                QTimer.singleShot(0, place_start_marker)

            characterization_box.resizeEvent = characterization_resize_event
            QTimer.singleShot(0, place_start_marker)

            self.slide1_btn = slide1_btn
            self.slide2_btn = slide2_btn
            self.plate_sensor_btn = plate_sensor_btn
            self.fluorescence_slide_btn = fluorescence_slide_btn
            self.resolution_slide_btn = resolution_slide_btn
            self.t_btn = t_btn
            self.start_marker = start_marker
            self.spectrometer_btn = spectrometer_btn
            self.power_meter_btn = power_btn

        # Keep fixed camera slots so downstream instrument controls do not move when cameras are missing.
        for i in range(self.camera_slot_count):
            camera_detected = i < self.cam_mgr.num_cameras
            # ------- CAMERA TITLE + PREVIEW LABEL -------
            model = ""
            if camera_detected and hasattr(self.cam_mgr, "camera_names") and i < len(self.cam_mgr.camera_names):
                model = str(self.cam_mgr.camera_names[i])

            if i == 0:
                cam_title = "Cam 1: Microscope"
            elif i == 1:
                cam_title = "Cam 2: Characterization plate"
            else:
                cam_title = f"Cam {i + 1}"
            title_suffix = f" ({model})" if model else ""
            if not camera_detected:
                title_suffix = " (camera not detected)"
            title = QLabel(cam_title + title_suffix)
            title.setStyleSheet("font-weight: 600;")

            label = QLabel("" if camera_detected else "Camera not detected")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("border:1px solid gray; background:black; color:white;")
            label.setMinimumSize(180, 80)
            label.resize(preview_w, preview_h)
            # Ignore pixmap size hints while streaming so live frames do not block window shrinking.
            label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
            label.setMouseTracking(camera_detected)
            label.setProperty("cam_index", i)
            label.installEventFilter(self)

            # Camera controls live on the preview so the lower row stays focused on camera settings.
            zoom_out_btn = QPushButton("−")
            zoom_in_btn = QPushButton("+")
            zoom_reset_btn = QPushButton("⟳")
            ss_btn = QPushButton("▣")
            rec_btn = QPushButton("●")
            zoom_lbl = QLabel("1.0x")
            self.zoom_labels[i] = zoom_lbl

            overlay_button_style = (
                "QPushButton { background: rgba(255, 255, 255, 210); color: #111; "
                "border: 1px solid rgba(0, 0, 0, 110); border-radius: 13px; "
                "font-weight: 700; font-size: 15px; } "
                "QPushButton:hover { background: rgba(232, 240, 255, 235); } "
                "QPushButton:pressed { background: rgba(207, 224, 255, 245); } "
                "QPushButton:disabled { color: #888; background: rgba(230, 230, 230, 180); }"
            )
            for btn, tip in (
                (zoom_out_btn, "Zoom out"),
                (zoom_in_btn, "Zoom in"),
                (zoom_reset_btn, "Reset zoom"),
                (ss_btn, "Screenshot"),
            ):
                btn.setFixedSize(28, 28)
                btn.setToolTip(tip)
                btn.setStyleSheet(overlay_button_style)
            rec_btn.setFixedSize(28, 28)
            rec_btn.setToolTip("Record video")
            rec_btn.setStyleSheet(
                "QPushButton { background: rgba(255, 255, 255, 220); color: #dc2626; "
                "border: 1px solid rgba(220, 38, 38, 180); border-radius: 13px; "
                "font-weight: 900; font-size: 16px; } "
                "QPushButton:hover { background: rgba(254, 226, 226, 245); } "
                "QPushButton:pressed { background: rgba(254, 202, 202, 245); } "
                "QPushButton:disabled { color: #999; background: rgba(230, 230, 230, 180); }"
            )

            zoom_lbl.setFixedHeight(28)
            zoom_lbl.setMinimumWidth(46)
            zoom_lbl.setAlignment(Qt.AlignCenter)
            zoom_lbl.setStyleSheet(
                "QLabel { background: rgba(0, 0, 0, 145); color: white; "
                "border-radius: 10px; padding: 2px 6px; font-weight: 600; }"
            )

            zoom_out_btn.clicked.connect(lambda _, c=i: self.adjust_zoom(c, 1 / 1.25))
            zoom_in_btn.clicked.connect(lambda _, c=i: self.adjust_zoom(c, 1.25))
            zoom_reset_btn.clicked.connect(lambda _, c=i: self.reset_zoom(c))
            ss_btn.clicked.connect(lambda _, c=i: self._on_screenshot(c))
            def toggle_rec(cam_index=i, btn=rec_btn):
                if cam_index >= self.cam_mgr.num_cameras:
                    return
                if not self.cam_mgr.recording[cam_index]:
                    self.cam_mgr.start_recording(cam_index)
                    btn.setText("■")
                    btn.setToolTip("Stop recording")
                    btn.setStyleSheet(
                        "QPushButton { background: rgba(220, 38, 38, 235); color: white; "
                        "border: 2px solid rgba(127, 29, 29, 220); border-radius: 13px; "
                        "font-weight: 900; font-size: 15px; } "
                        "QPushButton:hover { background: rgba(185, 28, 28, 245); }"
                    )
                else:
                    self.cam_mgr.stop_recording(cam_index)
                    btn.setText("●")
                    btn.setToolTip("Record video")
                    btn.setStyleSheet(
                        "QPushButton { background: rgba(255, 255, 255, 220); color: #dc2626; "
                        "border: 1px solid rgba(220, 38, 38, 180); border-radius: 13px; "
                        "font-weight: 900; font-size: 16px; } "
                        "QPushButton:hover { background: rgba(254, 226, 226, 245); } "
                        "QPushButton:pressed { background: rgba(254, 202, 202, 245); } "
                        "QPushButton:disabled { color: #999; background: rgba(230, 230, 230, 180); }"
                    )
            rec_btn.clicked.connect(toggle_rec)

            zoom_overlay = QWidget()
            zoom_overlay.setAttribute(Qt.WA_TranslucentBackground)
            zoom_overlay_layout = QHBoxLayout(zoom_overlay)
            zoom_overlay_layout.setContentsMargins(6, 6, 6, 6)
            zoom_overlay_layout.setSpacing(5)
            zoom_overlay_layout.addWidget(zoom_out_btn)
            zoom_overlay_layout.addWidget(zoom_in_btn)
            zoom_overlay_layout.addWidget(zoom_reset_btn)
            zoom_overlay_layout.addWidget(ss_btn)
            zoom_overlay_layout.addWidget(rec_btn)
            zoom_overlay_layout.addWidget(zoom_lbl)

            view_container = QWidget()
            view_container.setMinimumSize(180, 80)
            view_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            view_layout = QGridLayout(view_container)
            view_layout.setContentsMargins(0, 0, 0, 0)
            view_layout.setSpacing(0)
            view_layout.addWidget(label, 0, 0)
            view_layout.addWidget(zoom_overlay, 0, 0, Qt.AlignTop | Qt.AlignRight)

            cam_box = QVBoxLayout()
            cam_box.addWidget(title)
            cam_box.addWidget(view_container)
            cam_box.setStretch(0, 0)
            cam_box.setStretch(1, 1)
            self.grid.addLayout(cam_box, i // cols * 2, i % cols)
            self.grid.setRowStretch(i // cols * 2, 1)
            self.grid.setRowStretch(i // cols * 2 + 1, 0)

            self.cam_labels.append(label)
            self.cam_title_labels.append(title)

            # ------- CONTROL PANEL -------
            # do 2 rows for the control panel
            panel = QHBoxLayout()
            panel.setContentsMargins(0, 0, 0, 0)
            panel.setSpacing(14)
            panel2 = QHBoxLayout()
            panel2.setContentsMargins(0, 0, 0, 0)
            panel2.setSpacing(6)

            # Exposure input (µs)
            exp_input = QDoubleSpinBox()
            exp_input.setDecimals(2)
            exp_input.setKeyboardTracking(False)

            exp_rng = self.cam_mgr.get_exposure_range(i) if camera_detected else None
            if exp_rng:
                exp_input.setRange(float(exp_rng["min"]), float(exp_rng["max"]))
                # Daheng typically uses µs; let user type any value, step is convenience only
                exp_input.setSingleStep(1000.0)
            else:
                exp_input.setRange(0.0, 1e9)
                exp_input.setSingleStep(1000.0)

            exp_input.setValue(float(self.cam_mgr.get_exposure(i)) if camera_detected else 0.0)
            exp_apply = QPushButton("Set Exp")
            exp_apply.clicked.connect(lambda _, c=i, w=exp_input: self.apply_exposure(c, w))

            exp_label = QLabel("Exposure (us):")
            exp_label.setFixedWidth(92)
            exp_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            exp_input.setFixedWidth(110)
            exp_apply.setFixedWidth(64)
            exp_group = QHBoxLayout()
            exp_group.setContentsMargins(0, 0, 0, 0)
            exp_group.setSpacing(4)
            exp_group.addWidget(exp_label)
            exp_group.addWidget(exp_input)
            exp_group.addWidget(exp_apply)
            panel.addLayout(exp_group)
            self.exposure_inputs.append(exp_input)

            # Gain input
            gain_input = QDoubleSpinBox()
            gain_input.setDecimals(2)
            gain_input.setKeyboardTracking(False)

            gain_rng = self.cam_mgr.get_gain_range(i) if camera_detected else None
            if gain_rng:
                gain_input.setRange(float(gain_rng["min"]), float(gain_rng["max"]))
                gain_input.setSingleStep(0.5)
            else:
                gain_input.setRange(0.0, 100.0)
                gain_input.setSingleStep(0.5)

            gain_input.setValue(float(self.cam_mgr.get_gain(i)) if camera_detected else 0.0)
            gain_apply = QPushButton("Set Gain")
            gain_apply.clicked.connect(lambda _, c=i, w=gain_input: self.apply_gain(c, w))

            gain_label = QLabel("Gain:")
            gain_label.setFixedWidth(42)
            gain_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            gain_input.setFixedWidth(90)
            gain_apply.setFixedWidth(68)
            gain_group = QHBoxLayout()
            gain_group.setContentsMargins(0, 0, 0, 0)
            gain_group.setSpacing(4)
            gain_group.addWidget(gain_label)
            gain_group.addWidget(gain_input)
            gain_group.addWidget(gain_apply)
            panel.addLayout(gain_group)
            panel.addStretch(1)
            self.gain_inputs.append(gain_input)

            if i == 1:
                self.characterization_camera_select = QComboBox()
                self.characterization_camera_select.addItem("Daheng / current Cam 2", "daheng")
                self.characterization_camera_select.addItem("DMK 27BUP031", "dmk:0")
                char_index = self.characterization_camera_select.findData(self.characterization_camera_source)
                self.characterization_camera_select.setCurrentIndex(max(0, char_index))
                self.characterization_camera_select.currentIndexChanged.connect(self.on_characterization_camera_changed)

            self.camera_control_widgets.append(
                {
                    "zoom_out": zoom_out_btn,
                    "zoom_in": zoom_in_btn,
                    "zoom_reset": zoom_reset_btn,
                    "zoom_label": zoom_lbl,
                    "exposure_input": exp_input,
                    "exposure_apply": exp_apply,
                    "gain_input": gain_input,
                    "gain_apply": gain_apply,
                    "screenshot": ss_btn,
                    "record": rec_btn,
                }
            )

            control_stack = QVBoxLayout()
            control_stack.addLayout(panel)
            control_stack.addLayout(panel2)

            if i == 1:
                add_characterization_controls(control_stack)

            self.grid.addLayout(control_stack, i // cols * 2 + 1, i % cols)
            self.control_panels.append(panel)

        # Top area: camera grid + C# stage status/log
        top_layout = QHBoxLayout()
        top_layout.addLayout(self.grid, 3)
        stage_panel = QVBoxLayout()
        stage_controls_box = QGroupBox("Controls")
        stage_controls_box.setMinimumWidth(220)
        stage_controls_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        stage_controls_box.setStyleSheet(
            "QGroupBox { font-weight: 600; border: 1px solid #8a8a8a; border-radius: 5px; "
            "margin-top: 8px; padding-top: 10px; background: #f7f7f7; } "
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
        )
        self.stage_controls_layout = QVBoxLayout(stage_controls_box)
        self.stage_controls_layout.setContentsMargins(8, 12, 8, 8)
        self.stage_controls_layout.setSpacing(6)
        stage_panel.addWidget(self.preview_status)
        stage_panel.addWidget(stage_controls_box)
        stage_panel.addWidget(self.stage_log)
        stage_panel.setStretch(0, 0)
        stage_panel.setStretch(1, 1)
        stage_panel.setStretch(2, 1)
        top_layout.addLayout(stage_panel, 2)

        self.layout.addLayout(top_layout)
        self.setLayout(self.layout)

        # Set a comfortable initial size; child widgets remain resizable.
        win_w = cols * preview_w + self.stage_log.width() + 80
        win_h = rows * (preview_h + caption_h + control_h) + bottom_panel_h
        self.resize(win_w, win_h)


        # - -   -   -   -
        #Bottom panel for routine, Autofocus, ZeroMQ
        # -     -   -   -
        #stage_routine_panel for stage routine, resume step
        stage_routine_panel = QHBoxLayout()
        #autofocus_panel for autofocus, score, n, score button, capture frame button
        autofocus_panel = QHBoxLayout()
        # Backend/stage command controls live in the right-side controls panel.
        backend_panel = QHBoxLayout()
        stage_connection_panel = QHBoxLayout()
        command_panel = QHBoxLayout()
        command_target_panel = QHBoxLayout()
        
        # Convenience: allow user to go to individual instruments using StageRoutine
        self.cmd_select = QComboBox()
        self.cmd_select.addItems([
            "RunToAlign",
            "RunToFlr",
            "RunToEmpty",
            "RunToImg",
            "RunToPSF",
            "RunToSpectrom",
            "RunToPwr",
            "RunToSlide",
            "AutoFocusRes",
        ])
        self.cmd_select.setMinimumWidth(112)
        self.cmd_select.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.axis_spin = QSpinBox()
        self.axis_spin.setRange(0, 5)
        self.axis_spin.setValue(0)
        self.axis_spin.setFixedWidth(46)

        self.target_spin = QDoubleSpinBox()
        self.target_spin.setDecimals(4)
        self.target_spin.setRange(-50000.0, 50000.0)
        self.target_spin.setSingleStep(0.1)
        self.target_spin.setKeyboardTracking(False)
        self.target_spin.setValue(0.0)
        self.target_spin.setFixedWidth(82)

        send_btn = QPushButton("Send Command")
        send_btn.clicked.connect(self.send_zmq_command)
        send_btn.setText("Send")
        send_btn.setFixedWidth(58)

        # ---- Focus scoring tool (noise check) ----
        score_cam_select = QComboBox()
        if self.cam_mgr.num_cameras:
            score_cam_select.addItems([f"Cam {i+1}" for i in range(self.cam_mgr.num_cameras)])
            score_cam_select.setCurrentIndex(0)
        else:
            score_cam_select.addItem("No camera detected")
            score_cam_select.setEnabled(False)
        score_cam_select.setMinimumWidth(74)
        self.score_cam_select = score_cam_select

        score_n = QSpinBox()
        score_n.setRange(1, 50)
        score_n.setValue(5)
        score_n.setFixedWidth(46)
        self.score_n = score_n

        score_btn = QPushButton("Score")
        score_btn.clicked.connect(self.score_current_frame)
        score_btn.setEnabled(self.cam_mgr.num_cameras > 0)
        score_btn.setFixedWidth(58)
        self.score_btn = score_btn

        #013026 add these buttons for the stageRoutine
        # ---- Stage Routine Controls ----
        setStageSequence_btn = QPushButton("Set Stage Sequence")
        setProjectionSettings_btn = QPushButton("Set Projection Settings")
        startRoutine_btn = QPushButton("Start Characterization")
        resumeRoutine_btn = QPushButton("Resume")
        resumePauseMode_check = QCheckBox("Enable Resume")
        resumePauseMode_check.setChecked(True)
        resumePauseMode_check.setToolTip("Checked pauses after each characterization stop so Resume is required. Unchecked runs through the sequence automatically.")
        autofocus_btn = QPushButton("Autofocus")
        cancel_af_btn = QPushButton("Cancel AF")
        for sequence_btn in (setStageSequence_btn, setProjectionSettings_btn, startRoutine_btn, resumeRoutine_btn):
            sequence_btn.setMinimumWidth(136)
            sequence_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        resumePauseMode_check.setMinimumWidth(136)
        resumePauseMode_check.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        autofocus_btn.setEnabled(self.cam_mgr.num_cameras > 0)
        cancel_af_btn.setEnabled(False)

        startRoutine_btn.clicked.connect(self.start_stage_routine)
        setStageSequence_btn.clicked.connect(self.open_stage_sequence_editor)
        setProjectionSettings_btn.clicked.connect(self.open_projection_settings_editor)
        resumeRoutine_btn.clicked.connect(self.resume_stage_routine)
        resumePauseMode_check.stateChanged.connect(lambda _=None: self._refresh_resume_button_state())
        autofocus_btn.clicked.connect(lambda: self.start_autofocus(cam_index=0))
        cancel_af_btn.clicked.connect(self.cancel_autofocus)

        stage_sequence_buttons = QGridLayout()
        stage_sequence_buttons.setContentsMargins(0, 0, 0, 0)
        stage_sequence_buttons.setHorizontalSpacing(6)
        stage_sequence_buttons.setVerticalSpacing(4)
        stage_sequence_buttons.addWidget(setStageSequence_btn, 0, 0)
        stage_sequence_buttons.addWidget(setProjectionSettings_btn, 0, 1)
        stage_sequence_buttons.addWidget(startRoutine_btn, 1, 0)
        stage_sequence_buttons.addWidget(resumeRoutine_btn, 1, 1)
        stage_sequence_buttons.addWidget(resumePauseMode_check, 1, 2)
        stage_sequence_buttons.setColumnStretch(0, 1)
        stage_sequence_buttons.setColumnStretch(1, 1)
        stage_sequence_buttons.setColumnStretch(2, 1)
        stage_routine_panel.addLayout(stage_sequence_buttons)
        stage_routine_panel.addStretch(1)
        autofocus_panel.addWidget(autofocus_btn)
        autofocus_panel.addWidget(cancel_af_btn)
        autofocus_panel.addWidget(QLabel("Score:"))
        autofocus_panel.addWidget(score_cam_select)
        autofocus_panel.addWidget(QLabel("N:"))
        autofocus_panel.addWidget(score_n)
        autofocus_panel.addWidget(score_btn)

        self.autofocus_btn = autofocus_btn
        self.cancel_af_btn = cancel_af_btn
        self.resumeRoutine_btn = resumeRoutine_btn
        self.setStageSequence_btn = setStageSequence_btn
        self.setProjectionSettings_btn = setProjectionSettings_btn
        self.startRoutine_btn = startRoutine_btn
        self.resumePauseMode_check = resumePauseMode_check
        self._refresh_camera_ui_state()
        self._refresh_resume_button_state()



        # ---- Connect/Disconnect ----
        self.connect_btn = QPushButton("Connect Stage")
        self.disconnect_btn = QPushButton("Disconnect Stage")
        self.status_label = QLabel("Disconnected")
        self.backend_select = QComboBox()
        self.backend_select.addItem(BACKEND_LABELS[BACKEND_NATIVE], BACKEND_NATIVE)
        self.backend_select.addItem(BACKEND_LABELS[BACKEND_PYCRO], BACKEND_PYCRO)
        backend_index = self.backend_select.findData(self.hardware_backend)
        self.backend_select.setCurrentIndex(max(0, backend_index))
        self.backend_select.currentIndexChanged.connect(self.on_backend_changed)
        self.backend_select.setMinimumWidth(104)
        self.backend_select.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.status_label.setWordWrap(False)
        self.status_label.setMinimumWidth(230)
        self.status_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.connect_btn.clicked.connect(self.connect_zmq)
        self.disconnect_btn.clicked.connect(self.disconnect_zmq)

        # ---- Layout ----
        backend_panel.addWidget(QLabel("Backend:"))
        backend_panel.addWidget(self.backend_select)
        backend_panel.addStretch(1)

        stage_connection_panel.addWidget(self.connect_btn)
        stage_connection_panel.addWidget(self.disconnect_btn)
        stage_connection_panel.addWidget(self.status_label)
        stage_connection_panel.addStretch(1)

        command_panel.addWidget(QLabel("Stage Command:"))
        command_panel.addWidget(self.cmd_select)
        command_panel.addStretch(1)

        command_target_panel.addWidget(QLabel("Axis:"))
        command_target_panel.addWidget(self.axis_spin)
        command_target_panel.addWidget(QLabel("Target:"))
        command_target_panel.addWidget(self.target_spin)
        command_target_panel.addWidget(send_btn)
        command_target_panel.addStretch(1)

        for row in (stage_routine_panel, autofocus_panel, backend_panel, stage_connection_panel, command_panel, command_target_panel):
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            self.stage_controls_layout.addLayout(row)
        self.stage_controls_layout.addStretch(1)
        self.layout.setStretch(0, 1)

        # Timer to update frames
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frames)
        self.timer.start(30)

        #013026 add this for stageRoutine
        self.stage_routine = StageRoutine(
            send_move_callback=self.send_stage_move,
            log_callback=print  # for now, just print to console
        )

    def _camera_title(self, cam_index: int, camera_detected: bool) -> str:
        if cam_index == 0:
            cam_title = "Cam 1: Microscope"
        elif cam_index == 1:
            cam_title = "Cam 2: Characterization plate"
        else:
            cam_title = f"Cam {cam_index + 1}"

        if camera_detected and hasattr(self.cam_mgr, "camera_names") and cam_index < len(self.cam_mgr.camera_names):
            model = str(self.cam_mgr.camera_names[cam_index])
            return cam_title + (f" ({model})" if model else "")
        return cam_title + " (camera not detected)"

    def _set_camera_controls_enabled(self, cam_index: int, enabled: bool):
        if cam_index >= len(self.camera_control_widgets):
            return
        widgets = self.camera_control_widgets[cam_index]
        for key in (
            "zoom_out",
            "zoom_in",
            "zoom_reset",
            "exposure_input",
            "exposure_apply",
            "gain_input",
            "gain_apply",
            "screenshot",
            "record",
        ):
            widgets[key].setEnabled(enabled)
        gain_supported = enabled
        if enabled and hasattr(self.cam_mgr, "is_gain_supported"):
            try:
                gain_supported = bool(self.cam_mgr.is_gain_supported(cam_index))
            except Exception:
                gain_supported = enabled
        widgets["gain_input"].setEnabled(gain_supported)
        widgets["gain_apply"].setEnabled(gain_supported)
        widgets["zoom_label"].setText("1.0x" if enabled else "--")

    def _refresh_score_camera_choices(self):
        if not hasattr(self, "score_cam_select"):
            return
        self.score_cam_select.blockSignals(True)
        self.score_cam_select.clear()
        if self.cam_mgr.num_cameras:
            self.score_cam_select.addItems([f"Cam {i + 1}" for i in range(min(self.cam_mgr.num_cameras, self.camera_slot_count))])
            self.score_cam_select.setCurrentIndex(0)
            self.score_cam_select.setEnabled(True)
            self.score_btn.setEnabled(True)
            self.autofocus_btn.setEnabled(True)
        else:
            self.score_cam_select.addItem("No camera detected")
            self.score_cam_select.setEnabled(False)
            self.score_btn.setEnabled(False)
            self.autofocus_btn.setEnabled(False)
        self.score_cam_select.blockSignals(False)

    def _refresh_camera_ui_state(self):
        if hasattr(self, "characterization_camera_select"):
            self.characterization_camera_select.setEnabled(self.hardware_backend == BACKEND_NATIVE)

        for i, label in enumerate(self.cam_labels):
            camera_detected = i < self.cam_mgr.num_cameras
            self.cam_title_labels[i].setText(self._camera_title(i, camera_detected))
            label.setMouseTracking(camera_detected)
            if not camera_detected:
                label.clear()
                label.setText("Camera not detected")
            else:
                label.setText("")
            self._set_camera_controls_enabled(i, camera_detected)

            if i < len(self.exposure_inputs):
                self.exposure_inputs[i].setValue(float(self.cam_mgr.get_exposure(i)) if camera_detected else 0.0)
            if i < len(self.gain_inputs):
                self.gain_inputs[i].setValue(float(self.cam_mgr.get_gain(i)) if camera_detected else 0.0)

        self._refresh_score_camera_choices()

    def on_characterization_camera_changed(self, _index=None):
        if self.hardware_backend != BACKEND_NATIVE:
            return
        if not hasattr(self, "characterization_camera_select"):
            return

        source_id = self.characterization_camera_select.currentData()
        if source_id == self.characterization_camera_source:
            return

        if not hasattr(self.cam_mgr, "set_characterization_source"):
            self.append_local_log("[Camera] current manager does not support Cam 2 source switching")
            return

        try:
            self.characterization_camera_source = source_id
            self.cam_mgr.set_characterization_source(source_id)
            self.view_states[1] = {"zoom": 1.0, "cx": 0.5, "cy": 0.5}
            self.last_frame_sizes[1] = None
            self._refresh_camera_ui_state()
            self.append_local_log(
                f"[Camera] Cam 2 source selected: {self.characterization_camera_select.currentText()}"
            )
        except Exception as e:
            self.append_local_log(f"[Camera] failed to select Cam 2 source: {e}")
            self.characterization_camera_source = "daheng"
            try:
                self.cam_mgr.set_characterization_source("daheng")
            except Exception:
                pass
            self.characterization_camera_select.blockSignals(True)
            self.characterization_camera_select.setCurrentIndex(0)
            self.characterization_camera_select.blockSignals(False)
            self._refresh_camera_ui_state()

    def on_backend_changed(self, _index=None):
        backend = self.backend_select.currentData()
        if backend == self.hardware_backend:
            return

        if self.zmq_thread or self.zmq_events:
            self.disconnect_zmq()

        try:
            self.cam_mgr.close()
        except Exception:
            pass

        self.hardware_backend = backend
        self.stage_host, self.stage_cmd_port, self.stage_event_port = self._stage_ports_for_backend(backend)
        self.stage_event_queue = queue.Queue(maxsize=2000)
        with self._stage_seq_lock:
            self._stage_last_seq = 0
        self.cam_mgr = self._create_camera_manager(backend)
        self._refresh_camera_ui_state()
        self.stage_status.setText(f"{self._stage_status_prefix()}: backend selected")
        self.append_local_log(
            f"[Backend] selected {BACKEND_LABELS.get(backend, backend)} "
            f"(stage tcp://{self.stage_host}:{self.stage_cmd_port}, events {self.stage_event_port})"
        )

    def eventFilter(self, obj, event):
        # Mouse-wheel zoom + cursor tracking on each preview label
        cam_index = obj.property("cam_index") if hasattr(obj, "property") else None
        if cam_index is None:
            return super().eventFilter(obj, event)

        cam_index = int(cam_index)
        if cam_index >= self.cam_mgr.num_cameras:
            return False

        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self.last_mouse_pos[cam_index] = event.pos()
            if float(self.view_states[cam_index]["zoom"]) > 1.000001:
                self.pan_active[cam_index] = True
                self.pan_last_pos[cam_index] = event.pos()
                obj.setCursor(Qt.ClosedHandCursor)
                return True
            obj.setCursor(Qt.OpenHandCursor)
            return False

        if event.type() == QEvent.MouseMove:
            self.last_mouse_pos[cam_index] = event.pos()
            if self.pan_active[cam_index]:
                self.pan_camera_view(cam_index, event.pos())
                return True
            if float(self.view_states[cam_index]["zoom"]) > 1.000001:
                obj.setCursor(Qt.OpenHandCursor)
            else:
                obj.unsetCursor()
            return False

        if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            self.pan_active[cam_index] = False
            self.pan_last_pos[cam_index] = None
            if float(self.view_states[cam_index]["zoom"]) > 1.000001:
                obj.setCursor(Qt.OpenHandCursor)
            else:
                obj.unsetCursor()
            return True

        if event.type() == QEvent.Leave:
            if not self.pan_active[cam_index]:
                obj.unsetCursor()
            return False

        if event.type() == QEvent.Wheel:
            dy = event.angleDelta().y()
            if dy == 0:
                return True

            steps = dy / 120.0
            factor = float(1.25 ** steps)
            self.zoom_at_label_pos(cam_index, factor, event.pos())
            if float(self.view_states[cam_index]["zoom"]) > 1.000001:
                obj.setCursor(Qt.OpenHandCursor)
            else:
                obj.unsetCursor()
            return True

        return super().eventFilter(obj, event)

    def pan_camera_view(self, cam_index, label_pos):
        prev = self.pan_last_pos[cam_index]
        if prev is None or label_pos is None:
            self.pan_last_pos[cam_index] = label_pos
            return

        state = self.view_states[cam_index]
        z = float(state["zoom"])
        if z <= 1.000001:
            self.pan_last_pos[cam_index] = label_pos
            return

        label = self.cam_labels[cam_index]
        pm_rect = self._get_pixmap_rect_in_label(label)
        if pm_rect is None:
            self.pan_last_pos[cam_index] = label_pos
            return
        _off_x, _off_y, pm_w, pm_h = pm_rect
        if pm_w <= 0 or pm_h <= 0:
            self.pan_last_pos[cam_index] = label_pos
            return

        dx = float(label_pos.x() - prev.x())
        dy = float(label_pos.y() - prev.y())
        view_w = 1.0 / z
        view_h = 1.0 / z

        cx = float(state["cx"]) - dx / float(pm_w) * view_w
        cy = float(state["cy"]) - dy / float(pm_h) * view_h
        half_w = view_w / 2.0
        half_h = view_h / 2.0
        state["cx"] = max(half_w, min(1.0 - half_w, cx))
        state["cy"] = max(half_h, min(1.0 - half_h, cy))
        self.pan_last_pos[cam_index] = label_pos

    def adjust_zoom(self, cam_index, multiplier):
        self.zoom_at_label_pos(cam_index, float(multiplier), self.last_mouse_pos[cam_index])

    def reset_zoom(self, cam_index):
        self.view_states[cam_index] = {"zoom": 1.0, "cx": 0.5, "cy": 0.5}
        self._update_zoom_label(cam_index)

    def _update_zoom_label(self, cam_index):
        lbl = self.zoom_labels[cam_index]
        if not lbl:
            return
        z = float(self.view_states[cam_index]["zoom"])
        if abs(z - 1.0) < 1e-6:
            lbl.setText("1.0x")
        else:
            lbl.setText(f"{z:.2f}x")

    def _get_pixmap_rect_in_label(self, label: QLabel):
        pm = label.pixmap()
        if pm is None:
            return None
        pm_w = pm.width()
        pm_h = pm.height()
        if pm_w <= 0 or pm_h <= 0:
            return None
        off_x = int((label.width() - pm_w) / 2)
        off_y = int((label.height() - pm_h) / 2)
        return off_x, off_y, pm_w, pm_h

    def zoom_at_label_pos(self, cam_index, factor, label_pos):
        state = self.view_states[cam_index]
        z_old = float(state["zoom"])
        z_new = max(1.0, z_old * float(factor))

        # Remove fixed 8x cap, but avoid degenerate crops by enforcing a minimum crop size.
        wh = self.last_frame_sizes[cam_index]
        if wh is not None:
            w, h = wh
            min_crop = 20
            max_zoom = max(1.0, min(w / float(min_crop), h / float(min_crop)))
            if z_new > max_zoom:
                z_new = max_zoom

        label = self.cam_labels[cam_index]
        pm_rect = self._get_pixmap_rect_in_label(label)

        # If we don't have a pixmap yet (or cursor not provided), zoom around center.
        if pm_rect is None or label_pos is None:
            u_view = 0.5
            v_view = 0.5
        else:
            off_x, off_y, pm_w, pm_h = pm_rect
            x = float(label_pos.x()) - off_x
            y = float(label_pos.y()) - off_y
            if x < 0 or y < 0 or x >= pm_w or y >= pm_h:
                u_view = 0.5
                v_view = 0.5
            else:
                u_view = x / float(pm_w)
                v_view = y / float(pm_h)

        # Compute the source normalized coordinate currently under cursor
        cx = float(state["cx"])
        cy = float(state["cy"])
        w_old = 1.0 / z_old
        h_old = 1.0 / z_old
        px = cx + (u_view - 0.5) * w_old
        py = cy + (v_view - 0.5) * h_old

        # Choose new center so px/py stays under cursor in new zoom
        w_new = 1.0 / z_new
        h_new = 1.0 / z_new
        cx_new = px - (u_view - 0.5) * w_new
        cy_new = py - (v_view - 0.5) * h_new

        # Clamp center so view window stays within bounds
        half_w = w_new / 2.0
        half_h = h_new / 2.0
        cx_new = max(half_w, min(1.0 - half_w, cx_new))
        cy_new = max(half_h, min(1.0 - half_h, cy_new))

        state["zoom"] = z_new
        state["cx"] = cx_new
        state["cy"] = cy_new
        self._update_zoom_label(cam_index)

    def apply_zoom(self, frame, cam_index):
        if frame is None:
            return frame

        state = self.view_states[cam_index]
        z = float(state["zoom"])
        if z <= 1.000001:
            return frame

        h, w = frame.shape[:2]
        min_crop = 20
        max_zoom = max(1.0, min(w / float(min_crop), h / float(min_crop)))
        if z > max_zoom:
            z = max_zoom
            state["zoom"] = z
            self._update_zoom_label(cam_index)

        crop_w = max(min_crop, int(round(w / z)))
        crop_h = max(min_crop, int(round(h / z)))

        cx = float(state["cx"]) * w
        cy = float(state["cy"]) * h
        x1 = int(round(cx - crop_w / 2.0))
        y1 = int(round(cy - crop_h / 2.0))
        x1 = max(0, min(w - crop_w, x1))
        y1 = max(0, min(h - crop_h, y1))
        x2 = x1 + crop_w
        y2 = y1 + crop_h

        cropped = frame[y1:y2, x1:x2]
        if cropped.size == 0:
            return frame
        return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)

    def apply_exposure(self, cam_index, widget: QDoubleSpinBox):
        if cam_index < 0 or cam_index >= self.cam_mgr.num_cameras:
            self.append_local_log(f"[Camera] cam={cam_index+1} not available")
            return
        desired = float(widget.value())
        ok, applied = self.cam_mgr.set_exposure(cam_index, desired)
        # reflect clamping / rejection in UI without crashing
        widget.blockSignals(True)
        widget.setValue(float(applied))
        widget.blockSignals(False)
        if not ok:
            print(f"[UI] Exposure rejected cam{cam_index}, kept {applied}")

    def apply_gain(self, cam_index, widget: QDoubleSpinBox):
        if cam_index < 0 or cam_index >= self.cam_mgr.num_cameras:
            self.append_local_log(f"[Camera] cam={cam_index+1} not available")
            return
        desired = float(widget.value())
        ok, applied = self.cam_mgr.set_gain(cam_index, desired)
        widget.blockSignals(True)
        widget.setValue(float(applied))
        widget.blockSignals(False)
        if not ok:
            print(f"[UI] Gain rejected cam{cam_index}, kept {applied}")

    def on_stage_event(self, msg: str):
        # Called on the Qt thread via StageEventBus
        try:
            data = json.loads(msg)
        except Exception:
            line = f"{self._now_hhmmss()} raw: {msg}"
            self.stage_status.setText(f"{self._stage_status_prefix()}: {line}")
            self.stage_log.appendPlainText(line)
            return

        evt = str(data.get("event", "") or "")
        cmd = str(data.get("command", "") or "")
        ts = data.get("ts_utc_ms")

        # During autofocus, suppress noisy per-move stage events (AF prints its own lines).
        if self.af_thread and self.af_thread.is_alive():
            if evt in {"CommandStarted", "CommandCompleted"} and cmd == "MoveToXYZ":
                return

        # Filter noisy events by default
        if evt in {"CommandQueued", "CommandReceived"}:
            return

        payload = data.get("payload")
        message = data.get("message")

        extras = ""
        if isinstance(payload, dict):
            if "X" in payload or "Y" in payload or "Z" in payload:
                try:
                    x = float(payload.get("X"))
                    y = float(payload.get("Y"))
                    z = float(payload.get("Z"))
                    extras = f" x={x:.3f} y={y:.3f} z={z:.3f}"
                except Exception:
                    extras = f" x={payload.get('X')} y={payload.get('Y')} z={payload.get('Z')}"
            elif "axis" in payload or "target" in payload:
                extras = f" axis={payload.get('axis')} target={payload.get('target')}"
            elif "pos" in payload:
                extras = f" axis={payload.get('axis')} pos={payload.get('pos')}"

        if message:
            extras = (extras + f" msg={message}").strip()

        t = self._fmt_ts(ts)
        line = f"{t} {evt} {cmd}{extras}".strip()
        self.stage_status.setText(f"{self._stage_status_prefix()}: {line}")
        self.stage_log.appendPlainText(line)

        # Add a blank line after completion/errors to improve readability
        if evt in {"CommandCompleted", "CommandError", "ParseError", "PositionError"}:
            self.stage_log.appendPlainText("")
        elif evt in {"Position", "StopRun", "ServerStarted", "ServerStopped"}:
            self.stage_log.appendPlainText("")

        routine_waiting = bool(getattr(self.stage_routine, "awaiting_step_completion", False))
        stage_move_completed = evt == "CommandCompleted" and (cmd == "MoveToXYZ" or routine_waiting)
        if stage_move_completed:
            if not self._handle_completed_stage_stop_actions():
                self.stage_routine.StepCompleted()

    def _now_hhmmss(self):
        return datetime.now().strftime("%H:%M:%S")

    def _fmt_ts(self, ts_utc_ms):
        try:
            ms = int(ts_utc_ms)
            dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).astimezone()
            return dt.strftime("%H:%M:%S.%f")[:-3]
        except Exception:
            return self._now_hhmmss()

    def send_zmq_command(self):
        if not (self.zmq_thread and self.zmq_thread.running):
            print("[ZMQ] Not connected.")
            return

        command = self.cmd_select.currentText()

        # Local StageRoutine helpers (still send ZMQ MoveToXYZ under the hood)
        if command in {
            "RunToAlign",
            "RunToFlr",
            "RunToEmpty",
            "RunToImg",
            "RunToPSF",
            "RunToSpectrom",
            "RunToPwr",
            "RunToSlide",
        }:
            getattr(self.stage_routine, command)()
            return
        if command == "AutoFocusRes":
            self.start_autofocus(cam_index=0)
            return

        # Build JSON
        if command == "RunToTarget":
            axis = int(self.axis_spin.value())
            msg = {
                "command": "RunToTarget",
                "axis": axis,
                "target": float(self.target_spin.value())
            }
        elif command == "GetCurrentPosition":
            msg = {"command": "GetCurrentPosition"}
        else:
            msg = {"command": command}

        json_msg = json.dumps(msg)
        self.zmq_thread.send_message(json_msg)

    def update_frames(self):
        # Display each camera live feed
        for i in range(self.cam_mgr.num_cameras):
            frame = self.cam_mgr.get_frame(i)
            if frame is None:
                continue
            now = time.monotonic()
            frame_id = None
            if hasattr(self.cam_mgr, "get_frame_counter"):
                try:
                    frame_id = self.cam_mgr.get_frame_counter(i)
                except Exception:
                    frame_id = None

            should_update_fps = frame_id is None or frame_id != self.frame_last_ids[i]
            if should_update_fps:
                last_ts = self.frame_last_ts[i]
                if last_ts is not None:
                    dt = max(1e-6, now - last_ts)
                    instant_fps = 1.0 / dt
                    prev = float(self.frame_fps[i])
                    self.frame_fps[i] = instant_fps if prev <= 0.0 else (0.85 * prev + 0.15 * instant_fps)
                self.frame_last_ts[i] = now
                self.frame_last_ids[i] = frame_id

            h0, w0 = frame.shape[:2]
            self.last_frame_sizes[i] = (w0, h0)
            frame = self.apply_zoom(frame, i)

            # Convert BGR → RGB for Qt
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape

            qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
            pix = QPixmap.fromImage(qimg)

            target_size = self.cam_labels[i].size()
            if target_size.width() <= 0 or target_size.height() <= 0:
                continue

            scaled = pix.scaled(target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            canvas = QPixmap(target_size)
            canvas.fill(QColor(0, 0, 0))
            painter = QPainter(canvas)
            x = int((target_size.width() - scaled.width()) / 2)
            y = int((target_size.height() - scaled.height()) / 2)
            painter.drawPixmap(x, y, scaled)
            fps_text = f"{self.frame_fps[i]:.1f} fps" if self.frame_fps[i] > 0 else "-- fps"
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.fillRect(8, 8, 72, 22, QColor(0, 0, 0, 150))
            painter.drawText(8, 8, 72, 22, Qt.AlignCenter, fps_text)
            painter.end()
            self.cam_labels[i].setPixmap(canvas)

        # Write recording frames per camera
        for cam_index in range(self.cam_mgr.num_cameras):
            self.cam_mgr.write_record_frame(cam_index)




    # ---- ZMQ Controls ---- #
    def connect_zmq(self):
        if self.zmq_thread and self.zmq_thread.running:
            print("[ZMQ] Already connected.")
            return
        self.stage_host, self.stage_cmd_port, self.stage_event_port = self._stage_ports_for_backend(self.hardware_backend)
        self.status_label.setText("Checking stage...")
        self.append_local_log(
            f"[Backend] checking {BACKEND_LABELS.get(self.hardware_backend, self.hardware_backend)} "
            f"stage tcp://{self.stage_host}:{self.stage_cmd_port}"
        )
        self.zmq_thread = ZMQWorker(self.stage_host, self.stage_cmd_port)
        self.zmq_thread.start()
        # Start C# -> Python status listener
        if not self.zmq_events:
            self.zmq_events = ZMQPullListener(
                self.stage_host,
                self.stage_event_port,
                on_message=self._handle_stage_event_from_thread,
            )
            self.zmq_events.start()

        if not self._probe_stage_connection(timeout_s=3.0):
            self.disconnect_zmq()
            return

        self.status_label.setText(f"Connected ({BACKEND_LABELS.get(self.hardware_backend, self.hardware_backend)})")
        self.append_local_log(
            f"[Backend] connected to {BACKEND_LABELS.get(self.hardware_backend, self.hardware_backend)} "
            f"stage tcp://{self.stage_host}:{self.stage_cmd_port}"
        )

    def disconnect_zmq(self):
        if self.zmq_thread:
            self.zmq_thread.stop()
            self.zmq_thread = None
        if self.zmq_events:
            self.zmq_events.stop()
            self.zmq_events = None
        self.status_label.setText("Disconnected")

    def _show_stage_connection_error(self, detail: str):
        QMessageBox.critical(
            self,
            "Stage Connection Failed",
            (
                f"{detail}\n\n"
                "Please check that:\n"
                "- SC3U_stage_control is running\n"
                "- The stage controller is connected in the SC3U window\n"
                "- The selected backend/ports are correct"
            ),
        )

    def _probe_stage_connection(self, timeout_s: float = 3.0) -> bool:
        deadline = time.monotonic() + float(timeout_s)
        while time.monotonic() < deadline:
            if self.zmq_thread and self.zmq_thread.running:
                break
            time.sleep(0.02)

        if not (self.zmq_thread and self.zmq_thread.running):
            self.status_label.setText("Disconnected")
            detail = "Stage connection failed: ZMQ command socket did not start."
            self.append_local_log(f"[Backend] {detail}")
            self._show_stage_connection_error(detail)
            return False

        min_seq = self._get_stage_seq()
        self.zmq_thread.send_message(json.dumps({"command": "GetCurrentPosition"}))

        try:
            ev = self._wait_for_stage_event(
                lambda e: e.get("command") == "GetCurrentPosition"
                and e.get("event") in {"Position", "PositionError", "CommandError", "ParseError"},
                min_seq=min_seq,
                timeout_s=timeout_s,
            )
        except TimeoutError:
            self.status_label.setText("Disconnected")
            detail = "Stage connection failed: no response from the stage script."
            self.append_local_log(f"[Backend] {detail}")
            self._show_stage_connection_error(detail)
            return False

        if ev.get("event") != "Position":
            message = ev.get("message") or "Stage did not return a valid position."
            self.status_label.setText("Disconnected")
            self.append_local_log(f"[Backend] stage connection failed: {message}")
            self._show_stage_connection_error(f"Stage connection failed: {message}")
            return False

        return True

    def _handle_stage_event_from_thread(self, msg: str):
        # Called on ZMQPullListener thread
        try:
            data = json.loads(msg)
        except Exception:
            data = None

        if isinstance(data, dict):
            seq = data.get("seq")
            if isinstance(seq, int):
                with self._stage_seq_lock:
                    if seq > self._stage_last_seq:
                        self._stage_last_seq = seq

            try:
                self.stage_event_queue.put_nowait(data)
            except queue.Full:
                try:
                    _ = self.stage_event_queue.get_nowait()
                except Exception:
                    pass
                try:
                    self.stage_event_queue.put_nowait(data)
                except Exception:
                    pass

        # Always emit raw message to UI logger
        self.stage_event_bus.message.emit(msg)

    def _get_stage_seq(self) -> int:
        with self._stage_seq_lock:
            return int(self._stage_last_seq)

    def _wait_for_stage_event(self, predicate, *, min_seq: int, timeout_s: float):
        deadline = time.monotonic() + float(timeout_s)
        while time.monotonic() < deadline:
            remaining = max(0.05, deadline - time.monotonic())
            try:
                ev = self.stage_event_queue.get(timeout=min(0.25, remaining))
            except queue.Empty:
                continue
            if not isinstance(ev, dict):
                continue
            seq = ev.get("seq")
            if isinstance(seq, int) and seq <= min_seq:
                continue
            if predicate(ev):
                return ev
        raise TimeoutError("Timed out waiting for stage event")

    def stage_get_position_xyz(self, timeout_s: float = 5.0) -> tuple[float, float, float]:
        if not (self.zmq_thread and self.zmq_thread.running):
            raise RuntimeError("Not connected to stage (ZMQ)")
        min_seq = self._get_stage_seq()
        self.zmq_thread.send_message(json.dumps({"command": "GetCurrentPosition"}))

        ev = self._wait_for_stage_event(
            lambda e: e.get("event") == "Position" and e.get("command") == "GetCurrentPosition",
            min_seq=min_seq,
            timeout_s=timeout_s,
        )
        payload = ev.get("payload") or {}
        x = float(payload.get("X"))
        y = float(payload.get("Y"))
        z = float(payload.get("Z"))
        return x, y, z

    def stage_move_to_xyz_and_wait(self, x: float, y: float, z: float, timeout_s: float = 30.0):
        if not (self.zmq_thread and self.zmq_thread.running):
            raise RuntimeError("Not connected to stage (ZMQ)")
        if self.af_cancel.is_set():
            raise RuntimeError("Autofocus cancelled")

        min_seq = self._get_stage_seq()
        self.zmq_thread.send_message(json.dumps({"command": "MoveToXYZ", "x": float(x), "y": float(y), "z": float(z)}))

        def _match_completed(e):
            print(f"CommandReceived: {e}")
            if e.get("event") != "CommandCompleted":
                return False
            if e.get("command") != "MoveToXYZ":
                return False
            payload = e.get("payload") or {}
            try:
                zx = float(payload.get("X"))
                zy = float(payload.get("Y"))
                zz = float(payload.get("Z"))
            except Exception:
                return False
            # Payload currently echoes commanded targets; allow small tolerance.
            tol = 1e-3
            return abs(zx - float(x)) < tol and abs(zy - float(y)) < tol and abs(zz - float(z)) < tol

        self._wait_for_stage_event(_match_completed, min_seq=min_seq, timeout_s=timeout_s)

    def append_local_log(self, line: str):
        t = self._now_hhmmss()
        txt = f"{t} {line}".strip()
        self.stage_log.appendPlainText(txt)
        self.stage_status.setText(f"{self._stage_status_prefix()}: {txt}")

    def _center_crop_fraction(self, gray: np.ndarray, fraction: float) -> np.ndarray:
        f = float(fraction)
        if f >= 1.0:
            return gray
        h, w = gray.shape[:2]
        ch = max(1, int(round(h * f)))
        cw = max(1, int(round(w * f)))
        y0 = (h - ch) // 2
        x0 = (w - cw) // 2
        return gray[y0 : y0 + ch, x0 : x0 + cw]

    def _downscale_max_size(self, gray: np.ndarray, max_size: int) -> np.ndarray:
        m = int(max_size)
        if m <= 0:
            return gray
        h, w = gray.shape[:2]
        longest = max(h, w)
        if longest <= m:
            return gray
        scale = m / float(longest)
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        return cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_AREA)

    def compute_focus_score_from_frame(
        self, frame_bgr: np.ndarray, metric: af.MetricName = "laplacian_var", roi: float = 0.8, max_size: int = 1024
    ) -> float:
        gray_u8 = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = gray_u8.astype(np.float32) / 255.0
        gray = self._downscale_max_size(gray, max_size=max_size)
        gray = self._center_crop_fraction(gray, fraction=roi)
        return float(af.focus_score(gray, metric=metric))

    def score_current_frame(self):
        cam_index = int(self.score_cam_select.currentIndex())
        if cam_index < 0 or cam_index >= self.cam_mgr.num_cameras:
            self.append_local_log("[Score] no camera available")
            return
        n = int(self.score_n.value())
        metric: af.MetricName = "laplacian_var"
        roi = 0.8
        max_size = 1024

        scores = []
        for i in range(n):
            frame = self.cam_mgr.get_frame(cam_index)
            if frame is None:
                self.append_local_log(f"[Score] cam={cam_index+1} no frame")
                return
            s = self.compute_focus_score_from_frame(frame, metric=metric, roi=roi, max_size=max_size)
            scores.append(s)
            time.sleep(0.02)

        arr = np.array(scores, dtype=np.float64)
        mean = float(arr.mean())
        std = float(arr.std(ddof=0)) if len(arr) > 1 else 0.0
        self.append_local_log(
            f"[Score] cam={cam_index+1} metric={metric} (higher=sharper) n={n} mean={mean:.6g} std={std:.6g} min={arr.min():.6g} max={arr.max():.6g}"
        )

    def start_autofocus(self, cam_index: int = 0):
        if not (self.zmq_thread and self.zmq_thread.running):
            self.append_local_log("[AF] Not connected.")
            return
        if cam_index < 0 or cam_index >= self.cam_mgr.num_cameras:
            self.append_local_log("[AF] No camera available.")
            return
        if self.af_thread and self.af_thread.is_alive():
            self.append_local_log("[AF] Already running.")
            return

        self.af_cancel.clear()
        self.autofocus_btn.setEnabled(False)
        self.cancel_af_btn.setEnabled(True)
        if hasattr(self, "resumeRoutine_btn"):
            self.resumeRoutine_btn.setEnabled(False)

        # Pause preview to avoid camera contention while taking screenshots.
        self.timer.stop()
        self.preview_status.setText("Preview paused (autofocus running).")
        self.preview_status.show()

        def _runner():
            try:
                routine = AutofocusRoutine(
                    cam_index=cam_index,
                    get_position_xyz=self.stage_get_position_xyz,
                    move_to_xyz_and_wait=self.stage_move_to_xyz_and_wait,
                    take_screenshot=lambda ci, out_dir, prefix, warmup_frames: self.cam_mgr.take_screenshot(
                        ci, save_dir=out_dir, prefix=prefix, warmup_frames=warmup_frames, simple_name=True
                    ),
                    log=lambda s: self.ui_bus.log.emit(s),
                    base_dir=self.cam_mgr.save_dir,
                    metric="laplacian_var",
                    roi=0.8,
                    max_size=1024,
                    cancel_event=self.af_cancel,
                )
                best_z, best_img_path, _pts = routine.run()
                self.ui_bus.log.emit(f"[AF] done best_z={best_z:.3f}")

            except Exception as e:
                self.ui_bus.log.emit(f"[AF] error: {e}")
            finally:
                self.ui_bus.autofocus_finished.emit()

        self.af_thread = threading.Thread(target=_runner, daemon=True)
        self.af_thread.start()

    def cancel_autofocus(self):
        if not (self.af_thread and self.af_thread.is_alive()):
            return
        self.af_cancel.set()
        try:
            if self.zmq_thread and self.zmq_thread.running:
                self.zmq_thread.send_message(json.dumps({"command": "StopRun"}))
        except Exception:
            pass
        self.append_local_log("[AF] cancel requested (sent StopRun)")

    def _on_autofocus_finished(self):
        # Resume preview
        try:
            self.timer.start(30)
        except Exception:
            pass
        self.autofocus_btn.setEnabled(self.cam_mgr.num_cameras > 0)
        self.cancel_af_btn.setEnabled(False)
        self._refresh_resume_button_state()
        self.preview_status.hide()

    def open_power_meter_plot(self):
        if self.power_meter_window is not None:
            self.power_meter_window.show()
            self.power_meter_window.raise_()
            self.power_meter_window.activateWindow()
            if not (self.power_meter_thread and self.power_meter_thread.is_alive()):
                self.start_power_meter_stream()
            return

        self.power_meter_window = PowerMeterWindow(
            start_callback=self.start_power_meter_stream,
            stop_callback=self.stop_power_meter_stream,
        )
        self.power_meter_window.closed.connect(self._on_power_meter_window_closed)
        self.power_meter_window.show()
        self.start_power_meter_stream()

    def start_power_meter_stream(self):
        if self.power_meter_thread and self.power_meter_thread.is_alive():
            self._on_power_meter_status("Power meter stream already running.")
            return

        if hasattr(self, "power_meter_btn"):
            self.power_meter_btn.setEnabled(False)

        self.power_meter_thread = PowerMeterWorker(self.power_meter_bus, sample_interval_s=0.2)
        self.power_meter_thread.start()
        if self.power_meter_window is not None:
            self.power_meter_window.set_stream_running(True)

    def stop_power_meter_stream(self):
        if self.power_meter_thread:
            self.power_meter_thread.stop()
            self.power_meter_thread = None
        if hasattr(self, "power_meter_btn"):
            self.power_meter_btn.setEnabled(True)
        if self.power_meter_window is not None:
            self.power_meter_window.set_stream_running(False)

    def _on_power_meter_sample(self, elapsed_s: float, power_w: float):
        if self.power_meter_window is not None:
            self.power_meter_window.add_sample(elapsed_s, power_w)

    def _on_power_meter_status(self, text: str):
        if self.power_meter_window is not None:
            self.power_meter_window.set_status(text)
        self.append_local_log(f"[PowerMeter] {text}")
        if text.startswith("Connected:") and self.power_meter_window is not None:
            self.power_meter_window.set_stream_running(True)
        if text == "Power meter disconnected." and hasattr(self, "power_meter_btn"):
            self.power_meter_btn.setEnabled(True)
            if self.power_meter_window is not None:
                self.power_meter_window.set_stream_running(False)

    def _on_power_meter_error(self, text: str):
        if self.power_meter_window is not None:
            self.power_meter_window.set_status(text)
            self.power_meter_window.set_stream_running(False)
        self.append_local_log(f"[PowerMeter] {text}")
        if hasattr(self, "power_meter_btn"):
            self.power_meter_btn.setEnabled(True)

    def _on_power_meter_window_closed(self):
        self.power_meter_window = None

    def open_spectrometer_plot(self):
        if self.spectrometer_window is not None:
            self.spectrometer_window.show()
            self.spectrometer_window.raise_()
            self.spectrometer_window.activateWindow()
            if not (self.spectrometer_thread and self.spectrometer_thread.is_alive()):
                self.start_spectrometer_stream()
            return

        self.spectrometer_window = SpectrometerWindow(
            start_callback=self.start_spectrometer_stream,
            stop_callback=self.stop_spectrometer_stream,
        )
        self.spectrometer_window.closed.connect(self._on_spectrometer_window_closed)
        self.spectrometer_window.show()
        self.start_spectrometer_stream()

    def start_spectrometer_stream(self):
        if self.spectrometer_thread and self.spectrometer_thread.is_alive():
            self._on_spectrometer_status("Spectrometer stream already running.")
            return

        if hasattr(self, "spectrometer_btn"):
            self.spectrometer_btn.setEnabled(False)

        self.spectrometer_thread = SpectrometerWorker(
            self.spectrometer_bus,
            integration_time_s=10.0e-3,
            plot_interval_s=0.2,
        )
        self.spectrometer_thread.start()
        if self.spectrometer_window is not None:
            self.spectrometer_window.set_stream_running(True)

    def stop_spectrometer_stream(self):
        if self.spectrometer_thread:
            self.spectrometer_thread.stop()
            self.spectrometer_thread = None
        if hasattr(self, "spectrometer_btn"):
            self.spectrometer_btn.setEnabled(True)
        if self.spectrometer_window is not None:
            self.spectrometer_window.set_stream_running(False)

    def _on_spectrometer_spectrum(self, wavelengths, intensities):
        if self.spectrometer_window is not None:
            self.spectrometer_window.set_spectrum(wavelengths, intensities)

    def _on_spectrometer_status(self, text: str):
        if self.spectrometer_window is not None:
            self.spectrometer_window.set_status(text)
        self.append_local_log(f"[Spectrometer] {text}")
        if text.startswith("Connected:") and self.spectrometer_window is not None:
            self.spectrometer_window.set_stream_running(True)
        if text == "Spectrometer disconnected." and hasattr(self, "spectrometer_btn"):
            self.spectrometer_btn.setEnabled(True)
            if self.spectrometer_window is not None:
                self.spectrometer_window.set_stream_running(False)

    def _on_spectrometer_error(self, text: str):
        if self.spectrometer_window is not None:
            self.spectrometer_window.set_status(text)
            self.spectrometer_window.set_stream_running(False)
        self.append_local_log(f"[Spectrometer] {text}")
        if hasattr(self, "spectrometer_btn"):
            self.spectrometer_btn.setEnabled(True)

    def _on_spectrometer_window_closed(self):
        self.spectrometer_window = None

    #make the json & pass it to the zmq class to send
    def send_message(self):
        if not (self.zmq_thread and self.zmq_thread.running):
            print("[ZMQ] Not connected.")
            return

        text = self.msg_input.text().strip()
        if not text:
            print("[ZMQ] No message entered.")
            return

        # Build JSON command from text
        if text == "run_test":
            msg = {"command": "RunTestRoute"}
        elif text.startswith("move"):
            # Example: move 1 5000
            try:
                _, a, t = text.split()
                msg = {"command": "RunToTarget", "axis": int(a), "target": float(t)}
            except Exception as e:
                print("[ZMQ] Invalid syntax. Use: move <axis> <target>")
                return
        elif text == "stop":
            msg = {"command": "StopRun"}
        elif text == "origin":
            msg = {"command": "SetOrigin"}
        else:
            msg = {"command": text}

        json_msg = json.dumps(msg)
        self.zmq_thread.send_message(json_msg)

    def _handle_completed_stage_stop_actions(self):
        stop = self.stage_routine.CurrentCompletedStop()
        if not stop or len(stop) < 4:
            return False

        prop = str(stop[3]).strip().lower()
        if prop != "projection":
            return False

        projector_index = stop[4] if len(stop) >= 5 else None
        if projector_index is None:
            self.append_local_log("[Projection] projection stop has no projector selected")
            return False
        try:
            projector_index = int(projector_index)
        except Exception:
            self.append_local_log(f"[Projection] invalid projector selected for projection stop: {projector_index}")
            return False

        role, patterns = self._projection_patterns_for_projector(projector_index)
        if not patterns:
            self.append_local_log(
                f"[Projection] no saved projection patterns for Display {projector_index + 1}; continuing"
            )
            return False

        started = self._start_projection_sequence(
            projector_index,
            patterns,
            role,
            on_finished=self.stage_routine.StepCompleted,
        )
        return started

    def _projection_patterns_for_projector(self, projector_index):
        if projector_index is None:
            return None, []
        try:
            projector_index = int(projector_index)
        except Exception:
            return None, []

        settings = getattr(self, "projection_settings", {}) or {}
        matches = (
            ("microscope", settings.get("microscope_display"), settings.get("microscope_patterns", [])),
            ("plate", settings.get("plate_display"), settings.get("plate_patterns", [])),
        )
        for role, display_index, patterns in matches:
            try:
                display_index = int(display_index)
            except Exception:
                continue
            if display_index == projector_index:
                return role, list(patterns or [])
        return None, []

    def _show_live_solid_projection(self, projector_index, color: QColor):
        screens = QApplication.screens()
        try:
            projector_index = int(projector_index)
        except Exception:
            self.append_local_log("[Projection] solid color projection has no valid display selected")
            return False
        if projector_index < 0 or projector_index >= len(screens):
            self.append_local_log(f"[Projection] Display {projector_index + 1} is not available for solid color projection")
            return False

        window = self.projection_windows.get(projector_index)
        if window is None:
            window = ProjectionWindow()
            self.projection_windows[projector_index] = window
        window.show_on_screen(screens[projector_index])
        window.display_solid_color(color)
        return True

    def _stop_live_solid_projection(self, projector_index=None):
        if projector_index is None:
            for window in list(self.projection_windows.values()):
                window.close()
            return
        try:
            projector_index = int(projector_index)
        except Exception:
            return
        window = self.projection_windows.get(projector_index)
        if window is not None:
            window.close()
            self.append_local_log(f"[Projection] Display {projector_index + 1}: solid color projection stopped")

    def _start_projection_sequence(self, projector_index, patterns, role=None, on_finished=None):
        screens = QApplication.screens()
        if projector_index < 0 or projector_index >= len(screens):
            self.append_local_log(f"[Projection] Display {projector_index + 1} is not available")
            return False
        if self.projection_sequence_running:
            self.append_local_log("[Projection] projection already running; skipping new projection request")
            return False

        image_paths = [path for path in patterns if os.path.exists(path)]
        missing_count = len(patterns) - len(image_paths)
        if not image_paths:
            self.append_local_log(f"[Projection] no existing image files for Display {projector_index + 1}")
            return False
        if missing_count:
            self.append_local_log(f"[Projection] skipped {missing_count} missing image file(s)")

        window = self.projection_windows.get(projector_index)
        if window is None:
            window = ProjectionWindow()
            self.projection_windows[projector_index] = window
        window.show_on_screen(screens[projector_index])

        self.projection_sequence_running = True
        role_label = role or "selected"
        self.append_local_log(
            f"[Projection] Display {projector_index + 1}: projecting {len(image_paths)} {role_label} pattern(s)"
        )

        def show_next(index=0):
            if index >= len(image_paths):
                window.close()
                self.projection_sequence_running = False
                self.append_local_log(f"[Projection] Display {projector_index + 1}: sequence finished")
                if on_finished:
                    on_finished()
                return

            path = image_paths[index]
            ok = window.display_image(path)
            status = "shown" if ok else "failed"
            self.append_local_log(
                f"[Projection] Display {projector_index + 1}: {status} {index + 1}/{len(image_paths)} {path}"
            )
            QTimer.singleShot(PROJECTION_PATTERN_INTERVAL_MS, lambda: show_next(index + 1))

        QTimer.singleShot(0, show_next)
        return True

    #013026 add this for importing stage routine
    def open_stage_sequence_editor(self):
        dialog = StageSequenceEditorDialog(getattr(self, "custom_stage_sequence", None), self)
        if dialog.exec_() != QDialog.Accepted:
            return
        self.custom_stage_sequence = dialog.get_stops()
        self.append_local_log(f"[StageSequence] saved {len(self.custom_stage_sequence)} stop(s)")

    def open_projection_settings_editor(self):
        dialog = ProjectionSettingsDialog(getattr(self, "projection_settings", None), self)
        if dialog.exec_() != QDialog.Accepted:
            return
        self.projection_settings = dialog.get_settings()
        microscope_count = len(self.projection_settings.get("microscope_patterns", []))
        plate_count = len(self.projection_settings.get("plate_patterns", []))
        self.append_local_log(
            "[Projection] settings saved "
            f"(microscope display={self.projection_settings.get('microscope_display')}, "
            f"plate display={self.projection_settings.get('plate_display')}, "
            f"microscope patterns={microscope_count}, plate patterns={plate_count})"
        )

    def _resume_pause_enabled(self):
        if hasattr(self, "resumePauseMode_check"):
            return self.resumePauseMode_check.isChecked()
        return True

    def _refresh_resume_button_state(self):
        if not hasattr(self, "resumeRoutine_btn"):
            return
        autofocus_running = bool(self.af_thread and self.af_thread.is_alive())
        self.resumeRoutine_btn.setEnabled(self._resume_pause_enabled() and not autofocus_running)

    def start_stage_routine(self):
        # For now, use your hardcoded test values
        custom_stops = getattr(self, "custom_stage_sequence", None)
        pause_after_each_step = self._resume_pause_enabled()
        self.stage_routine.SetPauseAfterEachStep(pause_after_each_step)
        if pause_after_each_step:
            self.append_local_log("[StageSequence] resume pause enabled")
        else:
            self.append_local_log("[StageSequence] resume pause disabled; auto-advancing through sequence")
        if custom_stops:
            self.stage_routine.SetCustomStops(custom_stops)
            self.append_local_log(f"[StageSequence] using custom sequence with {len(custom_stops)} stop(s)")
        else:
            self.stage_routine.SetAlignPt(66.8, 4, 60.875)
            self.stage_routine.ClearCustomStops()
        self.stage_routine.StartRoutine()

    def resume_stage_routine(self):
        self.stage_routine.Resume()

    def send_stage_move(self, x, y, z):
        if not (self.zmq_thread and self.zmq_thread.running):
            print("[ZMQ] Not connected (cannot send stage move).")
            self.append_local_log("[Stage] Not connected (cannot send move).")
            return
        msg = {
            "command": "MoveToXYZ",
            "x": float(x),
            "y": float(y),
            "z": float(z),
        }
        self.zmq_thread.send_message(json.dumps(msg))



    def closeEvent(self, event):
        try:
            self.af_cancel.set()
        except Exception:
            pass
        self.timer.stop()
        self.cam_mgr.close()
        if self.zmq_thread:
            self.zmq_thread.stop()
        if self.zmq_events:
            self.zmq_events.stop()
            self.zmq_events = None
        self.stop_power_meter_stream()
        if self.power_meter_window is not None:
            self.power_meter_window.close()
            self.power_meter_window = None
        self.stop_spectrometer_stream()
        if self.spectrometer_window is not None:
            self.spectrometer_window.close()
            self.spectrometer_window = None
        for window in self.projection_windows.values():
            window.close()
        self.projection_windows.clear()
        event.accept()

    def _on_screenshot(self, cam_index: int):
        if cam_index < 0 or cam_index >= self.cam_mgr.num_cameras:
            self.append_local_log(f"[Screenshot] cam={cam_index+1} not available")
            return
        try:
            fname = self.cam_mgr.take_screenshot(cam_index)
            if fname:
                self.append_local_log(f"[Screenshot] saved: {fname}")
            else:
                self.append_local_log(f"[Screenshot] failed cam={cam_index+1}")
        except Exception as e:
            self.append_local_log(f"[Screenshot] error: {e}")




















if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = CameraApp()
    win.show()
    sys.exit(app.exec_())


# Non-breaking alias for future rename
PythonGUI = CameraApp
