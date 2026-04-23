// SC3U.dll - Key Methods Analysis and Comments
// This is a commented version of the critical methods from SC3U_class.cs

using System;
using System.Windows.Forms;

public class SC3U : UserControl
{
    // ===== CRITICAL PRIVATE VARIABLES =====
    
    // This flag determines if GetCurrentPosition will work!
    private bool BlnParamFlag;  // Must be true for position queries to work
    
    // Current axis selection - managed by private GetCurrAxis() method
    private short ShrCurrAxis;  // 0=X, 1=Y, 2=Z, 3=R, 4=T1, 5=T2
    
    // Parameter arrays for all 6 axes
    private short[] ShrType = new short[6];        // Stage type (0=Linear, 1=Translation, etc.)
    private short[] ShrUnit = new short[6];        // Unit (0=mm, 1=degree, 2=step)
    private float[] FlaMotorAngle = new float[6];  // Motor angle (0.9 or 1.8)
    private short[] ShrSubsection = new short[6];  // Microstepping
    private float[] FlaPitch = new float[6];       // Screw pitch
    private double[] DblTravel = new double[6];    // Travel range
    
    // Position arrays - only updated by RefreshCurrentPosition()
    private long[] LngCurrStep = new long[6];      // Current step position
    private double[] DblCurrPosi = new double[6];  // Current position in units
    private double[] DblPulseEqui = new double[6]; // Pulse equivalent (calculated in SaveParam)
    
    // GUI Controls - These are the problem!
    private ComboBox CboType;        // Type selection ComboBox
    private ComboBox CboUnit;        // Unit selection ComboBox  
    private ComboBox CboMotorAngle;  // Motor angle ComboBox
    private ComboBox CboSubsection;  // Subdivision ComboBox
    private ComboBox CboPitch;       // Pitch ComboBox
    private ComboBox CboTravel;      // Travel ComboBox
    private RadioButton[] RadAxis = new RadioButton[6]; // Axis selection radio buttons

    // ===== PUBLIC METHODS (What you can call) =====
    
    /// <summary>
    /// Gets current position of specified axis
    /// PROBLEM: Returns DblCurrPosi[sIndex] which is only updated by private RefreshCurrentPosition()
    /// </summary>
    public double GetCurrentPosition(short sIndex)
    {
        if (sIndex < 0 || sIndex > 5)
        {
            // Error handling...
            return -1.0;
        }
        // This just returns the stored value - doesn't query the stage!
        return Convert.ToDouble(DblCurrPosi[sIndex].ToString("0.##"));
    }
    
    /// <summary>
    /// Sets stage type for specified axis
    /// PROBLEM: Only updates GUI control if sIndex == ShrCurrAxis
    /// </summary>
    public short SetType(short sIndex, short sType)
    {
        // Update the variable
        ShrType[sIndex] = sType;
        
        // CRITICAL ISSUE: Only updates GUI if it's the current axis
        if (sIndex == ShrCurrAxis)
        {
            CboType.SelectedIndex = ShrType[sIndex];  // Updates GUI control
        }
        return 1;
    }
    
    /// <summary>
    /// Sets unit for specified axis
    /// Same problem as SetType - only updates GUI for current axis
    /// </summary>
    public short SetUnit(short sIndex, short sUnit)
    {
        ShrUnit[sIndex] = sUnit;
        if (sIndex == ShrCurrAxis)
        {
            CboUnit.SelectedIndex = ShrUnit[sIndex];
        }
        return 1;
    }
    
    /// <summary>
    /// Sets motor angle for specified axis
    /// Same GUI dependency issue
    /// </summary>
    public short SetMotorAngle(short sIndex, float fMotorAngle)
    {
        FlaMotorAngle[sIndex] = fMotorAngle;
        if (sIndex == ShrCurrAxis)
        {
            CboMotorAngle.Text = FlaMotorAngle[sIndex].ToString();
        }
        return 1;
    }
    
