from PyQt6 import QtWidgets, QtGui, QtCore
from networkcontrol.model.network_model import (
    get_network_interfaces,
    get_network_interfaces_deep,
)


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

        # Initial table fill
        self.populate_table()

        # Button bindings
        self.btn_refresh.clicked.connect(self.populate_table)
        self.btn_deep_scan.clicked.connect(self.handle_deep_scan)

    # ------------------------------------------------------------
    def populate_table(self):
        """Quick reload using standard (psutil/netsh/WMI) model."""
        self.status_bar.showMessage("Refreshing adapter list...")
        QtWidgets.QApplication.setOverrideCursor(
            QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor)
        )

        try:
            self.table.setRowCount(0)
            interfaces = get_network_interfaces()
            self._populate_table_rows(interfaces)
            self.status_bar.showMessage(f"Loaded {len(interfaces)} adapters.", 4000)

        except Exception as e:
            self.status_bar.showMessage(f"Error: {e}")
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    # ------------------------------------------------------------
    def handle_deep_scan(self):
        """Perform PowerShell-based deep verification."""
        self.status_bar.showMessage("Performing deep PowerShell scan...")
        QtWidgets.QApplication.setOverrideCursor(
            QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor)
        )
        self.table.setRowCount(0)
        QtWidgets.QApplication.processEvents()

        try:
            interfaces = get_network_interfaces_deep()
            self._populate_table_rows(interfaces)
            self.status_bar.showMessage(
                f"Deep scan loaded {len(interfaces)} adapters.", 6000
            )

        except Exception as e:
            QtWidgets.QMessageBox.warning(self.window, "Deep Scan Error", str(e))
            self.status_bar.showMessage("Deep scan failed.", 4000)

        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    # ------------------------------------------------------------
    def _populate_table_rows(self, interfaces):
        """Shared logic for populating the table with plain text link status."""
        for row, iface in enumerate(interfaces):
            self.table.insertRow(row)

            # Connection
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(iface["connection"]))

            # --- Link Status (Plain Text) ---
            link_text = self._get_link_status_text(iface)
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(link_text))

            # Description
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(iface["description"]))
            # IP
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(iface["ip"]))
            # Subnet
            self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(iface["subnet"]))
            # Gateway
            self.table.setItem(row, 5, QtWidgets.QTableWidgetItem(iface["gateway"]))
            # DHCP/Static
            self.table.setItem(row, 6, QtWidgets.QTableWidgetItem(iface["mode"]))

        self.table.resizeColumnsToContents()

    # ------------------------------------------------------------
    def _get_link_status_text(self, iface):
        """Return plain text link status: Internet, Network, or Down."""
        link_state = iface.get("link", "—").lower()
        gateway = str(iface.get("gateway", "")).strip()

        if "down" in link_state:
            return "Down"

        if gateway in ("—", "", "none", "0.0.0.0"):
            return "Network"

        return "Internet"
