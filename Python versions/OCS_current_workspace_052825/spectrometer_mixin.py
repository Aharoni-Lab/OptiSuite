from spectro_meter import SpectrometerWindow, SpectrometerWorker




class SpectrometerMixin:
    """Mixin for the spectrometer."""
    
    #------------------------------------------------------------------------------------------------------------------
    #spectrometer
    #------------------------------------------------------------------------------------------------------------------
    def open_spectrometer_plot(self):
        """Open the spectrometer plot window and start streaming spectra."""
        if self.spectrometer_window is not None:
            self.spectrometer_window.show()
            self.spectrometer_window.raise_()
            self.spectrometer_window.activateWindow()
            if not (self.spectrometer_thread and self.spectrometer_thread.is_alive()):
                self.start_spectrometer_stream()
            return

        self.spectrometer_window = SpectrometerWindow(
            start_callback=self.start_spectrometer_stream,
            stop_callback=self.stop_spectrometer_stream,
        )
        self.spectrometer_window.closed.connect(self._on_spectrometer_window_closed)
        self.spectrometer_window.show()
        self.start_spectrometer_stream()

    def start_spectrometer_stream(self):
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

    def stop_spectrometer_stream(self):
        """Stop the background spectrometer worker and update controls."""
        if self.spectrometer_thread:
            self.spectrometer_thread.stop()
            self.spectrometer_thread = None
        if hasattr(self, "spectrometer_btn"):
            self.spectrometer_btn.setEnabled(True)
        if self.spectrometer_window is not None:
            self.spectrometer_window.set_stream_running(False)

    def _on_spectrometer_spectrum(self, wavelengths, intensities):
        """Forward a spectrum to the spectrometer plot window."""
        if self.spectrometer_window is not None:
            self.spectrometer_window.set_spectrum(wavelengths, intensities)

    def _on_spectrometer_status(self, text: str):
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

    def _on_spectrometer_error(self, text: str):
        """Display a spectrometer error and re-enable related controls."""
        if self.spectrometer_window is not None:
            self.spectrometer_window.set_status(text)
            self.spectrometer_window.set_stream_running(False)
        self.append_local_log(f"[Spectrometer] {text}")
        if hasattr(self, "spectrometer_btn"):
            self.spectrometer_btn.setEnabled(True)

    def _on_spectrometer_window_closed(self):
        """Clear the stored spectrometer window reference after close."""
        self.spectrometer_window = None




