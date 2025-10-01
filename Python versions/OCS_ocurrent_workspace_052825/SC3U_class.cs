// SC3U, Version=1.6.0.0, Culture=neutral, PublicKeyToken=null
// SC3Us.SC3U
using System;
using System.ComponentModel;
using System.Drawing;
using System.IO;
using System.IO.Ports;
using System.Text.RegularExpressions;
using System.Windows.Forms;
using SC3Us;

public class SC3U : UserControl
{
	private MainClass mMainClass;

	private bool BlnConnect;

	private static SerialPort SCPort;

	private string StrReceiver;

	private bool BlnBusy;

	private bool BlnReadCom;

	private bool BlnStopCommand;

	private short ShrPort;

	private short ShrSpeed;

	private double[] DblSpeed = new double[6];

	private short[] ShrType = new short[6];

	private short[] ShrUnit = new short[6];

	private float[] FlaMotorAngle = new float[6];

	private short[] ShrSubsection = new short[6];

	private float[] FlaPitch = new float[6];

	private int[] IntTranRatio = new int[6];

	private double[] DblTravel = new double[6];

	private long[] LngNegaTravel = new long[6];

	private long[] LngPosiTravel = new long[6];

	private short ShrCurrAxis;

	private long[] LngCurrStep = new long[6];

	private double[] DblCurrPosi = new double[6];

	private double[] DblPulseEqui = new double[6];

	private long[] LngZeroOffset = new long[6];

	private string[] StrAxisName = new string[6];

	private bool BlnSet;

	private short ShrLanguage;

	private bool BlnParamFlag;

	private bool BlnDonotTip;

	private short[] ShrUseMode = new short[6];

	private short[] ShrShutterStatus = new short[6];

	private short ShrShutterSpeed;

	private RadioButton[] RadAxis = new RadioButton[6];

	private IContainer components;

	private Button BtnFreeUp;

	private GroupBox groupBox2;

	public RadioButton RadXAxis;

	public RadioButton RadT2Axis;

	public RadioButton RadT1Axis;

	public RadioButton RadRAxis;

	public RadioButton RadZAxis;

	public RadioButton RadYAxis;

	private Button BtnRun;

	private Button BtnLimitReturnZero;

	private Label label7;

	private Button BtnFreeDown;

	private NumericUpDown NudRunToValue;

	private Button BtnFixSub;

	private Button BtnStop;

	private Button BtnFixAdd;

	private Label LblRunToValueUnit;

	private Label LblFixValueUnit;

	private Button BtnSetZero;

	private NumericUpDown NudAddOrSubValue;

	private Label label1;

	private Label LblCurrValue;

	private Label LblCurrUnit;

	private Button BtnCancelZero;

	private Label label4;

	private Label LblCurrSpeed;

	private Button BtnParamSet;

	private ComboBox CboType;

	private Label label6;

	private ComboBox CboUnit;

	private Label label8;

	private ComboBox CboMotorAngle;

	private Label label9;

	private ComboBox CboSubsection;

	private Label label10;

	private ComboBox CboPitch;

	private Label label11;

	private ComboBox CboTranRatio;

	private Label label12;

	private ComboBox CboTravel;

	private Label label13;

	private ComboBox CboNegaTravel;

	private Label label14;

	private ComboBox CboPosiTravel;

	private Label label15;

	private GroupBox GrdParam;

	private Button BtnClose;

	private Button BtnOk;

	private ComboBox CboSpeed;

	private Timer timer1;

	private Label label2;

	public short Port
	{
		[Browsable(true)]
		get
		{
			return ShrPort;
		}
	}

	public bool ConnectStatus
	{
		[Browsable(true)]
		get
		{
			return BlnConnect;
		}
	}

	public bool BusyStatus
	{
		[Browsable(true)]
		get
		{
			return BlnBusy;
		}
	}

	public bool ParameterFlag
	{
		[Browsable(true)]
		get
		{
			return BlnParamFlag;
		}
	}

	public short Language
	{
		[Browsable(true)]
		get
		{
			return ShrLanguage;
		}
		set
		{
			ShrLanguage = value;
			ChangeLanguage();
		}
	}

	public short SpeedGrades
	{
		[Browsable(true)]
		get
		{
			return ShrSpeed;
		}
		set
		{
			if (BlnConnect)
			{
				SetSpeed(value);
			}
		}
	}

