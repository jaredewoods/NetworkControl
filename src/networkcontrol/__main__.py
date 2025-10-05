import sys
from pathlib import Path
from PyQt6 import QtWidgets, uic
from networkcontrol.controller.main_controller import MainController


def main():
    app = QtWidgets.QApplication(sys.argv)

    # Load the UI file
    ui_path = Path(__file__).parent / "view" / "ui" / "main_window.ui"
    window = QtWidgets.QMainWindow()
    uic.loadUi(str(ui_path), window)

    # Initialize controller
    controller = MainController(window)
    window.show()

    # Gracefully stop background worker if active
    if hasattr(controller, "worker") and controller.worker:
        app.aboutToQuit.connect(controller.worker.stop)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
