import os
import socket
import threading
from datetime import datetime

import cv2
import numpy as np


class PycroManagerCameraManager:
    """
    CameraManager-compatible wrapper for the active Micro-Manager camera.

    Pycro-Manager/Micro-Manager exposes the selected camera through Core, so the
    first implementation presents it as a single OptiSuite camera slot.
    """

    def __init__(self, save_dir="captures", mm_host="127.0.0.1", mm_port=4827):
        self.mm_host = mm_host
        self.mm_port = int(mm_port)
        if not self._is_port_open(self.mm_host, self.mm_port):
            raise RuntimeError(
                f"Micro-Manager ZMQ server is not reachable at {self.mm_host}:{self.mm_port}. "
                "Open Micro-Manager, load your hardware configuration, and enable the ZMQ server."
            )

        try:
            from pycromanager import Core
        except Exception as e:
            raise RuntimeError("pycromanager is not installed. Install it with: pip install pycromanager") from e

        self.core = Core(port=self.mm_port)
        self.save_dir = save_dir
        os.makedirs(self.save_dir, exist_ok=True)

        camera_name = self._call_optional("get_camera_device") or "Micro-Manager Camera"
        self.cameras = [camera_name]
        self.camera_names = [str(camera_name)]
        self.num_cameras = 1
        self._cam_locks = [threading.Lock()]
        self.recording = [False]
        self.video_writers = [None]

        print(f"[PycroCamera] Connected camera: {camera_name}")

    def _is_port_open(self, host, port, timeout_s=0.75):
        try:
            with socket.create_connection((host, int(port)), timeout=float(timeout_s)):
                return True
        except OSError:
            return False

    def _safe_name(self, s: str) -> str:
        return "".join(ch if (ch.isalnum() or ch in ("-", "_")) else "_" for ch in str(s)).strip("_")

    def _call_optional(self, name, *args):
        fn = getattr(self.core, name, None)
        if fn is None:
            return None
        try:
            return fn(*args)
        except Exception:
            return None

    def _tag_value(self, tags, *names):
        for name in names:
            try:
                if isinstance(tags, dict) and name in tags:
                    return tags[name]
                if hasattr(tags, name):
                    return getattr(tags, name)
            except Exception:
                pass
        return None

    def _tagged_image_to_array(self, tagged):
        pix = getattr(tagged, "pix", None)
        tags = getattr(tagged, "tags", None)
        if pix is None and isinstance(tagged, dict):
            pix = tagged.get("pix")
            tags = tagged.get("tags")
        if pix is None:
            return None

        arr = np.asarray(pix)
        if arr.ndim >= 2:
            return arr

        width = self._tag_value(tags, "Width", "width")
        height = self._tag_value(tags, "Height", "height")
        if width is None:
            width = self._call_optional("get_image_width")
        if height is None:
            height = self._call_optional("get_image_height")
        if width is None or height is None:
            return arr

        width = int(width)
        height = int(height)
        channels = max(1, int(arr.size // max(1, width * height)))
        try:
            if channels == 1:
                return arr.reshape((height, width))
            return arr.reshape((height, width, channels))
        except Exception:
            return arr

    def get_frame(self, cam_index):
        if cam_index != 0:
            return None

        try:
            with self._cam_locks[0]:
                snap = getattr(self.core, "snap_image", None)
                if callable(snap):
                    snap()

                img = None
                get_image = getattr(self.core, "get_image", None)
                if callable(get_image):
                    try:
                        img = np.asarray(get_image())
                    except Exception:
                        img = None

                if img is None or img.ndim < 2:
                    tagged = self._call_optional("get_tagged_image")
                    img = self._tagged_image_to_array(tagged) if tagged is not None else img

                if img is None:
                    return None

                img = np.asarray(img)
                if img.ndim == 2:
                    return cv2.cvtColor(img.astype(np.uint8, copy=False), cv2.COLOR_GRAY2BGR)
                if img.ndim == 3 and img.shape[2] >= 3:
                    return cv2.cvtColor(img[:, :, :3].astype(np.uint8, copy=False), cv2.COLOR_RGB2BGR)
                return img.astype(np.uint8, copy=False)
        except Exception as e:
            print(f"[PycroCamera] get_frame error: {e}")
            return None

    def get_exposure_range(self, cam_index):
        return None

    def get_gain_range(self, cam_index):
        return None

    def get_exposure(self, cam_index):
        value = self._call_optional("get_exposure")
        return float(value or 0.0)

    def set_exposure(self, cam_index, value):
        try:
            self.core.set_exposure(float(value))
            return True, self.get_exposure(cam_index)
        except Exception as e:
            print(f"[PycroCamera] set_exposure error: {e}")
            return False, self.get_exposure(cam_index)

    def get_gain(self, cam_index):
        try:
            camera = self.camera_names[0]
            value = self.core.get_property(camera, "Gain")
            return float(value)
        except Exception:
            return 0.0

    def set_gain(self, cam_index, value):
        try:
            camera = self.camera_names[0]
            self.core.set_property(camera, "Gain", str(float(value)))
            return True, self.get_gain(cam_index)
        except Exception as e:
            print(f"[PycroCamera] set_gain error: {e}")
            return False, self.get_gain(cam_index)

    def take_screenshot(
        self,
        cam_index,
        save_dir=None,
        prefix="screenshot",
        warmup_frames: int = 0,
        simple_name: bool = False,
    ):
        for _ in range(max(0, int(warmup_frames))):
            _ = self.get_frame(cam_index)
        frame = self.get_frame(cam_index)
        if frame is None:
            print("[PycroCamera] Screenshot failed")
            return None

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = save_dir if save_dir is not None else self.save_dir
        os.makedirs(out_dir, exist_ok=True)
        prefix_safe = self._safe_name(prefix) if prefix else "screenshot"
        model = self._safe_name(self.camera_names[0])
        if simple_name:
            fname = os.path.join(out_dir, f"{prefix_safe}_{ts}.png")
        else:
            fname = os.path.join(out_dir, f"{prefix_safe}_cam1_{model}_{ts}.png")
        cv2.imwrite(fname, frame)
        print(f"[PycroCamera] Saved {fname}")
        return fname

    def start_recording(self, cam_index):
        if self.recording[0]:
            return
        frame = self.get_frame(0)
        if frame is None:
            print("[PycroCamera] Cannot start recording: no frame")
            return
        h, w = frame.shape[:2]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        model = self._safe_name(self.camera_names[0])
        fname = os.path.join(self.save_dir, f"video_cam1_{model}_{ts}.avi")
        self.video_writers[0] = cv2.VideoWriter(fname, cv2.VideoWriter_fourcc(*"XVID"), 20.0, (w, h))
        self.recording[0] = True
        print(f"[PycroCamera] Recording -> {fname}")

    def stop_recording(self, cam_index):
        writer = self.video_writers[0]
        if writer:
            writer.release()
        self.video_writers[0] = None
        self.recording[0] = False

    def write_record_frame(self, cam_index):
        if not self.recording[0]:
            return
        frame = self.get_frame(0)
        writer = self.video_writers[0]
        if frame is not None and writer is not None:
            writer.write(frame)

    def close(self):
        self.stop_recording(0)
        print("[PycroCamera] Closed.")
