import matplotlib.pyplot as plt
import scipy.signal as scisig
import pandas as pd
import numpy as np


class EEGGenerator:

    def __init__(self, fs, n_cha, tones=None, pink_method="offline"):
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
            self.pink_noise = noise_.reshape(NO_SECS * self.fs, self.n_cha)

        # Generated
        self.current_time = 0

    def get_chunk(self, chunk_size):
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

        return times, chunk

    @staticmethod
    def generate_offline_pink(no_samples, exponent=0.51, amplitude=30):
        out_n = no_samples
        n = no_samples + 1 if no_samples & 1 == 1 else no_samples
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
        """Generates pink noise using the Voss-McCartney algorithm.

        nrows: number of values to generate
        rcols: number of random sources to add

        returns: NumPy array
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


if __name__ == '__main__':
    import time

    gen = EEGGenerator(250, 1, pink_method="real-time")

    times = None
    eeg = None
    for i in range(100):
        t, chunk = gen.get_chunk(16)
        if times is None:
            times = t
            eeg = chunk
        else:
            times = np.concatenate((times, t))
            eeg = np.concatenate((eeg, chunk))
        time.sleep(16/250)
    print("")

    fig = plt.figure()
    ax = fig.add_subplot(2,1,1)
    ax.plot(times, eeg)

    f, psd = scisig.welch(eeg, fs=250, nperseg=250,
                 noverlap=250//2,
                 nfft=250, axis=0)

    ax = fig.add_subplot(2,1,2)
    ax.plot(f, psd)
    plt.show()


