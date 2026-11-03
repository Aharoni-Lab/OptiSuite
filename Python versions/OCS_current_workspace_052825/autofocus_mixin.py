from pathlib import Path
import sys
import json
import threading
import subprocess
from autofocus_routine import AutofocusRoutine
ROOT_DIR = Path(__file__).resolve().parents[2]




class AutofocusMixin:
    """Mixin for autofocus."""
    

    #------------------------------------------------------------------------------------------------------------------
    # autofocus functions
    #------------------------------------------------------------------------------------------------------------------


    def _load_default_usaf_config(self, config_path: Path):
        self.config_path = config_path

    def start_autofocus(self, cam_index: int = 0, on_finished=None, no_ui=False):
        """Run autofocus in a worker thread and open the USAF result UI."""
        if not (self.zmq_thread and self.zmq_thread.running):
            self.append_local_log("[AF] Not connected.")
            return False
        if cam_index < 0 or cam_index >= self.cam_mgr.num_cameras:
            self.append_local_log("[AF] No camera available.")
            return False
        if self.af_thread and self.af_thread.is_alive():
            self.append_local_log("[AF] Already running.")
            return False
        if self.auto_solid_thread and self.auto_solid_thread.is_alive():
            self.append_local_log("[AF] wait for auto solid projection to finish")
            return False

        self.autofocus_finished_callback = on_finished
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
                best_z, _pts, best_img_path = routine.run()
                self.autofocus_best_image_paths.append(str(best_img_path))
                self.ui_bus.log.emit(f"[AF] done best_z={best_z:.3f}")

                resolution_cmd = [sys.executable, "-m", "usaf_interface.resolution_app", str(best_img_path)]
                if no_ui:
                    resolution_cmd.append("--no-ui")
                if self.config_path is not None:
                    resolution_cmd.append("--usaf-config-path")
                    resolution_cmd.append(str(self.config_path))
                subprocess.Popen(
                    resolution_cmd,
                    cwd=str(ROOT_DIR),
                )
                
                self.ui_bus.log.emit(f"[AF] launched USAF UI for {best_img_path}")

            except Exception as e:
                self.ui_bus.log.emit(f"[AF] error: {e}")
            finally:
                self.ui_bus.autofocus_finished.emit()

        self.af_thread = threading.Thread(target=_runner, daemon=True)
        self.af_thread.start()
        return True


    def cancel_autofocus(self):
        """Request cancellation of the running autofocus routine."""
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
        """Restore preview and button state after autofocus exits."""
        # Resume preview
        try:
            self.timer.start(30)
        except Exception:
            pass
        self.autofocus_btn.setEnabled(self.cam_mgr.num_cameras > 0)
        self.cancel_af_btn.setEnabled(False)
        self._refresh_resume_button_state()
        self.preview_status.hide()
        callback = getattr(self, "autofocus_finished_callback", None)
        self.autofocus_finished_callback = None
        if callback:
            callback()



