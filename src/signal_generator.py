"""
Author:   Eduardo Santamaría-Vázquez
Date:     09 June 2021
Version:  0.1
"""

from pylsl import StreamInfo, StreamOutlet, local_clock
import time, threading
import numpy as np


class SignalGenerator:

    def __init__(self, stream_name, stream_type, chunk_size, format, n_cha,
                 l_cha, units, mean, std, sample_rate):

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
        self.mean = mean
        self.std = std
        self.sample_rate = sample_rate

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
                    sample = self.std * np.random.randn(
                        self.chunk_size, self.n_cha) + self.mean
                    sample = sample.tolist()
                    # Get a time stamp in seconds
                    stamp = local_clock()
                    # Now send it
                    self.lsl_outlet.push_chunk(sample, stamp)
                    # Wait
                    time.sleep(self.chunk_size / self.sample_rate)
            except Exception as e:
                raise e
        print('[SignalGenerator] > IO thread done.')

