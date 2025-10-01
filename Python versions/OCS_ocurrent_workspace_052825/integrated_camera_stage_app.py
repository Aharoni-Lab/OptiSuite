import sys
import os
import clr
import cv2
import numpy as np
import json
import threading
import time
from typing import Optional, Dict, Any

# Import local gxipy library
try:
    import gxipy as gx
    GXIPY_AVAILABLE = True
    print("gxipy imported successfully")
except ImportError as e:
    print(f"Warning: gxipy not available - camera functionality will be limited: {e}")
    GXIPY_AVAILABLE = False
except Exception as e:
    print(f"Warning: gxipy initialization failed - camera functionality will be limited: {e}")
    GXIPY_AVAILABLE = False

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QMessageBox, QDialog, QGridLayout, QLineEdit, QTextEdit,
    QGroupBox, QSpinBox, QDoubleSpinBox, QCheckBox, QTabWidget
)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, QObject, QMutex, QMutexLocker, Qt
from PyQt5.QtGui import QImage, QPixmap, QFont

# Load SC3U.dll
try:
    cwd_path = os.path.join(os.getcwd(), 'SC3U.dll')
    if not os.path.exists(cwd_path):
        raise FileNotFoundError(f"SC3U.dll not found in CWD: {cwd_path}")
    clr.AddReference(os.path.abspath(cwd_path))
    file_path = cwd_path
    print(f"Loaded SC3U.dll from: {cwd_path}")
except Exception as e:
    print(f"Failed to load from CWD: {e}")
    fallback_path = r"C:\Users\stimscope1\Documents\OptiSuite\Python versions\OCS_op_new_052825\SC3U.dll"
    if not os.path.exists(fallback_path):
        raise FileNotFoundError(f"SC3U.dll not found at fallback path: {fallback_path}")
    clr.AddReference(os.path.abspath(fallback_path))
    file_path = fallback_path
    print(f"Loaded SC3U.dll from fallback path: {fallback_path}")

from SC3Us import SC3U

