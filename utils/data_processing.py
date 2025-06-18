import numpy as np

def normalize_data(data):
    """Normiert ein 1D-Array auf den Bereich 0...1."""
    data = np.array(data)
    min_val = np.min(data)
    max_val = np.max(data)
    if max_val > min_val:
        return (data - min_val) / (max_val - min_val)
    else:
        return data * 0  # alles auf Null, falls keine Variation

def scale_to_unit(data, unit="V"):
    """Skaliert Werte in eine andere Einheit (z. B. mV, µV, ...)."""
    factor = 1.0
    if unit == "mV":
        factor = 1e3
    elif unit == "uV":
        factor = 1e6
    return np.array(data) * factor

def smooth(data, window_size=5):
    """Gleitet Mittelwert (Moving Average) über die Daten."""
    data = np.array(data)
    if len(data) < window_size:
        return data
    return np.convolve(data, np.ones(window_size)/window_size, mode='valid')
