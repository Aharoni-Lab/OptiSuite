from __future__ import annotations

from pathlib import Path
import json
from typing import Any, TYPE_CHECKING

from configuration_dialog import ConfigurationDialog
from PyQt5.QtWidgets import QDialog
ROOT_DIR = Path(__file__).resolve().parents[2]
import importlib.util
# load the usaf constants as standalone module to avoid library conflict of yolo with other libraries
_usaf_constants_spec = importlib.util.spec_from_file_location(
    "usaf_constants",
    ROOT_DIR / "usaf_interface" / "usaf_registration" / "constants.py",
)
_usaf_constants = importlib.util.module_from_spec(_usaf_constants_spec)
_usaf_constants_spec.loader.exec_module(_usaf_constants)
UsafConfig = _usaf_constants.UsafConfig

if TYPE_CHECKING:
    from camera_app_protocol import CameraAppHost



class ConfigurationMixin:
    """Mixin for configuration loading and saving."""
    


    #------------------------------------------------------------------------------------------------------------------
    #configuration functions
    #------------------------------------------------------------------------------------------------------------------

    #013026 add this for importing stage routine
    def _load_default_stage_sequence(self: CameraAppHost, path: Path) -> None:
        """Load default stage stops from config.json."""
        try:
            with open(path, "r", encoding="utf-8") as file:
                payload = json.load(file)
            if isinstance(payload, dict):
                self.custom_stage_sequence = payload.get("default_routine")
        except Exception as e:
            print(f"[StageSequence] failed to load default routine from {path}: {e}")
        return None

    def _current_configuration_payload(self: CameraAppHost) -> dict[str, Any]:
        """Build the current app configuration for saving."""
        payload = {}
        payload["default_routine"] = self.custom_stage_sequence or []
        try:
            with open(self.config_path, "r", encoding="utf-8") as file:
                current_config = json.load(file)
            if isinstance(current_config, dict):
                payload["resolution"] = current_config.get("resolution", {})
        except Exception as e:
            print(f"[Configuration] failed to load current configuration from {self.config_path}: {e}")
            payload["resolution"] = {}
            payload["resolution"]["usaf_target"] = UsafConfig().export_to_dict()

        payload["camera"] = [
            {
                "exposure": float(self.camera_control_widgets[cam_index]["exposure_input"].value()) if cam_index < self.cam_mgr.num_cameras else None,
                "gain": float(self.camera_control_widgets[cam_index]["gain_input"].value()) if cam_index < self.cam_mgr.num_cameras else None,
            }
            for cam_index in range(self.cam_mgr.num_cameras)
        ]

        return payload

    def open_configuration_dialog(self: CameraAppHost) -> None:
        """Open JSON configuration editor and reload default routine after save."""
        dialog = ConfigurationDialog(self.config_path, self._current_configuration_payload(), self)
        if dialog.exec_() != QDialog.Accepted:
            return
        if dialog.load_config:
            self.config_path = dialog.config_path
            self._load_default_cam_config(self.config_path)
            self._load_default_usaf_config(self.config_path)
            self._load_default_stage_sequence(self.config_path)
            self.append_local_log(f"[Configuration] loaded {self.config_path};")
        elif dialog.save_config:
            self.append_local_log(f"[Configuration] saved {dialog.save_path}")



    def _load_default_cam_config(self: CameraAppHost, path: Path) -> None:
        """Load default camera configuration from config.json."""
        try:
            with open(path, "r", encoding="utf-8") as file:
                payload = json.load(file)
            if isinstance(payload, dict):
                cam_config = payload.get("camera", [])
                valid_cam_config = min(len(cam_config), self.cam_mgr.num_cameras)
                for cam_index in range(valid_cam_config):
                    exposure = cam_config[cam_index].get("exposure", None)
                    gain = cam_config[cam_index].get("gain", None)
                    if exposure is not None:
                        self.apply_exposure(cam_index, self.camera_control_widgets[cam_index]["exposure_input"], exposure)
                    if gain is not None:
                        self.apply_gain(cam_index, self.camera_control_widgets[cam_index]["gain_input"], gain)
        except Exception as e:
            print(f"[Camera] failed to load camera configuration from {path}: {e}")