class StageWorker(QObject):
    """Worker thread for stage operations to avoid blocking the GUI"""
    position_updated = pyqtSignal(int, float)  # axis, position
    connection_changed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)
    operation_completed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.stage_control = None
        self.mutex = QMutex()
        self.is_connected = False
        
    def initialize_stage(self):
        """Initialize the stage control object"""
        try:
            with QMutexLocker(self.mutex):
                self.stage_control = SC3U()
            self.operation_completed.emit("Stage control initialized")
        except Exception as e:
            self.error_occurred.emit(f"Failed to initialize stage: {e}")
    
    def connect_stage(self, port: int):
        """Connect to stage on specified port"""
        try:
            with QMutexLocker(self.mutex):
                if self.stage_control is None:
                    self.stage_control = SC3U()
                
                self.stage_control.ConnectPort(port)
                self.is_connected = self.stage_control.ConnectStatus
                
            self.connection_changed.emit(self.is_connected)
            if self.is_connected:
                self.operation_completed.emit(f"Connected to stage on port {port}")
                # Set default parameters to avoid DLL GUI issues
                self._set_default_parameters()
            else:
                self.error_occurred.emit("Failed to connect to stage")
                
        except Exception as e:
            self.error_occurred.emit(f"Connection error: {e}")
            self.connection_changed.emit(False)
    
    def _set_default_parameters(self):
        """Set default parameters to avoid DLL GUI dependency issues"""
        try:
            with QMutexLocker(self.mutex):
                if not self.stage_control or not self.is_connected:
                    return
                
                # Try to display the parameter interface first (this might be required)
                try:
                    self.stage_control.DisplayParameterInterface()
                    self.operation_completed.emit("Parameter interface displayed")
                except Exception as e:
                    self.operation_completed.emit(f"Parameter interface display failed: {e}")
                
                # Set parameters for all 3 axes (required to suppress DLL dialog)
                for axis in range(3):
                    # Set the current axis to the one we're configuring
                    self.stage_control.CurrentAxis = axis
                    
                    # Set parameters (this updates both variables and GUI controls)
                    self.stage_control.SetType(axis, 0)        # Linear stage
                    self.stage_control.SetUnit(axis, 0)        # Millimeters
                    self.stage_control.SetMotorAngle(axis, 1.8)  # 1.8 degrees
                    self.stage_control.SetSubsection(axis, 2)   # Microstepping
                    self.stage_control.SetPitch(axis, 1.0)     # 1mm per revolution
                    self.stage_control.SetTravel(axis, 100)    # 100mm travel
                    
                    # Save parameters - now the GUI controls have the correct values
                    self.stage_control.SaveParam(axis)
                    
            self.operation_completed.emit("Default parameters set and saved")
        except Exception as e:
            self.error_occurred.emit(f"Parameter setting error: {e}")
    
    def get_current_position(self, axis: int) -> float:
        """Get current position of specified axis"""
        try:
            with QMutexLocker(self.mutex):
                if self.stage_control and self.is_connected:
                    return self.stage_control.GetCurrentPosition(axis)
                return 0.0
        except Exception as e:
            self.error_occurred.emit(f"Position read error: {e}")
            return 0.0
    
    def move_to_position(self, axis: int, target_position: float):
        """Move stage to target position"""
        try:
            with QMutexLocker(self.mutex):
                if not self.stage_control or not self.is_connected:
                    self.error_occurred.emit("Stage not connected")
                    return
                
                current_pos = self.stage_control.GetCurrentPosition(axis)
                delta = target_position - current_pos
                self.stage_control.RunToPosition(axis, delta)
                
            self.operation_completed.emit(f"Moved axis {axis} to {target_position:.2f}mm")
        except Exception as e:
            self.error_occurred.emit(f"Movement error: {e}")
    
    def nudge_stage(self, axis: int, delta: float):
        """Move stage by a small amount"""
        try:
            with QMutexLocker(self.mutex):
                if not self.stage_control or not self.is_connected:
                    self.error_occurred.emit("Stage not connected")
                    return
                
                self.stage_control.RunToPosition(axis, delta)
                
            self.operation_completed.emit(f"Nudged axis {axis} by {delta:.2f}mm")
        except Exception as e:
            self.error_occurred.emit(f"Nudge error: {e}")
    
    def display_parameter_interface(self):
        """Display the DLL's parameter interface"""
        try:
            with QMutexLocker(self.mutex):
                if not self.stage_control or not self.is_connected:
                    self.error_occurred.emit("Stage not connected")
                    return
                
                # Display the parameter interface - this might trigger the "Parameter setting completed!" message
                self.stage_control.DisplayParameterInterface()
                self.operation_completed.emit("Parameter interface displayed")
        except Exception as e:
            self.error_occurred.emit(f"Parameter interface display error: {e}")
    
    def apply_parameters(self, params):
        """Apply parameters to the stage"""
        try:
            with QMutexLocker(self.mutex):
                if not self.stage_control or not self.is_connected:
                    self.error_occurred.emit("Stage not connected")
                    return
                
                # Apply parameters for all 3 axes
                for axis in range(3):
                    # Set the current axis to the one we're configuring
                    self.stage_control.CurrentAxis = axis
                    
                    # Apply parameters (this updates both variables and GUI controls)
                    self.stage_control.SetType(axis, params["type"])
                    self.stage_control.SetUnit(axis, params["unit"])
                    self.stage_control.SetMotorAngle(axis, params["motor_angle"])
                    self.stage_control.SetSubsection(axis, params["subdivision"])
                    self.stage_control.SetPitch(axis, params["pitch"])
                    self.stage_control.SetTravel(axis, params["travel"])
                    
                    # Save parameters - now the GUI controls have the correct values
                    self.stage_control.SaveParam(axis)
                    
            self.operation_completed.emit("Parameters applied and saved successfully")
        except Exception as e:
            self.error_occurred.emit(f"Parameter application error: {e}")
    
    def disconnect_stage(self):
        """Disconnect from stage"""
        try:
            with QMutexLocker(self.mutex):
                if self.stage_control and self.is_connected:
                    self.stage_control.ClosePort()
                    self.is_connected = False
                    
            self.connection_changed.emit(False)
            self.operation_completed.emit("Stage disconnected")
        except Exception as e:
            self.error_occurred.emit(f"Disconnect error: {e}")

