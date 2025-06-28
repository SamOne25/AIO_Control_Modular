from pyvisa.errors import VisaIOError
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading, time
import numpy as np
import logging
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import MaxNLocator, AutoMinorLocator

from controllers.osa_controller import OSAController
from utils.helpers import (
    CreateToolTip,
    integration_string_to_hz,
    SMT_OPTIONS,
    append_event,
    save_event_log,
    _OSA_make_filename
)

class OSAGUI(ttk.Frame):
    def __init__(self, parent, controller=None, wavegen_controller=None):
        super().__init__(parent)
        # OSA-Controller und Wavegen-Controller
        self.controller = controller if controller else OSAController()
        from controllers.wavegen_controller import WavegenController
        self.wavegen_controller = wavegen_controller if wavegen_controller else WavegenController()

        # Connection & Status
        self.osa_ip = tk.StringVar(value="192.168.1.112")
        self.status_var = tk.StringVar(value="Status: Not connected")
        self.error_var = tk.StringVar(value="")
        self.connection_state = tk.StringVar(value="disconnected")

        # Sweep-Parameter
        self.resolutions   = ["1.0","0.5","0.2","0.1","0.07","0.05","0.03"]
        self.integrations  = ["1MHz","100kHz","10kHz","1kHz","100Hz","10Hz"]
        self.samp_points   = ["51","101","201","251","501","1001","2001","5001","10001","20001","50001"]
        self.spans         = ["1200","1000","500","200","100","50","20","10","5","2","1"]

        self.central_wl    = tk.DoubleVar(value=1548.5)
        self.span          = tk.StringVar(value="2")
        self.resolution    = tk.StringVar(value="0.1")
        self.integration   = tk.StringVar(value="1kHz")
        self.points        = tk.StringVar(value="501")
        self.smooth_points = tk.StringVar(value="OFF")
        self.reference_lvl = tk.DoubleVar(value=0.0)
        self.level_offset  = tk.DoubleVar(value=0.0)
        
        # Debug-Modus: alle Events sammeln
        self.event_log = []

        # Sweep-Kontrolle
        self.sweep_running   = False
        self.repeat_running  = False
        self.scan_abort_flag   = threading.Event()
        self.repeat_abort_flag = threading.Event()

        # Matplotlib-Figures
        self.fig_dbm, self.ax_dbm = plt.subplots(figsize=(6,4), dpi=150)
        self.fig_lin, self.ax_lin = plt.subplots(figsize=(6,4), dpi=150)
        self.last_wavelengths = None
        self.last_power_dbm   = None
        self.last_power_lin   = None

        # Peak-Anzeige
        self.current_peak_var = tk.StringVar(value="Peak: -- dBm @ -- nm, -- Hz")
        self._max_peak_dbm = -np.inf
        self.max_peak_var  = tk.StringVar()
        self._reset_max_peak()

        # Scan-Kontrolle
        self.scan_running = False
        self.scan_mode = False

        # GUI aufbauen
        self.build_gui()
        self.update_conn_btn()

    def build_gui(self):
        main = tk.Frame(self)
        main.pack(fill="both", expand=True, padx=12, pady=8)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=3)
        main.rowconfigure(1, weight=1)

        # Top bar
        top = tk.Frame(main)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0,10))
        tk.Label(top, text="OSA IP:").grid(row=0, column=0, sticky="e")
        tk.Entry(top, textvariable=self.osa_ip, width=16).grid(row=0, column=1, sticky="w")
        self.connect_btn = tk.Button(top, text="Connect", width=12, command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=2, padx=(10,0))
        tk.Label(top, text="Wavegen IP:").grid(row=0, column=3, sticky="e", padx=(20,2))
        self.wg_ip = tk.StringVar(value="192.168.1.122")
        tk.Entry(top, textvariable=self.wg_ip, width=16).grid(row=0, column=4, sticky="w")
        self.wg_connect_btn = tk.Button(top, text="Connect WG", width=12, bg="red",
                                        command=self.toggle_wavegen_connection)
        self.wg_connect_btn.grid(row=0, column=5, padx=(10,0))

        # Sweep Parameters
        param = tk.LabelFrame(main, text="Sweep Parameters", padx=8, pady=10)
        param.grid(row=1, column=0, sticky="nsew", pady=6)
        for c in range(2):
            param.columnconfigure(c*2, weight=0)
            param.columnconfigure(c*2+1, weight=1)

        cmd_map = {"Span [nm]:":"SPN","Resolution [nm]:":"RES",
                   "Integration:":"VBW","Sampling Points:":"MPT","Smooth:":"SMT"}
        spin_map = {"Reference LvL [dBm]:":"RLV","Level Offset [dB]:":"LOFS"}
        specs = [
            ("Central WL [nm]:","entry", self.central_wl, 800, 1700),
            ("Span [nm]:","combo", self.span, self.spans, None),
            ("Resolution [nm]:","combo", self.resolution, self.resolutions, None),
            ("Integration:","combo", self.integration, self.integrations, None),
            ("Sampling Points:","combo", self.points, self.samp_points, None),
            ("Reference LvL [dBm]:","spin", self.reference_lvl, -90, 30),
            ("Level Offset [dB]:","spin", self.level_offset, -30, 30),
            ("Smooth:","combo", self.smooth_points, SMT_OPTIONS, None),
        ]
        row = 0
        for idx, (txt, typ, var, opt1, opt2) in enumerate(specs):
            col = (idx % 2) * 2
            tk.Label(param, text=txt).grid(row=row, column=col, sticky="e", padx=4, pady=4)
            if typ == "entry":
                e = tk.Entry(param, textvariable=var, width=10)
                e.grid(row=row, column=col+1, sticky="w", padx=4, pady=4)
                CreateToolTip(e, f"Valid {opt1}–{opt2} nm")
                e.bind("<Return>",   lambda e, v=var: self.set_single_param("CNT", v.get()))
                e.bind("<FocusOut>", lambda e, v=var: self.set_single_param("CNT", v.get()))
            elif typ == "combo":
                # für Span erlauben wir auch eigene Eingabe
                state = "normal" if txt == "Span [nm]:" else "readonly"
                cb = ttk.Combobox(param, values=opt1, textvariable=var, width=10, state=state)
                cb.grid(row=row, column=col+1, sticky="w", padx=4, pady=4)
                cb.bind("<<ComboboxSelected>>",
                        lambda e, v=var, cmd=cmd_map[txt]: self.set_single_param(cmd, v.get()))
                if txt == "Span [nm]:":
                    self.span_cb = cb
                    # bei Fokusverlust oder Enter den neuen Span-Wert setzen
                    self.span_cb.bind("<FocusOut>",
                        lambda e: self.set_single_param("SPN", self.span.get()))
                    self.span_cb.bind("<Return>",
                        lambda e: self.set_single_param("SPN", self.span.get()))
                elif txt == "Resolution [nm]:":
                    self.resolution_cb = cb
                elif txt == "Integration:":
                    self.integration_cb = cb
                elif txt == "Sampling Points:":
                    self.points_cb = cb
                elif txt == "Smooth:":
                    self.smooth_cb = cb
            else:
                sb = tk.Spinbox(param, from_=opt1, to=opt2, increment=1.0,
                                textvariable=var, width=10,
                                command=lambda v=var, cmd=spin_map[txt]: self.set_single_param(cmd, v.get()))
                sb.grid(row=row, column=col+1, sticky="w", padx=4, pady=4)
                sb.bind("<FocusOut>",
                    lambda e, v=var, cmd=spin_map[txt]: self.set_single_param(cmd, v.get()))
                if txt == "Reference LvL [dBm]:":
                    self.ref_spin = sb
                elif txt == "Level Offset [dB]:":
                    self.offset_spin = sb
            if idx % 2 == 1:
                row += 1

        # Quality Buttons
        quality=tk.LabelFrame(param,text="Quality",padx=4,pady=4)
        quality.grid(row=row,column=0,columnspan=4,sticky="ew",pady=(10,0))
        self.quality_buttons=[]
        for i,q in enumerate(("low","med","high")):
            btn=ttk.Button(quality,text=q.capitalize(),
                           command=lambda q=q: self.apply_quality(q))
            btn.grid(row=0,column=i,padx=6,pady=2)
            self.quality_buttons.append(btn)
        row+=1

        # Sweep Buttons + Progress
        btns=tk.Frame(param)
        btns.grid(row=row,column=0,columnspan=4,pady=(8,4))
        self.single_btn=ttk.Button(btns,text="Single Sweep",command=self.start_single_sweep)
        self.repeat_btn=ttk.Button(btns,text="Repeat Sweep",command=self.start_repeat_sweep)
        self.single_btn.pack(side="left",padx=6)
        self.repeat_btn.pack(side="left",padx=6)
        self.scanmode_btn=tk.Button(btns,text="Scan Mode OFF",bg="lightgray",command=self.toggle_scan_mode)
        self.scanmode_btn.pack(side="left",padx=6)
        row+=1

        self.progressbar=ttk.Progressbar(param,mode="determinate",length=200)
        self.progressbar.grid(row=row,column=0,columnspan=4,pady=(4,0))
        row+=1

        # Status / Error
        tk.Label(param,textvariable=self.status_var,fg="blue").grid(row=row,column=0,columnspan=4)
        row+=1
        tk.Label(param,textvariable=self.error_var,fg="red").grid(row=row,column=0,columnspan=4)
        row+=1

        # ─── Scan via Wavegen ────────────────────────────────────────────────────
        self.scan_frame = tk.LabelFrame(param, text="Scan via Wavegen", padx=6, pady=6)
        self.scan_frame.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(10,0))
        self.scan_frame.grid_remove()
        scan_row = 0

        # Start / End / Step
        for label, attr, default in [
            ("Start Freq (Hz):", "scan_start", "4000"),
            ("End   Freq (Hz):", "scan_end",   "5000"),
            ("Step  (Hz):",      "scan_step",  "0.1"),
        ]:
            tk.Label(self.scan_frame, text=label).grid(row=scan_row, column=0, sticky="e", padx=4, pady=2)
            ent = tk.Entry(self.scan_frame, width=12)
            setattr(self, attr, ent)
            ent.insert(0, default)
            ent.grid(row=scan_row, column=1, columnspan=3, sticky="w", padx=4, pady=2)
            scan_row += 1

        # Current Freq
        tk.Label(self.scan_frame, text="Current Freq (Hz):").grid(row=scan_row, column=0, sticky="e", padx=4, pady=2)
        self.curr_freq_var = tk.StringVar(value="0.000")
        self.curr_freq_entry = tk.Entry(self.scan_frame, textvariable=self.curr_freq_var, width=12)
        self.curr_freq_entry.grid(row=scan_row, column=1, sticky="w", padx=4, pady=2)
        self.curr_freq_entry.bind("<Return>", self._manual_freq_entry)
        
        self.curr_freq_label = tk.Label(self.scan_frame, text="0.000 Hz", fg="blue", width=12, anchor="w")
        self.curr_freq_label.grid(row=scan_row, column=2, sticky="w", padx=4, pady=2)
        scan_row += 1

        # Adjust Frequency
        self.adj_frame = tk.LabelFrame(self.scan_frame, text="Adjust Frequency", padx=5, pady=5)
        self.adj_frame.grid(row=scan_row, column=0, columnspan=4, sticky="ew", padx=4, pady=4)
        steps = [(-10,10),(-1,1),(-0.1,0.1),(-0.01,0.01),(-0.001,0.001)]
        for col,(neg,pos) in enumerate(steps):
            tk.Button(self.adj_frame, text=f"{neg:+}Hz", width=6,
                      command=lambda s=neg: self.adjust_scan_freq(s)).grid(row=0, column=col, padx=2, pady=2)
            tk.Button(self.adj_frame, text=f"{pos:+}Hz", width=6,
                      command=lambda s=pos: self.adjust_scan_freq(s)).grid(row=1, column=col, padx=2, pady=2)
        tk.Button(self.adj_frame, text="×10", width=6,
                  command=lambda: self.scale_scan_freq(10)).grid(row=0, column=len(steps), padx=6, pady=2)
        tk.Button(self.adj_frame, text="÷10", width=6,
                  command=lambda: self.scale_scan_freq(0.1)).grid(row=1, column=len(steps), padx=6, pady=2)
        scan_row += 1

        # Start / Stop Scan Buttons
        tk.Button(self.scan_frame, text="Start Scan", command=self.start_scan)\
            .grid(row=scan_row, column=0, padx=6, pady=4, sticky="w")
        tk.Button(self.scan_frame, text="Stop Scan", command=lambda:[self.stop_scan(), self.start_repeat_sweep()])\
            .grid(row=scan_row, column=1, padx=6, pady=4, sticky="w")
        scan_row += 1

        # Peak Displays
        tk.Label(self.scan_frame, text="Current Peak:", fg="darkgreen")\
            .grid(row=scan_row, column=0, sticky="w", padx=4, pady=2)
        tk.Label(self.scan_frame, textvariable=self.current_peak_var, fg="darkgreen")\
            .grid(row=scan_row, column=1, columnspan=3, sticky="w", padx=4, pady=2)
        scan_row += 1
        
        tk.Label(self.scan_frame, text="Max Peak:", fg="darkred")\
            .grid(row=scan_row, column=0, sticky="w", padx=4, pady=2)
        tk.Label(self.scan_frame, textvariable=self.max_peak_var, fg="darkred")\
            .grid(row=scan_row, column=1, columnspan=3, sticky="w", padx=4, pady=2)
        scan_row += 1

        # Reset Max
        tk.Button(self.scan_frame, text="Reset Max", width=10, command=self._reset_max_peak)\
            .grid(row=scan_row, column=0, padx=6, pady=(4,0), sticky="w")

        # ─── Save Frame (Data & Plots) ────────────────────────────────────────────
        save_frame = tk.LabelFrame(param, text="Save", padx=8, pady=6)
        save_frame.grid(row=row+1, column=0, columnspan=4, sticky="ew", pady=(10,0))
        ttk.Button(save_frame, text="Save Data (.npy)", command=self.save_data_npy).grid(row=0, column=0, padx=6)
        ttk.Button(save_frame, text="Save Linear Plot", command=self.save_linear_plot).grid(row=0, column=1, padx=6)
        ttk.Button(save_frame, text="Save dBm Plot", command=self.save_dbm_plot).grid(row=0, column=2, padx=6)

        # Plots
        plots=tk.Frame(main)
        plots.grid(row=1,column=1,rowspan=2,sticky="nsew",padx=10)
        plots.columnconfigure(0,weight=1); plots.rowconfigure(0,weight=1)

        self.plot_tabs=ttk.Notebook(plots)
        self.dbm_tab=ttk.Frame(self.plot_tabs)
        self.lin_tab=ttk.Frame(self.plot_tabs)
        self.plot_tabs.add(self.dbm_tab,text="dBm Scale")
        self.plot_tabs.add(self.lin_tab,text="Linear Scale")
        
        # Canvas für dBm-Plot
        self.canvas_dbm = FigureCanvasTkAgg(self.fig_dbm, master=self.dbm_tab)
        self.canvas_dbm.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)
        
        # Canvas für Linear-Plot
        self.canvas_lin = FigureCanvasTkAgg(self.fig_lin, master=self.lin_tab)
        self.canvas_lin.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)

        # Log-Tab
        self.log_tab=ttk.Frame(self.plot_tabs)
        self.plot_tabs.add(self.log_tab,text="Event Log")
        # Setup log text and save btn
        self.log_text=tk.Text(self.log_tab,wrap="none",height=20)
        self.log_text.pack(fill="both",expand=True,padx=8,pady=8)
        btnf=tk.Frame(self.log_tab); btnf.pack(fill="x",padx=8,pady=(0,8))
        tk.Button(btnf,text="Save Log to file",command=self._save_event_log).pack(side="right")
        self.plot_tabs.grid(row=0,column=0,sticky="nsew",pady=6)

    # ─── UI-Update für Connect/Disconnect ─────────────────────────────────────
    def update_conn_btn(self):
        if self.connection_state.get() == "connected":
            self.connect_btn.config(text="Disconnect", bg="green", fg="white")
        else:
            self.connect_btn.config(text="Connect",    bg="red",   fg="white")

    def toggle_connection(self):
        if self.connection_state.get() == "disconnected":
            self.connect_osa()
        else:
            self.disconnect_osa()
        self.update_conn_btn()

    # ─── OSA Verbindung ───────────────────────────────────────────────────────
    def connect_osa(self):
        try:
            import pyvisa
            if self.controller.rm is None:
                self.controller.rm = pyvisa.ResourceManager()
            append_event(self.event_log, self.log_text, "SEND", "*IDN?")
            self.controller.osa = self.controller.rm.open_resource(
                f"TCPIP0::{self.osa_ip.get()}::INSTR"
            )
            self.controller.osa.timeout = 300_000

            resp = self.controller.osa.query("*IDN?")
            append_event(self.event_log, self.log_text, "RESPONSE", resp.strip())

            append_event(self.event_log, self.log_text, "SEND", "LOG 5")
            self.controller.osa.write("LOG 5")

            self.status_var.set(f"Connected: {resp.strip()}")
            self.connection_state.set("connected")
            self.read_all_params()
        except Exception as e:
            messagebox.showerror("OSA Error", f"Connection failed: {e}")
            self.connection_state.set("disconnected")
            self.controller.osa = None

    def disconnect_osa(self):
        self.scan_abort_flag.set()
        if getattr(self.controller, "osa", None):
            append_event(self.event_log, self.log_text, "SEND", "SST")
            try:
                self.controller.osa.write("SST")
                self.controller.osa.close()
            except:
                pass
        self.controller.osa = None
        self.connection_state.set("disconnected")
        self.status_var.set("Status: Not connected")

    # ─── Parameter aus OSA auslesen ────────────────────────────────────────────
    def read_all_params(self):
        try:
            osa = self.controller.osa
            if not osa:
                return
            for cmd, var, cast in [
                ("CNT?", self.central_wl, float),
                ("SPN?", self.span, lambda x: str(int(float(x)))),
                ("RES?", self.resolution, float),
                ("VBW?", self.integration, str),
                ("MPT?", self.points, lambda x: str(int(float(x)))),
            ]:
                append_event(self.event_log, self.log_text, "SEND", cmd)
                resp = osa.query(cmd)
                append_event(self.event_log, self.log_text, "RESPONSE", resp.strip())
                var.set(cast(resp.strip()))

            # optional RLV und LOFS
            try:
                append_event(self.event_log, self.log_text, "SEND", "RLV?")
                resp = osa.query("RLV?")
                append_event(self.event_log, self.log_text, "RESPONSE", resp.strip())
                self.reference_lvl.set(float(resp.strip()))
            except:
                pass
            try:
                append_event(self.event_log, self.log_text, "SEND", "LOFS?")
                resp = osa.query("LOFS?")
                append_event(self.event_log, self.log_text, "RESPONSE", resp.strip())
                self.level_offset.set(float(resp.strip()))
            except:
                pass

            self.status_var.set("Parameters loaded.")
        except Exception as e:
            self.error_var.set(f"Read failed: {e}")

    # ─── Einzelparameter setzen ─────────────────────────────────────────────────
    def set_single_param(self, cmd, value):
        if self.connection_state.get() != "connected":
            return
        osa = self.controller.osa

        append_event(self.event_log, self.log_text, "SEND", f"{cmd} {value}")
        try:
            if cmd == "VBW":
                hz = integration_string_to_hz(value)
                osa.write(f"{cmd} {hz}")
                append_event(self.event_log, self.log_text, "SEND", "VBW?")
                resp = osa.query("VBW?")
                append_event(self.event_log, self.log_text, "RESPONSE", resp.strip())
                if int(round(float(resp))) != int(round(hz)):
                    raise ValueError(f"expected {hz}, got {resp}")
            else:
                osa.write(f"{cmd} {value}")
                append_event(self.event_log, self.log_text, "SEND", f"{cmd}?")
                resp = osa.query(f"{cmd}?")
                append_event(self.event_log, self.log_text, "RESPONSE", resp.strip())
                try:
                    if abs(float(resp) - float(value)) > 0.1:
                        raise ValueError(f"expected {value}, got {resp}")
                except ValueError:
                    if resp.strip().upper() != str(value).strip().upper():
                        raise
            self.error_var.set("")
        except Exception as e:
            self.error_var.set(f"{cmd} set warning: {e}")

    # ─── Quality Presets ───────────────────────────────────────────────────────
    def apply_quality(self, quality):
        if quality == "high":
            res, vbw, mpt = "0.03", "10Hz", "1001"
        elif quality == "med":
            res, vbw, mpt = "0.07", "100Hz", "501"
        else:
            res, vbw, mpt = "0.1", "100Hz", "501"
        self.resolution.set(res)
        self.integration.set(vbw)
        self.points.set(mpt)
        self.set_single_param("RES", res)
        self.set_single_param("VBW", vbw)
        self.set_single_param("MPT", mpt)
        self.status_var.set(f"Quality: {quality}")

    # ─── Button Update ─────────────────────────────────────────────────────────
    def set_button_states(self, mode="stopped"):
        """
        Schaltet die Beschriftung und den Zustand der Sweep-Buttons um.
        mode: "single" | "repeat" | "stopped"
        """
        if mode == "single":
            # Single-Sweep läuft
            self.single_btn.config(text="Stop", state="normal")
            self.repeat_btn.config(text="Repeat Sweep", state="disabled")
        elif mode == "repeat":
            # Repeat-Sweep läuft
            self.single_btn.config(text="Single Sweep", state="disabled")
            self.repeat_btn.config(text="Stop", state="normal")
        else:
            # Beide gestoppt
            self.single_btn.config(text="Single Sweep", state="normal")
            self.repeat_btn.config(text="Repeat Sweep", state="normal")


    # ─── Single Sweep ──────────────────────────────────────────────────────────
    def start_single_sweep(self):
        if self.sweep_running:
            self.scan_abort_flag.set()
            self.set_button_states("stopped")
            self.status_var.set("Sweep stopped.")
            return
        self.sweep_running = True
        self.scan_abort_flag.clear()
        self.set_button_states("single")
        self.progressbar["value"] = 0
        threading.Thread(target=self.single_sweep_thread, daemon=True).start()

    def single_sweep_thread(self):
        try:
            osa = self.controller.osa
            self.status_var.set("Sweep running…")
            self.progressbar["value"] = 10
    
            # 1) Gerät zurücksetzen und Sweep starten
            for cmd in ("*CLS", "SSI"):
                if self.scan_abort_flag.is_set():
                    self.master.after(0, lambda: self.status_var.set("Sweep aborted"))
                    return
                append_event(self.event_log, self.log_text, "SEND", cmd)
                osa.write(cmd)
    
            # 2) Auf Fertigmeldung warten
            append_event(self.event_log, self.log_text, "SEND", "*OPC?")
            osa.query("*OPC?")
            append_event(self.event_log, self.log_text, "RESPONSE", "1")
    
            if self.scan_abort_flag.is_set():
                self.master.after(0, lambda: self.status_var.set("Sweep aborted"))
                return
    
            # 3) Sweep-Daten abholen
            append_event(self.event_log, self.log_text, "SEND", "DCA?")
            dca = osa.query("DCA?")
            append_event(self.event_log, self.log_text, "RESPONSE", dca.strip())
            staw, stow, npts = map(float, dca.split(","))
            wl = np.linspace(staw, stow, int(npts))
    
            if self.scan_abort_flag.is_set():
                self.master.after(0, lambda: self.status_var.set("Sweep aborted"))
                return
    
            append_event(self.event_log, self.log_text, "SEND", "DMA?")
            dbm = np.fromstring(osa.query("DMA?"), dtype=float, sep="\r\n")
            append_event(self.event_log, self.log_text, "RESPONSE", "<binary>")
            lin = 10 ** (dbm / 10)
    
            # 4) Peak berechnen und anzeigen
            idx = int(np.nanargmax(dbm))
            val, wl0 = dbm[idx], wl[idx]
            try:
                append_event(self.event_log, self.log_text, "SEND", "SOUR1:FREQ?")
                resp = self.wavegen_controller.query("SOUR1:FREQ?")
                append_event(self.event_log, self.log_text, "RESPONSE", resp.strip())
                freq = float(resp)
            except:
                freq = 0.0
    
            self.master.after(0, lambda v=val, w=wl0, f=freq: self._set_peak(v, w, f))
    
            # 5) Plotten
            self.master.after(0, lambda w=wl, ln=lin, db=dbm: 
                             self.plot_results(w, ln, db, live=False))
    
            self.progressbar["value"] = 100
            self.status_var.set("Sweep done.")
        except Exception as e:
            self.error_var.set(f"Sweep failed: {e}")
            self.status_var.set("Sweep error")
        finally:
            # Auf jeden Fall zurücksetzen
            self.sweep_running = False
            # Buttons wieder aktivieren
            self.master.after(0, self.set_button_states, "stopped")
            # Falls du einen indeterminierten Progressbar benutzt, evtl. auch:
            try: self.progressbar.stop()
            except: pass

    # ─── Repeat Sweep ─────────────────────────────────────────────────────────
    def start_repeat_sweep(self):
        if self.controller.osa is None:
            messagebox.showerror("Error", "Repeat Sweep only after OSA connect!")
            return
        if self.repeat_running:
            # abbrechen
            self.repeat_abort_flag.set()
            return

        # Repeat starten
        self.repeat_abort_flag.clear()
        self.repeat_running = True
        self.set_button_states("repeat")
        self.progressbar.config(mode="indeterminate")
        self.progressbar.start()
        threading.Thread(target=self.repeat_polling_loop, daemon=True).start()

    def repeat_polling_loop(self):
        osa = self.controller.osa
        append_event(self.event_log, self.log_text, "INFO", "repeat_polling_loop started")

        # OSA in Repeat-Mode schalten
        append_event(self.event_log, self.log_text, "SEND", "*CLS")
        osa.write("*CLS")
        append_event(self.event_log, self.log_text, "SEND", "SRT")
        osa.write("SRT")
        self.master.after(0, lambda: self.status_var.set("Repeat (live polling)…"))

        # Polling-Schleife
        while not self.repeat_abort_flag.is_set():
            try:
                # Sweep-Beschreibung
                append_event(self.event_log, self.log_text, "SEND", "DCA?")
                dca = osa.query("DCA?")
                append_event(self.event_log, self.log_text, "RESPONSE", dca.strip())
                staw, stow, npts = map(float, dca.split(","))
                wl = np.linspace(staw, stow, int(npts))

                # Power-Daten
                append_event(self.event_log, self.log_text, "SEND", "DMA?")
                raw = osa.query("DMA?")
                append_event(self.event_log, self.log_text, "RESPONSE", "<binary>")
                dbm = np.fromstring(raw, dtype=float, sep="\r\n")
                lin = 10 ** (dbm / 10)

                # Wavegen-Freq
                if getattr(self.wavegen_controller, "gen", None):
                    append_event(self.event_log, self.log_text, "SEND", "SOUR1:FREQ?")
                    resp = self.wavegen_controller.query("SOUR1:FREQ?")
                    append_event(self.event_log, self.log_text, "RESPONSE", resp.strip())
                    freq = float(resp)
                    self.master.after(0, lambda f=freq: self.curr_freq_label.config(text=f"{f:.3f} Hz"))
                else:
                    self.master.after(0, lambda: self.curr_freq_label.config(text="0.000 Hz"))

                # Peak & Plot
                idx = int(np.nanargmax(dbm))
                cur_val, cur_wl = dbm[idx], wl[idx]
                self.master.after(0, lambda v=cur_val, w=cur_wl, f=freq if 'freq' in locals() else 0.0:
                                  self._set_peak(v, w, f))
                self.master.after(0, lambda w=wl, ln=lin, db=dbm: self.plot_results(w, ln, db, live=True))

            except VisaIOError as e:
                self.master.after(0, lambda e=e: self.error_var.set(f"I/O error during repeat: {e}"))
                break
            except Exception as e:
                append_event(self.event_log, self.log_text, "ERROR", f"repeat_polling_loop crash: {e}")
                self.master.after(0, lambda e=e: self.error_var.set(f"Repeat polling error: {e}"))
                break

            time.sleep(0.3)

        # Repeat beenden
        append_event(self.event_log, self.log_text, "SEND", "SST")
        try:
            osa.write("SST")
        except:
            pass

        append_event(self.event_log, self.log_text, "INFO", "repeat_polling_loop exited")
        self.repeat_running = False
        self.master.after(0, lambda: self.status_var.set("Repeat stopped."))
        self.master.after(0, self._finish_repeat)

    # ─── Scan Mode ────────────────────────────────────────────────────────────
    def toggle_scan_mode(self):
        """
        Scan-Mode EIN/AUS schalten:
        - Im Scan-Mode verhält sich die GUI wie bei Repeat-Sweep (Live-Polling).
        - Automatisch mit dem Wavegen verbinden und Start-Freq abfragen.
        """
        if self.connection_state.get() != "connected":
            messagebox.showerror("Error", "Please connect OSA first!")
            return

        # Modus umschalten
        self.scan_mode = not self.scan_mode
        if self.scan_mode:
            append_event(self.event_log, self.log_text, "INFO", "Enter Scan Mode")
            self.scanmode_btn.config(text="Scan Mode ON", bg="yellow")
            self.single_btn.config(state="disabled")
            self.repeat_btn.config(state="disabled")

            # laufendes Live-Polling stoppen
            self.repeat_abort_flag.set()
            self.repeat_running = False

            # WAVEGEN: verbinden falls nötig
            if getattr(self.wavegen_controller, "gen", None) is None:
                try:
                    ip = self.wg_ip.get().strip()
                    self.wavegen_controller.connect(ip)
                    append_event(self.event_log, self.log_text, "INFO", f"Wavegen connected @ {ip}")
                    self.wg_connect_btn.config(text="Disconnect WG", bg="green")
                except Exception as e:
                    messagebox.showerror("Wavegen Error", f"Connection failed: {e}")
                    # Modus rückgängig machen
                    self.scan_mode = False
                    self.scanmode_btn.config(text="Scan Mode OFF", bg="lightgray")
                    self.single_btn.config(state="normal")
                    self.repeat_btn.config(state="normal")
                    return

            # aktuelle Freq vom Wavegen abfragen
            append_event(self.event_log, self.log_text, "SEND", "SOUR1:FREQ?")
            try:
                resp = self.wavegen_controller.query("SOUR1:FREQ?")
                append_event(self.event_log, self.log_text, "RESPONSE", resp.strip())
                f0 = round(float(resp), 3)
            except Exception as e:
                append_event(self.event_log, self.log_text, "ERROR", f"Freq query failed: {e}")
                f0 = 0.0

            # Felder vorbelegen
            self.curr_freq_var.set(f"{f0:.3f}")
            self.curr_freq_label.config(text=f"{f0:.3f} Hz")
            self.scan_start.delete(0, tk.END)
            self.scan_start.insert(0, f"{f0-1:.3f}")
            self.scan_end.delete(0, tk.END)
            self.scan_end.insert(0, f"{f0+1:.3f}")

            # Live-Polling wieder starten
            self.repeat_abort_flag.clear()
            self.repeat_running = True
            threading.Thread(target=self.repeat_polling_loop, daemon=True).start()

            # Scan-Frame einblenden
            self.scan_frame.grid()

        else:
            append_event(self.event_log, self.log_text, "INFO", "Exit Scan Mode")
            self.scanmode_btn.config(text="Scan Mode OFF", bg="lightgray")
            self.scan_frame.grid_remove()

            self.repeat_abort_flag.set()
            self.repeat_running = False
            self.single_btn.config(state="normal")
            self.repeat_btn.config(state="normal")


    def start_scan(self):
        """
        Einmal-Scan von self._scan_f0 bis self._scan_f1 in Schritten self._scan_df.
        Stoppt das Live-Polling, macht pro Schritt einen Single-Sweep, plottet,
        und startet danach das Live-Polling wieder.
        """
        append_event(self.event_log, self.log_text, "BUTTON", "Start Scan pressed")

        if not self.scan_mode:
            messagebox.showerror("Error", "Enable Scan Mode first!")
            return

        # 1) Live-Polling sauber beenden
        self.repeat_abort_flag.set()
        self.repeat_running = False

        # 2) OSA aus Repeat-Mode holen
        try:
            append_event(self.event_log, self.log_text, "SEND", "SST")
            self.controller.osa.write("SST")
        except Exception as e:
            append_event(self.event_log, self.log_text, "ERROR", f"SST failed: {e}")

        # 3) Scan-Parameter einlesen
        try:
            self._scan_f0 = float(self.scan_start.get())
            self._scan_f1 = float(self.scan_end.get())
            self._scan_df = float(self.scan_step.get())
        except ValueError:
            messagebox.showerror("Scan error", "Invalid frequency parameters")
            return

        # 4) Scan starten
        self.scan_abort_flag.clear()
        threading.Thread(target=self._scan_thread, daemon=True).start()


    def _scan_thread(self):
        """
        Arbeitet pro Frequenzschritt:
         - Wavegen setzen
         - Single-Sweep am OSA (*CLS, SSI, *OPC?, DCA?, DMA?)
         - Plot + Peak
        Am Ende: "Scan finished" und Restart des Live-Polling.
        """
        osa = self.controller.osa
        f = self._scan_f0
        df = self._scan_df

        try:
            while not self.scan_abort_flag.is_set() and f <= self._scan_f1:
                # Wavegen setzen
                if getattr(self.wavegen_controller, "gen", None):
                    try:
                        self.wavegen_controller.write(f"SOUR1:FREQ {f}")
                        append_event(self.event_log, self.log_text, "SEND", f"SOUR1:FREQ {f}")
                        append_event(self.event_log, self.log_text, "RESPONSE", f"Wavegen set to {f:.3f} Hz")
                    except Exception as e:
                        append_event(self.event_log, self.log_text, "ERROR", f"Wavegen write failed: {e}")
                else:
                    append_event(self.event_log, self.log_text, "WARN", "Wavegen not connected")

                # Single-Sweep
                append_event(self.event_log, self.log_text, "SEND", "*CLS"); osa.write("*CLS")
                append_event(self.event_log, self.log_text, "SEND", "SSI"); osa.write("SSI")
                append_event(self.event_log, self.log_text, "SEND", "*OPC?")
                resp = osa.query("*OPC?"); append_event(self.event_log, self.log_text, "RESPONSE", resp.strip())

                # DCA?
                append_event(self.event_log, self.log_text, "SEND", "DCA?")
                dca = osa.query("DCA?"); append_event(self.event_log, self.log_text, "RESPONSE", dca.strip())
                staw, stow, npts = map(float, dca.split(","))
                wl = np.linspace(staw, stow, int(npts))

                # DMA?
                append_event(self.event_log, self.log_text, "SEND", "DMA?")
                raw = osa.query("DMA?"); append_event(self.event_log, self.log_text, "RESPONSE", "<binary>")
                dbm = np.fromstring(raw, dtype=float, sep="\r\n")
                lin = 10 ** (dbm / 10)

                # Peak & Plot über main-Thread
                idx = int(np.nanargmax(dbm))
                val, wl0 = dbm[idx], wl[idx]
                self.master.after(0, lambda v=val, w=wl0, f=f: self._set_peak(v, w, f))
                self.master.after(0, lambda w=wl, ln=lin, db=dbm: self.plot_results(w, ln, db, live=False))

                # Schritt vorwärts
                f = round(f + df, 6)
                time.sleep(0.3)

            # Ende
            self.master.after(0, lambda: self.status_var.set("Scan finished"))

        except Exception as e:
            self.master.after(0, lambda: self.error_var.set(f"Scan error: {e}"))

        finally:
            # Live-Polling neu starten
            self.repeat_abort_flag.clear()
            self.repeat_running = True
            threading.Thread(target=self.repeat_polling_loop, daemon=True).start()


    # ─── Plot-Update ─────────────────────────────────────────────────────────
    def plot_results(self, wavelengths, data_lin, data_dbm, live=False):
        max_lin = np.nanmax(data_lin) if len(data_lin) else 1
        if max_lin < 1e-6:
            unit, factor = "pW", 1e9
        elif max_lin < 1e-3:
            unit, factor = "nW", 1e6
        elif max_lin < 1:
            unit, factor = "µW", 1e3
        else:
            unit, factor = "mW", 1
        y_lin = data_lin * factor
        txt = " (Live)" if live else ""
        # linear
        self.ax_lin.clear()
        self.ax_lin.plot(wavelengths, y_lin)
        self.ax_lin.set_title(f"OSA Linear Scale{txt}")
        self.ax_lin.set_xlabel("Wavelength (nm)")
        self.ax_lin.set_ylabel(f"Power ({unit})")
        self.ax_lin.xaxis.set_major_locator(MaxNLocator(5))
        self.ax_lin.xaxis.set_minor_locator(AutoMinorLocator(2))
        self.ax_lin.grid(which='major', axis='x', linestyle='-')
        self.ax_lin.grid(which='minor', axis='x', linestyle=':', alpha=0.7)
        self.fig_lin.tight_layout()
        self.canvas_lin.draw()
        # dBm
        self.ax_dbm.clear()
        self.ax_dbm.plot(wavelengths, data_dbm)
        self.ax_dbm.set_title(f"OSA dBm Scale{txt}")
        self.ax_dbm.set_xlabel("Wavelength (nm)")
        self.ax_dbm.set_ylabel("Power (dBm)")
        self.ax_dbm.xaxis.set_major_locator(MaxNLocator(5))
        self.ax_dbm.xaxis.set_minor_locator(AutoMinorLocator(2))
        self.ax_dbm.grid(which='major', axis='x', linestyle='-')
        self.ax_dbm.grid(which='minor', axis='x', linestyle=':', alpha=0.7)
        self.fig_dbm.tight_layout()
        self.canvas_dbm.draw()

    # ─── Scan stoppen und Repeat zurück ───────────────────────────────────────
    def stop_scan(self):
        append_event(self.event_log, self.log_text, "BUTTON", "Stop Scan pressed")
        # Scan-Abbruch setzen; Repeat-Restart übernimmt _scan_thread finally
        self.scan_abort_flag.set()
        
    def _finish_repeat(self):
        self.progressbar.stop()
        self.set_button_states("stopped")
        
    # ─── Data & Plot Speichern ────────────────────────────────────────────────
    def save_data_npy(self):
        if self.last_wavelengths is None:
            messagebox.showwarning("No Data", "Run a sweep first!")
            return
        default = _OSA_make_filename(
            central_wl    = self.central_wl.get(),
            span          = self.span.get(),
            resolution    = self.resolution.get(),
            integration   = self.integration.get(),
            points        = self.points.get(),
            suffix        = "",
            ext           = ".npy"
        )
        fname = filedialog.asksaveasfilename(
            defaultextension=".npy",
            initialfile=default,
            filetypes=[("NumPy","*.npy")]
        )
        if not fname: return
        arr = np.vstack((self.last_wavelengths,
                         self.last_power_dbm,
                         self.last_power_lin)).T
        np.save(fname, arr)
        messagebox.showinfo("Saved", f"Data saved: {fname}")
    
    def save_linear_plot(self):
        default = _OSA_make_filename(
            self.central_wl.get(), self.span.get(), self.resolution.get(),
            self.integration.get(), self.points.get(),
            suffix="_lin", ext=".png"
        )
        fname = filedialog.asksaveasfilename(
            defaultextension=".png",
            initialfile=default,
            filetypes=[("PNG","*.png")]
        )
        if not fname: return
        self.fig_lin.savefig(fname, dpi=600, bbox_inches='tight')
        messagebox.showinfo("Saved", f"Linear plot saved: {fname}")
    
    def save_dbm_plot(self):
        default = _OSA_make_filename(
            self.central_wl.get(), self.span.get(), self.resolution.get(),
            self.integration.get(), self.points.get(),
            suffix="_dbm", ext=".png"
        )
        fname = filedialog.asksaveasfilename(
            defaultextension=".png",
            initialfile=default,
            filetypes=[("PNG","*.png")]
        )
        if not fname: return
        self.fig_dbm.savefig(fname, dpi=600, bbox_inches='tight')
        messagebox.showinfo("Saved", f"dBm plot saved: {fname}")

    # ─── Wavegen Control ─────────────────────────────────────────────────────
    def toggle_wavegen_connection(self):
        if getattr(self.wavegen_controller, "gen", None) is None:
            try:
                ip = self.wg_ip.get().strip()
                self.wavegen_controller.connect(ip)
                self.wg_connect_btn.config(text="Disconnect WG", bg="green")
            except Exception as e:
                messagebox.showerror("Wavegen Error", f"Connection failed: {e}")
        else:
            try:
                self.wavegen_controller.disconnect()
                self.wg_connect_btn.config(text="Connect WG", bg="red")
            except Exception as e:
                messagebox.showerror("Wavegen Error", f"Disconnection failed: {e}")

    def toggle_wavegen_panel(self):
        if self.wavegen_embed.winfo_ismapped():
            self.wavegen_embed.grid_remove()
        else:
            from gui.widgets.wavegen_gui import WavegenGUI
            if not hasattr(self, 'wavegen_gui'):
                self.wavegen_gui = WavegenGUI(self.wavegen_embed,
                                              controller=self.wavegen_controller)
                self.wavegen_gui.pack(fill="both", expand=True)
            self.wavegen_embed.grid()
            
    def _manual_freq_entry(self, _event=None):
        try:
            freq = float(self.curr_freq_var.get())
            self.wavegen_controller.write(f"SOUR1:FREQ {freq}")
            append_event(self.event_log, self.log_text, "SEND", f"SOUR1:FREQ {freq}")
            self.curr_freq_label.config(text=f"{freq:.3f} Hz")
        except Exception as e:
            append_event(self.event_log, self.log_text, "ERROR", f"Invalid manual freq entry: {e}")
            messagebox.showerror("Invalid Entry", "Please enter a valid frequency in Hz.")

    # ─── Peak-Handling ───────────────────────────────────────────────────────
    def _set_peak(self, val_dbm, wl_nm, freq_hz=0.0):
        text = f"Peak: {val_dbm:.2f} dBm @ {wl_nm:.3f} nm, {freq_hz:.3f} Hz"
        append_event(self.event_log, self.log_text, "PEAK", text)
        self.current_peak_var.set(text)
        if val_dbm > self._max_peak_dbm:
            self._max_peak_dbm = val_dbm
            self.max_peak_var.set(text)


    def _reset_max_peak(self):
        self._max_peak_dbm = -np.inf
        self.max_peak_var.set("Max Peak: -- dBm @ -- nm, -- Hz")

    # ─── Scan Frequency Adjustment ────────────────────────────────────────────
    def adjust_scan_freq(self, step):
        new_f = float(self.curr_freq_var.get()) + step
        self.curr_freq_var.set(new_f)
        append_event(self.event_log, self.log_text, "SEND", f"SOUR1:FREQ {new_f}")
        self.wavegen_controller.write(f"SOUR1:FREQ {new_f}")

    def scale_scan_freq(self, factor):
        new_f = float(self.curr_freq_var.get()) * factor
        self.curr_freq_var.set(new_f)
        append_event(self.event_log, self.log_text, "SEND", f"SOUR1:FREQ {new_f}")
        self.wavegen_controller.write(f"SOUR1:FREQ {new_f}")

    # ─── Log speichern ───────────────────────────────────────────────────────
    def _save_event_log(self):
        save_event_log(self.event_log)
        
    def safe_after(self, delay_ms, callback):
        try:
            if self.master.winfo_exists():
                self.master.after(delay_ms, callback)
        except RuntimeError:
            pass
        
# Logger so konfigurieren, dass er bei Programmstart die Datei leert
logging.basicConfig(
    filename='event_log.txt',
    filemode='w',                # 'w' leert die Datei beim Öffnen
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%H:%M:%S'
)

# Monkey-patch: jedes Mal, wenn append_event gerufen wird, loggen wir es
_orig_append_event = append_event
def append_event(ev_list, text_widget, ev_type, msg):
    _orig_append_event(ev_list, text_widget, ev_type, msg)
    logging.info(f"{ev_type}: {msg}")
    

    # ─── Aufräumen bei Schließen ─────────────────────────────────────────────
    def on_closing(self):
        self.scan_abort_flag.set()
        try:
            if self.controller.osa:
                append_event(self.event_log, self.log_text, "SEND", "SST")
                self.controller.osa.write("SST")
        except:
            pass
        self.master.destroy()

