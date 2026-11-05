from PyQt5.QtCore import QObject, pyqtSignal


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
    stage_routine_finished = pyqtSignal()


class UiBus(QObject):
    log = pyqtSignal(str)
    autofocus_finished = pyqtSignal()
    auto_solid_apply = pyqtSignal(int)
    auto_solid_finished = pyqtSignal()
    power_meter_finished = pyqtSignal(float)
    spectro_meter_finished = pyqtSignal(object)