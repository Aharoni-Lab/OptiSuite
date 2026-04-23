// SC3U, Version=1.6.0.0, Culture=neutral, PublicKeyToken=null
// SC3Us.MainClass
using System.Drawing;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;

public class MainClass
{
	[DllImport("kernel32")]
	private static extern long GetPrivateProfileString(string lpApplicationName, string lpKeyName, string lpDefault, StringBuilder lpReturnedString, int nSize, string lpFileName);

	[DllImport("kernel32")]
	private static extern long WritePrivateProfileString(string lpApplicationName, string lpKeyName, string lpString, string lpFileName);

	public string GetFromIni(string AppName, string KeyName, string FileName = "34SysParam.ini")
	{
		string text = "";
		string lpDefault = "defaultValue";
		StringBuilder stringBuilder = new StringBuilder(250);
		text = Application.StartupPath;
		if (text.Substring(text.Length - 1, 1) != "\\")
		{
			text += "\\";
		}
		text += FileName;
		GetPrivateProfileString(AppName, KeyName, lpDefault, stringBuilder, 250, text);
		return stringBuilder.ToString().Trim();
	}

	public bool WriteToIni(string AppName, string KeyName, string OutStr, string FileName = "34SysParam.ini")
	{
		string text;
		if (FileName.IndexOf("\\") == -1)
		{
			text = Application.StartupPath;
			if (text.Substring(text.Length - 1, 1) != "\\")
			{
				text += "\\";
			}
			text += FileName;
		}
		else
		{
			text = FileName;
		}
		if (WritePrivateProfileString(AppName, KeyName, OutStr, text) == 0L)
		{
			return false;
		}
		return true;
	}

	public static void GetControl(Control control, short sLanguage)
	{
		foreach (Control control2 in control.Controls)
		{
			if (control2 == null)
			{
				break;
			}
			if (sLanguage == 0)
			{
				control2.Font = new Font("微软雅黑", control2.Font.Size, control2.Font.Style);
			}
			else
			{
				control2.Font = new Font("Arial", control2.Font.Size, control2.Font.Style);
			}
			if (control2.HasChildren)
			{
				GetControl(control2, sLanguage);
			}
		}
	}
}