class CameraWorker(QObject):
    """Worker thread for camera operations"""
    frame_ready = pyqtSignal(np.ndarray)
    camera_connected = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.device_manager = None
        self.device = None
        self.is_running = False
        self.mutex = QMutex()
        
    def initialize_camera(self):
        """Initialize camera system"""
        if not GXIPY_AVAILABLE:
            self.error_occurred.emit("gxipy library not available - camera functionality disabled")
            self.camera_connected.emit(False)
            return
            
        try:
            with QMutexLocker(self.mutex):
                self.device_manager = gx.DeviceManager()
                device_num, device_info_list = self.device_manager.update_device_list()
                
                if device_num == 0:
                    self.error_occurred.emit("No camera devices found")
                    return
                
                # Use first available camera
                self.device = self.device_manager.open_device_by_index(1)
                self.device.TriggerMode.set(gx.GxSwitchEntry.OFF)
                self.device.ExposureTime.set(10000)  # 10ms exposure
                self.device.Gain.set(1.0)
                
                # Start acquisition
                self.device.stream_on()
                self.is_running = True
                
            self.camera_connected.emit(True)
        except Exception as e:
            self.error_occurred.emit(f"Camera initialization error: {e}")
            self.camera_connected.emit(False)
    
    def start_capture(self):
        """Start continuous image capture"""
        if not GXIPY_AVAILABLE:
            return
            
        self.is_running = True
        while self.is_running:
            try:
                with QMutexLocker(self.mutex):
                    if self.device and self.is_running:
                        raw_image = self.device.data_stream[0].get_image()
                        if raw_image.get_status() == gx.GxFrameStatusList.SUCCESS:
                            numpy_image = raw_image.get_numpy_array()
                            if numpy_image is not None:
                                self.frame_ready.emit(numpy_image)
                time.sleep(0.033)  # ~30 FPS
            except Exception as e:
                self.error_occurred.emit(f"Capture error: {e}")
                break
    
    def stop_capture(self):
        """Stop image capture"""
        with QMutexLocker(self.mutex):
            self.is_running = False
    
    def disconnect_camera(self):
        """Disconnect camera"""
        if not GXIPY_AVAILABLE:
            self.camera_connected.emit(False)
            return
            
        try:
            with QMutexLocker(self.mutex):
                self.is_running = False
                if self.device:
                    self.device.stream_off()
                    self.device.close_device()
                    self.device = None
                    
            self.camera_connected.emit(False)
        except Exception as e:
            self.error_occurred.emit(f"Camera disconnect error: {e}")

