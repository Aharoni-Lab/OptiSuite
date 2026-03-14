# stage_routine.py

class StageRoutine:
    def __init__(self, send_move_callback, log_callback=None):
        """
        send_move_callback(x, y, z): function to send a move command (e.g., via ZMQ)
        log_callback(str): optional function to log messages to GUI
        """
        self.send_move = send_move_callback
        self.log = log_callback if log_callback else print

        # -----------------------------
        # Optional stage travel safety limits (soft clamp)
        # Defaults are conservative: do not command negative positions.
        # Set any of these to None to disable that bound.
        # -----------------------------
        self.StageMinX = 0.0
        # Some stages/controllers can behave badly extremely close to 0.
        # Default to a small >0 minimum for Y; adjust as you learn hardware limits.
        self.StageMinY = 0.3
        self.StageMinZ = 0.0
        self.StageMaxX = None
        self.StageMaxY = None
        self.StageMaxZ = None

        # -----------------------------
        # Absolute (Autodesk drawing of the 3D printed slide ) coordinates
        # Bottom-right = (0, 0)
        # X, Y are abs but Z is measured
        # -----------------------------
        self.AlignPtX, self.AlignPtY, self.AlignPtZ = 105.0, 23.5, 60.875 
        self.FlrX, self.FlrY, self.FlrZ = 130.0, 23.5, 60.875
        self.EmptyX, self.EmptyY, self.EmptyZ = 113, 47, 60.875      
        self.ImgX, self.ImgY, self.ImgZ = 113, 74, 65 #PLACEHOLDER Z VALUE            
        self.PSFX, self.PSFY, self.PSFZ = 152, 104, 60.875             
        self.SpectromX, self.SpectromY, self.SpectromZ = 51, 99, 55 #PLACEHOLDER Z VALUE
        self.PwrMX, self.PwrMY, self.PwrMZ = 44, 55, 50 #PLACEHOLDER Z VALUE      
        self.SlideX, self.SlideY, self.SlideZ = 75, 11, 60.875         

        # -----------------------------
        # Measured & transform
        # -----------------------------
        self.MeasuredAlignPtX = None
        self.MeasuredAlignPtY = None
        self.MeasuredAlignPtZ = None

        #only x and y trans offsets bc z axis is fixed (as is the stage)
        self.TransOffsetX = 0.0
        self.TransOffsetY = 0.0

        # -----------------------------
        # Routine state
        # -----------------------------
        self.steps = []
        self.current_step = 0
        self.paused = False
        self.running = False

    # -----------------------------
    # Calibration
    # -----------------------------
    def SetAlignPt(self, measured_x = 66.8, measured_y = 4, measured_z = 60.875): #normally, don't hardcode these values 
        self.MeasuredAlignPtX = measured_x
        self.MeasuredAlignPtY = measured_y
        self.MeasuredAlignPtZ = measured_z
        self.CalcTransOffset()

    def CalcTransOffset(self):
        if self.MeasuredAlignPtX is None or self.MeasuredAlignPtY is None:
            raise ValueError("Measured alignment point not set.")

        self.TransOffsetX = self.MeasuredAlignPtX - self.AlignPtX
        self.TransOffsetY = self.MeasuredAlignPtY - self.AlignPtY

        self.log(f"[StageRoutine] TransOffset = ({self.TransOffsetX}, {self.TransOffsetY})")
        

    # -----------------------------
    # Internal helper
    # -----------------------------
    def _clamp(self, v, vmin, vmax):
        if vmin is not None and v < vmin:
            return vmin, True
        if vmax is not None and v > vmax:
            return vmax, True
        return v, False

    def _apply_stage_limits(self, x, y, z, label=""):
        x2, cx = self._clamp(float(x), self.StageMinX, self.StageMaxX)
        y2, cy = self._clamp(float(y), self.StageMinY, self.StageMaxY)
        z2, cz = self._clamp(float(z), self.StageMinZ, self.StageMaxZ)
        if cx or cy or cz:
            self.log(
                f"[StageRoutine] WARNING: clamped target for {label} "
                f"from ({x:.3f}, {y:.3f}, {z:.3f}) to ({x2:.3f}, {y2:.3f}, {z2:.3f})"
            )
        return x2, y2, z2

    def _run_to_abs(self, abs_x, abs_y, abs_z, label=""):
        target_x = abs_x + self.TransOffsetX
        target_y = abs_y + self.TransOffsetY
        target_z = abs_z

        self.log(f"[StageRoutine] Running to {label} -> Stage ({target_x}, {target_y}, {target_z})")

        # Keep floats to preserve calibration precision (e.g. Z=60.875)
        x2, y2, z2 = self._apply_stage_limits(target_x, target_y, target_z, label=label)
        self.send_move(x2, y2, z2)


    # def _run_to_abs(self, abs_x, abs_y, label=""):
    #     target_x = abs_x + self.TransOffsetX
    #     target_y = abs_y + self.TransOffsetY

    #     self.log(f"[StageRoutine] Running to {label} -> Stage ({target_x}, {target_y})")

    #     # Axis 0 = X, Axis 1 = Y (based on your setup)
    #     self._pending_moves = [
    #         (0, int(target_x)),
    #         (1, int(target_y)),
    #     ]
    #     self._run_next_axis_move()
    
    # #do this to prevent too many sequential zeromq commands (I really ought to properly implement a C# queue lol)
    # def _run_next_axis_move(self):
    #     if not self._pending_moves:
    #         return

    #     axis, target = self._pending_moves.pop(0)
    #     self.log(f"[StageRoutine] Moving axis {axis} -> {target}")
    #     self.send_move(axis, target)


    # -----------------------------
    # RunTo<Instrument> functions
    # -----------------------------
    def RunToAlign(self):
        self._run_to_abs(self.AlignPtX, self.AlignPtY, self.AlignPtZ, "AlignPt")

    def RunToFlr(self):
        self._run_to_abs(self.FlrX, self.FlrY, self.FlrZ, "Fluorescent")

    def RunToEmpty(self):
        self._run_to_abs(self.EmptyX, self.EmptyY, self.EmptyZ, "Empty")

    def RunToImg(self):
        self._run_to_abs(self.ImgX, self.ImgY, self.ImgZ, "Image")

    def RunToPSF(self):
        self._run_to_abs(self.PSFX, self.PSFY, self.PSFZ, "PSF")

    def RunToSpectrom(self):
        self._run_to_abs(self.SpectromX, self.SpectromY, self.SpectromZ, "Spectrometer")

    def RunToPwr(self):
        self._run_to_abs(self.PwrMX, self.PwrMY, self.PwrMZ, "PowerMeter")

    def RunToSlide(self):
        self._run_to_abs(self.SlideX, self.SlideY, self.SlideZ, "Slide")

    # -----------------------------
    # Routine control
    # -----------------------------
    def BuildTestRoutine(self):
        # Clockwise from AlignPt, with pause after each step
        self.steps = [
            self.RunToAlign,
            self.RunToFlr,
            self.RunToEmpty,
            self.RunToImg,
            self.RunToPSF,
            self.RunToSpectrom,
            self.RunToPwr,
            self.RunToSlide,
        ]
        self.current_step = 0

    def StartRoutine(self):
        if not self.steps:
            self.BuildTestRoutine()

        self.running = True
        self.paused = False
        self.current_step = 0
        self.log("[StageRoutine] Routine started.")
        self._run_next_step()

    def Pause(self):
        if not self.running:
            return
        self.paused = True
        self.log("[StageRoutine] Routine paused.")

    def Resume(self):
        if not self.running:
            return
        if not self.paused:
            return

        self.paused = False
        self.log("[StageRoutine] Routine resumed.")

        # If still moving axes for this station, continue those first
        if hasattr(self, "_pending_moves") and self._pending_moves:
            self._run_next_axis_move()
        else:
            self._run_next_step()


    def Stop(self):
        self.running = False
        self.paused = False
        self.log("[StageRoutine] Routine stopped.")

    def StepCompleted(self):
        if not self.running:
            return

        # If we still have axis moves pending for this step, do next one
        if hasattr(self, "_pending_moves") and self._pending_moves:
            self._run_next_axis_move()
            return

        # Otherwise go to next station
        self._run_next_step()


    def _run_next_step(self):
        if not self.running:
            return

        if self.current_step >= len(self.steps):
            self.log("[StageRoutine] Routine finished.")
            self.running = False
            return

        step_fn = self.steps[self.current_step]
        self.log(f"[StageRoutine] Step {self.current_step + 1}/{len(self.steps)}")

        step_fn() # This will send the first axis move

        self.current_step += 1
        self.paused = True  # Paused after station (X+Y done)
        self.log("[StageRoutine] Paused after step.")
