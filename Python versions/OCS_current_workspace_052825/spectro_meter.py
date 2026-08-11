from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QApplication, QFileDialog
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QPainter, QPen, QColor
import threading
import time
import numpy as np
import os
from ctypes import byref, c_double, c_int, c_void_p, cdll
from datetime import datetime




class SpectrometerBus(QObject):
    spectrum = pyqtSignal(object, object)
    status = pyqtSignal(str)
    error = pyqtSignal(str)






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