using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows.Forms;
using SC3Us; //try this

namespace CSharp
{
    static class Program // static class cannot be instantiated and can only contain static members
    {
        /// <summary>
        /// 应用程序的主入口点。
        /// </summary>
        [STAThread] //attribute that indicates COM threading model for the application is single-threaded apartment (STA)
        static void Main()
        {
            System.Diagnostics.Debug.WriteLine("Printing from Program.cs main");

            // Diagnostics to confirm which EXE is running.
            System.Diagnostics.Debug.WriteLine("BaseDirectory: " + AppDomain.CurrentDomain.BaseDirectory);

            System.Diagnostics.Debug.WriteLine("Process MainModule: " + System.Diagnostics.Process.GetCurrentProcess().MainModule.FileName);

            // Optional visible confirmation when not attached todebugger
            MessageBox.Show("Running EXE:\n" + Application.ExecutablePath);
            System.Diagnostics.Debug.WriteLine("Main ran");
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new Form1());
        }
    }
}
