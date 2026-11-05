from __future__ import annotations

from typing import Any, TYPE_CHECKING

from spectro_meter import SpectrometerWindow, SpectrometerWorker

if TYPE_CHECKING:
    from camera_app_protocol import CameraAppHost, FinishedCallback




class SpectrometerMixin:
    """Mixin for the spectrometer."""
    
    #------------------------------------------------------------------------------------------------------------------
    #spectrometer
    #------------------------------------------------------------------------------------------------------------------
    def open_spectrometer_plot(self: CameraAppHost, show_window: bool = True, on_finished: FinishedCallback | None = None) -> None:
        """Open the spectrometer plot window and start streaming spectra."""
        if self.spectrometer_window is not None:
            if show_window:
                self.spectrometer_window.show()
                self.spectrometer_window.raise_()
                self.spectrometer_window.activateWindow()
            
            return

        if on_finished is None:
            self.spectro_meter_finished_callback = self.stage_routine.StepCompleted
        self.spectro_meter_finished_callback = on_finished

        self.spectrometer_window = SpectrometerWindow(
            start_callback=self.start_spectrometer_stream,
            stop_callback=self.stop_spectrometer_stream,
            finish_callback=self.spectro_meter_finished_signal,
        )
        self.spectrometer_window.closed.connect(self._on_spectrometer_window_closed)
        if show_window:
            self.spectrometer_window.show()
        self.start_spectrometer_stream()


    def spectro_meter_finished_signal(self: CameraAppHost, result: Any) -> None:
        """light wrapper that signals the spectrometer finished to the UI bus"""
        self.ui_bus.spectro_meter_finished.emit(result)

    def _on_spectrometer_finished(self: CameraAppHost, result: Any) -> None:
        """Callback for the spectrometer finished signal"""
        callback = self.spectro_meter_finished_callback
        if callback is not None:
            callback()

    def start_spectrometer_stream(self: CameraAppHost) -> None:
        """Start the background spectrometer worker."""
        if self.spectrometer_thread and self.spectrometer_thread.is_alive():
            self._on_spectrometer_status("Spectrometer stream already running.")
            return

        if hasattr(self, "spectrometer_btn"):
            self.spectrometer_btn.setEnabled(False)

        self.spectrometer_thread = SpectrometerWorker(
            self.spectrometer_bus,
            integration_time_s=10.0e-3,
            plot_interval_s=0.2,
        )
        self.spectrometer_thread.start()
        if self.spectrometer_window is not None:
            self.spectrometer_window.set_stream_running(True)

    def stop_spectrometer_stream(self: CameraAppHost) -> None:
        """Stop the background spectrometer worker and update controls."""
        if self.spectrometer_thread:
            self.spectrometer_thread.stop()
            self.spectrometer_thread = None
        if hasattr(self, "spectrometer_btn"):
            self.spectrometer_btn.setEnabled(True)
        if self.spectrometer_window is not None:
            self.spectrometer_window.set_stream_running(False)

    def _on_spectrometer_spectrum(self: CameraAppHost, wavelengths: Any, intensities: Any) -> None:
        """Forward a spectrum to the spectrometer plot window."""
        if self.spectrometer_window is not None:
            self.spectrometer_window.set_spectrum(wavelengths, intensities)

    def _on_spectrometer_status(self: CameraAppHost, text: str) -> None:
        """Display spectrometer status in the plot window and main log."""
        if self.spectrometer_window is not None:
            self.spectrometer_window.set_status(text)
        self.append_local_log(f"[Spectrometer] {text}")
        if text.startswith("Connected:") and self.spectrometer_window is not None:
            self.spectrometer_window.set_stream_running(True)
        if text == "Spectrometer disconnected." and hasattr(self, "spectrometer_btn"):
            self.spectrometer_btn.setEnabled(True)
            if self.spectrometer_window is not None:
                self.spectrometer_window.set_stream_running(False)

    def _on_spectrometer_error(self: CameraAppHost, text: str) -> None:
        """Display a spectrometer error and re-enable related controls."""
        if self.spectrometer_window is not None:
            self.spectrometer_window.set_status(text)
            self.spectrometer_window.set_stream_running(False)
        self.append_local_log(f"[Spectrometer] {text}")
        if hasattr(self, "spectrometer_btn"):
            self.spectrometer_btn.setEnabled(True)

    def _on_spectrometer_window_closed(self: CameraAppHost) -> None:
        """Clear the stored spectrometer window reference after close."""
        self.spectrometer_window = None




    def spectro_meter_after_routine(self: CameraAppHost) -> None:
        if getattr(self.stage_routine, "running", False):
            return
        # show the spectrometer window if it is not already shown
        if self.spectrometer_window is not None and not self.spectrometer_window.isVisible():
            self.spectrometer_window.show()
            self.spectrometer_window.raise_()
            self.spectrometer_window.activateWindow()
            self.append_local_log("[Spectrometer] Spectrometer window shown after routine")

