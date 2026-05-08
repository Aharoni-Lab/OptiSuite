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
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QComboBox, QHBoxLayout, QGridLayout, QLineEdit, QSpinBox
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QGroupBox
from PyQt5.QtWidgets import QDoubleSpinBox, QPlainTextEdit
from PyQt5.QtCore import QEvent, QObject, QTimer, Qt, pyqtSignal, QRectF
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QIcon
import gxipy as gx
import json #for sending run commands
import autofocus as af
from camera_manager_class_import_120425 import CameraManager #camera manager class
from stage_routine_import_013026 import StageRoutine #stage routine class
from zmq_push_worker import ZMQWorker
from zmq_pull_listener import ZMQPullListener
from autofocus_routine import AutofocusRoutine

#main pytHON gui FOR CAM, STAGE CONNECTION

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
    painter.drawArc(rect, 225 * 16, 270 * 16)

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
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DaHeng Multi-Camera + ZeroMQ GUI")
        # We set a fixed size later after building the layout.

        # ZMQ Setup
        self.zmq_thread = None
        self.zmq_events = None
        self.stage_host = "localhost"
        self.stage_cmd_port = 5555
        self.stage_event_port = 5556
        self.stage_event_queue = queue.Queue(maxsize=2000)
        self._stage_seq_lock = threading.Lock()
        self._stage_last_seq = 0

        # C# stage status/event UI + thread-safe signal bridge
        self.stage_event_bus = StageEventBus()
        self.stage_event_bus.message.connect(self.on_stage_event)
        self.preview_status = QLabel("")
        self.preview_status.setStyleSheet("color: #b45309; font-weight: 600;")
        self.preview_status.setWordWrap(True)
        self.preview_status.hide()
        self.stage_status = QLabel("C# stage: (no events)")
        self.stage_status.setWordWrap(True)
        self.stage_log = QPlainTextEdit()
        self.stage_log.setReadOnly(True)
        self.stage_log.setMaximumBlockCount(500)
        self.stage_log.setFixedWidth(420)

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

        #use the class instead
        self.cam_mgr = CameraManager(save_dir=r"C:\Users\stimscope1\Documents\OptiSuite\screenshots")
        self.zoom_labels = [None] * self.cam_mgr.num_cameras
        # Per-camera view state for software zoom/pan
        # zoom: >= 1.0, cx/cy are normalized [0..1] center coordinates in the source frame
        self.view_states = [{"zoom": 1.0, "cx": 0.5, "cy": 0.5} for _ in range(self.cam_mgr.num_cameras)]
        # Track last mouse position in label coords (for button zoom anchoring)
        self.last_mouse_pos = [None] * self.cam_mgr.num_cameras
        # Track last seen frame sizes (w, h) per camera
        self.last_frame_sizes = [None] * self.cam_mgr.num_cameras
       
        # - -   -   -   -   -
        # for the dual camera layout
        #   -   --  -   -   -

        self.layout = QVBoxLayout()
        self.grid = QGridLayout()
        self.cam_labels = []
        self.cam_title_labels = []
        self.control_panels = []
        self.exposure_inputs = []
        self.gain_inputs = []

        # Layout is intentionally 1 camera per row (less cramped).
        cols = 1
        n_cams = max(1, len(self.cam_mgr.cameras))
        rows = (n_cams + cols - 1) // cols

        # Fit to screen so the bottom panel doesn't get pushed off-screen.
        screen = QApplication.primaryScreen().availableGeometry()
        max_win_w = int(screen.width() * 0.95)
        max_win_h = int(screen.height() * 0.95)

        stage_log_w = min(400, max(320, int(max_win_w * 0.32)))
        self.stage_log.setFixedWidth(stage_log_w)

        # Reserve enough vertical space for stacked bottom control rows
        bottom_panel_h = 360
        caption_h = 22
        control_h = 260
        preview_h = int((max_win_h - bottom_panel_h) / rows) - caption_h - control_h
        preview_h = max(220, min(360, preview_h))

        preview_w = min(520, max_win_w - stage_log_w - 80)
        preview_w = max(360, preview_w)

        #1 for each camera
        for i in range(len(self.cam_mgr.cameras)):
            # ------- CAMERA TITLE + PREVIEW LABEL -------
            model = ""
            if hasattr(self.cam_mgr, "camera_names") and i < len(self.cam_mgr.camera_names):
                model = str(self.cam_mgr.camera_names[i])

            cam_title = "Cam 1: Microscope" if i == 0 else f"Cam {i + 1}"
            title = QLabel(cam_title + (f" ({model})" if model else ""))
            title.setStyleSheet("font-weight: 600;")

            label = QLabel("")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("border:1px solid gray; background:black; color:white;")
            # Prevent feedback-loop resizing (pixmap sizeHint -> layout -> window growth).
            label.setFixedSize(preview_w, preview_h)
            label.setMouseTracking(True)
            label.setProperty("cam_index", i)
            label.installEventFilter(self)

            cam_box = QVBoxLayout()
            cam_box.addWidget(title)
            cam_box.addWidget(label)
            self.grid.addLayout(cam_box, i // cols * 2, i % cols)

            self.cam_labels.append(label)
            self.cam_title_labels.append(title)

            # ------- CONTROL PANEL -------
            # do 2 rows for the control panel
            panel = QHBoxLayout()
            panel2 = QHBoxLayout()

            # Zoom controls (software zoom in display)
            zoom_out_btn = QPushButton("Zoom -")
            zoom_in_btn = QPushButton("Zoom +")
            zoom_reset_btn = QPushButton("Reset Zoom")
            zoom_lbl = QLabel("1.0x")
            self.zoom_labels[i] = zoom_lbl

            zoom_out_btn.clicked.connect(lambda _, c=i: self.adjust_zoom(c, 1 / 1.25))
            zoom_in_btn.clicked.connect(lambda _, c=i: self.adjust_zoom(c, 1.25))
            zoom_reset_btn.clicked.connect(lambda _, c=i: self.reset_zoom(c))

            panel.addWidget(zoom_out_btn)
            panel.addWidget(zoom_in_btn)
            panel.addWidget(zoom_reset_btn)
            panel.addWidget(zoom_lbl)

            # Exposure input (µs)
            exp_input = QDoubleSpinBox()
            exp_input.setDecimals(2)
            exp_input.setKeyboardTracking(False)

            exp_rng = self.cam_mgr.get_exposure_range(i)
            if exp_rng:
                exp_input.setRange(float(exp_rng["min"]), float(exp_rng["max"]))
                # Daheng typically uses µs; let user type any value, step is convenience only
                exp_input.setSingleStep(1000.0)
            else:
                exp_input.setRange(0.0, 1e9)
                exp_input.setSingleStep(1000.0)

            exp_input.setValue(float(self.cam_mgr.get_exposure(i)))
            exp_apply = QPushButton("Set Exp")
            exp_apply.clicked.connect(lambda _, c=i, w=exp_input: self.apply_exposure(c, w))

            panel.addWidget(QLabel("Exp (us):"))
            panel.addWidget(exp_input)
            panel.addWidget(exp_apply)
            self.exposure_inputs.append(exp_input)

            # Gain input
            gain_input = QDoubleSpinBox()
            gain_input.setDecimals(2)
            gain_input.setKeyboardTracking(False)

            gain_rng = self.cam_mgr.get_gain_range(i)
            if gain_rng:
                gain_input.setRange(float(gain_rng["min"]), float(gain_rng["max"]))
                gain_input.setSingleStep(0.5)
            else:
                gain_input.setRange(0.0, 100.0)
                gain_input.setSingleStep(0.5)

            gain_input.setValue(float(self.cam_mgr.get_gain(i)))
            gain_apply = QPushButton("Set Gain")
            gain_apply.clicked.connect(lambda _, c=i, w=gain_input: self.apply_gain(c, w))

            panel.addWidget(QLabel("Gain:"))
            panel.addWidget(gain_input)
            panel.addWidget(gain_apply)
            self.gain_inputs.append(gain_input)


            # Screenshot
            ss_btn = QPushButton("Screenshot")
            ss_btn.clicked.connect(lambda _, c=i: self._on_screenshot(c))
            panel2.addWidget(ss_btn)

            # Video Record
            rec_btn = QPushButton("▶")
            def toggle_rec(cam_index=i, btn=rec_btn):
                if not self.cam_mgr.recording[cam_index]:
                    self.cam_mgr.start_recording(cam_index)
                    btn.setText("⏹")
                else:
                    self.cam_mgr.stop_recording(cam_index)
                    btn.setText("▶")
            rec_btn.clicked.connect(toggle_rec)
            panel2.addWidget(rec_btn)

            control_stack = QVBoxLayout()
            control_stack.addLayout(panel)
            control_stack.addLayout(panel2)

            if i == 1:
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

                spectrometer_btn = QPushButton("Spectrumeter")
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

                button_stack = QVBoxLayout()
                button_stack.addWidget(spectrometer_btn)
                button_stack.addSpacing(12)
                button_stack.addWidget(power_btn)

                characterization_panel.addStretch(1)
                characterization_panel.addLayout(button_stack)
                control_stack.addWidget(characterization_box)
                self.spectrometer_btn = spectrometer_btn
                self.power_meter_btn = power_btn

            self.grid.addLayout(control_stack, i // cols * 2 + 1, i % cols)
            self.control_panels.append(panel)

        # Top area: camera grid + C# stage status/log
        top_layout = QHBoxLayout()
        top_layout.setAlignment(Qt.AlignTop)
        self.grid.setAlignment(Qt.AlignTop)
        top_layout.addLayout(self.grid)
        stage_panel = QVBoxLayout()
        stage_panel.addWidget(self.preview_status)
        stage_panel.addWidget(self.stage_status)
        stage_panel.addWidget(self.stage_log)
        top_layout.addLayout(stage_panel)

        self.layout.addLayout(top_layout)
        self.setLayout(self.layout)

        # Fix window size so it doesn't grow while streaming.
        # Adjust here if you change preview/log widths.
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
        #zmq_panel for connect, disconnect, status, axis, target, send command button
        zmq_panel = QHBoxLayout()
        
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

        self.axis_spin = QSpinBox()
        self.axis_spin.setRange(0, 5)
        self.axis_spin.setValue(0)

        self.target_spin = QDoubleSpinBox()
        self.target_spin.setDecimals(4)
        self.target_spin.setRange(-50000.0, 50000.0)
        self.target_spin.setSingleStep(0.1)
        self.target_spin.setKeyboardTracking(False)
        self.target_spin.setValue(0.0)

        send_btn = QPushButton("Send Command")
        send_btn.clicked.connect(self.send_zmq_command)

        # ---- Focus scoring tool (noise check) ----
        score_cam_select = QComboBox()
        score_cam_select.addItems([f"Cam {i+1}" for i in range(self.cam_mgr.num_cameras)])
        score_cam_select.setCurrentIndex(0)
        self.score_cam_select = score_cam_select

        score_n = QSpinBox()
        score_n.setRange(1, 50)
        score_n.setValue(5)
        self.score_n = score_n

        score_btn = QPushButton("Score frame(s)")
        score_btn.clicked.connect(self.score_current_frame)
        self.score_btn = score_btn

        #013026 add these buttons for the stageRoutine
        # ---- Stage Routine Controls ----
        startRoutine_btn = QPushButton("Start Stage Routine")
        resumeRoutine_btn = QPushButton("Resume Step")
        autofocus_btn = QPushButton("Autofocus Cam 1")
        cancel_af_btn = QPushButton("Cancel AF")
        cancel_af_btn.setEnabled(False)

        startRoutine_btn.clicked.connect(self.start_stage_routine)
        resumeRoutine_btn.clicked.connect(self.resume_stage_routine)
        autofocus_btn.clicked.connect(lambda: self.start_autofocus(cam_index=0))
        cancel_af_btn.clicked.connect(self.cancel_autofocus)

        stage_routine_panel.addWidget(startRoutine_btn)
        stage_routine_panel.addWidget(resumeRoutine_btn)
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
        self.startRoutine_btn = startRoutine_btn



        # ---- Connect/Disconnect ----
        self.connect_btn = QPushButton("Connect")
        self.disconnect_btn = QPushButton("Disconnect")
        self.status_label = QLabel("Disconnected ❌")

        self.connect_btn.clicked.connect(self.connect_zmq)
        self.disconnect_btn.clicked.connect(self.disconnect_zmq)

        # ---- Layout ----
        zmq_panel.addWidget(self.connect_btn)
        zmq_panel.addWidget(self.disconnect_btn)
        zmq_panel.addWidget(self.status_label)

        zmq_panel.addWidget(QLabel("Command:"))
        zmq_panel.addWidget(self.cmd_select)
        zmq_panel.addWidget(QLabel("Axis:"))    
        zmq_panel.addWidget(self.axis_spin)
        zmq_panel.addWidget(QLabel("Target:"))
        zmq_panel.addWidget(self.target_spin)
        zmq_panel.addWidget(send_btn)

        self.layout.addLayout(stage_routine_panel)
        self.layout.addLayout(autofocus_panel)
        self.layout.addLayout(zmq_panel)

        # Timer to update frames
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frames)
        self.timer.start(30)

        #013026 add this for stageRoutine
        self.stage_routine = StageRoutine(
            send_move_callback=self.send_stage_move,
            log_callback=print  # for now, just print to console
        )

    def eventFilter(self, obj, event):
        # Mouse-wheel zoom + cursor tracking on each preview label
        cam_index = obj.property("cam_index") if hasattr(obj, "property") else None
        if cam_index is None:
            return super().eventFilter(obj, event)

        cam_index = int(cam_index)

        if event.type() == QEvent.MouseMove:
            self.last_mouse_pos[cam_index] = event.pos()
            return False

        if event.type() == QEvent.Wheel:
            dy = event.angleDelta().y()
            if dy == 0:
                return True

            steps = dy / 120.0
            factor = float(1.25 ** steps)
            self.zoom_at_label_pos(cam_index, factor, event.pos())
            return True

        return super().eventFilter(obj, event)

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
        desired = float(widget.value())
        ok, applied = self.cam_mgr.set_exposure(cam_index, desired)
        # reflect clamping / rejection in UI without crashing
        widget.blockSignals(True)
        widget.setValue(float(applied))
        widget.blockSignals(False)
        if not ok:
            print(f"[UI] Exposure rejected cam{cam_index}, kept {applied}")

    def apply_gain(self, cam_index, widget: QDoubleSpinBox):
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
            self.stage_status.setText(f"C# stage: {line}")
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
        self.stage_status.setText(f"C# stage: {line}")
        self.stage_log.appendPlainText(line)

        # Add a blank line after completion/errors to improve readability
        if evt in {"CommandCompleted", "CommandError", "ParseError", "PositionError"}:
            self.stage_log.appendPlainText("")
        elif evt in {"Position", "StopRun", "ServerStarted", "ServerStopped"}:
            self.stage_log.appendPlainText("")

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
            h0, w0 = frame.shape[:2]
            self.last_frame_sizes[i] = (w0, h0)
            frame = self.apply_zoom(frame, i)

            # Convert BGR → RGB for Qt
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape

            qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
            pix = QPixmap.fromImage(qimg)

            target_size = self.cam_labels[i].size()
            self.cam_labels[i].setPixmap(
                pix.scaled(target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

        # Write recording frames per camera
        for cam_index in range(self.cam_mgr.num_cameras):
            self.cam_mgr.write_record_frame(cam_index)




    # ---- ZMQ Controls ---- #
    def connect_zmq(self):
        if self.zmq_thread and self.zmq_thread.running:
            print("[ZMQ] Already connected.")
            return
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
        self.status_label.setText("Connected")

    def disconnect_zmq(self):
        if self.zmq_thread:
            self.zmq_thread.stop()
            self.zmq_thread = None
        if self.zmq_events:
            self.zmq_events.stop()
            self.zmq_events = None
        self.status_label.setText("Disconnected")

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
        self.stage_status.setText(f"C# stage: {txt}")

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
                best_z, _pts = routine.run()
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
        self.autofocus_btn.setEnabled(True)
        self.cancel_af_btn.setEnabled(False)
        if hasattr(self, "resumeRoutine_btn"):
            self.resumeRoutine_btn.setEnabled(True)
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

    #013026 add this for importing stage routine
    def start_stage_routine(self):
        # For now, use your hardcoded test values
        self.stage_routine.SetAlignPt(66.8, 4, 60.875)
        self.stage_routine.StartRoutine()

    def resume_stage_routine(self):
        self.stage_routine.Resume()

    def send_stage_move(self, x, y, z):
        if not (self.zmq_thread and self.zmq_thread.running):
            print("[ZMQ] Not connected (cannot send stage move).")
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
        event.accept()

    def _on_screenshot(self, cam_index: int):
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
