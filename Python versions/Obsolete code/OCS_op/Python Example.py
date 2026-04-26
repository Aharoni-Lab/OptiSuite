
import clr
import sys
import os

#this thing didn't work
os.environ["SC3U_INI_PATH"] = r"C:\Users\Melody\Documents\Melody School\UCLA\OCS Research\Python versions\OCS_op\34SysParam.ini"

#sys.path.append(r'path_to_directory_containing_dll')

dll_dir = r'C:\Users\Melody\Documents\Melody School\UCLA\OCS Research\Python versions\OCS_op\DLL'
sys.path.append(dll_dir)
#clr.AddReference("C:\\Users\\info\\User_interface_for_alignment\\test\\SC3U.dll")
clr.AddReference(os.path.join(dll_dir, "SC3U.dll"))

#print("Startup Path") 
#print(os.getcwd())

#print("finding python path")
#print(sys.executable)

ini_file_path = r'C:\Users\Melody\Documents\Melody School\UCLA\OCS Research\Python versions\OCS_op\venv\Scripts\34SysParam.ini'

'''
# Check if the INI file exists
if os.path.exists(ini_file_path):
    print(f"INI file found at {ini_file_path}")
else:
    print(f"INI file not found at {ini_file_path}")

#check if INI file is writable
if os.path.exists(ini_file_path):
    file_stats = os.stat(ini_file_path)
    if file_stats.st_mode & stat.S_IWRITE:
        print(f"File is writable: {ini_file_path}")
    else:
        print(f"File is not writable: {ini_file_path}")
else:
    print(f"File does not exist at: {ini_file_path}")
'''

import stat
#check if Python can read it
''' 

import configparser
config = configparser.ConfigParser()

if os.path.exists(ini_file_path):
    print("the file is at")
    print(ini_file_path)
    config.read(ini_file_path)
    try:
        print(config.sections())
        section = "XAxis"
        key = "MotorAngle"
        value = config.get(section, key)
        print(f"Read value: {value}")
    except Exception as e:
        print(f"Error reading from INI: {e}")
else:
    print(f"INI file does not exist at: {ini_file_path}")
'''

#Check if python can write to it

'''
config = configparser.ConfigParser()

# Add a new section if it doesn't exist
if not config.has_section("YourSectionName"):
    config.add_section("YourSectionName")

# Write a value to the INI file
config.set("YourSectionName", "YourKeyName", "YourNewValue")

with open(ini_file_path, 'w') as configfile:
    config.write(configfile)
    print(f"Successfully wrote to {ini_file_path}")'''


from SC3Us import *

'''#quick debugging
print(dir())  # See if SC3U is in the global namespace
print("SC3U class loaded:", hasattr(sys.modules[__name__], "SC3U"))
'''

# Create an instance of MainClass
ini_handler = MainClass()
from SC3Us import MainClass

# Now you can call GetFromIni
print("trying to use getFromIni")
value = ini_handler.GetFromIni("XAxis", "MotorAngle")
print(value)



class StageDriver:
    def __init__(self):
        print(">>> After sC3U1 init")
        self.sC3U1 = SC3U()
        print(">>> Done")

    def test_ini_read(self):
        # Test reading from the INI file (adjust section and key names)
        section = "XAxis"
        key = "MotorAngle"
        ini_handler = MainClass()
        value = ini_handler.GetFromIni(section, key)
        print(f"Read value: {value}")

    def test_ini_write(self):
        # Test writing to the INI file (adjust section, key, and value)
        section = "XAxis"
        key = "MotorAngle"
        value = "100"
        ini_handler = MainClass()
        success = ini_handler.WriteToIni(section, key, value)
        if success:
            print("Successfully wrote to the INI file.")
        else:
            print("Failed to write to the INI file.")

if __name__ == "__main__":
    stage_driver = StageDriver()
    stage_driver.test_ini_read()
    stage_driver.test_ini_write()
'''
class StageDriver:
    def __init__(self):
        print(">>> After sC3U1 init")
        self.sC3U1 = SC3U()
        print(">>> Done")

    def connect(self): 
        self.sC3U1.ConnectPort(3)
        bConnect = self.sC3U1.ConnectStatus

        if bConnect:
            print("[✓] Connected to motion controller on COM3")
        else:
            print("[X] Failed to connect.")

        
    def initStage(self):

        for axis in range(3):  # For X, Y, Z axes
            self.sC3U1.SetType(axis, 1)
            self.sC3U1.SetUnit(axis, 0)
            self.sC3U1.SetMotorAngle(axis, 1.8)
            self.sC3U1.SetSubsection(axis, 8)
            self.sC3U1.SetPitch(axis, 1.0)
            self.sC3U1.SetTravel(axis, 100)
            #need: tranratio, negatravel, positravel, zerooffset too
            self.sC3U1.SaveParam(axis)

            #print stuff out to debug
            motor_type = self.sC3U1.GetType(axis)
            unit = self.sC3U1.GetUnit(axis)
            motor_angle = self.sC3U1.GetMotorAngle(axis)
            subsection = self.sC3U1.GetSubsection(axis)
            pitch = self.sC3U1.GetPitch(axis)
            travel = self.sC3U1.GetTravel(axis)


            print(f"{['X','Y','Z'][axis]} axis")
            print("Step:", self.sC3U1.GetCurrentStep(axis))
            print("Position:", self.sC3U1.GetCurrentPosition(axis))
            print("Speed:", self.sC3U1.GetActualSpeed(axis))


    def close(self):
        self.sC3U1.ClosePort()


if __name__ == "__main__":
    stage_driver = StageDriver()
    stage_driver.connect()
    stage_driver.initStage()
    stage_driver.close()'''