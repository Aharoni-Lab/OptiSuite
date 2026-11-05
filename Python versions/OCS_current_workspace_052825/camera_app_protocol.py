"""Typed surface shared by CameraApp and its mixins.

The GUI module name starts with a digit, so the mixins cannot import CameraApp.
CameraApp subclasses CameraAppHost. Mixin methods annotate ``self`` as
CameraAppHost, which lets a type checker follow attributes and methods across
the mixins. Methods implemented on CameraApp are declared here and overridden
there. Methods implemented on a mixin are left on that mixin so navigation
lands on the real function.
"""

from __future__ import annotations

import queue
import subprocess
import threading
from collections.abc import Callable
from typing import Any, TypedDict

from PyQt5.QtCore import QPoint, QTimer
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from autofocus_mixin import AutofocusMixin
from camera_focus_scoring_mixin import CameraFocusScoringMixin
from camera_manager_class_import_120425 import CameraManager
from camera_preview_mixin import CameraPreviewMixin
from camera_source_router import CharacterizationCameraRouter
from configuration_mixin import ConfigurationMixin
from constants import StageEventBus, UiBus
from empty_cam_mgr import EmptyCameraManager
from pathlib import Path
from power_meter import PowerMeterBus, PowerMeterWindow, PowerMeterWorker
from power_meter_mixin import PowerMeterMixin
from projection_mixin import ProjectionMixin
from projection_settings import ProjectionWindow
from pycro_camera_client import PycroManagerCameraManager
from spectro_meter import SpectrometerBus, SpectrometerWindow, SpectrometerWorker
from spectrometer_mixin import SpectrometerMixin
from stage_routine_import_013026 import StageRoutine
from zmq_pull_listener import ZMQPullListener
from zmq_push_worker import ZMQWorker

CameraBackend = CameraManager | CharacterizationCameraRouter | EmptyCameraManager | PycroManagerCameraManager
FinishedCallback = Callable[[], None]
StageEvent = dict[str, Any]
ViewState = dict[str, float]


class CameraControlWidgets(TypedDict):
    zoom_out: QPushButton
    zoom_in: QPushButton
    zoom_reset: QPushButton
    zoom_label: QLabel
    exposure_input: QDoubleSpinBox
    exposure_apply: QPushButton
    gain_input: QDoubleSpinBox
    gain_apply: QPushButton
    screenshot: QPushButton
    record: QPushButton


