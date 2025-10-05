from PyQt6 import QtWidgets, QtGui, QtCore
from networkcontrol.model.network_model import (
    get_network_interfaces,
    get_network_interfaces_deep,
)
from networkcontrol.model.network_apply import apply_nic_settings, validate_ip_structure
from networkcontrol.controller.worker_thread import NetworkMonitorWorker


# ------------------------------------------------------------
# Delegate for DHCP / Static drop-down
# ------------------------------------------------------------
class ComboBoxDelegate(QtWidgets.QStyledItemDelegate):
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

        # Drop-down delegate for DHCP/Static column (index 6)
        self.table.setItemDelegateForColumn(6, ComboBoxDelegate(self.table))

        # Editing-pause state
        self._editing = False
        self._resume_timer = None

        # Connect edit detection
        self.table.itemSelectionChanged.connect(self._pause_for_editing)
        self.table.cellClicked.connect(self._pause_for_editing)
        self.table.cellActivated.connect(self._pause_for_editing)
        self.table.itemChanged.connect(self._pause_for_editing)

        # Start background worker
        self.worker = NetworkMonitorWorker(interval=10)
        self.worker.update_signal.connect(self._on_background_update)
        self.worker.start()

        # Button bindings
        self.btn_refresh.clicked.connect(self.manual_refresh)
        self.btn_deep_scan.clicked.connect(self.handle_deep_scan)
        self.btn_apply.clicked.connect(self.apply_changes)

        # Initial load
        self.manual_refresh()

    # ------------------------------------------------------------
    # Editing-pause logic
    # ------------------------------------------------------------
    def _pause_for_editing(self):
        if self._resume_timer:
            self._resume_timer.stop()
        self._editing = True
        self.status_bar.showMessage("Editing detected — background updates paused")

        self._resume_timer = QtCore.QTimer()
        self._resume_timer.setSingleShot(True)
        self._resume_timer.timeout.connect(self._resume_updates)
        self._resume_timer.start(10000)  # 10 s delay

    def _resume_updates(self):
        self._editing = False
        self.status_bar.showMessage("Background updates resumed", 2000)

    # ------------------------------------------------------------
    # Refresh & update handling
    # ------------------------------------------------------------
    def manual_refresh(self):
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

    def _on_background_update(self, interfaces):
        if self._editing:
            return
        self._populate_table_rows(interfaces)
        self.status_bar.showMessage("Background refresh complete", 2000)

    # ------------------------------------------------------------
    def handle_deep_scan(self):
        self.status_bar.showMessage("Performing deep PowerShell scan...")
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor))
        QtWidgets.QApplication.processEvents()
        try:
            self.worker.stop()
            interfaces = get_network_interfaces_deep()
            self._populate_table_rows(interfaces)
            self.status_bar.showMessage(f"Deep scan loaded {len(interfaces)} adapters.", 5000)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self.window, "Deep Scan Error", str(e))
            self.status_bar.showMessage("Deep scan failed.", 4000)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
            self.worker = NetworkMonitorWorker(interval=10)
            self.worker.update_signal.connect(self._on_background_update)
            self.worker.start()

    # ------------------------------------------------------------
    # Apply-Changes logic
    # ------------------------------------------------------------
    def apply_changes(self):
        self.status_bar.showMessage("Applying changes...")
        if self._resume_timer:
            self._resume_timer.stop()
        self._editing = False

        rows = self.table.rowCount()
        results = []

        for r in range(rows):
            connection = self._get_text(r, 0)
            ip = self._get_text(r, 3)
            subnet = self._get_text(r, 4)
            gateway = self._get_text(r, 5)
            mode = self._get_text(r, 6)

            # Validate static entries
            if mode.upper() == "STATIC" and not validate_ip_structure(ip):
                results.append(f"{connection}: Invalid IP '{ip}' — skipped")
                continue

            res = apply_nic_settings(connection, ip, subnet, gateway, mode)
            status = "OK" if res["success"] else "FAILED"
            results.append(f"{connection}: {status}\n{res['stderr'] or res['stdout']}")

        msg = "\n\n".join(results)
        QtWidgets.QMessageBox.information(self.window, "Apply Results", msg)
        self._resume_updates()

    # ------------------------------------------------------------
    # Table population helpers
    # ------------------------------------------------------------
    def _populate_table_rows(self, interfaces):
        self.table.setRowCount(0)
        for row, iface in enumerate(interfaces):
            self.table.insertRow(row)
            self._set_readonly(row, 0, iface["connection"])
            self._set_readonly(row, 1, self._get_link_status_text(iface))
            self._set_readonly(row, 2, iface["description"])
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(iface["ip"]))
            self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(iface["subnet"]))
            self.table.setItem(row, 5, QtWidgets.QTableWidgetItem(iface["gateway"]))
            self.table.setItem(row, 6, QtWidgets.QTableWidgetItem(iface["mode"]))
        self.table.resizeColumnsToContents()

    def _get_text(self, row, col):
        item = self.table.item(row, col)
        return item.text().strip() if item else ""

    def _set_readonly(self, row, col, text):
        item = QtWidgets.QTableWidgetItem(text)
        item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, col, item)

    def _get_link_status_text(self, iface):
        link_state = iface.get("link", "—").lower()
        gateway = str(iface.get("gateway", "")).strip()
        if "down" in link_state:
            return "Down"
        if gateway in ("—", "", "none", "0.0.0.0"):
            return "Network"
        return "Internet"
