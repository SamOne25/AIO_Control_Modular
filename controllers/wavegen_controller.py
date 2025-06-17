"""
wavegen_controller.py

Controls a function/waveform generator via SCPI over VISA.
"""

import pyvisa


class WavegenSettings:
    """
    Data structure for current waveform generator settings.
    """
    def __init__(self, frequency: float, amplitude: float, output_enabled: bool):
        self.frequency = frequency          # in Hz
        self.amplitude = amplitude          # in Volts peak-to-peak
        self.output_enabled = output_enabled


class WavegenController:
    """
    Controller for a Keysight (or similar) waveform generator.
    """

    def __init__(self, address: str):
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(address)
        self.inst.write("OUTP:STAT OFF")    # Ensure output off at init

    def set_frequency(self, freq_hz: float) -> None:
        """
        Set the output frequency in Hz.
        """
        self.inst.write(f"FREQ {freq_hz}")

    def set_amplitude(self, amplitude_vpp: float) -> None:
        """
        Set the output amplitude in Vpp.
        """
        self.inst.write(f"VOLT {amplitude_vpp}")

    def enable_output(self, enable: bool = True) -> None:
        """
        Turn the generator output on or off.
        """
        state = "ON" if enable else "OFF"
        self.inst.write(f"OUTP:STAT {state}")

    def get_settings(self) -> WavegenSettings:
        """
        Query current settings and return a WavegenSettings object.
        """
        freq = float(self.inst.query("FREQ?"))
        amp = float(self.inst.query("VOLT?"))
        stat = self.inst.query("OUTP:STAT?").strip() == "1"
        return WavegenSettings(freq, amp, stat)

    def close(self) -> None:
        """
        Close the VISA session.
        """
        self.inst.close()
        self.rm.close()
