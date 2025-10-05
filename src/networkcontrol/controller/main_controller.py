from PyQt6 import QtWidgets, QtGui, QtCore
from networkcontrol.model.network_model import (
    get_network_interfaces,
    get_network_interfaces_deep,
)

class NetworkMonitorWorker(QtCore.QThread):
    """Background thread that periodically polls interface data."""
    update_signal = QtCore.pyqtSignal(list)

    def __init__(self, interval=10):
        super().__init__()
        self.interval = interval  # seconds
        self._running = True

    def run(self):
        from networkcontrol.model.network_model import get_network_interfaces
        while self._running:
            try:
                data = get_network_interfaces()
                self.update_signal.emit(data)
            except Exception:
                pass
            self.msleep(self.interval * 1000)

    def stop(self):
        self._running = False
        self.quit()
        self.wait()



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

        # --- Live monitor thread ---
        self.worker = NetworkMonitorWorker(interval=10)
        self.worker.update_signal.connect(self._on_background_update)
        self.worker.start()

        # --- Manual controls ---
        self.btn_refresh.clicked.connect(self.manual_refresh)
        self.btn_deep_scan.clicked.connect(self.handle_deep_scan)

        # Initial load
        self.manual_refresh()

    # ------------------------------------------------------------
    def manual_refresh(self):
        """Trigger a one-time immediate refresh."""
        self.status_bar.showMessage("Manual refresh...")
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor))
        try:
            interfaces = get_network_interfaces()
            self._populate_table_rows(interfaces)
            self.status_bar.showMessage(f"Loaded {len(interfaces)} adapters.", 3000)
        except Exception as e:
            self.status_bar.showMessage(f"Error: {e}")
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    # ------------------------------------------------------------
    def _on_background_update(self, interfaces):
        """Handle data emitted from worker thread."""
        # You could add diff-checking here later
        self._populate_table_rows(interfaces)
        self.status_bar.showMessage("Background refresh complete", 2000)

    # ------------------------------------------------------------
    def handle_deep_scan(self):
        """Perform PowerShell-based deep verification."""
        self.status_bar.showMessage("Performing deep PowerShell scan...")
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor))
        self.worker.stop()  # temporarily stop background thread
        QtWidgets.QApplication.processEvents()

        try:
            interfaces = get_network_interfaces_deep()
            self._populate_table_rows(interfaces)
            self.status_bar.showMessage(f"Deep scan loaded {len(interfaces)} adapters.", 5000)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self.window, "Deep Scan Error", str(e))
            self.status_bar.showMessage("Deep scan failed.", 4000)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
            self.worker.start()  # resume monitoring

    # ------------------------------------------------------------
    def _populate_table_rows(self, interfaces):
        """Shared logic for populating the table."""
        self.table.setRowCount(0)
        for row, iface in enumerate(interfaces):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(iface["connection"]))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(self._get_link_status_text(iface)))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(iface["description"]))
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(iface["ip"]))
            self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(iface["subnet"]))
            self.table.setItem(row, 5, QtWidgets.QTableWidgetItem(iface["gateway"]))
            self.table.setItem(row, 6, QtWidgets.QTableWidgetItem(iface["mode"]))
        self.table.resizeColumnsToContents()

    # ------------------------------------------------------------
    def _get_link_status_text(self, iface):
        """Plain text link state logic."""
        link_state = iface.get("link", "—").lower()
        gateway = str(iface.get("gateway", "")).strip()
        if "down" in link_state:
            return "Down"
        if gateway in ("—", "", "none", "0.0.0.0"):
            return "Network"
        return "Internet"
