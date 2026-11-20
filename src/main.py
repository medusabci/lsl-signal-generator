"""
Author:   Víctor Martínez-Cagigal & Eduardo Santamaría-Vázquez
Date:     20 November 2026
Version:  2.4

Changes in v2.4 (UI/UX and robustness, found by testing v2.3):
  - Closing the window raised an exception when the signal had never been started (signal_generator was None), so the
    window could not be closed; every Start created a new generator without closing the previous one (threads and a
    process spinning at 100 % each, and the application did not exit); a failure while creating the outlet left the
    generator and the timer running. Now there is one generator per Start and it is always closed.
  - Errors are shown in a message box (the 2 s bubble of v2.3 cut the text) and the parameters are validated before
    starting (empty name, labels that do not match the channels, ...). The labels field turns red while they do not match.
  - The parameters are locked while transmitting (changing them had no effect) and the format is a list of the valid
    values (v2.3 accepted any text and failed when starting). Tooltips explain every parameter.
  - The status shows what happens (stopped / generating / transmitting), the effective rate and whether any receiver is
    reading the stream. The signal is generated in a thread, so the window does not freeze.
  - Whenever the number of channels changes (arrows, keyboard or mouse wheel) the labels are rewritten for that number.
  - The last parameters are remembered between runs; there is a log file (logs/); the resources are found whatever the
    working directory is, and nothing is written in the installation folder.
"""

import os
import sys
import threading


def _set_working_directory():
    """ The resources (.ui, style, images) are loaded with relative paths: use the folder of the bundle / of src/. """
    base = getattr(sys, '_MEIPASS', None) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
    if base:
        os.chdir(base)


_set_working_directory()

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import Qt, QTimer, QSettings, pyqtSignal
from PyQt5 import uic
import ctypes
import socket

import constants
from constants import *
import logging_setup
from gui import gui_utils
from signal_generator import SignalGenerator

log = logging_setup.get_logger('gui')

# Load the .ui file
gui_main_user_interface = uic.loadUiType(gui_utils.resource_path("signal_generator.ui"))[0]

# Status constants
STATUS_STOPPED = 'stopped'
STATUS_GENERATING = 'generating'
STATUS_TRANSMITTING = 'transmitting'

TOOLTIPS = {
    'lineEdit_lsl_stream_name': 'Name of the LSL stream. Receivers (MEDUSA, LabRecorder...) find the stream by its name.',
    'lineEdit_lsl_stream_type': 'Type of the LSL stream (for example EEG). It is also the type of every channel.',
    'spinBox_lsl_chunk_size': 'Samples sent together in each LSL push. A smaller chunk lowers the latency but uses more '
                              'CPU; 16 samples at 250 Hz is a chunk every 64 ms. The rate is always the sample rate.',
    'comboBox_lsl_format': 'Data type of the samples. float32 is the usual one; int16 and int32 round the signal '
                           '(the EEG amplitude is about +-100).',
    'lineEdit_hostname': 'Name of this computer (part of the source id of the stream).',
    'spinBox_n_cha': 'Number of channels of the stream.',
    'lineEdit_l_cha': 'Labels of the channels separated by ";". There must be one per channel. They are replaced by '
                      'the standard 10-20 / 10-10 names whenever the number of channels changes.',
    'lineEdit_signal_units': 'Units written in the meta-data of the channels (for example uV).',
    'doubleSpinBox_signal_sample_rate': 'Nominal sample rate of the stream. The chunks are sent against an absolute '
                                        'schedule, so the real rate does not drift from this value.',
    'comboBox_generator': 'EEG (closed eyes): pink noise + 10 and 20 Hz tones. EEG (open eyes): pink noise only. '
                          'Uniform: white noise with the mean and standard deviation below.',
    'checkBox_ac_power': 'Adds the 50 Hz power-line interference and its 100 Hz harmonic.',
    'checkBox_pink_online': 'Generates the 1/f noise with the Voss-McCartney algorithm. Unchecked: it is generated '
                            'with an inverse FFT (a loop of 20 s of noise).',
    'doubleSpinBox_signal_mean': 'Mean of the Uniform generator.',
    'doubleSpinBox_signal_std': 'Standard deviation of the Uniform generator.',
    'button_play': 'Creates the LSL stream and starts sending the signal.',
    'button_stop': 'Stops the transmission and closes the LSL stream.',
}

