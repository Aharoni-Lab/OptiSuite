import os
import cv2
import numpy as np
from datetime import datetime
import threading

try:
    import gxipy as gx
except Exception as e:
    gx = None
    print(f"[CameraManager] gxipy unavailable: {e}")


class CameraManager:
    def __init__(self, save_dir="captures", num_fake_cams=1, use_fake_camera=None):
        self.save_dir = save_dir
        self.cameras = []
        self.camera_names = []
        self.is_fake = False
        self._fake_exposure = []
        self._fake_gain = []
        self._dummy_frame_idx = []

        if use_fake_camera is None:
            use_fake_camera = gx is None

        if not use_fake_camera and gx is not None:
            try:
                self.device_manager = gx.DeviceManager()
                num_devices, dev_info_list = self.device_manager.update_device_list()

                for idx in range(1, num_devices + 1):
                    try:
                        cam = self.device_manager.open_device_by_index(idx)
                        cam.TriggerMode.set(gx.GxSwitchEntry.OFF)
                        cam.stream_on()

                        dev_info = dev_info_list[idx - 1]
                        model_name = dev_info.get("model_name", "Unknown")

                        self.cameras.append(cam)
                        self.camera_names.append(str(model_name))
                        print(f"[CameraManager] Opened camera {idx}: {model_name}")

                    except Exception as e:
                        print(f"[CameraManager] Failed to open camera {idx}: {e}")
            except Exception as e:
                print(f"[CameraManager] Failed to initialize device manager: {e}")
                use_fake_camera = True

        if not self.cameras:
            print("[CameraManager] No cameras detected, using dummy camera mode.")
            self.is_fake = True
            self.cameras = [None] * num_fake_cams
            self.camera_names = [f"DummyCam{i+1}" for i in range(num_fake_cams)]
            self._fake_exposure = [10000.0] * num_fake_cams
            self._fake_gain = [10.0] * num_fake_cams
            self._dummy_frame_idx = [0] * num_fake_cams

        self.num_cameras = max(1, len(self.cameras))
        self._cam_locks = [threading.Lock() for _ in range(self.num_cameras)]

        os.makedirs(self.save_dir, exist_ok=True)

        # For per-camera recording
        self.recording = [False] * self.num_cameras
        self.video_writers = [None] * self.num_cameras

    def _safe_name(self, s: str) -> str:
        return "".join(ch if (ch.isalnum() or ch in ("-", "_")) else "_" for ch in str(s)).strip("_")

    # --------------------------------------------------------------
    # Feature Ranges (Exposure/Gain)
    # --------------------------------------------------------------
    def get_exposure_range(self, cam_index):
        if self.is_fake:
            return {"min": 100.0, "max": 1000000.0}
        try:
            return self.cameras[cam_index].ExposureTime.get_range()
        except Exception as e:
            print(f"[CamMgr] Exposure range unavailable cam{cam_index}: {e}")
            return None

    def get_gain_range(self, cam_index):
        if self.is_fake:
            return {"min": 0.0, "max": 24.0}
        try:
            return self.cameras[cam_index].Gain.get_range()
        except Exception as e:
            print(f"[CamMgr] Gain range unavailable cam{cam_index}: {e}")
            return None

    # --------------------------------------------------------------
    # Frame Retrieval
    # --------------------------------------------------------------
    def get_frame(self, cam_index):
        if self.is_fake:
            return self._get_dummy_frame(cam_index)

        try:
            with self._cam_locks[cam_index]:
                cam = self.cameras[cam_index]
                raw = cam.data_stream[0].get_image()
                if raw is None:
                    return None

                img = raw.get_numpy_array()
                if img is None:
                    return None

                # convert GREY → BGR if needed
                if len(img.shape) == 2:
                    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

                return img

        except Exception as e:
            print(f"[CameraManager] get_frame error cam {cam_index}: {e}")
            return None

    def _get_dummy_frame(self, cam_index):
        cam_index = int(cam_index)
        if cam_index < 0 or cam_index >= self.num_cameras:
            return None

        self._dummy_frame_idx[cam_index] += 1
        h, w = 720, 1280
        frame = np.zeros((h, w, 3), dtype=np.uint8)

        label = f"Dummy Camera {cam_index + 1}"
        timestamp = datetime.now().strftime("%H:%M:%S")
        cv2.putText(frame, label, (40, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3, cv2.LINE_AA)
        cv2.putText(frame, timestamp, (40, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2, cv2.LINE_AA)

        x = 200 + (self._dummy_frame_idx[cam_index] * 6) % 800
        y = 300 + (self._dummy_frame_idx[cam_index] * 4) % 200
        cv2.circle(frame, (x, y), 40, (255, 128, 0), -1)

        info = f"Exp {self._fake_exposure[cam_index]:.0f} us  Gain {self._fake_gain[cam_index]:.2f}"
        cv2.putText(frame, info, (40, 700), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
        return frame

    # --------------------------------------------------------------
    # Screenshot
    # --------------------------------------------------------------
    def take_screenshot(
        self,
        cam_index,
        save_dir=None,
        prefix="screenshot",
        warmup_frames: int = 0,
        simple_name: bool = False,
    ):
        """
        Saves a PNG screenshot and returns the file path (or None on failure).
        """
        # Flush a few frames to reduce pipeline latency after stage moves.
        for _ in range(max(0, int(warmup_frames))):
            _ = self.get_frame(cam_index)
        frame = self.get_frame(cam_index)
        if frame is None:
            print(f"[CameraManager] Screenshot failed for cam {cam_index}")
            return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        cam_num = cam_index + 1
        model = self._safe_name(self.camera_names[cam_index]) if cam_index < len(self.camera_names) else "Unknown"
        out_dir = save_dir if save_dir is not None else self.save_dir
        os.makedirs(out_dir, exist_ok=True)
        prefix_safe = self._safe_name(prefix) if prefix else "screenshot"
        if simple_name:
            fname = os.path.join(out_dir, f"{prefix_safe}_{ts}.png")
        else:
            fname = os.path.join(out_dir, f"{prefix_safe}_cam{cam_num}_{model}_{ts}.png")
        with self._cam_locks[cam_index]:
            cv2.imwrite(fname, frame)
        print(f"[CameraManager] Saved {fname}")
        return fname

    # --------------------------------------------------------------
    # Video Recording (Per Camera)
    # --------------------------------------------------------------
    def start_recording(self, cam_index):
        if self.recording[cam_index]:
            print(f"[CameraManager] Cam {cam_index} already recording")
            return

        if self.is_fake:
            width, height = 1280, 720
        else:
            cam = self.cameras[cam_index]
            width = cam.Width.get()
            height = cam.Height.get()

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        cam_num = cam_index + 1
        model = self._safe_name(self.camera_names[cam_index]) if cam_index < len(self.camera_names) else "Unknown"
        fname = os.path.join(self.save_dir, f"video_cam{cam_num}_{model}_{ts}.avi")
        self.video_writers[cam_index] = cv2.VideoWriter(fname, fourcc, 20.0, (width, height))

        self.recording[cam_index] = True
        print(f"[CameraManager] Recording cam {cam_index} → {fname}")

    def stop_recording(self, cam_index):
        if not self.recording[cam_index]:
            return

        writer = self.video_writers[cam_index]
        if writer:
            writer.release()

        self.video_writers[cam_index] = None
        self.recording[cam_index] = False
        print(f"[CameraManager] Stopped recording cam {cam_index}")

    def write_record_frame(self, cam_index):
        if not self.recording[cam_index]:
            return
        frame = self.get_frame(cam_index)
        writer = self.video_writers[cam_index]
        if frame is not None and writer is not None:
            with self._cam_locks[cam_index]:
                writer.write(frame)

    # --------------------------------------------------------------
    # Exposure & Gain (Per Camera)
    # --------------------------------------------------------------
    
    def get_exposure(self, cam_index):
        if self.is_fake:
            return float(self._fake_exposure[cam_index])
        try:
            return float(self.cameras[cam_index].ExposureTime.get())
        except Exception as e:
            print(f"[CamMgr] get_exposure error cam{cam_index}: {e}")
            return 0.0

    def set_exposure(self, cam_index, value):
        if self.is_fake:
            v = float(value)
            rng = self.get_exposure_range(cam_index)
            if rng:
                v = max(float(rng["min"]), min(float(rng["max"]), v))
            self._fake_exposure[cam_index] = v
            return True, v
        try:
            v = float(value)
            rng = self.get_exposure_range(cam_index)
            if rng:
                v = max(float(rng["min"]), min(float(rng["max"]), v))
            self.cameras[cam_index].ExposureTime.set(v)
            print(f"[CamMgr] Exposure cam{cam_index} → {v}")
            return True, v
        except Exception as e:
            print(f"[CamMgr] set_exposure error cam{cam_index} value={value}: {e}")
            return False, self.get_exposure(cam_index)

    def get_gain(self, cam_index):
        if self.is_fake:
            return float(self._fake_gain[cam_index])
        try:
            return float(self.cameras[cam_index].Gain.get())
        except Exception as e:
            print(f"[CamMgr] get_gain error cam{cam_index}: {e}")
            return 0.0

    def set_gain(self, cam_index, value):
        if self.is_fake:
            v = float(value)
            rng = self.get_gain_range(cam_index)
            if rng:
                v = max(float(rng["min"]), min(float(rng["max"]), v))
            self._fake_gain[cam_index] = v
            return True, v
        try:
            v = float(value)
            rng = self.get_gain_range(cam_index)
            if rng:
                v = max(float(rng["min"]), min(float(rng["max"]), v))
            self.cameras[cam_index].Gain.set(v)
            print(f"[CamMgr] Gain cam{cam_index} → {v}")
            return True, v
        except Exception as e:
            print(f"[CamMgr] set_gain error cam{cam_index} value={value}: {e}")
            return False, self.get_gain(cam_index)


    # --------------------------------------------------------------
    # Cleanup
    # --------------------------------------------------------------
    def close(self):
        for i in range(len(self.cameras)):
            if self.video_writers[i]:
                self.video_writers[i].release()

        if not self.is_fake:
            for cam in self.cameras:
                try:
                    cam.stream_off()
                    cam.close_device()
                except Exception as e:
                    print(f"[CameraManager] close error: {e}")

        print("[CameraManager] Cameras closed.")


# Non-breaking alias for future rename (keep old name for imports)
CamImageManager = CameraManager
