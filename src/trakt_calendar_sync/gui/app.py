"""PySide6 application bootstrap: first-run setup wizard, then the main
window. Both are on-demand - there's no background process, just this GUI
plus whatever scheduler.enable_auto_sync() registered with the OS.
"""

import sys

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow
from .setup_wizard import SetupWizard, is_setup_complete


def run() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Trakt Calendar Sync")

    if not is_setup_complete():
        wizard = SetupWizard()
        if wizard.exec() != SetupWizard.DialogCode.Accepted:
            return

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
