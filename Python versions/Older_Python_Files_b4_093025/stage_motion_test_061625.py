import os
import clr

# Load SC3U.dll
try:
    dll_path = os.path.join(os.getcwd(), "SC3U.dll")
    clr.AddReference(os.path.abspath(dll_path))
    print("Loaded SC3U.dll from current dir")
except Exception:
    fallback_path = r"C:\Users\Melody\Documents\Melody School\UCLA\OCS Research\Python versions\OCS_op_new_052825\SC3U.dll"
    try:
        clr.AddReference(os.path.abspath(fallback_path))
        print("Loaded SC3U.dll from fallback path")
    except Exception as e:
        print(f"Failed to load DLL: {e}")
        raise

from SC3Us import SC3U

def test_stage_control():
    control = SC3U()
    
    try:
        # Port number may vary (COM4 = 3)
        port_num = 3
        control.ConnectPort(port_num)
        
        if not control.ConnectStatus:
            print("Failed to connect to stage.")
            return

        print("Stage connected.")
        
        # Required motor params — must be set to suppress DLL dialog
        for axis in range(3):
            control.SetType(axis, 0)             # 0 = Linear
            control.SetUnit(axis, 0)             # 0 = mm
            control.SetMotorAngle(axis, 1.8)
            control.SetSubsection(axis, 2)       # microstepping
            control.SetPitch(axis, 1.0)          # mm/rev
            control.SetTravel(axis, 100)         # max travel range
            control.SaveParam(axis)

        print("Parameters set successfully.")
        #check x axis values
        for axis in range(1):
            print(f"Axis {axis} Type: {control.GetType(axis)}")
            print(f"Axis {axis} Unit: {control.GetUnit(axis)}")
            print(f"Axis {axis} Motor Angle: {control.GetMotorAngle(axis)}")
            print(f"Axis {axis} Subsection: {control.GetSubsection(axis)}")
            print(f"Axis {axis} Pitch: {control.GetPitch(axis)}")
            print(f"Axis {axis} Travel: {control.GetTravel(axis)}")


        print("Parameters set successfully.")
        import time
        time.sleep(1)  # wait a moment for parameters to settle

        # Refresh positions for all axes to try resetting flags
        for axis in range(3):
            ret = control.RefreshCurrentPosition(axis)
            print(f"RefreshCurrentPosition axis {axis} returned: {ret}")

        # Move axis 0
        print("Moving X axis by +1.0 mm")
        #ret = control.RunToPosition(0, 1.0)
        #print(f"RunToPosition returned: {ret}")

        time.sleep(2)

        # Refresh again after move
        for axis in range(3):
            ret = control.RefreshCurrentPosition(axis)
            print(f"RefreshCurrentPosition axis {axis} returned: {ret}")

        # Read positions
        for axis in range(3):
            pos = control.GetCurrentPosition(axis)
            print(f"Axis {axis} New Position: {pos:.3f}")



    except Exception as e:
        print(f"Error during stage test: {e}")
    finally:
        try:
            control.Disconnect()
            print("Disconnected from stage.")
        except:
            pass

if __name__ == "__main__":
    test_stage_control()