# Parameters remembered between runs: (widget attribute, QSettings key, type)
REMEMBERED = [
    ('lineEdit_lsl_stream_name', 'stream_name', str), ('lineEdit_lsl_stream_type', 'stream_type', str),
    ('spinBox_lsl_chunk_size', 'chunk_size', int), ('comboBox_lsl_format', 'format', str),
    ('spinBox_n_cha', 'n_cha', int), ('lineEdit_l_cha', 'labels', str), ('lineEdit_signal_units', 'units', str),
    ('doubleSpinBox_signal_sample_rate', 'sample_rate', float), ('comboBox_generator', 'generator', str),
    ('checkBox_ac_power', 'eeg_ac', bool), ('checkBox_pink_online', 'pink_online', bool),
    ('doubleSpinBox_signal_mean', 'uniform_mean', float), ('doubleSpinBox_signal_std', 'uniform_std', float),
]


class SignalGeneratorGUI(QMainWindow, gui_main_user_interface):

    # Emitted from the thread that generates the signal: (generator, exception)
    generator_ready = pyqtSignal(object, object)

    def __init__(self):
        QMainWindow.__init__(self)
        self.signal_generator = None
        self.current_status = None
        self._closing = False
        self.settings = QSettings('GIB-UVa', 'SignalGenerator')

        # Setup UI
        self.setupUi(self)

        # Tell windows that this application is not pythonw.exe so it can have its own icon
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(u'gib.medusa.signalgen')
        except Exception:
            pass
        threading.current_thread().name = "SignalGen_MainGUI"

        # Initialize the application
        self.theme_colors = gui_utils.get_theme_colors('dark')
        self.stl = gui_utils.set_css_and_theme(self, self.theme_colors)
        self.setWindowIcon(QIcon(gui_utils.resource_path('gui/images/icons/icon.png')))
        self.setWindowTitle('Signal generator v%s' % constants.VERSION)
        self.statusBar().hide()
        self.menuBar().hide()

        # Set current hostname
        self.lineEdit_hostname.setText(socket.gethostname())

        # Buttons
        self.button_play.setIcon(gui_utils.get_icon("play.svg", custom_color=self.theme_colors['THEME_GREEN']))
        self.button_play.clicked.connect(self.on_play)
        self.button_stop.setIcon(gui_utils.get_icon("stop.svg", custom_color=self.theme_colors['THEME_RED']))
        self.button_stop.clicked.connect(self.on_stop)
        for name, text in TOOLTIPS.items():
            getattr(self, name).setToolTip(text)

        # Remembered parameters
        self.load_settings()

        # Listeners
        self.spinBox_n_cha.valueChanged.connect(self.on_change_n_cha)
        self.lineEdit_l_cha.textChanged.connect(self.check_labels)
        self.comboBox_generator.currentTextChanged.connect(self.on_change_generator)
        self.generator_ready.connect(self.on_generator_ready)
        if not self.settings.contains('labels'):
            self.on_change_n_cha()          # First run: labels of the default number of channels
        self.on_change_generator()
        self.check_labels()

        # Timer to update the status while transmitting
        self.update_samples_timer = QTimer()
        self.update_samples_timer.timeout.connect(self.on_update_samples)

        self.set_status(STATUS_STOPPED)
        log.info('main window created')
        self.show()

    # ------------------------------------------------------------------ settings
    def load_settings(self):
        try:
            for attr, key, type_ in REMEMBERED:
                if not self.settings.contains(key):
                    continue
                widget, value = getattr(self, attr), self.settings.value(key, type=type_)
                if isinstance(widget, QLineEdit):
                    widget.setText(value)
                elif isinstance(widget, QComboBox):
                    gui_utils.select_entry_combobox_with_text(widget, value)
                elif isinstance(widget, QCheckBox):
                    widget.setChecked(value)
                else:
                    widget.setValue(value)
        except Exception:
            log.exception('could not load the remembered parameters')

    def save_settings(self):
        try:
            for attr, key, type_ in REMEMBERED:
                widget = getattr(self, attr)
                if isinstance(widget, QLineEdit):
                    value = widget.text()
                elif isinstance(widget, QComboBox):
                    value = widget.currentText()
                elif isinstance(widget, QCheckBox):
                    value = widget.isChecked()
                else:
                    value = widget.value()
                self.settings.setValue(key, value)
        except Exception:
            log.exception('could not save the parameters')

    # ------------------------------------------------------------------ parameters
    def get_labels(self):
        """ List of the labels of the field (empty list if the field is empty). """
        text = self.lineEdit_l_cha.text().strip()
        return [label.strip() for label in text.split(';')] if text else []

    def check_labels(self):
        """ Marks the labels field in red while the number of labels does not match the number of channels. """
        labels, n_cha = self.get_labels(), self.spinBox_n_cha.value()
        valid = len(labels) == n_cha and all(labels)
        self.lineEdit_l_cha.setProperty('invalid', not valid)
        self.lineEdit_l_cha.style().unpolish(self.lineEdit_l_cha)
        self.lineEdit_l_cha.style().polish(self.lineEdit_l_cha)
        base = TOOLTIPS['lineEdit_l_cha']
        self.lineEdit_l_cha.setToolTip(base if valid else '%i labels for %i channels (or an empty label). %s' %
                                       (len(labels), n_cha, base))
        return valid

    @staticmethod
    def default_labels(n_cha):
        """ First n_cha labels of EEG_CHANNELS (10-20, then 10-10, then 10-05); numbers if there are not enough. """
        l_cha = EEG_CHANNELS[:n_cha] + [str(i) for i in range(len(EEG_CHANNELS), n_cha)]
        return ';'.join(l_cha)

    def on_change_n_cha(self):
        # As in v2.3: every change of the number of channels (arrows, typing or mouse wheel) rewrites the labels with the
        # standard names for that number of channels
        self.lineEdit_l_cha.setText(self.default_labels(self.spinBox_n_cha.value()))
        self.check_labels()

    def on_change_generator(self):
        uniform = self.comboBox_generator.currentText() == "Uniform"
        self.doubleSpinBox_signal_mean.setEnabled(uniform)
        self.doubleSpinBox_signal_std.setEnabled(uniform)
        self.checkBox_ac_power.setEnabled(not uniform)
        self.checkBox_pink_online.setEnabled(not uniform)

    def read_parameters(self):
        """ Parameters of the GUI for the SignalGenerator. Raises ValueError with a message for the user. """
        stream_name = self.lineEdit_lsl_stream_name.text().strip()
        if not stream_name:
            self.lineEdit_lsl_stream_name.setFocus()
            raise ValueError('Write a name for the LSL stream.')
        n_cha = self.spinBox_n_cha.value()
        l_cha = self.get_labels()
        if len(l_cha) != n_cha or not all(l_cha):
            self.lineEdit_l_cha.setFocus()
            raise ValueError('There are %i channel labels but %i channels. Write one label per channel, separated by '
                             '";" (for example FZ;CZ;PZ;OZ).' % (len(l_cha), n_cha))
        gen_settings = dict()
        gen_settings["gen_type"] = self.comboBox_generator.currentText()
        gen_settings["eeg_ac"] = self.checkBox_ac_power.isChecked()
        gen_settings["eeg_pink"] = "real-time" if self.checkBox_pink_online.isChecked() else "offline"
        gen_settings["uniform_mean"] = self.doubleSpinBox_signal_mean.value()
        gen_settings["uniform_std"] = self.doubleSpinBox_signal_std.value()
        return dict(stream_name=stream_name, stream_type=self.lineEdit_lsl_stream_type.text().strip(),
                    chunk_size=self.spinBox_lsl_chunk_size.value(), format=self.comboBox_lsl_format.currentText(),
                    n_cha=n_cha, l_cha=l_cha, units=self.lineEdit_signal_units.text().strip(),
                    sample_rate=self.doubleSpinBox_signal_sample_rate.value(), gen_settings=gen_settings,
                    hostname=self.lineEdit_hostname.text())

    # ------------------------------------------------------------------ start / stop
    def on_play(self):
        if self.current_status != STATUS_STOPPED:
            return
        try:
            params = self.read_parameters()
        except ValueError as e:
            QMessageBox.warning(self, 'Check the parameters', str(e))
            return
        self.save_settings()
        log.info('start requested: %s', {k: v for k, v in params.items() if k != 'l_cha'})
        self.set_status(STATUS_GENERATING)
        QApplication.setOverrideCursor(Qt.BusyCursor)
        threading.Thread(name='SignalGenerator_Build', target=self._build, args=(params,), daemon=True).start()

    def _build(self, params):
        """ Generates the signal (can take a few seconds with many channels). Runs in its own thread. """
        try:
            self.generator_ready.emit(SignalGenerator(**params), None)
        except Exception as e:
            log.exception('could not create the generator')
            self.generator_ready.emit(None, e)

    def on_generator_ready(self, generator, error):
        QApplication.restoreOverrideCursor()
        if self._closing:
            if generator is not None:
                generator.close()
            return
        try:
            if error is not None:
                raise error
            generator.init_send_lsl()
            self.signal_generator = generator
            self.set_status(STATUS_TRANSMITTING)
            self.update_samples_timer.start(1000)
            self.on_update_samples()
        except Exception as e:
            log.exception('could not start the transmission')
            if generator is not None:
                generator.close()
            self.signal_generator = None
            self.set_status(STATUS_STOPPED)
            QMessageBox.critical(self, 'The stream could not be started', str(e))

    def on_stop(self):
        if self.current_status != STATUS_TRANSMITTING:
            return
        self.stop_generator()
        self.set_status(STATUS_STOPPED)

    def stop_generator(self):
        """ Stops the transmission and releases the generator. It never raises. """
        self.update_samples_timer.stop()
        generator, self.signal_generator = self.signal_generator, None
        if generator is not None:
            try:
                generator.close()
            except Exception:
                log.exception('error while closing the generator')

    # ------------------------------------------------------------------ status
    def set_status(self, status):
        self.current_status = status
        stopped = status == STATUS_STOPPED
        self.button_play.setEnabled(stopped)
        self.button_stop.setEnabled(status == STATUS_TRANSMITTING)
        # The parameters are read when the stream starts: they cannot be changed while it exists
        self.parameter_box.setEnabled(stopped)
        self.groupBox.setEnabled(stopped)
        if stopped:
            self.label_status.setText('Stopped. Press Start to create the LSL stream.')
        elif status == STATUS_GENERATING:
            self.label_status.setText('Generating the signal...')

    def on_update_samples(self):
        generator = self.signal_generator
        if self.current_status != STATUS_TRANSMITTING or generator is None:
            return
        n_samples = generator.n_chunks_sent * generator.chunk_size
        receivers = 'a receiver is reading the stream' if generator.has_consumers() else 'no receiver is reading it yet'
        self.label_status.setText(
            "Transmitting \"%s\": %i samples x %i channels sent, %.2f Hz (nominal %g Hz); %s." %
            (generator.stream_name, n_samples, generator.n_cha, generator.effective_rate(), generator.sample_rate,
             receivers))

    def closeEvent(self, event):
        self._closing = True
        self.save_settings()
        self.stop_generator()
        log.info('window closed')
        event.accept()


if __name__ == '__main__':
    logging_setup.setup_logging()
    application = QApplication(sys.argv)
    main_window = SignalGeneratorGUI()
    sys.exit(application.exec_())
