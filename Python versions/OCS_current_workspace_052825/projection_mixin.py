from __future__ import annotations

import os
import threading
from typing import Any, TYPE_CHECKING

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication

from auto_solid_project import AutoSolidIntensityController
from constants import PROJECTION_PATTERN_INTERVAL_MS
from projection_settings import ProjectionWindow

if TYPE_CHECKING:
    from camera_app_protocol import CameraAppHost, FinishedCallback





class ProjectionMixin:
    """Mixin for projection."""
    


    #------------------------------------------------------------------------------------------------------------------
    #projection
    #------------------------------------------------------------------------------------------------------------------
    def _projection_patterns_for_projector(self: CameraAppHost, projector_index: int | None) -> tuple[str | None, list[Any]]:
        """Return the saved projection role and image list for a display."""
        if projector_index is None:
            return None, []
        try:
            projector_index = int(projector_index)
        except Exception:
            return None, []

        settings = getattr(self, "projection_settings", {}) or {}
        matches = (
            ("microscope", settings.get("microscope_display"), settings.get("microscope_patterns", [])),
            ("plate", settings.get("plate_display"), settings.get("plate_patterns", [])),
        )
        for role, display_index, patterns in matches:
            try:
                display_index = int(display_index)
            except Exception:
                continue
            if display_index == projector_index:
                return role, list(patterns or [])
        return None, []

    def _solid_color_from_settings(self: CameraAppHost, settings: dict[str, Any] | None) -> QColor:
        """Build a solid-projection QColor from saved intensity and channel."""
        settings = settings or {}
        intensity = max(0, min(100, int(settings.get("solid_intensity", 100))))
        value = int(round(255 * intensity / 100.0))
        color_name = str(settings.get("solid_color") or "red").strip().lower()
        if color_name == "green":
            return QColor(0, value, 0)
        if color_name == "blue":
            return QColor(0, 0, value)
        return QColor(value, 0, 0)

    def _show_live_solid_projection(self: CameraAppHost, projector_index: int | None, color: QColor) -> bool:
        """Show a solid color on the selected projector display."""
        screens = QApplication.screens()
        try:
            projector_index = int(projector_index)
        except Exception:
            self.append_local_log("[Projection] solid color projection has no valid display selected")
            return False
        if projector_index < 0 or projector_index >= len(screens):
            self.append_local_log(f"[Projection] Display {projector_index + 1} is not available for solid color projection")
            return False

        window = self.projection_windows.get(projector_index)
        if window is None:
            window = ProjectionWindow()
            self.projection_windows[projector_index] = window
        window.show_on_screen(screens[projector_index])
        window.display_solid_color(color)
        return True

    def _solid_display_index(self: CameraAppHost) -> int | None:
        """Return the saved or first external display index for solid projection."""
        settings = getattr(self, "projection_settings", {}) or {}
        for key in ("solid_display", "microscope_display", "plate_display"):
            try:
                return int(settings[key])
            except Exception:
                continue
        screens = QApplication.screens()
        primary = QApplication.primaryScreen()
        for index, screen in enumerate(screens):
            if screen != primary:
                return index
        return 0 if screens else None

    def _apply_stage_projection_color(self: CameraAppHost, color_name: str, projector_index: int) -> None:
        """Apply a solid projection color from a stage sequence stop."""
        settings = dict(getattr(self, "projection_settings", {}) or {})
        settings["solid_color"] = str(color_name).strip().lower()
        settings["solid_display"] = projector_index
        settings["solid_intensity"] = settings.get("solid_intensity", 100)
        self.projection_settings = settings
        self._show_live_solid_projection(projector_index, self._solid_color_from_settings(settings))

    def _apply_auto_solid_intensity(self: CameraAppHost, intensity: int) -> bool:
        """Show the saved solid color at intensity without opening the dialog."""
        settings = dict(getattr(self, "projection_settings", {}) or {})
        settings["solid_intensity"] = int(intensity)
        settings["solid_color"] = settings.get("solid_color") or "red"
        settings["solid_display"] = self._solid_display_index()
        self.projection_settings = settings
        return self._show_live_solid_projection(
            settings.get("solid_display"),
            self._solid_color_from_settings(settings),
        )

    def _set_auto_solid_intensity(self: CameraAppHost, intensity: int) -> None:
        """Ask the GUI thread to update the projector, then wait until it is applied."""
        self.auto_solid_applied.clear()
        self.ui_bus.auto_solid_apply.emit(int(intensity))
        self.auto_solid_applied.wait(2.0)

    def _on_auto_solid_apply(self: CameraAppHost, intensity: int) -> None:
        """Apply solid projection on the GUI thread."""
        try:
            self._apply_auto_solid_intensity(intensity)
        finally:
            self.auto_solid_applied.set()

    def start_auto_solid_projection(self: CameraAppHost, cam_index: int = 0, on_finished: FinishedCallback | None = None) -> bool:
        """Run AutoSolidIntensityController in a worker thread."""
        if self.auto_solid_thread and self.auto_solid_thread.is_alive():
            self.append_local_log("[AutoSolid] already running")
            return False
        if self.af_thread and self.af_thread.is_alive():
            self.append_local_log("[AutoSolid] wait for autofocus to finish")
            return False
        if cam_index < 0 or cam_index >= self.cam_mgr.num_cameras:
            self.append_local_log("[AutoSolid] no camera available")
            return False

        self.auto_solid_finished_callback = on_finished
        if hasattr(self, "autoSolidProjection_btn"):
            self.autoSolidProjection_btn.setEnabled(False)
        self.timer.stop()
        self.preview_status.setText("Preview paused (auto solid projection running).")
        self.preview_status.show()

        start_intensity = int((getattr(self, "projection_settings", {}) or {}).get("solid_intensity", 50) or 50)
        out_dir = os.path.join(self.cam_mgr.save_dir, "auto_solid")

        def _runner():
            try:
                controller = AutoSolidIntensityController(
                    cam_index=cam_index,
                    take_screenshot=lambda ci, save_dir, prefix, warmup_frames: self.cam_mgr.take_screenshot(
                        ci, save_dir=save_dir, prefix=prefix, warmup_frames=warmup_frames, simple_name=True
                    ),
                    set_intensity=self._set_auto_solid_intensity,
                    log=lambda s: self.ui_bus.log.emit(s),
                    start_intensity=start_intensity,
                )
                best, _stats = controller.run(out_dir=out_dir)
                self.ui_bus.log.emit(f"[AutoSolid] done intensity={best}%")
            except Exception as e:
                self.ui_bus.log.emit(f"[AutoSolid] error: {e}")
            finally:
                self.ui_bus.auto_solid_finished.emit()

        self.auto_solid_thread = threading.Thread(target=_runner, daemon=True)
        self.auto_solid_thread.start()
        return True

    def _on_auto_solid_finished(self: CameraAppHost) -> None:
        """Restore preview and button state after auto solid intensity exits."""
        try:
            self.timer.start(30)
        except Exception:
            pass
        if hasattr(self, "autoSolidProjection_btn"):
            self.autoSolidProjection_btn.setEnabled(self.cam_mgr.num_cameras > 0)
        self.preview_status.hide()
        callback = self.auto_solid_finished_callback
        self.auto_solid_finished_callback = None
        if callback:
            callback()

    def _stop_live_solid_projection(self: CameraAppHost, projector_index: int | None = None) -> None:
        """Close one or all live solid-color projection windows."""
        if projector_index is None:
            for window in list(self.projection_windows.values()):
                window.close()
            return
        try:
            projector_index = int(projector_index)
        except Exception: 
            return
        window = self.projection_windows.get(projector_index)
        if window is not None:
            window.close()
            self.append_local_log(f"[Projection] Display {projector_index + 1}: solid color projection stopped")

    def _start_projection_sequence(self: CameraAppHost, projector_index: int, patterns: list[str], role: str | None = None, on_finished: FinishedCallback | None = None) -> bool:
        """Display projection images in sequence on a selected display."""
        screens = QApplication.screens()
        if projector_index < 0 or projector_index >= len(screens):
            self.append_local_log(f"[Projection] Display {projector_index + 1} is not available")
            return False
        if self.projection_sequence_running:
            self.append_local_log("[Projection] projection already running; skipping new projection request")
            return False

        image_paths = [path for path in patterns if os.path.exists(path)]
        missing_count = len(patterns) - len(image_paths)
        if not image_paths:
            self.append_local_log(f"[Projection] no existing image files for Display {projector_index + 1}")
            return False
        if missing_count:
            self.append_local_log(f"[Projection] skipped {missing_count} missing image file(s)")

        window = self.projection_windows.get(projector_index)
        if window is None:
            window = ProjectionWindow()
            self.projection_windows[projector_index] = window
        window.show_on_screen(screens[projector_index])

        self.projection_sequence_running = True
        role_label = role or "selected"
        self.append_local_log(
            f"[Projection] Display {projector_index + 1}: projecting {len(image_paths)} {role_label} pattern(s)"
        )

        def show_next(index=0):
            if index >= len(image_paths):
                window.close()
                self.projection_sequence_running = False
                self.append_local_log(f"[Projection] Display {projector_index + 1}: sequence finished")
                if on_finished:
                    on_finished()
                return

            path = image_paths[index]
            ok = window.display_image(path)
            status = "shown" if ok else "failed"
            self.append_local_log(
                f"[Projection] Display {projector_index + 1}: {status} {index + 1}/{len(image_paths)} {path}"
            )
            QTimer.singleShot(PROJECTION_PATTERN_INTERVAL_MS, lambda: show_next(index + 1))

        QTimer.singleShot(0, show_next)
        return True










