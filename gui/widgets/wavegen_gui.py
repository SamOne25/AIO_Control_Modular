# gui/widgets/wavegen_gui.py

"""
wavegen_gui.py

Tkinter GUI widget for waveform generator controls.
"""

import tkinter as tk
from tkinter import ttk

class WavegenGUI(tk.LabelFrame):
    """
    Frame containing controls for the waveform generator.
    """

    def __init__(self, master, wavegen_ctrl, *args, **kwargs):
        super().__init__(master, text="Waveform Generator", *args, **kwargs)
        self.ctrl = wavegen_ctrl
        self._build_widgets()

    def _build_widgets(self):
        # Frequency
        tk.Label(self, text="Frequency (Hz):").grid(row=0, column=0, sticky="e")
        self.freq_var = tk.DoubleVar(value=self.ctrl.get_settings().frequency)
        ttk.Entry(self, textvariable=self.freq_var, width=12).grid(row=0, column=1, sticky="w")
        ttk.Button(self, text="Set Freq", command=self._set_frequency).grid(row=0, column=2, padx=5)

        # Amplitude
        tk.Label(self, text="Amplitude (Vpp):").grid(row=1, column=0, sticky="e")
        self.amp_var = tk.DoubleVar(value=self.ctrl.get_settings().amplitude)
        ttk.Entry(self, textvariable=self.amp_var, width=12).grid(row=1, column=1, sticky="w")
        ttk.Button(self, text="Set Amp", command=self._set_amplitude).grid(row=1, column=2, padx=5)

        # Output on/off
        self.output_btn = ttk.Button(self, text="Output ON" if not self.ctrl.get_settings().output_enabled else "Output OFF",
                                     command=self._toggle_output)
        self.output_btn.grid(row=2, column=0, columnspan=3, pady=5)

    def _set_frequency(self):
        freq = self.freq_var.get()
        self.ctrl.set_frequency(freq)

    def _set_amplitude(self):
        amp = self.amp_var.get()
        self.ctrl.set_amplitude(amp)

    def _toggle_output(self):
        current = self.ctrl.get_settings().output_enabled
        self.ctrl.enable_output(not current)
        # Update button text
        self.output_btn.config(text="Output OFF" if not current else "Output ON")