    /// <summary>
    /// Sets subdivision for specified axis
    /// Same GUI dependency issue
    /// </summary>
    public short SetSubsection(short sIndex, short sSubsection)
    {
        ShrSubsection[sIndex] = sSubsection;
        if (sIndex == ShrCurrAxis)
        {
            CboSubsection.Text = ShrSubsection[sIndex].ToString();
        }
        return 1;
    }
    
    /// <summary>
    /// Sets pitch for specified axis
    /// Same GUI dependency issue
    /// </summary>
    public short SetPitch(short sIndex, float fPitch)
    {
        FlaPitch[sIndex] = fPitch;
        if (sIndex == ShrCurrAxis)
        {
            CboPitch.Text = FlaPitch[sIndex].ToString();
        }
        return 1;
    }
    
    /// <summary>
    /// Sets travel range for specified axis
    /// Same GUI dependency issue
    /// </summary>
    public short SetTravel(short sIndex, double dTravel)
    {
        DblTravel[sIndex] = dTravel;
        if (sIndex == ShrCurrAxis)
        {
            CboTravel.Text = DblTravel[sIndex].ToString();
        }
        return 1;
    }
    
    /// <summary>
    /// CRITICAL METHOD: Saves parameters and calculates pulse equivalents
    /// MAJOR PROBLEM: Reads from GUI ComboBox controls, not from variables!
    /// </summary>
    public short SaveParam(short sIndex)
    {
        try
        {
            // CRITICAL ISSUE: This reads from GUI controls that don't exist in PyQt!
            if (ShrType[sIndex] == 1)  // Linear stage
            {
                // Reads from CboMotorAngle.Text, CboPitch.Text, CboSubsection.Text
                DblPulseEqui[sIndex] = Convert.ToDouble(CboMotorAngle.Text) * 
                                      Convert.ToDouble(CboPitch.Text) / 
                                      (double)(360 * Convert.ToInt16(CboSubsection.Text));
            }
            else if (ShrType[sIndex] == 2 || ShrType[sIndex] == 3)  // Rotary/Goniometer
            {
                // Reads from CboMotorAngle.Text, CboTranRatio.Text, CboSubsection.Text
                DblPulseEqui[sIndex] = Convert.ToDouble(CboMotorAngle.Text) / 
                                      (Convert.ToDouble(CboTranRatio.Text) * 
                                       Convert.ToDouble(CboSubsection.Text));
            }
            else if (ShrType[sIndex] == 4)  // Elevating stage
            {
                // Reads from CboPitch.Text, CboTranRatio.Text, CboMotorAngle.Text, CboSubsection.Text
                DblPulseEqui[sIndex] = Convert.ToDouble(CboPitch.Text) / 
                                      Convert.ToDouble(CboTranRatio.Text) / 
                                      (360.0 / Convert.ToDouble(CboMotorAngle.Text) * 
                                       Convert.ToDouble(CboSubsection.Text));
            }
            else
            {
                DblPulseEqui[sIndex] = -1.0;
            }
            
            // Calculate speed based on pulse equivalent
            if (ShrType[sIndex] != 0)
            {
                if (ShrUnit[sIndex] == 2)  // Step unit
                {
                    DblSpeed[sIndex] = (ShrSpeed + 1) * 22000 / 720;
                }
                else  // mm or degree unit
                {
                    DblSpeed[sIndex] = (double)((ShrSpeed + 1) * 22000) * DblPulseEqui[sIndex] / 720.0;
                }
                RadAxis[sIndex].Enabled = true;  // Enable axis radio button
            }
            else
            {
                RadAxis[sIndex].Enabled = false;  // Disable axis radio button
            }
            
            // Save parameters to INI file
            mMainClass.WriteToIni(StrAxisName[sIndex], "Type", ShrType[sIndex].ToString());
            mMainClass.WriteToIni(StrAxisName[sIndex], "Unit", ShrUnit[sIndex].ToString());
            mMainClass.WriteToIni(StrAxisName[sIndex], "MotorAngle", FlaMotorAngle[sIndex].ToString());
            mMainClass.WriteToIni(StrAxisName[sIndex], "Subsection", ShrSubsection[sIndex].ToString());
            mMainClass.WriteToIni(StrAxisName[sIndex], "Pitch", FlaPitch[sIndex].ToString());
            mMainClass.WriteToIni(StrAxisName[sIndex], "TranRatio", IntTranRatio[sIndex].ToString());
            mMainClass.WriteToIni(StrAxisName[sIndex], "Travel", DblTravel[sIndex].ToString());
            mMainClass.WriteToIni(StrAxisName[sIndex], "NegaTravel", LngNegaTravel[sIndex].ToString());
            mMainClass.WriteToIni(StrAxisName[sIndex], "PosiTravel", LngPosiTravel[sIndex].ToString());
            
            // Check if any axes have parameters set
            short num2 = 0;
            for (short num3 = 0; num3 < 6; num3++)
            {
                if (ShrType[num3] != 0)
                {
                    num2++;
                }
            }
            
            // CRITICAL: Set the parameter flag that GetCurrentPosition needs!
            if (num2 == 0)
            {
                BlnParamFlag = false;  // No parameters set
            }
            else
            {
                BlnParamFlag = true;   // Parameters are set - GetCurrentPosition will work!
            }
            
            // Handle current axis selection
            if (ShrType[sIndex] == 0 && RadAxis[sIndex].Checked)
            {
                // Find first axis with parameters
                short num3;
                for (num3 = 0; num3 < 6; num3++)
                {
                    if (ShrType[num3] != 0)
                    {
                        RadAxis[num3].Checked = true;
                        break;
                    }
                }
                if (num3 == 6)
                {
                    RadAxis[sIndex].Checked = false;
                    RadAxis[0].Checked = true;
                }
            }
            
            GetCurrAxis();           // Update current axis (private method)
            RefreshShow();           // Update display (private method)
            RefreshCurrentPosition(ShrCurrAxis);  // Update position (private method)
            
            return 1;
        }
        catch (Exception)
        {
            // Error handling...
            return -1;
        }
    }
    
