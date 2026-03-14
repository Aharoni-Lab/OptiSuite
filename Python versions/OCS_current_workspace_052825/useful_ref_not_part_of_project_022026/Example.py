import clr
clr.AddReference("System.Windows.Forms")
import sys
import os
import System
from System.Windows.Forms import Application, Form, Label, Button,TextBox

#note: installed python 3.11 on lab computer

file_path = None  # This will hold the actual loaded path

try:
    cwd_path = os.path.join(os.getcwd(), 'SC3U.dll')
    if not os.path.exists(cwd_path):
        raise FileNotFoundError(f"SC3U.dll not found in CWD: {cwd_path}")
    clr.AddReference(os.path.abspath(cwd_path))
    file_path = cwd_path
    print(f"Loaded SC3U.dll from: {cwd_path}")

except Exception as e:
    print(f"Failed to load from CWD: {e}")
    #hardcoded backup path, version Melody laptop
    #fallback_path = r"C:\Users\Melody\Documents\Melody School\UCLA\OCS Research\Python versions\OCS_op_new_052825\SC3U.dll"
    
    #hardcoded backup path, version current laptop
    fallback_path = r"C:\Users\stimscope1\Documents\OptiSuite"
    
    if not os.path.exists(fallback_path):
        raise FileNotFoundError(f"SC3U.dll not found at fallback path: {fallback_path}")
    clr.AddReference(os.path.abspath(fallback_path))
    file_path = fallback_path
    print(f"Loaded SC3U.dll from fallback path: {fallback_path}")

from SC3Us import SC3U

class MyForm(Form):
    def __init__(self):
        super().__init__()

        #experimental: removed al the self. txt int his section, blank window opened up 
        # (no gui) when the program was ran
        
        self.Text="Python with C# Control"
        self.Width=1000
        self.Height=450

        self.my_control=SC3U()
        self.lblStatus=Label()
        self.btnConnect = Button()
        self.btnSetParam= Button()
        self.lblInfo=Label()
        self.TxtPosition=TextBox()
        self.btnRun= Button()

        self.Controls.Add(self.my_control)
        self.Controls.Add(self.lblStatus)
        self.Controls.Add(self.btnConnect)
        self.Controls.Add(self.btnSetParam)
        self.Controls.Add(self.lblInfo)
        self.Controls.Add(self.TxtPosition)
        self.Controls.Add(self.btnRun)
        
        self.my_control.Left=10
        self.my_control.Top=10
        self.my_control.Width=606
        self.my_control.Height=366

        self.lblStatus.Left=630
        self.lblStatus.Top=10
        self.lblStatus.Height=20
        self.lblStatus.Text="Connection Status:"
        
        self.btnConnect.Left=630
        self.btnConnect.Top=40
        self.btnConnect.Height=30
        self.btnConnect.Text="Connect"
        self.btnConnect.Click += self.on_btnConnect_click

        self.btnSetParam.Left=630
        self.btnSetParam.Top=80
        self.btnSetParam.Height=30
        self.btnSetParam.Text="Parameter Settings"
        self.btnSetParam.Click += self.on_btnSetParam_click

        self.lblInfo.Left=630
        self.lblInfo.Top=120
        self.lblInfo.Height=20
        self.lblInfo.Text="Move to Position:"
        
        self.TxtPosition.Left=630
        self.TxtPosition.Top=140
        self.TxtPosition.Height=30
        
        self.btnRun.Left=630
        self.btnRun.Top=170
        self.btnRun.Height=30
        self.btnRun.Text="Run"
        self.btnRun.Click += self.on_btnRun_click
        

    def on_btnConnect_click(self, sender, event):
        print("Connect button was clicked")
        # The handling method for the button click event
        file_path = os.path.join(os.getcwd(), 'SC3U.dll')
        #print(file_path)
        
        #NOTE TO SELF: THE LEFT PORT ON YOUR COMPUTER IS COM6, THE RIGHT IS COM3
        #check port if on a different device
        self.my_control.ConnectPort(4) 

        self.lblStatus.Text="Connection Status"+str(self.my_control.ConnectStatus)

    #parameter setting button which does not set anything/pull up the parameter setting window
    #need to hit connect to do that 
    def on_btnSetParam_click(self, sender, event):
        if self.my_control.ConnectStatus==True:
            print("Set parameters button was clicked")
            # self.my_control.SetType(0, 1)                                      # Set parameters for linear stage
            # self.my_control.SetUnit(0, 0)                                       # Set mm as the unit
            # self.my_control.SetMotorAngle(0, 0.9)                       # Set the motor angle to 1.8
            # self.my_control.SetSubsection(0, 2)                           # Set the subdivision to 2
            # self.my_control.SetPitch(0, 1)                                     # Set the screw pitch to 1
            # self.my_control.SetTravel(0, 50)                                 # Set the travel range to 50
            # self.my_control.SaveParam(0)                                   # Save the parameters
            
    def on_btnRun_click(self, sender, event):
        if self.my_control.ConnectStatus==True:
            print("Run button was clicked")
            self.my_control.RunToPosition(0,float(self.TxtPosition.Text)-self.my_control.GetCurrentPosition(0))

if __name__=="__main__":
    form=MyForm()
    Application.Run(form)
