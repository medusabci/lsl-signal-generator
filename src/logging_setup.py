"""
Author:   Víctor Martínez-Cagigal & Eduardo Santamaría-Vázquez
Date:     20 November 2026
Version:  2.4

Logging for the signal generator (same approach as signal-gtec). The goal is to be able to find out afterwards why the application closed or misbehaved:

  - A rotating log file (logs/signal_generator_<date>.log) with timestamp (ms), level, thread and module.
  - Uncaught exceptions of the main thread and of any other thread (sys.excepthook / threading.excepthook).
  - faulthandler: if the process dies because of a native crash (access violation in Qt, cffi or the g.tec DLL), Python
    writes the traceback of every thread in logs/native_crash.log. A silent disappearance of the window is usually that.
  - Qt warnings/criticals (e.g. "QObject::setParent: Cannot set parent, new parent is in a different thread", which
    reveals widgets touched from a worker thread) are redirected to the log.
  - Start/exit markers with versions, so a missing "clean exit" line means that the process was killed or crashed.
"""
import atexit
import faulthandler
import logging
import logging.handlers
import os
import platform
import sys
import threading
import time

from version import VERSION

LOGGER_NAME = 'signal_generator'
_state = {'initialized': False, 'fault_file': None}


def get_logger(name=None):
    """ Returns a child logger of 'signal_generator' (e.g., get_logger('generator')). """
    return logging.getLogger(LOGGER_NAME if not name else LOGGER_NAME + '.' + name)


def get_log_dir():
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # src/
    return os.path.join(base, 'logs')


def setup_logging(level=logging.DEBUG):
    """ Initializes logging. Safe to call more than once. Returns the path of the log file. """
    if _state['initialized']:
        return _state['log_path']
    log_dir = get_log_dir()
    try:
        os.makedirs(log_dir, exist_ok=True)
        probe = os.path.join(log_dir, '.write_test')        # Installed in Program Files the folder may be read-only
        with open(probe, 'w'):
            pass
        os.remove(probe)
    except OSError:
        log_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'SignalGenerator', 'logs')
        os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'signal_generator_%s.log' % time.strftime('%Y%m%d'))

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False
    fmt = logging.Formatter('%(asctime)s.%(msecs)03d | %(levelname)-8s | %(threadName)-18s | %(name)s | %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S')
    fh = logging.handlers.RotatingFileHandler(log_path, maxBytes=10 * 1024 * 1024, backupCount=10, encoding='utf-8')
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    if sys.stderr is not None:          # No console when frozen with --windowed
        sh = logging.StreamHandler(sys.stderr)
        sh.setLevel(logging.INFO)
        sh.setFormatter(fmt)
        logger.addHandler(sh)

    # Native crashes: keep the file open for the whole life of the process
    try:
        fault_path = os.path.join(log_dir, 'native_crash.log')
        fault_file = open(fault_path, 'a', buffering=1)
        fault_file.write('\n===== process start %s (pid %d) =====\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), os.getpid()))
        faulthandler.enable(file=fault_file, all_threads=True)
        _state['fault_file'] = fault_file
    except Exception:
        logger.exception('Could not enable faulthandler')

    # Uncaught exceptions
    def _excepthook(exc_type, exc, tb):
        logger.critical('Uncaught exception in the main thread', exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)

    def _threading_excepthook(args):
        logger.critical('Uncaught exception in thread "%s"', args.thread.name if args.thread else '?',
                        exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    sys.excepthook = _excepthook
    threading.excepthook = _threading_excepthook

    # Qt messages
    try:
        from PyQt5 import QtCore
        qt_logger = get_logger('qt')

        qt_counts = {}
        QT_MAX_REPEATS = 3      # The same Qt message (e.g., "Unknown property cursor" of the stylesheet) can appear
                                # hundreds of times: the first ones are logged, the rest are counted

        def _qt_handler(msg_type, context, message):
            n = qt_counts[message] = qt_counts.get(message, 0) + 1
            if n > QT_MAX_REPEATS:
                return
            level_ = {QtCore.QtDebugMsg: logging.DEBUG, QtCore.QtInfoMsg: logging.INFO,
                      QtCore.QtWarningMsg: logging.WARNING, QtCore.QtCriticalMsg: logging.ERROR,
                      QtCore.QtFatalMsg: logging.CRITICAL}.get(msg_type, logging.WARNING)
            qt_logger.log(level_, '%s (%s:%s)%s', message, getattr(context, 'file', None),
                          getattr(context, 'line', None),
                          '  [further repetitions are only counted]' if n == QT_MAX_REPEATS else '')

        QtCore.qInstallMessageHandler(_qt_handler)

        def _qt_summary():
            for m, n in qt_counts.items():
                if n > QT_MAX_REPEATS:
                    qt_logger.info('Qt message repeated %d times: %s', n, ' '.join(m.split())[:200])

        atexit.register(_qt_summary)
    except Exception:
        logger.exception('Could not install the Qt message handler')

    # Marker of a running process: if it is still there at the next start, the previous run did not end cleanly
    # (crash, kill, or the whole PC rebooted: compare with Event Viewer > System > "Kernel-Power 41" / "BugCheck 1001")
    marker = os.path.join(log_dir, 'running.marker')
    try:
        if os.path.exists(marker):
            with open(marker) as f:
                prev = f.read().strip()
            logger.warning('The previous run did NOT end cleanly (marker left by: %s). Check native_crash.log and '
                           'the Windows event log (Kernel-Power 41 / BugCheck 1001 mean that the PC itself crashed '
                           'or rebooted)', prev)
        with open(marker, 'w') as f:
            f.write('pid %d, started %s' % (os.getpid(), time.strftime('%Y-%m-%d %H:%M:%S')))
    except Exception:
        logger.exception('Could not handle the running marker')

    def _on_exit():
        logger.info('Clean exit of the process (atexit). If this line is missing, the process was killed or crashed')
        try:
            os.remove(marker)
        except OSError:
            pass

    atexit.register(_on_exit)

    logger.info('=' * 70)
    logger.info('signal generator v%s started | pid %d | python %s %s | %s | frozen=%s', VERSION, os.getpid(), platform.python_version(),
                platform.architecture()[0], platform.platform(), getattr(sys, 'frozen', False))
    for mod in ('PyQt5.QtCore', 'numpy', 'pylsl'):
        try:
            m = __import__(mod, fromlist=['x'])
            ver = getattr(m, 'PYQT_VERSION_STR', None) or getattr(m, '__version__', None) \
                or getattr(m, '__version', None)
            logger.info('module %s %s', mod, ver)
        except Exception as e:
            logger.info('module %s not available (%s)', mod, e)
    logger.info('log file: %s', log_path)
    _state['initialized'] = True
    _state['log_path'] = log_path
    return log_path
