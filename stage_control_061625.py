import sys
import os
import clr
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QObject, QMetaObject
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QMessageBox, QDialog, QGridLayout
)

# Load DLL
try:
    cwd_path = os.path.join(os.getcwd(), 'SC3U.dll')
    clr.AddReference(os.path.abspath(cwd_path))
    print("Loaded SC3U from current dir")
except Exception:
    fallback_path = r"C:\Users\Melody\Documents\Melody School\UCLA\OCS Research\Python versions\OCS_op_new_052825\SC3U.dll"
    try:
        clr.AddReference(os.path.abspath(fallback_path))
        print("Loaded SC3U from fallback path")
    except Exception as e2:
        print(f"Failed to load SC3U from fallback path: {e2}")
        raise

from SC3Us import SC3U



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
            self.sub_combo.setCurrentText(str(initial_params.get("subdivision", "2")))
            self.pitch_combo.setCurrentText(str(initial_params.get("pitch", "1.0")))
            self.travel_combo.setCurrentText(str(initial_params.get("travel", "100")))

    def get_params(self):
        return {
            "type": self.type_combo.currentIndex(),
            "unit": self.unit_combo.currentIndex(),
            "motor_angle": float(self.angle_combo.currentText()),
            "subdivision": int(self.sub_combo.currentText()),
            "pitch": float(self.pitch_combo.currentText()),
            "travel": float(self.travel_combo.currentText())
        }

class StageWorker(QObject):
    
    connected = pyqtSignal(bool)
    position_updated = pyqtSignal(list)
    move_complete = pyqtSignal(int, float)
    error_occurred = pyqtSignal(str)

    def __init__(self, control):
        super().__init__()
        self.control = control
        self.control.Show()

        print("stageworker init called")

        self.params = {
            "type": 0,
            "unit": 0,
            "motor_angle": 1.8,
            "subdivision": 2,
            "pitch": 1.0,
            "travel": 100
    }

    @pyqtSlot()
    def connect_stage(self):
        try:
            self.control.ConnectPort(3)
            connected = self.control.ConnectStatus
            print(f"ConnectStatus: {connected}")
            
            for axis in range(3):
                self.control.SetType(axis, self.params["type"])
                self.control.SetUnit(axis, self.params["unit"])
                self.control.SetMotorAngle(axis, self.params["motor_angle"])
                self.control.SetSubsection(axis, self.params["subdivision"])
                self.control.SetPitch(axis, self.params["pitch"])
                self.control.SetTravel(axis, self.params["travel"])
                self.control.SaveParam(axis)
            self.connected.emit(True)
        except Exception as e:
            print(f"Connection error: {e}")
            self.error_occurred.emit(str(e))
            self.connected.emit(False)
            
    @pyqtSlot()
    def get_positions(self):
        try:
            pos = [self.control.GetCurrentPosition(i) for i in range(3)]
            self.position_updated.emit(pos)
            #print the current position
            print(pos)
        except Exception as e:
            self.error_occurred.emit(f"Position error: {e}")

    @pyqtSlot(int, float)
    def move_axis(self, axis, delta):
        try:
            pos = self.control.GetCurrentPosition(axis)
            self.control.RunToPosition(axis, delta)
            self.move_complete.emit(axis, pos)
        except Exception as e:
            self.error_occurred.emit(f"Move error: {e}")

    @pyqtSlot(dict)
    def set_parameters(self, params):
        try:
            
            self.params = params
            for axis in range(3):
                self.control.SetType(axis, params["type"])
                self.control.SetUnit(axis, params["unit"])
                self.control.SetMotorAngle(axis, params["motor_angle"])
                self.control.SetSubsection(axis, params["subdivision"])
                self.control.SetPitch(axis, params["pitch"])
                self.control.SetTravel(axis, params["travel"])
                self.control.SaveParam(axis)
            self.get_positions()
        except Exception as e:
            self.error_occurred.emit(str(e))

   

