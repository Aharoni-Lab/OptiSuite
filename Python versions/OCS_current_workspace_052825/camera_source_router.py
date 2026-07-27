import os
import threading
import time
from datetime import datetime

import cv2
import numpy as np


DMK_DEFAULT_EXPOSURE_US = 66666.0


class OpenCVDShowCamera:
    def __init__(self, camera_index=None, save_dir="captures", display_name="DMK 27BUP031"):
        self.camera_index = camera_index
        self.save_dir = save_dir
        self.display_name = display_name
        self.cap = None
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.capture_thread = None
        self.latest_frame = None
        self.latest_seq = 0
        self.latest_lock = threading.Lock()
        self.exposure_us = DMK_DEFAULT_EXPOSURE_US
        self.gain_value = 0.0
        self.pending_exposure_us = None
        self.pending_gain = None
        self.pending_lock = threading.Lock()
        self.recording = [False]
        self.video_writers = [None]
        self.camera_names = [display_name]
        self.num_cameras = 1
        self.cameras = [display_name]
        os.makedirs(self.save_dir, exist_ok=True)
        self._open()
        self._apply_exposure_to_capture(self.exposure_us)
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()

    def _safe_name(self, s: str) -> str:
        return "".join(ch if (ch.isalnum() or ch in ("-", "_")) else "_" for ch in str(s)).strip("_")

    def _try_open_index(self, index):
        cap = cv2.VideoCapture(int(index), cv2.CAP_DSHOW)
        if not cap or not cap.isOpened():
            try:
                cap.release()
            except Exception:
                pass
            return None
        ok, frame = cap.read()
        if not ok or frame is None:
            cap.release()
            return None
        return cap

    def _open(self):
        if self.camera_index is not None:
            cap = self._try_open_index(self.camera_index)
            if cap is None:
                raise RuntimeError(f"Could not open {self.display_name} at DirectShow index {self.camera_index}")
            self.cap = cap
            return

        for index in range(10):
            cap = self._try_open_index(index)
            if cap is not None:
                self.camera_index = index
                self.cap = cap
                print(f"[OpenCVCamera] Opened {self.display_name} at DirectShow index {index}")
                return

        raise RuntimeError(f"Could not find an available DirectShow camera for {self.display_name}")

    def _capture_loop(self):
        while not self.stop_event.is_set():
            frame = None
            try:
                with self.lock:
                    if self.cap is not None:
                        self._apply_pending_properties_locked()
                        ok, frame = self.cap.read()
                        if not ok:
                            frame = None
            except Exception as e:
                print(f"[OpenCVCamera] capture error: {e}")
                frame = None

            if frame is not None:
                with self.latest_lock:
                    self.latest_frame = frame
                    self.latest_seq += 1
            self.stop_event.wait(0.001)

    def get_frame(self, cam_index=0):
        if cam_index != 0 or self.cap is None:
            return None
        try:
            with self.latest_lock:
                return None if self.latest_frame is None else self.latest_frame.copy()
        except Exception as e:
            print(f"[OpenCVCamera] get_frame error: {e}")
            return None

    def get_exposure_range(self, cam_index=0):
        return None

    def get_gain_range(self, cam_index=0):
        return {"min": 0.0, "max": 100.0}

    def is_gain_supported(self, cam_index=0):
        return True

    def get_exposure(self, cam_index=0):
        return float(self.exposure_us)

    def set_exposure(self, cam_index, value):
        self.exposure_us = float(value)
        with self.pending_lock:
            self.pending_exposure_us = float(value)
        return True, float(value)

    def _exposure_us_to_directshow(self, exposure_us):
        # The DMK DirectShow driver reports about half the expected FPS when
        # using the nominal log2(seconds) exposure value. Halve the requested
        # exposure period here so the UI value matches observed frame rate.
        seconds = max(float(exposure_us) / 2_000_000.0, 1e-6)
        return int(round(float(np.log2(seconds))))

    def _apply_pending_properties_locked(self):
        with self.pending_lock:
            exposure_us = self.pending_exposure_us
            gain = self.pending_gain
            self.pending_exposure_us = None
            self.pending_gain = None

        if exposure_us is not None:
            self._apply_exposure_to_capture(exposure_us)
        if gain is not None:
            self._apply_gain_to_capture(gain)

    def _apply_exposure_to_capture(self, value):
        try:
            v = self._exposure_us_to_directshow(value)
            fps = max(0.1, min(120.0, 1_000_000.0 / max(float(value), 1.0)))
            if self.cap is not None:
                self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
                fps_ok = self.cap.set(cv2.CAP_PROP_FPS, fps)
                exposure_ok = self.cap.set(cv2.CAP_PROP_EXPOSURE, v)
                for _ in range(3):
                    self.cap.grab()
                print(
                    f"[OpenCVCamera] DMK exposure set: {float(value):.2f} us "
                    f"-> DirectShow {v}, target_fps={fps:.2f} "
                    f"(fps_ok={fps_ok}, exposure_ok={exposure_ok})"
                )
        except Exception as e:
            print(f"[OpenCVCamera] set_exposure error: {e}")

    def get_gain(self, cam_index=0):
        return float(self.gain_value)

    def get_frame_counter(self, cam_index=0):
        if cam_index != 0:
            return None
        with self.latest_lock:
            return int(self.latest_seq)

    def set_gain(self, cam_index, value):
        self.gain_value = float(value)
        with self.pending_lock:
            self.pending_gain = float(value)
        return True, float(value)

    def _apply_gain_to_capture(self, value):
        try:
            v = int(round(float(value)))
            if self.cap is not None:
                ok = self.cap.set(cv2.CAP_PROP_GAIN, v)
                for _ in range(3):
                    self.cap.grab()
                print(f"[OpenCVCamera] DMK gain set: {v} (ok={ok})")
        except Exception as e:
            print(f"[OpenCVCamera] set_gain error: {e}")

    def take_screenshot(self, cam_index, save_dir=None, prefix="screenshot", warmup_frames=0, simple_name=False):
        for _ in range(max(0, int(warmup_frames))):
            _ = self.get_frame(0)
        frame = self.get_frame(0)
        if frame is None:
            return None

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = save_dir if save_dir is not None else self.save_dir
        os.makedirs(out_dir, exist_ok=True)
        prefix_safe = self._safe_name(prefix) if prefix else "screenshot"
        model = self._safe_name(self.display_name)
        fname = os.path.join(out_dir, f"{prefix_safe}_{ts}.png" if simple_name else f"{prefix_safe}_cam2_{model}_{ts}.png")
        with self.lock:
            cv2.imwrite(fname, frame)
        return fname

    def start_recording(self, cam_index=0):
        if self.recording[0]:
            return
        frame = self.get_frame(0)
        if frame is None:
            return
        h, w = frame.shape[:2]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        model = self._safe_name(self.display_name)
        fname = os.path.join(self.save_dir, f"video_cam2_{model}_{ts}.avi")
        self.video_writers[0] = cv2.VideoWriter(fname, cv2.VideoWriter_fourcc(*"XVID"), 20.0, (w, h))
        self.recording[0] = True

    def stop_recording(self, cam_index=0):
        writer = self.video_writers[0]
        if writer:
            writer.release()
        self.video_writers[0] = None
        self.recording[0] = False

    def write_record_frame(self, cam_index=0):
        if not self.recording[0]:
            return
        frame = self.get_frame(0)
        writer = self.video_writers[0]
        if frame is not None and writer is not None:
            writer.write(frame)

    def close(self):
        self.stop_event.set()
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=1.0)
        self.stop_recording(0)
        if self.cap is not None:
            self.cap.release()
            self.cap = None


