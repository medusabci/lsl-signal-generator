"""
Author:   Víctor Martínez-Cagigal & Eduardo Santamaría-Vázquez
Date:     11 April 2023
Version:  2.0
"""

from pylsl import StreamInfo, StreamOutlet, local_clock
import time
import threading
import numpy as np
import pandas as pd


class SignalGenerator:

    def __init__(self, stream_name, stream_type, chunk_size, format, n_cha,
                 l_cha, units, sample_rate, gen_settings):

        # Error check
        if len(l_cha) != n_cha:
            raise ValueError('The number of channel labels does not match with '
                             'the number of channels')

        # Parameters
        self.stream_name = stream_name
        self.stream_type = stream_type
        self.chunk_size = chunk_size
        self.format = format
        self.n_cha = n_cha
        self.l_cha = l_cha
        self.units = units
        self.sample_rate = sample_rate
        self.gen_settings = gen_settings

        # Initialize the generator
        if self.gen_settings["gen_type"] == "EEG (closed eyes)":
            tones = list()
            tones.append((10, 11))
            tones.append((20, 7))
            if self.gen_settings["eeg_ac"]:
                tones.append((50, 12))
                tones.append((100, 7))
            self.generator = EEGGenerator(
                fs=self.sample_rate, n_cha=self.n_cha, tones=tones,
                pink_method=self.gen_settings["eeg_pink"])
        elif self.gen_settings["gen_type"] == "EEG (open eyes)":
            tones = list()
            if self.gen_settings["eeg_ac"]:
                tones.append((50, 12))
                tones.append((100, 7))
            self.generator = EEGGenerator(
                fs=self.sample_rate, n_cha=self.n_cha, tones=tones,
                pink_method=self.gen_settings["eeg_pink"])
        elif self.gen_settings["gen_type"] == "Uniform":
            self.generator = UniformGenerator(
                n_cha=self.n_cha, mean=gen_settings["uniform_mean"],
                std=gen_settings["uniform_std"])
        else:
            raise ValueError("Unknown generator value: %s!" % self.generator)

        # Event for stopping the IO thread
        self.io_run = threading.Event()
        self.io_run.set()

        # LSL
        self.lsl_outlet = None
        self.lsl_buffer = []
        self.lsl_thread = None

        # Run IO function in other thread
        self.io_init_timestamp = None
        self.io_thread = threading.Thread(
            name='SignalGenerator_Data_Thread',
            target=self.send_data,
            args=[self.io_run]
        )
        self.io_thread.start()

    def close(self):
        self.io_run.clear()
        self.io_thread.join()

    def init_send_lsl(self):
        # Create the steam outlet
        source_id = '_'.join([self.stream_name, self.stream_type,
                              str(self.n_cha), str(self.sample_rate),
                              self.format])
        lsl_info = StreamInfo(name=self.stream_name,
                              type=self.stream_type,
                              channel_count=self.n_cha,
                              nominal_srate=self.sample_rate,
                              channel_format=self.format,
                              source_id=source_id)
        # lsl_info.desc().append_child_value("manufacturer", "")
        channels = lsl_info.desc().append_child("channels")
        for l in self.l_cha:
            channels.append_child("channel") \
                .append_child_value("label", l) \
                .append_child_value("units", self.units) \
                .append_child_value("type", self.stream_type)

        self.lsl_outlet = StreamOutlet(info=lsl_info,
                                       chunk_size=self.chunk_size,
                                       max_buffered=360)
        print('[SignalGenerator] > LSL stream created.')

    def close_lsl(self):
        self.lsl_outlet = None
        self.lsl_buffer = []
        print('[SignalGenerator] > LSL stream closed.')

    # In Thread
    def send_data(self, running_event):
        while running_event.is_set():
            # Assert that the parse to float is correct
            try:
                if self.lsl_outlet is not None:
                    tic = time.time()
                    sample = self.generator.get_chunk(self.chunk_size).tolist()
                    # Get a time stamp in seconds
                    stamp = local_clock()
                    # Now send it
                    self.lsl_outlet.push_chunk(sample, stamp)
                    # Wait
                    time.sleep(
                        (self.chunk_size / self.sample_rate) -
                        (time.time() - tic)
                    )
            except Exception as e:
                raise e
        print('[SignalGenerator] > IO thread done.')


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
        times = [self.current_time + i*(1/self.fs) for i in range(chunk_size)]
        times = np.array(times)
        self.current_time = self.current_time + chunk_size/self.fs

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
                                    self.pink_noise_sample + chunk_size, :]
            self.pink_noise_sample += chunk_size
        else:
            # Real-time generation using Voss-McCartney algorithm
            noise = self.generate_online_pink(chunk_size * self.n_cha)
            chunk = noise.reshape(chunk_size, self.n_cha)

        # Add each tone
        for tone in self.tones:
            eeg_tone = tone[1] * np.sin(2 * np.pi * times * tone[0])
            chunk += np.tile(eeg_tone.reshape(chunk_size, 1), self.n_cha)

        return chunk

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
        pink_freq = np.random.normal(scale=scales) *\
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
        samples.

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

        df = pd.DataFrame(array)
        df.fillna(method='ffill', axis=0, inplace=True)
        total = df.sum(axis=1)

        return amp * total.values
