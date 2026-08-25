import sys
import os
import cv2
import numpy as np
import queue
import subprocess
import threading
import time
from ctypes import byref, c_double, c_int, c_void_p, cdll
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
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
from stage_seq_editor import StageSequenceEditorDialog
from projection_settings import ProjectionSettingsDialog, ProjectionWindow
from auto_solid_project import AutoSolidIntensityController
from empty_cam_mgr import EmptyCameraManager
from power_meter import PowerMeterBus, PowerMeterWorker, PowerMeterWindow, PowerTraceWidget, format_power_watts
from spectro_meter import SpectrometerBus, SpectrometerWorker, SpectrometerWindow, SpectrumTraceWidget

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
    auto_solid_apply = pyqtSignal(int)
    auto_solid_finished = pyqtSignal()






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






#import the camera functinality from another file
# -------- Main GUI Application -------- #
class CameraApp(QWidget):
    #---------------------------------------------------------------------------------------------------------------------------------
    # Configuration Functions
    #---------------------------------------------------------------------------------------------------------------------------------
    def _stage_ports_for_backend(self, backend: str):
        """Return the ZMQ command and event ports for the selected hardware backend."""
        if backend == BACKEND_PYCRO:
            return self.pycro_stage_host, self.pycro_stage_cmd_port, self.pycro_stage_event_port
        return self.native_stage_host, self.native_stage_cmd_port, self.native_stage_event_port

    def _stage_status_prefix(self):
        """Return the stage label prefix shown for the active hardware backend."""
        return "Pycro stage" if getattr(self, "hardware_backend", BACKEND_NATIVE) == BACKEND_PYCRO else "C# stage"


    def _apply_microscope_default_exposure(self, manager):
        """Apply the default microscope exposure to camera slot 1 if available."""
        if getattr(manager, "num_cameras", 0) <= 0:
            return
        try:
            ok, applied = manager.set_exposure(0, MICROSCOPE_DEFAULT_EXPOSURE_US)
            print(f"[Camera] Microscope default exposure set to {applied:.2f} us (ok={ok})")
        except Exception as e:
            print(f"[Camera] Could not set microscope default exposure: {e}")

    def _create_camera_manager(self, backend: str):
        """Create the camera manager or fallback manager for the requested backend."""
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




    #---------------------------------------------------------------------------------------------------------------------------------
    # Initialization Functions
    #---------------------------------------------------------------------------------------------------------------------------------
    def __init__(self):
        """Build the main OptiSuite camera, stage, instrument, and routine UI."""
        
        #---------------------------------------------------------------------------------------------------------------------------------
        # stage event and ZMQ Setup
        #---------------------------------------------------------------------------------------------------------------------------------
        
        # initialize the super class QWidget
        super().__init__()
        self.setWindowTitle("OptiSuite GUI interface")
        # We set a fixed size later after building the layout.

        # ZMQ Setup
        self.zmq_thread = None
        self.zmq_events = None

        # hard coded TCP setup, only accesses via config functions
        self.native_stage_host = "localhost"
        self.native_stage_cmd_port = 5555
        self.native_stage_event_port = 5556
        self.pycro_stage_host = "127.0.0.1"
        self.pycro_stage_cmd_port = 5655
        self.pycro_stage_event_port = 5656

        # get the hardware backend from the environment variable, if not set, use the default
        self.hardware_backend = os.environ.get("OPTISUITE_BACKEND", BACKEND_NATIVE).strip().lower()
        if self.hardware_backend not in BACKEND_LABELS:
            self.hardware_backend = BACKEND_NATIVE
        self.characterization_camera_source = os.environ.get("OPTISUITE_CHAR_CAMERA", "dmk:0").strip().lower()

        # get the stage ports for the selected backend, will be used for the stage event
        self.stage_host, self.stage_cmd_port, self.stage_event_port = self._stage_ports_for_backend(self.hardware_backend)


        self.stage_event_queue = queue.Queue(maxsize=2000)
        self._stage_seq_lock = threading.Lock()
        self._stage_last_seq = 0
        # stage event bus for the stage event signals
        self.stage_event_bus = StageEventBus()
        self.stage_event_bus.message.connect(self.on_stage_event)

        #---------------------------------------------------------------------------------------------------------------------------------
        # Preview Status/UI
        #---------------------------------------------------------------------------------------------------------------------------------

        # preview status label, used to indicate preview is paused
        self.preview_status = QLabel("")
        self.preview_status.setStyleSheet("color: #b45309; font-weight: 600;")
        self.preview_status.setWordWrap(True)
        self.preview_status.hide()

        # stage status label, unused feature for now
        self.stage_status = QLabel(f"{self._stage_status_prefix()}: (no events)")
        self.stage_status.setWordWrap(True)
        self.stage_status.hide()

        # stage log text edit, used to display the stage event log
        self.stage_log = QPlainTextEdit()
        self.stage_log.setReadOnly(True)
        self.stage_log.setMaximumBlockCount(500)

        #---------------------------------------------------------------------------------------------------------------------------------
        # Functionality Bus Setup
        #---------------------------------------------------------------------------------------------------------------------------------

        # ui bus for the ui event signals
        self.ui_bus = UiBus()
        self.ui_bus.log.connect(self.append_local_log)
        self.ui_bus.autofocus_finished.connect(self._on_autofocus_finished)
        self.ui_bus.auto_solid_apply.connect(self._on_auto_solid_apply)
        self.ui_bus.auto_solid_finished.connect(self._on_auto_solid_finished)

        # autofocus related variables
        # autofocus cancel flag
        self.af_cancel = threading.Event()
        # autofocus thread
        self.af_thread = None
        # autofocus best image paths, used to store the best image paths for the autofocus routine
        self.autofocus_best_image_paths = []

        # auto solid related variables
        self.auto_solid_thread = None
        self.auto_solid_applied = threading.Event()
        self.auto_solid_finished_callback = None

        # finished 
        # power meter variables
        self.power_meter_bus = PowerMeterBus()
        self.power_meter_bus.sample.connect(self._on_power_meter_sample)
        self.power_meter_bus.status.connect(self._on_power_meter_status)
        self.power_meter_bus.error.connect(self._on_power_meter_error)
        self.power_meter_thread = None
        self.power_meter_window = None

        # spectrometer variables
        self.spectrometer_bus = SpectrometerBus()
        self.spectrometer_bus.spectrum.connect(self._on_spectrometer_spectrum)
        self.spectrometer_bus.status.connect(self._on_spectrometer_status)
        self.spectrometer_bus.error.connect(self._on_spectrometer_error)
        self.spectrometer_thread = None
        self.spectrometer_window = None

        # projection settings variables
        self.projection_settings = {}
        self.projection_windows = {}
        self.projection_sequence_running = False

        # save directory for the screenshots
        self.save_dir = r"C:\Users\stimscope1\Documents\OptiSuite\screenshots"

        #---------------------------------------------------------------------------------------------------------------------------------
        # Camera Manager and Zoom Setup
        #---------------------------------------------------------------------------------------------------------------------------------

        # create the camera manager for the selected backend
        #use the class instead
        self.cam_mgr = self._create_camera_manager(self.hardware_backend)
        self.camera_slot_count = max(2, self.cam_mgr.num_cameras)
        # indicate the zoom level for each camera, initialized with None, but will be set later
        self.zoom_labels = [None] * self.camera_slot_count
        # Per-camera view state for software zoom/pan
        # zoom: >= 1.0, cx/cy are normalized [0..1] center coordinates in the source frame
        # track zoom level and center coordinates for each camera in the current view
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

        #---------------------------------------------------------------------------------------------------------------------------------
        # Camera UI Layout
        #---------------------------------------------------------------------------------------------------------------------------------

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
        # set the initial window size relative to the available geometry of the primary screen
        screen = QApplication.primaryScreen().availableGeometry()
        max_win_w = int(screen.width() * 0.95)
        max_win_h = int(screen.height() * 0.95)

        #---------------------------------------------------------------------------------------------------------------------------------
        # set stage log ui, cont.
        stage_log_w = min(400, max(320, int(max_win_w * 0.32)))
        self.stage_log.setMinimumWidth(260)
        self.stage_log.resize(stage_log_w, self.stage_log.height())
        self.stage_log.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        #---------------------------------------------------------------------------------------------------------------------------------

        #---------------------------------------------------------------------------------------------------------------------------------
        # Camera UI starting size and position
        #---------------------------------------------------------------------------------------------------------------------------------

        # Reserve enough vertical space for stacked bottom control rows.
        # Keep the initial preview size modest; resizing can then grow it.
        bottom_panel_h = 320
        caption_h = 22
        control_h = 220
        preview_h = int((max_win_h - bottom_panel_h) / rows) - caption_h - control_h
        preview_h = max(140, min(260, preview_h))

        preview_w = min(520, max_win_w - stage_log_w - 80)
        preview_w = max(360, preview_w)

        #---------------------------------------------------------------------------------------------------------------------------------
        # Characterization Plate Control UI
        #---------------------------------------------------------------------------------------------------------------------------------

        # builder for characterization plate control ui
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

        #---------------------------------------------------------------------------------------------------------------------------------
        # Camera UI Initialization loop (Left side)
        #---------------------------------------------------------------------------------------------------------------------------------

        # Keep fixed camera slots so downstream instrument controls do not move when cameras are missing.
        for i in range(self.camera_slot_count):
            camera_detected = i < self.cam_mgr.num_cameras
            # ------- CAMERA TITLE + PREVIEW LABEL -------
            model = ""
            if camera_detected and hasattr(self.cam_mgr, "camera_names") and i < len(self.cam_mgr.camera_names):
                model = str(self.cam_mgr.camera_names[i])

            # camera title, based on the camera index
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

            # camera preview label
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
            
            # record button
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

            # view container for the camera preview and zoom overlay
            # constain both the preview label and the zoom overlay
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
            # set the row stretch for ui
            # i // cols * 2 are preview cam box
            # i // cols * 2 + 1 are control panel, added later, not allow to change size
            self.grid.setRowStretch(i // cols * 2, 1)
            self.grid.setRowStretch(i // cols * 2 + 1, 0)

            # store the camera preview label and title label
            self.cam_labels.append(label)
            self.cam_title_labels.append(title)

            # ------- CONTROL PANEL -------
            # created two row for preview control panel
            # only panel 1 was used, panel 2 was unused
            panel = QHBoxLayout()
            panel.setContentsMargins(0, 0, 0, 0)
            panel.setSpacing(14)
            panel2 = QHBoxLayout()
            panel2.setContentsMargins(0, 0, 0, 0)
            panel2.setSpacing(6)

            # Exposure input box (µs)
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
            exp_input.setFixedWidth(110)

            # apply button for the exposure input box
            exp_apply = QPushButton("Set Exp")
            exp_apply.clicked.connect(lambda _, c=i, w=exp_input: self.apply_exposure(c, w))
            exp_apply.setFixedWidth(64)

            # exposure label
            exp_label = QLabel("Exposure (us):")
            exp_label.setFixedWidth(92)
            exp_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            # exposure group for the exposure input box and apply button and label
            exp_group = QHBoxLayout()
            exp_group.setContentsMargins(0, 0, 0, 0)
            exp_group.setSpacing(4)
            exp_group.addWidget(exp_label)
            exp_group.addWidget(exp_input)
            exp_group.addWidget(exp_apply)
            # add the exposure group to the preview control panel
            panel.addLayout(exp_group)
            self.exposure_inputs.append(exp_input)

            # Gain input box
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
            gain_input.setFixedWidth(90)

            # apply button for the gain input box
            gain_apply = QPushButton("Set Gain")
            gain_apply.clicked.connect(lambda _, c=i, w=gain_input: self.apply_gain(c, w))
            gain_apply.setFixedWidth(68)

            # gain label
            gain_label = QLabel("Gain:")
            gain_label.setFixedWidth(42)
            gain_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            # gain group for the gain input box and apply button and label
            gain_group = QHBoxLayout()
            gain_group.setContentsMargins(0, 0, 0, 0)
            gain_group.setSpacing(4)
            gain_group.addWidget(gain_label)
            gain_group.addWidget(gain_input)
            gain_group.addWidget(gain_apply)
            # add the gain group to the preview control panel
            panel.addLayout(gain_group)
            # add a stretch to the preview control panel
            panel.addStretch(1)
            self.gain_inputs.append(gain_input)



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
                # characterization camera select box, never used in ui, but is still needed as other ui templates use it
                self.characterization_camera_select = QComboBox()
                self.characterization_camera_select.addItem("Daheng / current Cam 2", "daheng")
                self.characterization_camera_select.addItem("DMK 27BUP031", "dmk:0")
                char_index = self.characterization_camera_select.findData(self.characterization_camera_source)
                self.characterization_camera_select.setCurrentIndex(max(0, char_index))
                self.characterization_camera_select.currentIndexChanged.connect(self.on_characterization_camera_changed)
                # build the characterizaion plate control panel
                add_characterization_controls(control_stack)

            # add the control stack to the grid
            self.grid.addLayout(control_stack, i // cols * 2 + 1, i % cols)
            self.control_panels.append(panel)

        #---------------------------------------------------------------------------------------------------------------------------------
        # Main UI Layout
        #---------------------------------------------------------------------------------------------------------------------------------

        # Top area: camera grid + C# stage status/log
        top_layout = QHBoxLayout()
        top_layout.addLayout(self.grid, 3)

        #---------------------------------------------------------------------------------------------------------------------------------
        # Status log and stage controls layout (Right side)
        #---------------------------------------------------------------------------------------------------------------------------------

        # right side ui layout
        # stage controls box for the stage controls
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
        
        # stage panel for the stage status, controls, and log
        stage_panel = QVBoxLayout()
        stage_panel.addWidget(self.preview_status)
        stage_panel.addWidget(stage_controls_box)
        stage_panel.addWidget(self.stage_log)
        stage_panel.setStretch(0, 0)
        stage_panel.setStretch(1, 1)
        stage_panel.setStretch(2, 1)

        #---------------------------------------------------------------------------------------------------------------------------------
        # Assemble Main UI
        #---------------------------------------------------------------------------------------------------------------------------------

        top_layout.addLayout(stage_panel, 2)
        self.layout.addLayout(top_layout)
        self.setLayout(self.layout)

        # Set a comfortable initial size; child widgets remain resizable.
        win_w = cols * preview_w + self.stage_log.width() + 80
        win_h = rows * (preview_h + caption_h + control_h) + bottom_panel_h
        self.resize(win_w, win_h)

        #---------------------------------------------------------------------------------------------------------------------------------
        # Stage Routine, Autofocus, ZeroMQ, and Backend/stage command controls layout (right side)
        #---------------------------------------------------------------------------------------------------------------------------------

        #stage_routine_panel for stage routine, resume step
        stage_routine_panel = QHBoxLayout()
        #autofocus_panel for autofocus, score, n, score button, capture frame button
        autofocus_panel = QHBoxLayout()
        # Backend/stage command controls live in the right-side controls panel.
        backend_panel = QHBoxLayout()
        stage_connection_panel = QHBoxLayout()
        command_panel = QHBoxLayout()
        command_target_panel = QHBoxLayout()

        #---------------------------------------------------------------------------------------------------------------------------------
        # Stage Command Controls
        #---------------------------------------------------------------------------------------------------------------------------------

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

        #---------------------------------------------------------------------------------------------------------------------------------
        # Focus Scoring Tool
        #---------------------------------------------------------------------------------------------------------------------------------

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

        #---------------------------------------------------------------------------------------------------------------------------------
        # Stage Functionality Controls (Stage Routine, Projection, AutoSolid Projection)
        #---------------------------------------------------------------------------------------------------------------------------------

        #013026 add these buttons for the stageRoutine
        # ---- Stage Routine Controls ----
        setStageSequence_btn = QPushButton("Set Stage Sequence")
        setProjectionSettings_btn = QPushButton("Set Projection Settings")
        autoSolidProjection_btn = QPushButton("Auto Solid Projection")
        startRoutine_btn = QPushButton("Start Characterization")
        resumeRoutine_btn = QPushButton("Resume")

        for sequence_btn in (
            setStageSequence_btn,
            setProjectionSettings_btn,
            autoSolidProjection_btn,
            startRoutine_btn,
            resumeRoutine_btn,
        ):
            sequence_btn.setMinimumWidth(136)
            sequence_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        autoSolidProjection_btn.setEnabled(self.cam_mgr.num_cameras > 0)



        resumePauseMode_check = QCheckBox("Enable Resume")
        resumePauseMode_check.setChecked(True)
        resumePauseMode_check.setToolTip("Checked pauses after each characterization stop so Resume is required. Unchecked runs through the sequence automatically.")
        autofocus_btn = QPushButton("Autofocus")
        cancel_af_btn = QPushButton("Cancel AF")
    
        resumePauseMode_check.setMinimumWidth(136)
        resumePauseMode_check.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        autofocus_btn.setEnabled(self.cam_mgr.num_cameras > 0)
        cancel_af_btn.setEnabled(False)

        #---------------------------------------------------------------------------------------------------------------------------------
        # Stage Functionality Connections (Stage Routine, Projection, AutoSolid Projection)
        #---------------------------------------------------------------------------------------------------------------------------------

        startRoutine_btn.clicked.connect(self.start_stage_routine)
        setStageSequence_btn.clicked.connect(self.open_stage_sequence_editor)
        setProjectionSettings_btn.clicked.connect(self.open_projection_settings_editor)
        autoSolidProjection_btn.clicked.connect(lambda: self.start_auto_solid_projection(cam_index=0))
        resumeRoutine_btn.clicked.connect(self.resume_stage_routine)
        resumePauseMode_check.stateChanged.connect(lambda _=None: self._refresh_resume_button_state())
        autofocus_btn.clicked.connect(lambda: self.start_autofocus(cam_index=0))
        cancel_af_btn.clicked.connect(self.cancel_autofocus)

        #---------------------------------------------------------------------------------------------------------------------------------
        # Stage Functionality UI Assembly (Stage Routine, Projection, AutoSolid Projection)
        #---------------------------------------------------------------------------------------------------------------------------------

        stage_sequence_buttons = QGridLayout()
        stage_sequence_buttons.setContentsMargins(0, 0, 0, 0)
        stage_sequence_buttons.setHorizontalSpacing(6)
        stage_sequence_buttons.setVerticalSpacing(4)
        stage_sequence_buttons.addWidget(setStageSequence_btn, 0, 0)
        stage_sequence_buttons.addWidget(setProjectionSettings_btn, 0, 1)
        stage_sequence_buttons.addWidget(autoSolidProjection_btn, 0, 2)
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
        self.autoSolidProjection_btn = autoSolidProjection_btn
        self.startRoutine_btn = startRoutine_btn
        self.resumePauseMode_check = resumePauseMode_check
        self._refresh_camera_ui_state()
        self._refresh_resume_button_state()

        #---------------------------------------------------------------------------------------------------------------------------------
        # Stage Connection Controls
        #---------------------------------------------------------------------------------------------------------------------------------

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

        #---------------------------------------------------------------------------------------------------------------------------------
        # Stage Connection UI Assembly
        #---------------------------------------------------------------------------------------------------------------------------------

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

        #---------------------------------------------------------------------------------------------------------------------------------
        # Full Control Panel Assembly
        #---------------------------------------------------------------------------------------------------------------------------------

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
        """Build the display title for a camera slot."""
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
        """Enable or disable camera controls for one camera slot."""
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
        """Refresh the focus-score camera dropdown based on available cameras."""
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
        """Refresh camera labels, controls, exposure, gain, and score choices."""
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
        """Switch the Cam 2 characterization source in native backend mode."""
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
        """Switch between native and Pycro hardware backends."""
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
        """Handle camera preview mouse events for zooming and panning."""
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
        """Pan a zoomed camera preview based on mouse movement."""
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
        """Zoom a camera preview around the last known mouse position."""
        self.zoom_at_label_pos(cam_index, float(multiplier), self.last_mouse_pos[cam_index])

    def reset_zoom(self, cam_index):
        """Reset one camera preview to full-frame 1x zoom."""
        self.view_states[cam_index] = {"zoom": 1.0, "cx": 0.5, "cy": 0.5}
        self._update_zoom_label(cam_index)

    def _update_zoom_label(self, cam_index):
        """Update the text label that shows the current preview zoom level."""
        lbl = self.zoom_labels[cam_index]
        if not lbl:
            return
        z = float(self.view_states[cam_index]["zoom"])
        if abs(z - 1.0) < 1e-6:
            lbl.setText("1.0x")
        else:
            lbl.setText(f"{z:.2f}x")

    def _get_pixmap_rect_in_label(self, label: QLabel):
        """Return the displayed pixmap rectangle inside a preview label."""
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
        """Zoom toward a point in the preview while keeping that point anchored."""
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
        """Crop and resize a frame according to the stored software zoom state."""
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
        """Apply the exposure value from the UI to the selected camera."""
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
        """Apply the gain value from the UI to the selected camera."""
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
        """Display stage events and advance routines when stage moves complete."""
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

            self.resolution_app_after_routine()

    def _now_hhmmss(self):
        """Return the current local time formatted for UI log lines."""
        return datetime.now().strftime("%H:%M:%S")

    def _fmt_ts(self, ts_utc_ms):
        """Format a stage event timestamp, falling back to local time."""
        try:
            ms = int(ts_utc_ms)
            dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).astimezone()
            return dt.strftime("%H:%M:%S.%f")[:-3]
        except Exception:
            return self._now_hhmmss()

    def send_zmq_command(self):
        """Send the selected manual stage command over ZMQ."""
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
        """Refresh live camera previews and write recording frames."""
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
        """Start ZMQ stage command/event connections and verify the stage responds."""
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
        """Stop ZMQ stage command/event connections."""
        if self.zmq_thread:
            self.zmq_thread.stop()
            self.zmq_thread = None
        if self.zmq_events:
            self.zmq_events.stop()
            self.zmq_events = None
        self.status_label.setText("Disconnected")

    def _show_stage_connection_error(self, detail: str):
        """Show a modal error explaining why stage connection failed."""
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
        """Send a position query to confirm the stage backend is alive."""
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
        """Queue background stage events and forward them to the UI thread."""
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
        """Return the latest received stage event sequence number."""
        with self._stage_seq_lock:
            return int(self._stage_last_seq)

    def _wait_for_stage_event(self, predicate, *, min_seq: int, timeout_s: float):
        """Wait until a queued stage event newer than min_seq matches a predicate."""
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
        """Request and return the current stage XYZ position."""
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
        """Move the stage to XYZ and block until the matching completion event arrives."""
        if not (self.zmq_thread and self.zmq_thread.running):
            raise RuntimeError("Not connected to stage (ZMQ)")
        if self.af_cancel.is_set():
            raise RuntimeError("Autofocus cancelled")

        min_seq = self._get_stage_seq()
        self.zmq_thread.send_message(json.dumps({"command": "MoveToXYZ", "x": float(x), "y": float(y), "z": float(z)}))

        def _match_completed(e):
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
        """Append a timestamped message to the local stage/status log."""
        t = self._now_hhmmss()
        txt = f"{t} {line}".strip()
        self.stage_log.appendPlainText(txt)
        self.stage_status.setText(f"{self._stage_status_prefix()}: {txt}")

    def _center_crop_fraction(self, gray: np.ndarray, fraction: float) -> np.ndarray:
        """Return the centered crop used for focus scoring."""
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
        """Downscale an image so focus scoring stays fast."""
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
        """Compute a focus score from a BGR camera frame."""
        gray_u8 = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = gray_u8.astype(np.float32) / 255.0
        gray = self._downscale_max_size(gray, max_size=max_size)
        gray = self._center_crop_fraction(gray, fraction=roi)
        return float(af.focus_score(gray, metric=metric))

    def score_current_frame(self):
        """Sample one camera repeatedly and log focus-score statistics."""
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

    def start_autofocus(self, cam_index: int = 0, on_finished=None, no_ui=False):
        """Run autofocus in a worker thread and open the USAF result UI."""
        if not (self.zmq_thread and self.zmq_thread.running):
            self.append_local_log("[AF] Not connected.")
            return False
        if cam_index < 0 or cam_index >= self.cam_mgr.num_cameras:
            self.append_local_log("[AF] No camera available.")
            return False
        if self.af_thread and self.af_thread.is_alive():
            self.append_local_log("[AF] Already running.")
            return False
        if self.auto_solid_thread and self.auto_solid_thread.is_alive():
            self.append_local_log("[AF] wait for auto solid projection to finish")
            return False

        self.autofocus_finished_callback = on_finished
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
                best_z, _pts, best_img_path = routine.run()
                self.autofocus_best_image_paths.append(str(best_img_path))
                self.ui_bus.log.emit(f"[AF] done best_z={best_z:.3f}")

                resolution_cmd = [sys.executable, "-m", "usaf_interface.resolution_app", str(best_img_path)]
                if no_ui:
                    resolution_cmd.append("--no-ui")
                subprocess.Popen(
                    resolution_cmd,
                    cwd=str(ROOT_DIR),
                )
                self.ui_bus.log.emit(f"[AF] launched USAF UI for {best_img_path}")

            except Exception as e:
                self.ui_bus.log.emit(f"[AF] error: {e}")
            finally:
                self.ui_bus.autofocus_finished.emit()

        self.af_thread = threading.Thread(target=_runner, daemon=True)
        self.af_thread.start()
        return True


    def cancel_autofocus(self):
        """Request cancellation of the running autofocus routine."""
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
        """Restore preview and button state after autofocus exits."""
        # Resume preview
        try:
            self.timer.start(30)
        except Exception:
            pass
        self.autofocus_btn.setEnabled(self.cam_mgr.num_cameras > 0)
        self.cancel_af_btn.setEnabled(False)
        self._refresh_resume_button_state()
        self.preview_status.hide()
        callback = getattr(self, "autofocus_finished_callback", None)
        self.autofocus_finished_callback = None
        if callback:
            callback()

    #------------------------------------------------------------------------------------------------------------------
    #power meter
    #------------------------------------------------------------------------------------------------------------------
    def open_power_meter_plot(self):
        """Open the power meter plot window and start streaming samples."""
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
        """Start the background power meter worker."""
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
        """Stop the background power meter worker and update controls."""
        if self.power_meter_thread:
            self.power_meter_thread.stop()
            self.power_meter_thread = None
        if hasattr(self, "power_meter_btn"):
            self.power_meter_btn.setEnabled(True)
        if self.power_meter_window is not None:
            self.power_meter_window.set_stream_running(False)

    def _on_power_meter_sample(self, elapsed_s: float, power_w: float):
        """Forward a power meter sample to the plot window."""
        if self.power_meter_window is not None:
            self.power_meter_window.add_sample(elapsed_s, power_w)

    def _on_power_meter_status(self, text: str):
        """Display power meter status in the plot window and main log."""
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
        """Display a power meter error and re-enable related controls."""
        if self.power_meter_window is not None:
            self.power_meter_window.set_status(text)
            self.power_meter_window.set_stream_running(False)
        self.append_local_log(f"[PowerMeter] {text}")
        if hasattr(self, "power_meter_btn"):
            self.power_meter_btn.setEnabled(True)

    def _on_power_meter_window_closed(self):
        """Clear the stored power meter window reference after close."""
        self.power_meter_window = None

    #------------------------------------------------------------------------------------------------------------------
    #spectrometer
    #------------------------------------------------------------------------------------------------------------------
    def open_spectrometer_plot(self):
        """Open the spectrometer plot window and start streaming spectra."""
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
        """Start the background spectrometer worker."""
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
        """Stop the background spectrometer worker and update controls."""
        if self.spectrometer_thread:
            self.spectrometer_thread.stop()
            self.spectrometer_thread = None
        if hasattr(self, "spectrometer_btn"):
            self.spectrometer_btn.setEnabled(True)
        if self.spectrometer_window is not None:
            self.spectrometer_window.set_stream_running(False)

    def _on_spectrometer_spectrum(self, wavelengths, intensities):
        """Forward a spectrum to the spectrometer plot window."""
        if self.spectrometer_window is not None:
            self.spectrometer_window.set_spectrum(wavelengths, intensities)

    def _on_spectrometer_status(self, text: str):
        """Display spectrometer status in the plot window and main log."""
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
        """Display a spectrometer error and re-enable related controls."""
        if self.spectrometer_window is not None:
            self.spectrometer_window.set_status(text)
            self.spectrometer_window.set_stream_running(False)
        self.append_local_log(f"[Spectrometer] {text}")
        if hasattr(self, "spectrometer_btn"):
            self.spectrometer_btn.setEnabled(True)

    def _on_spectrometer_window_closed(self):
        """Clear the stored spectrometer window reference after close."""
        self.spectrometer_window = None















    #make the json & pass it to the zmq class to send
    def send_message(self):
        """Parse the free-text command box and send a JSON stage command."""
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

    def resolution_app_after_routine(self):
        """launch a final multi-image USAF run if finished."""
        if getattr(self.stage_routine, "running", False) or not self.autofocus_best_image_paths:
            return
        image_paths = list(self.autofocus_best_image_paths)
        self.autofocus_best_image_paths.clear()
        subprocess.Popen(
            [sys.executable, "-m", "usaf_interface.resolution_app", *image_paths],
            cwd=str(ROOT_DIR),
        )
        self.append_local_log(f"[AF] launched final USAF UI for {len(image_paths)} image(s)")

    def _handle_completed_stage_stop_actions(self):
        """Run stop-specific actions after a custom stage stop completes."""
        stop = self.stage_routine.CurrentCompletedStop()
        if not stop or len(stop) < 4:
            return False

        prop = str(stop[3]).strip().lower()
        if prop == "projection":
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
        elif prop == "resolution":
            return self.start_autofocus(cam_index=0, on_finished=self.stage_routine.StepCompleted, no_ui=True)
        elif prop == "auto solid projection":
            return self.start_auto_solid_projection(cam_index=0, on_finished=self.stage_routine.StepCompleted)
        else:
            return False









    #------------------------------------------------------------------------------------------------------------------
    #projection
    #------------------------------------------------------------------------------------------------------------------
    def _projection_patterns_for_projector(self, projector_index):
        """Return the saved projection role and image list for a display."""
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

    def _solid_color_from_settings(self, settings):
        """Build a solid-projection QColor from saved intensity and channel."""
        settings = settings or {}
        intensity = max(0, min(100, int(settings.get("solid_intensity", 100))))
        value = int(round(255 * intensity / 100.0))
        color_name = str(settings.get("solid_color") or "red").strip().lower()
        if color_name == "green":
            return QColor(0, value, 0)
        if color_name == "blue":
            return QColor(0, 0, value)
        return QColor(value, 0, 0)

    def _show_live_solid_projection(self, projector_index, color: QColor):
        """Show a solid color on the selected projector display."""
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

    def _solid_display_index(self):
        """Return the saved or first external display index for solid projection."""
        settings = getattr(self, "projection_settings", {}) or {}
        for key in ("solid_display", "microscope_display", "plate_display"):
            try:
                return int(settings[key])
            except Exception:
                continue
        screens = QApplication.screens()
        primary = QApplication.primaryScreen()
        for index, screen in enumerate(screens):
            if screen != primary:
                return index
        return 0 if screens else None

    def _apply_auto_solid_intensity(self, intensity):
        """Show the saved solid color at intensity without opening the dialog."""
        settings = dict(getattr(self, "projection_settings", {}) or {})
        settings["solid_intensity"] = int(intensity)
        settings["solid_color"] = settings.get("solid_color") or "red"
        settings["solid_display"] = self._solid_display_index()
        self.projection_settings = settings
        return self._show_live_solid_projection(
            settings.get("solid_display"),
            self._solid_color_from_settings(settings),
        )

    def _set_auto_solid_intensity(self, intensity):
        """Ask the GUI thread to update the projector, then wait until it is applied."""
        self.auto_solid_applied.clear()
        self.ui_bus.auto_solid_apply.emit(int(intensity))
        self.auto_solid_applied.wait(2.0)

    def _on_auto_solid_apply(self, intensity):
        """Apply solid projection on the GUI thread."""
        try:
            self._apply_auto_solid_intensity(intensity)
        finally:
            self.auto_solid_applied.set()

    def start_auto_solid_projection(self, cam_index: int = 0, on_finished=None):
        """Run AutoSolidIntensityController in a worker thread."""
        if self.auto_solid_thread and self.auto_solid_thread.is_alive():
            self.append_local_log("[AutoSolid] already running")
            return False
        if self.af_thread and self.af_thread.is_alive():
            self.append_local_log("[AutoSolid] wait for autofocus to finish")
            return False
        if cam_index < 0 or cam_index >= self.cam_mgr.num_cameras:
            self.append_local_log("[AutoSolid] no camera available")
            return False

        self.auto_solid_finished_callback = on_finished
        if hasattr(self, "autoSolidProjection_btn"):
            self.autoSolidProjection_btn.setEnabled(False)
        self.timer.stop()
        self.preview_status.setText("Preview paused (auto solid projection running).")
        self.preview_status.show()

        start_intensity = int((getattr(self, "projection_settings", {}) or {}).get("solid_intensity", 50) or 50)
        out_dir = os.path.join(self.cam_mgr.save_dir, "auto_solid")

        def _runner():
            try:
                controller = AutoSolidIntensityController(
                    cam_index=cam_index,
                    take_screenshot=lambda ci, save_dir, prefix, warmup_frames: self.cam_mgr.take_screenshot(
                        ci, save_dir=save_dir, prefix=prefix, warmup_frames=warmup_frames, simple_name=True
                    ),
                    set_intensity=self._set_auto_solid_intensity,
                    log=lambda s: self.ui_bus.log.emit(s),
                    start_intensity=start_intensity,
                )
                best, _stats = controller.run(out_dir=out_dir)
                self.ui_bus.log.emit(f"[AutoSolid] done intensity={best}%")
            except Exception as e:
                self.ui_bus.log.emit(f"[AutoSolid] error: {e}")
            finally:
                self.ui_bus.auto_solid_finished.emit()

        self.auto_solid_thread = threading.Thread(target=_runner, daemon=True)
        self.auto_solid_thread.start()
        return True

    def _on_auto_solid_finished(self):
        """Restore preview and button state after auto solid intensity exits."""
        try:
            self.timer.start(30)
        except Exception:
            pass
        if hasattr(self, "autoSolidProjection_btn"):
            self.autoSolidProjection_btn.setEnabled(self.cam_mgr.num_cameras > 0)
        self.preview_status.hide()
        callback = self.auto_solid_finished_callback
        self.auto_solid_finished_callback = None
        if callback:
            callback()

    def _stop_live_solid_projection(self, projector_index=None):
        """Close one or all live solid-color projection windows."""
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
        """Display projection images in sequence on a selected display."""
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
        """Open the custom stage sequence editor and save its stops."""
        dialog = StageSequenceEditorDialog(getattr(self, "custom_stage_sequence", None), self)
        if dialog.exec_() != QDialog.Accepted:
            return
        self.custom_stage_sequence = dialog.get_stops()
        self.append_local_log(f"[StageSequence] saved {len(self.custom_stage_sequence)} stop(s)")

    def open_projection_settings_editor(self):
        """Open the projection settings editor and save display/pattern settings."""
        dialog = ProjectionSettingsDialog(getattr(self, "projection_settings", None), self)
        if dialog.exec_() != QDialog.Accepted:
            return
        self.projection_settings = dialog.get_settings()
        microscope_count = len(self.projection_settings.get("microscope_patterns", []))
        plate_count = len(self.projection_settings.get("plate_patterns", []))
        applied = self._show_live_solid_projection(
            self.projection_settings.get("solid_display"),
            self._solid_color_from_settings(self.projection_settings),
        )
        self.append_local_log(
            "[Projection] settings saved "
            f"(microscope display={self.projection_settings.get('microscope_display')}, "
            f"plate display={self.projection_settings.get('plate_display')}, "
            f"microscope patterns={microscope_count}, plate patterns={plate_count}, "
            f"solid display={self.projection_settings.get('solid_display')}, "
            f"solid color={self.projection_settings.get('solid_color')}, "
            f"solid intensity={self.projection_settings.get('solid_intensity')}%)"
        )
        if applied:
            self.append_local_log("[Projection] solid color projection updated on screen")

    def _resume_pause_enabled(self):
        """Return whether stage routines should pause after each stop."""
        if hasattr(self, "resumePauseMode_check"):
            return self.resumePauseMode_check.isChecked()
        return True

    def _refresh_resume_button_state(self):
        """Enable Resume only when allowed and autofocus is not running."""
        if not hasattr(self, "resumeRoutine_btn"):
            return
        autofocus_running = bool(self.af_thread and self.af_thread.is_alive())
        self.resumeRoutine_btn.setEnabled(self._resume_pause_enabled() and not autofocus_running)

    def start_stage_routine(self):
        """Start the configured custom or fallback stage routine."""
        # For now, use your hardcoded test values
        self.autofocus_best_image_paths.clear()
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
        """Resume a paused stage routine."""
        self.stage_routine.Resume()

    def send_stage_move(self, x, y, z):
        """Send a MoveToXYZ command for StageRoutine callbacks."""
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
        """Clean up cameras, workers, ZMQ threads, and windows on exit."""
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
        """Capture and log a screenshot from the selected camera."""
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