class MotionStageApp(QWidget):
    connect_requested = pyqtSignal()
    set_param_requested = pyqtSignal(dict)
    move_requested = pyqtSignal(int, float)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Camera + Stage Control")
        self.setGeometry(100, 100, 800, 400)

        self.status_label = QLabel("Connection Status: Not connected")
        self.connect_btn = QPushButton("Connect")
        self.param_btn = QPushButton("Set Parameters")
        self.x_plus_btn = QPushButton("X+")
        self.x_minus_btn = QPushButton("X-")
        self.y_plus_btn = QPushButton("Y+")
        self.y_minus_btn = QPushButton("Y-")
        self.z_plus_btn = QPushButton("Z+")
        self.z_minus_btn = QPushButton("Z-")

        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addWidget(self.connect_btn)
        layout.addWidget(self.param_btn)

        move_layout = QGridLayout()
        move_layout.addWidget(self.x_minus_btn, 0, 0)
        move_layout.addWidget(self.x_plus_btn, 0, 1)
        move_layout.addWidget(self.y_minus_btn, 1, 0)
        move_layout.addWidget(self.y_plus_btn, 1, 1)
        move_layout.addWidget(self.z_minus_btn, 2, 0)
        move_layout.addWidget(self.z_plus_btn, 2, 1)
        layout.addLayout(move_layout)
        self.setLayout(layout)

        self.my_control = SC3U()
        #print all the exposed functions in the dll + inherited ones
        #print(dir(self.my_control))



        self.stage_thread = QThread()
        self.stage_worker = StageWorker(self.my_control)
        self.stage_worker.moveToThread(self.stage_thread)
        self.stage_thread.start()

        self.connect_requested.connect(self.stage_worker.connect_stage)
        self.set_param_requested.connect(self.stage_worker.set_parameters)
        self.move_requested.connect(self.stage_worker.move_axis)

        self.connect_btn.clicked.connect(lambda: self.connect_requested.emit())
        self.param_btn.clicked.connect(self.set_parameters)

        self.x_plus_btn.clicked.connect(lambda: self.move_requested.emit(0, 1.0))
        self.x_minus_btn.clicked.connect(lambda: self.move_requested.emit(0, -1.0))
        self.y_plus_btn.clicked.connect(lambda: self.move_requested.emit(1, 1.0))
        self.y_minus_btn.clicked.connect(lambda: self.move_requested.emit(1, -1.0))
        self.z_plus_btn.clicked.connect(lambda: self.move_requested.emit(2, 1.0))
        self.z_minus_btn.clicked.connect(lambda: self.move_requested.emit(2, -1.0))

        self.stage_worker.connected.connect(self.on_connected)
        self.stage_worker.position_updated.connect(self.update_position)
        self.stage_worker.move_complete.connect(self.on_move_complete)
        self.stage_worker.error_occurred.connect(self.on_error)

    def set_parameters(self):
        print("trying to display params")
        self.stage_worker.control.DisplayParameterInterface()
        print("tried to display params")
        
        '''
        dlg = StageParamDialog(self)
        if dlg.exec_():
            params = dlg.get_params()
            self.set_param_requested.emit(params)
            #1 if the text was saved 
            print(f"Dialog result: {dlg.exec_()}")
            print(params)'''

    def on_connected(self, status):
        self.status_label.setText("Connected" if status else "Connection Failed")
        if status:
            QMetaObject.invokeMethod(self.stage_worker, "get_positions")

    def update_position(self, pos):
        pos_str = ", ".join([f"Axis {i}: {p:.2f}" for i, p in enumerate(pos)])
        self.status_label.setText(f"Positions: {pos_str}")

    def on_move_complete(self, axis, pos):
        self.status_label.setText(f"Axis {axis} moved. New position: {pos:.2f}")

    def on_error(self, msg):
        QMessageBox.critical(self, "Error", msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MotionStageApp()
    win.show()
    sys.exit(app.exec_())
