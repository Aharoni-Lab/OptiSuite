import sys 
import os
import clr
import cv2
import numpy as np
import json
import gxipy as gx

from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, 
                             QVBoxLayout, QHBoxLayout, QLineEdit, QGridLayout)
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QImage, QPixmap

# Load SC3U.dll
file_path = None
try:
    cwd_path = os.path.join(os.getcwd(), 'SC3U.dll')
    if not os.path.exists(cwd_path):
        raise FileNotFoundError(f"SC3U.dll not found in CWD: {cwd_path}")
    clr.AddReference(os.path.abspath(cwd_path))
    file_path = cwd_path
except Exception as e:
    print(f"Failed to load from CWD: {e}")
    fallback_path = r"C:\\Users\\Melody\\Documents\\Melody School\\UCLA\\OCS Research\\Python versions\\OCS_op_new_052825\\SC3U.dll"
    if not os.path.exists(fallback_path):
        raise FileNotFoundError(f"SC3U.dll not found at fallback path: {fallback_path}")
    clr.AddReference(os.path.abspath(fallback_path))
    file_path = fallback_path

from SC3Us import SC3U

CONFIG_FILE = "stage_config.json"

class CameraControlApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt Camera + Stage Control")
        self.setGeometry(100, 100, 1100, 600)

        # UI Elements
        self.camera_label = QLabel("Camera Feed")
        self.camera_label.setFixedSize(640, 480)

        self.status_label = QLabel("Connection Status: Not connected")
        self.connect_btn = QPushButton("Connect")
        self.param_btn = QPushButton("Set Parameters")
        self.save_param_btn = QPushButton("Save Parameters")

        self.position_input = QLineEdit()
        self.position_input.setPlaceholderText("Enter position")
        self.run_btn = QPushButton("Move")

        # Parameter fields
        self.param_fields = {}
        param_labels = ["Type", "Unit", "Motor Angle", "Subsection", "Pitch", "Travel"]
        for label in param_labels:
            self.param_fields[label] = QLineEdit()
            self.param_fields[label].setPlaceholderText(label)

        # Layout
        param_layout = QVBoxLayout()
        for label in param_labels:
            param_layout.addWidget(QLabel(label))
            param_layout.addWidget(self.param_fields[label])

        btn_layout = QVBoxLayout()
        btn_layout.addWidget(self.status_label)
        btn_layout.addWidget(self.connect_btn)
        btn_layout.addWidget(self.param_btn)
        btn_layout.addWidget(self.save_param_btn)
        btn_layout.addLayout(param_layout)
        btn_layout.addWidget(QLabel("Move to Position:"))
        btn_layout.addWidget(self.position_input)
        btn_layout.addWidget(self.run_btn)

        layout = QHBoxLayout()
        layout.addWidget(self.camera_label)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

        # SC3U stage setup
        self.my_control = SC3U()
        self.connect_btn.clicked.connect(self.connect_stage)
        self.param_btn.clicked.connect(self.set_parameters)
        self.save_param_btn.clicked.connect(self.save_parameters)
        self.run_btn.clicked.connect(self.move_to_position)

        # Load saved config if exists
        self.load_parameters()

        # DaHeng camera setup
        self.device_manager = gx.DeviceManager()
        dev_info_list = self.device_manager.update_device_list()
        if len(dev_info_list) == 0:
            raise Exception("No Daheng camera found.")
        self.cam = self.device_manager.open_device_by_index(1)
        self.cam.TriggerMode.set(gx.GxSwitchEntry.OFF)
        self.cam.stream_on()

        # Timer to refresh camera feed
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

    def connect_stage(self):
        self.my_control.ConnectPort(6)
        connected = self.my_control.ConnectStatus
        self.status_label.setText(f"Connection Status: {'Connected' if connected else 'Failed'}")

    def set_parameters(self):
        if self.my_control.ConnectStatus:
            try:
                t = int(self.param_fields["Type"].text())
                u = int(self.param_fields["Unit"].text())
                a = float(self.param_fields["Motor Angle"].text())
                s = int(self.param_fields["Subsection"].text())
                p = float(self.param_fields["Pitch"].text())
                tr = float(self.param_fields["Travel"].text())

                self.my_control.SetType(0, t)
                self.my_control.SetUnit(0, u)
                self.my_control.SetMotorAngle(0, a)
                self.my_control.SetSubsection(0, s)
                self.my_control.SetPitch(0, p)
                self.my_control.SetTravel(0, tr)
                self.my_control.SaveParam(0)
            except Exception as e:
                self.status_label.setText(f"Parameter Error: {e}")

    def save_parameters(self):
        params = {
            "Type": self.param_fields["Type"].text(),
            "Unit": self.param_fields["Unit"].text(),
            "Motor Angle": self.param_fields["Motor Angle"].text(),
            "Subsection": self.param_fields["Subsection"].text(),
            "Pitch": self.param_fields["Pitch"].text(),
            "Travel": self.param_fields["Travel"].text()
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(params, f, indent=4)
        self.status_label.setText("Parameters saved.")

    def load_parameters(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                params = json.load(f)
                for key, val in params.items():
                    if key in self.param_fields:
                        self.param_fields[key].setText(str(val))

    def move_to_position(self):
        if self.my_control.ConnectStatus:
            try:
                target = float(self.position_input.text())
                current = self.my_control.GetCurrentPosition(0)
                self.my_control.RunToPosition(0, target - current)
            except Exception as e:
                self.status_label.setText(f"Invalid position: {e}")

    def update_frame(self):
        if not hasattr(self, "cam") or self.cam is None:
            return

        try:
            raw_image = self.cam.data_stream[0].get_image()
            if raw_image is None:
                return

            rgb_image = raw_image.convert("RGB")
            img_np = rgb_image.get_numpy_array()

            h, w, ch = img_np.shape
            bytes_per_line = ch * w
            q_img = QImage(img_np.data, w, h, bytes_per_line, QImage.Format_RGB888)
            self.camera_label.setPixmap(QPixmap.fromImage(q_img))

        except gx.Exception as e:
            print(f"Camera Error (likely during shutdown): {e}")

    def closeEvent(self, event):
        self.timer.stop()
        if hasattr(self, "cam") and self.cam is not None:
            try:
                self.cam.stream_off()
                self.cam.close_device()
            except Exception as e:
                print(f"Error during camera shutdown: {e}")
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CameraControlApp()
    window.show()
    sys.exit(app.exec_())
