from PyQt6 import QtWidgets, QtGui, QtCore
from networkcontrol.model.network_model import (
    get_network_interfaces,
    get_network_interfaces_deep,
)


# ------------------------------------------------------------
# Background worker thread for live updates
# ------------------------------------------------------------
class NetworkMonitorWorker(QtCore.QThread):
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


# ------------------------------------------------------------
# Delegate for DHCP / Static drop-down
# ------------------------------------------------------------
class ComboBoxDelegate(QtWidgets.QStyledItemDelegate):
    """Delegate to display a drop-down for DHCP / Static column."""
    def createEditor(self, parent, option, index):
        combo = QtWidgets.QComboBox(parent)
        combo.addItems(["DHCP", "Static"])
        return combo

    def setEditorData(self, editor, index):
        value = index.data(QtCore.Qt.ItemDataRole.EditRole)
        i = editor.findText(value)
        if i >= 0:
            editor.setCurrentIndex(i)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), QtCore.Qt.ItemDataRole.EditRole)


# ------------------------------------------------------------
# Main Controller
# ------------------------------------------------------------
class MainController:
    def __init__(self, window: QtWidgets.QMainWindow):
        self.window = window
        self.table = window.findChild(QtWidgets.QTableWidget, "tableNetwork")
        self.btn_refresh = window.findChild(QtWidgets.QPushButton, "btnRefresh")
        self.btn_deep_scan = window.findChild(QtWidgets.QPushButton, "btnDeepScan")
        self.btn_apply = window.findChild(QtWidgets.QPushButton, "btnApply")
        self.status_bar = window.statusBar()

        if not self.table:
            raise RuntimeError("UI missing 'tableNetwork'")
        if not all([self.btn_refresh, self.btn_deep_scan, self.btn_apply]):
            raise RuntimeError("UI missing one or more control buttons")

        # --- Drop-down delegate for DHCP/Static column (index 6)
        self.table.setItemDelegateForColumn(6, ComboBoxDelegate(self.table))

        # --- Editing state flag
        self._editing = False

        # --- Connect edit tracking signals
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._on_edit_start)

        # --- Start background worker
        self.worker = NetworkMonitorWorker(interval=10)
        self.worker.update_signal.connect(self._on_background_update)
        self.worker.start()

        # --- Button bindings
        self.btn_refresh.clicked.connect(self.manual_refresh)
        self.btn_deep_scan.clicked.connect(self.handle_deep_scan)
        self.btn_apply.clicked.connect(self.apply_changes)

        # --- Initial data load
        self.manual_refresh()

    # ------------------------------------------------------------
    def _on_edit_start(self):
        """Pause live updates while user is editing."""
        self._editing = True

    def _on_item_changed(self):
        """Resume updates when user finishes editing."""
        # Slight delay to avoid multiple triggers
        QtCore.QTimer.singleShot(1500, self._resume_updates)

    def _resume_updates(self):
        self._editing = False

    # ------------------------------------------------------------
    def manual_refresh(self):
        """Trigger a one-time immediate refresh."""
        self.status_bar.showMessage("Refreshing adapter list...")
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
        """Handle updates from the background thread."""
        if self._editing:
            return  # skip update while user editing
        self._populate_table_rows(interfaces)
        self.status_bar.showMessage("Background refresh complete", 2000)

    # ------------------------------------------------------------
    def handle_deep_scan(self):
        """Perform PowerShell-based deep verification."""
        self.status_bar.showMessage("Performing deep PowerShell scan...")
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor))
        QtWidgets.QApplication.processEvents()

        try:
            self.worker.stop()  # pause updates during deep scan
            interfaces = get_network_interfaces_deep()
            self._populate_table_rows(interfaces)
            self.status_bar.showMessage(f"Deep scan loaded {len(interfaces)} adapters.", 5000)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self.window, "Deep Scan Error", str(e))
            self.status_bar.showMessage("Deep scan failed.", 4000)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
            # restart background worker
            self.worker = NetworkMonitorWorker(interval=10)
            self.worker.update_signal.connect(self._on_background_update)
            self.worker.start()

    # ------------------------------------------------------------
    def apply_changes(self):
        """Collect user-edited NIC values and prepare for application."""
        self.status_bar.showMessage("Collecting edited data...")

        rows = self.table.rowCount()
        changes = []

        for r in range(rows):
            connection = self._get_text(r, 0)
            ip = self._get_text(r, 3)
            subnet = self._get_text(r, 4)
            gateway = self._get_text(r, 5)
            mode = self._get_text(r, 6)
            changes.append({
                "connection": connection,
                "ip": ip,
                "subnet": subnet,
                "gateway": gateway,
                "mode": mode,
            })

        msg = "\n".join([
            f"{c['connection']}: {c['ip']}  {c['subnet']}  GW={c['gateway']}  ({c['mode']})"
            for c in changes
        ])
        QtWidgets.QMessageBox.information(
            self.window,
            "Planned Changes",
            f"The following settings were collected:\n\n{msg}\n\n"
            "In the next step these values will be applied to adapters via PowerShell."
        )

    # ------------------------------------------------------------
    def _populate_table_rows(self, interfaces):
        """Populate the table with editable columns."""
        self.table.setRowCount(0)

        for row, iface in enumerate(interfaces):
            self.table.insertRow(row)

            # --- Read-only columns ---
            self._set_readonly(row, 0, iface["connection"])
            self._set_readonly(row, 1, self._get_link_status_text(iface))
            self._set_readonly(row, 2, iface["description"])

            # --- Editable columns ---
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(iface["ip"]))
            self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(iface["subnet"]))
            self.table.setItem(row, 5, QtWidgets.QTableWidgetItem(iface["gateway"]))
            self.table.setItem(row, 6, QtWidgets.QTableWidgetItem(iface["mode"]))

        self.table.resizeColumnsToContents()

    # ------------------------------------------------------------
    def _get_text(self, row, col):
        item = self.table.item(row, col)
        return item.text().strip() if item else ""

    def _set_readonly(self, row, col, text):
        item = QtWidgets.QTableWidgetItem(text)
        item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, col, item)

    # ------------------------------------------------------------
    def _get_link_status_text(self, iface):
        """Plain-text link state."""
        link_state = iface.get("link", "—").lower()
        gateway = str(iface.get("gateway", "")).strip()
        if "down" in link_state:
            return "Down"
        if gateway in ("—", "", "none", "0.0.0.0"):
            return "Network"
        return "Internet"
