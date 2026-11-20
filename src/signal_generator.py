"""
Author:   Víctor Martínez-Cagigal & Eduardo Santamaría-Vázquez
Date:     20 November 2026
Version:  2.4

Changes in v2.4 (found by testing v2.3 against what was learnt with signal-gtec):
  - Timing: v2.3 slept for update_ms after every chunk, so the time spent in each iteration accumulated and the stream
    ran slower than the nominal rate (-528 ppm measured: 249.868 Hz instead of 250 Hz, 1.9 s per hour). Now the chunks
    are paced against an ABSOLUTE schedule (next = start + k * chunk_period): no drift, whatever the jitter.
  - CPU: v2.3 used a timer process and an IO thread that spun at 100 % each. Now there is a single sender thread that
    sleeps and only spins during the last ~1.5 ms before each chunk (timeBeginPeriod(1) on Windows).
  - Stamps: each chunk is stamped with local_clock() when it is pushed (arrival-style stamping, like gNEEDaccess.exe and
    signal-gtec); LSL back-fills the previous samples with 1/nominal_srate.
  - Data: the chunks are pushed as C-contiguous numpy arrays of the data type of the stream (no .tolist()), the
    channel-count / chunk-size 1 cases work (np.squeeze broke them) and the buffer has a size limit (v2.3 could ask for
    several GB with many channels and a large chunk).
  - Life cycle: the sender thread exists only while the stream is open; start/stop/start no longer leaks threads and
    processes, close() can be called more than once, and nothing is left running when the window is closed.
  - Meta-data: XDF/LSL conventions (unit in singular, manufacturer, acquisition, synchronization) and no pandas.
"""

import threading
import time
from collections import deque

import numpy as np
from pylsl import StreamInfo, StreamOutlet, local_clock

from logging_setup import get_logger

log = get_logger('generator')

# Channel formats that the application can send. Names of the LSL formats -> numpy type
FORMATS = {'float32': np.float32, 'double64': np.float64, 'int32': np.int32, 'int16': np.int16}
GENERATORS = ('EEG (closed eyes)', 'EEG (open eyes)', 'Uniform')

LOOP_SECONDS = 64               # Duration of the pre-generated signal that is played in a loop (v2.3: 1000 chunks)
BUFFER_MAX_BYTES = 64 * 2 ** 20  # Maximum size of that signal
SPIN_S = 0.0015                 # The sender thread spins only during the last SPIN_S before each chunk
RESYNC_PERIODS = 20             # If the thread is this many chunk periods late (suspended PC), the schedule is restarted
SENT_TIMES_LEN = 100            # Stamps of the last chunks to estimate the effective rate


def _begin_timer_resolution(ms=1):
    """ Windows sleeps in steps of 15.6 ms unless the timer resolution is raised. Returns a function to restore it. """
    try:
        import ctypes
        winmm = ctypes.windll.winmm
        winmm.timeBeginPeriod(ms)
        return lambda: winmm.timeEndPeriod(ms)
    except Exception:
        return lambda: None


