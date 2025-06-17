# utils/data_processing.py

"""
data_processing.py

Signal- and spectrum-processing functions for post-capture analysis.
"""

import numpy as np


def find_peaks(signal: np.ndarray, threshold: float) -> np.ndarray:
    """
    Simple local-maximum peak finder.
    Returns indices where signal[i] > signal[i-1] and signal[i] > signal[i+1]
    and signal[i] >= threshold.
    """
    peaks = []
    for i in range(1, len(signal) - 1):
        if signal[i] > signal[i - 1] and signal[i] > signal[i + 1] and signal[i] >= threshold:
            peaks.append(i)
    return np.array(peaks, dtype=int)


def smooth_signal(signal: np.ndarray, window_size: int = 5) -> np.ndarray:
    """
    Moving-average smoothing.
    """
    if window_size < 1:
        return signal
    kernel = np.ones(window_size) / window_size
    return np.convolve(signal, kernel, mode="same")


def normalize(signal: np.ndarray) -> np.ndarray:
    """
    Normalize an array to the range [0, 1].
    """
    min_val = np.min(signal)
    max_val = np.max(signal)
    if max_val == min_val:
        return np.zeros_like(signal)
    return (signal - min_val) / (max_val - min_val)


def dbm_to_mw(p_dbm: np.ndarray) -> np.ndarray:
    """
    Convert power values from dBm to mW.
    """
    return 10 ** (p_dbm / 10.0)
