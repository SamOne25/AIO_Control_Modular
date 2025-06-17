# gui/widgets/osa_gui.py

"""
osa_gui.py

Tkinter GUI widget for OSA controls and spectrum plotting.
"""

import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class OSAGUI(tk.LabelFrame):
    """
    Frame containing controls and plot for the OSA.
    """

    def __init__(self, master, osa_ctrl, *args, **kwargs):
        super().__init__(master, text="Optical Spectrum Analyzer", *args, **kwargs)
        self.ctrl = osa_ctrl
        self._build_widgets()
        self._build_plot()

    def _build_widgets(self):
        # Sweep start
        tk.Label(self, text="Start λ (nm):").grid(row=0, column=0, sticky="e")
        self.start_var = tk.DoubleVar(value=1550.0)
        ttk.Entry(self, textvariable=self.start_var, width=10).grid(row=0, column=1, sticky="w")

        # Sweep stop
        tk.Label(self, text="Stop λ (nm):").grid(row=0, column=2, sticky="e")
        self.stop_var = tk.DoubleVar(value=1560.0)
        ttk.Entry(self, textvariable=self.stop_var, width=10).grid(row=0, column=3, sticky="w")

        # Resolution
        tk.Label(self, text="Res (nm):").grid(row=1, column=0, sticky="e")
        self.res_var = tk.DoubleVar(value=0.1)
        ttk.Entry(self, textvariable=self.res_var, width=10).grid(row=1, column=1, sticky="w")

        # Sweep button
        ttk.Button(self, text="Sweep", command=self._do_sweep).grid(row=1, column=3, padx=5, pady=5)

    def _build_plot(self):
        self.fig, self.ax = plt.subplots(figsize=(5, 2.5))
        self.ax.set_title("OSA Spectrum")
        self.ax.set_xlabel("Wavelength (nm)")
        self.ax.set_ylabel("Power (dBm)")
        self.line, = self.ax.plot([], [], lw=1)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().grid(row=2, column=0, columnspan=4, pady=5)

    def _do_sweep(self):
        # configure and trigger
        self.ctrl.configure_sweep(self.start_var.get(), self.stop_var.get(), self.res_var.get())
        spec = self.ctrl.measure_spectrum()
        self._update_plot(spec.wavelengths, spec.powers_dbm)

    def _update_plot(self, wavelengths, powers_dbm):
        self.line.set_data(wavelengths, powers_dbm)
        self.ax.set_xlim(wavelengths.min(), wavelengths.max())
        self.ax.set_ylim(min(powers_dbm), max(powers_dbm))
        self.canvas.draw_idle()
