# version:1.0.2312.9221
import sys
import MultiCamDlg
import gxipy as gx
from PyQt5.Qt import *
import time
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.Qt import (QApplication, QThread)
from ctypes import *
from gxipy.gxidef import *
import numpy
from gxipy.ImageFormatConvert import *

device_num = 2  # Maximum number of supported display devices
thread_flag = [0, 1]  # Thread start stop thread flag array
thread_cam = [0, 1]  # Thread array


class MultiCam(QMainWindow, MultiCamDlg.Ui_MultiCamDlg):

    # Initialize Ui interface
    def __init__(self, parent=None):
        super(MultiCam, self).__init__(parent)
        self.setupUi(self)

        self.__is_open = False  # Camera On Flag
        self.__is_snap = False  # Camera capture flag
        self.__enable_open = True  # Turn on device button enable flag bit
        self.__is_exposure_time = False  # Exposure time enable indicator
        self.__is_gain = False  # Gain enable indicator
        self.index = 0  # Device ID
        self.__number = 0  # Device Number
        self.__exposure_max = 0  # Maximum exposure value
        self.__exposure_min = 0  # Minimum exposure value
        self.__gain_max = 0  # Minimum gain value
        self.__gain_min = 0  # Minimum gain value

        # Update ui
        self.update_ui()

        try:
            # Enumerating cameras
            self.device_manager = gx.DeviceManager()
            self.dev_num, self.dev_info_list = self.device_manager.update_all_device_list()
            if self.dev_num is 0:
                QMessageBox.warning(self, "Warning dialog box",
                                    "No devices listed, please insert the camera and restart the program!")
                self.__enable_open = False

        except Exception as exception:
            QMessageBox.critical(self, "Warning dialog box", "{}".format(exception))
            return

        # Default display of the first camera
        self.device_list_box.itemText(0)

        # The maximum number of devices is 2
        if self.dev_num >= device_num:
            self.__number = device_num
        else:
            self.__number = self.dev_num

        # Add the listed cameras to the drop-down list
        for i in range(self.__number):
            self.device_list_box.addItem(self.dev_info_list[i].get("display_name"))

        # Dropdown box signal slot
        self.device_list_box.currentIndexChanged.connect(self.combo_device_list)

        # Open the camera signal slot
        self.open_device_btn.clicked.connect(self.open_device)

        # Close the camera signal slot
        self.close_device_btn.clicked.connect(self.close_device)

        # Start collecting signal slots
        self.acquisition_start_btn.clicked.connect(self.acquisition_start)

        # Stop collecting signal slots
        self.acquisition_stop_btn.clicked.connect(self.acquisition_stop)

        # Exposure signal slot
        self.exposure_time_edit.editingFinished.connect(self.edit_shutter_value)

        # Gain signal slot
        self.gain_edit.editingFinished.connect(self.edit_gain_value)

    def keyPressEvent(self, QKeyEvent):
        if QKeyEvent.key() == Qt.Key_Return or QKeyEvent.key() == Qt.Key_Enter:
            if self.focusWidget() == self.close_device_btn:
                self.close_device()
            elif self.focusWidget() == self.open_device_btn:
                self.open_device()
            elif self.focusWidget() == self.acquisition_start_btn:
                self.acquisition_start()
            elif self.focusWidget() == self.acquisition_stop_btn:
                self.acquisition_stop()
            elif self.focusWidget() == self.exposure_time_edit:
                self.exposure_time_edit.clearFocus()
            elif self.focusWidget() == self.gain_edit:
                self.gain_edit.clearFocus()
            else:
                return

    def init_ui(self):

        try:
            device = device_process[self.index].cam
            remote_device_feature = device.get_remote_device_feature_control()
            __is_exposure_time = remote_device_feature.is_implemented("ExposureTime")
            __is_gain = remote_device_feature.is_implemented("Gain")
            if __is_exposure_time is True:
                exposure_time_value = remote_device_feature.get_float_feature("ExposureTime").get()
                self.exposure_time_edit.setText(str(exposure_time_value))
                exposure_range = remote_device_feature.get_float_feature("ExposureTime").get_range()
                self.__exposure_max = exposure_range["max"]
                self.__exposure_min = exposure_range["min"]
                self.exposure_range.setText(str(self.__exposure_min) + "~" + str(self.__exposure_max))
                self.__is_exposure_time = True

            if __is_gain is True:
                gain_value = remote_device_feature.get_float_feature("Gain").get()
                self.gain_edit.setText(str(gain_value))
                gain_range = remote_device_feature.get_float_feature("Gain").get_range()
                self.__gain_max = gain_range["max"]
                self.__gain_min = gain_range["min"]
                self.gain_range.setText(str(self.__gain_min) + "~" + str(self.__gain_max))
                self.__is_gain = True

        except Exception as exception:
            QMessageBox.critical(self, "Warning dialog box", "{}".format(exception))
            return

        self.update_ui()

    # Dropdown list update
    def combo_device_list(self):

        self.index = self.device_list_box.currentIndex()

        if device_process[self.index].is_open is True:
            self.__is_open = True
            self.__is_snap = device_process[self.index].is_snap
            self.__enable_open = False
            self.init_ui()
            self.update_ui()
        else:
            self.__is_open = False
            self.__is_snap = device_process[self.index].is_snap
            self.__enable_open = True
            self.update_ui()

    # Open device interface
    def open_device(self):

        # Get the current dropdown index
        self.index = self.device_list_box.currentIndex()
        if self.index < 0:
            print("Please insert the camera")

        # Obtain the selected device SN
        str_sn = self.dev_info_list[self.index].get("sn")

        try:
            # open device
            device_process[self.index].open_device(str_sn)
        except Exception as exception:
            QMessageBox.critical(self, "Warning dialog box", "{}".format(exception))
            return

        self.__is_open = device_process[self.index].get_open_state()
        self.__enable_open = False
        self.init_ui()
        self.update_ui()

    # Close device interface
    def close_device(self):

        try:

            # close device
            device_process[self.index].close_device()

        except Exception as exception:
            QMessageBox.critical(self, "Warning dialog box", "{}".format(exception))
            return

        self.__is_open = device_process[self.index].is_open
        self.__is_snap = device_process[self.index].is_snap
        self.__enable_open = True
        self.update_ui()

    # Start collecting interfaces
    def acquisition_start(self):

        try:
            device_process[self.index].start_sanp()
        except Exception as exception:
            QMessageBox.critical(self, "Warning dialog box", "{}".format(exception))
            return

        self.__is_snap = device_process[self.index].is_snap
        self.update_ui()

    # Stop collection interface
    def acquisition_stop(self):

        try:
            device_process[self.index].stop_snap()
        except Exception as exception:
            QMessageBox.critical(self, "Warning dialog box", "{}".format(exception))
            return

        self.__is_snap = device_process[self.index].is_snap
        self.update_ui()

    def edit_shutter_value(self):

        device = device_process[self.index].cam
        remote_device_feature = device.get_remote_device_feature_control()

        str_exposure_value = self.exposure_time_edit.text()
        exposure_value = float(str_exposure_value)
        if exposure_value <= self.__exposure_min:
            exposure_value = self.__exposure_min
        elif exposure_value >= self.__exposure_max:
            exposure_value = self.__exposure_max

        remote_device_feature.get_float_feature("ExposureTime").set(exposure_value)
        self.exposure_time_edit.setText(str(exposure_value))

    def edit_gain_value(self):

        device = device_process[self.index].cam
        remote_device_feature = device.get_remote_device_feature_control()

        str_gain = self.gain_edit.text()
        gain_value = float(str_gain)
        if gain_value <= self.__gain_min:
            gain_value = self.__gain_min
        elif gain_value >= self.__gain_max:
            gain_value = self.__gain_max

        remote_device_feature.get_float_feature("Gain").set(gain_value)
        self.gain_edit.setText(str(gain_value))

    def update_ui(self):
        self.exposure_time_edit.setEnabled(self.__is_open and self.__is_exposure_time)
        self.gain_edit.setEnabled(self.__is_open and self.__is_gain)
        self.open_device_btn.setEnabled(self.__enable_open)
        self.close_device_btn.setEnabled(not (self.__enable_open))
        self.acquisition_start_btn.setEnabled(self.__is_open and not (self.__is_snap))
        self.acquisition_stop_btn.setEnabled(self.__is_open and self.__is_snap)

    def closeEvent(self, event):
        for i in range(self.__number):
            if device_process[i].is_open is False:
                continue
            if device_process[i].is_snap is True:

                thread_flag[i] = 0
                thread_cam[i].quit()

                # Stop collection
                device_process[i].cam.stream_off()

                # close device
                device_process[i].cam.close_device()
            else:
                # close device
                device_process[i].cam.close_device()


