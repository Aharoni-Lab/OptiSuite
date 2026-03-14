import cv2
import gxipy as gx
import numpy as np
import os
from datetime import datetime

# -----------------------------
# Setup device manager and cameras
# -----------------------------
device_manager = gx.DeviceManager()
dev_info_list = device_manager.update_device_list()
cameras = []

for idx, dev_info in enumerate(dev_info_list):
    try:
        cam = device_manager.open_device_by_index(idx)
        cam.TriggerMode.set(gx.GxSwitchEntry.OFF)
        cam.stream_on()
        cameras.append(cam)
        print(f"Opened camera {idx}: {dev_info.get('model_name')}")
    except Exception as e:
        print(f"Failed to open camera {idx}: {e}")

if not cameras:
    print("No cameras available.")
    exit()

# -----------------------------
# Helper to get frame safely
# -----------------------------
def get_frame(cam, stream_index=0):
    """Return a raw image from camera, handling single or multi-stream cameras."""
    ds = cam.data_stream
    if isinstance(ds, list):
        ds = ds[stream_index]  # take first stream by default
    return ds.get_image()

# -----------------------------
# Setup save directory
# -----------------------------
#manual path
save_dir = r"C:\Users\stimscope1\Documents\OptiSuite\screenshots"
os.makedirs(save_dir, exist_ok=True)

# Video writers (will initialize on first recording)
video_writers = [None] * len(cameras)
recording = False
frame_count = 0

# -----------------------------
# Main loop
# -----------------------------
try:
    while True:
        # Capture frames from all cameras
        for i, cam in enumerate(cameras):
            raw_image = get_frame(cam)
            if raw_image is None:
                continue

            img = raw_image.get_numpy_array()
            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

            cv2.imshow(f'Camera {i}', img)

            # Write video only if recording
            if recording and video_writers[i] is not None:
                video_writers[i].write(img)

        key = cv2.waitKey(1) & 0xFF

        # Quit program
        if key == ord('q'):
            break

        # Toggle video recording
        elif key == ord('v'):
            recording = not recording
            if recording:
                print("Recording started")
                # Initialize new video files for this recording session
                for i, cam in enumerate(cameras):
                    width = cam.Width.get()
                    height = cam.Height.get()
                    fourcc = cv2.VideoWriter_fourcc(*'XVID')
                    filename = os.path.join(save_dir, f'camera_{i}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.avi')
                    video_writers[i] = cv2.VideoWriter(filename, fourcc, 20.0, (width, height))
                    print(f"Recording camera {i} to {filename}")
            else:
                print("Recording stopped")
                for writer in video_writers:
                    if writer is not None:
                        writer.release()
                video_writers = [None] * len(cameras)

        # Take screenshots
        elif key == ord('s'):
            for i, cam in enumerate(cameras):
                try:
                    raw_image = get_frame(cam)
                    if raw_image is None:
                        print(f"Camera {i} frame not ready for screenshot")
                        continue
                    img = raw_image.get_numpy_array()
                    if len(img.shape) == 2:
                        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

                    filename = os.path.join(save_dir, f'screenshot_cam_{i}_{frame_count}.png')
                    cv2.imwrite(filename, img)
                    print(f"Saved {filename}")
                except Exception as e:
                    print(f"Failed to save screenshot for camera {i}: {e}")

            frame_count += 1

        # Real-time exposure/gain adjustment
        elif key == ord('e'):  # increase exposure
            for cam in cameras:
                current = cam.ExposureTime.get()
                cam.ExposureTime.set(current + 1000)
            print("Increased exposure")
        elif key == ord('d'):  # decrease exposure
            for cam in cameras:
                current = cam.ExposureTime.get()
                cam.ExposureTime.set(max(1, current - 1000))
            print("Decreased exposure")
        elif key == ord('g'):  # increase gain
            for cam in cameras:
                current = cam.Gain.get()
                cam.Gain.set(min(24, current + 1))
            print("Increased gain")
        elif key == ord('f'):  # decrease gain
            for cam in cameras:
                current = cam.Gain.get()
                cam.Gain.set(max(0, current - 1))
            print("Decreased gain")

finally:
    # Cleanup
    for cam, writer in zip(cameras, video_writers):
        cam.stream_off()
        cam.close_device()
        if writer is not None:
            writer.release()
    cv2.destroyAllWindows()
    print("All cameras closed and videos saved.")
