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

	public SC3U()
	{
		InitializeComponent();
		RadAxis[0] = RadXAxis;
		RadAxis[1] = RadYAxis;
		RadAxis[2] = RadZAxis;
		RadAxis[3] = RadRAxis;
		RadAxis[4] = RadT1Axis;
		RadAxis[5] = RadT2Axis;
		Control.CheckForIllegalCrossThreadCalls = false;
		SCPort = new SerialPort();
		mMainClass = new MainClass();
		CboSpeed.Items.Clear();
		for (short num = 0; num <= 255; num++)
		{
			CboSpeed.Items.Add(num.ToString());
		}
		StrAxisName[0] = "XAxis";
		StrAxisName[1] = "YAxis";
		StrAxisName[2] = "ZAxis";
		StrAxisName[3] = "RAxis";
		StrAxisName[4] = "T1Axis";
		StrAxisName[5] = "T2Axis";
		base.Width = 563;
		ShrLanguage = 1;
		ChangeLanguage();
	}

	~SC3U()
	{
		BlnStopCommand = true;
		timer1.Enabled = false;
		ClosePort();
	}

	public void ConnectPort(short sPort)
	{
		short num = 0;
		try
		{
			if (SCPort.IsOpen)
			{
				SCPort.Close();
			}
			SCPort.PortName = "COM" + sPort;
			SCPort.BaudRate = 9600;
			SCPort.DataBits = 8;
			SCPort.StopBits = StopBits.One;
			SCPort.Parity = Parity.None;
			SCPort.ReadBufferSize = 2048;
			SCPort.WriteBufferSize = 1024;
			SCPort.DtrEnable = true;
			SCPort.Handshake = Handshake.None;
			SCPort.ReceivedBytesThreshold = 1;
			SCPort.RtsEnable = false;
			num++;
			SCPort.DataReceived += SCPort_DataReceived;
			SCPort.Open();
			if (!SCPort.IsOpen)
			{
				return;
			}
			StrReceiver = "";
			BlnBusy = true;
			BlnSet = false;
			SendCommand("?R\r");
			Delay(5000L);
			BlnBusy = false;
			if (StrReceiver == "?R\rOK\n")
			{
				BlnConnect = true;
				ShrPort = sPort;
				mMainClass.WriteToIni("Connect", "232Port34", ShrPort.ToString(), "ConnectParam.ini");
				num++;
				StrReceiver = "";
				BlnBusy = true;
				BlnSet = false;
				SendCommand("?V\r");
				Delay(100000L);
				BlnBusy = false;
				if (StrReceiver != "")
				{
					ShrSpeed = Convert.ToInt16(StringToLong(StrReceiver));
				}
				num++;
				ReadParam();
				num++;
				GetCurrAxis();
				if (RadAxis[ShrCurrAxis].Checked && ShrType[ShrCurrAxis] == 0)
				{
					short num2;
					for (num2 = 0; num2 < 6; num2++)
					{
						if (ShrType[num2] != 0)
						{
							RadAxis[num2].Checked = true;
							break;
						}
					}
					if (num2 == 6)
					{
						RadAxis[ShrCurrAxis].Checked = false;
						RadAxis[0].Checked = true;
					}
					GetCurrAxis();
				}
				num++;
				short num3 = 0;
				short num4 = 0;
				for (short num2 = 0; num2 < 6; num2++)
				{
					if (ShrType[num2] != 0)
					{
						RefreshCurrentPosition(num2);
						num3++;
					}
					if (ShrUseMode[num2] == 0)
					{
						num4++;
					}
				}
				if (num3 == 0 && num4 != 0)
				{
					if (ShrLanguage == 0)
					{
						MessageBox.Show("请先设置电移台参数！", "提示", MessageBoxButtons.OK);
					}
					else
					{
						MessageBox.Show("Set parameters of motorized positioning stages first!", "Prompt", MessageBoxButtons.OK);
					}
					DisplayParameterInterface();
				}
				num++;
				RefreshShow();
				if (!BlnParamFlag)
				{
					BtnParamSet_Click(BtnParamSet, null);
				}
			}
			else
			{
				BlnBusy = false;
				BlnConnect = false;
				if (ShrLanguage == 0)
				{
					MessageBox.Show("运动控制器串口连接失败！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("Serial port connection of motion controller failed!", "Prompt", MessageBoxButtons.OK);
				}
			}
		}
		catch (Exception)
		{
			switch (num)
			{
			case 0:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数ConnectPort中“串口信息设置”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Settings of serial port info\" in function ConnectPort go wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 1:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数ConnectPort中“联络控制器”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Communicate with controller\" in function ConnectPort goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 2:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数ConnectPort中“读取速度”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Reading speed\" in function ConnectPort goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 3:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数ConnectPort中“读入参数并显示”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Read in and display parameters\" in function ConnectPort goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 4:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数ConnectPort中“得到使用轴”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Obtain use axis\" in function ConnectPort goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 5:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数ConnectPort中“刷新当前位置”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Refresh current position\" in function ConnectPort goes wrong! ", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 6:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数ConnectPort中“刷新单位信息”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Refresh unit info\" in function ConnectPort goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			}
			BlnBusy = false;
			BlnConnect = false;
		}
	}

	public void ClosePort()
	{
		if (SCPort.IsOpen)
		{
			SCPort.Close();
			BlnConnect = false;
		}
	}

	public void StopDelay()
	{
		BlnStopCommand = true;
	}

	public double GetActualSpeed(short sIndex)
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
		return DblSpeed[sIndex];
	}

	public double GetPulseEquivalent(short sIndex)
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
		return DblPulseEqui[sIndex];
	}

	public short GetType(short sIndex)
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
			return -1;
		}
		return ShrType[sIndex];
	}

	public short GetUnit(short sIndex)
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
			return -1;
		}
		return ShrUnit[sIndex];
	}

	public float GetMotorAngle(short sIndex)
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
			return -1f;
		}
		return FlaMotorAngle[sIndex];
	}

	public short GetSubsection(short sIndex)
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
			return -1;
		}
		return ShrSubsection[sIndex];
	}

	public float GetPitch(short sIndex)
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
			return -1f;
		}
		return FlaPitch[sIndex];
	}

	public int GetTranRatio(short sIndex)
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
			return -1;
		}
		return IntTranRatio[sIndex];
	}

	public double GetTravel(short sIndex)
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
		return DblTravel[sIndex];
	}

	public long GetNegativeTravel(short sIndex)
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
			return -1L;
		}
		return LngNegaTravel[sIndex];
	}

	public long GetPositiveTravel(short sIndex)
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
			return -1L;
		}
		return LngPosiTravel[sIndex];
	}

	public long GetCurrentStep(short sIndex)
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
			return -1L;
		}
		return LngCurrStep[sIndex];
	}

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

	public long GetZeroOffset(short sIndex)
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
			return -1L;
		}
		return LngZeroOffset[sIndex];
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

	public short SetTranRatio(short sIndex, int iTranRatio)
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
		if (!IsNumber(iTranRatio.ToString()))
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("传动比必须为大于0的数值，请修改！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Transmission ratio must be greater than 0, pls modify!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		short num = ShrType[sIndex];
		if ((uint)(num - 2) <= 2u && iTranRatio <= 0)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("传动比必须为大于0的数值，请修改！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Transmission ratio must be greater than 0, pls modify!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		IntTranRatio[sIndex] = iTranRatio;
		if (sIndex == ShrCurrAxis)
		{
			CboTranRatio.Text = IntTranRatio[sIndex].ToString();
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

	public short SetNegativeTravel(short sIndex, long sNegativeTravel)
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
		if (LngZeroOffset[sIndex] == 0L)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("参考零位不能为0！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Zero reference cannot be 0!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if (!IsNumber(sNegativeTravel.ToString()))
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("负向行程必须为数字，请修改！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Negative stroke must be number, pls modify!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		LngNegaTravel[sIndex] = sNegativeTravel;
		if (sIndex == ShrCurrAxis)
		{
			CboNegaTravel.Text = LngNegaTravel[sIndex].ToString();
		}
		return 1;
	}

	public short SetPositiveTravel(short sIndex, long sPositiveTravel)
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
		if (LngZeroOffset[sIndex] == 0L)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("请先设置参考零位！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Pls set zero reference first!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if (!IsNumber(sPositiveTravel.ToString()))
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("正向行程必须为数字，请修改！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Positive stroke must be number, pls modify!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		LngPosiTravel[sIndex] = sPositiveTravel;
		if (sIndex == ShrCurrAxis)
		{
			CboPosiTravel.Text = LngPosiTravel[sIndex].ToString();
		}
		return 1;
	}

	public short SetZeroOffset(short sIndex, long lZeroOffset)
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
		if (ShrType[ShrCurrAxis] == 2)
		{
			DialogResult dialogResult = ((ShrLanguage != 0) ? MessageBox.Show("Does the rotary stage have zero position?", "Prompt", MessageBoxButtons.YesNo) : MessageBox.Show("这个旋转台有零位吗？", "提示", MessageBoxButtons.YesNo));
			if (dialogResult == DialogResult.No)
			{
				if (ShrLanguage == 0)
				{
					MessageBox.Show("没有零位的旋转台无法设置软零位！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("Rotary stage  without zero position cannot set soft zero position!", "Prompt", MessageBoxButtons.OK);
				}
				return -1;
			}
		}
		if (ShrType[ShrCurrAxis] != 3 && ShrType[ShrCurrAxis] != 1 && ShrType[ShrCurrAxis] != 2)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("只有平移台、旋转台和角位移台可以设置零位！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Zero position can be set for translation stage,rotary stage and goniometer only!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if (!IsNumber(lZeroOffset.ToString()))
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("零点偏移量必须为数字，请修改！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Zero point offset must be number, pls modify!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if (lZeroOffset > 999999)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("lZeroOffset必须是小于999999的整数！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("lZeroOffset must be an integer smaller than 999,999!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		LngZeroOffset[sIndex] = lZeroOffset;
		mMainClass.WriteToIni(StrAxisName[sIndex], "ZeroOffset", LngZeroOffset[sIndex].ToString());
		return 1;
	}

	public short RefreshCurrentPosition(short iAxis)
	{
		short num = 0;
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
		if (!BlnParamFlag)
		{
			LblCurrValue.Text = "0";
			return -1;
		}
		try
		{
			StrReceiver = "";
			BlnBusy = true;
			BlnSet = false;
			SendCommand("?" + AxisName(iAxis) + "\r");
			Delay(100000L);
			BlnBusy = false;
			if (StrReceiver != "")
			{
				if (StrReceiver.Substring(5, 1) == "-")
				{
					LngCurrStep[iAxis] = -StringToLong(StrReceiver);
				}
				else
				{
					LngCurrStep[iAxis] = StringToLong(StrReceiver);
				}
				num++;
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
					if (ShrCurrAxis == iAxis)
					{
						switch (ShrUnit[iAxis])
						{
						case 0:
							LblCurrValue.Text = DblCurrPosi[iAxis].ToString("0.###");
							break;
						case 1:
							LblCurrValue.Text = DblCurrPosi[iAxis].ToString("0.###");
							break;
						case 2:
							LblCurrValue.Text = $"{LngCurrStep[iAxis]:0}";
							break;
						}
						LblCurrValue.Refresh();
					}
					return 1;
				}
				return -1;
			}
			return -1;
		}
		catch (Exception)
		{
			switch (num)
			{
			case 0:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数RefreshCurrentPosition中“位置查询”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Position query\" in function RefreshCurrentPosition goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 1:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数RefreshCurrentPosition中“刷新参数”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Refresh parameters\" in function RefreshCurrentPosition goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			}
			return -1;
		}
	}

	public short RunToZero(short sIndex, short sMode)
	{
		short num = 0;
		try
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
			if (BlnBusy)
			{
				if (ShrLanguage == 0)
				{
					MessageBox.Show("通讯忙，请稍候！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("Busy, try later!", "Prompt", MessageBoxButtons.OK);
				}
				return -1;
			}
			if ((ShrType[sIndex] == 3 || ShrType[sIndex] == 1 || ShrType[sIndex] == 2) && LngZeroOffset[sIndex] != 0L)
			{
				SendRunToZeroAndShow(sIndex, 0);
				num++;
				switch (sMode)
				{
				case 0:
					RunToStep(sIndex, LngZeroOffset[sIndex]);
					break;
				case 1:
					RunToStep(sIndex, LngCurrStep[sIndex]);
					break;
				}
			}
			else
			{
				SendRunToZeroAndShow(sIndex, sMode);
				num = 2;
				RefreshCurrentPosition(sIndex);
				if (sMode == 2)
				{
					switch (ShrUnit[sIndex])
					{
					case 0:
					case 1:
						if (Math.Round(DblCurrPosi[sIndex], 5) != 0.0)
						{
							num = 3;
							SendRunToZeroAndShow(sIndex, sMode);
							num = 4;
							RefreshCurrentPosition(sIndex);
						}
						break;
					case 2:
						if (LngCurrStep[sIndex] != 0L)
						{
							num = 3;
							SendRunToZeroAndShow(sIndex, sMode);
							num = 4;
							RefreshCurrentPosition(sIndex);
						}
						break;
					}
				}
			}
			return 1;
		}
		catch (Exception)
		{
			switch (num)
			{
			case 0:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数RunToZero中“归零”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Return to zero\" in function RunToZero goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 1:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数RunToZero中“移动到零位偏移量或当前位置”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Move to zero position offset or current position\" in function RunToZero goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 2:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数RunToZero中“刷新当前位置”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Refresh current position\" in function RunToZero goes wrong! ", "Prompt", MessageBoxButtons.OK);
				}
				break;
			}
			return -1;
		}
	}

	public short RunToStep(short sIndex, long lStep)
	{
		short num = 0;
		try
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
			if (BlnBusy)
			{
				if (ShrLanguage == 0)
				{
					MessageBox.Show("通讯忙，请稍候！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("Busy, try later!", "Prompt", MessageBoxButtons.OK);
				}
				return -1;
			}
			string text = ((lStep <= 0) ? lStep.ToString() : ("+" + lStep));
			StrReceiver = "";
			BlnBusy = true;
			BlnSet = true;
			SendCommand(AxisName(sIndex) + text + "\r");
			LblCurrValue.Text = "...... ";
			timer1.Interval = 310 - ShrSpeed;
			timer1.Enabled = true;
			Delay(100000000L);
			timer1.Enabled = false;
			BlnBusy = false;
			num++;
			RefreshCurrentPosition(sIndex);
			if (sIndex != ShrCurrAxis)
			{
				RefreshCurrentPosition(ShrCurrAxis);
			}
			return 1;
		}
		catch (Exception)
		{
			switch (num)
			{
			case 0:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数RunToStep中“移动到指定位置”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Move to designated position\" in function RunToStep goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 1:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数RunToStep中“刷新当前位置”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Refresh current position\" in function RunToStep goes wrong! ", "Prompt", MessageBoxButtons.OK);
				}
				break;
			}
			return -1;
		}
	}

	public short RunToPosition(short sIndex, double dPosition)
	{
		short num = 0;
		try
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
			if (BlnBusy)
			{
				if (ShrLanguage == 0)
				{
					MessageBox.Show("通讯忙，请稍候！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("Busy, try later!", "Prompt", MessageBoxButtons.OK);
				}
				return -1;
			}
			long lStep = Convert.ToInt64(dPosition / DblPulseEqui[sIndex]);
			num++;
			RunToStep(sIndex, lStep);
			return 1;
		}
		catch (Exception)
		{
			switch (num)
			{
			case 0:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数RunToPosition中“计算步数”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Calculate steps\" in function RunToPosition goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 1:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数RunToPosition中“刷新当前位置”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Refresh current position\" in function RunToPosition goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			}
			return -1;
		}
	}

	public short StopRun()
	{
		try
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
			StrReceiver = "";
			BlnBusy = true;
			BlnSet = true;
			SendCommand("S\r");
			timer1.Enabled = false;
			Delay(500L, IsCheck: false);
			BlnStopCommand = true;
			BlnBusy = false;
			return 1;
		}
		catch (Exception)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("函数StopRun中“发送停止命令”出现错误！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("\"Sending stop command\" in function StopRun goes wrong!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
	}

	public short SaveParam(short sIndex)
	{
		short num = 0;
		short num2 = 0;
		try
		{
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
					MessageBox.Show("函数SaveParam中“参数计算和赋值”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Parameter calculation and assignment\" in function BtnOk_Click go wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 1:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数SaveParam中“参数保存”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Parameter saving\" in function BtnOk_Click goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 2:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数BtnOk_Click中“刷新单位和速度”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Refresh unit and speed\" in function BtnOk_Click goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 3:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数BtnOk_Click中“刷新当前位置”出现错误！", "提示", MessageBoxButtons.OK);
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

	public void DisplayOperationInterface()
	{
		GrdParam.Left = -10000;
	}

	public short SetUseMode(short sIndex, short sUseMode)
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
			return -1;
		}
		ShrUseMode[sIndex] = sUseMode;
		if (sUseMode == 1)
		{
			RadAxis[sIndex].Enabled = true;
		}
		if (sIndex == ShrCurrAxis)
		{
			RefreshShutterDisplay(sIndex);
		}
		return 1;
	}

	public short GetUseMode(short sIndex)
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
			return -1;
		}
		return ShrUseMode[sIndex];
	}

	public short GetShutterStatus(short sIndex)
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
			return -1;
		}
		return ShrShutterStatus[sIndex];
	}

	public short OpenShutter(short sIndex)
	{
		short speed = 0;
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
		try
		{
			speed = ShrSpeed;
			SetSpeed(ShrShutterSpeed);
			StrReceiver = "";
			BlnBusy = true;
			BlnSet = true;
			SendCommand(AxisName(sIndex) + "+600\r");
			Delay(10000L);
			BlnBusy = false;
			ShrShutterStatus[sIndex] = 1;
			SetSpeed(speed);
			return 1;
		}
		catch (Exception)
		{
			BlnBusy = false;
			ShrShutterStatus[sIndex] = 1;
			SetSpeed(speed);
			return -1;
		}
	}

	public short CloseShutter(short sIndex)
	{
		short speed = 0;
		if (!BlnConnect)
		{
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
		try
		{
			speed = ShrSpeed;
			SetSpeed(ShrShutterSpeed);
			SendRunToZeroAndShow(sIndex, 2);
			ShrShutterStatus[sIndex] = 0;
			SetSpeed(speed);
			return 1;
		}
		catch (Exception)
		{
			ShrShutterStatus[sIndex] = 0;
			SetSpeed(speed);
			return -1;
		}
	}

	public short FreeUp(ref string sInfo)
	{
		try
		{
			if (!BlnConnect)
			{
				if (ShrLanguage == 0)
				{
					sInfo = "运动控制器未连接，请连接后再重试！";
				}
				else
				{
					sInfo = "Motion controller not connected, retry after connection!";
				}
				return -1;
			}
			if (BlnBusy)
			{
				if (ShrLanguage == 0)
				{
					sInfo = "通讯忙，请稍候！";
				}
				else
				{
					sInfo = "Busy, try later!";
				}
				return -1;
			}
			if (!BlnParamFlag)
			{
				if (ShrLanguage == 0)
				{
					sInfo = "请先设置参数，再使用！";
				}
				else
				{
					sInfo = "Set parameters before use!";
				}
				return -1;
			}
			if (ShrUseMode[ShrCurrAxis] == 1)
			{
				OpenShutter(ShrCurrAxis);
				return 1;
			}
			if (ShrType[ShrCurrAxis] == 4 || ((ShrType[ShrCurrAxis] == 3 || ShrType[ShrCurrAxis] == 1) && LngZeroOffset[ShrCurrAxis] == 0L))
			{
				if ((double)LngCurrStep[ShrCurrAxis] == DblTravel[ShrCurrAxis] / DblPulseEqui[ShrCurrAxis])
				{
					if (ShrLanguage == 0)
					{
						sInfo = "已经到达最大行程！";
					}
					else
					{
						sInfo = "Max. stroke reached!";
					}
					return -1;
				}
				BtnStop.Focus();
				ControlEnable(bEnable: false);
				if (ShrUnit[ShrCurrAxis] == 2)
				{
					RunToStep(ShrCurrAxis, Convert.ToInt64(DblTravel[ShrCurrAxis] / DblPulseEqui[ShrCurrAxis] - (double)LngCurrStep[ShrCurrAxis]));
				}
				else
				{
					RunToPosition(ShrCurrAxis, DblTravel[ShrCurrAxis] - (double)LngCurrStep[ShrCurrAxis] * DblPulseEqui[ShrCurrAxis]);
				}
			}
			else if ((ShrType[ShrCurrAxis] == 3 || ShrType[ShrCurrAxis] == 1) && LngZeroOffset[ShrCurrAxis] != 0L)
			{
				if ((double)LngCurrStep[ShrCurrAxis] >= (double)LngPosiTravel[ShrCurrAxis] / DblPulseEqui[ShrCurrAxis])
				{
					if (ShrLanguage == 0)
					{
						sInfo = "已经到达正向行程！";
					}
					else
					{
						sInfo = "Positive stroke position reached!";
					}
					return -1;
				}
				BtnStop.Focus();
				ControlEnable(bEnable: false);
				if (ShrUnit[ShrCurrAxis] == 2)
				{
					RunToStep(ShrCurrAxis, Convert.ToInt64((double)LngPosiTravel[ShrCurrAxis] / DblPulseEqui[ShrCurrAxis]) - LngCurrStep[ShrCurrAxis]);
				}
				else
				{
					RunToPosition(ShrCurrAxis, ((double)LngPosiTravel[ShrCurrAxis] / DblPulseEqui[ShrCurrAxis] - (double)LngCurrStep[ShrCurrAxis]) * DblPulseEqui[ShrCurrAxis]);
				}
			}
			else
			{
				BtnStop.Focus();
				ControlEnable(bEnable: false);
				RunToStep(ShrCurrAxis, 100000L);
			}
			ControlEnable(bEnable: true);
			return 1;
		}
		catch (Exception)
		{
			return -1;
		}
	}

	public short FreeDown(ref string sInfo)
	{
		try
		{
			if (!BlnConnect)
			{
				if (ShrLanguage == 0)
				{
					sInfo = "运动控制器未连接，请连接后再重试！";
				}
				else
				{
					sInfo = "Motion controller not connected, retry after connection!";
				}
				return -1;
			}
			if (BlnBusy)
			{
				if (ShrLanguage == 0)
				{
					sInfo = "通讯忙，请稍候！";
				}
				else
				{
					sInfo = "Busy, try later!";
				}
				return -1;
			}
			if (!BlnParamFlag)
			{
				if (ShrLanguage == 0)
				{
					sInfo = "请先设置参数，再使用！";
				}
				else
				{
					sInfo = "Set parameters before use!";
				}
				return -1;
			}
			if (ShrUseMode[ShrCurrAxis] == 1)
			{
				CloseShutter(ShrCurrAxis);
				return 1;
			}
			if (ShrType[ShrCurrAxis] == 4 || ((ShrType[ShrCurrAxis] == 3 || ShrType[ShrCurrAxis] == 1) && LngZeroOffset[ShrCurrAxis] == 0L))
			{
				if (LngCurrStep[ShrCurrAxis] == 0L)
				{
					if (ShrLanguage == 0)
					{
						sInfo = "已经到达零位！";
					}
					else
					{
						sInfo = "Zero position reached!";
					}
					return -1;
				}
				BtnStop.Focus();
				ControlEnable(bEnable: false);
				if (ShrUnit[ShrCurrAxis] == 2)
				{
					RunToStep(ShrCurrAxis, -LngCurrStep[ShrCurrAxis]);
				}
				else
				{
					RunToPosition(ShrCurrAxis, 0.0 - (double)LngCurrStep[ShrCurrAxis] * DblPulseEqui[ShrCurrAxis]);
				}
			}
			else if ((ShrType[ShrCurrAxis] == 3 || ShrType[ShrCurrAxis] == 1 || ShrType[ShrCurrAxis] == 2) && LngZeroOffset[ShrCurrAxis] != 0L)
			{
				if (ShrType[ShrCurrAxis] == 3 || ShrType[ShrCurrAxis] == 1)
				{
					if ((double)LngCurrStep[ShrCurrAxis] <= (double)(-LngNegaTravel[ShrCurrAxis]) / DblPulseEqui[ShrCurrAxis])
					{
						if (ShrLanguage == 0)
						{
							sInfo = "已经到达负向行程！";
						}
						else
						{
							sInfo = "Negative stroke position reached!";
						}
						return -1;
					}
					BtnStop.Focus();
					ControlEnable(bEnable: false);
					if (ShrUnit[ShrCurrAxis] == 2)
					{
						RunToStep(ShrCurrAxis, -Convert.ToInt64((double)LngNegaTravel[ShrCurrAxis] / DblPulseEqui[ShrCurrAxis] + (double)LngCurrStep[ShrCurrAxis]));
					}
					else
					{
						RunToPosition(ShrCurrAxis, (0.0 - ((double)LngNegaTravel[ShrCurrAxis] / DblPulseEqui[ShrCurrAxis] + (double)LngCurrStep[ShrCurrAxis])) * DblPulseEqui[ShrCurrAxis]);
					}
				}
				else
				{
					if (LngCurrStep[ShrCurrAxis] <= 0)
					{
						if (ShrLanguage == 0)
						{
							sInfo = "已经到达零点！";
						}
						else
						{
							sInfo = "Zero position reached!";
						}
						return -1;
					}
					BtnStop.Focus();
					ControlEnable(bEnable: false);
					if (ShrUnit[ShrCurrAxis] == 2)
					{
						RunToStep(ShrCurrAxis, -LngCurrStep[ShrCurrAxis]);
					}
					else
					{
						RunToPosition(ShrCurrAxis, (double)(-LngCurrStep[ShrCurrAxis]) * DblPulseEqui[ShrCurrAxis]);
					}
				}
			}
			else
			{
				BtnStop.Focus();
				ControlEnable(bEnable: false);
				RunToStep(ShrCurrAxis, -100000L);
			}
			ControlEnable(bEnable: true);
			return 1;
		}
		catch (Exception)
		{
			return -1;
		}
	}

	public short FixIncrease(string sFixValue, ref string sInfo)
	{
		try
		{
			if (!BlnConnect)
			{
				if (ShrLanguage == 0)
				{
					sInfo = "运动控制器未连接，请连接后再重试！";
				}
				else
				{
					sInfo = "Motion controller not connected, retry after connection!";
				}
				return -1;
			}
			if (BlnBusy)
			{
				if (ShrLanguage == 0)
				{
					sInfo = "通讯忙，请稍候！";
				}
				else
				{
					sInfo = "Busy, try later!";
				}
				return -1;
			}
			if (!BlnParamFlag)
			{
				if (ShrLanguage == 0)
				{
					sInfo = "请先设置参数，再使用！";
				}
				else
				{
					sInfo = "Set parameters before use!";
				}
				return -1;
			}
			if (!IsNumber(sFixValue))
			{
				if (ShrLanguage == 0)
				{
					sInfo = "请输入数值！";
				}
				else
				{
					sInfo = "Pls enter value!";
				}
				NudAddOrSubValue.Focus();
				return -1;
			}
			if (ShrType[ShrCurrAxis] == 4 || ((ShrType[ShrCurrAxis] == 3 || ShrType[ShrCurrAxis] == 1) && LngZeroOffset[ShrCurrAxis] == 0L))
			{
				if (ShrUnit[ShrCurrAxis] == 2)
				{
					if ((double)LngCurrStep[ShrCurrAxis] + Convert.ToDouble(sFixValue) > DblTravel[ShrCurrAxis] / DblPulseEqui[ShrCurrAxis])
					{
						if (ShrLanguage == 0)
						{
							sInfo = "最终位置大于行程！";
						}
						else
						{
							sInfo = "Final position is greater than stroke!";
						}
						NudAddOrSubValue.Focus();
						return -1;
					}
				}
				else if (Math.Round(DblCurrPosi[ShrCurrAxis], 5) + Convert.ToDouble(sFixValue) > DblTravel[ShrCurrAxis])
				{
					if (ShrLanguage == 0)
					{
						sInfo = "最终位置大于行程！";
					}
					else
					{
						sInfo = "Final position is greater than stroke!";
					}
					NudAddOrSubValue.Focus();
					return -1;
				}
			}
			else if ((ShrType[ShrCurrAxis] == 3 || ShrType[ShrCurrAxis] == 1) && LngZeroOffset[ShrCurrAxis] != 0L)
			{
				if (ShrUnit[ShrCurrAxis] == 2)
				{
					if ((double)LngCurrStep[ShrCurrAxis] + Convert.ToDouble(sFixValue) > (double)LngZeroOffset[ShrCurrAxis] + (double)LngPosiTravel[ShrCurrAxis] / DblPulseEqui[ShrCurrAxis])
					{
						if (ShrLanguage == 0)
						{
							sInfo = "最终位置大于行程！";
						}
						else
						{
							sInfo = "Final position is greater than stroke!";
						}
						NudAddOrSubValue.Focus();
						return -1;
					}
				}
				else if (Math.Round(DblCurrPosi[ShrCurrAxis], 5) + Convert.ToDouble(sFixValue) > (double)LngPosiTravel[ShrCurrAxis])
				{
					if (ShrLanguage == 0)
					{
						sInfo = "最终位置大于行程！";
					}
					else
					{
						sInfo = "Final position is greater than stroke!";
					}
					NudAddOrSubValue.Focus();
					return -1;
				}
			}
			BtnStop.Focus();
			ControlEnable(bEnable: false);
			if (ShrUnit[ShrCurrAxis] == 2)
			{
				RunToStep(ShrCurrAxis, Convert.ToInt64(sFixValue));
			}
			else
			{
				RunToPosition(ShrCurrAxis, Convert.ToDouble(sFixValue));
			}
			ControlEnable(bEnable: true);
			return 1;
		}
		catch (Exception)
		{
			return -1;
		}
	}

	public short FixDecrease(string sFixValue, ref string sInfo)
	{
		try
		{
			if (!BlnConnect)
			{
				if (ShrLanguage == 0)
				{
					sInfo = "运动控制器未连接，请连接后再重试！";
				}
				else
				{
					sInfo = "Motion controller not connected, retry after connection!";
				}
				return -1;
			}
			if (BlnBusy)
			{
				if (ShrLanguage == 0)
				{
					sInfo = "通讯忙，请稍候！";
				}
				else
				{
					sInfo = "Busy, try later!";
				}
				return -1;
			}
			if (!BlnParamFlag)
			{
				if (ShrLanguage == 0)
				{
					sInfo = "请先设置参数，再使用！";
				}
				else
				{
					sInfo = "Set parameters before use!";
				}
				return -1;
			}
			if (!IsNumber(sFixValue))
			{
				if (ShrLanguage == 0)
				{
					sInfo = "请输入数值！";
				}
				else
				{
					sInfo = "Pls enter value!";
				}
				NudAddOrSubValue.Focus();
				return -1;
			}
			if (ShrType[ShrCurrAxis] == 4 || ((ShrType[ShrCurrAxis] == 3 || ShrType[ShrCurrAxis] == 1) && LngZeroOffset[ShrCurrAxis] == 0L))
			{
				if (ShrUnit[ShrCurrAxis] == 2)
				{
					if ((double)LngCurrStep[ShrCurrAxis] - Convert.ToDouble(sFixValue) < 0.0)
					{
						if (ShrLanguage == 0)
						{
							sInfo = "最终位置小于0！";
						}
						else
						{
							sInfo = "Final position is smaller than 0!";
						}
						NudAddOrSubValue.Focus();
						return -1;
					}
				}
				else if (Math.Round(DblCurrPosi[ShrCurrAxis], 5) - Convert.ToDouble(sFixValue) < 0.0)
				{
					if (ShrLanguage == 0)
					{
						sInfo = "最终位置小于0！";
					}
					else
					{
						sInfo = "Final position is smaller than 0!";
					}
					NudAddOrSubValue.Focus();
					return -1;
				}
			}
			else if ((ShrType[ShrCurrAxis] == 3 || ShrType[ShrCurrAxis] == 1 || ShrType[ShrCurrAxis] == 2) && LngZeroOffset[ShrCurrAxis] != 0L)
			{
				if (ShrType[ShrCurrAxis] == 3 || ShrType[ShrCurrAxis] == 1)
				{
					if (ShrUnit[ShrCurrAxis] == 2)
					{
						if ((double)LngCurrStep[ShrCurrAxis] - Convert.ToDouble(sFixValue) < Math.Abs((double)LngNegaTravel[ShrCurrAxis] / DblPulseEqui[ShrCurrAxis] - (double)LngZeroOffset[ShrCurrAxis]))
						{
							if (ShrLanguage == 0)
							{
								sInfo = "最终位置小于负向行程！";
							}
							else
							{
								sInfo = "Final position is smaller than negative stroke!";
							}
							NudAddOrSubValue.Focus();
							return -1;
						}
					}
					else if (Math.Round(DblCurrPosi[ShrCurrAxis], 5) - Convert.ToDouble(sFixValue) < (double)(-LngNegaTravel[ShrCurrAxis]))
					{
						if (ShrLanguage == 0)
						{
							sInfo = "最终位置小于负向行程！";
						}
						else
						{
							sInfo = "Final position is smaller than negative stroke!";
						}
						NudAddOrSubValue.Focus();
						return -1;
					}
				}
				else if (ShrUnit[ShrCurrAxis] == 2)
				{
					if ((double)LngCurrStep[ShrCurrAxis] - Convert.ToDouble(sFixValue) < 0.0)
					{
						if (ShrLanguage == 0)
						{
							sInfo = "最终位置小于零点！";
						}
						else
						{
							sInfo = "Final position is smaller than zero position!";
						}
						NudAddOrSubValue.Focus();
						return -1;
					}
				}
				else if (Math.Round(DblCurrPosi[ShrCurrAxis], 5) - Convert.ToDouble(sFixValue) < 0.0)
				{
					if (ShrLanguage == 0)
					{
						sInfo = "最终位置小于零点！";
					}
					else
					{
						sInfo = "Final position is smaller than zero position!";
					}
					NudAddOrSubValue.Focus();
					return -1;
				}
			}
			BtnStop.Focus();
			ControlEnable(bEnable: false);
			if (ShrUnit[ShrCurrAxis] == 2)
			{
				RunToStep(ShrCurrAxis, -Convert.ToInt64(sFixValue));
			}
			else
			{
				RunToPosition(ShrCurrAxis, 0.0 - Convert.ToDouble(sFixValue));
			}
			ControlEnable(bEnable: true);
			return 1;
		}
		catch (Exception)
		{
			return -1;
		}
	}

	private void SendCommand(string CommandString)
	{
		if (SCPort.IsOpen)
		{
			SCPort.Write(CommandString);
			SCPort.DiscardOutBuffer();
		}
	}

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
			Application.DoEvents();
		}
	}

	private void DelayWait(long milliSecond)
	{
		int tickCount = Environment.TickCount;
		BlnReadCom = false;
		while (Math.Abs(Environment.TickCount - tickCount) < milliSecond)
		{
			Application.DoEvents();
		}
	}

	private short SetSpeed(short sSpeed)
	{
		short num = 0;
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
		if (sSpeed < 0 || sSpeed > 255)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("速度值只能是0到255之间的整数！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Speed value must be an integer from 0 to 255!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		if (BlnBusy)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("通讯忙，请稍候！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Busy, try later!", "Prompt", MessageBoxButtons.OK);
			}
			return -1;
		}
		try
		{
			StrReceiver = "";
			BlnBusy = true;
			BlnSet = true;
			SendCommand("V" + sSpeed + "\r");
			Delay(100000L);
			BlnBusy = false;
			num++;
			StrReceiver = "";
			BlnBusy = true;
			BlnSet = false;
			SendCommand("?V\r");
			Delay(100000L);
			BlnBusy = false;
			if (StrReceiver != "")
			{
				ShrSpeed = Convert.ToInt16(StringToLong(StrReceiver));
			}
			num++;
			for (short num2 = 0; num2 < 6; num2++)
			{
				if (ShrType[num2] != 0)
				{
					CboSpeed.Text = ShrSpeed.ToString();
					if (ShrUnit[num2] == 2)
					{
						DblSpeed[num2] = (ShrSpeed + 1) * 22000 / 720;
					}
					else
					{
						DblSpeed[num2] = (double)((ShrSpeed + 1) * 22000) * DblPulseEqui[num2] / 720.0;
					}
				}
			}
			num++;
			RefreshShow();
			return 1;
		}
		catch (Exception)
		{
			switch (num)
			{
			case 0:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数SetSpeed中“发送速度命令”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Send speed command\" in function SetSpeed goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 1:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数SetSpeed中“查询速度命令”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Query speed command\" in function SetSpeed goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 2:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数SetSpeed中“计算实际速度”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Calculate actual speed command\" in function SetSpeed goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 3:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数SetSpeed中“刷新单位和速度”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Refresh unit and speed\" in function SetSpeed goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			}
			return -1;
		}
	}

	private void ReadParam()
	{
		short num = 0;
		short num2 = 0;
		try
		{
			if (!File.Exists(Application.StartupPath + "\\34SysParam.ini"))
			{
				BlnParamFlag = false;
				return;
			}
			for (short num3 = 0; num3 < 6; num3++)
			{
				if (mMainClass.GetFromIni(StrAxisName[num3], "Type") != "defaultValue")
				{
					ShrType[num3] = Convert.ToInt16(mMainClass.GetFromIni(StrAxisName[num3], "Type"));
					ShrUnit[num3] = Convert.ToInt16(mMainClass.GetFromIni(StrAxisName[num3], "Unit"));
					FlaMotorAngle[num3] = Convert.ToSingle(mMainClass.GetFromIni(StrAxisName[num3], "MotorAngle"));
					ShrSubsection[num3] = Convert.ToInt16(mMainClass.GetFromIni(StrAxisName[num3], "Subsection"));
					FlaPitch[num3] = Convert.ToSingle(mMainClass.GetFromIni(StrAxisName[num3], "Pitch"));
					IntTranRatio[num3] = Convert.ToInt32(mMainClass.GetFromIni(StrAxisName[num3], "TranRatio"));
					DblTravel[num3] = Convert.ToSingle(mMainClass.GetFromIni(StrAxisName[num3], "Travel"));
					LngNegaTravel[num3] = Convert.ToInt64(mMainClass.GetFromIni(StrAxisName[num3], "NegaTravel"));
					LngPosiTravel[num3] = Convert.ToInt64(mMainClass.GetFromIni(StrAxisName[num3], "PosiTravel"));
					LngZeroOffset[num3] = Convert.ToInt64(mMainClass.GetFromIni(StrAxisName[num3], "ZeroOffset"));
					if (ShrType[num3] == 1)
					{
						DblPulseEqui[num3] = FlaMotorAngle[num3] * FlaPitch[num3] / (float)(360 * ShrSubsection[num3]);
					}
					else if (ShrType[num3] == 2 || ShrType[num3] == 3)
					{
						DblPulseEqui[num3] = FlaMotorAngle[num3] / (float)(IntTranRatio[num3] * ShrSubsection[num3]);
					}
					else if (ShrType[num3] == 4)
					{
						DblPulseEqui[num3] = FlaPitch[num3] / (float)IntTranRatio[num3] / (360f / FlaMotorAngle[num3] * (float)ShrSubsection[num3]);
					}
					else
					{
						DblPulseEqui[num3] = -1.0;
					}
					if (ShrType[num3] != 0)
					{
						num++;
						if (ShrUnit[num3] == 2)
						{
							DblSpeed[num3] = (ShrSpeed + 1) * 22000 / 720;
						}
						else
						{
							DblSpeed[num3] = (double)((ShrSpeed + 1) * 22000) * DblPulseEqui[num3] / 720.0;
						}
					}
				}
			}
			if (num == 0)
			{
				BlnParamFlag = false;
			}
			else
			{
				BlnParamFlag = true;
			}
			num2++;
			RefreshParam(ShrCurrAxis);
		}
		catch (Exception)
		{
			switch (num2)
			{
			case 0:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数ReadParam中“参数文件读取”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Parameter file reading\" in function ReadParam goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 1:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数ReadParam中“刷新当前参数显示”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Refresh current parameter display\" in function ReadParam goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			}
		}
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

	private void RefreshParam(short sAxis)
	{
		short num = 0;
		try
		{
			CboType.SelectedIndex = ShrType[sAxis];
			CboUnit.SelectedIndex = ShrUnit[sAxis];
			CboMotorAngle.Text = FlaMotorAngle[sAxis].ToString();
			CboSubsection.Text = ShrSubsection[sAxis].ToString();
			CboPitch.Text = FlaPitch[sAxis].ToString();
			CboTranRatio.Text = IntTranRatio[sAxis].ToString();
			CboTravel.Text = DblTravel[sAxis].ToString();
			CboNegaTravel.Text = LngNegaTravel[sAxis].ToString();
			CboPosiTravel.Text = LngPosiTravel[sAxis].ToString();
			num++;
			if (ShrType[sAxis] == 3 || ShrType[sAxis] == 1 || ShrType[sAxis] == 2)
			{
				BtnSetZero.Enabled = true;
				BtnCancelZero.Enabled = true;
			}
			else
			{
				BtnSetZero.Enabled = false;
				BtnCancelZero.Enabled = false;
			}
		}
		catch (Exception)
		{
			switch (num)
			{
			case 0:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数RefreshParam中“参数赋值”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Parameter assignment\" in function RefreshParam goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 1:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数RefreshParam中“计算脉冲当量”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Calculate pulse equivalent\" in function RefreshParam goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			}
		}
	}

	private long StringToLong(string s)
	{
		return Convert.ToInt64(Regex.Replace(StrReceiver, "[^0-9]+", ""));
	}

	private void RefreshShow()
	{
		try
		{
			BlnDonotTip = false;
			CboSpeed.Text = ShrSpeed.ToString();
			if (ShrLanguage == 0)
			{
				switch (ShrUnit[ShrCurrAxis])
				{
				case 0:
					LblCurrUnit.Text = "毫米";
					LblFixValueUnit.Text = "毫米";
					LblRunToValueUnit.Text = "毫米";
					LblCurrSpeed.Text = $"{DblSpeed[ShrCurrAxis]:0.000}" + "毫米/秒";
					break;
				case 1:
					LblCurrUnit.Text = "度";
					LblFixValueUnit.Text = "度";
					LblRunToValueUnit.Text = "度";
					LblCurrSpeed.Text = $"{DblSpeed[ShrCurrAxis]:000.000}" + "度/秒";
					break;
				case 2:
					LblCurrUnit.Text = "步";
					LblFixValueUnit.Text = "步";
					LblRunToValueUnit.Text = "步";
					LblCurrSpeed.Text = $"{DblSpeed[ShrCurrAxis]:000.000}" + "步/秒";
					break;
				}
			}
			else
			{
				switch (ShrUnit[ShrCurrAxis])
				{
				case 0:
					LblCurrUnit.Text = "mm";
					LblFixValueUnit.Text = "mm";
					LblRunToValueUnit.Text = "mm";
					LblCurrSpeed.Text = $"{DblSpeed[ShrCurrAxis]:0.000}" + "mm/s";
					break;
				case 1:
					LblCurrUnit.Text = "Degree";
					LblFixValueUnit.Text = "Degree";
					LblRunToValueUnit.Text = "Degree";
					LblCurrSpeed.Text = $"{DblSpeed[ShrCurrAxis]:000.000}" + "º/s";
					break;
				case 2:
					LblCurrUnit.Text = "Step";
					LblFixValueUnit.Text = "Step";
					LblRunToValueUnit.Text = "Step";
					LblCurrSpeed.Text = $"{DblSpeed[ShrCurrAxis]:000.000}" + "Step/s";
					break;
				}
			}
			for (short num = 0; num < 6; num++)
			{
				if (GrdParam.Left == -10000)
				{
					if (ShrType[num] != 0)
					{
						RadAxis[num].Enabled = true;
					}
					else if (ShrUseMode[num] == 1)
					{
						RadAxis[num].Enabled = true;
					}
					else
					{
						RadAxis[num].Enabled = false;
					}
				}
				else
				{
					RadAxis[num].Enabled = true;
				}
			}
			BlnDonotTip = true;
		}
		catch (Exception)
		{
			BlnDonotTip = true;
			if (ShrLanguage == 0)
			{
				MessageBox.Show("函数RefreshShow中“刷新参数”出现错误！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("\"Refresh parameters\" in function RefreshShow goes wrong!", "Prompt", MessageBoxButtons.OK);
			}
		}
	}

	private void SendRunToZeroAndShow(short sIndex, short sMode)
	{
		try
		{
			StrReceiver = "";
			BlnBusy = true;
			BlnSet = true;
			SendCommand("H" + AxisName(sIndex) + sMode + "\r");
			if (sMode == 2)
			{
				Delay(10000L);
			}
			else
			{
				LblCurrValue.Text = "...... ";
				timer1.Interval = 310 - ShrSpeed;
				timer1.Enabled = true;
				Delay(1000000L);
				timer1.Enabled = false;
			}
			BlnBusy = false;
		}
		catch (Exception)
		{
			BlnBusy = false;
			if (ShrLanguage == 0)
			{
				MessageBox.Show("函数SendRunToZeroAndShow中“归零”出现错误！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("\"Return to zero\" in function SendRunToZeroAndShow goes wrong!", "Prompt", MessageBoxButtons.OK);
			}
		}
	}

	private string AxisName(short sIndex)
	{
		return sIndex switch
		{
			0 => "X", 
			1 => "Y", 
			2 => "Z", 
			3 => "r", 
			4 => "t", 
			5 => "T", 
			_ => "", 
		};
	}

	private void ChangeLanguage()
	{
		MainClass.GetControl(this, ShrLanguage);
		if (ShrLanguage == 0)
		{
			groupBox2.Text = "移动轴";
			RadXAxis.Text = "X  轴";
			RadYAxis.Text = "Y  轴";
			RadZAxis.Text = "Z  轴";
			RadRAxis.Text = "R  轴";
			RadT1Axis.Text = "T1 轴";
			RadT2Axis.Text = "T2 轴";
			label1.Text = "当前位置";
			label2.Text = "-------------------------------------------------------------------";
			BtnFreeDown.Text = "自 由 减 少";
			BtnFreeUp.Text = "自 由 增 加";
			BtnFixSub.Text = "定值减少";
			BtnFixAdd.Text = "定值增加";
			label7.Text = "目  标  位  置";
			BtnRun.Text = "运  行";
			label4.Text = "最  大  速  度";
			BtnParamSet.Text = "参数设置";
			BtnLimitReturnZero.Text = "限位归零";
			BtnSetZero.Text = "设置零位";
			BtnCancelZero.Text = "取消零位";
			BtnStop.Text = "停   止";
			GrdParam.Text = "参数设置";
			label6.Text = "电移台类型";
			label8.Text = "运行单位";
			label9.Text = "电机度数";
			label10.Text = "细分数";
			label11.Text = "丝杆导程(平移台)";
			label12.Text = "传动比";
			label13.Text = "最大行程";
			label14.Text = "负向行程";
			label15.Text = "正向行程";
			int selectedIndex = CboType.SelectedIndex;
			CboType.Items.Clear();
			CboType.Items.Add("无");
			CboType.Items.Add("平移台");
			CboType.Items.Add("旋转台");
			CboType.Items.Add("角位移台");
			CboType.Items.Add("升降台");
			CboType.SelectedIndex = selectedIndex;
			selectedIndex = CboUnit.SelectedIndex;
			CboUnit.Items.Clear();
			CboUnit.Items.Add("毫米");
			CboUnit.Items.Add("度");
			CboUnit.Items.Add("步数");
			CboUnit.SelectedIndex = selectedIndex;
			string text = CboPitch.Text;
			CboPitch.Items.Clear();
			CboPitch.Items.Add("无");
			CboPitch.Items.Add("0.5");
			CboPitch.Items.Add("1");
			CboPitch.Items.Add("1.5");
			CboPitch.Items.Add("4");
			CboPitch.Items.Add("5");
			CboPitch.Text = text;
			text = CboTranRatio.Text;
			CboTranRatio.Items.Clear();
			CboTranRatio.Items.Add("无");
			CboTranRatio.Items.Add("6");
			CboTranRatio.Items.Add("72");
			CboTranRatio.Items.Add("90");
			CboTranRatio.Items.Add("180");
			CboTranRatio.Items.Add("252");
			CboTranRatio.Items.Add("352");
			CboTranRatio.Items.Add("360");
			CboTranRatio.Items.Add("400");
			CboTranRatio.Items.Add("576");
			CboTranRatio.Items.Add("720");
			CboTranRatio.Text = text;
			BtnOk.Text = "确   定";
			BtnClose.Text = "关   闭";
		}
		else
		{
			groupBox2.Text = "Running Axis";
			RadXAxis.Text = "X-Axis";
			RadYAxis.Text = "Y-Axis";
			RadZAxis.Text = "Z-Axis";
			RadRAxis.Text = "R-Axis";
			RadT1Axis.Text = "T1-Axis";
			RadT2Axis.Text = "T2-Axis";
			label1.Text = "Position";
			label2.Text = "----------------------------------------------------------------------------------";
			BtnFreeDown.Text = "Backward";
			BtnFreeUp.Text = "Forward";
			BtnFixSub.Text = "Decrease";
			BtnFixAdd.Text = "Increase";
			label7.Text = "Target Position";
			BtnRun.Text = "Run";
			label4.Text = "Max Speed";
			BtnParamSet.Text = "Settings";
			BtnLimitReturnZero.Text = "Return to Zero";
			BtnSetZero.Text = "Set Zero";
			BtnCancelZero.Text = "Cancel Zero";
			BtnStop.Text = "Stop";
			GrdParam.Text = "Parameter Settings";
			label6.Text = "Stage Type";
			label8.Text = "Running Unit";
			label9.Text = "Step Angle";
			label10.Text = "Subdivision";
			label11.Text = "Screw  Lead(Linear Stage)";
			label12.Text = "Transmission Ratio";
			label13.Text = "Travel Range";
			label14.Text = "Negative Travel Range";
			label15.Text = "Positive Travel Range";
			int selectedIndex = CboType.SelectedIndex;
			CboType.Items.Clear();
			CboType.Items.Add("None");
			CboType.Items.Add("Translation Stage");
			CboType.Items.Add("Rotary Stage");
			CboType.Items.Add("Goniometer Stage");
			CboType.Items.Add("Lab Jack");
			CboType.SelectedIndex = selectedIndex;
			selectedIndex = CboUnit.SelectedIndex;
			CboUnit.Items.Clear();
			CboUnit.Items.Add("mm");
			CboUnit.Items.Add("Degree");
			CboUnit.Items.Add("Step");
			CboUnit.SelectedIndex = selectedIndex;
			string text = CboPitch.Text;
			CboPitch.Items.Clear();
			CboPitch.Items.Add("None");
			CboPitch.Items.Add("0.5");
			CboPitch.Items.Add("1");
			CboPitch.Items.Add("1.5");
			CboPitch.Items.Add("4");
			CboPitch.Items.Add("5");
			CboPitch.Text = text;
			text = CboTranRatio.Text;
			CboTranRatio.Items.Clear();
			CboTranRatio.Items.Add("None");
			CboTranRatio.Items.Add("6");
			CboTranRatio.Items.Add("72");
			CboTranRatio.Items.Add("90");
			CboTranRatio.Items.Add("180");
			CboTranRatio.Items.Add("252");
			CboTranRatio.Items.Add("352");
			CboTranRatio.Items.Add("360");
			CboTranRatio.Items.Add("400");
			CboTranRatio.Items.Add("576");
			CboTranRatio.Items.Add("720");
			CboTranRatio.Text = text;
			BtnOk.Text = "Ok";
			BtnClose.Text = "Close";
		}
		RefreshShow();
	}

	private void ControlEnable(bool bEnable)
	{
		BtnFreeDown.Enabled = bEnable;
		BtnFreeUp.Enabled = bEnable;
		BtnFixAdd.Enabled = bEnable;
		BtnFixSub.Enabled = bEnable;
		BtnRun.Enabled = bEnable;
		CboSpeed.Enabled = bEnable;
		BtnParamSet.Enabled = bEnable;
		BtnLimitReturnZero.Enabled = bEnable;
	}

	private static bool IsNumber(string s)
	{
		if (string.IsNullOrWhiteSpace(s))
		{
			return false;
		}
		return new Regex("^[-+]?[0-9]+(\\.[0-9]+)?$").IsMatch(s);
	}

	private void SCPort_DataReceived(object sender, SerialDataReceivedEventArgs e)
	{
		try
		{
			string text = "";
			text = SCPort.ReadExisting();
			if (text != "")
			{
				StrReceiver += text;
			}
			if (BlnSet)
			{
				if (StrReceiver.Length == 3)
				{
					if (StrReceiver.Substring(StrReceiver.Length - 3) == "OK\n")
					{
						BlnReadCom = true;
					}
				}
				else if (StrReceiver.Length == 4)
				{
					if (StrReceiver.Substring(StrReceiver.Length - 3) == "OK\n" || StrReceiver.Substring(StrReceiver.Length - 4) == "OK\nS")
					{
						BlnReadCom = true;
					}
				}
				else if (StrReceiver.Length > 4 && (StrReceiver.Substring(StrReceiver.Length - 3) == "OK\n" || StrReceiver.Substring(StrReceiver.Length - 4) == "OK\nS" || StrReceiver.Substring(StrReceiver.Length - 5) == "ERR1\n" || StrReceiver.Substring(StrReceiver.Length - 5) == "ERR5\n"))
				{
					BlnReadCom = true;
				}
			}
			else if (StrReceiver.Length > 1 && StrReceiver.Substring(StrReceiver.Length - 1, 1) == "\n")
			{
				BlnReadCom = true;
			}
		}
		catch (Exception)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("本次接收数据出错！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Data receiving this time goes wrong!", "Prompt", MessageBoxButtons.OK);
			}
		}
	}

	private void BtnParamSet_Click(object sender, EventArgs e)
	{
		DisplayParameterInterface();
	}

	private void RadAxis_CheckedChanged(object sender, EventArgs e)
	{
		short num = 0;
		RadioButton radioButton = (RadioButton)sender;
		if (BlnBusy)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("通讯忙，请稍候！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Busy, try later!", "Prompt", MessageBoxButtons.OK);
			}
			RadAxis[ShrCurrAxis].Checked = true;
			return;
		}
		try
		{
			if (radioButton.Checked)
			{
				GetCurrAxis();
				RefreshParam(ShrCurrAxis);
				num++;
				if (ShrType[ShrCurrAxis] != 0)
				{
					RefreshCurrentPosition(ShrCurrAxis);
					RefreshShow();
				}
				RefreshShutterDisplay(ShrCurrAxis);
			}
		}
		catch (Exception)
		{
			switch (num)
			{
			case 0:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数RadAxis_CheckedChanged中“刷新参数信息”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Refresh parameter info\" in function RadAxis_CheckedChanged goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 1:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数RadAxis_CheckedChanged中“刷新当前位置”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Refresh current position\" in function RadAxis_CheckedChanged goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			}
		}
	}

	private void BtnOk_Click(object sender, EventArgs e)
	{
		short num = 0;
		try
		{
			if (CboType.SelectedIndex == -1)
			{
				if (ShrLanguage == 0)
				{
					MessageBox.Show("电移台类型只能从列表中选择！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("Choose the type of motorized positioning stage from list only!", "Prompt", MessageBoxButtons.OK);
				}
				CboType.Focus();
				return;
			}
			if (CboUnit.SelectedIndex == -1)
			{
				if (ShrLanguage == 0)
				{
					MessageBox.Show("运行单位只能从列表中选择！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("Choose operation unit from list only!", "Prompt", MessageBoxButtons.OK);
				}
				CboUnit.Focus();
				return;
			}
			if ((CboType.SelectedIndex == 2 || CboType.SelectedIndex == 3) && CboUnit.SelectedIndex == 0)
			{
				if (ShrLanguage == 0)
				{
					MessageBox.Show("旋转台和角位移台的运行单位不能为毫米！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("The running unit of rotary stage and goniometer cannot be in mm!", "Prompt", MessageBoxButtons.OK);
				}
				CboUnit.Focus();
				return;
			}
			if ((CboType.SelectedIndex == 1 || CboType.SelectedIndex == 4) && CboUnit.SelectedIndex == 1)
			{
				if (ShrLanguage == 0)
				{
					MessageBox.Show("平移台和升降台的运行单位不能为度！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("The running unit of translation stage and elevating stage cannot be in degree!", "Prompt", MessageBoxButtons.OK);
				}
				CboUnit.Focus();
				return;
			}
			if (CboMotorAngle.SelectedIndex == -1 && CboType.Text != "无" && CboType.Text != "None")
			{
				if (ShrLanguage == 0)
				{
					MessageBox.Show("电机度数只能从列表中选择！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("Choose stepping angle from list only!", "Prompt", MessageBoxButtons.OK);
				}
				CboMotorAngle.Focus();
				return;
			}
			if (CboSubsection.SelectedIndex == -1 && CboType.Text != "无" && CboType.Text != "None")
			{
				if (ShrLanguage == 0)
				{
					MessageBox.Show("细分数只能从列表中选择！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("Choose subdivision from list only!", "Prompt", MessageBoxButtons.OK);
				}
				CboSubsection.Focus();
				return;
			}
			int selectedIndex = CboType.SelectedIndex;
			if ((uint)(selectedIndex - 2) <= 2u)
			{
				if (CboTranRatio.Text == "无" || CboTranRatio.Text == "None")
				{
					if (ShrLanguage == 0)
					{
						MessageBox.Show("传动比必须为大于0的数值或者从列表中选择！", "提示", MessageBoxButtons.OK);
					}
					else
					{
						MessageBox.Show("Transmission ratio must be greater than 0 or chosen from list!", "Prompt", MessageBoxButtons.OK);
					}
					CboTranRatio.Focus();
					return;
				}
				if (CboTranRatio.SelectedIndex < 1 && Convert.ToDouble(CboTranRatio.Text) <= 0.0)
				{
					if (ShrLanguage == 0)
					{
						MessageBox.Show("传动比必须为大于0的数值或者从列表中选择！", "提示", MessageBoxButtons.OK);
					}
					else
					{
						MessageBox.Show("Transmission ratio must be greater than 0 or chosen from list!", "Prompt", MessageBoxButtons.OK);
					}
					CboTranRatio.Focus();
					return;
				}
			}
			selectedIndex = CboType.SelectedIndex;
			if (selectedIndex == 1 || selectedIndex == 4)
			{
				if (CboPitch.Text == "无" || CboPitch.Text == "None")
				{
					if (ShrLanguage == 0)
					{
						MessageBox.Show("丝杆导程必须为大于0的数值或者从列表中选择！", "提示", MessageBoxButtons.OK);
					}
					else
					{
						MessageBox.Show("Screw lead must be greater than 0 or chosen from list!", "Prompt", MessageBoxButtons.OK);
					}
					CboPitch.Focus();
					return;
				}
				if (CboPitch.SelectedIndex > CboPitch.Items.Count - 1)
				{
					if (ShrLanguage == 0)
					{
						MessageBox.Show("丝杆导程必须为大于0的数值或者从列表中选择！", "提示", MessageBoxButtons.OK);
					}
					else
					{
						MessageBox.Show("Screw lead must be greater than 0 or chosen from list!", "Prompt", MessageBoxButtons.OK);
					}
					CboPitch.Focus();
					return;
				}
				if (Convert.ToSingle(CboPitch.Text) <= 0f)
				{
					if (ShrLanguage == 0)
					{
						MessageBox.Show("丝杆导程必须为大于0的数值或者从列表中选择！", "提示", MessageBoxButtons.OK);
					}
					else
					{
						MessageBox.Show("Screw lead must be greater than 0 or chosen from list!", "Prompt", MessageBoxButtons.OK);
					}
					CboPitch.Focus();
					return;
				}
			}
			selectedIndex = CboType.SelectedIndex;
			if (selectedIndex == 1 || (uint)(selectedIndex - 3) <= 1u)
			{
				if (CboTravel.Text == "")
				{
					if (ShrLanguage == 0)
					{
						MessageBox.Show("行程不能为空！", "提示", MessageBoxButtons.OK);
					}
					else
					{
						MessageBox.Show("Stroke cannot be null!", "Prompt", MessageBoxButtons.OK);
					}
					CboTravel.Focus();
					return;
				}
				if (Convert.ToDouble(CboTravel.Text) <= 0.0)
				{
					if (ShrLanguage == 0)
					{
						MessageBox.Show("行程必须大于0！", "提示", MessageBoxButtons.OK);
					}
					else
					{
						MessageBox.Show("Stroke must be greater than 0!", "Prompt", MessageBoxButtons.OK);
					}
					CboTravel.Focus();
					return;
				}
			}
			num++;
			if ((ShrType[ShrCurrAxis] != Convert.ToInt16(CboType.SelectedIndex) && (CboType.SelectedIndex == 3 || CboType.SelectedIndex == 1 || CboType.SelectedIndex == 2)) || (CboType.SelectedIndex != 3 && CboType.SelectedIndex != 1 && CboType.SelectedIndex != 2) || (!CboNegaTravel.Enabled && (CboType.SelectedIndex == 3 || CboType.SelectedIndex == 1)))
			{
				LngZeroOffset[ShrCurrAxis] = 0L;
				mMainClass.WriteToIni(StrAxisName[ShrCurrAxis], "ZeroOffset", LngZeroOffset[ShrCurrAxis].ToString());
			}
			ShrType[ShrCurrAxis] = Convert.ToInt16(CboType.SelectedIndex);
			ShrUnit[ShrCurrAxis] = Convert.ToInt16(CboUnit.SelectedIndex);
			if (CboMotorAngle.Text != "")
			{
				FlaMotorAngle[ShrCurrAxis] = Convert.ToSingle(CboMotorAngle.Text);
			}
			if (CboSubsection.Text != "")
			{
				ShrSubsection[ShrCurrAxis] = Convert.ToInt16(CboSubsection.Text);
			}
			if (CboPitch.Text == "无" || CboPitch.Text == "None" || CboPitch.Text == "")
			{
				FlaPitch[ShrCurrAxis] = 0f;
			}
			else
			{
				FlaPitch[ShrCurrAxis] = Convert.ToSingle(CboPitch.Text);
			}
			if (CboTranRatio.Text == "无" || CboTranRatio.Text == "None" || CboTranRatio.Text == "")
			{
				IntTranRatio[ShrCurrAxis] = 0;
			}
			else
			{
				IntTranRatio[ShrCurrAxis] = Convert.ToInt32(CboTranRatio.Text);
			}
			if (CboTravel.Text != "")
			{
				DblTravel[ShrCurrAxis] = Convert.ToDouble(CboTravel.Text);
			}
			if (CboNegaTravel.Text != "")
			{
				LngNegaTravel[ShrCurrAxis] = Convert.ToInt64(CboNegaTravel.Text);
			}
			if (CboPosiTravel.Text != "")
			{
				LngPosiTravel[ShrCurrAxis] = Convert.ToInt64(CboPosiTravel.Text);
			}
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
		catch (Exception)
		{
			switch (num)
			{
			case 0:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数BtnOk_Click中“参数判断”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Parameter judgment\" in function BtnOk_Click goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			case 1:
				if (ShrLanguage == 0)
				{
					MessageBox.Show("函数BtnOk_Click中“保存参数”出现错误！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("\"Save parameters\" in function BtnOk_Click goes wrong!", "Prompt", MessageBoxButtons.OK);
				}
				break;
			}
		}
	}

	private void CboType_SelectedIndexChanged(object sender, EventArgs e)
	{
		switch (CboType.SelectedIndex)
		{
		case 0:
			CboUnit.Text = "";
			CboUnit.Enabled = false;
			CboMotorAngle.Enabled = false;
			CboSubsection.Enabled = false;
			CboPitch.Enabled = false;
			CboTranRatio.Enabled = false;
			CboTravel.Enabled = false;
			CboNegaTravel.Enabled = false;
			CboPosiTravel.Enabled = false;
			break;
		case 1:
			CboUnit.Enabled = true;
			CboMotorAngle.Enabled = true;
			CboSubsection.Enabled = true;
			CboPitch.Enabled = true;
			CboTranRatio.Enabled = false;
			if (ShrLanguage == 0)
			{
				CboTranRatio.Text = "无";
			}
			else
			{
				CboTranRatio.Text = "None";
			}
			CboTravel.Enabled = true;
			CboNegaTravel.Enabled = false;
			CboPosiTravel.Enabled = false;
			break;
		case 2:
			CboUnit.Enabled = true;
			CboMotorAngle.Enabled = true;
			CboSubsection.Enabled = true;
			CboPitch.Enabled = false;
			if (ShrLanguage == 0)
			{
				CboPitch.Text = "无";
			}
			else
			{
				CboPitch.Text = "None";
			}
			CboTranRatio.Enabled = true;
			CboTravel.Enabled = false;
			CboNegaTravel.Enabled = false;
			CboPosiTravel.Enabled = false;
			break;
		case 3:
			CboUnit.Enabled = true;
			CboMotorAngle.Enabled = true;
			CboSubsection.Enabled = true;
			CboPitch.Enabled = false;
			if (ShrLanguage == 0)
			{
				CboPitch.Text = "无";
			}
			else
			{
				CboPitch.Text = "None";
			}
			CboTranRatio.Enabled = true;
			CboTravel.Enabled = true;
			CboNegaTravel.Enabled = false;
			CboPosiTravel.Enabled = false;
			break;
		case 4:
			CboUnit.Enabled = true;
			CboMotorAngle.Enabled = true;
			CboSubsection.Enabled = true;
			CboPitch.Enabled = true;
			CboTranRatio.Enabled = true;
			CboTravel.Enabled = true;
			CboNegaTravel.Enabled = false;
			CboPosiTravel.Enabled = false;
			break;
		}
		switch (ShrType[ShrCurrAxis])
		{
		case 1:
		case 2:
		case 4:
			CboTravel.Items.Clear();
			CboTravel.Items.Add("50");
			CboTravel.Items.Add("100");
			CboTravel.Items.Add("250");
			CboTravel.Items.Add("300");
			CboTravel.Items.Add("400");
			CboTravel.Items.Add("500");
			CboTravel.Items.Add("600");
			CboTravel.Items.Add("850");
			CboTravel.Items.Add("1000");
			break;
		case 3:
			CboTravel.Items.Clear();
			CboTravel.Items.Add("25");
			CboTravel.Items.Add("35");
			break;
		}
	}

	private void BtnClose_Click(object sender, EventArgs e)
	{
		GrdParam.Left = -10000;
		RefreshShow();
	}

	private void CboSpeed_SelectedIndexChanged(object sender, EventArgs e)
	{
		if (!BlnDonotTip)
		{
			return;
		}
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
			CboSpeed.Text = ShrSpeed.ToString();
			CboSpeed.Focus();
		}
		else if (BlnBusy)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("通讯忙，请稍候！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Busy, try later!", "Prompt", MessageBoxButtons.OK);
			}
			CboSpeed.Text = ShrSpeed.ToString();
			CboSpeed.Focus();
		}
		else if (CboSpeed.SelectedIndex == -1)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("请从列表中选择速度值！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Choose speed from list!", "Prompt", MessageBoxButtons.OK);
			}
			CboSpeed.Focus();
		}
		else
		{
			SetSpeed(Convert.ToInt16(CboSpeed.Text));
		}
	}

	private void CboTravel_Validating(object sender, CancelEventArgs e)
	{
		if (!IsNumber(CboTravel.Text))
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("行程必须为数字，请修改！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Stroke must be number, pls modify!", "Prompt", MessageBoxButtons.OK);
			}
			e.Cancel = true;
			CboTravel.Focus();
		}
		else if (Convert.ToInt64(CboTravel.Text) <= 0)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("行程必须为大于0的数字，请修改！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Travel must be a number greater than 0, please modify!", "Prompt", MessageBoxButtons.OK);
			}
			e.Cancel = true;
			CboTravel.Focus();
		}
	}

	private void CboNegaTravel_Validating(object sender, CancelEventArgs e)
	{
		if (!IsNumber(CboNegaTravel.Text))
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("负向行程必须为数字，请修改！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Negative stroke must be number, pls modify!", "Prompt", MessageBoxButtons.OK);
			}
			e.Cancel = true;
			CboNegaTravel.Focus();
		}
		else if (Convert.ToInt64(CboNegaTravel.Text) <= 0)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("负向行程必须为大于0的数字，请修改！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Negative travel must be a number greater than 0, please modify!", "Prompt", MessageBoxButtons.OK);
			}
			e.Cancel = true;
			CboNegaTravel.Focus();
		}
	}

	private void CboPosiTravel_Validating(object sender, CancelEventArgs e)
	{
		if (!IsNumber(CboPosiTravel.Text))
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("正向行程必须为数字，请修改！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Positive stroke must be number, pls modify!", "Prompt", MessageBoxButtons.OK);
			}
			e.Cancel = true;
			CboPosiTravel.Focus();
		}
		else if (Convert.ToInt64(CboPosiTravel.Text) <= 0)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("正向行程必须为大于0的数字，请修改！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Positive stroke must be greater than 0, pls modify!", "Prompt", MessageBoxButtons.OK);
			}
			e.Cancel = true;
			CboPosiTravel.Focus();
		}
	}

	private void CboPitch_Validating(object sender, CancelEventArgs e)
	{
		if (!(CboPitch.Text == "无") && !(CboPitch.Text == "None") && !IsNumber(CboPitch.Text))
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("丝杆导程必须为数字，请修改！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Screw lead must be number, pls modify!", "Prompt", MessageBoxButtons.OK);
			}
			e.Cancel = true;
			CboPitch.Focus();
		}
	}

	private void CboTranRatio_Validating(object sender, CancelEventArgs e)
	{
		if (!(CboTranRatio.Text == "无") && !(CboTranRatio.Text == "None") && !IsNumber(CboTranRatio.Text))
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("传动比必须为数字，请修改！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Transmission ratio must be number, pls modify!", "Prompt", MessageBoxButtons.OK);
			}
			e.Cancel = true;
			CboTranRatio.Focus();
		}
	}

	private void timer1_Tick(object sender, EventArgs e)
	{
		if (BlnReadCom)
		{
			timer1.Enabled = false;
			return;
		}
		string text = LblCurrValue.Text;
		LblCurrValue.Text = text.Substring(text.Length - 1, 1) + text.Substring(0, text.Length - 1);
	}

	private void BtnRun_Click(object sender, EventArgs e)
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
		if (BlnBusy)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("通讯忙，请稍候！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Busy, try later!", "Prompt", MessageBoxButtons.OK);
			}
			return;
		}
		if (!BlnParamFlag)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("请先设置参数，再使用！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Set parameters before use!", "Prompt", MessageBoxButtons.OK);
			}
			return;
		}
		if (!IsNumber(NudRunToValue.Text))
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("请输入数值！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Pls enter value!", "Prompt", MessageBoxButtons.OK);
			}
			NudRunToValue.Focus();
			return;
		}
		if (ShrType[ShrCurrAxis] == 4 || ((ShrType[ShrCurrAxis] == 3 || ShrType[ShrCurrAxis] == 1) && LngZeroOffset[ShrCurrAxis] == 0L))
		{
			if (ShrUnit[ShrCurrAxis] == 2)
			{
				if (Convert.ToDouble(NudRunToValue.Value) < 0.0 || Convert.ToDouble(NudRunToValue.Value) > DblTravel[ShrCurrAxis] / DblPulseEqui[ShrCurrAxis])
				{
					if (ShrLanguage == 0)
					{
						MessageBox.Show("目标位置必须大于0且小于最大行程！", "提示", MessageBoxButtons.OK);
					}
					else
					{
						MessageBox.Show("Target position must be greater than 0 and smaller than max. stroke!", "Prompt", MessageBoxButtons.OK);
					}
					NudRunToValue.Focus();
					return;
				}
			}
			else if (Convert.ToDouble(NudRunToValue.Value) < 0.0 || Convert.ToDouble(NudRunToValue.Value) > DblTravel[ShrCurrAxis])
			{
				if (ShrLanguage == 0)
				{
					MessageBox.Show("目标位置必须大于0且小于最大行程！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("Target position must be greater than 0 and smaller than max. stroke!", "Prompt", MessageBoxButtons.OK);
				}
				NudRunToValue.Focus();
				return;
			}
		}
		if ((ShrType[ShrCurrAxis] == 3 || ShrType[ShrCurrAxis] == 1 || ShrType[ShrCurrAxis] == 2) && LngZeroOffset[ShrCurrAxis] != 0L)
		{
			if (ShrType[ShrCurrAxis] == 3 || ShrType[ShrCurrAxis] == 1)
			{
				if (ShrUnit[ShrCurrAxis] == 2)
				{
					if (Convert.ToDouble(NudRunToValue.Value) < Math.Abs((double)LngNegaTravel[ShrCurrAxis] / DblPulseEqui[ShrCurrAxis] - (double)LngZeroOffset[ShrCurrAxis]) || Convert.ToDouble(NudRunToValue.Value) > (double)LngPosiTravel[ShrCurrAxis] / DblPulseEqui[ShrCurrAxis] + (double)LngZeroOffset[ShrCurrAxis])
					{
						if (ShrLanguage == 0)
						{
							MessageBox.Show("目标位置必须大于等于负向行程且小于等于正向行程！", "提示", MessageBoxButtons.OK);
						}
						else
						{
							MessageBox.Show("Target position must be ≥ negative stroke and ≤positive stroke!", "Prompt", MessageBoxButtons.OK);
						}
						NudRunToValue.Focus();
						return;
					}
				}
				else if (Convert.ToDouble(NudRunToValue.Value) < (double)(-LngNegaTravel[ShrCurrAxis]) || Convert.ToDouble(NudRunToValue.Value) > (double)LngPosiTravel[ShrCurrAxis])
				{
					if (ShrLanguage == 0)
					{
						MessageBox.Show("目标位置必须大于等于负向行程且小于等于正向行程！", "提示", MessageBoxButtons.OK);
					}
					else
					{
						MessageBox.Show("Target position must be ≥ negative stroke and ≤positive stroke!", "Prompt", MessageBoxButtons.OK);
					}
					NudRunToValue.Focus();
					return;
				}
			}
			else if (Convert.ToDouble(NudRunToValue.Value) < 0.0)
			{
				if (ShrLanguage == 0)
				{
					MessageBox.Show("目标位置必须大于0！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("Target position must be greater than 0!", "Prompt", MessageBoxButtons.OK);
				}
				NudRunToValue.Focus();
				return;
			}
		}
		BtnStop.Focus();
		ControlEnable(bEnable: false);
		if (ShrUnit[ShrCurrAxis] == 2)
		{
			RunToStep(ShrCurrAxis, Convert.ToInt64(Convert.ToDouble(NudRunToValue.Value) - (double)LngCurrStep[ShrCurrAxis]));
		}
		else
		{
			RunToPosition(ShrCurrAxis, Convert.ToDouble(NudRunToValue.Value) - DblCurrPosi[ShrCurrAxis]);
		}
		ControlEnable(bEnable: true);
	}

	private void BtnFreeUp_Click(object sender, EventArgs e)
	{
		string sInfo = "";
		if (FreeUp(ref sInfo) == -1)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show(sInfo, "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show(sInfo, "Prompt", MessageBoxButtons.OK);
			}
		}
	}

	private void BtnFreeDown_Click(object sender, EventArgs e)
	{
		string sInfo = "";
		if (FreeDown(ref sInfo) == -1)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show(sInfo, "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show(sInfo, "Prompt", MessageBoxButtons.OK);
			}
		}
	}

	private void BtnFixAdd_Click(object sender, EventArgs e)
	{
		string sInfo = "";
		if (FixIncrease(NudAddOrSubValue.Value.ToString(), ref sInfo) == -1)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show(sInfo, "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show(sInfo, "Prompt", MessageBoxButtons.OK);
			}
		}
	}

	private void BtnFixSub_Click(object sender, EventArgs e)
	{
		string sInfo = "";
		if (FixDecrease(NudAddOrSubValue.Value.ToString(), ref sInfo) == -1)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show(sInfo, "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show(sInfo, "Prompt", MessageBoxButtons.OK);
			}
		}
	}

	private void BtnLimitReturnZero_Click(object sender, EventArgs e)
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
		if (BlnBusy)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("通讯忙，请稍候！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Busy, try later!", "Prompt", MessageBoxButtons.OK);
			}
			return;
		}
		if (!BlnParamFlag)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("请先设置参数，再使用！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Set parameters before use!", "Prompt", MessageBoxButtons.OK);
			}
			return;
		}
		DialogResult dialogResult;
		if (ShrType[ShrCurrAxis] == 2)
		{
			dialogResult = ((ShrLanguage != 0) ? MessageBox.Show("Does the rotary stage have zero position?", "Prompt", MessageBoxButtons.YesNo) : MessageBox.Show("这个旋转台有零位吗？", "提示", MessageBoxButtons.YesNo));
			if (dialogResult == DialogResult.No)
			{
				if (ShrLanguage == 0)
				{
					MessageBox.Show("没有零位的旋转台归零没有实际意义！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("Zero return for rotary stage with no zero position is meaningless!", "Prompt", MessageBoxButtons.OK);
				}
				return;
			}
		}
		dialogResult = ((ShrLanguage != 0) ? MessageBox.Show("Return to current position after zero return?", "Prompt", MessageBoxButtons.YesNoCancel) : MessageBox.Show("归零后是否还回到当前位置？", "提示", MessageBoxButtons.YesNoCancel));
		if (dialogResult != DialogResult.Cancel)
		{
			ControlEnable(bEnable: false);
			switch (dialogResult)
			{
			case DialogResult.Yes:
				RunToZero(ShrCurrAxis, 1);
				break;
			case DialogResult.No:
				RunToZero(ShrCurrAxis, 0);
				break;
			}
			ControlEnable(bEnable: true);
		}
	}

	private void BtnStop_Click(object sender, EventArgs e)
	{
		StopRun();
		BlnStopCommand = true;
	}

	private void BtnSetZero_Click(object sender, EventArgs e)
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
		if (BlnBusy)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("通讯忙，请稍候！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Busy, try later!", "Prompt", MessageBoxButtons.OK);
			}
			return;
		}
		if (!BlnParamFlag)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("请先设置参数，再使用！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Set parameters before use!", "Prompt", MessageBoxButtons.OK);
			}
			return;
		}
		DialogResult dialogResult;
		if (ShrType[ShrCurrAxis] == 2)
		{
			dialogResult = ((ShrLanguage != 0) ? MessageBox.Show("Does the rotary stage have zero position?", "Prompt", MessageBoxButtons.YesNo) : MessageBox.Show("这个旋转台有零位吗？", "提示", MessageBoxButtons.YesNo));
			if (dialogResult == DialogResult.No)
			{
				if (ShrLanguage == 0)
				{
					MessageBox.Show("没有零位的旋转台无法设置软零位！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("Rotary stage  without zero position cannot set soft zero position!", "Prompt", MessageBoxButtons.OK);
				}
				return;
			}
		}
		if (ShrType[ShrCurrAxis] != 3 && ShrType[ShrCurrAxis] != 1 && ShrType[ShrCurrAxis] != 2)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("只有平移台、旋转台和角位移台可以设置零位！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Zero position can be set for translation stage,rotary stage and goniometer only!", "Prompt", MessageBoxButtons.OK);
			}
			return;
		}
		dialogResult = ((ShrLanguage != 0) ? MessageBox.Show("Are you sure to set current position as zero reference?", "Prompt", MessageBoxButtons.YesNo) : MessageBox.Show("确定将当前位置设置为参考零位吗？", "提示", MessageBoxButtons.YesNo));
		if (dialogResult != DialogResult.Yes)
		{
			return;
		}
		LngZeroOffset[ShrCurrAxis] = LngCurrStep[ShrCurrAxis] + LngZeroOffset[ShrCurrAxis];
		mMainClass.WriteToIni(StrAxisName[ShrCurrAxis], "ZeroOffset", LngZeroOffset[ShrCurrAxis].ToString());
		if (ShrType[ShrCurrAxis] == 3 || ShrType[ShrCurrAxis] == 1)
		{
			GrdParam.Left = groupBox2.Left + groupBox2.Width + 15;
			GrdParam.Top = groupBox2.Top;
			GrdParam.BringToFront();
			CboTravel.Enabled = false;
			CboPosiTravel.Enabled = true;
			CboNegaTravel.Enabled = true;
			if (ShrType[ShrCurrAxis] == 3)
			{
				if (ShrLanguage == 0)
				{
					MessageBox.Show("请重新设置角位移台的正、负行程！", "提示", MessageBoxButtons.OK);
				}
				else
				{
					MessageBox.Show("Pls reset positive and negative strokes of goniometer!", "Prompt", MessageBoxButtons.OK);
				}
			}
			else if (ShrLanguage == 0)
			{
				MessageBox.Show("请重新设置平移台的正、负行程！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Pls reset positive and negative strokes of translation stage!", "Prompt", MessageBoxButtons.OK);
			}
		}
		else
		{
			RefreshCurrentPosition(ShrCurrAxis);
		}
	}

	private void BtnCancelZero_Click(object sender, EventArgs e)
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
		if (BlnBusy)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("通讯忙，请稍候！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Busy, try later!", "Prompt", MessageBoxButtons.OK);
			}
			return;
		}
		if (!BlnParamFlag)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("请先设置参数，再使用！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Set parameters before use!", "Prompt", MessageBoxButtons.OK);
			}
			return;
		}
		if (ShrType[ShrCurrAxis] != 3 && ShrType[ShrCurrAxis] != 1 && ShrType[ShrCurrAxis] != 2)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("只有平移台、旋转台和角位移台可以取消零位！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Zero position can be cancelled for translation stage,rotary stage and goniometer only!", "Prompt", MessageBoxButtons.OK);
			}
			return;
		}
		LngZeroOffset[ShrCurrAxis] = 0L;
		mMainClass.WriteToIni(StrAxisName[ShrCurrAxis], "ZeroOffset", LngZeroOffset[ShrCurrAxis].ToString());
		if (ShrType[ShrCurrAxis] != 3 && ShrType[ShrCurrAxis] != 1)
		{
			return;
		}
		GrdParam.Left = groupBox2.Left + groupBox2.Width + 15;
		GrdParam.Top = groupBox2.Top;
		GrdParam.BringToFront();
		CboTravel.Enabled = true;
		CboPosiTravel.Enabled = false;
		CboNegaTravel.Enabled = false;
		if (ShrType[ShrCurrAxis] == 3)
		{
			if (ShrLanguage == 0)
			{
				MessageBox.Show("请重新设置角位移台的行程！", "提示", MessageBoxButtons.OK);
			}
			else
			{
				MessageBox.Show("Pls reset stroke of goniometer!", "Prompt", MessageBoxButtons.OK);
			}
		}
		else if (ShrLanguage == 0)
		{
			MessageBox.Show("请重新设置平移台的行程！", "提示", MessageBoxButtons.OK);
		}
		else
		{
			MessageBox.Show("Pls reset stroke of translation stage!", "Prompt", MessageBoxButtons.OK);
		}
	}

	private void SCU_Load(object sender, EventArgs e)
	{
		GrdParam.Left = -10000;
	}

	private short RefreshShutterDisplay(short sIndex)
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
			return -1;
		}
		if (ShrUseMode[sIndex] != 1)
		{
			label1.Visible = true;
			LblCurrValue.Visible = true;
			LblCurrUnit.Visible = true;
			label2.Visible = true;
			BtnFixSub.Visible = true;
			NudAddOrSubValue.Visible = true;
			LblFixValueUnit.Visible = true;
			BtnFixAdd.Visible = true;
			label7.Visible = true;
			NudRunToValue.Visible = true;
			LblRunToValueUnit.Visible = true;
			BtnRun.Visible = true;
			label4.Visible = true;
			CboSpeed.Visible = true;
			LblCurrSpeed.Visible = true;
			BtnParamSet.Visible = true;
			BtnLimitReturnZero.Visible = true;
			BtnSetZero.Visible = true;
			BtnCancelZero.Visible = true;
			BtnStop.Visible = true;
			if (ShrLanguage == 0)
			{
				BtnFreeDown.Text = "自 由 减 少";
				BtnFreeUp.Text = "自 由 增 加";
			}
			else
			{
				BtnFreeDown.Text = "Backward";
				BtnFreeUp.Text = "Forward";
			}
		}
		else
		{
			label1.Visible = false;
			LblCurrValue.Visible = false;
			LblCurrUnit.Visible = false;
			label2.Visible = false;
			BtnFixSub.Visible = false;
			NudAddOrSubValue.Visible = false;
			LblFixValueUnit.Visible = false;
			BtnFixAdd.Visible = false;
			label7.Visible = false;
			NudRunToValue.Visible = false;
			LblRunToValueUnit.Visible = false;
			BtnRun.Visible = false;
			label4.Visible = false;
			CboSpeed.Visible = false;
			LblCurrSpeed.Visible = false;
			BtnParamSet.Visible = false;
			BtnLimitReturnZero.Visible = false;
			BtnSetZero.Visible = false;
			BtnCancelZero.Visible = false;
			BtnStop.Visible = false;
			if (ShrLanguage == 0)
			{
				BtnFreeDown.Text = "关 闭 快 门";
				BtnFreeUp.Text = "打 开 快 门";
			}
			else
			{
				BtnFreeDown.Text = "Close Shutter";
				BtnFreeUp.Text = "Open Shutter";
			}
		}
		return 1;
	}

	protected override void Dispose(bool disposing)
	{
		if (disposing && components != null)
		{
			components.Dispose();
		}
		base.Dispose(disposing);
	}

	private void InitializeComponent()
	{
		this.components = new System.ComponentModel.Container();
		this.BtnFreeUp = new System.Windows.Forms.Button();
		this.groupBox2 = new System.Windows.Forms.GroupBox();
		this.RadXAxis = new System.Windows.Forms.RadioButton();
		this.RadT2Axis = new System.Windows.Forms.RadioButton();
		this.RadT1Axis = new System.Windows.Forms.RadioButton();
		this.RadRAxis = new System.Windows.Forms.RadioButton();
		this.RadZAxis = new System.Windows.Forms.RadioButton();
		this.RadYAxis = new System.Windows.Forms.RadioButton();
		this.BtnRun = new System.Windows.Forms.Button();
		this.BtnLimitReturnZero = new System.Windows.Forms.Button();
		this.label7 = new System.Windows.Forms.Label();
		this.BtnFreeDown = new System.Windows.Forms.Button();
		this.NudRunToValue = new System.Windows.Forms.NumericUpDown();
		this.BtnFixSub = new System.Windows.Forms.Button();
		this.BtnStop = new System.Windows.Forms.Button();
		this.BtnFixAdd = new System.Windows.Forms.Button();
		this.LblRunToValueUnit = new System.Windows.Forms.Label();
		this.LblFixValueUnit = new System.Windows.Forms.Label();
		this.BtnSetZero = new System.Windows.Forms.Button();
		this.NudAddOrSubValue = new System.Windows.Forms.NumericUpDown();
		this.label1 = new System.Windows.Forms.Label();
		this.LblCurrValue = new System.Windows.Forms.Label();
		this.LblCurrUnit = new System.Windows.Forms.Label();
		this.BtnCancelZero = new System.Windows.Forms.Button();
		this.label4 = new System.Windows.Forms.Label();
		this.LblCurrSpeed = new System.Windows.Forms.Label();
		this.BtnParamSet = new System.Windows.Forms.Button();
		this.CboType = new System.Windows.Forms.ComboBox();
		this.label6 = new System.Windows.Forms.Label();
		this.CboUnit = new System.Windows.Forms.ComboBox();
		this.label8 = new System.Windows.Forms.Label();
		this.CboMotorAngle = new System.Windows.Forms.ComboBox();
		this.label9 = new System.Windows.Forms.Label();
		this.CboSubsection = new System.Windows.Forms.ComboBox();
		this.label10 = new System.Windows.Forms.Label();
		this.CboPitch = new System.Windows.Forms.ComboBox();
		this.label11 = new System.Windows.Forms.Label();
		this.CboTranRatio = new System.Windows.Forms.ComboBox();
		this.label12 = new System.Windows.Forms.Label();
		this.CboTravel = new System.Windows.Forms.ComboBox();
		this.label13 = new System.Windows.Forms.Label();
		this.CboNegaTravel = new System.Windows.Forms.ComboBox();
		this.label14 = new System.Windows.Forms.Label();
		this.CboPosiTravel = new System.Windows.Forms.ComboBox();
		this.label15 = new System.Windows.Forms.Label();
		this.GrdParam = new System.Windows.Forms.GroupBox();
		this.BtnClose = new System.Windows.Forms.Button();
		this.BtnOk = new System.Windows.Forms.Button();
		this.CboSpeed = new System.Windows.Forms.ComboBox();
		this.timer1 = new System.Windows.Forms.Timer(this.components);
		this.label2 = new System.Windows.Forms.Label();
		this.groupBox2.SuspendLayout();
		((System.ComponentModel.ISupportInitialize)this.NudRunToValue).BeginInit();
		((System.ComponentModel.ISupportInitialize)this.NudAddOrSubValue).BeginInit();
		this.GrdParam.SuspendLayout();
		base.SuspendLayout();
		this.BtnFreeUp.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.BtnFreeUp.Location = new System.Drawing.Point(305, 100);
		this.BtnFreeUp.Name = "BtnFreeUp";
		this.BtnFreeUp.Size = new System.Drawing.Size(141, 34);
		this.BtnFreeUp.TabIndex = 31;
		this.BtnFreeUp.Text = "自 由 增 加";
		this.BtnFreeUp.UseVisualStyleBackColor = true;
		this.BtnFreeUp.Click += new System.EventHandler(BtnFreeUp_Click);
		this.groupBox2.Controls.Add(this.RadXAxis);
		this.groupBox2.Controls.Add(this.RadT2Axis);
		this.groupBox2.Controls.Add(this.RadT1Axis);
		this.groupBox2.Controls.Add(this.RadRAxis);
		this.groupBox2.Controls.Add(this.RadZAxis);
		this.groupBox2.Controls.Add(this.RadYAxis);
		this.groupBox2.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.groupBox2.Location = new System.Drawing.Point(3, 3);
		this.groupBox2.Name = "groupBox2";
		this.groupBox2.Size = new System.Drawing.Size(95, 356);
		this.groupBox2.TabIndex = 34;
		this.groupBox2.TabStop = false;
		this.groupBox2.Text = "移动轴";
		this.RadXAxis.Checked = true;
		this.RadXAxis.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.RadXAxis.Location = new System.Drawing.Point(15, 43);
		this.RadXAxis.Name = "RadXAxis";
		this.RadXAxis.Size = new System.Drawing.Size(77, 22);
		this.RadXAxis.TabIndex = 0;
		this.RadXAxis.TabStop = true;
		this.RadXAxis.Text = "X  轴";
		this.RadXAxis.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
		this.RadXAxis.UseVisualStyleBackColor = true;
		this.RadXAxis.CheckedChanged += new System.EventHandler(RadAxis_CheckedChanged);
		this.RadT2Axis.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.RadT2Axis.Location = new System.Drawing.Point(15, 298);
		this.RadT2Axis.Name = "RadT2Axis";
		this.RadT2Axis.Size = new System.Drawing.Size(77, 22);
		this.RadT2Axis.TabIndex = 0;
		this.RadT2Axis.Text = "T2 轴";
		this.RadT2Axis.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
		this.RadT2Axis.UseVisualStyleBackColor = true;
		this.RadT2Axis.CheckedChanged += new System.EventHandler(RadAxis_CheckedChanged);
		this.RadT1Axis.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.RadT1Axis.Location = new System.Drawing.Point(15, 247);
		this.RadT1Axis.Name = "RadT1Axis";
		this.RadT1Axis.Size = new System.Drawing.Size(77, 22);
		this.RadT1Axis.TabIndex = 0;
		this.RadT1Axis.Text = "T1 轴";
		this.RadT1Axis.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
		this.RadT1Axis.UseVisualStyleBackColor = true;
		this.RadT1Axis.CheckedChanged += new System.EventHandler(RadAxis_CheckedChanged);
		this.RadRAxis.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.RadRAxis.Location = new System.Drawing.Point(15, 196);
		this.RadRAxis.Name = "RadRAxis";
		this.RadRAxis.Size = new System.Drawing.Size(77, 22);
		this.RadRAxis.TabIndex = 0;
		this.RadRAxis.Text = "R  轴";
		this.RadRAxis.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
		this.RadRAxis.UseVisualStyleBackColor = true;
		this.RadRAxis.CheckedChanged += new System.EventHandler(RadAxis_CheckedChanged);
		this.RadZAxis.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.RadZAxis.Location = new System.Drawing.Point(15, 145);
		this.RadZAxis.Name = "RadZAxis";
		this.RadZAxis.Size = new System.Drawing.Size(77, 22);
		this.RadZAxis.TabIndex = 0;
		this.RadZAxis.Text = "Z  轴";
		this.RadZAxis.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
		this.RadZAxis.UseVisualStyleBackColor = true;
		this.RadZAxis.CheckedChanged += new System.EventHandler(RadAxis_CheckedChanged);
		this.RadYAxis.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.RadYAxis.Location = new System.Drawing.Point(15, 94);
		this.RadYAxis.Name = "RadYAxis";
		this.RadYAxis.Size = new System.Drawing.Size(77, 22);
		this.RadYAxis.TabIndex = 0;
		this.RadYAxis.Text = "Y  轴";
		this.RadYAxis.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
		this.RadYAxis.UseVisualStyleBackColor = true;
		this.RadYAxis.CheckedChanged += new System.EventHandler(RadAxis_CheckedChanged);
		this.BtnRun.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.BtnRun.Location = new System.Drawing.Point(366, 230);
		this.BtnRun.Name = "BtnRun";
		this.BtnRun.Size = new System.Drawing.Size(80, 34);
		this.BtnRun.TabIndex = 22;
		this.BtnRun.Text = "运  行";
		this.BtnRun.UseVisualStyleBackColor = true;
		this.BtnRun.Click += new System.EventHandler(BtnRun_Click);
		this.BtnLimitReturnZero.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.BtnLimitReturnZero.Location = new System.Drawing.Point(472, 100);
		this.BtnLimitReturnZero.Name = "BtnLimitReturnZero";
		this.BtnLimitReturnZero.Size = new System.Drawing.Size(125, 34);
		this.BtnLimitReturnZero.TabIndex = 33;
		this.BtnLimitReturnZero.Text = "限位归零";
		this.BtnLimitReturnZero.UseVisualStyleBackColor = true;
		this.BtnLimitReturnZero.Click += new System.EventHandler(BtnLimitReturnZero_Click);
		this.label7.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.label7.Location = new System.Drawing.Point(119, 234);
		this.label7.Name = "label7";
		this.label7.Size = new System.Drawing.Size(116, 23);
		this.label7.TabIndex = 21;
		this.label7.Text = "目  标  位  置";
		this.label7.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
		this.BtnFreeDown.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.BtnFreeDown.Location = new System.Drawing.Point(119, 100);
		this.BtnFreeDown.Name = "BtnFreeDown";
		this.BtnFreeDown.Size = new System.Drawing.Size(141, 34);
		this.BtnFreeDown.TabIndex = 32;
		this.BtnFreeDown.Text = "自 由 减 少";
		this.BtnFreeDown.UseVisualStyleBackColor = true;
		this.BtnFreeDown.Click += new System.EventHandler(BtnFreeDown_Click);
		this.NudRunToValue.DecimalPlaces = 5;
		this.NudRunToValue.Font = new System.Drawing.Font("微软雅黑", 10.5f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.NudRunToValue.Location = new System.Drawing.Point(235, 235);
		this.NudRunToValue.Maximum = new decimal(new int[4] { -727379968, 232, 0, 0 });
		this.NudRunToValue.Minimum = new decimal(new int[4] { -727379968, 232, 0, -2147483648 });
		this.NudRunToValue.Name = "NudRunToValue";
		this.NudRunToValue.Size = new System.Drawing.Size(89, 26);
		this.NudRunToValue.TabIndex = 23;
		this.BtnFixSub.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.BtnFixSub.Location = new System.Drawing.Point(119, 165);
		this.BtnFixSub.Name = "BtnFixSub";
		this.BtnFixSub.Size = new System.Drawing.Size(80, 34);
		this.BtnFixSub.TabIndex = 30;
		this.BtnFixSub.Text = "定值减少";
		this.BtnFixSub.UseVisualStyleBackColor = true;
		this.BtnFixSub.Click += new System.EventHandler(BtnFixSub_Click);
		this.BtnStop.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.BtnStop.Location = new System.Drawing.Point(472, 295);
		this.BtnStop.Name = "BtnStop";
		this.BtnStop.Size = new System.Drawing.Size(125, 34);
		this.BtnStop.TabIndex = 24;
		this.BtnStop.Text = "停   止";
		this.BtnStop.UseVisualStyleBackColor = true;
		this.BtnStop.Click += new System.EventHandler(BtnStop_Click);
		this.BtnFixAdd.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.BtnFixAdd.Location = new System.Drawing.Point(366, 165);
		this.BtnFixAdd.Name = "BtnFixAdd";
		this.BtnFixAdd.Size = new System.Drawing.Size(80, 34);
		this.BtnFixAdd.TabIndex = 29;
		this.BtnFixAdd.Text = "定值增加";
		this.BtnFixAdd.UseVisualStyleBackColor = true;
		this.BtnFixAdd.Click += new System.EventHandler(BtnFixAdd_Click);
		this.LblRunToValueUnit.AutoSize = true;
		this.LblRunToValueUnit.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.LblRunToValueUnit.Location = new System.Drawing.Point(327, 240);
		this.LblRunToValueUnit.Name = "LblRunToValueUnit";
		this.LblRunToValueUnit.Size = new System.Drawing.Size(33, 19);
		this.LblRunToValueUnit.TabIndex = 25;
		this.LblRunToValueUnit.Text = "mm";
		this.LblFixValueUnit.AutoSize = true;
		this.LblFixValueUnit.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.LblFixValueUnit.Location = new System.Drawing.Point(327, 176);
		this.LblFixValueUnit.Name = "LblFixValueUnit";
		this.LblFixValueUnit.Size = new System.Drawing.Size(33, 19);
		this.LblFixValueUnit.TabIndex = 28;
		this.LblFixValueUnit.Text = "mm";
		this.BtnSetZero.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.BtnSetZero.Location = new System.Drawing.Point(472, 165);
		this.BtnSetZero.Name = "BtnSetZero";
		this.BtnSetZero.Size = new System.Drawing.Size(125, 34);
		this.BtnSetZero.TabIndex = 26;
		this.BtnSetZero.Text = "设置零位";
		this.BtnSetZero.UseVisualStyleBackColor = true;
		this.BtnSetZero.Click += new System.EventHandler(BtnSetZero_Click);
		this.NudAddOrSubValue.DecimalPlaces = 5;
		this.NudAddOrSubValue.Font = new System.Drawing.Font("微软雅黑", 10.5f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.NudAddOrSubValue.Location = new System.Drawing.Point(235, 171);
		this.NudAddOrSubValue.Maximum = new decimal(new int[4] { -727379968, 232, 0, 0 });
		this.NudAddOrSubValue.Minimum = new decimal(new int[4] { -727379968, 232, 0, -2147483648 });
		this.NudAddOrSubValue.Name = "NudAddOrSubValue";
		this.NudAddOrSubValue.Size = new System.Drawing.Size(89, 26);
		this.NudAddOrSubValue.TabIndex = 27;
		this.label1.AutoSize = true;
		this.label1.Font = new System.Drawing.Font("微软雅黑", 15f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.label1.Location = new System.Drawing.Point(119, 30);
		this.label1.Name = "label1";
		this.label1.Size = new System.Drawing.Size(92, 27);
		this.label1.TabIndex = 35;
		this.label1.Text = "当前位置";
		this.LblCurrValue.Font = new System.Drawing.Font("微软雅黑", 32.25f, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, 134);
		this.LblCurrValue.ForeColor = System.Drawing.Color.FromArgb(0, 192, 0);
		this.LblCurrValue.Location = new System.Drawing.Point(217, 7);
		this.LblCurrValue.Name = "LblCurrValue";
		this.LblCurrValue.Size = new System.Drawing.Size(178, 64);
		this.LblCurrValue.TabIndex = 36;
		this.LblCurrValue.Text = "0";
		this.LblCurrValue.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
		this.LblCurrUnit.AutoSize = true;
		this.LblCurrUnit.Font = new System.Drawing.Font("微软雅黑", 15f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.LblCurrUnit.Location = new System.Drawing.Point(397, 30);
		this.LblCurrUnit.Name = "LblCurrUnit";
		this.LblCurrUnit.Size = new System.Drawing.Size(52, 27);
		this.LblCurrUnit.TabIndex = 37;
		this.LblCurrUnit.Text = "毫米";
		this.BtnCancelZero.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.BtnCancelZero.Location = new System.Drawing.Point(472, 230);
		this.BtnCancelZero.Name = "BtnCancelZero";
		this.BtnCancelZero.Size = new System.Drawing.Size(125, 34);
		this.BtnCancelZero.TabIndex = 38;
		this.BtnCancelZero.Text = "取消零位";
		this.BtnCancelZero.UseVisualStyleBackColor = true;
		this.BtnCancelZero.Click += new System.EventHandler(BtnCancelZero_Click);
		this.label4.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.label4.Location = new System.Drawing.Point(119, 301);
		this.label4.Name = "label4";
		this.label4.Size = new System.Drawing.Size(116, 23);
		this.label4.TabIndex = 39;
		this.label4.Text = "最  大  速  度";
		this.label4.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
		this.LblCurrSpeed.BackColor = System.Drawing.Color.White;
		this.LblCurrSpeed.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle;
		this.LblCurrSpeed.Font = new System.Drawing.Font("微软雅黑", 11.25f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.LblCurrSpeed.ForeColor = System.Drawing.Color.Teal;
		this.LblCurrSpeed.Location = new System.Drawing.Point(333, 300);
		this.LblCurrSpeed.Name = "LblCurrSpeed";
		this.LblCurrSpeed.Size = new System.Drawing.Size(113, 25);
		this.LblCurrSpeed.TabIndex = 41;
		this.LblCurrSpeed.Text = "0.000毫米/秒";
		this.LblCurrSpeed.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
		this.BtnParamSet.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.BtnParamSet.Location = new System.Drawing.Point(472, 18);
		this.BtnParamSet.Name = "BtnParamSet";
		this.BtnParamSet.Size = new System.Drawing.Size(125, 62);
		this.BtnParamSet.TabIndex = 42;
		this.BtnParamSet.Text = "参数设置";
		this.BtnParamSet.UseVisualStyleBackColor = true;
		this.BtnParamSet.Click += new System.EventHandler(BtnParamSet_Click);
		this.CboType.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList;
		this.CboType.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.CboType.FormattingEnabled = true;
		this.CboType.Items.AddRange(new object[5] { "无", "平移台", "旋转台", "角位移台", "升降台" });
		this.CboType.Location = new System.Drawing.Point(89, 50);
		this.CboType.Name = "CboType";
		this.CboType.Size = new System.Drawing.Size(115, 27);
		this.CboType.TabIndex = 45;
		this.CboType.SelectedIndexChanged += new System.EventHandler(CboType_SelectedIndexChanged);
		this.label6.AutoSize = true;
		this.label6.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.label6.Location = new System.Drawing.Point(89, 30);
		this.label6.Name = "label6";
		this.label6.Size = new System.Drawing.Size(74, 19);
		this.label6.TabIndex = 44;
		this.label6.Text = "电移台类型";
		this.CboUnit.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList;
		this.CboUnit.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.CboUnit.FormattingEnabled = true;
		this.CboUnit.Items.AddRange(new object[3] { "毫米", "度", "步数" });
		this.CboUnit.Location = new System.Drawing.Point(89, 101);
		this.CboUnit.Name = "CboUnit";
		this.CboUnit.Size = new System.Drawing.Size(115, 27);
		this.CboUnit.TabIndex = 47;
		this.label8.AutoSize = true;
		this.label8.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.label8.Location = new System.Drawing.Point(89, 81);
		this.label8.Name = "label8";
		this.label8.Size = new System.Drawing.Size(61, 19);
		this.label8.TabIndex = 46;
		this.label8.Text = "运行单位";
		this.CboMotorAngle.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList;
		this.CboMotorAngle.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.CboMotorAngle.FormattingEnabled = true;
		this.CboMotorAngle.Items.AddRange(new object[2] { "1.8", "0.9" });
		this.CboMotorAngle.Location = new System.Drawing.Point(89, 152);
		this.CboMotorAngle.Name = "CboMotorAngle";
		this.CboMotorAngle.Size = new System.Drawing.Size(115, 27);
		this.CboMotorAngle.TabIndex = 49;
		this.label9.AutoSize = true;
		this.label9.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.label9.Location = new System.Drawing.Point(89, 132);
		this.label9.Name = "label9";
		this.label9.Size = new System.Drawing.Size(61, 19);
		this.label9.TabIndex = 48;
		this.label9.Text = "电机度数";
		this.CboSubsection.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList;
		this.CboSubsection.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.CboSubsection.FormattingEnabled = true;
		this.CboSubsection.Items.AddRange(new object[3] { "8", "4", "2" });
		this.CboSubsection.Location = new System.Drawing.Point(89, 203);
		this.CboSubsection.Name = "CboSubsection";
		this.CboSubsection.Size = new System.Drawing.Size(115, 27);
		this.CboSubsection.TabIndex = 51;
		this.label10.AutoSize = true;
		this.label10.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.label10.Location = new System.Drawing.Point(89, 183);
		this.label10.Name = "label10";
		this.label10.Size = new System.Drawing.Size(48, 19);
		this.label10.TabIndex = 50;
		this.label10.Text = "细分数";
		this.CboPitch.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.CboPitch.FormattingEnabled = true;
		this.CboPitch.Items.AddRange(new object[6] { "无", "0.5", "1", "1.5", "4", "5" });
		this.CboPitch.Location = new System.Drawing.Point(89, 254);
		this.CboPitch.Name = "CboPitch";
		this.CboPitch.Size = new System.Drawing.Size(115, 27);
		this.CboPitch.TabIndex = 53;
		this.CboPitch.Validating += new System.ComponentModel.CancelEventHandler(CboPitch_Validating);
		this.label11.AutoSize = true;
		this.label11.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.label11.Location = new System.Drawing.Point(89, 233);
		this.label11.Name = "label11";
		this.label11.Size = new System.Drawing.Size(108, 19);
		this.label11.TabIndex = 52;
		this.label11.Text = "丝杆导程(平移台)";
		this.CboTranRatio.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.CboTranRatio.FormattingEnabled = true;
		this.CboTranRatio.Items.AddRange(new object[11]
		{
			"无", "6", "72", "90", "180", "252", "352", "360", "400", "576",
			"720"
		});
		this.CboTranRatio.Location = new System.Drawing.Point(288, 50);
		this.CboTranRatio.Name = "CboTranRatio";
		this.CboTranRatio.Size = new System.Drawing.Size(115, 27);
		this.CboTranRatio.TabIndex = 55;
		this.CboTranRatio.Validating += new System.ComponentModel.CancelEventHandler(CboTranRatio_Validating);
		this.label12.AutoSize = true;
		this.label12.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.label12.Location = new System.Drawing.Point(288, 30);
		this.label12.Name = "label12";
		this.label12.Size = new System.Drawing.Size(48, 19);
		this.label12.TabIndex = 54;
		this.label12.Text = "传动比";
		this.CboTravel.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.CboTravel.FormattingEnabled = true;
		this.CboTravel.Items.AddRange(new object[9] { "50", "100", "250", "300", "400", "500", "600", "850", "1000" });
		this.CboTravel.Location = new System.Drawing.Point(288, 101);
		this.CboTravel.Name = "CboTravel";
		this.CboTravel.Size = new System.Drawing.Size(115, 27);
		this.CboTravel.TabIndex = 57;
		this.CboTravel.Validating += new System.ComponentModel.CancelEventHandler(CboTravel_Validating);
		this.label13.AutoSize = true;
		this.label13.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.label13.Location = new System.Drawing.Point(288, 81);
		this.label13.Name = "label13";
		this.label13.Size = new System.Drawing.Size(61, 19);
		this.label13.TabIndex = 56;
		this.label13.Text = "最大行程";
		this.CboNegaTravel.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.CboNegaTravel.FormattingEnabled = true;
		this.CboNegaTravel.Items.AddRange(new object[2] { "10", "15" });
		this.CboNegaTravel.Location = new System.Drawing.Point(288, 152);
		this.CboNegaTravel.Name = "CboNegaTravel";
		this.CboNegaTravel.Size = new System.Drawing.Size(115, 27);
		this.CboNegaTravel.TabIndex = 59;
		this.CboNegaTravel.Validating += new System.ComponentModel.CancelEventHandler(CboNegaTravel_Validating);
		this.label14.AutoSize = true;
		this.label14.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.label14.Location = new System.Drawing.Point(288, 132);
		this.label14.Name = "label14";
		this.label14.Size = new System.Drawing.Size(61, 19);
		this.label14.TabIndex = 58;
		this.label14.Text = "负向行程";
		this.CboPosiTravel.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.CboPosiTravel.FormattingEnabled = true;
		this.CboPosiTravel.Items.AddRange(new object[2] { "10", "15" });
		this.CboPosiTravel.Location = new System.Drawing.Point(288, 203);
		this.CboPosiTravel.Name = "CboPosiTravel";
		this.CboPosiTravel.Size = new System.Drawing.Size(115, 27);
		this.CboPosiTravel.TabIndex = 61;
		this.CboPosiTravel.Validating += new System.ComponentModel.CancelEventHandler(CboPosiTravel_Validating);
		this.label15.AutoSize = true;
		this.label15.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.label15.Location = new System.Drawing.Point(288, 183);
		this.label15.Name = "label15";
		this.label15.Size = new System.Drawing.Size(61, 19);
		this.label15.TabIndex = 60;
		this.label15.Text = "正向行程";
		this.GrdParam.Controls.Add(this.BtnClose);
		this.GrdParam.Controls.Add(this.BtnOk);
		this.GrdParam.Controls.Add(this.CboPosiTravel);
		this.GrdParam.Controls.Add(this.label15);
		this.GrdParam.Controls.Add(this.CboNegaTravel);
		this.GrdParam.Controls.Add(this.label14);
		this.GrdParam.Controls.Add(this.CboTravel);
		this.GrdParam.Controls.Add(this.label13);
		this.GrdParam.Controls.Add(this.CboTranRatio);
		this.GrdParam.Controls.Add(this.label12);
		this.GrdParam.Controls.Add(this.CboPitch);
		this.GrdParam.Controls.Add(this.label11);
		this.GrdParam.Controls.Add(this.CboSubsection);
		this.GrdParam.Controls.Add(this.label10);
		this.GrdParam.Controls.Add(this.CboMotorAngle);
		this.GrdParam.Controls.Add(this.label9);
		this.GrdParam.Controls.Add(this.CboUnit);
		this.GrdParam.Controls.Add(this.label8);
		this.GrdParam.Controls.Add(this.CboType);
		this.GrdParam.Controls.Add(this.label6);
		this.GrdParam.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.GrdParam.Location = new System.Drawing.Point(623, 18);
		this.GrdParam.Name = "GrdParam";
		this.GrdParam.Size = new System.Drawing.Size(490, 356);
		this.GrdParam.TabIndex = 62;
		this.GrdParam.TabStop = false;
		this.GrdParam.Text = "参数设置";
		this.BtnClose.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.BtnClose.Location = new System.Drawing.Point(288, 303);
		this.BtnClose.Name = "BtnClose";
		this.BtnClose.Size = new System.Drawing.Size(80, 34);
		this.BtnClose.TabIndex = 63;
		this.BtnClose.Text = "关   闭";
		this.BtnClose.UseVisualStyleBackColor = true;
		this.BtnClose.Click += new System.EventHandler(BtnClose_Click);
		this.BtnOk.Font = new System.Drawing.Font("微软雅黑", 9.75f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.BtnOk.Location = new System.Drawing.Point(124, 303);
		this.BtnOk.Name = "BtnOk";
		this.BtnOk.Size = new System.Drawing.Size(80, 34);
		this.BtnOk.TabIndex = 62;
		this.BtnOk.Text = "确   定";
		this.BtnOk.UseVisualStyleBackColor = true;
		this.BtnOk.Click += new System.EventHandler(BtnOk_Click);
		this.CboSpeed.Font = new System.Drawing.Font("微软雅黑", 10.5f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		this.CboSpeed.FormattingEnabled = true;
		this.CboSpeed.Items.AddRange(new object[6] { "无", "0.5", "1", "1.5", "4", "5" });
		this.CboSpeed.Location = new System.Drawing.Point(235, 298);
		this.CboSpeed.Name = "CboSpeed";
		this.CboSpeed.Size = new System.Drawing.Size(89, 28);
		this.CboSpeed.TabIndex = 64;
		this.CboSpeed.SelectedIndexChanged += new System.EventHandler(CboSpeed_SelectedIndexChanged);
		this.timer1.Tick += new System.EventHandler(timer1_Tick);
		this.label2.AutoSize = true;
		this.label2.BackColor = System.Drawing.Color.Transparent;
		this.label2.Font = new System.Drawing.Font("微软雅黑", 9f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 0);
		this.label2.Location = new System.Drawing.Point(117, 71);
		this.label2.Name = "label2";
		this.label2.Size = new System.Drawing.Size(343, 17);
		this.label2.TabIndex = 65;
		this.label2.Text = "-------------------------------------------------------------------";
		base.AutoScaleMode = System.Windows.Forms.AutoScaleMode.None;
		this.BackColor = System.Drawing.Color.FromArgb(251, 251, 251);
		base.Controls.Add(this.label2);
		base.Controls.Add(this.GrdParam);
		base.Controls.Add(this.CboSpeed);
		base.Controls.Add(this.BtnParamSet);
		base.Controls.Add(this.label4);
		base.Controls.Add(this.LblCurrSpeed);
		base.Controls.Add(this.BtnCancelZero);
		base.Controls.Add(this.LblCurrUnit);
		base.Controls.Add(this.LblCurrValue);
		base.Controls.Add(this.label1);
		base.Controls.Add(this.BtnFreeUp);
		base.Controls.Add(this.groupBox2);
		base.Controls.Add(this.BtnRun);
		base.Controls.Add(this.BtnLimitReturnZero);
		base.Controls.Add(this.label7);
		base.Controls.Add(this.BtnFreeDown);
		base.Controls.Add(this.NudRunToValue);
		base.Controls.Add(this.BtnFixSub);
		base.Controls.Add(this.BtnStop);
		base.Controls.Add(this.BtnFixAdd);
		base.Controls.Add(this.LblRunToValueUnit);
		base.Controls.Add(this.LblFixValueUnit);
		base.Controls.Add(this.BtnSetZero);
		base.Controls.Add(this.NudAddOrSubValue);
		this.Font = new System.Drawing.Font("微软雅黑", 9f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 134);
		base.Name = "SC3U";
		base.Size = new System.Drawing.Size(1209, 413);
		base.Load += new System.EventHandler(SCU_Load);
		this.groupBox2.ResumeLayout(false);
		((System.ComponentModel.ISupportInitialize)this.NudRunToValue).EndInit();
		((System.ComponentModel.ISupportInitialize)this.NudAddOrSubValue).EndInit();
		this.GrdParam.ResumeLayout(false);
		this.GrdParam.PerformLayout();
		base.ResumeLayout(false);
		base.PerformLayout();
	}
}