class CameraAppHost(
    AutofocusMixin,
    CameraFocusScoringMixin,
    ConfigurationMixin,
    PowerMeterMixin,
    ProjectionMixin,
    SpectrometerMixin,
    CameraPreviewMixin,
    QWidget,
):
    config_path: Path | None
    zmq_thread: ZMQWorker | None
    zmq_events: ZMQPullListener | None
    native_stage_host: str
    native_stage_cmd_port: int
    native_stage_event_port: int
    pycro_stage_host: str
    pycro_stage_cmd_port: int
    pycro_stage_event_port: int
    hardware_backend: str
    _pycro_headless_proc: subprocess.Popen[Any] | None
    _pycro_bridge_proc: subprocess.Popen[Any] | None
    characterization_camera_source: str
    stage_host: str
    stage_cmd_port: int
    stage_event_port: int
    stage_event_queue: queue.Queue[StageEvent]
    _stage_seq_lock: threading.Lock
    _stage_last_seq: int
    stage_event_bus: StageEventBus
    preview_status: QLabel
    stage_status: QLabel
    stage_log: QPlainTextEdit
    ui_bus: UiBus
    af_cancel: threading.Event
    af_thread: threading.Thread | None
    autofocus_best_image_paths: list[str]
    autofocus_finished_callback: FinishedCallback | None
    auto_solid_thread: threading.Thread | None
    auto_solid_applied: threading.Event
    auto_solid_finished_callback: FinishedCallback | None
    power_meter_bus: PowerMeterBus
    power_meter_thread: PowerMeterWorker | None
    power_meter_window: PowerMeterWindow | None
    power_meter_finished_callback: FinishedCallback | None
    spectrometer_bus: SpectrometerBus
    spectrometer_thread: SpectrometerWorker | None
    spectrometer_window: SpectrometerWindow | None
    spectro_meter_finished_callback: FinishedCallback | None
    projection_settings: dict[str, Any]
    projection_windows: dict[int, ProjectionWindow]
    projection_sequence_running: bool
    custom_stage_sequence: list[Any] | None
    save_dir: str
    cam_mgr: CameraBackend
    camera_slot_count: int
    zoom_labels: list[QLabel | None]
    view_states: list[ViewState]
    last_mouse_pos: list[QPoint | None]
    pan_active: list[bool]
    pan_last_pos: list[QPoint | None]
    last_frame_sizes: list[tuple[int, int] | None]
    frame_fps: list[float]
    frame_last_ts: list[float | None]
    frame_last_ids: list[int | None]
    layout: QVBoxLayout
    grid: QGridLayout
    cam_labels: list[QLabel]
    cam_title_labels: list[QLabel]
    camera_control_widgets: list[CameraControlWidgets]
    control_panels: list[QHBoxLayout]
    exposure_inputs: list[QDoubleSpinBox]
    gain_inputs: list[QDoubleSpinBox]
    slide_selections: dict[str, str | None]
    resolution_slide_selection: str | None
    slide1_btn: QPushButton
    slide2_btn: QPushButton
    plate_sensor_btn: QPushButton
    fluorescence_slide_btn: QPushButton
    resolution_slide_btn: QPushButton
    t_btn: QPushButton
    start_marker: QLabel
    spectrometer_btn: QPushButton
    power_meter_btn: QPushButton
    characterization_camera_select: QComboBox
    stage_controls_layout: QVBoxLayout
    cmd_select: QComboBox
    axis_spin: QSpinBox
    target_spin: QDoubleSpinBox
    score_cam_select: QComboBox
    score_n: QSpinBox
    score_btn: QPushButton
    autofocus_btn: QPushButton
    cancel_af_btn: QPushButton
    resumeRoutine_btn: QPushButton
    setStageSequence_btn: QPushButton
    setProjectionSettings_btn: QPushButton
    configuration_btn: QPushButton
    autoSolidProjection_btn: QPushButton
    startRoutine_btn: QPushButton
    resumePauseMode_check: QCheckBox
    connect_btn: QPushButton
    disconnect_btn: QPushButton
    status_label: QLabel
    msg_input: QLineEdit
    backend_select: QComboBox
    timer: QTimer
    stage_routine: StageRoutine

    def _stage_ports_for_backend(self, backend: str) -> tuple[str, int, int]: ...
    def _stage_status_prefix(self) -> str: ...
    def _apply_microscope_default_exposure(self, manager: CameraBackend) -> None: ...
    def _create_camera_manager(self, backend: str) -> CameraBackend: ...
    def _camera_title(self, cam_index: int, camera_detected: bool) -> str: ...
    def _set_camera_controls_enabled(self, cam_index: int, enabled: bool) -> None: ...
    def _refresh_score_camera_choices(self) -> None: ...
    def _refresh_camera_ui_state(self) -> None: ...
    def on_characterization_camera_changed(self, _index: int | None = None) -> None: ...
    def on_backend_changed(self, _index: int | None = None) -> None: ...
    def _stop_pycro_helper_processes(self) -> None: ...
    def _wait_for_local_port(self, port: int, timeout_s: float = 20.0) -> bool: ...
    def _start_pycro_headless(self) -> None: ...
    def _start_pycro_bridge(self) -> None: ...
    def apply_exposure(self, cam_index: int, widget: QDoubleSpinBox, config_exposure: float | None = None) -> None: ...
    def apply_gain(self, cam_index: int, widget: QDoubleSpinBox, config_gain: float | None = None) -> None: ...
    def on_stage_event(self, msg: str) -> None: ...
    def _now_hhmmss(self) -> str: ...
    def _fmt_ts(self, ts_utc_ms: Any) -> str: ...
    def send_zmq_command(self) -> None: ...
    def update_frames(self) -> None: ...
    def connect_zmq(self) -> None: ...
    def disconnect_zmq(self) -> None: ...
    def _show_stage_connection_error(self, detail: str) -> None: ...
    def _probe_stage_connection(self, timeout_s: float = 3.0) -> bool: ...
    def _handle_stage_event_from_thread(self, msg: str) -> None: ...
    def _get_stage_seq(self) -> int: ...
    def _wait_for_stage_event(self, predicate: Callable[[StageEvent], bool], *, min_seq: int, timeout_s: float) -> StageEvent: ...
    def stage_get_position_xyz(self, timeout_s: float = 5.0) -> tuple[float, float, float]: ...
    def stage_move_to_xyz_and_wait(self, x: float, y: float, z: float, timeout_s: float = 30.0) -> None: ...
    def append_local_log(self, line: str) -> None: ...
    def send_message(self) -> None: ...
    def _on_stage_routine_finished(self) -> None: ...
    def resolution_app_after_routine(self) -> None: ...
    def _handle_completed_stage_stop_actions(self) -> bool: ...
    def open_stage_sequence_editor(self) -> None: ...
    def open_projection_settings_editor(self) -> None: ...
    def _resume_pause_enabled(self) -> bool: ...
    def _refresh_resume_button_state(self) -> None: ...
    def start_stage_routine(self) -> None: ...
    def resume_stage_routine(self) -> None: ...
    def send_stage_move(self, x: float, y: float, z: float) -> None: ...
    def closeEvent(self, event: QCloseEvent) -> None: ...
    def _on_screenshot(self, cam_index: int) -> None: ...
