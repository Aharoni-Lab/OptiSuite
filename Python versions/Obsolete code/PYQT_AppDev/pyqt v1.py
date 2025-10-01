#create a small window and open it
'''import sys
from PyQt5.QtWidgets import QApplication, QWidget

app = QApplication(sys.argv)

window = QWidget()
window.setWindowTitle('Hello PyQt5')
window.setGeometry(100, 100, 280, 80)  # x, y, width, height
window.show()

sys.exit(app.exec_())'''


#small window with clickable button
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout

class MyApp(QWidget):
    def __init__(self):
        super().__init__()

        self.initUI()

    def initUI(self):
        self.label = QLabel('Hello', self)
        btn = QPushButton('Click Me', self)
        btn.clicked.connect(self.on_click)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(btn)

        self.setLayout(layout)
        self.setWindowTitle('Button Example')
        self.setGeometry(100, 100, 300, 100)

    def on_click(self):
        self.label.setText('Button Clicked!')

app = QApplication(sys.argv)
win = MyApp()
win.show()
sys.exit(app.exec_())


