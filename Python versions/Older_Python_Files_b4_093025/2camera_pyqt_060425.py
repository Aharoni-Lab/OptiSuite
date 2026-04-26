import sys
import os
import clr
import json
import gxipy as gx
import cv2
import numpy as np

from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QComboBox, QLineEdit, QMessageBox, QDialog
from PyQt5.QtCore import QTimer, QObject, QThread, pyqtSignal

from PyQt5.QtGui import QImage, QPixmap

# Load SC3U.dll
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


class StageConnectionWorker(QObject):
    finished = pyqtSignal(bool)

    def __init__(self, control):
        super().__init__()
        self.control = control

    def run(self):
        try:
            
            self.control.ConnectPort(3)
            connected = self.control.ConnectStatus
            print(f"ConnectStatus: {connected}")
            self.finished.emit(connected)

        except Exception as e:
            print(f"Connection error: {e}")
            self.finished.emit(False)



from SC3Us import SC3U

class StageParamDialog(QDialog):
    def __init__(self, parent=None):
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



    def get_params(self):
        return {
            "type": 1 if self.type_combo.currentText() == "Linear" else 0,
            "unit": 0 if self.unit_combo.currentText() == "Millimeters" else 1,
            "motor_angle": float(self.angle_combo.currentText()),
            "subdivision": int(self.sub_combo.currentText()),
            "pitch": float(self.pitch_combo.currentText()),
            "travel": float(self.travel_combo.currentText())
        }


class MotionControlApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt Dual Camera + Stage Control")
        self.setGeometry(100, 100, 1400, 600)

        # UI Elements
        self.camera_label_1 = QLabel("Camera 1")
        self.camera_label_1.setStyleSheet("font-weight: bold; font-size: 16px;")
        self.camera_label_1.setFixedSize(300, 500)

        self.camera_label_2 = QLabel("Camera 2")
        self.camera_label_2.setStyleSheet("font-weight: bold; font-size: 16px;")
        self.camera_label_2.setFixedSize(300, 200)

        self.status_label = QLabel("Connection Status: Not connected")
        self.connect_btn = QPushButton("Connect")
        self.param_btn = QPushButton("Set Parameters")
        self.run_btn = QPushButton("Run")
        self.position_input = QLineEdit()
        self.position_input.setPlaceholderText("Enter position")

        self.position_display = QLabel("Current Position: N/A")
        self.position_display.setStyleSheet("font-size: 16px; padding: 10px;")


        # Layout setup: H for horizontal, V for vertical

        '''middle_layout = QVBoxLayout()
        
        middle_layout.addWidget(QLabel("Camera 1"))
        middle_layout.addWidget(self.camera_label_1)

        right_layout = QVBoxLayout()
        middle_layout.addWidget(QLabel("Camera 2"))
        right_layout.addWidget(self.camera_label_2)


        control_layout = QVBoxLayout()
        control_layout.addWidget(self.status_label)
        control_layout.addWidget(self.connect_btn)
        control_layout.addWidget(self.param_btn)
        control_layout.addWidget(QLabel("Move to Position:"))
        control_layout.addWidget(self.position_input)
        control_layout.addWidget(self.run_btn)

        main_layout = QHBoxLayout()
        main_layout.addLayout(control_layout)
        main_layout.addLayout(middle_layout)
        main_layout.addLayout(right_layout)
        self.setLayout(main_layout)'''

        # Left Column (Control Buttons)
        control_layout = QVBoxLayout()
        control_layout.addWidget(self.status_label)
        control_layout.addWidget(self.connect_btn)
        control_layout.addWidget(self.param_btn)
        control_layout.addWidget(QLabel("Move to Position:"))
        control_layout.addWidget(self.position_input)
        control_layout.addWidget(self.run_btn)

        # Middle Column (Cameras)
        camera_layout = QVBoxLayout()
        camera_layout.addWidget(QLabel("Camera 1"))
        camera_layout.addWidget(self.camera_label_1)
        camera_layout.addWidget(QLabel("Camera 2"))
        camera_layout.addWidget(self.camera_label_2)

        # Right Column (Stage Monitor)
        stage_layout = QVBoxLayout()
        stage_layout.addWidget(QLabel("Stage Monitor"))
        stage_layout.addWidget(self.position_display)

        # Combine into main layout
        main_layout = QHBoxLayout()
        main_layout.addLayout(control_layout)
        main_layout.addLayout(camera_layout)
        main_layout.addLayout(stage_layout)
        self.setLayout(main_layout)


        # Stage setup
        self.my_control = SC3U()
        print(f"SC3U instance created: {self.my_control}")

        self.connect_btn.clicked.connect(self.connect_stage)
        self.param_btn.clicked.connect(self.set_parameters)
        self.run_btn.clicked.connect(self.move_to_position)

        # Camera setup
        self.device_manager = gx.DeviceManager()
        dev_info_list = self.device_manager.update_device_list()
        self.cam1 = self.cam2 = None

        if len(dev_info_list) >= 1:
            self.cam1 = self.device_manager.open_device_by_index(1)
            self.cam1.TriggerMode.set(gx.GxSwitchEntry.OFF)
            self.cam1.stream_on()

        if len(dev_info_list) >= 2:
            self.cam2 = self.device_manager.open_device_by_index(2)
            self.cam2.TriggerMode.set(gx.GxSwitchEntry.OFF)
            self.cam2.stream_on()

        # Timer for refreshing images
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

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
        self.status_label.setText(f"Connection Status: {'Connected' if connected else 'Failed'}")

    
   


    def set_parameters(self):
        if not self.my_control.ConnectStatus:
            self.status_label.setText("Stage not connected.")
            return

        try:
            dialog = StageParamDialog(self)
            if dialog.exec_() == QDialog.Accepted:
                params = dialog.get_params()

                # Apply parameters
                # Apply parameters
            for axis in range(3):
                self.my_control.SetType(axis, params["type"])
                self.my_control.SetUnit(axis, params["unit"])
                self.my_control.SetMotorAngle(axis, params["motor_angle"])
                self.my_control.SetSubsection(axis, params["subdivision"])
                self.my_control.SetPitch(axis, params["pitch"])
                self.my_control.SetTravel(axis, params["travel"])
                self.my_control.SaveParam(axis)

                # Save to config
                with open("stage_config.json", "w") as f:
                    json.dump(params, f, indent=4)

                self.status_label.setText("Parameters set successfully.")
        except Exception as e:
            self.status_label.setText(f"Parameter Error: {e}")
            QMessageBox.critical(self, "Error", f"Parameter error: {e}")

    def move_to_position(self):
        if self.my_control.ConnectStatus:
            try:
                target = float(self.position_input.text())
                current = self.my_control.GetCurrentPosition(0)
                self.my_control.RunToPosition(0, target - current)
            except Exception as e:
                QMessageBox.critical(self, "Invalid Input", str(e))

    def update_frame(self):
        for cam, label in [(self.cam1, self.camera_label_1), (self.cam2, self.camera_label_2)]:
            if cam is None:
                continue
            try:
                raw_image = cam.data_stream[0].get_image()
                if raw_image is None:
                    continue
                rgb_image = raw_image.convert("RGB")
                img_np = rgb_image.get_numpy_array()
                h, w, ch = img_np.shape
                q_img = QImage(img_np.data, w, h, ch * w, QImage.Format_RGB888)
                label.setPixmap(QPixmap.fromImage(q_img))
            except gx.Exception as e:
                print(f"Camera Error: {e}")

    def closeEvent(self, event):
        self.timer.stop()
        for cam in [self.cam1, self.cam2]:
            if cam is not None:
                try:
                    cam.stream_off()
                    cam.close_device()
                except:
                    pass
        event.accept()

    def update_stage_position(self):
        if self.my_control.ConnectStatus:
            try:
                pos = self.my_control.GetCurrentPosition(0)
                self.position_display.setText(f"Current Position: {pos:.2f}")
            except Exception as e:
                self.position_display.setText(f"Error: {e}")
        else:
            self.position_display.setText("Stage not connected.")


    


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MotionControlApp()
    window.show()
    sys.exit(app.exec_())
