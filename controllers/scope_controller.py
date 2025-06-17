"""
scope_controller.py

Provides a clean interface for communicating with the oscilloscope via SCPI over VISA.
"""

import pyvisa
import numpy as np


class ScopeMeasurement:
    """
    Data structure to hold a single waveform capture.
    """
    def __init__(self, time_axis: np.ndarray, voltages: np.ndarray, params: dict):
        self.time = time_axis         # 1D array of time points (seconds)
        self.voltage = voltages       # 1D array of measured voltages (volts)
        self.params = params          # Dict of scope settings at capture time


class ScopeController:
    """
    Controller for a Tektronix (or similar) oscilloscope.
    """

    def __init__(self, address: str):
        """
        Open VISA session and initialize the instrument.
        """
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(address)
        self.inst.write(":HEADER OFF")               # Turn off headers
        self.inst.write("DATA:ENC RIBinary")         # 16-bit signed, big-endian
        self.inst.write("DATA:WIDTH 2")              # 2 bytes per sample
        self.inst.write("DATA:START 1")              # Start of waveform
        self.inst.write("DATA:STOP 2500")            # Default record length

    def get_settings(self) -> dict:
        """
        Query key settings from the scope (e.g. timebase, vertical scale, trigger).
        Returns a dict of parameter name → value.
        """
        settings = {}
        settings['timebase_s_per_div'] = float(self.inst.query("HOR:MAIN:SCALE?"))
        settings['record_length']      = int(self.inst.query("DATA:STOP?"))
        settings['volts_per_div']      = float(self.inst.query("CH1:SCAL?"))
        settings['trigger_source']     = self.inst.query("TRIG:A:EDGE:SOUR?").strip()
        settings['trigger_level']      = float(self.inst.query("TRIG:A:LEVel?"))
        return settings

    def read_waveform(self, channel: int = 1) -> ScopeMeasurement:
        """
        Fetch waveform data from the specified channel.
        Returns a ScopeMeasurement dataclass instance.
        """
        # Select channel
        self.inst.write(f"DATA:SOURCE CH{channel}")

        # Query record length to set stop point
        stop = int(self.inst.query("DATA:STOP?"))
        self.inst.write(f"DATA:STOP {stop}")

        # Read raw binary data
        raw = self.inst.query_binary_values("CURVE?", datatype='h', container=np.array)

        # Build time axis
        tb_s = float(self.inst.query("HOR:MAIN:SCALE?"))
        points = raw.size
        # Tektronix uses 10 divisions on screen
        total_time = tb_s * 10
        time_axis = np.linspace(0, total_time, points)

        # Package parameters
        params = self.get_settings()
        params['channel'] = channel

        return ScopeMeasurement(time_axis, raw, params)

    def set_trigger(self, source_channel: int, level_volts: float) -> None:
        """
        Configure the trigger on the given channel and level.
        """
        self.inst.write(f"TRIG:A:EDGE:SOUR CH{source_channel}")
        self.inst.write(f"TRIG:A:LEVel {level_volts}")

    def close(self) -> None:
        """
        Close VISA session.
        """
        self.inst.close()
        self.rm.close()
