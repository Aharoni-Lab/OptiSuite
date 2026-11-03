# version:1.0.2403.9191
import sys
import ImageProcessDlg
import gxipy as gx
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import QDateTime
import cv2
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import Qt
from PyQt5.QtCore import *
from gxipy.gxidef import *
from ctypes import *
import numpy
from gxipy.dxwrapper import *
from gxipy.ImageProc import Utility


class ImageProcess(QMainWindow, ImageProcessDlg.Ui_ImageProcessDlg):

    # Initialize Ui interface
    def __init__(self, parent=None):
        super(ImageProcess, self).__init__(parent)
        self.setupUi(self)

        self.__is_open = False  # Camera On Flag
        self.__is_snap = False  # Camera capture flag
        self.__color_filter = False  # Is it a color camera logo
        self.__enable_open = False  # Turn on device button enable flag bit
        self.__is_open_cc = True  # Is the color correction checkbox selected for identification
        self.__color_correction = False  # Indicate whether color correction is supported
        self.__is_trigger_mode = False  # Trigger mode enable indicator
        self.__is_trigger_source = False  # Trigger source enable indicator
        self.__is_exposure_time = False  # Exposure time enable indicator
        self.__is_gain = False  # Gain enable indicator
        self.__enable_color_correct = False  # Whether the identification device has enabled color correction
        self.save_image_enable = False  # Save Image Enable Flag
        self.__enable_gamma = False  # Gamma enable flag
        self.__enable_sharpness = False  # Sharpen slider enable flag
        self.is_sharpness = False  # Sharpening switch
        self.__get_color_correction = 0  # Color correction value
        self.__color_correction = 0  # Color correction value
        self.sharpen_value = 0.1  # Sharpness current value
        self.__contrast_value = 0  # Current value of contrast
        self.lightness_value = 0  # Current brightness value
        self.__gamma_value = 1  # Gamma current value
        self.__gamma_lut = None  # Gamma_lut
        self.__contrast_lut = None  # Contrast lut
        self.__exposure_max = 0  # Maximum exposure value
        self.__exposure_min = 0  # Minimum exposure value
        self.__gain_max = 0  # Minimum gain value
        self.__gain_min = 0  # Minimum gain value

        try:
            # Enumerating cameras
            self.device_manager = gx.DeviceManager()
            self.dev_num, self.dev_info_list = self.device_manager.update_all_device_list()
            if self.dev_num is 0:
                QMessageBox.warning(self, "Warning dialog box",
                                    "No devices listed, please insert the camera and restart the program!")
                self.__enable_open = False

                # Update interface
                self.update_ui()
                return
            else:
                self.__enable_open = True

                # Update interface
                self.update_ui()

        except Exception as exception:
            QMessageBox.critical(self, "Warning dialog box", "{}".format(exception))
            return

        # Default display of the first camera
        self.device_list_box.itemText(0)

        # Add the listed cameras to the drop-down list
        for i in range(self.dev_num):
            self.device_list_box.addItem(self.dev_info_list[i].get("display_name"))

        # Open the camera signal slot
        self.open_device_btn.clicked.connect(self.open_device)

        # Close the camera signal slot
        self.close_device_btn.clicked.connect(self.close_device)

        # Start collecting signal slots
        self.acquisition_start_btn.clicked.connect(self.acquisition_start)

        # Stop collecting signal slots
        self.acquisition_stop_btn.clicked.connect(self.acquisition_stop)

        # Trigger mode signal slot
        self.trigger_mode_box.currentIndexChanged.connect(self.combo_trigger_mode)

        # Trigger source signal slot
        self.trigger_source_box.currentIndexChanged.connect(self.combo_trigger_source)

        # Soft trigger signal slot
        self.trigger_software_btn.clicked.connect(self.soft_trigger)

        # Color correction signal slot
        self.color_box.stateChanged.connect(self.device_color_correct)

        # Save image signal slot
        self.save_img_btn.clicked.connect(self.save_image)

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
            elif self.focusWidget() == self.trigger_software_btn:
                self.soft_trigger()
            elif self.focusWidget() == self.save_img_btn:
                self.save_image()
            elif self.focusWidget() == self.exposure_time_edit:
                self.exposure_time_edit.clearFocus()
            elif self.focusWidget() == self.gain_edit:
                self.gain_edit.clearFocus()
            else:
                return

    def init_ui(self):

        try:
            pixel_format_value, pixel_format_str = self.remote_device_feature.get_enum_feature("PixelFormat").get()
            if Utility.is_gray(pixel_format_value):
                # camera is mono camera
                self.__color_filter = False
            else:
                # camera is color camera
                self.__color_filter = True

            if self.remote_device_feature.is_implemented("TriggerMode") is True:
                trigger_mode_list = {}
                mode_list = self.remote_device_feature.get_enum_feature("TriggerMode").get_range()
                for mode_dict in mode_list:
                    trigger_mode_list[mode_dict['symbolic']] = mode_dict['value']
                if self.trigger_mode_box.count() == 0:
                    self.trigger_mode_box.addItems(trigger_mode_list)
                    self.__is_trigger_mode = True
            else:
                QMessageBox.warning(self, "Warning dialog box", "Compared to support TriggerMode")

            if self.remote_device_feature.is_implemented("TriggerSource") is True:
                trigger_source_list = {}
                trigger_list = self.remote_device_feature.get_enum_feature("TriggerSource").get_range()
                for trigger_dict in trigger_list:
                    trigger_source_list[trigger_dict['symbolic']] = trigger_dict['value']

                if self.trigger_source_box.count() == 0:
                    self.trigger_source_box.addItems(trigger_source_list)
                    self.__is_trigger_source = True
            else:
                QMessageBox.warning(self, "Warning dialog box", "Compared to support TriggerSource")

            if self.remote_device_feature.is_implemented("ExposureTime") is True:
                exposure_time_value = self.remote_device_feature.get_float_feature("ExposureTime").get()
                self.exposure_time_edit.setText(str(exposure_time_value))
                exposure_range = self.remote_device_feature.get_float_feature("ExposureTime").get_range()
                self.__exposure_max = exposure_range["max"]
                self.__exposure_min = exposure_range["min"]
                self.exposure_range.setText(str(self.__exposure_min) + "~" + str(self.__exposure_max))
                self.__is_exposure_time = True
            else:
                QMessageBox.warning(self, "Warning dialog box", "Compared to support ExposureTime")

            if self.remote_device_feature.is_implemented("Gain") is True:
                gain_value = self.remote_device_feature.get_float_feature("Gain").get()
                self.gain_edit.setText(str(gain_value))
                gain_range = self.remote_device_feature.get_float_feature("Gain").get_range()
                self.__gain_max = gain_range["max"]
                self.__gain_min = gain_range["min"]
                self.gain_range.setText(str(self.__gain_min) + "~" + str(self.__gain_max))
                self.__is_gain = True
            else:
                QMessageBox.warning(self, "Warning dialog box", "Compared to support Gain")

            if self.__color_filter is True:
                if self.remote_device_feature.is_implemented("ColorTransformationEnable") is True and \
                        self.remote_device_feature.is_readable("ColorTransformationEnable") is True:
                    self.__enable_color_correct = self.remote_device_feature.get_bool_feature(
                        "ColorTransformationEnable").get()
                if self.remote_device_feature.is_implemented("ColorCorrectionParam") is True and \
                        self.remote_device_feature.is_readable("ColorCorrectionParam") is True:
                    self.__get_color_correction = self.remote_device_feature.get_int_feature(
                        "ColorCorrectionParam").get()
                    self.__color_correction = True
                else:
                    self.__color_correction = False
            else:
                self.__enable_color_correct = False
                self.__color_correction = False
                self.__get_color_correction = 0
                self.__color_correction = 0

            if self.remote_device_feature.is_implemented("GammaEnable") is True:
                self.__enable_gamma = self.remote_device_feature.get_bool_feature("GammaEnable").get()
            if self.remote_device_feature.is_implemented("GammaParam") is True:
                self.__gamma_value = 1
            else:
                QMessageBox.warning(self, "Warning dialog box", "Compared to support GammaParam")

            if self.remote_device_feature.is_implemented("SharpnessMode") is True:
                __sharpness_mode = self.remote_device_feature.get_enum_feature("SharpnessMode").get()
                if __sharpness_mode[0] == 0:
                    self.__enable_sharpness = False
                else:
                    self.__enable_sharpness = True
            else:
                QMessageBox.warning(self, "Warning dialog box", "Compared to support SharpnessMode")

            self.sharpness_slider.setMinimum(1)
            self.sharpness_slider.setMaximum(50)
            self.sharpness_slider.setValue(int(self.sharpen_value * 10))
            self.sharpness_edit.setText(str(self.sharpen_value))

            self.gamma_slider.setMinimum(1)
            self.gamma_slider.setMaximum(100)
            self.gamma_slider.setValue(int(self.__gamma_value * 10))
            self.gamma_edit.setText(str(self.__gamma_value))

            self.contrast_slider.setMinimum(-50)
            self.contrast_slider.setMaximum(100)
            self.contrast_slider.setValue(self.__contrast_value)
            self.contrast_edit.setText(str(self.__contrast_value))

            self.lightness_slider.setMinimum(-150)
            self.lightness_slider.setMaximum(150)
            self.lightness_slider.setValue(self.lightness_value)
            self.lightness_edit.setText(str(self.lightness_value))

            # Sharpen signal slot
            self.sharpness_slider.valueChanged.connect(self.set_sharpness)
            self.sharpness_box.stateChanged.connect(self.sharpness_switch)

            # Gamma signal slot
            self.gamma_slider.valueChanged.connect(self.set_gamma)

            # Contrast signal slot
            self.contrast_slider.valueChanged.connect(self.set_contrast)

            # Brightness signal slot
            self.lightness_slider.valueChanged.connect(self.set_lightness)

        except Exception as exception:
            QMessageBox.critical(self, "Warning dialog box", "{}".format(exception))
            return

        # Update interface
        self.update_ui()

    # Open device interface
    def open_device(self):

        try:
            # Get the current dropdown index
            index = self.device_list_box.currentIndex()
            if index < 0:
                QMessageBox.critical(self, "Warning dialog box", "Please insert the camera")
                return

            # Obtain the selected device SN
            str_sn = self.dev_info_list[index].get("sn")
            if str_sn == "":
                QMessageBox.critical(self, "Warning dialog box", "Failed to obtain device SN")
                return

            # Open the currently selected device
            self.cam = self.device_manager.open_device_by_sn(str_sn)
        except Exception as exception:
            QMessageBox.critical(self, "Warning dialog box", "{}".format(exception))
            return

        self.remote_device_feature = self.cam.get_remote_device_feature_control()
        self.image_process_config = self.cam.create_image_process_config()

        self.image_format_convert = self.device_manager.create_image_format_convert()
        self.image_process = self.device_manager.create_image_process()

        self.__is_open = True
        self.__enable_open = False
        self.init_ui()
        self.update_ui()
        self.image_process_config.set_gamma_param(self.__gamma_value)
        self.image_process_config.set_contrast_param(self.__contrast_value)
        self.image_process_config.enable_color_correction(False)

    # Close device interface
    def close_device(self):

        try:
            # If the camera is in mining mode
            if self.__is_snap == True:
                # Stop collection
                self.cam.stream_off()

            # Unregister capture callback
            self.cam.data_stream[0].unregister_capture_callback()

            # close device
            self.cam.close_device()
        except Exception as exception:
            QMessageBox.critical(self, "Warning dialog box", "{}".format(exception))
            return

        self.__is_open = False
        self.__is_snap = False
        self.__enable_open = True
        self.update_ui()

    # Start collecting interfaces
    def acquisition_start(self):

        try:
            # Register capture callback (Notice: Linux USB2 SDK does not support register_capture_callback)
            self.cam.data_stream[0].register_capture_callback(capture_callback)

            # Start collecting
            self.cam.stream_on()
        except Exception as exception:
            QMessageBox.critical(self, "Warning dialog box", "{}".format(exception))
            return

        self.__is_snap = True
        self.update_ui()

    # Stop collection interface
    def acquisition_stop(self):

        try:
            # Stop collection
            self.cam.stream_off()

            # Unregister capture callback
            self.cam.data_stream[0].unregister_capture_callback()

        except Exception as exception:
            QMessageBox.critical(self, "Warning dialog box", "{}".format(exception))
            return
        self.__is_snap = False
        self.update_ui()

    def edit_shutter_value(self):
        str_exposure_time = self.exposure_time_edit.text()
        exposure_time_value = float(str_exposure_time)

        if exposure_time_value <= self.__exposure_min:
            exposure_time_value = self.__exposure_min
        elif exposure_time_value >= self.__exposure_max:
            exposure_time_value = self.__exposure_max

        self.remote_device_feature.get_float_feature("ExposureTime").set(exposure_time_value)
        self.exposure_time_edit.setText(str(exposure_time_value))

    def edit_gain_value(self):
        str_gain_value = self.gain_edit.text()
        gain_value = float(str_gain_value)

        if gain_value <= self.__gain_min:
            gain_value = self.__gain_min
        elif gain_value >= self.__gain_max:
            gain_value = self.__gain_max

        self.remote_device_feature.get_float_feature("Gain").set(gain_value)
        self.gain_edit.setText(str(gain_value))

    def combo_trigger_source(self):

        try:
            if self.remote_device_feature.is_implemented("TriggerSource") is True:
                trigger_source_value = self.trigger_source_box.currentIndex()
                self.remote_device_feature.get_enum_feature("TriggerSource").set(trigger_source_value)
        except Exception as exception:
            QMessageBox.critical(self, "Warning dialog box", "{}".format(exception))
            return

    def soft_trigger(self):

        try:
            trigger_software_command_feature = self.remote_device_feature.get_command_feature("TriggerSoftware")
            trigger_software_command_feature.send_command()
        except Exception as exception:
            QMessageBox.critical(self, "Warning dialog box", "{}".format(exception))
            return

    def combo_trigger_mode(self):

        try:
            if self.remote_device_feature.is_implemented("TriggerMode") is True:
                trigger_mode_value = self.trigger_mode_box.currentIndex()
                self.remote_device_feature.get_enum_feature("TriggerMode").set(trigger_mode_value)

                self.update_ui()
        except Exception as exception:
            QMessageBox.critical(self, "Warning dialog box", "{}".format(exception))
            return

    def save_image(self):
        self.time = QDateTime.currentDateTime()
        self.time_display = self.time.toString('yyyy_MM_dd_hh_mm_ss')
        self.image_filename = 'BMP_' + self.time_display + '.bmp'
        self.save_image_enable = True
        self.update_ui()

    def device_color_correct(self):
        if self.color_box.isChecked():
            self.__color_correction = self.__get_color_correction
            self.__is_open_cc = True
        else:
            self.__color_correction = 0
            self.__is_open_cc = False
        self.image_process_config.enable_color_correction(self.__is_open_cc)
        self.update_ui()

    def sharpness_switch(self):
        if self.sharpness_box.isChecked():
            self.is_sharpness = True
        else:
            self.is_sharpness = False
        self.update_ui()

    # sharpening
    def set_sharpness(self):
        size = self.sharpness_slider.value()
        self.sharpness_edit.setText(str(size / 10))
        self.sharpen_value = size / 10

    # Gamma
    def set_gamma(self):
        size = self.gamma_slider.value()
        self.gamma_edit.setText(str(size / 10))
        self.__gamma_value = size / 10
        main_window.image_process_config.set_gamma_param(self.__gamma_value)

    # contrast ratio
    def set_contrast(self):
        size = self.contrast_slider.value()
        self.contrast_edit.setText(str(size))
        self.__contrast_value = size
        main_window.image_process_config.set_contrast_param(self.__contrast_value)

    # brightness
    def set_lightness(self):
        size = self.lightness_slider.value()
        self.lightness_edit.setText(str(size))
        self.lightness_value = size

    def closeEvent(self, event):
        # If the camera is in mining mode
        if self.__is_snap == True:
            # Stop collection
            self.cam.stream_off()

            # Unregister capture callback
            self.cam.data_stream[0].unregister_capture_callback()

        if self.__is_open == True:
            # close device
            self.cam.close_device()

    def update_ui(self):
        self.open_device_btn.setEnabled(self.__enable_open)
        self.close_device_btn.setEnabled(self.__is_open)
        self.acquisition_start_btn.setEnabled(self.__is_open and not (self.__is_snap))
        self.acquisition_stop_btn.setEnabled(self.__is_open and self.__is_snap)
        self.exposure_time_edit.setEnabled(self.__is_open and self.__is_exposure_time)
        self.gain_edit.setEnabled(self.__is_open and self.__is_gain)
        self.trigger_mode_box.setEnabled(self.__is_open and self.__is_trigger_mode)
        self.trigger_source_box.setEnabled(self.__is_open and self.__is_trigger_source)
        self.device_list_box.setEnabled(not (self.__is_open) and self.__enable_open)

        if self.trigger_mode_box.currentIndex() == 1:
            trigger_software_btn_enable = True
        else:
            trigger_software_btn_enable = False
        self.trigger_software_btn.setEnabled(self.__is_open and self.__is_snap and trigger_software_btn_enable)
        self.color_box.setEnabled(
            self.__is_open and self.__color_correction and not (self.__enable_color_correct) and self.__color_filter)
        self.save_img_btn.setEnabled(self.__is_snap)
        self.sharpness_slider.setEnabled(self.__is_open and self.is_sharpness and not (self.__enable_sharpness))
        self.gamma_slider.setEnabled(self.__is_open and not (self.__enable_gamma))
        self.contrast_slider.setEnabled(self.__is_open)
        self.lightness_slider.setEnabled(self.__is_open)
        self.sharpness_box.setEnabled(self.__is_open and not (self.__enable_sharpness))


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


