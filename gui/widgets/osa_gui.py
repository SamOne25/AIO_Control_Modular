import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from controllers.osa_controller import OSAController
from utils.helpers import (
    CreateToolTip, integration_string_to_hz, SMT_OPTIONS
)

class OSAGUI(ttk.Frame):
    def __init__(self, parent, controller=None):
        super().__init__(parent)
        self.controller = controller if controller else OSAController()
        self.osa_ip = tk.StringVar(value="192.168.1.112")
        self.status_var = tk.StringVar(value="Status: Not connected")
        self.error_var = tk.StringVar(value="")
        self.connection_state = tk.StringVar(value="disconnected")

        self.resolutions = ["1.0", "0.5", "0.2", "0.1", "0.07", "0.05", "0.03"]
        self.integrations = ["1MHz", "100kHz", "10kHz", "1kHz", "100Hz", "10Hz"]
        self.samp_points = [
            "51", "101", "201", "251", "501", "1001",
            "2001", "5001", "10001", "20001", "50001"
        ]
        self.spans = ["1200", "1000", "500", "200", "100", "50", "20", "10", "5", "2", "1"]

        self.resolution = tk.StringVar(value="0.1")
        self.integration = tk.StringVar(value="1kHz")
        self.points = tk.StringVar(value="501")
        self.central_wl = tk.DoubleVar(value=1548.5)
        self.span = tk.StringVar(value="2")
        self.smooth_points = tk.StringVar(value="OFF")
        self.reference_lvl = tk.DoubleVar(value=0.0)
        self.level_offset = tk.DoubleVar(value=0.0)

        self.sweep_running = False
        self.repeat_running = False
        self.abort_flag = threading.Event()
        self.polling_thread = None

        self.fig_dbm, self.ax_dbm = plt.subplots(figsize=(6, 4), dpi=150)
        self.fig_lin, self.ax_lin = plt.subplots(figsize=(6, 4), dpi=150)
        self.last_wavelengths = None
        self.last_power_dbm = None
        self.last_power_lin = None

        self.build_gui()
        self.update_conn_btn()

    def build_gui(self):
        main = tk.Frame(self)
        main.pack(fill="both", expand=True, padx=12, pady=8)
        top = tk.Frame(main)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        tk.Label(top, text="OSA IP:").grid(row=0, column=0, sticky="e")
        ip_entry = tk.Entry(top, textvariable=self.osa_ip, width=16)
        ip_entry.grid(row=0, column=1, sticky="w")
        ip_entry.bind("<Return>", lambda _=None: self.toggle_connection())
        self.connect_btn = tk.Button(
            top, text="Connect", width=12, command=self.toggle_connection
        )
        self.connect_btn.grid(row=0, column=2, padx=(10, 0))

        # Parameter
        param = tk.LabelFrame(main, text="Sweep Parameters", padx=8, pady=10)
        param.grid(row=1, column=0, sticky="nsew", pady=6)
        for c in range(4): param.columnconfigure(c, weight=1)
        row = 0
        tk.Label(param, text="Central WL [nm]:").grid(row=row, column=0, sticky="e")
        cw_entry = tk.Entry(param, textvariable=self.central_wl, width=10)
        cw_entry.grid(row=row, column=1, sticky="w")
        CreateToolTip(cw_entry, "Valid 800 – 1700 nm")
        cw_entry.bind("<Return>", lambda _e: self.set_single_param("CNT", self.central_wl.get()))
        cw_entry.bind("<FocusOut>", lambda _e: self.set_single_param("CNT", self.central_wl.get()))
        row += 1
        tk.Label(param, text="Span [nm]:").grid(row=row, column=0, sticky="e")
        span_cb = ttk.Combobox(param, values=self.spans, textvariable=self.span,
                               width=8, state="readonly")
        span_cb.grid(row=row, column=1, sticky="w")
        span_cb.bind("<<ComboboxSelected>>", lambda _e: self.set_single_param("SPN", self.span.get()))
        row += 1
        tk.Label(param, text="Resolution [nm]:").grid(row=row, column=0, sticky="e")
        res_cb = ttk.Combobox(param, values=self.resolutions, textvariable=self.resolution,
                              width=8, state="readonly")
        res_cb.grid(row=row, column=1, sticky="w")
        res_cb.bind("<<ComboboxSelected>>", lambda _e: self.set_single_param("RES", self.resolution.get()))
        row += 1
        tk.Label(param, text="Integration:").grid(row=row, column=0, sticky="e")
        integ_cb = ttk.Combobox(param, values=self.integrations, textvariable=self.integration,
                                width=8, state="readonly")
        integ_cb.grid(row=row, column=1, sticky="w")
        integ_cb.bind("<<ComboboxSelected>>", lambda _e: self.set_single_param("VBW", self.integration.get()))
        row += 1
        tk.Label(param, text="Sampling Points:").grid(row=row, column=0, sticky="e")
        pts_cb = ttk.Combobox(param, values=self.samp_points, textvariable=self.points,
                              width=8, state="readonly")
        pts_cb.grid(row=row, column=1, sticky="w")
        pts_cb.bind("<<ComboboxSelected>>", lambda _e: self.set_single_param("MPT", self.points.get()))
        row += 1
        tk.Label(param, text="Reference LvL [dBm]:").grid(row=row, column=0, sticky="e")
        rlv_spin = tk.Spinbox(param, from_=-90.0, to=30.0, increment=1.0,
                              textvariable=self.reference_lvl, width=8, format="%.1f",
                              command=lambda: self.set_single_param("RLV", self.reference_lvl.get()))
        rlv_spin.grid(row=row, column=1, sticky="w")
        rlv_spin.bind("<FocusOut>", lambda _e: self.set_single_param("RLV", self.reference_lvl.get()))
        row += 1
        tk.Label(param, text="Level Offset [dB]:").grid(row=row, column=0, sticky="e")
        lof_spin = tk.Spinbox(param, from_=-30.0, to=30.0, increment=1.0,
                              textvariable=self.level_offset, width=8, format="%.1f",
                              command=lambda: self.set_single_param("LOFS", self.level_offset.get()))
        lof_spin.grid(row=row, column=1, sticky="w")
        lof_spin.bind("<FocusOut>", lambda _e: self.set_single_param("LOFS", self.level_offset.get()))
        row += 1
        tk.Label(param, text="Smooth:").grid(row=row, column=0, sticky="e")
        smooth_cb = ttk.Combobox(param, values=SMT_OPTIONS, textvariable=self.smooth_points,
                                 width=6, state="readonly")
        smooth_cb.grid(row=row, column=1, sticky="w")
        smooth_cb.bind("<<ComboboxSelected>>", lambda _e: self.set_single_param("SMT", self.smooth_points.get()))
        row += 1
        quality = tk.LabelFrame(param, text="Quality", padx=4, pady=4)
        quality.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        ttk.Button(quality, text="Low", command=lambda: self.apply_quality("low")).grid(row=0, column=0, sticky="ew", padx=4, pady=2)
        ttk.Button(quality, text="Med", command=lambda: self.apply_quality("med")).grid(row=1, column=0, sticky="ew", padx=4, pady=2)
        ttk.Button(quality, text="High", command=lambda: self.apply_quality("high")).grid(row=2, column=0, sticky="ew", padx=4, pady=2)
        row += 1

        button_frame = tk.Frame(param)
        button_frame.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(5,2))
        self.single_btn = ttk.Button(button_frame, text="Single Sweep", width=16, command=self.start_single_sweep)
        self.single_btn.pack(side="left", padx=(0,6))
        self.repeat_btn = ttk.Button(button_frame, text="Repeat Sweep", width=16, command=self.start_repeat_sweep)
        self.repeat_btn.pack(side="left", padx=(6,0))
        row += 1

        # Progressbar
        self.progressbar = ttk.Progressbar(param, mode="determinate", maximum=100)
        self.progressbar.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        row += 1

        tk.Label(param, textvariable=self.status_var, fg="blue").grid(row=row, column=0, columnspan=4)
        row += 1
        tk.Label(param, textvariable=self.error_var, fg="red").grid(row=row, column=0, columnspan=4)

        plots = tk.Frame(main)
        plots.grid(row=1, column=1, rowspan=2, sticky="nsew", padx=10)
        plots.columnconfigure(0, weight=1)
        plots.rowconfigure(1, weight=1)

        self.plot_tabs = ttk.Notebook(plots)
        self.plot_tabs.grid(row=1, column=0, sticky="nsew", pady=6)

        self.dbm_tab = ttk.Frame(self.plot_tabs)
        self.plot_tabs.add(self.dbm_tab, text="dBm Scale")
        self.canvas_dbm = FigureCanvasTkAgg(self.fig_dbm, self.dbm_tab)
        self.canvas_dbm.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)

        self.lin_tab = ttk.Frame(self.plot_tabs)
        self.plot_tabs.add(self.lin_tab, text="Linear Scale")
        self.canvas_lin = FigureCanvasTkAgg(self.fig_lin, self.lin_tab)
        self.canvas_lin.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)

    def update_conn_btn(self):
        if self.connection_state.get() == "connected":
            self.connect_btn.config(text="Disconnect", bg="green", fg="white")
        else:
            self.connect_btn.config(text="Connect", bg="red", fg="white")

    def toggle_connection(self):
        if self.connection_state.get() == "disconnected":
            self.connect_osa()
        else:
            self.disconnect_osa()
        self.update_conn_btn()

    def connect_osa(self):
        try:
            import pyvisa
            if self.controller.rm is None:
                self.controller.rm = pyvisa.ResourceManager()
            self.controller.osa = self.controller.rm.open_resource(f"TCPIP0::{self.osa_ip.get()}::INSTR")
            self.controller.osa.timeout = 300_000
            idn = self.controller.osa.query("*IDN?")
            self.controller.osa.write("LOG 5")  # Set dBm mode once
            self.status_var.set(f"Connected: {idn.strip()}")
            self.connection_state.set("connected")
            self.read_all_params()  # NEU: Parameter lesen
        except Exception as exc:
            messagebox.showerror("OSA Error", f"Connection failed: {exc}")
            self.connection_state.set("disconnected")
            self.controller.osa = None

    def disconnect_osa(self):
        self.abort_flag.set()
        try:
            if self.controller.osa:
                self.controller.osa.write("SST")
                self.controller.osa.close()
        except Exception:
            pass
        self.controller.osa = None
        self.connection_state.set("disconnected")
        self.status_var.set("Status: Not connected")

    def read_all_params(self):
        try:
            osa = self.controller.osa
            if osa is None:
                return
            cwl = float(osa.query("CNT?").strip())
            self.central_wl.set(cwl)
            span = float(osa.query("SPN?").strip())
            self.span.set(str(int(span)))
            res = float(osa.query("RES?").strip())
            self.resolution.set(str(res))
            vbw = osa.query("VBW?").strip()
            self.integration.set(vbw)
            mpt = int(osa.query("MPT?").strip())
            self.points.set(str(mpt))
            try:
                rlv = float(osa.query("RLV?").strip())
                self.reference_lvl.set(rlv)
            except Exception:
                pass
            try:
                lof = float(osa.query("LOFS?").strip())
                self.level_offset.set(lof)
            except Exception:
                pass
            self.status_var.set("Parameters loaded.")
        except Exception as exc:
            self.error_var.set(f"Read failed: {exc}")

    def set_single_param(self, cmd, value):
        if self.connection_state.get() != "connected":
            return
        try:
            osa = self.controller.osa
            if cmd == "VBW":
                hz = integration_string_to_hz(value)
                osa.write(f"{cmd} {hz}")
                actual = osa.query("VBW?").strip()
                # Try to cast to int for comparison if possible
                try:
                    if int(float(actual)) != int(float(hz)):
                        self.error_var.set(f"Set {cmd} failed: {actual}")
                        return
                except Exception:
                    if str(actual) != str(hz):
                        self.error_var.set(f"Set {cmd} failed: {actual}")
                        return
            elif cmd == "RLV":
                osa.write(f"LOG 5")
                osa.write(f"{cmd} {float(value):.1f}")
                actual = float(osa.query("RLV?").strip())
                if abs(actual - float(value)) > 0.11:
                    self.error_var.set(f"Set {cmd} failed: {actual}")
                    return
            elif cmd == "LOFS":
                osa.write(f"{cmd} {float(value):.2f}")
                actual = float(osa.query("LOFS?").strip())
                if abs(actual - float(value)) > 0.11:
                    self.error_var.set(f"Set {cmd} failed: {actual}")
                    return
            else:
                osa.write(f"{cmd} {value}")
                actual = osa.query(f"{cmd}?").strip()
                # FLOAT/INT-Vergleich für CNT/SPN/MPT/RES
                try:
                    if abs(float(actual) - float(value)) > 0.11:
                        self.error_var.set(f"Set {cmd} failed: {actual}")
                        return
                except Exception:
                    if str(actual) != str(value):
                        self.error_var.set(f"Set {cmd} failed: {actual}")
                        return
            self.error_var.set("")
        except Exception as exc:
            self.error_var.set(f"{cmd} set failed: {exc}")

    def apply_quality(self, quality):
        if quality == "high":
            self.set_single_param("RES", "0.03")
            self.set_single_param("VBW", "10Hz")
            self.set_single_param("MPT", "1001")
        elif quality == "med":
            self.set_single_param("RES", "0.07")
            self.set_single_param("VBW", "100Hz")
            self.set_single_param("MPT", "501")
        elif quality == "low":
            self.set_single_param("RES", "0.1")
            self.set_single_param("VBW", "100Hz")
            self.set_single_param("MPT", "501")
        self.status_var.set(f"Quality: {quality.capitalize()}")

    def start_single_sweep(self):
        if self.sweep_running:
            self.abort_flag.set()
            self.set_button_states("stopped")
            self.status_var.set("Sweep stopped.")
            return
        self.sweep_running = True
        self.abort_flag.clear()
        self.set_button_states("single")
        self.progressbar["value"] = 0
        threading.Thread(target=self.single_sweep_thread, daemon=True).start()

    def single_sweep_thread(self):
        try:
            osa = self.controller.osa
            self.status_var.set("Sweep running…")
            self.progressbar["value"] = 10
            osa.write('*CLS')
            osa.write('SSI')
            osa.query('*OPC?')  # Blockiert bis fertig
            self.progressbar["value"] = 80
            staw, stow, npoints = np.fromstring(osa.query("DCA?"), sep=",")
            wavelengths = np.linspace(staw, stow, int(npoints))
            data_dbm = np.fromstring(osa.query("DMA?"), dtype=float, sep="\r\n")
            data_lin = 10 ** (data_dbm / 10)
            self.last_wavelengths = wavelengths
            self.last_power_dbm = data_dbm
            self.last_power_lin = data_lin
            self.plot_results(wavelengths, data_lin, data_dbm, live=False)
            self.progressbar["value"] = 100
            self.status_var.set("Sweep done.")
        except Exception as exc:
            self.error_var.set(f"Sweep failed: {exc}")
            self.status_var.set("Sweep error")
            self.disconnect_osa()
        finally:
            self.sweep_running = False
            self.set_button_states("stopped")

    def start_repeat_sweep(self):
        if self.repeat_running:
            self.abort_flag.set()
            self.set_button_states("stopped")
            self.status_var.set("Repeat stopped.")
            return
        self.abort_flag.clear()
        self.repeat_running = True
        self.set_button_states("repeat")
        self.progressbar.config(mode="indeterminate")
        self.progressbar.start()
        threading.Thread(target=self.repeat_polling_loop, daemon=True).start()

    def repeat_polling_loop(self):
        try:
            osa = self.controller.osa
            osa.write('SRT')  # Repeat Mode an
            self.status_var.set("Repeat (live polling)…")
            while not self.abort_flag.is_set():
                staw, stow, npoints = np.fromstring(osa.query("DCA?"), sep=",")
                wavelengths = np.linspace(staw, stow, int(npoints))
                data_dbm = np.fromstring(osa.query("DMA?"), dtype=float, sep="\r\n")
                data_lin = 10 ** (data_dbm / 10)
                self.last_wavelengths = wavelengths
                self.last_power_dbm = data_dbm
                self.last_power_lin = data_lin
                self.plot_results(wavelengths, data_lin, data_dbm, live=True)
                time.sleep(0.3)
            osa.write('SST')
            self.status_var.set("Repeat stopped.")
        except Exception as exc:
            self.error_var.set(f"Repeat failed: {exc}")
            self.status_var.set("Repeat error")
            self.disconnect_osa()
        finally:
            self.progressbar.stop()
            self.progressbar.config(mode="determinate")
            self.repeat_running = False
            self.set_button_states("stopped")

    def set_button_states(self, mode="stopped"):
        if mode == "single":
            self.single_btn.config(text="Stop", state="normal")
            self.repeat_btn.config(text="Repeat Sweep", state="disabled")
        elif mode == "repeat":
            self.single_btn.config(text="Single Sweep", state="disabled")
            self.repeat_btn.config(text="Stop", state="normal")
        else:
            self.single_btn.config(text="Single Sweep", state="normal")
            self.repeat_btn.config(text="Repeat Sweep", state="normal")

    def plot_results(self, wavelengths, data_lin, data_dbm, live=False):
        max_val = np.nanmax(data_lin) if len(data_lin) else 1
        if max_val < 1e-6:
            unit, factor = "nW", 1e9
        elif max_val < 1e-3:
            unit, factor = "µW", 1e6
        elif max_val < 1:
            unit, factor = "mW", 1e3
        else:
            unit, factor = "W", 1
        y_lin = data_lin * factor
        live_txt = " (Live)" if live else ""
        self.ax_lin.clear()
        self.ax_lin.plot(wavelengths, y_lin)
        self.ax_lin.set_title(f"OSA Linear Scale{live_txt}")
        self.ax_lin.set_xlabel("Wavelength (nm)")
        self.ax_lin.set_ylabel(f"Power ({unit})")
        self.ax_lin.grid(True)
        self.fig_lin.tight_layout()
        self.canvas_lin.draw()
        self.ax_dbm.clear()
        self.ax_dbm.plot(wavelengths, data_dbm)
        self.ax_dbm.set_title(f"OSA dBm Scale{live_txt}")
        self.ax_dbm.set_xlabel("Wavelength (nm)")
        self.ax_dbm.set_ylabel("Power (dBm)")
        self.ax_dbm.grid(True)
        self.fig_dbm.tight_layout()
        self.canvas_dbm.draw()

    def save_data_npy(self):
        if (self.last_wavelengths is None or self.last_power_dbm is None or self.last_power_lin is None):
            messagebox.showwarning("No Data", "Please run a sweep first!")
            return
        file = filedialog.asksaveasfilename(defaultextension=".npy",
                                            filetypes=[("NumPy File", "*.npy")])
        if file:
            arr = np.vstack((self.last_wavelengths,
                             self.last_power_dbm,
                             self.last_power_lin)).T
            np.save(file, arr)
            messagebox.showinfo("Saved", f"Data saved: {file}")

    def save_linear_plot(self):
        file = filedialog.asksaveasfilename(defaultextension=".png",
                                            filetypes=[("PNG Files", "*.png")])
        if file:
            self.fig_lin.savefig(file, dpi=600, bbox_inches='tight')
            messagebox.showinfo("Saved", "Linear plot saved.")

    def save_dbm_plot(self):
        file = filedialog.asksaveasfilename(defaultextension=".png",
                                            filetypes=[("PNG Files", "*.png")])
        if file:
            self.fig_dbm.savefig(file, dpi=600, bbox_inches='tight')
            messagebox.showinfo("Saved", "dBm plot saved.")

    def on_closing(self):
        self.abort_flag.set()
        try:
            if self.controller.osa:
                self.controller.osa.write("SST")
        except Exception:
            pass
        self.master.destroy()
