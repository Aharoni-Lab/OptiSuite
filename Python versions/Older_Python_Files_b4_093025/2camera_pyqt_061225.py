import sys
import os
import clr
import gxipy as gx
import cv2
import numpy as np
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QMessageBox, QDialog, QGridLayout
)

try:
    cwd_path = os.path.join(os.getcwd(), 'SC3U.dll')
    clr.AddReference(os.path.abspath(cwd_path))
    print("Loaded SC3U from current dir")
except Exception as e:
    print(f"Failed to load SC3U from current dir: {e}")
    fallback_path = r"C:\Users\Melody\Documents\Melody School\UCLA\OCS Research\Python versions\OCS_op_new_052825\SC3U.dll"
    try:
        clr.AddReference(os.path.abspath(fallback_path))
        print("Loaded SC3U from fallback path")
    except Exception as e2:
        print(f"Failed to load SC3U from fallback path: {e2}")
        raise

try:
    from SC3Us import SC3U
    print("Imported SC3U class successfully")
except Exception as e:
    print(f"Failed to import SC3U class: {e}")
    raise


class StageParamDialog(QDialog):
    def __init__(self, parent=None, initial_params=None):
        super().__init__(parent)
        self.setWindowTitle("Stage Parameter Settings")
        self.setFixedSize(300, 300)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["Linear", "Rotary"])

        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["Millimeters", "Degrees"])

        self.angle_combo = QComboBox()
        self.angle_combo.addItems(["0.9", "1.8"])

        self.sub_combo = QComboBox()
        self.sub_combo.addItems(["1", "2", "4", "8"])

        self.pitch_combo = QComboBox()
        self.pitch_combo.addItems(["0.5", "1.0", "2.0"])

        self.travel_combo = QComboBox()
        self.travel_combo.addItems(["25", "50", "100"])

        self.ok_btn = QPushButton("Apply")

        layout = QVBoxLayout()
        for label, combo in [
            ("Stage Type", self.type_combo),
            ("Unit", self.unit_combo),
            ("Motor Angle", self.angle_combo),
            ("Subdivision", self.sub_combo),
            ("Pitch", self.pitch_combo),
            ("Travel", self.travel_combo)
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            row.addWidget(combo)
            layout.addLayout(row)

        layout.addWidget(self.ok_btn)
        self.setLayout(layout)

        self.ok_btn.clicked.connect(self.accept)

        if initial_params:
            self.type_combo.setCurrentIndex(initial_params.get("type", 0))
            self.unit_combo.setCurrentIndex(initial_params.get("unit", 0))
            self.angle_combo.setCurrentText(str(initial_params.get("motor_angle", "1.8")))
            self.sub_combo.setCurrentText(str(initial_params.get("subdivision", "8")))
            self.pitch_combo.setCurrentText(str(initial_params.get("pitch", "1.0")))
            self.travel_combo.setCurrentText(str(initial_params.get("travel", "50")))

    def get_params(self):
        return {
            "type": self.type_combo.currentIndex(),
            "unit": self.unit_combo.currentIndex(),
            "motor_angle": float(self.angle_combo.currentText()),
            "subdivision": int(self.sub_combo.currentText()),
            "pitch": float(self.pitch_combo.currentText()),
            "travel": float(self.travel_combo.currentText())
        }


class StageConnectionWorker(QObject):
    finished = pyqtSignal(bool)

    def __init__(self, stage_obj):
        super().__init__()
        self.stage_obj = stage_obj

    def run(self):
        try:
            self.stage_obj.ConnectPort(3)
            connected = self.stage_obj.ConnectStatus
            print(f"ConnectStatus: {connected}")
            self.finished.emit(connected)
        except Exception as e:
            print(f"Connection error: {e}")
            self.finished.emit(False)


class MotionStageApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Camera + Stage Control")
        self.setGeometry(100, 100, 1400, 600)

        self.my_control = SC3U()
        self.status_label = QLabel("Connection Status: Not connected")
        self.stage_params = None  # <-- IN-MEMORY PARAM STORE

        # Buttons
        self.connect_btn = QPushButton("Connect")
        self.param_btn = QPushButton("Set Parameters")

        self.x_plus_btn = QPushButton("X+")
        self.x_minus_btn = QPushButton("X-")
        self.y_plus_btn = QPushButton("Y+")
        self.y_minus_btn = QPushButton("Y-")
        self.z_plus_btn = QPushButton("Z+")
        self.z_minus_btn = QPushButton("Z-")

        self.connect_btn.clicked.connect(self.connect_stage)
        self.param_btn.clicked.connect(self.set_parameters)
        self.x_plus_btn.clicked.connect(lambda: self.nudge_stage(0, +1.0))
        self.x_minus_btn.clicked.connect(lambda: self.nudge_stage(0, -1.0))
        self.y_plus_btn.clicked.connect(lambda: self.nudge_stage(1, +1.0))
        self.y_minus_btn.clicked.connect(lambda: self.nudge_stage(1, -1.0))
        self.z_plus_btn.clicked.connect(lambda: self.nudge_stage(2, +1.0))
        self.z_minus_btn.clicked.connect(lambda: self.nudge_stage(2, -1.0))

        control_layout = QVBoxLayout()
        control_layout.addWidget(self.status_label)
        control_layout.addWidget(self.connect_btn)
        control_layout.addWidget(self.param_btn)

        move_layout = QGridLayout()
        move_layout.addWidget(self.x_minus_btn, 0, 0)
        move_layout.addWidget(self.x_plus_btn, 0, 1)
        move_layout.addWidget(self.y_minus_btn, 1, 0)
        move_layout.addWidget(self.y_plus_btn, 1, 1)
        move_layout.addWidget(self.z_minus_btn, 2, 0)
        move_layout.addWidget(self.z_plus_btn, 2, 1)
        control_layout.addLayout(move_layout)

        self.setLayout(control_layout)

    def connect_stage(self):
        self.status_label.setText("Connecting...")
        self.thread = QThread()
        self.worker = StageConnectionWorker(self.my_control)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_connection_result)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def on_connection_result(self, connected):
        if connected:
            # Set default stage parameters if not yet set
            if not self.stage_params:
                self.stage_params = {
                    "type": 0,             # 0: Linear
                    "unit": 0,             # 0: mm
                    "motor_angle": 1.8,
                    "subdivision": 8,
                    "pitch": 1.0,
                    "travel": 50
                }
            try:
                for axis in range(3):
                    self.my_control.SetType(axis, self.stage_params["type"])
                    self.my_control.SetUnit(axis, self.stage_params["unit"])
                    self.my_control.SetMotorAngle(axis, self.stage_params["motor_angle"])
                    self.my_control.SetSubsection(axis, self.stage_params["subdivision"])
                    self.my_control.SetPitch(axis, self.stage_params["pitch"])
                    self.my_control.SetTravel(axis, self.stage_params["travel"])
                    self.my_control.SaveParam(axis)
                    # Try LoadParam or Initialize if supported
                    # self.my_control.LoadParam(axis)

                # NOW try reading positions
                positions = [self.my_control.GetCurrentPosition(i) for i in range(3)]
                for i, p in enumerate(positions):
                    print(f"[DEBUG] Axis {i} current position: {p}")
                pos_str = ", ".join([f"Axis {i}: {p:.2f}" for i, p in enumerate(positions)])
                self.status_label.setText(f"Connected. {pos_str}")

            except Exception as e:
                self.status_label.setText(f"Connected, failed to init stage: {e}")
        else:
            self.status_label.setText("Connection Status: Failed")

    def set_parameters(self):
        if not self.my_control.ConnectStatus:
            self.status_label.setText("Stage not connected.")
            return

        try:
            dialog = StageParamDialog(self, initial_params=self.stage_params)
            result = dialog.exec_()
            print(f"Dialog result: {result}")

            if result == QDialog.Accepted:
                params = dialog.get_params()
                for axis in range(3):
                    print(f"Setting parameters for axis {axis}")
                    self.my_control.SetType(axis, params["type"])
                    self.my_control.SetUnit(axis, params["unit"])
                    self.my_control.SetMotorAngle(axis, params["motor_angle"])
                    self.my_control.SetSubsection(axis, params["subdivision"])
                    self.my_control.SetPitch(axis, params["pitch"])
                    self.my_control.SetTravel(axis, params["travel"])
                    self.my_control.SaveParam(axis)

                self.stage_params = params  # Save in-memory
                self.status_label.setText("Parameters set successfully.")

                positions = [self.my_control.GetCurrentPosition(i) for i in range(3)]
                pos_str = ", ".join([f"Axis {i}: {p:.2f}" for i, p in enumerate(positions)])
                self.status_label.setText(f"Parameters set. {pos_str}")

        except Exception as e:
            self.status_label.setText(f"Parameter Error: {e}")
            QMessageBox.critical(self, "Error", f"Parameter error: {e}")

def nudge_stage(self, axis, delta):
    if not self.my_control.ConnectStatus:
        QMessageBox.warning(self, "Stage not connected", "Please connect the stage first.")
        return
    try:
        current = self.my_control.GetCurrentPosition(axis)
        print(f"[DEBUG] Current position on axis {axis}: {current}")
        target_offset = delta  # RELATIVE movement
        self.my_control.RunToPosition(axis, target_offset)
        new_pos = self.my_control.GetCurrentPosition(axis)
        self.status_label.setText(f"Axis {axis} moved by {delta}. New position: {new_pos:.2f}")
    except Exception as e:
        QMessageBox.critical(self, "Move Error", str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MotionStageApp()
    window.show()
    sys.exit(app.exec_())
