from __future__ import annotations

from typing import Any, TYPE_CHECKING

import cv2
from PyQt5.QtCore import QEvent, QObject, QPoint, Qt
from PyQt5.QtWidgets import QLabel

if TYPE_CHECKING:
    from camera_app_protocol import CameraAppHost




class CameraPreviewMixin:
    """Mixin for camera preview mouse events and zooming."""
    #---------------------------------------------------------------------------------------------------------------------------------
    # Camera Preview Mouse Events and Zooming Functions
    #---------------------------------------------------------------------------------------------------------------------------------

    def eventFilter(self: CameraAppHost, obj: QObject, event: QEvent) -> bool:
        """Handle camera preview mouse events for zooming and panning."""
        # Mouse-wheel zoom + cursor tracking on each preview label
        cam_index = obj.property("cam_index") if hasattr(obj, "property") else None
        if cam_index is None:
            return super().eventFilter(obj, event)

        cam_index = int(cam_index)
        if cam_index >= self.cam_mgr.num_cameras:
            return False

        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self.last_mouse_pos[cam_index] = event.pos()
            if float(self.view_states[cam_index]["zoom"]) > 1.000001:
                self.pan_active[cam_index] = True
                self.pan_last_pos[cam_index] = event.pos()
                obj.setCursor(Qt.ClosedHandCursor)
                return True
            obj.setCursor(Qt.OpenHandCursor)
            return False

        if event.type() == QEvent.MouseMove:
            self.last_mouse_pos[cam_index] = event.pos()
            if self.pan_active[cam_index]:
                self.pan_camera_view(cam_index, event.pos())
                return True
            if float(self.view_states[cam_index]["zoom"]) > 1.000001:
                obj.setCursor(Qt.OpenHandCursor)
            else:
                obj.unsetCursor()
            return False

        if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            self.pan_active[cam_index] = False
            self.pan_last_pos[cam_index] = None
            if float(self.view_states[cam_index]["zoom"]) > 1.000001:
                obj.setCursor(Qt.OpenHandCursor)
            else:
                obj.unsetCursor()
            return True

        if event.type() == QEvent.Leave:
            if not self.pan_active[cam_index]:
                obj.unsetCursor()
            return False

        if event.type() == QEvent.Wheel:
            dy = event.angleDelta().y()
            if dy == 0:
                return True

            steps = dy / 120.0
            factor = float(1.25 ** steps)
            self.zoom_at_label_pos(cam_index, factor, event.pos())
            if float(self.view_states[cam_index]["zoom"]) > 1.000001:
                obj.setCursor(Qt.OpenHandCursor)
            else:
                obj.unsetCursor()
            return True

        return super().eventFilter(obj, event)

    def pan_camera_view(self: CameraAppHost, cam_index: int, label_pos: QPoint | None) -> None:
        """Pan a zoomed camera preview based on mouse movement."""
        prev = self.pan_last_pos[cam_index]
        if prev is None or label_pos is None:
            self.pan_last_pos[cam_index] = label_pos
            return

        state = self.view_states[cam_index]
        z = float(state["zoom"])
        if z <= 1.000001:
            self.pan_last_pos[cam_index] = label_pos
            return

        label = self.cam_labels[cam_index]
        pm_rect = self._get_pixmap_rect_in_label(label)
        if pm_rect is None:
            self.pan_last_pos[cam_index] = label_pos
            return
        _off_x, _off_y, pm_w, pm_h = pm_rect
        if pm_w <= 0 or pm_h <= 0:
            self.pan_last_pos[cam_index] = label_pos
            return

        dx = float(label_pos.x() - prev.x())
        dy = float(label_pos.y() - prev.y())
        view_w = 1.0 / z
        view_h = 1.0 / z

        cx = float(state["cx"]) - dx / float(pm_w) * view_w
        cy = float(state["cy"]) - dy / float(pm_h) * view_h
        half_w = view_w / 2.0
        half_h = view_h / 2.0
        state["cx"] = max(half_w, min(1.0 - half_w, cx))
        state["cy"] = max(half_h, min(1.0 - half_h, cy))
        self.pan_last_pos[cam_index] = label_pos

    def adjust_zoom(self: CameraAppHost, cam_index: int, multiplier: float) -> None:
        """
        Zoom a camera preview around the last known mouse position.
        use for zoom button where no mouse position is provided
        """
        self.zoom_at_label_pos(cam_index, float(multiplier), self.last_mouse_pos[cam_index])

    def reset_zoom(self: CameraAppHost, cam_index: int) -> None:
        """Reset one camera preview to full-frame 1x zoom."""
        self.view_states[cam_index] = {"zoom": 1.0, "cx": 0.5, "cy": 0.5}
        self._update_zoom_label(cam_index)

    def _update_zoom_label(self: CameraAppHost, cam_index: int) -> None:
        """Update the text label that shows the current preview zoom level."""
        lbl = self.zoom_labels[cam_index]
        if not lbl:
            return
        z = float(self.view_states[cam_index]["zoom"])
        if abs(z - 1.0) < 1e-6:
            lbl.setText("1.0x")
        else:
            lbl.setText(f"{z:.2f}x")

    def _get_pixmap_rect_in_label(self: CameraAppHost, label: QLabel) -> tuple[int, int, int, int] | None:
        """Return the displayed pixmap rectangle inside a preview label."""
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

    def zoom_at_label_pos(self: CameraAppHost, cam_index: int, factor: float, label_pos: QPoint | None) -> None:
        """Zoom toward a point in the preview while keeping that point anchored."""
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

    def apply_zoom(self: CameraAppHost, frame: Any, cam_index: int) -> Any:
        """Crop and resize a frame according to the stored software zoom state."""
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