class DeviceProcess():

    # Initialize Ui interface
    def __init__(self):
        super(DeviceProcess, self).__init__()

        self.is_open = False  # Camera On Flag
        self.is_snap = False  # Camera capture flag

    def get_open_state(self):
        return self.is_open

    def get_snap_state(self):
        return self.is_snap

    def open_device(self, str_device_sn):

        self.device_manager = gx.DeviceManager()
        self.image_convert = self.device_manager.create_image_format_convert()

        # Open the currently selected device
        self.cam = self.device_manager.open_device_by_sn(str_device_sn)

        if main_window.index == 0:
            thread_cam[0] = image_thread_up()
        else:
            thread_cam[1] = image_thread_down()

        self.is_open = True

    def close_device(self):
        if self.is_snap is True:

            thread_flag[main_window.index] = 0
            thread_cam[main_window.index].quit()

            time.sleep(0.1)

            # Stop collection
            device_process[main_window.index].cam.stream_off()

            # close device
            device_process[main_window.index].cam.close_device()
        else:
            # close device
            device_process[main_window.index].cam.close_device()
        self.is_snap = False
        self.is_open = False

    def start_sanp(self):

        # Start collecting
        device_process[main_window.index].cam.stream_on()
        thread_flag[main_window.index] = 1
        thread_cam[main_window.index].start()

        self.is_snap = True

    def stop_snap(self):

        thread_flag[main_window.index] = 0
        thread_cam[main_window.index].terminate()
        device_process[main_window.index].cam.stream_off()

        self.is_snap = False


