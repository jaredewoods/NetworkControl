from pathlib import Path
import sys
from PyQt6 import QtWidgets, uic

def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    ui_path = Path(__file__).parent / "view" / "ui" / "main_window.ui"
    if not ui_path.exists():
        raise FileNotFoundError(f"UI file not found: {ui_path}")
    window = QtWidgets.QMainWindow()
    uic.loadUi(str(ui_path), window)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
