//using Newtonsoft.Json; //for JSON parsing, need to install the package via
                       //NuGet bc this version of NET 4.7.2 doesn't support json


using System;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Text.Json; //for JSON parsing
using System.Threading.Tasks;
using System.Windows.Forms;

namespace CSharp
{
    public partial class Form1 : Form
    {
        private ZmqStageServer _zmqStageServer;

        //This is the GUI
        public Form1()
        {
            Console.WriteLine("Forrm1 created");
            InitializeComponent();

            // start ZeroMQ listener + queue runner
            _zmqStageServer = new ZmqStageServer(
                "tcp://*:5555",
                RunToTarget,
                RunTestRoute,
                stopRun: () => sC3U1.StopRun(),
                setOrigin: () =>
                {
                    sC3U1.SetZeroOffset(0, sC3U1.GetCurrentStep(0));
                    sC3U1.SaveParam(0);
                },
                getCurrentPositionAsync: GetCurrentPositionAsync
            );
            _zmqStageServer.Start();
        }

        private void button1_Click(object sender, EventArgs e)
        {
            Console.WriteLine("button1 in Forrm1 clicked");
            sC3U1.ConnectPort(Convert.ToInt16(textBox1.Text));
        }
        //btw this is for axis 0 an ddisplays on the bottom half of the page
        private void button2_Click(object sender, EventArgs e)
        {
            Console.WriteLine("button2 in Forrm1 clicked");
            label1.Text = " Position X:" + sC3U1.GetCurrentPosition(0).ToString("#0.00")
                + " Y:" + sC3U1.GetCurrentPosition(1).ToString("#0.00")
                + " Z:" + sC3U1.GetCurrentPosition(2).ToString("#0.00");
        }
        //translation stage button (I think???)
        private void button9_Click(object sender, EventArgs e)
        {
            Console.WriteLine("button9 in Forrm1 clicked");
            sC3U1.SetType(0, 1);                                    //Set parameters for translation stage
            sC3U1.SetUnit(0, 0);                                    //Set mm as the unit
            sC3U1.SetMotorAngle(0, Convert.ToSingle(0.9));          //Set the motor angle to 0.9
            sC3U1.SetSubsection(0, 2);                              //Set the subdivision to 2
            sC3U1.SetPitch(0, 1);                                   //Set the pitch to 1
            sC3U1.SetTravel(0, 100);                                 //Set the travel range to 100
            sC3U1.SaveParam(0);                                     //Save all parameters
        }

        private void button4_Click(object sender, EventArgs e)
        {
            Console.WriteLine("button4 in Forrm1 clicked");
            sC3U1.SetType(0, 2);                                    //Set parameters for rotation stage
            sC3U1.SetUnit(0, 1);                                    //Set degree as the unit
            sC3U1.SetMotorAngle(0, Convert.ToSingle(0.9));          //Set the motor angle to 0.9
            sC3U1.SetSubsection(0, 2);                              //Set the subdivision to 2
            sC3U1.SetTranRatio(0, 180);                             //Set the transmission ratio to 180
            sC3U1.SaveParam(0);                                     //Save all parameters
        }

        private void button5_Click(object sender, EventArgs e)
        {
            Console.WriteLine("button5 in Forrm1 clicked");
            sC3U1.SetType(0, 4);                                    //Set parameters for lab jack
            sC3U1.SetUnit(0, 0);                                    //Set mm as the unit
            sC3U1.SetMotorAngle(0, Convert.ToSingle(0.9));          //Set the motor angle to 0.9
            sC3U1.SetSubsection(0, 2);                              //Set the subdivision to 2
            sC3U1.SetPitch(0, 1);                                   //Set the pitch to 1
            sC3U1.SetTranRatio(0, 1);                               //Set the transmission ratio to 1
            sC3U1.SetTravel(0, 50);                                 //Set the travel range to 50
            sC3U1.SaveParam(0);                                     //Save all parameters
        }

        private void button8_Click(object sender, EventArgs e)
        {
            Console.WriteLine("button8 in Forrm1 clicked");
            sC3U1.SetType(0, 0);                                    //Reset the parameters
            sC3U1.SaveParam(0);                                     //Save all parameters
        }