class StageParamDialog(QDialog):
    """Dialog for setting stage parameters"""
    def __init__(self, parent=None, initial_params=None):
        super().__init__(parent)
        self.setWindowTitle("Stage Parameter Settings")
        self.setFixedSize(400, 500)
        
        # Default parameters
        self.params = initial_params or {
            "type": 0, "unit": 0, "motor_angle": 1.8,
            "subdivision": 2, "pitch": 1.0, "travel": 100
        }
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Stage Type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Stage Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Linear", "Rotary"])
        self.type_combo.setCurrentIndex(self.params["type"])
        type_layout.addWidget(self.type_combo)
        layout.addLayout(type_layout)
        
        # Unit
        unit_layout = QHBoxLayout()
        unit_layout.addWidget(QLabel("Unit:"))
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["Millimeters", "Degrees"])
        self.unit_combo.setCurrentIndex(self.params["unit"])
        unit_layout.addWidget(self.unit_combo)
        layout.addLayout(unit_layout)
        
        # Motor Angle
        angle_layout = QHBoxLayout()
        angle_layout.addWidget(QLabel("Motor Angle:"))
        self.angle_spin = QDoubleSpinBox()
        self.angle_spin.setRange(0.1, 10.0)
        self.angle_spin.setValue(self.params["motor_angle"])
        self.angle_spin.setSuffix("°")
        angle_layout.addWidget(self.angle_spin)
        layout.addLayout(angle_layout)
        
        # Subdivision
        sub_layout = QHBoxLayout()
        sub_layout.addWidget(QLabel("Subdivision:"))
        self.sub_spin = QSpinBox()
        self.sub_spin.setRange(1, 256)
        self.sub_spin.setValue(self.params["subdivision"])
        sub_layout.addWidget(self.sub_spin)
        layout.addLayout(sub_layout)
        
        # Pitch
        pitch_layout = QHBoxLayout()
        pitch_layout.addWidget(QLabel("Pitch:"))
        self.pitch_spin = QDoubleSpinBox()
        self.pitch_spin.setRange(0.1, 10.0)
        self.pitch_spin.setValue(self.params["pitch"])
        self.pitch_spin.setSuffix(" mm/rev")
        pitch_layout.addWidget(self.pitch_spin)
        layout.addLayout(pitch_layout)
        
        # Travel
        travel_layout = QHBoxLayout()
        travel_layout.addWidget(QLabel("Travel Range:"))
        self.travel_spin = QDoubleSpinBox()
        self.travel_spin.setRange(1.0, 1000.0)
        self.travel_spin.setValue(self.params["travel"])
        self.travel_spin.setSuffix(" mm")
        travel_layout.addWidget(self.travel_spin)
        layout.addLayout(travel_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.ok_btn = QPushButton("Apply")
        self.cancel_btn = QPushButton("Cancel")
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def get_params(self):
        """Get current parameter values"""
        return {
            "type": self.type_combo.currentIndex(),
            "unit": self.unit_combo.currentIndex(),
            "motor_angle": self.angle_spin.value(),
            "subdivision": self.sub_spin.value(),
            "pitch": self.pitch_spin.value(),
            "travel": self.travel_spin.value()
        }

class IntegratedCameraStageApp(QWidget):
    """Main application window integrating camera and stage control"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Integrated Camera & Stage Control System")
        self.setGeometry(100, 100, 1400, 800)
        
        # Initialize workers
        self.stage_worker = StageWorker()
        self.camera_worker = CameraWorker()
        
        # Threads
        self.stage_thread = QThread()
        self.camera_thread = QThread()
        
        # Move workers to threads
        self.stage_worker.moveToThread(self.stage_thread)
        self.camera_worker.moveToThread(self.camera_thread)
        
        # Connect signals
        self.connect_signals()
        
        # Start threads
        self.stage_thread.start()
        self.camera_thread.start()
        
        # Initialize UI
        self.setup_ui()
        
        # Initialize stage control
        self.stage_worker.initialize_stage()
        
    def connect_signals(self):
        """Connect worker signals to UI slots"""
        # Stage signals
        self.stage_worker.connection_changed.connect(self.on_stage_connection_changed)
        self.stage_worker.error_occurred.connect(self.on_stage_error)
        self.stage_worker.operation_completed.connect(self.on_stage_operation_completed)
        
        # Camera signals
        self.camera_worker.frame_ready.connect(self.update_camera_display)
        self.camera_worker.camera_connected.connect(self.on_camera_connection_changed)
        self.camera_worker.error_occurred.connect(self.on_camera_error)
        
    def setup_ui(self):
        """Setup the user interface"""
        main_layout = QHBoxLayout()
        
        # Left panel - Camera
        camera_group = QGroupBox("Camera Feed")
        camera_layout = QVBoxLayout()
        
        self.camera_label = QLabel("Camera Not Connected")
        self.camera_label.setFixedSize(640, 480)
        self.camera_label.setStyleSheet("border: 1px solid black; background-color: black; color: white;")
        self.camera_label.setAlignment(Qt.AlignCenter)
        camera_layout.addWidget(self.camera_label)
        
        # Camera controls
        camera_controls = QHBoxLayout()
        self.camera_connect_btn = QPushButton("Connect Camera")
        self.camera_disconnect_btn = QPushButton("Disconnect Camera")
        self.camera_disconnect_btn.setEnabled(False)
        
        self.camera_connect_btn.clicked.connect(self.connect_camera)
        self.camera_disconnect_btn.clicked.connect(self.disconnect_camera)
        
        camera_controls.addWidget(self.camera_connect_btn)
        camera_controls.addWidget(self.camera_disconnect_btn)
        camera_layout.addLayout(camera_controls)
        
        camera_group.setLayout(camera_layout)
        main_layout.addWidget(camera_group)
        
        # Right panel - Stage Control
        stage_group = QGroupBox("Stage Control")
        stage_layout = QVBoxLayout()
        
        # Connection controlsf
        conn_layout = QHBoxLayout()
        conn_layout.addWidget(QLabel("Port:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 10)
        #change this value based on the actual COM port number
        self.port_spin.setValue(4)
        conn_layout.addWidget(self.port_spin)
        
        self.stage_connect_btn = QPushButton("Connect Stage")
        self.stage_disconnect_btn = QPushButton("Disconnect Stage")
        self.stage_disconnect_btn.setEnabled(False)
        
        self.stage_connect_btn.clicked.connect(self.connect_stage)
        self.stage_disconnect_btn.clicked.connect(self.disconnect_stage)
        
        conn_layout.addWidget(self.stage_connect_btn)
        conn_layout.addWidget(self.stage_disconnect_btn)
        stage_layout.addLayout(conn_layout)
        
        # Status
        self.status_label = QLabel("Stage Status: Not Connected")
        stage_layout.addWidget(self.status_label)
        
        # Position display
        pos_group = QGroupBox("Current Position")
        pos_layout = QGridLayout()
        
        for i, axis in enumerate(['X', 'Y', 'Z']):
            pos_layout.addWidget(QLabel(f"{axis}:"), i, 0)
            pos_label = QLabel("0.00")
            pos_label.setStyleSheet("font-weight: bold;")
            setattr(self, f"pos_{axis.lower()}_label", pos_label)
            pos_layout.addWidget(pos_label, i, 1)
            pos_layout.addWidget(QLabel("mm"), i, 2)
        
        pos_group.setLayout(pos_layout)
        stage_layout.addWidget(pos_group)
        
        # Movement controls
        move_group = QGroupBox("Movement Control")
        move_layout = QVBoxLayout()
        
        # Target position
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Target Position:"))
        self.target_x = QDoubleSpinBox()
        self.target_x.setRange(-1000, 1000)
        self.target_x.setSuffix(" mm")
        self.target_y = QDoubleSpinBox()
        self.target_y.setRange(-1000, 1000)
        self.target_y.setSuffix(" mm")
        self.target_z = QDoubleSpinBox()
        self.target_z.setRange(-1000, 1000)
        self.target_z.setSuffix(" mm")
        
        target_layout.addWidget(QLabel("X:"))
        target_layout.addWidget(self.target_x)
        target_layout.addWidget(QLabel("Y:"))
        target_layout.addWidget(self.target_y)
        target_layout.addWidget(QLabel("Z:"))
        target_layout.addWidget(self.target_z)
        
        move_layout.addLayout(target_layout)
        
        # Move button
        self.move_btn = QPushButton("Move to Position")
        self.move_btn.clicked.connect(self.move_to_position)
        self.move_btn.setEnabled(False)
        move_layout.addWidget(self.move_btn)
        
        # Nudge controls
        nudge_layout = QGridLayout()
        nudge_layout.addWidget(QLabel("Nudge Controls:"), 0, 0, 1, 3)
        
        for i, axis in enumerate(['X', 'Y', 'Z']):
            nudge_layout.addWidget(QLabel(f"{axis}:"), i+1, 0)
            
            # Negative nudge
            neg_btn = QPushButton(f"-{axis}")
            neg_btn.clicked.connect(lambda checked, ax=i: self.nudge_stage(ax, -0.1))
            nudge_layout.addWidget(neg_btn, i+1, 1)
            
            # Positive nudge
            pos_btn = QPushButton(f"+{axis}")
            pos_btn.clicked.connect(lambda checked, ax=i: self.nudge_stage(ax, 0.1))
            nudge_layout.addWidget(pos_btn, i+1, 2)
        
        move_layout.addLayout(nudge_layout)
        move_group.setLayout(move_layout)
        stage_layout.addWidget(move_group)
        
        # Parameters
        param_layout = QHBoxLayout()
        self.param_btn = QPushButton("Set Parameters")
        self.param_btn.clicked.connect(self.set_parameters)
        self.param_btn.setEnabled(False)
        param_layout.addWidget(self.param_btn)
        
        self.test_position_btn = QPushButton("Test GetCurrentPosition")
        self.test_position_btn.clicked.connect(self.test_current_position)
        self.test_position_btn.setEnabled(False)
        param_layout.addWidget(self.test_position_btn)
        
        stage_layout.addLayout(param_layout)
        
        # Log
        log_group = QGroupBox("Operation Log")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        stage_layout.addWidget(log_group)
        
        stage_group.setLayout(stage_layout)
        main_layout.addWidget(stage_group)
        
        self.setLayout(main_layout)
        
        # Update timer for position display
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_position_display)
        self.update_timer.start(100)  # Update every 100ms
    
    def connect_camera(self):
        """Connect to camera"""
        self.camera_worker.initialize_camera()
        # Start capture in a separate thread
        threading.Thread(target=self.camera_worker.start_capture, daemon=True).start()
    
    def disconnect_camera(self):
        """Disconnect camera"""
        self.camera_worker.disconnect_camera()
    
    def connect_stage(self):
        """Connect to stage"""
        port = self.port_spin.value()
        self.stage_worker.connect_stage(port)
    
    def disconnect_stage(self):
        """Disconnect stage"""
        self.stage_worker.disconnect_stage()
    
    def set_parameters(self):
        """Open parameter setting dialog"""
        try:
            # First try to display the DLL's parameter interface
            self.stage_worker.display_parameter_interface()
            
            # Then show our custom dialog
            dialog = StageParamDialog(self)
            if dialog.exec_() == QDialog.Accepted:
                params = dialog.get_params()
                self.log_message(f"Parameters set: {params}")
                # Apply parameters to stage
                self.apply_stage_parameters(params)
        except Exception as e:
            self.log_message(f"Parameter dialog error: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open parameter dialog: {e}")
    
    def test_current_position(self):
        """Test GetCurrentPosition for all axes"""
        if not self.stage_worker.is_connected:
            self.log_message("Stage not connected")
            return
        
        self.log_message("Testing GetCurrentPosition...")
        for axis in range(3):
            pos = self.stage_worker.get_current_position(axis)
            self.log_message(f"Axis {axis} ({'XYZ'[axis]}): {pos:.3f} mm")
        
        # Also update the display
        self.update_position_display()
    
    def apply_stage_parameters(self, params):
        """Apply parameters to the stage"""
        try:
            # Call the stage worker to apply parameters
            self.stage_worker.apply_parameters(params)
        except Exception as e:
            self.log_message(f"Parameter application error: {e}")
            QMessageBox.critical(self, "Error", f"Failed to apply parameters: {e}")
    
    def move_to_position(self):
        """Move stage to target position"""
        x = self.target_x.value()
        y = self.target_y.value()
        z = self.target_z.value()
        
        # Move each axis
        for axis, pos in enumerate([x, y, z]):
            if pos != 0:  # Only move if position is not zero
                self.stage_worker.move_to_position(axis, pos)
    
    def nudge_stage(self, axis: int, delta: float):
        """Nudge stage by small amount"""
        self.stage_worker.nudge_stage(axis, delta)
    
    def update_camera_display(self, frame: np.ndarray):
        """Update camera display with new frame"""
        try:
            # Convert BGR to RGB
            if len(frame.shape) == 3:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                frame_rgb = frame
            
            # Convert to QImage
            height, width, channel = frame_rgb.shape
            bytes_per_line = 3 * width
            q_image = QImage(frame_rgb.data, width, height, bytes_per_line, QImage.Format_RGB888)
            
            # Scale to fit display
            pixmap = QPixmap.fromImage(q_image)
            scaled_pixmap = pixmap.scaled(self.camera_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            self.camera_label.setPixmap(scaled_pixmap)
        except Exception as e:
            self.log_message(f"Camera display error: {e}")
    
    def update_position_display(self):
        """Update position display"""
        if hasattr(self, 'stage_worker') and self.stage_worker.is_connected:
            for i, axis in enumerate(['x', 'y', 'z']):
                pos = self.stage_worker.get_current_position(i)
                label = getattr(self, f"pos_{axis}_label")
                label.setText(f"{pos:.2f}")
    
    def on_stage_connection_changed(self, connected: bool):
        """Handle stage connection status change"""
        if connected:
            self.status_label.setText("Stage Status: Connected")
            self.stage_connect_btn.setEnabled(False)
            self.stage_disconnect_btn.setEnabled(True)
            self.move_btn.setEnabled(True)
            self.param_btn.setEnabled(True)
            self.test_position_btn.setEnabled(True)
        else:
            self.status_label.setText("Stage Status: Not Connected")
            self.stage_connect_btn.setEnabled(True)
            self.stage_disconnect_btn.setEnabled(False)
            self.move_btn.setEnabled(False)
            self.param_btn.setEnabled(False)
            self.test_position_btn.setEnabled(False)
    
    def on_camera_connection_changed(self, connected: bool):
        """Handle camera connection status change"""
        if connected:
            self.camera_connect_btn.setEnabled(False)
            self.camera_disconnect_btn.setEnabled(True)
            self.camera_label.setText("Camera Connected")
        else:
            self.camera_connect_btn.setEnabled(True)
            self.camera_disconnect_btn.setEnabled(False)
            self.camera_label.setText("Camera Not Connected")
            self.camera_label.setPixmap(QPixmap())
    
    def on_stage_error(self, error_msg: str):
        """Handle stage errors"""
        self.log_message(f"Stage Error: {error_msg}")
        QMessageBox.warning(self, "Stage Error", error_msg)
    
    def on_camera_error(self, error_msg: str):
        """Handle camera errors"""
        self.log_message(f"Camera Error: {error_msg}")
        QMessageBox.warning(self, "Camera Error", error_msg)
    
    def on_stage_operation_completed(self, message: str):
        """Handle stage operation completion"""
        self.log_message(f"Stage: {message}")
    
    def log_message(self, message: str):
        """Add message to log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
    
    def closeEvent(self, event):
        """Clean up on application close"""
        self.camera_worker.disconnect_camera()
        self.stage_worker.disconnect_stage()
        
        self.stage_thread.quit()
        self.camera_thread.quit()
        
        self.stage_thread.wait()
        self.camera_thread.wait()
        
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = IntegratedCameraStageApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