class SignalGenerator:
    """ Synthetic signal transmitted through LSL.

    Usage: SignalGenerator(...) generates the signal (it can take a few seconds), init_send_lsl() creates the outlet and
    starts the sender thread, close_lsl() stops the transmission (the object can be started again) and close() releases
    everything.
    """

    def __init__(self, stream_name, stream_type, chunk_size, format, n_cha,
                 l_cha, units, sample_rate, gen_settings, hostname):

        # Error check
        if not stream_name or not str(stream_name).strip():
            raise ValueError('The stream name cannot be empty')
        if int(chunk_size) < 1:
            raise ValueError('The chunk size must be at least 1 sample')
        if int(n_cha) < 1:
            raise ValueError('The number of channels must be at least 1')
        if not float(sample_rate) > 0:
            raise ValueError('The sample rate must be greater than 0')
        if format not in FORMATS:
            raise ValueError('Unknown channel format "%s" (valid: %s)' % (format, ', '.join(FORMATS)))
        if len(l_cha) != n_cha:
            raise ValueError('The number of channel labels (%i) does not match with the number of channels (%i)' %
                             (len(l_cha), n_cha))
        if gen_settings["gen_type"] not in GENERATORS:
            raise ValueError("Unknown generator: %s" % gen_settings["gen_type"])

        # Parameters
        self.stream_name = stream_name
        self.stream_type = stream_type
        self.chunk_size = int(chunk_size)
        self.format = format
        self.n_cha = int(n_cha)
        self.l_cha = list(l_cha)
        self.units = units
        self.sample_rate = float(sample_rate)
        self.gen_settings = gen_settings
        self.hostname = hostname

        # Initialize the generator
        if self.gen_settings["gen_type"] == "EEG (closed eyes)":
            tones = [(10, 11), (20, 7)]
            if self.gen_settings["eeg_ac"]:
                tones += [(50, 12), (100, 7)]
            self.generator = EEGGenerator(
                fs=self.sample_rate, n_cha=self.n_cha, tones=tones,
                pink_method=self.gen_settings["eeg_pink"])
        elif self.gen_settings["gen_type"] == "EEG (open eyes)":
            tones = []
            if self.gen_settings["eeg_ac"]:
                tones += [(50, 12), (100, 7)]
            self.generator = EEGGenerator(
                fs=self.sample_rate, n_cha=self.n_cha, tones=tones,
                pink_method=self.gen_settings["eeg_pink"])
        else:
            self.generator = UniformGenerator(
                n_cha=self.n_cha, mean=gen_settings["uniform_mean"],
                std=gen_settings["uniform_std"])

        # Offline generation of data
        #   This allows us to avoid delays regarding real-time EEG generation. Instead, we generate N chunks of data
        #   beforehand and loop over them circularly. They are stored with the data type of the stream
        self.n_buffer_chunks = self._choose_n_chunks()
        t0 = time.perf_counter()
        buffer = self.generator.get_chunks(self.n_buffer_chunks, self.chunk_size)
        self.eeg_buffer = self._to_format(buffer)
        log.info('signal generated: %d chunks x %d samples x %d channels (%s, %.1f MB, loop of %.1f s) in %.2f s',
                 self.n_buffer_chunks, self.chunk_size, self.n_cha, self.format, self.eeg_buffer.nbytes / 2 ** 20,
                 self.n_buffer_chunks * self.chunk_size / self.sample_rate, time.perf_counter() - t0)

        # Transmission state
        self.n_chunks_sent = 0
        self.buffer_sent_times = deque(maxlen=SENT_TIMES_LEN)
        self.n_late = 0                 # chunks that left more than half a chunk period late
        self.max_late_s = 0.0
        self.n_resync = 0
        self.lsl_outlet = None
        self._io_stop = threading.Event()      # set to stop the sender thread (it also interrupts its sleep)
        self._io_thread = None

    # ------------------------------------------------------------------ signal buffer
    def _choose_n_chunks(self):
        """ Number of chunks of the loop: about LOOP_SECONDS seconds, limited to BUFFER_MAX_BYTES. If possible the loop
        lasts a whole number of seconds, so that the tones (integer frequencies) are continuous when it restarts. """
        bytes_per_chunk = self.chunk_size * self.n_cha * np.dtype(FORMATS[self.format]).itemsize
        target = max(1, int(round(LOOP_SECONDS * self.sample_rate / self.chunk_size)))
        target = max(1, min(target, BUFFER_MAX_BYTES // bytes_per_chunk))
        for n in range(target, 2 * target + 1):
            secs = n * self.chunk_size / self.sample_rate
            if secs >= 1 and abs(secs - round(secs)) < 1e-9 and n * bytes_per_chunk <= BUFFER_MAX_BYTES:
                return n
        return target

    def _to_format(self, data):
        dtype = FORMATS[self.format]
        if np.issubdtype(dtype, np.integer):
            info = np.iinfo(dtype)
            data = np.clip(np.rint(data), info.min, info.max)
        return np.ascontiguousarray(data, dtype=dtype)

    # ------------------------------------------------------------------ LSL
    def init_send_lsl(self):
        """ Creates the LSL outlet and starts the sender thread. """
        if self._io_thread is not None and self._io_thread.is_alive():
            raise RuntimeError('The transmission is already running')
        source_id = '_'.join([self.stream_name, self.stream_type, str(self.n_cha), str(self.sample_rate),
                              self.format, self.hostname])
        lsl_info = StreamInfo(name=self.stream_name, type=self.stream_type, channel_count=self.n_cha,
                              nominal_srate=self.sample_rate, channel_format=self.format, source_id=source_id)
        self._fill_metadata(lsl_info)
        self.lsl_outlet = StreamOutlet(info=lsl_info, chunk_size=self.chunk_size, max_buffered=360)
        self.n_chunks_sent = 0
        self.buffer_sent_times.clear()
        self.n_late = 0
        self.max_late_s = 0.0
        self.n_resync = 0
        self._io_stop.clear()
        self._io_thread = threading.Thread(name='SignalGenerator_IO_Thread', target=self._send_data,
                                           args=(self.lsl_outlet,), daemon=True)
        self._io_thread.start()
        log.info('LSL stream created (source_id=%s, %.4f Hz, chunk %d)', source_id, self.sample_rate, self.chunk_size)

    def _fill_metadata(self, lsl_info):
        """ Meta-data following the XDF/LSL conventions (https://github.com/sccn/xdf/wiki/EEG-Meta-Data). Both <unit>
        (standard) and <units> (written by v2.3 and by the MEDUSA outlet) are written, so that no receiver breaks. """
        from version import VERSION
        desc = lsl_info.desc()
        desc.append_child_value('manufacturer', 'GIB-UVa (MEDUSA)')
        acq = desc.append_child('acquisition')
        acq.append_child_value('manufacturer', 'GIB-UVa (MEDUSA)')
        acq.append_child_value('model', 'Signal generator')
        acq.append_child_value('software_version', VERSION)
        acq.append_child_value('generator', str(self.gen_settings['gen_type']))
        acq.append_child_value('chunk_size', str(self.chunk_size))
        acq.append_child_value('timestamps', 'local_clock() when each chunk is pushed (the chunks are paced against an '
                                             'absolute schedule, so the rate is exactly the nominal one); the previous '
                                             'samples are back-filled with 1/nominal_srate')
        # A synthetic signal has no acquisition delay and never drops samples
        sync = desc.append_child('synchronization')
        sync.append_child_value('can_drop_samples', 'false')
        channels = desc.append_child('channels')
        for label in self.l_cha:
            channels.append_child('channel') \
                .append_child_value('label', label) \
                .append_child_value('unit', self.units) \
                .append_child_value('units', self.units) \
                .append_child_value('type', self.stream_type)

    def has_consumers(self):
        """ True if any LSL inlet is reading the stream (it does not tell which one). """
        outlet = self.lsl_outlet
        return bool(outlet is not None and outlet.have_consumers())

    def close_lsl(self):
        """ Stops the transmission and closes the stream. It can be called more than once. """
        thread = self._io_thread
        self._io_stop.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=5)
            if thread.is_alive():
                log.error('the sender thread did not stop in 5 s')
        self._io_thread = None
        if self.lsl_outlet is not None:
            self.lsl_outlet = None
            log.info('LSL stream closed (%d chunks sent, %d late, max lateness %.2f ms, %d resynchronizations)',
                     self.n_chunks_sent, self.n_late, self.max_late_s * 1000, self.n_resync)

    def close(self):
        self.close_lsl()

    def effective_rate(self):
        """ Sample rate of the last chunks according to their stamps (0 if there are not enough chunks). """
        times = list(self.buffer_sent_times)
        if len(times) < 2 or times[-1] <= times[0]:
            return 0.0
        return (len(times) - 1) * self.chunk_size / (times[-1] - times[0])

    # ------------------------------------------------------------------ sender thread
    def _send_data(self, outlet):
        """ Pushes a chunk every chunk_size / sample_rate seconds, against an absolute schedule. """
        restore_timer = _begin_timer_resolution(1)
        period = self.chunk_size / self.sample_rate
        perf = time.perf_counter
        stop = self._io_stop
        c_idx = 0
        try:
            next_t = perf() + period
            while not stop.is_set():
                # Wait (sleeping, then spinning for the last milliseconds) until the scheduled time
                remaining = next_t - perf()
                if remaining > SPIN_S:
                    stop.wait(remaining - SPIN_S)
                    continue
                while next_t - perf() > 0:
                    pass
                if stop.is_set():
                    break

                late = perf() - next_t
                if late > RESYNC_PERIODS * period:      # PC suspended or thread starved: restart the schedule
                    self.n_resync += 1
                    log.warning('the sender thread was %.0f ms late: schedule restarted', late * 1000)
                    next_t = perf()
                    late = 0.0
                if late > period / 2:
                    self.n_late += 1
                self.max_late_s = max(self.max_late_s, late)

                timestamp = local_clock()
                outlet.push_chunk(self.eeg_buffer[c_idx], timestamp)
                self.buffer_sent_times.append(timestamp)
                self.n_chunks_sent += 1
                c_idx += 1
                if c_idx >= self.eeg_buffer.shape[0]:
                    c_idx = 0
                next_t += period
        except Exception:
            log.exception('the sender thread failed')
        finally:
            restore_timer()
            log.info('sender thread done')


class UniformGenerator:
    """ Uniform signal generator.

    Parameters
    ------------
    n_cha:  int
        Number of channels.
    mean: float
        Mean of the output signal.
    std: float
        Standard deviation of the output signal.
    """

    def __init__(self, n_cha, mean=0.0, std=1.0):
        self.n_cha = n_cha
        self.mean = mean
        self.std = std

    def get_chunk(self, chunk_size):
        """ Function to get a new chunk.

        Parameters
        ------------
        chunk_size : int
            Chunk size in samples.

        Returns
        ------------
        ndarray: [samples x channels]
            Generated chunk.
        """
        return self.std * np.random.randn(chunk_size, self.n_cha) + self.mean

    def get_chunks(self, n_chunks, chunk_size):
        """ Function to generate several chunks at once.

        Parameters
        ------------
        n_chunks : int
            Number of chunks to generate
        chunk_size : int
            Chunk size in samples.

        Returns
        ------------
        ndarray: [n_chunks x samples x channels]
            Generated chunks.
        """
        data = np.empty((n_chunks, chunk_size, self.n_cha))
        for i in range(n_chunks):
            data[i, :, :] = self.get_chunk(chunk_size)
        return data


class EEGGenerator:
    """ Synthetic EEG generator.

    Parameters
    --------------
    fs : float
        Sampling rate.
    n_cha: float
        Number of channels.
    tones : list()
        List of the tones to include in the signal, each one represented by a
        tuple containing (target frequency in Hz, amplitude).
    pink_method: basestring
        If "real-time", the pink noise is online generated using the
        Voss-McCartney algorithm. If "offline", the pink noise is generated
        using the inverse FFT, stored offline and then played each time a
        chunk is requested.
    """

    def __init__(self, fs, n_cha, tones=None, pink_method="real-time"):
        self.fs = fs
        self.n_cha = n_cha
        self.tones = tones
        self.pink_method = pink_method
        if tones is None:
            self.tones = list()
            self.tones.append((10, 11))
            self.tones.append((20, 7))
            self.tones.append((50, 12))
            self.tones.append((100, 7))
        if self.pink_method != "offline":
            self.pink_method = "real-time"

        # If method is offline, then generate a big stream of pink noise
        self.pink_noise = None
        self.pink_noise_sample = 0
        if self.pink_method == "offline":
            NO_SECS = 20
            noise_ = self.generate_offline_pink(NO_SECS * self.fs * self.n_cha)
            self.pink_noise = noise_.reshape(int(NO_SECS * self.fs),
                                             int(self.n_cha))

        # Generated
        self.current_time = 0

    def get_chunk(self, chunk_size):
        """ Function to get a new chunk. The method adds pink noise and
        overlayed tones.

        Parameters
        ------------
        chunk_size : int
            Chunk size in samples.

        Returns
        ------------
        ndarray: [samples x channels]
            Generated chunk.
        """
        # Get the time series
        times = [self.current_time + i * (1 / self.fs) for i in
                 range(chunk_size)]
        times = np.array(times)
        self.current_time = self.current_time + chunk_size / self.fs

        # Get the pink noise (1/f)
        if self.pink_method == "offline":
            if chunk_size > self.pink_noise.shape[0]:
                raise ValueError("The chunk size (%i) is greater than the "
                                 "offline generated pink noise length (%i)! "
                                 "Increment manually the NO_SECS variable" %
                                 (chunk_size, self.pink_noise.shape[0]))
            if self.pink_noise_sample + chunk_size > self.pink_noise.shape[0]:
                self.pink_noise_sample = 0
            chunk = self.pink_noise[self.pink_noise_sample:
                                    self.pink_noise_sample + chunk_size, :].copy()
            self.pink_noise_sample += chunk_size
        else:
            # Real-time generation using Voss-McCartney algorithm
            noise = self.generate_online_pink(int(chunk_size * self.n_cha))
            chunk = noise.reshape(chunk_size, self.n_cha)

        # Add each tone
        for tone in self.tones:
            eeg_tone = tone[1] * np.sin(2 * np.pi * times * tone[0])
            chunk += np.tile(eeg_tone.reshape(chunk_size, 1), self.n_cha)

        return chunk

    def get_chunks(self, n_chunks, chunk_size):
        """ Function to generate several chunks at once.

        Parameters
        ------------
        n_chunks : int
            Number of chunks to generate
        chunk_size : int
            Chunk size in samples.

        Returns
        ------------
        ndarray: [n_chunks x samples x channels]
            Generated chunks.
        """
        data = np.empty((n_chunks, chunk_size, self.n_cha))
        for i in range(n_chunks):
            data[i, :, :] = self.get_chunk(chunk_size)
        return data

    @staticmethod
    def generate_offline_pink(no_samples, exponent=0.51, amplitude=30):
        """ Function to generate an offline stream of pink noise. Based on
        the EEG simulator of https://github.com/pennmem/eegsim. It generates
        a desired shape in the frequency domain and performs a IFFT to get
        the temporal counterpart. Not suitable for a small number of samples.

        Parameters
        -------------
        no_samples : int
            Number of samples to generate
        exponent : float
            Exponent to normalize the scales.
        amplitude : int
            Amplitude to normalize the pink noise.

        Returns
        ----------
        ndarray: (samples, )
            Generated pink noise signal.
        """
        out_n = int(no_samples)
        n = int(no_samples) + 1 if int(no_samples) & 1 == 1 else int(no_samples)
        scales = np.linspace(0, 0.5, n // 2 + 1)[1:]
        scales = scales ** (-exponent / 2)
        pink_freq = np.random.normal(scale=scales) * \
                    np.exp(2j * np.pi * np.random.random(n // 2))
        fdata = np.concatenate([[0], pink_freq])
        sigma = np.sqrt(2 * np.sum(scales ** 2)) / n
        data = amplitude * np.real(np.fft.irfft(fdata)) / sigma
        return data[:out_n]

    @staticmethod
    def generate_online_pink(nrows, ncols=16, amp=18):
        """ Generates pink noise using the Voss-McCartney algorithm.
        Extracted from https://www.dsprelated.com/showarticle/908.php. This
        method computes the pink noise directly on the temporal domain,
        so it is suitable for a real-time generation of a small number of
        samples. (v2.4: the forward fill is done with numpy, v2.3 used pandas,
        whose fillna(method=...) is deprecated; the result is the same.)

        Parameters
        -----------
        nrows: int
            Number of samples
        ncols: int
            Number of random sources to add
        amp: int
            Amplitude to normalize the pink noise.

        Returns
        -------------
        ndarray: (samples, )
            Generated pink noise signal.
        """
        array = np.empty((nrows, ncols))
        array.fill(np.nan)
        array[0, :] = np.random.random(ncols)
        array[:, 0] = np.random.random(nrows)

        # the total number of changes is nrows
        n = nrows
        cols = np.random.geometric(0.5, n)
        cols[cols >= ncols] = 0
        rows = np.random.randint(nrows, size=n)
        array[rows, cols] = np.random.random(n)

        # Forward fill along the rows (the first row has no NaN)
        valid = ~np.isnan(array)
        last_valid = np.where(valid, np.arange(nrows)[:, None], 0)
        np.maximum.accumulate(last_valid, axis=0, out=last_valid)
        filled = array[last_valid, np.arange(ncols)[None, :]]
        total = filled.sum(axis=1)

        return amp * total
