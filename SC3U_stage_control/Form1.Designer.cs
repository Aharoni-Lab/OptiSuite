namespace CSharp
{
    partial class Form1
    {
        /// <summary>
        /// 必需的设计器变量。
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary>
        /// 清理所有正在使用的资源。
        /// </summary>
        /// <param name="disposing">如果应释放托管资源，为 true；否则为 false。</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region Windows 窗体设计器生成的代码

        /// <summary>
        /// 设计器支持所需的方法 - 不要
        /// 使用代码编辑器修改此方法的内容。
        /// </summary>
        private void InitializeComponent()
        {
			this.button1 = new System.Windows.Forms.Button();
			this.textBox1 = new System.Windows.Forms.TextBox();
			this.label1 = new System.Windows.Forms.Label();
			this.button2 = new System.Windows.Forms.Button();
			this.label2 = new System.Windows.Forms.Label();
			this.sC3U1 = new SC3Us.SC3U();
			this.label4 = new System.Windows.Forms.Label();
			this.button3 = new System.Windows.Forms.Button();
			this.textBox2 = new System.Windows.Forms.TextBox();
			this.button8 = new System.Windows.Forms.Button();
			this.button7 = new System.Windows.Forms.Button();
			this.button5 = new System.Windows.Forms.Button();
			this.button6 = new System.Windows.Forms.Button();
			this.button4 = new System.Windows.Forms.Button();
			this.button9 = new System.Windows.Forms.Button();
			this.groupBox1 = new System.Windows.Forms.GroupBox();
			this.groupBox1.SuspendLayout();
			this.SuspendLayout();
			// 
			// button1
			// 
			this.button1.Location = new System.Drawing.Point(221, 454);
			this.button1.Name = "button1";
			this.button1.Size = new System.Drawing.Size(162, 24);
			this.button1.TabIndex = 1;
			this.button1.Text = "Connect";
			this.button1.UseVisualStyleBackColor = true;
			this.button1.Click += new System.EventHandler(this.button1_Click);
			// 
			// textBox1
			// 
			this.textBox1.Location = new System.Drawing.Point(142, 458);
			this.textBox1.Name = "textBox1";
			this.textBox1.Size = new System.Drawing.Size(60, 21);
			this.textBox1.TabIndex = 2;
			this.textBox1.Text = "2";
			// 
			// label1
			// 
			this.label1.AutoSize = true;
			this.label1.Location = new System.Drawing.Point(30, 501);
			this.label1.Name = "label1";
			this.label1.Size = new System.Drawing.Size(107, 12);
			this.label1.TabIndex = 3;
			this.label1.Text = "Current Position:";
			// 
			// button2
			// 
			this.button2.Location = new System.Drawing.Point(221, 495);
			this.button2.Name = "button2";
			this.button2.Size = new System.Drawing.Size(162, 24);
			this.button2.TabIndex = 4;
			this.button2.Text = "Get Current Position";
			this.button2.UseVisualStyleBackColor = true;
			this.button2.Click += new System.EventHandler(this.button2_Click);
			// 
			// label2
			// 
			this.label2.AutoSize = true;
			this.label2.Location = new System.Drawing.Point(30, 462);
			this.label2.Name = "label2";
			this.label2.Size = new System.Drawing.Size(77, 12);
			this.label2.TabIndex = 5;
			this.label2.Text = "Serial Port:";
			// 
			// sC3U1
			// 
			this.sC3U1.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(251)))), ((int)(((byte)(251)))), ((int)(((byte)(251)))));
			this.sC3U1.Language = ((short)(1));
			this.sC3U1.Location = new System.Drawing.Point(22, 34);
			this.sC3U1.Name = "sC3U1";
			this.sC3U1.Size = new System.Drawing.Size(616, 363);
			this.sC3U1.SpeedGrades = ((short)(0));
			this.sC3U1.TabIndex = 6;
			// 
			// label4
			// 
			this.label4.AutoSize = true;
			this.label4.Location = new System.Drawing.Point(30, 540);
			this.label4.Name = "label4";
			this.label4.Size = new System.Drawing.Size(53, 12);
			this.label4.TabIndex = 12;
			this.label4.Text = "Move To:";
			// 
			// button3
			// 
			this.button3.Location = new System.Drawing.Point(221, 534);
			this.button3.Name = "button3";
			this.button3.Size = new System.Drawing.Size(162, 24);
			this.button3.TabIndex = 11;
			this.button3.Text = "Run";
			this.button3.UseVisualStyleBackColor = true;
			this.button3.Click += new System.EventHandler(this.button3_Click);
			// 
			// textBox2
			// 
			this.textBox2.Location = new System.Drawing.Point(142, 537);
			this.textBox2.Name = "textBox2";
			this.textBox2.Size = new System.Drawing.Size(60, 21);
			this.textBox2.TabIndex = 10;
			// 
			// button8
			// 
			this.button8.Location = new System.Drawing.Point(399, 198);
			this.button8.Name = "button8";
			this.button8.Size = new System.Drawing.Size(119, 39);
			this.button8.TabIndex = 22;
			this.button8.Text = "Reset Parameters";
			this.button8.UseVisualStyleBackColor = true;
			this.button8.Click += new System.EventHandler(this.button8_Click);
			// 
			// button7
			// 
			this.button7.Location = new System.Drawing.Point(33, 163);
			this.button7.Name = "button7";
			this.button7.Size = new System.Drawing.Size(247, 39);
			this.button7.TabIndex = 21;
			this.button7.Text = "Goniometer(Set Zero Position)";
			this.button7.UseVisualStyleBackColor = true;
			this.button7.Click += new System.EventHandler(this.button7_Click);
			// 
			// button5
			// 
			this.button5.Location = new System.Drawing.Point(283, 51);
			this.button5.Name = "button5";
			this.button5.Size = new System.Drawing.Size(119, 39);
			this.button5.TabIndex = 20;
			this.button5.Text = "Lab Jack";
			this.button5.UseVisualStyleBackColor = true;
			this.button5.Click += new System.EventHandler(this.button5_Click);
			// 
			// button6
			// 
			this.button6.Location = new System.Drawing.Point(33, 105);
			this.button6.Name = "button6";
			this.button6.Size = new System.Drawing.Size(247, 39);
			this.button6.TabIndex = 19;
			this.button6.Text = "Goniometer(Not Set Zero Position)";
			this.button6.UseVisualStyleBackColor = true;
			this.button6.Click += new System.EventHandler(this.button6_Click);
			// 
			// button4
			// 
			this.button4.Location = new System.Drawing.Point(158, 51);
			this.button4.Name = "button4";
			this.button4.Size = new System.Drawing.Size(119, 39);
			this.button4.TabIndex = 18;
			this.button4.Text = "Rotation Stage";
			this.button4.UseVisualStyleBackColor = true;
			this.button4.Click += new System.EventHandler(this.button4_Click);
			// 
			// button9
			// 
			this.button9.Location = new System.Drawing.Point(33, 51);
			this.button9.Name = "button9";
			this.button9.Size = new System.Drawing.Size(119, 39);
			this.button9.TabIndex = 17;
			this.button9.Text = "Translation Stage";
			this.button9.UseVisualStyleBackColor = true;
			this.button9.Click += new System.EventHandler(this.button9_Click);
			// 
			// groupBox1
			// 
			this.groupBox1.Controls.Add(this.button6);
			this.groupBox1.Controls.Add(this.button8);
			this.groupBox1.Controls.Add(this.button9);
			this.groupBox1.Controls.Add(this.button7);
			this.groupBox1.Controls.Add(this.button4);
			this.groupBox1.Controls.Add(this.button5);
			this.groupBox1.Location = new System.Drawing.Point(406, 424);
			this.groupBox1.Name = "groupBox1";
			this.groupBox1.Size = new System.Drawing.Size(524, 243);
			this.groupBox1.TabIndex = 23;
			this.groupBox1.TabStop = false;
			this.groupBox1.Text = "Parameters Setting";
			// 
			// Form1
			// 
			this.AutoScaleDimensions = new System.Drawing.SizeF(6F, 12F);
			this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
			this.ClientSize = new System.Drawing.Size(982, 749);
			this.Controls.Add(this.groupBox1);
			this.Controls.Add(this.label4);
			this.Controls.Add(this.button3);
			this.Controls.Add(this.textBox2);
			this.Controls.Add(this.sC3U1);
			this.Controls.Add(this.label2);
			this.Controls.Add(this.button2);
			this.Controls.Add(this.label1);
			this.Controls.Add(this.textBox1);
			this.Controls.Add(this.button1);
			this.Name = "Form1";
			this.Text = "Form1";
			this.groupBox1.ResumeLayout(false);
			this.ResumeLayout(false);
			this.PerformLayout();

        }

        #endregion

        private System.Windows.Forms.Button button1;
        private System.Windows.Forms.TextBox textBox1;
        private System.Windows.Forms.Label label1;
        private System.Windows.Forms.Button button2;
        private System.Windows.Forms.Label label2;
        private SC3Us.SC3U sC3U1;
        private System.Windows.Forms.Label label4;
        private System.Windows.Forms.Button button3;
        private System.Windows.Forms.TextBox textBox2;
        private System.Windows.Forms.Button button8;
        private System.Windows.Forms.Button button7;
        private System.Windows.Forms.Button button5;
        private System.Windows.Forms.Button button6;
        private System.Windows.Forms.Button button4;
        private System.Windows.Forms.Button button9;
		private System.Windows.Forms.GroupBox groupBox1;
	}
}