    /// <summary>
    /// Displays the parameter interface
    /// This might be required to initialize the GUI controls
    /// </summary>
    public void DisplayParameterInterface()
    {
        if (!BlnConnect)
        {
            // Error handling...
            return;
        }
        
        // Enable all axis radio buttons
        for (short num = 0; num < 6; num++)
        {
            RadAxis[num].Enabled = true;
        }
        
        // Position the parameter group box
        GrdParam.Left = groupBox2.Left + groupBox2.Width + 15;
        GrdParam.Top = groupBox2.Top;
        GrdParam.BringToFront();
    }
    
    // ===== PRIVATE METHODS (What you CAN'T call) =====
    
    /// <summary>
    /// PRIVATE: Updates the current axis selection
    /// This is called by SaveParam() and other methods
    /// </summary>
    private void GetCurrAxis()
    {
        for (short num = 0; num < 6; num++)
        {
            if (RadAxis[num].Checked)
            {
                ShrCurrAxis = num;
                break;
            }
        }
    }
    
    /// <summary>
    /// PRIVATE: Refreshes the current position by querying the stage
    /// This is what actually updates DblCurrPosi[] that GetCurrentPosition() returns
    /// </summary>
    private short RefreshCurrentPosition(short iAxis)
    {
        if (!BlnConnect)
        {
            return -1;
        }
        
        // CRITICAL: If parameters not set, return 0!
        if (!BlnParamFlag)
        {
            LblCurrValue.Text = "0";  // Update GUI label
            return -1;
        }
        
        try
        {
            // Send position query command to stage
            StrReceiver = "";
            BlnBusy = true;
            BlnSet = false;
            SendCommand("?" + AxisName(iAxis) + "\r");  // Send query command
            Delay(100000L);  // Wait for response
            BlnBusy = false;
            
            if (StrReceiver != "")
            {
                // Parse response
                if (StrReceiver.Substring(5, 1) == "-")
                {
                    LngCurrStep[iAxis] = -StringToLong(StrReceiver);
                }
                else
                {
                    LngCurrStep[iAxis] = StringToLong(StrReceiver);
                }
                
                // Calculate position in units
                if (ShrType[iAxis] != 0)
                {
                    if (ShrType[iAxis] == 1 || ShrType[iAxis] == 3 || ShrType[iAxis] == 2)
                    {
                        DblCurrPosi[iAxis] = (double)(LngCurrStep[iAxis] - LngZeroOffset[iAxis]) * DblPulseEqui[iAxis];
                        LngCurrStep[iAxis] -= LngZeroOffset[iAxis];
                    }
                    else
                    {
                        DblCurrPosi[iAxis] = (double)LngCurrStep[iAxis] * DblPulseEqui[iAxis];
                    }
                    
                    // Update GUI display
                    if (ShrCurrAxis == iAxis)
                    {
                        switch (ShrUnit[iAxis])
                        {
                            case 0:  // mm
                                LblCurrValue.Text = DblCurrPosi[iAxis].ToString("0.###");
                                break;
                            case 1:  // degree
                                LblCurrValue.Text = DblCurrPosi[iAxis].ToString("0.###");
                                break;
                            case 2:  // step
                                LblCurrValue.Text = $"{LngCurrStep[iAxis]:0}";
                                break;
                        }
                        LblCurrValue.Refresh();
                    }
                }
                return 1;
            }
            return -1;
        }
        catch (Exception)
        {
            return -1;
        }
    }
    
