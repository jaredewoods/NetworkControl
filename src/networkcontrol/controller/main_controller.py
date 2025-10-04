from PyQt6 import QtWidgets, QtGui, QtCore
from networkcontrol.model.network_model import get_network_interfaces


class MainController:
    def __init__(self, window: QtWidgets.QMainWindow):
        self.window = window
        self.table = window.findChild(QtWidgets.QTableWidget, "tableNetwork")
        self.btn_refresh = window.findChild(QtWidgets.QPushButton, "btnRefresh")
        self.btn_deep_scan = window.findChild(QtWidgets.QPushButton, "btnDeepScan")
        self.status_bar = window.statusBar()

        if not self.table:
            raise RuntimeError("UI missing 'tableNetwork'")
        if not self.btn_refresh or not self.btn_deep_scan:
            raise RuntimeError("UI missing one or both scan buttons")

        # --- initial populate ---
        self.populate_table()

        # --- connect buttons ---
        self.btn_refresh.clicked.connect(self.populate_table)
        self.btn_deep_scan.clicked.connect(self.handle_deep_scan)

    # ------------------------------------------------------------
    def populate_table(self):
        """Quick reload using standard model."""
        self.status_bar.showMessage("Refreshing adapter list...")
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor))

        try:
            self.table.setRowCount(0)
            interfaces = get_network_interfaces()

            for row, iface in enumerate(interfaces):
                self.table.insertRow(row)
                self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(iface["connection"]))
                self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(iface["description"]))
                self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(iface["ip"]))
                self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(iface["subnet"]))
                self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(iface["gateway"]))
                self.table.setItem(row, 5, QtWidgets.QTableWidgetItem(iface["mode"]))

            self.table.resizeColumnsToContents()
            self.status_bar.showMessage(f"Loaded {len(interfaces)} adapters.", 4000)

        except Exception as e:
            self.status_bar.showMessage(f"Error: {e}")
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    # ------------------------------------------------------------
    def handle_deep_scan(self):
        """Placeholder for PowerShell JSON validation (Step 3)."""
        self.status_bar.showMessage("Performing deep validation...")
        QtWidgets.QApplication.processEvents()
        QtWidgets.QMessageBox.information(
            self.window,
            "Deep Scan",
            "Deep Scan feature not yet implemented — coming in Step 3."
        )
        self.status_bar.clearMessage()
