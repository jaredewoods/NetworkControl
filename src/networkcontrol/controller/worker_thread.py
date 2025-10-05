from PyQt6 import QtCore
from networkcontrol.model.network_model import get_network_interfaces


class NetworkMonitorWorker(QtCore.QThread):
    """
    Background thread that periodically polls network interface data.

    Emits:
        update_signal (list): List of interface dictionaries
    """
    update_signal = QtCore.pyqtSignal(list)

    def __init__(self, interval: int = 10):
        super().__init__()
        self.interval = interval  # seconds
        self._running = True

    def run(self):
        """Loop and emit interface data until stopped."""
        while self._running:
            try:
                data = get_network_interfaces()
                self.update_signal.emit(data)
            except Exception:
                # Suppress transient failures (e.g., PowerShell access)
                pass
            self.msleep(self.interval * 1000)

    def stop(self):
        """Stop thread safely."""
        self._running = False
        self.quit()
        self.wait()
