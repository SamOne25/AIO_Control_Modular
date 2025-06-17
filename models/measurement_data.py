"""
measurement_data.py

Defines the MeasurementData model to accumulate and export
measurements from scope, wavegen, and OSA.
"""

import numpy as np


class MeasurementData:
    """
    Container for a full frequency sweep experiment.
    """

    def __init__(self):
        # Lists to hold per-frequency records
        self.frequencies = []        # float, Hz
        self.scope_records = []      # ScopeMeasurement instances
        self.osa_records = []        # OSASpectrum instances
        self.wavegen_settings = []   # WavegenSettings instances

    def add_record(self, freq_hz: float, scope_rec, osa_rec, wavegen_set):
        """
        Append one set of measurements at a given frequency.
        """
        self.frequencies.append(freq_hz)
        self.scope_records.append(scope_rec)
        self.osa_records.append(osa_rec)
        self.wavegen_settings.append(wavegen_set)

    def as_numpy(self):
        """
        Convert stored data to a structured NumPy array for export or analysis.
        Returns an array of tuples:
          (frequency, time_axis, voltage_data, wavelengths, power_data)
        """
        dtype = [
            ("frequency", "f8"),
            ("time", "O"),       # object array for variable-length
            ("voltage", "O"),
            ("wavelengths", "O"),
            ("powers_dbm", "O"),
        ]

        structured = []
        for f, s, o in zip(self.frequencies, self.scope_records, self.osa_records):
            structured.append((
                f,
                s.time,
                s.voltage,
                o.wavelengths,
                o.powers_dbm
            ))

        return np.array(structured, dtype=dtype)