def get_best_valid_bits(pixel_format):
    valid_bits = DxValidBit.BIT0_7
    if pixel_format in (GxPixelFormatEntry.MONO8,
                        GxPixelFormatEntry.BAYER_GR8, GxPixelFormatEntry.BAYER_RG8,
                        GxPixelFormatEntry.BAYER_GB8, GxPixelFormatEntry.BAYER_BG8,
                        GxPixelFormatEntry.RGB8, GxPixelFormatEntry.BGR8,
                        GxPixelFormatEntry.R8, GxPixelFormatEntry.B8, GxPixelFormatEntry.G8):
        valid_bits = DxValidBit.BIT0_7
    elif pixel_format in (GxPixelFormatEntry.MONO10, GxPixelFormatEntry.MONO10_PACKED, GxPixelFormatEntry.MONO10_P,
                          GxPixelFormatEntry.BAYER_GR10, GxPixelFormatEntry.BAYER_RG10,
                          GxPixelFormatEntry.BAYER_GB10, GxPixelFormatEntry.BAYER_BG10,
                          GxPixelFormatEntry.BAYER_GR10_P, GxPixelFormatEntry.BAYER_RG10_P,
                          GxPixelFormatEntry.BAYER_GB10_P, GxPixelFormatEntry.BAYER_BG10_P,
                          GxPixelFormatEntry.BAYER_GR10_PACKED, GxPixelFormatEntry.BAYER_RG10_PACKED,
                          GxPixelFormatEntry.BAYER_GB10_PACKED, GxPixelFormatEntry.BAYER_BG10_PACKED):
        valid_bits = DxValidBit.BIT2_9
    elif pixel_format in (GxPixelFormatEntry.MONO12, GxPixelFormatEntry.MONO12_PACKED, GxPixelFormatEntry.MONO12_P,
                          GxPixelFormatEntry.BAYER_GR12, GxPixelFormatEntry.BAYER_RG12,
                          GxPixelFormatEntry.BAYER_GB12, GxPixelFormatEntry.BAYER_BG12,
                          GxPixelFormatEntry.BAYER_GR12_P, GxPixelFormatEntry.BAYER_RG12_P,
                          GxPixelFormatEntry.BAYER_GB12_P, GxPixelFormatEntry.BAYER_BG12_P,
                          GxPixelFormatEntry.BAYER_GR12_PACKED, GxPixelFormatEntry.BAYER_RG12_PACKED,
                          GxPixelFormatEntry.BAYER_GB12_PACKED, GxPixelFormatEntry.BAYER_BG12_PACKED):
        valid_bits = DxValidBit.BIT4_11
    elif pixel_format in (GxPixelFormatEntry.MONO14, GxPixelFormatEntry.MONO14_P,
                          GxPixelFormatEntry.BAYER_GR14, GxPixelFormatEntry.BAYER_RG14,
                          GxPixelFormatEntry.BAYER_GB14, GxPixelFormatEntry.BAYER_BG14,
                          GxPixelFormatEntry.BAYER_GR14_P, GxPixelFormatEntry.BAYER_RG14_P,
                          GxPixelFormatEntry.BAYER_GB14_P, GxPixelFormatEntry.BAYER_BG14_P,
                          ):
        valid_bits = DxValidBit.BIT6_13
    elif pixel_format in (GxPixelFormatEntry.MONO16,
                          GxPixelFormatEntry.BAYER_GR16, GxPixelFormatEntry.BAYER_RG16,
                          GxPixelFormatEntry.BAYER_GB16, GxPixelFormatEntry.BAYER_BG16):
        valid_bits = DxValidBit.BIT8_15
    return valid_bits


