import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.ticker as ticker
import re

from controllers.osa_controller import OSAController
from utils.helpers import (
    CreateToolTip, get_lin_unit_and_data, integration_string_to_hz, SMT_OPTIONS
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
        self.spans = ["1200", "1000", "500", "200", "100",
                      "50", "20", "10", "5", "2", "1"]
        self.resolution = tk.StringVar(value="0.1")
        self.integration = tk.StringVar(value="1kHz")
        self.points = tk.StringVar(value="501")
        self.central_wl = tk.DoubleVar(value=1548.5)
        self.span = tk.StringVar(value="2")
        self.smooth_points = tk.StringVar(value="OFF")
        self.reference_lvl = tk.DoubleVar(value=0.0)
        self.level_offset = tk.DoubleVar(value=0.0)
        self.repeat_mode = tk.BooleanVar(value=False)
        self.repeat_interval = tk.IntVar(value=0)
        self.prev_values = {
            "CNT": self.central_wl.get(),
            "SPN": float(self.span.get()),
            "RES": float(self.resolution.get()),
            "VBW": self.integration.get(),
            "MPT": int(self.points.get()),
            "RLV": self.reference_lvl.get(),
            "LOFS": self.level_offset.get(),
        }
        self.rm = None
        self.osa = None
        self.abort_flag = threading.Event()
        self.sweep_running = False
        self.last_wavelengths = None
        self.last_power_dbm = None
        self.last_power_lin = None
        self.unit = tk.StringVar(value="dBm")
        self.progress_factor = 2.0
        self.fig_lin, self.ax_lin = plt.subplots(figsize=(6, 4), dpi=150)
        self.fig_dbm, self.ax_dbm = plt.subplots(figsize=(6, 4), dpi=150)
        self.build_gui()
        self.update_conn_btn()

    # ---------- GUI Layout ----------
    def build_gui(self):
        main = tk.Frame(self)
        main.pack(fill="both", expand=True, padx=12, pady=8)
        main.columnconfigure(0, weight=0)
        main.columnconfigure(1, weight=1)
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
        param = tk.LabelFrame(main, text="Sweep Parameters", padx=8, pady=10)
        param.grid(row=1, column=0, sticky="nsew", pady=6)
        for c in range(4): param.columnconfigure(c, weight=1)
        row = 0
        tk.Label(param, text="Central WL [nm]:").grid(row=row, column=0, sticky="e")
        cw_entry = tk.Entry(param, textvariable=self.central_wl, width=10)
        cw_entry.grid(row=row, column=1, sticky="w")
        CreateToolTip(cw_entry, "Valid 800 – 1700 nm")
        cw_entry.bind("<Return>", lambda _e: self.validate_and_set("CNT", self.central_wl.get()))
        cw_entry.bind("<FocusOut>", lambda _e: self.validate_and_set("CNT", self.central_wl.get()))
        row += 1
        tk.Label(param, text="Span [nm]:").grid(row=row, column=0, sticky="e")
        span_cb = ttk.Combobox(param, values=self.spans, textvariable=self.span,
                               width=8, state="readonly")
        span_cb.grid(row=row, column=1, sticky="w")
        span_cb.bind("<<ComboboxSelected>>", lambda _e: self.validate_and_set("SPN", self.span.get()))
        row += 1
        tk.Label(param, text="Resolution [nm]:").grid(row=row, column=0, sticky="e")
        res_cb = ttk.Combobox(param, values=self.resolutions, textvariable=self.resolution,
                              width=8, state="readonly")
        res_cb.grid(row=row, column=1, sticky="w")
        res_cb.bind("<<ComboboxSelected>>", lambda _e: self.validate_and_set("RES", self.resolution.get()))
        row += 1
        tk.Label(param, text="Integration:").grid(row=row, column=0, sticky="e")
        integ_cb = ttk.Combobox(param, values=self.integrations, textvariable=self.integration,
                                width=8, state="readonly")
        integ_cb.grid(row=row, column=1, sticky="w")
        integ_cb.bind("<<ComboboxSelected>>", lambda _e: self.validate_and_set("VBW", self.integration.get()))
        row += 1
        tk.Label(param, text="Sampling Points:").grid(row=row, column=0, sticky="e")
        pts_cb = ttk.Combobox(param, values=self.samp_points, textvariable=self.points,
                              width=8, state="readonly")
        pts_cb.grid(row=row, column=1, sticky="w")
        pts_cb.bind("<<ComboboxSelected>>", lambda _e: self.validate_and_set("MPT", self.points.get()))
        row += 1
        tk.Label(param, text="Reference LvL [dBm]:").grid(row=row, column=0, sticky="e")
        rlv_spin = tk.Spinbox(param, from_=-90.0, to=30.0, increment=1.0,
                              textvariable=self.reference_lvl, width=8, format="%.1f",
                              command=lambda: self.validate_and_set("RLV", self.reference_lvl.get()))
        rlv_spin.grid(row=row, column=1, sticky="w")
        rlv_spin.bind("<FocusOut>", lambda _e: self.validate_and_set("RLV", self.reference_lvl.get()))
        row += 1
        tk.Label(param, text="Level Offset [dB]:").grid(row=row, column=0, sticky="e")
        lof_spin = tk.Spinbox(param, from_=-30.0, to=30.0, increment=1.0,
                              textvariable=self.level_offset, width=8, format="%.1f",
                              command=lambda: self.validate_and_set("LOFS", self.level_offset.get()))
        lof_spin.grid(row=row, column=1, sticky="w")
        lof_spin.bind("<FocusOut>", lambda _e: self.validate_and_set("LOFS", self.level_offset.get()))
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
        repeat = tk.LabelFrame(param, text="Repeat Sweep", padx=6, pady=6)
        repeat.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        tk.Checkbutton(repeat, text="Enable Repeat", variable=self.repeat_mode).grid(row=0, column=0, sticky="w")
        tk.Label(repeat, text="Interval [s]:").grid(row=1, column=0, sticky="e")
        tk.Spinbox(repeat, from_=0, to=5940, increment=1, textvariable=self.repeat_interval, width=6).grid(row=1, column=1, sticky="w")
        row += 1
        tk.Label(param, textvariable=self.status_var, fg="blue").grid(row=row, column=0, columnspan=4, pady=(14, 0))
        row += 1
        tk.Label(param, textvariable=self.error_var, fg="red", wraplength=300).grid(row=row, column=0, columnspan=4)
        row += 1
        self.progressbar = ttk.Progressbar(param, mode="determinate")
        self.progressbar.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        row += 1
        self.progress_label = tk.Label(param, text="")
        self.progress_label.grid(row=row, column=0, columnspan=4)
        row += 1
        tk.Label(param, textvariable=self.unit, fg="green", font=("Arial", 11)).grid(row=row, column=0, columnspan=4, pady=(5, 0))
        row += 1
        save_box = tk.LabelFrame(param, text="Save / Export", padx=8, pady=10)
        save_box.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        ttk.Button(save_box, text="Save Linear Plot", command=self.save_linear_plot).pack(fill="x", pady=(2, 4))
        ttk.Button(save_box, text="Save dBm Plot", command=self.save_dbm_plot).pack(fill="x", pady=(0, 4))
        ttk.Button(save_box, text="Save Data as NPY", command=self.save_data_npy).pack(fill="x", pady=(0, 4))
        plots = tk.Frame(main)
        plots.grid(row=1, column=1, rowspan=2, sticky="nsew", padx=10)
        plots.columnconfigure(0, weight=1)
        plots.columnconfigure(1, weight=1)
        plots.rowconfigure(3, weight=1)
        btn_bar = tk.Frame(plots)
        btn_bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.start_btn = ttk.Button(btn_bar, text="Start Sweep", command=self.toggle_sweep)
        self.start_btn.pack(fill="x")
        tk.Label(plots, text="Linear Scale", font=("Arial", 10, "bold")).grid(row=2, column=0)
        tk.Label(plots, text="dBm Scale", font=("Arial", 10, "bold")).grid(row=2, column=1)
        self.canvas_lin = FigureCanvasTkAgg(self.fig_lin, plots)
        self.canvas_lin.get_tk_widget().grid(row=3, column=0, sticky="nsew", padx=(6, 4), pady=8)
        self.canvas_dbm = FigureCanvasTkAgg(self.fig_dbm, plots)
        self.canvas_dbm.get_tk_widget().grid(row=3, column=1, sticky="nsew", padx=(4, 6), pady=8)

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
            if self.controller.rm is None:
                self.controller.rm = __import__('pyvisa').ResourceManager()
            self.controller.osa = self.controller.rm.open_resource(f"TCPIP0::{self.osa_ip.get()}::INSTR")
            self.controller.osa.timeout = 300_000
            idn = self.controller.osa.query("*IDN?")
            self.controller.osa.write("SND OFF")
            self.status_var.set(f"Connected: {idn.strip()}")
            self.connection_state.set("connected")
            self.read_all_params()
        except Exception as exc:
            messagebox.showerror("OSA Error", f"Connection failed: {exc}")
            self.connection_state.set("disconnected")
            self.controller.osa = None

    def disconnect_osa(self):
        try:
            if self.controller.osa:
                self.controller.osa.write("SST")
                self.controller.osa.write("SND ON")
                self.controller.osa.close()
        except Exception:
            pass
        self.controller.osa = None
        self.connection_state.set("disconnected")
        self.status_var.set("Status: Not connected")

    def read_all_params(self):
        try:
            if self.controller.osa is None:
                return
            cwl = float(self.controller.osa.query("CNT?").strip())
            self.central_wl.set(cwl)
            self.prev_values["CNT"] = cwl
            span = float(self.controller.osa.query("SPN?").strip())
            self.span.set(str(int(span)))
            self.prev_values["SPN"] = span
            res = float(self.controller.osa.query("RES?").strip())
            self.resolution.set(str(res))
            self.prev_values["RES"] = res
            vbw = self.controller.osa.query("VBW?").strip()
            self.integration.set(vbw)
            self.prev_values["VBW"] = vbw
            mpt = int(self.controller.osa.query("MPT?").strip())
            self.points.set(str(mpt))
            self.prev_values["MPT"] = mpt
            try:
                rlv = float(self.controller.osa.query("RLV?").strip())
                self.reference_lvl.set(rlv)
                self.prev_values["RLV"] = rlv
            except Exception:
                pass
            try:
                lof = float(self.controller.osa.query("LOFS?").strip())
                self.level_offset.set(lof)
                self.prev_values["LOFS"] = lof
            except Exception:
                pass
            self.status_var.set("Parameters loaded.")
        except Exception as exc:
            messagebox.showerror("OSA Error", f"Read failed: {exc}")
            self.disconnect_osa()

    @staticmethod
    def closest_integration(vbw):
        diffs = {
            k: abs(v - int(vbw))
            for k, v in {
                "1MHz": 1_000_000,
                "100kHz": 100_000,
                "10kHz": 10_000,
                "1kHz": 1_000,
                "100Hz": 100,
                "10Hz": 10,
            }.items()
        }
        return min(diffs, key=diffs.get)

    def validate_and_set(self, cmd, value):
        if cmd == "VBW":
            if value not in self.integrations:
                self.error_var.set("Invalid input or combination")
                self.integration.set(self.prev_values["VBW"])
                return
        else:
            try:
                val = float(value)
            except ValueError:
                self.error_var.set("Invalid input or combination")
                self._revert_field(cmd)
                return
            if cmd == "CNT" and not (800.0 <= val <= 1700.0):
                self.error_var.set("Invalid input or combination")
                self.central_wl.set(self.prev_values["CNT"])
                return
            if cmd == "SPN" and not (1.0 <= val <= 1200.0):
                self.error_var.set("Invalid input or combination")
                self.span.set(str(int(self.prev_values["SPN"])))
                return
            if cmd == "RES" and not (0.03 <= val <= 1.0):
                self.error_var.set("Invalid input or combination")
                self.resolution.set(str(self.prev_values["RES"]))
                return
            if cmd == "MPT":
                ival = int(val)
                if not (51 <= ival <= 50001):
                    self.error_var.set("Invalid input or combination")
                    self.points.set(str(self.prev_values["MPT"]))
                    return
            if cmd == "RLV" and not (-90.0 <= val <= 30.0):
                self.error_var.set("Invalid input or combination")
                self.reference_lvl.set(self.prev_values["RLV"])
                return
            if cmd == "LOFS" and not (-30.0 <= val <= 30.0):
                self.error_var.set("Invalid input or combination")
                self.level_offset.set(self.prev_values["LOFS"])
                return
        self.error_var.set("")
        self.set_single_param(cmd, value)

    def _revert_field(self, cmd):
        if cmd == "CNT":
            self.central_wl.set(self.prev_values["CNT"])
        elif cmd == "SPN":
            self.span.set(str(int(self.prev_values["SPN"])))
        elif cmd == "RES":
            self.resolution.set(str(self.prev_values["RES"]))
        elif cmd == "VBW":
            self.integration.set(self.prev_values["VBW"])
        elif cmd == "MPT":
            self.points.set(str(self.prev_values["MPT"]))
        elif cmd == "RLV":
            self.reference_lvl.set(self.prev_values["RLV"])
        elif cmd == "LOFS":
            self.level_offset.set(self.prev_values["LOFS"])

    def set_single_param(self, cmd, value):
        if self.connection_state.get() != "connected":
            return
        try:
            osa = self.controller.osa
            if cmd == "RLV":
                osa.write("LOG 5")
                _ = osa.query("ERR?")
                osa.write(f"{cmd} {float(value):.1f}")
            elif cmd == "VBW":
                hz = integration_string_to_hz(value)
                osa.write(f"{cmd} {hz}")
                # **Synchronisiere das Dropdown nach Setzen!**
                vbw_actual = osa.query("VBW?").strip()
                self.integration.set(vbw_actual)
                self.prev_values["VBW"] = vbw_actual
            elif cmd == "LOFS":
                osa.write(f"{cmd} {float(value):.2f}")
            else:
                osa.write(f"{cmd} {value}")

            err = int(osa.query("ERR?").strip())
            if err == -150:
                self.error_var.set("Invalid input or combination")
                self._revert_field(cmd)
                return
            if err not in (0, -113):
                self.error_var.set(f"OSA Error: {err}")
                return
            self.error_var.set("")
            self.status_var.set(f"Parameter {cmd} set.")
            if cmd in ("CNT", "SPN", "RES", "MPT", "RLV", "LOFS"):
                self.prev_values[cmd] = float(value)
            elif cmd == "VBW":
                self.prev_values["VBW"] = self.integration.get()
            self.confirm_and_update(cmd)
        except Exception as exc:
            messagebox.showerror("OSA Error", f"{cmd} set failed: {exc}")
            self.disconnect_osa()

    def confirm_and_update(self, cmd):
        try:
            osa = self.controller.osa
            if cmd == "CNT":
                val = float(osa.query("CNT?").strip())
                self.central_wl.set(val)
                self.prev_values["CNT"] = val
            elif cmd == "SPN":
                val = float(osa.query("SPN?").strip())
                self.span.set(str(int(val)))
                self.prev_values["SPN"] = val
            elif cmd == "RES":
                val = float(osa.query("RES?").strip())
                self.resolution.set(str(val))
                self.prev_values["RES"] = val
            elif cmd == "VBW":
                vbw_str = osa.query("VBW?").strip()
                self.integration.set(vbw_str)
                self.prev_values["VBW"] = vbw_str
            elif cmd == "MPT":
                val = int(osa.query("MPT?").strip())
                self.points.set(str(val))
                self.prev_values["MPT"] = val
            elif cmd == "RLV":
                val = float(osa.query("RLV?").strip())
                self.reference_lvl.set(val)
                self.prev_values["RLV"] = val
            elif cmd == "LOFS":
                val = float(osa.query("LOFS?").strip())
                self.level_offset.set(val)
                self.prev_values["LOFS"] = val
        except Exception:
            pass

    def apply_quality(self, quality):
        if quality == "high":
            self.resolution.set("0.03")
            self.integration.set("10Hz")
            self.points.set("1001")
        elif quality == "med":
            self.resolution.set("0.07")
            self.integration.set("100Hz")
            self.points.set("501")
        elif quality == "low":
            self.resolution.set("0.1")
            self.integration.set("100Hz")
            self.points.set("501")
        self.set_all_params()

    def set_all_params(self):
        if self.connection_state.get() != "connected":
            return
        try:
            osa = self.controller.osa
            old_vals = self.prev_values.copy()
            osa.write(f"CNT {self.central_wl.get():.2f}")
            osa.write(f"SPN {self.span.get()}")
            osa.write(f"RES {float(self.resolution.get())}")
            hz = integration_string_to_hz(self.integration.get())
            osa.write(f"VBW {hz}")
            # *** NACH VBW setzen, IMMER synchronisieren: ***
            vbw_actual = osa.query("VBW?").strip()
            self.integration.set(vbw_actual)
            self.prev_values["VBW"] = vbw_actual
            osa.write(f"MPT {int(self.points.get())}")
            osa.write("LOG 5")
            _ = osa.query("ERR?")
            osa.write(f"RLV {self.reference_lvl.get():.1f}")
            osa.write(f"LOFS {self.level_offset.get():.2f}")
            err = int(osa.query("ERR?").strip())
            if err == -150:
                self.error_var.set("Invalid input or combination")
                self.central_wl.set(old_vals["CNT"])
                self.span.set(str(int(old_vals["SPN"])))
                self.resolution.set(str(old_vals["RES"]))
                self.integration.set(old_vals["VBW"])
                self.points.set(str(old_vals["MPT"]))
                self.reference_lvl.set(old_vals["RLV"])
                self.level_offset.set(old_vals["LOFS"])
                self.prev_values = old_vals
                return
            if err not in (0, -113):
                self.error_var.set(f"OSA Error: {err}")
                return
            self.prev_values["CNT"] = self.central_wl.get()
            self.prev_values["SPN"] = float(self.span.get())
            self.prev_values["RES"] = float(self.resolution.get())
            self.prev_values["VBW"] = self.integration.get()
            self.prev_values["MPT"] = int(self.points.get())
            self.prev_values["RLV"] = self.reference_lvl.get()
            self.prev_values["LOFS"] = self.level_offset.get()
            self.error_var.set("")
            self.status_var.set("All parameters set.")
            for cmd in ("CNT", "SPN", "RES", "VBW", "MPT", "RLV", "LOFS"):
                self.confirm_and_update(cmd)
        except Exception as exc:
            messagebox.showerror("OSA Error", f"{exc}")
            self.disconnect_osa()

    def wait_for_sweep_end(self):
        try:
            while not self.abort_flag.is_set():
                mode = int(self.controller.osa.query("MOD?").strip())
                if mode != 2:
                    return True
                time.sleep(0.1)
        except Exception:
            pass
        return False

    def apply_repeat_mode(self):
        if self.connection_state.get() != "connected":
            return
        try:
            mode = 1 if self.repeat_mode.get() else 0
            osa = self.controller.osa
            osa.write(f"INIT:CONT {mode}")
            if mode:
                osa.write(f":SENS:SWE:TIME:INT {self.repeat_interval.get()}")
            _ = osa.query("ERR?")
        except Exception as exc:
            messagebox.showerror("OSA Error", f"Repeat-mode failed: {exc}")

    def toggle_sweep(self):
        if self.sweep_running:
            self.abort_flag.set()
        else:
            self.abort_flag.clear()
            self.apply_repeat_mode()
            if self.repeat_mode.get():
                threading.Thread(target=self.repeat_sweep_thread, daemon=True).start()
            else:
                threading.Thread(target=self.single_sweep_thread, daemon=True).start()

    def estimate_time(self, npoints):
        integ = self.integration.get()
        hz = integration_string_to_hz(integ)
        int_sec = 1 / hz if hz else 0.01
        return int_sec * npoints * self.progress_factor + 2

    def single_sweep_thread(self):
        try:
            self.sweep_running = True
            self.start_btn.config(text="Stop Sweep")
            self.status_var.set("Preparing sweep…")
            osa = self.controller.osa
            if osa is None:
                raise Exception("Not connected")
            osa.write("LOG 5")
            _ = osa.query("ERR?")
            osa.write(f"CNT {self.central_wl.get():.2f}")
            osa.write(f"SPN {self.span.get()}")
            osa.write(f"RES {float(self.resolution.get())}")
            hz = integration_string_to_hz(self.integration.get())
            osa.write(f"VBW {hz}")
            # **Nach VBW sofort synchronisieren!**
            vbw_actual = osa.query("VBW?").strip()
            self.integration.set(vbw_actual)
            self.prev_values["VBW"] = vbw_actual
            osa.write(f"MPT {int(self.points.get())}")
            actual_pts = int(float(osa.query("MPT?").strip()))
            if actual_pts != int(self.points.get()):
                self.error_var.set(f"Instrument chose {actual_pts} pts")
                self.points.set(str(actual_pts))
                self.prev_values["MPT"] = actual_pts
            err1 = int(osa.query("ERR?").strip())
            if err1 not in (0, -113):
                self.error_var.set(f"OSA Error: {err1}")
                return
            self.error_var.set("")
            eta = self.estimate_time(actual_pts)
            self.progressbar["maximum"] = 100
            self.progressbar["value"] = 0
            self.progress_label.config(text=f"{actual_pts} pts, ETA ~{eta:.1f}s")
            self.status_var.set("Sweep running…")
            osa.write("*CLS")
            osa.write("SSI")
            step_time = eta / actual_pts
            for i in range(actual_pts):
                if self.abort_flag.is_set():
                    osa.write("SST")
                    self.status_var.set("Sweep stopped.")
                    return
                percent = int((i + 1) / actual_pts * 100)
                self.progressbar["value"] = percent
                self.progress_label.config(
                    text=f"{actual_pts} pts, ETA ~{max(0, eta - (i * step_time)):.1f}s"
                )
                self.update_idletasks()
                time.sleep(step_time)
            staw, stow, npoints = np.fromstring(osa.query("DCA?"), sep=",")
            wavelengths = np.linspace(staw, stow, int(npoints))
            osa.write("TDF P")
            data_dbm = np.fromstring(osa.query("DMA?"), dtype=float, sep="\r\n")
            data_lin = 10 ** (data_dbm / 10)
            self.last_wavelengths = wavelengths
            self.last_power_dbm = data_dbm
            self.last_power_lin = data_lin
            err2 = int(osa.query("ERR?").strip())
            if err2 not in (0, -113):
                self.error_var.set(f"OSA Error: {err2}")
            else:
                self.error_var.set("")
            self.plot_results(wavelengths, data_lin, data_dbm)
            self.status_var.set("Sweep done.")
        except Exception as exc:
            messagebox.showerror("OSA Error", str(exc))
            self.status_var.set("Sweep error")
            self.disconnect_osa()
        finally:
            self.progressbar["value"] = 100
            self.progress_label.config(text="")
            self.sweep_running = False
            self.start_btn.config(text="Start Sweep")

    def repeat_sweep_thread(self):
        try:
            self.sweep_running = True
            self.start_btn.config(text="Stop Sweep")
            osa = self.controller.osa
            if osa is None:
                raise Exception("Not connected")
            osa.write("LOG 5")
            _ = osa.query("ERR?")
            self.set_all_params()
            osa.write("INIT:IMMed")
            self.progressbar.config(mode="indeterminate")
            self.progressbar.start(40)
            self.status_var.set("Repeat sweep running…   (Stop to abort)")
            while not self.abort_flag.is_set():
                if not self.wait_for_sweep_end():
                    break
                staw, stow, npts = np.fromstring(osa.query("DCA?"), sep=",")
                wl = np.linspace(staw, stow, int(npts))
                osa.write("TDF P")
                dbm = np.fromstring(osa.query("DMA?"), sep="\r\n")
                lin = 10 ** (dbm / 10)
                self.last_wavelengths, self.last_power_dbm, self.last_power_lin = wl, dbm, lin
                self.plot_results(wl, lin, dbm)
                self.update_idletasks()
                while not self.abort_flag.is_set():
                    if int(osa.query("MOD?").strip()) == 2:
                        break
                    time.sleep(0.05)
            osa.write("SST")
            self.apply_repeat_mode()
            self.status_var.set("Repeat sweep stopped.")
        except Exception as exc:
            messagebox.showerror("OSA Error", str(exc))
            self.disconnect_osa()
        finally:
            self.progressbar.stop()
            self.progressbar.config(mode="determinate", value=0)
            self.sweep_running = False
            self.start_btn.config(text="Start Sweep")

    def plot_results(self, wavelengths, data_lin, data_dbm):
        lin_unit, data_plot = get_lin_unit_and_data(data_lin)
        self.ax_lin.clear()
        self.ax_lin.plot(wavelengths, data_plot)
        self.ax_lin.set_title("OSA Linear Scale")
        self.ax_lin.set_xlabel("Wavelength (nm)")
        self.ax_lin.set_ylabel(f"Power ({lin_unit})")
        self.ax_lin.grid(True)
        self.ax_lin.xaxis.set_major_locator(ticker.MaxNLocator(nbins=5))
        self.ax_lin.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.2f'))
        self.fig_lin.tight_layout()
        self.canvas_lin.draw()
        self.ax_dbm.clear()
        self.ax_dbm.plot(wavelengths, data_dbm)
        self.ax_dbm.set_title("OSA dBm Scale")
        self.ax_dbm.set_xlabel("Wavelength (nm)")
        self.ax_dbm.set_ylabel("Power (dBm)")
        self.ax_dbm.grid(True)
        self.ax_dbm.xaxis.set_major_locator(ticker.MaxNLocator(nbins=5))
        self.ax_dbm.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.2f'))
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
