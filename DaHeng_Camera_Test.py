import gxipy as gx
import cv2

device_manager = gx.DeviceManager()
dev_info_list = device_manager.update_device_list()

if len(dev_info_list) == 0:
    raise Exception("No Daheng camera found.")

cam = device_manager.open_device_by_index(1)
cam.TriggerMode.set(gx.GxSwitchEntry.OFF)
cam.stream_on()

raw_image = cam.data_stream[0].get_image()
rgb_image = raw_image.convert("RGB")
img_np = rgb_image.get_numpy_array()

cv2.imshow("USB Camera Feed", img_np)
cv2.waitKey(0)
cv2.destroyAllWindows()

cam.stream_off()
cam.close_device()
