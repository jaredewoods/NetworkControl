from pathlib import Path
import sys
from PyQt6 import QtWidgets, uic
from networkcontrol.controller.main_controller import MainController


def main():
    app = QtWidgets.QApplication(sys.argv)

    ui_path = Path(__file__).parent / "view" / "ui" / "main_window.ui"
    if not ui_path.exists():
        raise FileNotFoundError(f"UI file not found: {ui_path}")

    window = QtWidgets.QMainWindow()
    uic.loadUi(str(ui_path), window)

    # Controller manages logic and table population
    controller = MainController(window)

    window.show()
    app.aboutToQuit.connect(controller.worker.stop)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