class CharacterizationCameraRouter:
    def __init__(self, base_manager, save_dir="captures"):
        self.base = base_manager
        self.save_dir = save_dir
        self.override_index = 1
        self.override = None
        self.override_source = "daheng"
        self._sync_metadata()

    def _sync_metadata(self):
        base_names = list(getattr(self.base, "camera_names", []))
        base_cameras = list(getattr(self.base, "cameras", []))
        min_len = max(getattr(self.base, "num_cameras", 0), self.override_index + 1 if self.override else 0)

        while len(base_names) < min_len:
            base_names.append("Camera not detected")
        while len(base_cameras) < min_len:
            base_cameras.append(None)

        if self.override:
            base_names[self.override_index] = self.override.camera_names[0]
            base_cameras[self.override_index] = self.override

        self.camera_names = base_names
        self.cameras = base_cameras
        self.num_cameras = min_len

    @property
    def recording(self):
        values = []
        for i in range(self.num_cameras):
            if self._is_override(i):
                values.append(bool(self.override.recording[0]))
            elif i < getattr(self.base, "num_cameras", 0):
                values.append(bool(self.base.recording[i]))
            else:
                values.append(False)
        return values

    def _is_override(self, cam_index):
        return self.override is not None and int(cam_index) == self.override_index

    def _base_available(self, cam_index):
        return int(cam_index) < getattr(self.base, "num_cameras", 0)

    def set_characterization_source(self, source_id):
        if self.override:
            self.override.close()
            self.override = None

        self.override_source = source_id
        if source_id.startswith("dmk"):
            camera_index = None
            if ":" in source_id:
                camera_index = int(source_id.split(":", 1)[1])
            self.override = OpenCVDShowCamera(
                camera_index=camera_index,
                save_dir=self.save_dir,
                display_name="DMK 27BUP031",
            )

        self._sync_metadata()

    def get_frame(self, cam_index):
        if self._is_override(cam_index):
            return self.override.get_frame(0)
        if self._base_available(cam_index):
            return self.base.get_frame(cam_index)
        return None

    def get_frame_counter(self, cam_index):
        if self._is_override(cam_index) and hasattr(self.override, "get_frame_counter"):
            return self.override.get_frame_counter(0)
        return None

    def get_exposure_range(self, cam_index):
        if self._is_override(cam_index):
            return self.override.get_exposure_range(0)
        return self.base.get_exposure_range(cam_index) if self._base_available(cam_index) else None

    def get_gain_range(self, cam_index):
        if self._is_override(cam_index):
            return self.override.get_gain_range(0)
        return self.base.get_gain_range(cam_index) if self._base_available(cam_index) else None

    def is_gain_supported(self, cam_index):
        if self._is_override(cam_index) and hasattr(self.override, "is_gain_supported"):
            return self.override.is_gain_supported(0)
        return self._base_available(cam_index)

    def get_exposure(self, cam_index):
        if self._is_override(cam_index):
            return self.override.get_exposure(0)
        return self.base.get_exposure(cam_index) if self._base_available(cam_index) else 0.0

    def set_exposure(self, cam_index, value):
        if self._is_override(cam_index):
            return self.override.set_exposure(0, value)
        return self.base.set_exposure(cam_index, value) if self._base_available(cam_index) else (False, 0.0)

    def get_gain(self, cam_index):
        if self._is_override(cam_index):
            return self.override.get_gain(0)
        return self.base.get_gain(cam_index) if self._base_available(cam_index) else 0.0

    def set_gain(self, cam_index, value):
        if self._is_override(cam_index):
            return self.override.set_gain(0, value)
        return self.base.set_gain(cam_index, value) if self._base_available(cam_index) else (False, 0.0)

    def take_screenshot(self, cam_index, **kwargs):
        if self._is_override(cam_index):
            return self.override.take_screenshot(0, **kwargs)
        return self.base.take_screenshot(cam_index, **kwargs) if self._base_available(cam_index) else None

    def start_recording(self, cam_index):
        if self._is_override(cam_index):
            return self.override.start_recording(0)
        if self._base_available(cam_index):
            return self.base.start_recording(cam_index)
        return None

    def stop_recording(self, cam_index):
        if self._is_override(cam_index):
            return self.override.stop_recording(0)
        if self._base_available(cam_index):
            return self.base.stop_recording(cam_index)
        return None

    def write_record_frame(self, cam_index):
        if self._is_override(cam_index):
            return self.override.write_record_frame(0)
        if self._base_available(cam_index):
            return self.base.write_record_frame(cam_index)
        return None

    def close(self):
        if self.override:
            self.override.close()
            self.override = None
        self.base.close()