    /// <summary>
    /// PRIVATE: Updates the GUI display
    /// </summary>
    private void RefreshShow()
    {
        // Updates various GUI labels and controls
        // This is called by SaveParam()
    }
    
    /// <summary>
    /// PRIVATE: Event handler for OK button click
    /// This is where "Parameter setting completed!" message comes from
    /// </summary>
    private void BtnOk_Click(object sender, EventArgs e)
    {
        // Validate parameters...
        // Call SaveParam(ShrCurrAxis)
        // Call RefreshShow()
        
        // Show completion message
        if (ShrLanguage == 0)
        {
            MessageBox.Show("参数设置完成！", "提示", MessageBoxButtons.OK);
        }
        else
        {
            MessageBox.Show("Parameter setting completed!", "Prompt", MessageBoxButtons.OK);
        }
    }
    
    // ===== HELPER METHODS =====
    
    /// <summary>
    /// Sends command to stage via serial port
    /// </summary>
    private void SendCommand(string CommandString)
    {
        if (SCPort.IsOpen)
        {
            SCPort.Write(CommandString);
            SCPort.DiscardOutBuffer();
        }
    }
    
    /// <summary>
    /// Delays execution for specified milliseconds
    /// </summary>
    private void Delay(long milliSecond = 500L, bool IsCheck = true)
    {
        int tickCount = Environment.TickCount;
        BlnReadCom = false;
        if (IsCheck)
        {
            BlnStopCommand = false;
        }
        while (Math.Abs(Environment.TickCount - tickCount) < milliSecond)
        {
            if (BlnReadCom)
            {
                BlnReadCom = false;
                break;
            }
            if (IsCheck && BlnStopCommand)
            {
                break;
            }
            Application.DoEvents();  // Process Windows messages
        }
    }
    
    /// <summary>
    /// Converts string to long integer
    /// </summary>
    private long StringToLong(string str)
    {
        // String parsing logic...
        return 0;  // Placeholder
    }
    
    /// <summary>
    /// Gets axis name for commands
    /// </summary>
    private string AxisName(short axis)
    {
        return StrAxisName[axis];  // "XAxis", "YAxis", etc.
    }
}

// ===== SUMMARY OF CRITICAL ISSUES =====

/*
1. SaveParam() reads from GUI ComboBox controls that don't exist in PyQt
2. GetCurrentPosition() returns DblCurrPosi[] which is only updated by private RefreshCurrentPosition()
3. RefreshCurrentPosition() returns -1 if BlnParamFlag is false
4. BlnParamFlag is only set to true by SaveParam()
5. Set* methods only update GUI controls if sIndex == ShrCurrAxis
6. ShrCurrAxis is managed by private GetCurrAxis() method
7. "Parameter setting completed!" message comes from private BtnOk_Click() event handler

SOLUTION: The DLL needs to be modified to remove GUI dependencies, or you need to use the full Windows Forms GUI that the DLL expects.
*/
