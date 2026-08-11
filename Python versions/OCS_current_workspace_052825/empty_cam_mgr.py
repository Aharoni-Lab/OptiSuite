import os






class EmptyCameraManager:
    def __init__(self, save_dir="captures", reason="No camera backend available."):
        self.save_dir = save_dir
        os.makedirs(self.save_dir, exist_ok=True)
        self.reason = reason
        self.cameras = []
        self.camera_names = []
        self.num_cameras = 0
        self.recording = []
        self.video_writers = []
        print(f"[CameraManager] {reason}")

    def get_frame(self, cam_index):
        return None

    def get_exposure_range(self, cam_index):
        return None

    def get_gain_range(self, cam_index):
        return None

    def get_exposure(self, cam_index):
        return 0.0

    def get_gain(self, cam_index):
        return 0.0

    def set_exposure(self, cam_index, value):
        return False, 0.0

    def set_gain(self, cam_index, value):
        return False, 0.0

    def take_screenshot(self, *args, **kwargs):
        return None

    def start_recording(self, cam_index):
        return

    def stop_recording(self, cam_index):
        return

    def write_record_frame(self, cam_index):
        return

    def close(self):
        return