def convert_to_RGB(image_convert, raw_image):
    image_convert.set_dest_format(GxPixelFormatEntry.RGB8)
    valid_bits = get_best_valid_bits(raw_image.get_pixel_format())
    image_convert.set_valid_bits(valid_bits)

    # create out put image buffer
    buffer_out_size = image_convert.get_buffer_size_for_conversion(raw_image)
    output_image_array = (c_ubyte * buffer_out_size)()
    output_image = addressof(output_image_array)

    # convert to rgb
    image_convert.convert(raw_image, output_image, buffer_out_size, False)
    if output_image is None:
        print('Failed to convert RawImage to RGBImage')
        return

    return output_image_array, buffer_out_size


class image_thread_up(QThread):

    def __init__(self):
        super(image_thread_up, self).__init__()
        thread_flag[0] = 0  # Control thread exit

    def run(self):  # Just call this interface directly when using this class
        while thread_flag[0]:
            raw_image = device_process[0].cam.data_stream[0].get_image()
            if raw_image is None:
                continue

            # Converted pixel format
            if raw_image.get_pixel_format() != GxPixelFormatEntry.RGB8:
                rgb_image_array, rgb_image_buffer_length = convert_to_RGB(device_process[0].image_convert, raw_image)
                if rgb_image_array is None:
                    return

                # create numpy array with data from rgb image
                numpy_image = numpy.frombuffer(rgb_image_array, dtype=numpy.ubyte, count=rgb_image_buffer_length). \
                    reshape(raw_image.frame_data.height, raw_image.frame_data.width, 3)
                if numpy_image is None:
                    print('Failed to get numpy array from RGBImage')
                    return
            else:
                # create numpy array with data from rgb image
                numpy_image = raw_image.get_numpy_array()
                if numpy_image is None:
                    print('Failed to get numpy array from RGBImage')
                    return

            temp_imgSrc = QImage(numpy_image, numpy_image.shape[1], numpy_image.shape[0],
                                 numpy_image.shape[1] * 3, QImage.Format_RGB888)

            # Get the size of the interface space Label
            label_size = main_window.show_image_up.size()

            # display image
            main_window.show_image_up.setPixmap(QPixmap.fromImage(temp_imgSrc).scaled(label_size))

            time.sleep(0.001)


class image_thread_down(QThread):

    def __init__(self):
        super(image_thread_down, self).__init__()
        thread_flag[1] = 0  # Control thread exit

    def run(self):  # Just call this interface directly when using this class
        while thread_flag[1]:
            raw_image = device_process[1].cam.data_stream[0].get_image()
            if raw_image is None:
                continue

            # Converted pixel format
            if raw_image.get_pixel_format() != GxPixelFormatEntry.RGB8:
                rgb_image_array, rgb_image_buffer_length = convert_to_RGB(device_process[1].image_convert, raw_image)
                if rgb_image_array is None:
                    return

                # create numpy array with data from rgb image
                numpy_image = numpy.frombuffer(rgb_image_array, dtype=numpy.ubyte, count=rgb_image_buffer_length). \
                    reshape(raw_image.frame_data.height, raw_image.frame_data.width, 3)
                if numpy_image is None:
                    print('Failed to get numpy array from RGBImage')
                    return
            else:
                # create numpy array with data from rgb image
                numpy_image = raw_image.get_numpy_array()
                if numpy_image is None:
                    print('Failed to get numpy array from RGBImage')
                    return

            temp_imgSrc = QImage(numpy_image, numpy_image.shape[1], numpy_image.shape[0],
                                 numpy_image.shape[1] * 3, QImage.Format_RGB888)

            # Get the size of the interface space Label
            label_size = main_window.show_image_down.size()

            # display image
            main_window.show_image_down.setPixmap(QPixmap.fromImage(temp_imgSrc).scaled(label_size))

            time.sleep(0.001)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = MultiCam()
    device_process = [DeviceProcess() for i in range(2)]
    main_window.setFixedSize(850, 810)
    QShortcut(QKeySequence('Esc', ), main_window, main_window.close)
    main_window.show()
    sys.exit(app.exec_())
