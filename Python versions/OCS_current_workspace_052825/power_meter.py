from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QApplication
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QPainter, QPen, QColor
import threading
import time
from collections import deque




class PowerMeterBus(QObject):
    sample = pyqtSignal(float, float)
    status = pyqtSignal(str)
    error = pyqtSignal(str)





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