# Minimal PyQt6 window
import sys
from PyQt6.QtWidgets import QApplication, QLabel

def run():
    app = QApplication.instance() or QApplication(sys.argv)
    w = QLabel("NetworkControl")
    w.setWindowTitle("NetworkControl")
    w.resize(360, 120)
    w.show()
    app.exec()
