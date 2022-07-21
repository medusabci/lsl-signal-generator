"""
Author:   Eduardo Santamaría-Vázquez
Date:     09 June 2021
Version:  0.1
"""

# PYTHON MODULES
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5 import uic
from signal_generator import SignalGenerator
from utils.gui_notifications import NotificationStack
from utils import gui_utils
from utils import theme_dark
import sys, os, ctypes, threading

# Load the .ui file
gui_main_user_interface = uic.loadUiType("signal_generator.ui")[0]

# Status constants
PD_NOT_CONNECTED = 'Not connected '
PD_READY = 'Ready '
PD_RECORDING = 'Recording... '
LSL_NOT_SENDING = 'Not sending '
LSL_SENDING = 'Transmitting... '


class SignalGeneratorGUI(QMainWindow, gui_main_user_interface):

    def __init__(self):
        try:
            QMainWindow.__init__(self)
            # Setup UI
            self.setupUi(self)
            self.resize(400, 450)

            # Tell windows that this application is not pythonw.exe so it can
            # have its own icon
            signalgenid = u'gib.medusa.signalgen'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                signalgenid)
            threading.current_thread().name = "SignalGen_MainGUI"

            # Initialize the notification stack
            self.notifications = NotificationStack(parent=self)
            # Initialize the application
            self.dir = os.path.dirname(__file__)
            self.stl = gui_utils.set_css_and_theme(
                self, os.path.join('utils/gui_stylesheet.css'), 'dark')
            self.setWindowIcon(QIcon('icons/icon.png'))
            self.setWindowTitle('Signal generator')
            # Current application status
            self.current_status = None
            self.set_status(PD_READY)
            # Initialize the notification stack
            self.notifications = NotificationStack(parent=self)
            # Buttons
            self.button_play.setIcon(gui_utils.get_icon(
                "play.svg", custom_color=theme_dark.THEME_GREEN))
            self.button_play.clicked.connect(self.on_play)
            self.button_stop.setIcon(gui_utils.get_icon(
                "stop.svg", custom_color=theme_dark.THEME_RED))
            self.button_stop.clicked.connect(self.on_stop)
            # Init signal generator
            self.signal_generator = None
            # Show the application
            self.show()
        except Exception as e:
            if self.signal_generator is not None:
                self.signal_generator.close()
            self.notifications.new_notification('[ERROR] %s' % str(e))
            print(str(e))

    def on_play(self):
        try:
            if self.current_status == PD_READY:
                # Get info from GUI
                stream_name = self.lineEdit_lsl_stream_name.text()
                stream_type = self.lineEdit_lsl_stream_type.text()
                chunk_size = self.spinBox_lsl_chunk_size.value()
                format = self.lineEdit_lsl_format.text()
                n_cha = self.spinBox_n_cha.value()
                l_cha_text = self.lineEdit_l_cha.text()
                if l_cha_text == 'auto':
                    l_cha = [str(c) for c in range(n_cha)]
                else:
                    l_cha = l_cha_text.split(';')
                units = self.lineEdit_signal_units.text()
                mean = self.doubleSpinBox_signal_mean.value()
                std = self.doubleSpinBox_signal_std.value()
                sample_rate = self.doubleSpinBox_signal_sample_rate.value()
                # Signal generator
                self.signal_generator = SignalGenerator(stream_name=stream_name,
                                                        stream_type=stream_type,
                                                        chunk_size=chunk_size,
                                                        format=format,
                                                        n_cha=n_cha,
                                                        l_cha=l_cha,
                                                        units=units,
                                                        mean=mean,
                                                        std=std,
                                                        sample_rate=sample_rate)
                # Init the LSL stream
                self.signal_generator.init_send_lsl()
                # Modify the status
                self.set_status(PD_RECORDING)
        except Exception as e:
            self.notifications.new_notification('[ERROR] %s' % str(e))

    def on_stop(self):
        try:
            if self.current_status == PD_RECORDING:
                # Close the LSL stream
                self.signal_generator.close_lsl()
                # Modify the status
                self.set_status(PD_READY)
        except Exception as e:
            self.notifications.new_notification('[ERROR] %s' % str(e))

    def set_status(self, status):
        try:
            # Status label and state
            self.current_status = status
            # Button enabling/disabling
            if status == PD_READY:
                self.button_play.setEnabled(True)
                self.button_stop.setEnabled(False)
            elif status == PD_RECORDING:
                self.button_play.setEnabled(False)
                self.button_stop.setEnabled(True)
            else:
                self.notifications.new_notification('Unknown status: ' + status)
                print('Exception: ' + 'Unknown status: ' + status)
        except Exception as e:
            self.notifications.new_notification('[ERROR] %s' % str(e))

    def closeEvent(self, event):
        try:
            # Let the window close
            self.signal_generator.close()
            event.accept()
        except Exception as e:
            self.notifications.new_notification('[ERROR] %s' % str(e))


if __name__ == '__main__':
    application = QApplication(sys.argv)
    main_window = SignalGeneratorGUI()
    sys.exit(application.exec_())
