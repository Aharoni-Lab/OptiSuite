import threading
import time
import gxipy as gx
import cv2
import clr

clr.AddReference("System.Drawing")
clr.AddReference("System.Windows.Forms")

import System
from System.Drawing import Bitmap, Imaging
from System.Drawing.Imaging import PixelFormat
from System.Windows.Forms import Application, Form, PictureBox, PictureBoxSizeMode, DockStyle, MethodInvoker


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
        self.bmp = None

        # Start camera thread
        print("Starting camera thread...")
        self.thread = threading.Thread(target=self.camera_loop)
        self.thread.daemon = True
        self.thread.start()

        # Hook form closing event to cleanup
        self.FormClosing += self.on_closing

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

            import System.Runtime.InteropServices as interop
            frame_count = 0

            while self.running:
                try:
                    raw_image = self.cam.data_stream[0].get_image()
                    if raw_image is None:
                        continue

                    rgb_image = raw_image.convert("RGB")
                    img_np = rgb_image.get_numpy_array()

                    # Resize (downsample)
                    img_np_small = cv2.resize(img_np, (img_np.shape[1] // 2, img_np.shape[0] // 2), interpolation=cv2.INTER_AREA)
                    height, width, _ = img_np_small.shape

                    # Create Bitmap once on first frame
                    if self.bmp is None:
                        from System.Drawing import Bitmap, Imaging
                        from System.Drawing.Imaging import PixelFormat
                        self.bmp = Bitmap(width, height, PixelFormat.Format24bppRgb)

                    # Update Bitmap pixels in place
                    bmp_data = self.bmp.LockBits(
                        System.Drawing.Rectangle(0, 0, width, height),
                        Imaging.ImageLockMode.WriteOnly,
                        PixelFormat.Format24bppRgb)

                    stride = bmp_data.Stride
                    ptr = bmp_data.Scan0

                    # Convert RGB to BGR for Windows bitmap
                    img_bgr = img_np_small[..., ::-1].copy()
                    flat = img_bgr.flatten()
                    byte_array = System.Array[System.Byte](flat.tolist())

                    if stride == width * 3:
                        interop.Marshal.Copy(byte_array, 0, ptr, flat.size)
                    else:
                        for y in range(height):
                            row_ptr = ptr + y * stride
                            offset = y * width * 3
                            interop.Marshal.Copy(byte_array, offset, row_ptr, width * 3)

                    self.bmp.UnlockBits(bmp_data)

                    frame_count += 1
                    if (frame_count == 1 or frame_count % 5 == 0) and not self.IsDisposed:
                        self.Invoke(MethodInvoker(lambda bmp=self.bmp: setattr(self.pictureBox, 'Image', bmp)))
                        print(f"Bitmap displayed (frame {frame_count}).")

                    print(f"Processed frame {frame_count}")
                    time.sleep(0.01)

                except Exception as e:
                    print(f"Error grabbing frame: {e}")
                    time.sleep(0.01)

        except Exception as e:
            print(f"Camera initialization error: {e}")
        finally:
            print("Stopping camera stream in finally block...")
            try:
                if self.streaming:
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
        
    def numpy_rgb_to_bitmap(self, img_np, width, height):
        import System.Runtime.InteropServices as interop
        import numpy as np
        import System

        print("Converting to Bitmap...")
        img_bgr = img_np[..., ::-1].copy()
        print("Flipping RGB to BGR...")

        bmp = Bitmap(width, height, PixelFormat.Format24bppRgb)
        print("Creating Bitmap...")
        bmp_data = bmp.LockBits(
            System.Drawing.Rectangle(0, 0, width, height),
            Imaging.ImageLockMode.WriteOnly,
            PixelFormat.Format24bppRgb)

        stride = bmp_data.Stride
        ptr = bmp_data.Scan0

        print(f"Stride: {stride}, Row size: {width * 3}")

        flat = img_bgr.flatten()
        byte_array = System.Array[System.Byte](flat.tolist())
        interop.Marshal.Copy(byte_array, 0, ptr, flat.size)


        try:
            if stride == width * 3:
                print("Copying entire buffer...")
                interop.Marshal.Copy(byte_array, 0, ptr, flat.size)
            else:
                print("Copying row by row...")
                for y in range(height):
                    row_ptr = ptr + y * stride
                    offset = y * width * 3
                    interop.Marshal.Copy(byte_array, offset, row_ptr, width * 3)
        except Exception as e:
            print(f"Error in Marshal.Copy: {e}")

        bmp.UnlockBits(bmp_data)
        print("Bitmap created.")
        return bmp

    def on_closing(self, sender, event):
        print("Form closing, stopping camera...")
        self.running = False

        if self.thread.is_alive():
            print("Waiting for thread to exit...")
            self.thread.join(timeout=2)
            


if __name__ == "__main__":
    print("Launching camera form...")
    form = CameraForm()
    Application.Run(form)