# Collection callback function
def capture_callback(raw_image):
    # Adjust sharpness
    if main_window.is_sharpness is True:
        main_window.image_process_config.enable_sharpen(True)
        main_window.image_process_config.set_sharpen_param(main_window.sharpen_value)

    # Adjust brightness
    main_window.image_process_config.set_lightness_param(main_window.lightness_value)
    main_window.image_process_config.set_valid_bits(get_best_valid_bits(raw_image.frame_data.pixel_format))

    # Image quality improvement
    if Utility.is_gray(raw_image.frame_data.pixel_format):
        rgb_image_array = (c_ubyte * raw_image.frame_data.height * raw_image.frame_data.width)()
        rgb_image_array_address = addressof(rgb_image_array)
    else:
        rgb_image_array = (c_ubyte * raw_image.frame_data.height * raw_image.frame_data.width * 3)()
        rgb_image_array_address = addressof(rgb_image_array)

    main_window.image_process.image_improvement(raw_image, rgb_image_array_address, main_window.image_process_config)

    if Utility.is_gray(raw_image.frame_data.pixel_format):
        numpy_image = numpy.frombuffer(rgb_image_array, dtype=numpy.ubyte,
                                       count=raw_image.frame_data.width * raw_image.frame_data.height).reshape(
            raw_image.frame_data.height, raw_image.frame_data.width)

        if numpy_image is None:
            print('Failed to get numpy array from MONO Image')
            return

        temp_imgSrc = QImage(numpy_image, raw_image.frame_data.width, raw_image.frame_data.height,
                             QImage.Format_Grayscale8)

        if main_window.save_image_enable is True:
            cv2.imwrite(main_window.image_filename, numpy_image)
            main_window.save_image_enable = False
    else:
        numpy_image = numpy.frombuffer(rgb_image_array, dtype=numpy.ubyte,
                                       count=raw_image.frame_data.width * raw_image.frame_data.height * 3).reshape(
            raw_image.frame_data.height, raw_image.frame_data.width, 3)

        if numpy_image is None:
            print('Failed to get numpy array from RGBImage')
            return

        temp_imgSrc = QImage(numpy_image, numpy_image.shape[1], numpy_image.shape[0],
                             numpy_image.shape[1] * 3, QImage.Format_RGB888)

        if main_window.save_image_enable is True:
            cv2.imwrite(main_window.image_filename, cv2.cvtColor(numpy_image, cv2.COLOR_BGR2RGB))
            main_window.save_image_enable = False

    # Get the size of the interface space Label
    label_size = main_window.show_image.size()

    # display image
    main_window.show_image.setPixmap(QPixmap.fromImage(temp_imgSrc).scaled(label_size))


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = ImageProcess()
    main_window.setFixedSize(977, 710)
    QShortcut(QKeySequence('Esc', ), main_window, main_window.close)
    main_window.show()
    sys.exit(app.exec_())