        private void button6_Click(object sender, EventArgs e)
        {
            Console.WriteLine("button6 in Forrm1 clicked");
            sC3U1.SetType(0, 3);                                    //Set parameters for goniometer stage
            sC3U1.SetUnit(0, 1);                                    //Set degree as the unit
            sC3U1.SetMotorAngle(0, Convert.ToSingle(0.9));          //Set the motor angle to 0.9
            sC3U1.SetSubsection(0, 2);                              //Set the subdivision to 2
            sC3U1.SetTranRatio(0, 90);                              //Set the transmission ratio to 90
            sC3U1.SetTravel(0, 20);                                 //Set the travel range to 20
            sC3U1.SaveParam(0);                                     //Save all parameters
        }

        private void button7_Click(object sender, EventArgs e)
        {
            Console.WriteLine("button7 in Forrm1 clicked");
            sC3U1.SetType(0, 3);                                    //Set parameters for goniometer stage
            sC3U1.SetUnit(0, 1);                                    //Set degree as the unit
            sC3U1.SetMotorAngle(0, Convert.ToSingle(0.9));          //Set the motor angle to 0.9
            sC3U1.SetSubsection(0, 2);                              //Set the subdivision to 2
            sC3U1.SetTranRatio(0, 90);                              //Set the transmission ratio to 90
            sC3U1.SetZeroOffset(0, sC3U1.GetCurrentStep(0));        //Set the current position as zero position
            sC3U1.SetNegativeTravel(0, 10);                         //Set the negative travel to 10
            sC3U1.SetPositiveTravel(0, 10);                         //Set the positive travel to 10
            sC3U1.SaveParam(0);                                     //Save all parameters
        }

        private void button3_Click(object sender, EventArgs e)
        {
            Console.WriteLine("button3 in Forrm1 clicked");
            //manually overwrite this to go to 10.10 for now to set up an auto-run
            //note that the instructions do not execute in parallel but sequentially
            //find out if there is a delay function
            sC3U1.RunToPosition(1, 10 - sC3U1.GetCurrentPosition(1));
            //await Task.Delay(10);

            sC3U1.RunToPosition(0, 10 - sC3U1.GetCurrentPosition(0));
            //sC3U1.RunToPosition(0, Convert.ToDouble(textBox2.Text) - sC3U1.GetCurrentPosition(0));      //Move X axis to the specified position
        }

        //for the ZMQ listener



        //general single axis running function
        //can and better to make this async so that it can be awaited
        //does need an await if you make it async though
        public Task RunToTarget(short axis, double target)
        {
            //creates a task, returns when tcs.SetResult is called
            var tcs = new TaskCompletionSource<bool>();

            this.BeginInvoke(new Action(() => _ = RunToTargetOnUiThreadAsync(axis, target, tcs)));

            return tcs.Task;
        }

        private async Task RunToTargetOnUiThreadAsync(short axis, double target, TaskCompletionSource<bool> tcs)
        {
            try
            {
                // Queue semantics: wait until device is free rather than failing.
                while (sC3U1.BusyStatus)
                {
                    await Task.Delay(50);
                }

                // Start move (RunToPosition expects delta).
                sC3U1.RunToPosition(axis, target - sC3U1.GetCurrentPosition(axis));

                // BusyStatus can lag; wait for it to go true (briefly) before waiting for completion.
                // This prevents "instant completion" races where subsequent axis moves start too early.
                int tries = 0;
                while (!sC3U1.BusyStatus && tries < 20)
                {
                    await Task.Delay(10);
                    tries++;
                }

                while (sC3U1.BusyStatus)
                {
                    await Task.Delay(50);
                }

                tcs.TrySetResult(true);
            }
            catch (Exception ex)
            {
                tcs.TrySetException(ex);
            }
        }

        public Task<double> GetCurrentPositionAsync(short axis)
        {
            var tcs = new TaskCompletionSource<double>();
            this.BeginInvoke(new Action(() =>
            {
                try
                {
                    tcs.TrySetResult(sC3U1.GetCurrentPosition(axis));
                }
                catch (Exception ex)
                {
                    tcs.TrySetException(ex);
                }
            }));
            return tcs.Task;
        }


        
        public async Task RunTestRoute()
        {   

            await RunToTarget(0, 60);
            await RunToTarget(1, 20);
            await Task.Delay(2000);
            await RunToTarget(0, 75);
            await RunToTarget(1, 40);
        }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            _zmqStageServer?.Dispose();
            base.OnFormClosing(e);
        }
    }
}