	public short ShutterSpeedGrades
	{
		[Browsable(true)]
		get
		{
			return ShrShutterSpeed;
		}
		set
		{
			ShrShutterSpeed = value;
		}
	}

	public short CurrentAxis
	{
		[Browsable(true)]
		get
		{
			return ShrCurrAxis;
		}
		set
		{
			if (ShrUseMode[value] == 1 || ShrType[value] != 0)
			{
				ShrCurrAxis = value;
				RadAxis[ShrCurrAxis].Checked = true;
			}
		}
	}

	// Key methods for parameter setting and position reading
	public double GetCurrentPosition(short sIndex)
	{
		if (sIndex < 0 || sIndex > 5)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("sIndex只能是0到5之间的整数！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("sIndex must be an integer from 0 to 5!", "Prompt", MessageBoxButtons.OK);
			}
			return -1.0;
		}
		return Convert.ToDouble(DblCurrPosi[sIndex].ToString("0.##"));
	}

	public short SetType(short sIndex, short sType)
	{
		if (!BlnConnect)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("运动控制器未连接，请连接后再重试！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Motion controller not connected, retry after connection!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if (sIndex < 0 || sIndex > 5)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("sIndex只能是0到5之间的整数！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("sIndex must be an integer from 0 to 5!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if (sType < 0 || sType > 4)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("sType只能是0到4之间的整数！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("sType must be an integer from 0 to 4!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if (ShrType[sIndex] != sType)
		{
			LngZeroOffset[sIndex] = 0L;
			mMainClass.WriteToIni(StrAxisName[sIndex], "ZeroOffset", LngZeroOffset[sIndex].ToString());
		}
		ShrType[sIndex] = sType;
		if (sIndex == ShrCurrAxis)
		{
			CboType.SelectedIndex = ShrType[sIndex];
		}
		return 1;
	}

	public short SetUnit(short sIndex, short sUnit)
	{
		if (!BlnConnect)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("运动控制器未连接，请连接后再重试！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Motion controller not connected, retry after connection!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if (sIndex < 0 || sIndex > 5)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("sIndex只能是0到5之间的整数！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("sIndex must be an integer from 0 to 5!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if ((ShrType[sIndex] == 2 || ShrType[sIndex] == 3) && sUnit == 0)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("旋转台和角位移台的运行单位不能为毫米！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("The running unit of rotary stage and goniometer cannot be in mm!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if ((ShrType[sIndex] == 1 || ShrType[sIndex] == 4) && sUnit == 1)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("平移台和升降台的运行单位不能为度！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("The running unit of translation stage and elevating stage cannot be in degree!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if (sUnit < 0 || sUnit > 2)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("sUnit只能是0到2之间的整数！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("sUnit must be an integer from 0 to 2!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		ShrUnit[sIndex] = sUnit;
		if (sIndex == ShrCurrAxis)
		{
			CboUnit.SelectedIndex = ShrUnit[sIndex];
		}
		return 1;
	}

	public short SetMotorAngle(short sIndex, float fMotorAngle)
	{
		if (!BlnConnect)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("运动控制器未连接，请连接后再重试！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Motion controller not connected, retry after connection!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if (sIndex < 0 || sIndex > 5)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("sIndex只能是0到5之间的整数！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("sIndex must be an integer from 0 to 5!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if (!IsNumber(fMotorAngle.ToString()))
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("电机度数必须为数字且只能是0.9或1.8，请修改！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Motor degree must be number of 0.9 or 1.8, pls modify!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if (fMotorAngle != Convert.ToSingle(0.9) && fMotorAngle != Convert.ToSingle(1.8))
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("电机度数只能是0.9或1.8，请修改！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Motor degree must be 0.9 or 1.8, pls modify!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		FlaMotorAngle[sIndex] = fMotorAngle;
		if (sIndex == ShrCurrAxis)
		{
			CboMotorAngle.Text = FlaMotorAngle[sIndex].ToString();
		}
		return 1;
	}

	public short SetSubsection(short sIndex, short sSubsection)
	{
		if (!BlnConnect)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("运动控制器未连接，请连接后再重试！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Motion controller not connected, retry after connection!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if (sIndex < 0 || sIndex > 5)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("sIndex只能是0到5之间的整数！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("sIndex must be an integer from 0 to 5!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if (!IsNumber(sSubsection.ToString()))
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("细分数必须为数字，请修改！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Subdivision must be number, pls modify!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		ShrSubsection[sIndex] = sSubsection;
		if (sIndex == ShrCurrAxis)
		{
			CboSubsection.Text = ShrSubsection[sIndex].ToString();
		}
		return 1;
	}

	public short SetPitch(short sIndex, float fPitch)
	{
		if (!BlnConnect)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("运动控制器未连接，请连接后再重试！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Motion controller not connected, retry after connection!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if (sIndex < 0 || sIndex > 5)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("sIndex只能是0到5之间的整数！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("sIndex must be an integer from 0 to 5!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if (!IsNumber(fPitch.ToString()))
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("丝杆导程必须为大于0的数值，请修改！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Screw lead must be greater than 0, pls modify!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		short num = ShrType[sIndex];
		if ((num == 1 || num == 4) && fPitch <= 0f)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("丝杆导程必须为大于0的数值，请修改！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Screw lead must be greater than 0, pls modify!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		FlaPitch[sIndex] = fPitch;
		if (sIndex == ShrCurrAxis)
		{
			CboPitch.Text = FlaPitch[sIndex].ToString();
		}
		return 1;
	}

	public short SetTravel(short sIndex, double dTravel)
	{
		if (!BlnConnect)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("运动控制器未连接，请连接后再重试！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Motion controller not connected, retry after connection!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if (sIndex < 0 || sIndex > 5)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("sIndex只能是0到5之间的整数！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("sIndex must be an integer from 0 to 5!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if (ShrType[sIndex] == 2)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("旋转台不可设置行程！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Stroke setting of rotary stage is forbidden!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if (ShrType[sIndex] == 3 && LngZeroOffset[sIndex] != 0L)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("已设置参考零位的角位移台,请使用SetNegativeTravel和SetPositiveTravelf设置正负行程！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Goniometer of zero reference has been set, pls use SetNegativeTravel and SetPositiveTravelf to set positive/negative stroke!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if (ShrType[sIndex] == 1 && LngZeroOffset[sIndex] != 0L)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("已设置参考零位的平位移台,请使用SetNegativeTravel和SetPositiveTravelf设置正负行程！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Translation stage of zero reference has been set, pls use SetNegativeTravel and SetPositiveTravelf to set positive/negative stroke!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if (!IsNumber(dTravel.ToString()))
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("行程必须为大于0的数值，请修改！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Stroke must be greater than 0, pls modify!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		short num = ShrType[sIndex];
		if ((num == 1 || (uint)(num - 3) <= 1u) && dTravel <= 0.0)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("行程必须为大于0的数值，请修改！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Stroke must be greater than 0, pls modify!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		DblTravel[sIndex] = dTravel;
		if (sIndex == ShrCurrAxis)
		{
			CboTravel.Text = DblTravel[sIndex].ToString();
		}
		return 1;
	}

	// CRITICAL: SaveParam reads from GUI controls, not variables!
	public short SaveParam(short sIndex)
	{
		short num = 0;
		short num2 = 0;
		try
		{
			// This is the key issue - SaveParam reads from GUI ComboBox controls!
			if (ShrType[sIndex] == 1)
			{
				DblPulseEqui[sIndex] = Convert.ToDouble(CboMotorAngle.Text) * Convert.ToDouble(CboPitch.Text) / (double)(360 * Convert.ToInt16(CboSubsection.Text));
			}
			else if (ShrType[sIndex] == 2 || ShrType[sIndex] == 3)
			{
				DblPulseEqui[sIndex] = Convert.ToDouble(CboMotorAngle.Text) / (Convert.ToDouble(CboTranRatio.Text) * Convert.ToDouble(CboSubsection.Text));
			}
			else if (ShrType[sIndex] == 4)
			{
				DblPulseEqui[sIndex] = Convert.ToDouble(CboPitch.Text) / Convert.ToDouble(CboTranRatio.Text) / (360.0 / Convert.ToDouble(CboMotorAngle.Text) * Convert.ToDouble(CboSubsection.Text));
			}
			else
			{
				DblPulseEqui[sIndex] = -1.0;
			}
			if (ShrType[sIndex] != 0)
			{
				if (ShrUnit[sIndex] == 2)
				{
					DblSpeed[sIndex] = (ShrSpeed + 1) * 22000 / 720;
				}
				else
				{
					DblSpeed[sIndex] = (double)((ShrSpeed + 1) * 22000) * DblPulseEqui[sIndex] / 720.0;
				}
				RadAxis[sIndex].Enabled = true;
			}
			else
			{
				RadAxis[sIndex].Enabled = false;
			}
			if (ShrType[sIndex] == 3 || ShrType[sIndex] == 1 || ShrType[sIndex] == 2)
			{
				BtnSetZero.Enabled = true;
				BtnCancelZero.Enabled = true;
			}
			else
			{
				BtnSetZero.Enabled = false;
				BtnCancelZero.Enabled = false;
			}
			num++;
			mMainClass.WriteToIni(StrAxisName[sIndex], "Type", ShrType[sIndex].ToString());
			mMainClass.WriteToIni(StrAxisName[sIndex], "Unit", ShrUnit[sIndex].ToString());
			mMainClass.WriteToIni(StrAxisName[sIndex], "MotorAngle", FlaMotorAngle[sIndex].ToString());
			mMainClass.WriteToIni(StrAxisName[sIndex], "Subsection", ShrSubsection[sIndex].ToString());
			mMainClass.WriteToIni(StrAxisName[sIndex], "Pitch", FlaPitch[sIndex].ToString());
			mMainClass.WriteToIni(StrAxisName[sIndex], "TranRatio", IntTranRatio[sIndex].ToString());
			mMainClass.WriteToIni(StrAxisName[sIndex], "Travel", DblTravel[sIndex].ToString());
			mMainClass.WriteToIni(StrAxisName[sIndex], "NegaTravel", LngNegaTravel[sIndex].ToString());
			mMainClass.WriteToIni(StrAxisName[sIndex], "PosiTravel", LngPosiTravel[sIndex].ToString());
			for (short num3 = 0; num3 < 6; num3++)
			{
				if (ShrType[num3] != 0)
				{
					num2++;
				}
			}
			if (num2 == 0)
			{
				BlnParamFlag = false;
			}
			else
			{
				BlnParamFlag = true;
			}
			if (ShrType[sIndex] == 0 && RadAxis[sIndex].Checked)
			{
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
			GetCurrAxis();
			num++;
			RefreshShow();
			num++;
			RefreshCurrentPosition(ShrCurrAxis);
			return 1;
		}
		catch (Exception)
		{
			switch (num)
			{
			case 0:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数SaveParam中"参数计算和赋值"出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Parameter calculation and assignment\" in function BtnOk_Click go wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 1:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数SaveParam中"参数保存"出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Parameter saving\" in function BtnOk_Click goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 2:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数BtnOk_Click中"刷新单位和速度"出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Refresh unit and speed\" in function BtnOk_Click goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 3:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数BtnOk_Click中"刷新当前位置"出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Refresh current position\" in function BtnOk_Click goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			}
			return -1;
		}
	}

	public void DisplayParameterInterface()
	{
		if (!BlnConnect)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("运动控制器未连接，请连接后再重试！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Motion controller not connected, retry after connection!", "Prompt", MessageBoxButtons.OK);
			}
			return;
		}
		for (short num = 0; num < 6; num++)
		{
			RadAxis[num].Enabled = true;
		}
		GrdParam.Left = groupBox2.Left + groupBox2.Width + 15;
		GrdParam.Top = groupBox2.Top;
		GrdParam.BringToFront();
	}

	// This is where "Parameter setting completed!" message comes from
	private void BtnOk_Click(object sender, EventArgs e)
	{
		// ... parameter validation code ...
		SaveParam(ShrCurrAxis);
		RefreshShow();
		if (ShrLanguage == 0)
		{
			MessageBox.Show("参数设置完成！", "提示", MessageBoxButtons.OK);
		}
		else
		{
			MessageBox.Show("Parameter setting completed!", "Prompt", MessageBoxButtons.OK);
		}
	}

	// Helper methods
	private static bool IsNumber(string s)
	{
		if (string.IsNullOrWhiteSpace(s))
		{
			return false;
		}
		return new Regex("^[-+]?[0-9]+(\\.[0-9]+)?$").IsMatch(s);
	}

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

	private void RefreshShow()
	{
		// Updates display labels and controls
	}

	private void RefreshCurrentPosition(short sAxis)
	{
		// Refreshes current position display
	}

	// Constructor and other methods would be here...
}
