"""
Author:   Víctor Martínez-Cagigal & Eduardo Santamaría-Vázquez
Date:     02 June 2023
Version:  2.2
"""

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import QTimer
from PyQt5 import uic
import constants
from signal_generator import SignalGenerator
from gui.gui_notifications import NotificationStack
from gui import gui_utils
import sys, os, ctypes, threading
from constants import *
import numpy as np
import socket
import multiprocessing

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
            self.theme_colors = gui_utils.get_theme_colors('dark')
            self.stl = gui_utils.set_css_and_theme(self, self.theme_colors)
            self.setWindowIcon(QIcon('gui/images/icons/icon.png'))
            self.setWindowTitle('Signal generator v%s' % constants.VERSION)

            # Current application status
            self.current_status = None
            self.set_status(PD_READY)

            # Initialize the notification stack
            self.notifications = NotificationStack(parent=self)

            # Set current hostname
            self.lineEdit_hostname.setText(socket.gethostname())

            # Buttons
            self.button_play.setIcon(
                gui_utils.get_icon("play.svg",
                                   custom_color=self.theme_colors['THEME_GREEN']
                                   )
            )
            self.button_play.clicked.connect(self.on_play)
            self.button_stop.setIcon(
                gui_utils.get_icon("stop.svg",
                                   custom_color=self.theme_colors['THEME_RED']))
            self.button_stop.clicked.connect(self.on_stop)

            # Listeners
            self.spinBox_n_cha.valueChanged.connect(self.on_change_n_cha)
            self.comboBox_generator.currentTextChanged.connect(
                self.on_change_generator)
            self.on_change_n_cha()
            self.on_change_generator()

            # Init signal generator
            self.signal_generator = None

            # Thread to update the sent samples
            self.update_samples_timer = QTimer()
            self.update_samples_timer.timeout.connect(self.on_update_samples)

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
                hostname = self.lineEdit_hostname.text()
                format = self.lineEdit_lsl_format.text()
                n_cha = self.spinBox_n_cha.value()
                l_cha_text = self.lineEdit_l_cha.text()
                if l_cha_text == 'auto':
                    l_cha = [str(c) for c in range(n_cha)]
                else:
                    l_cha = l_cha_text.split(';')
                units = self.lineEdit_signal_units.text()
                sample_rate = self.doubleSpinBox_signal_sample_rate.value()

                gen_settings = dict()
                gen_settings["gen_type"] = self.comboBox_generator.currentText()
                gen_settings["eeg_ac"] = self.checkBox_ac_power.isChecked()
                gen_settings["eeg_pink"] = "real-time" if \
                    self.checkBox_pink_online.isChecked() else "offline"
                gen_settings["uniform_mean"] = \
                    self.doubleSpinBox_signal_mean.value()
                gen_settings["uniform_std"] = \
                    self.doubleSpinBox_signal_std.value()

                # Signal generator
                self.signal_generator = SignalGenerator(
                    stream_name=stream_name, stream_type=stream_type,
                    chunk_size=chunk_size, format=format, n_cha=n_cha,
                    l_cha=l_cha, units=units, sample_rate=sample_rate,
                    gen_settings=gen_settings, hostname=hostname)

                # Thread to update number of EEG samples sent
                self.update_samples_timer.start(1000)

                # Init the LSL stream
                self.signal_generator.init_send_lsl()

                # Modify the status
                self.set_status(PD_RECORDING)
        except Exception as e:
            self.notifications.new_notification('[ERROR] %s' % str(e))

    def on_stop(self):
        try:
            if self.current_status == PD_RECORDING:
                # Stop the update samples thread
                self.update_samples_timer.stop()
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
                self.label_status.setText("Stopped")
            elif status == PD_RECORDING:
                self.button_play.setEnabled(False)
                self.button_stop.setEnabled(True)
                self.label_status.setText("Recording")
            else:
                self.notifications.new_notification('Unknown status: ' + status)
                print('Exception: ' + 'Unknown status: ' + status)
        except Exception as e:
            self.notifications.new_notification('[ERROR] %s' % str(e))

    def on_update_samples(self):
        if self.current_status == PD_RECORDING:
            n_samples = self.signal_generator.n_chunks_sent * \
                        self.signal_generator.chunk_size
            n_channels = self.signal_generator.n_cha
            approx_fs = 0
            if len(self.signal_generator.buffer_sent_times) >= 2:
                approx_fs = self.signal_generator.chunk_size / np.mean(np.diff(
                    np.array(self.signal_generator.buffer_sent_times)))
            self.label_status.setText(
                "Sent: [%i samples x %i channels] - Approx. fs of %.2f Hz" %
                (n_samples, n_channels, approx_fs)
            )

    def on_change_n_cha(self):
        n_cha = self.spinBox_n_cha.value()

        # Get a default list of channels
        if n_cha <= len(EEG_10_20):
            l_cha = EEG_10_20[:n_cha]
        elif n_cha <= len(EEG_10_10):
            l_cha = EEG_10_10[:n_cha]
        elif n_cha <= len(EEG_10_05):
            l_cha = EEG_10_05[:n_cha]
        else:
            l_cha = [str(i) for i in range(n_cha)]
        self.lineEdit_l_cha.setText(';'.join(l_cha))

    def on_change_generator(self):
        if self.comboBox_generator.currentText() == "Uniform":
            self.doubleSpinBox_signal_mean.setEnabled(True)
            self.doubleSpinBox_signal_std.setEnabled(True)
            self.checkBox_ac_power.setEnabled(False)
            self.checkBox_pink_online.setEnabled(False)
        else:
            self.doubleSpinBox_signal_mean.setEnabled(False)
            self.doubleSpinBox_signal_std.setEnabled(False)
            self.checkBox_ac_power.setEnabled(True)
            self.checkBox_pink_online.setEnabled(True)

    def closeEvent(self, event):
        try:
            # Let the window close
            self.signal_generator.close()
            event.accept()
        except Exception as e:
            self.notifications.new_notification('[ERROR] %s' % str(e))


if __name__ == '__main__':
    multiprocessing.freeze_support()
    application = QApplication(sys.argv)
    main_window = SignalGeneratorGUI()
    sys.exit(application.exec_())
