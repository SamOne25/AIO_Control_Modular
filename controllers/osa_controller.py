"""
osa_controller.py

Manages the Optical Spectrum Analyzer (OSA) via SCPI over VISA.
"""

import pyvisa
import numpy as np


class OSASpectrum:
    """
    Holds a single OSA sweep result.
    """
    def __init__(self, wavelengths: np.ndarray, powers_dbm: np.ndarray, params: dict):
        self.wavelengths = wavelengths   # in nanometers
        self.powers_dbm = powers_dbm     # in dBm
        self.params = params             # Dict of OSA settings at sweep time


class OSAController:
    """
    Controller for an optical spectrum analyzer (e.g., Anritsu MS9740A).
    """

    def __init__(self, address: str):
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(address)
        self.inst.write(":SWE:TIME:AUTO ON")    # Auto sweep time
        self.inst.write(":UNIT:POW DBM")        # Power unit
        self.inst.write(":SENS:WAV:RANG:MODE MAN")  # Manual wavelength range

    def configure_sweep(self, start_nm: float, stop_nm: float, resolution_nm: float) -> None:
        """
        Set sweep parameters: start/stop wavelength and resolution.
        """
        self.inst.write(f":SENS:WAV:START {start_nm}NM")
        self.inst.write(f":SENS:WAV:STOP {stop_nm}NM")
        self.inst.write(f":SENS:WAV:RES {resolution_nm}NM")

    def measure_spectrum(self) -> OSASpectrum:
        """
        Trigger a sweep and read back the wavelength vs. power data.
        """
        # Trigger sweep
        self.inst.write(":INIT:IMM")
        self.inst.query("*OPC?")  # wait until done

        # Read trace as ASCII for simplicity
        raw = self.inst.query_ascii_values("TRAC:DATA? TRACE1", separator=",")
        powers = np.array(raw)

        # Query axis data
        start = float(self.inst.query(":SENS:WAV:START?"))
        stop = float(self.inst.query(":SENS:WAV:STOP?"))
        points = powers.size
        wavelengths = np.linspace(start, stop, points)

        params = {
            "start_nm": start,
            "stop_nm": stop,
            "resolution_nm": float(self.inst.query(":SENS:WAV:RES?")),
            "unit": self.inst.query(":UNIT:POW?").strip(),
        }

        return OSASpectrum(wavelengths, powers, params)

    def close(self) -> None:
        """
        Close the VISA session.
        """
        self.inst.close()
        self.rm.close()
