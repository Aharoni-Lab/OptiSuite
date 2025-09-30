import threading
import time
import gxipy as gx
import cv2
import clr
import numpy as np

clr.AddReference("System.Drawing")
clr.AddReference("System.Windows.Forms")

import System
from System.Drawing import Bitmap, Imaging, Rectangle
from System.Drawing.Imaging import PixelFormat
from System.Windows.Forms import Application, Form, PictureBox, PictureBoxSizeMode, DockStyle, MethodInvoker
from System.Runtime.InteropServices import GCHandle, GCHandleType, Marshal


class CameraForm(Form):
    def __init__(self):
        super().__init__()
        print("Initializing Form...")
        self.Text = "Single Camera Test"
        self.Width = 800
        self.Height = 600

        self.pictureBox = PictureBox()
        self.pictureBox.Dock = DockStyle.Fill
        self.pictureBox.SizeMode = PictureBoxSizeMode.Zoom
        self.Controls.Add(self.pictureBox)

        self.cam = None
        self.streaming = False
        self.running = True

        # Bitmap related members for fast update
        self.bmp = None
        self.bmp_data = None
        self.buffer_size = 0
        self.buffer = None
        self.handle = None
        self.bmp_width = 0
        self.bmp_height = 0
        self.bmp_stride = 0

        print("Starting camera thread...")
        self.thread = threading.Thread(target=self.camera_loop)
        self.thread.daemon = True
        self.thread.start()

        self.FormClosing += self.on_closing

    def create_bitmap_and_buffer(self, width, height):
        print(f"Creating Bitmap and buffer for size {width}x{height}...")

        if self.bmp is not None:
            try:
                self.bmp.UnlockBits(self.bmp_data)
            except Exception as e:
                print(f"Exception unlocking bits: {e}")
            self.bmp.Dispose()

        self.bmp_width = width
        self.bmp_height = height
        
        self.bmp = Bitmap(width, height, PixelFormat.Format24bppRgb)
        self.bmp_data = self.bmp.LockBits(Rectangle(0, 0, width, height),
                                        Imaging.ImageLockMode.WriteOnly,
                                        PixelFormat.Format24bppRgb)
        self.bmp_stride = self.bmp_data.Stride
        print(f"Bitmap stride: {self.bmp_stride}")

        self.buffer_size = self.bmp_stride * height

        # Create a managed byte array for buffer
        self.buffer = System.Array.CreateInstance(System.Byte, self.buffer_size)

        # Free previous handle if any
        if self.handle is not None:
            self.handle.Free()
            self.handle = None

        # Pin the buffer
        self.handle = GCHandle.Alloc(self.buffer, GCHandleType.Pinned)


    def update_bitmap_from_numpy(self, img_np):
            # img_np: H x W x 3 uint8 RGB
        print("Updating bitmap from numpy array...")
        img_bgr = img_np[..., ::-1].copy()

        if self.handle is None:
            raise Exception("Pinned handle not allocated.")
        ptr = self.handle.AddrOfPinnedObject()
        
        print(f"img_np shape: {img_np.shape}")
        print(f"Bitmap dimensions: {self.bmp_width} x {self.bmp_height}, stride: {self.bmp_stride}")

        for y in range(self.bmp_height):
            src_row = img_bgr[y].tobytes()
            dest_offset = y * self.bmp_stride
            try:
                Marshal.Copy(src_row, 0, ptr + dest_offset, self.bmp_width * 3)
            except Exception as e:
                print(f"Exception during Marshal.Copy at row {y}: {e}")
                raise

            if y % 100 == 0:
                print(f"Copied row {y} of {self.bmp_height}")
        print("Finished updating bitmap buffer.")



    def camera_loop(self):
        try:
            print("Creating device manager...")
            dev_manager = gx.DeviceManager()
            print("Updating device list...")
            dev_info_list = dev_manager.update_device_list()
            print(f"Devices found: {len(dev_info_list)}")
            if len(dev_info_list) == 0:
                raise Exception("No Daheng camera found.")

            print("Opening camera...")
            self.cam = dev_manager.open_device_by_index(1)

            print("Starting camera stream...")
            self.cam.stream_on()
            self.streaming = True
            print("Camera streaming started.")

            frame_count = 0

            while self.running:
                try:
                    raw_image = self.cam.data_stream[0].get_image()
                    if raw_image is None:
                        continue

                    rgb_image = raw_image.convert("RGB")
                    img_np = rgb_image.get_numpy_array()

                    # Downsample by half for performance
                    img_np_small = cv2.resize(img_np, (img_np.shape[1] // 2, img_np.shape[0] // 2), interpolation=cv2.INTER_AREA)
                    height, width, _ = img_np_small.shape

                    if self.bmp is None or width != self.bmp_width or height != self.bmp_height:
                        self.create_bitmap_and_buffer(width, height)

                    # Update bitmap pixel data from numpy array (fast pinned buffer)
                    self.update_bitmap_from_numpy(img_np_small)

                    frame_count += 1
                    if (frame_count == 1 or frame_count % 5 == 0) and not self.IsDisposed:
                        try:
                            print("Before Invoke UI update")
                            self.Invoke(MethodInvoker(lambda bmp=self.bmp: setattr(self.pictureBox, 'Image', bmp)))
                            print(f"After Invoke UI update: Bitmap displayed (frame {frame_count}).")
                        except Exception as e:
                            print(f"Error invoking UI update: {e}")
                            # Optionally break or stop streaming if fatal

                    # Very small sleep to yield CPU
                    time.sleep(0.005)

                except Exception as e:
                    print(f"Error grabbing frame: {e}")
                    time.sleep(0.01)

        except Exception as e:
            print(f"Camera initialization error: {e}")
        finally:
            print("Stopping camera stream in finally block...")
            try:
                if self.streaming and self.cam is not None:
                    self.cam.stream_off()
                    print("Camera streaming stopped.")
            except Exception as e:
                print(f"Exception during stream_off: {e}")

            try:
                if self.cam is not None:
                    self.cam.close_device()
                    print("Camera device closed.")
            except Exception as e:
                print(f"Exception closing camera: {e}")

            print("Camera thread exiting.")

    def on_closing(self, sender, event):
        print("Form closing, stopping camera...")
        self.running = False

        if self.thread.is_alive():
            print("Waiting for thread to exit...")
            self.thread.join(timeout=5)  # Increase timeout if needed

        # Now safe to clean resources
        if self.bmp_data is not None and self.bmp is not None:
            try:
                self.bmp.UnlockBits(self.bmp_data)
            except Exception as e:
                print(f"Exception unlocking bits: {e}")
            self.bmp_data = None

        if self.handle is not None:
            self.handle.Free()
            self.handle = None

        if self.bmp is not None:
            self.bmp.Dispose()
            self.bmp = None

if __name__ == "__main__":
    print("Launching camera form...")
    form = CameraForm()
    Application.Run(form)
