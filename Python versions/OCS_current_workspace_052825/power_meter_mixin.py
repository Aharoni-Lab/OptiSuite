from power_meter import PowerMeterWindow, PowerMeterWorker


class PowerMeterMixin:
    """Mixin for the power meter."""
    

    #------------------------------------------------------------------------------------------------------------------
    #power meter
    #------------------------------------------------------------------------------------------------------------------
    def open_power_meter_plot(self, show_window=True, on_finished=None):
        """Open the power meter plot window and start streaming samples.
           if the window is already shown the fn wont hide it
           if the window is not shown the fn will show it depending on the show_window parameter"""
        if self.power_meter_window is not None:
            if show_window:
                self.power_meter_window.show()
                self.power_meter_window.raise_()
                self.power_meter_window.activateWindow()

            # Assume on_finished is already set correctly
            return

        if on_finished is None:
            self.power_meter_finished_callback = self.stage_routine.StepCompleted
        self.power_meter_finished_callback = on_finished

        self.power_meter_window = PowerMeterWindow(
            start_callback=self.start_power_meter_stream,
            stop_callback=self.stop_power_meter_stream,
            finish_callback=self.power_meter_finished_signal,
        )
        self.power_meter_window.closed.connect(self._on_power_meter_window_closed)
        if show_window:
            self.power_meter_window.show()
        self.start_power_meter_stream()

    def power_meter_finished_signal(self, power_w):
        """light wrapper that signals the power meter finished to the UI bus"""
        self.ui_bus.power_meter_finished.emit(power_w)

    def _on_power_meter_finished(self, power_w):
        """Callback for the power meter finished signal"""
        callback = self.power_meter_finished_callback
        if callback is not None:
            callback()

    def start_power_meter_stream(self):
        """Start the background power meter worker."""
        if self.power_meter_thread and self.power_meter_thread.is_alive():
            self._on_power_meter_status("Power meter stream already running.")
            return

        if hasattr(self, "power_meter_btn"):
            self.power_meter_btn.setEnabled(False)

        self.power_meter_thread = PowerMeterWorker(self.power_meter_bus, sample_interval_s=0.2)
        self.power_meter_thread.start()
        if self.power_meter_window is not None:
            self.power_meter_window.set_stream_running(True)

    def stop_power_meter_stream(self):
        """Stop the background power meter worker and update controls."""
        if self.power_meter_thread:
            self.power_meter_thread.stop()
            self.power_meter_thread = None
        if hasattr(self, "power_meter_btn"):
            self.power_meter_btn.setEnabled(True)
        if self.power_meter_window is not None:
            self.power_meter_window.set_stream_running(False)

    def _on_power_meter_sample(self, elapsed_s: float, power_w: float):
        """Forward a power meter sample to the plot window."""
        if self.power_meter_window is not None:
            self.power_meter_window.add_sample(elapsed_s, power_w)

    def _on_power_meter_status(self, text: str):
        """Display power meter status in the plot window and main log."""
        if self.power_meter_window is not None:
            self.power_meter_window.set_status(text)
        self.append_local_log(f"[PowerMeter] {text}")
        if text.startswith("Connected:") and self.power_meter_window is not None:
            self.power_meter_window.set_stream_running(True)
        if text == "Power meter disconnected." and hasattr(self, "power_meter_btn"):
            self.power_meter_btn.setEnabled(True)
            if self.power_meter_window is not None:
                self.power_meter_window.set_stream_running(False)

    def _on_power_meter_error(self, text: str):
        """Display a power meter error and re-enable related controls."""
        if self.power_meter_window is not None:
            self.power_meter_window.set_status(text)
            self.power_meter_window.set_stream_running(False)
        self.append_local_log(f"[PowerMeter] {text}")
        if hasattr(self, "power_meter_btn"):
            self.power_meter_btn.setEnabled(True)

    def _on_power_meter_window_closed(self):
        """Clear the stored power meter window reference after close."""
        self.power_meter_window = None



    def power_meter_after_routine(self):
        if getattr(self.stage_routine, "running", False):
            return
        # show the power meter window if it is not already shown
        if self.power_meter_window is not None and not self.power_meter_window.isVisible():
            self.power_meter_window.show()
            self.power_meter_window.raise_()
            self.power_meter_window.activateWindow()
        
        self.append_local_log("[PowerMeter] Power meter window shown after routine")

