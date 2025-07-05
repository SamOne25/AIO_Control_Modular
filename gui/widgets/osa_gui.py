from pyvisa.errors import VisaIOError
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading, time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import MaxNLocator, AutoMinorLocator
from scipy.signal import find_peaks
import tkinter.simpledialog as simpledialog
from controllers.osa_controller import OSAController

from utils.helpers import (
    CreateToolTip,
    integration_string_to_hz,
    save_scan_data, 
    save_linear_plot, 
    save_dbm_plot,
    append_event,
    save_event_log,
    save_with_metadata,
    get_lin_unit_and_data,
    meta_daten)

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
        

        self.central_wl    = tk.DoubleVar(value=1548.5)
        self.span          = tk.StringVar(value="2")
        self.resolution    = tk.StringVar(value="0.1")
        self.integration   = tk.StringVar(value="1kHz")
        self.points        = tk.StringVar(value="501")
        self.smooth_points = tk.StringVar(value="OFF")
        self.reference_lvl = tk.DoubleVar(value=0.0)
        self.level_offset  = tk.DoubleVar(value=0.0)
        self.voltage       = tk.StringVar(value="20.0")   # Default-Spannung
        self.fiberlen      = tk.StringVar(value="~25.0")   # Default-Faserlänge
        self.pulse_width   = tk.StringVar(value="100")    # Default 100 ns
        
        # Debug-Modus: alle Events sammeln
        self.debug_modus = tk.BooleanVar(value=False)
        self.event_log = []

        # Sweep-Kontrolle
        self.single_sweep_freq = None
        self.sweep_running  = False
        self.repeat_running = False
        self.repeat_abort     = threading.Event()
        self.scan_abort     = threading.Event()
        self.pause_event   = threading.Event()
        self.scan_running  = False    # Thread aktiv (auch wenn gerade pausiert)

        # Spec-Figure (gemeinsam für dBm und linear) + Scan-Figure
        self.fig_spec, self.ax_spec = plt.subplots(figsize=(6,4), dpi=150)
        self.fig_scan, self.ax_scan = plt.subplots(figsize=(6,4), dpi=150)
        
        # Merke dir die letzten Daten, damit Toggle re-plottet
        self.last_wavelengths = np.array([])
        self.last_power_dbm   = np.array([])
        self.last_power_lin   = np.array([])
        self.current_plot_scale = "dBm"

        # Peak-Anzeige
        self.current_peak_var = tk.StringVar(value="-- dBm @ -- nm, -- Hz")
        self._max_peak_dbm = 0
        self.max_peak_var  = tk.StringVar()
        self._reset_max_peak()

        # Scan-Kontrolle
        self.scan_running = False
        self.scan_mode = False
        
        
        self.scan_dtype = np.dtype([
            ("frequency", float),
            ("peak",      float),
            ("wavelength",float),
        ])
        self.scan_data = np.empty((0,), dtype=self.scan_dtype)
        # Für den Plot
        self._scan_freqs = []
        self._scan_peaks = []
        self._scan_wl = []
       
        
        #Peak finder
        self.min_peak_var     = tk.DoubleVar(value=-70.0)  # Mindestpegel in dBm
        self.min_distance_var = tk.IntVar(   value=1   )  # Mindestens so viele Messpunkte Abstand
        self.show_peaks_only  = tk.BooleanVar(value=False)
        self.peaks_idx        = []  # wird später von find_peaks befüllt
        self.min_peak_var.trace_add("write", lambda *args: self._on_peak_params_changed())
        self.min_distance_var.trace_add("write", lambda *args: self._on_peak_params_changed())
        
        
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
        self.debug_btn = tk.Button(top, text="Debug Modus: Off", width=15, command=self.toggle_debugmodus)
        self.debug_btn.grid(row=0, column=6, padx=(10,0))
               
        # Voltage-Feld
        tk.Label(top, text="Voltage [V]:") \
          .grid(row=0, column=7, sticky="e", padx=(20,2))
        tk.Entry(top, textvariable=self.voltage, width=8) \
          .grid(row=0, column=8, sticky="w")
        
        # Fiber Length-Feld
        tk.Label(top, text="Fiber Len [km]:") \
          .grid(row=0, column=9, sticky="e", padx=(20,2))
        tk.Entry(top, textvariable=self.fiberlen, width=8) \
          .grid(row=0, column=10, sticky="w")

        # Sweep Parameters
        param = tk.LabelFrame(main, text="Sweep Parameters", padx=8, pady=10)
        param.grid(row=1, column=0, sticky="nsew", pady=6)
        for c in range(2):
            param.columnconfigure(c*2, weight=0)
            param.columnconfigure(c*2+1, weight=1)

        specs = [
            ("Central WL [nm]:","entry", self.central_wl, 800, 1700),
            ("Span [nm]:","combo", self.span, self.controller.spans, None),
            ("Resolution [nm]:","combo", self.resolution, self.controller.resolutions, None),
            ("Integration:","combo", self.integration, self.controller.integrations, None),
            ("Sampling Points:","combo", self.points, self.controller.samp_points, None),
            ("Reference LvL [dBm]:","spin", self.reference_lvl, -90, 30),
            ("Level Offset [dB]:","spin", self.level_offset, -30, 30),
            ("Smooth:","combo", self.smooth_points, self.controller.smt_points, None),
        ]
        row = 0
        for idx, (txt, typ, var, opt1, opt2) in enumerate(specs):
            col = (idx % 2) * 2
            tk.Label(param, text=txt).grid(row=row, column=col, sticky="e", padx=4, pady=4)
            if typ == "entry":
                e = tk.Entry(param, textvariable=var, width=10)
                e.grid(row=row, column=col+1, sticky="w", padx=4, pady=4)
                CreateToolTip(e, f"Valid {opt1}–{opt2} nm")
                e.bind("<Return>",   lambda e, v=var: self.set_param("CNT", v.get()))
                e.bind("<FocusOut>", lambda e, v=var: self.set_param("CNT", v.get()))
            elif typ == "combo":
                # für Span erlauben wir auch eigene Eingabe
                state = "normal" if txt == "Span [nm]:" else "readonly"
                cb = ttk.Combobox(param, values=opt1, textvariable=var, width=10, state=state)
                cb.grid(row=row, column=col+1, sticky="w", padx=4, pady=4)
                cb.bind("<<ComboboxSelected>>",
                        lambda e, v=var, cmd=self.controller.cmd_map[txt]: self.set_param(cmd, v.get()))
                if txt == "Span [nm]:":
                    self.span_cb = cb
                    # bei Fokusverlust oder Enter den neuen Span-Wert setzen
                    self.span_cb.bind("<FocusOut>",
                        lambda e: self.set_param("SPN", self.span.get()))
                    self.span_cb.bind("<Return>",
                        lambda e: self.set_param("SPN", self.span.get()))
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
                                command=lambda v=var, cmd=self.controller.cmd_map[txt]: self.set_param(cmd, v.get()))
                sb.grid(row=row, column=col+1, sticky="w", padx=4, pady=4)
                sb.bind("<FocusOut>",
                    lambda e, v=var, cmd=self.controller.cmd_map[txt]: self.set_param(cmd, v.get()))
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
        for i,q in enumerate(("low","Med","High")):
            btn=ttk.Button(quality,text=q,
                           command=lambda q=q: self.apply_quality(q))
            btn.grid(row=0,column=i,padx=6,pady=2)
            self.quality_buttons.append(btn)
        row+=1

        # Sweep Buttons + Progress
        btns=tk.Frame(param)
        btns.grid(row=row,column=0,columnspan=4,pady=(8,4))
        self.single_btn=ttk.Button(btns,text="Single Sweep",command=self.single_sweep)
        self.single_btn.pack(side="left",padx=6)
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
        self.curr_freq_var   = tk.DoubleVar(value=0.0)
        self.curr_freq_entry = tk.Entry(self.scan_frame, textvariable=self.curr_freq_var, width=12)
        self.curr_freq_entry.grid(row=scan_row, column=1, columnspan=3, sticky="w", padx=4, pady=2)
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
        self.scan_btn = tk.Button(
            self.scan_frame,
            text="Run/Pause",
            bg="green",
            fg="white",
            command=self.toggle_scan_run_pause
        )
        self.scan_btn.grid(row=scan_row, column=0, padx=6, pady=4, sticky="w")
        
        self.stop_btn = tk.Button(
            self.scan_frame,
            text="Stop Scan",
            bg="red",
            fg="white",
            command=self.stop_scan    # stop_scan setzt scan_abort und ruft start_repeat_sweep()
        )
        self.stop_btn.grid(row=scan_row, column=1, padx=6, pady=4, sticky="w")
        scan_row += 1

        # Peak Displays
        tk.Label(self.scan_frame, text="Current Peak:", fg="darkgreen")\
            .grid(row=scan_row, column=0, sticky="e", padx=4, pady=2)
        tk.Label(self.scan_frame, textvariable=self.current_peak_var, fg="darkgreen")\
            .grid(row=scan_row, column=1, columnspan=3, sticky="w", padx=4, pady=2)
        scan_row += 1

        tk.Label(self.scan_frame, text="Max Peak:", fg="darkred")\
            .grid(row=scan_row, column=0, sticky="e", padx=4, pady=2)
        tk.Label(self.scan_frame, textvariable=self.max_peak_var, fg="darkred")\
            .grid(row=scan_row, column=1, columnspan=3, sticky="w", padx=4, pady=2)
        scan_row += 1

        # Reset Max
        tk.Button(self.scan_frame, text="Reset Max", width=10, command=self._reset_max_peak)\
            .grid(row=scan_row, column=0, padx=6, pady=(4,0), sticky="w")

        # ─── Save Frame (Data & Plots) ────────────────────────────────────────────
        save_frame = tk.LabelFrame(param, text="Save", padx=8, pady=6)
        save_frame.grid(row=row+1, column=0, columnspan=4, sticky="ew", pady=(10,0))
        ttk.Button(save_frame, text="Save Sweep (.npy/json)", command=self.save_sweep).grid(row=0, column=0, padx=6)
        ttk.Button(save_frame, text="Save Linear Plot", command=self.save_linear_plot).grid(row=0, column=1, padx=6)
        ttk.Button(save_frame, text="Save dBm Plot", command=self.save_dbm_plot).grid(row=0, column=2, padx=6)

        # Plots
        plots=tk.Frame(main)
        plots.grid(row=1,column=1,rowspan=2,sticky="nsew",padx=10)
        plots.columnconfigure(0,weight=1); plots.rowconfigure(0,weight=1)

        self.plot_tabs=ttk.Notebook(plots)
        self.plot_spec_tab=ttk.Frame(self.plot_tabs)
        
        #self.scan_tab=ttk.Frame(self.plot_tabs)   # zukünftiger Scan tab---------------------------
        self.plot_tabs.add(self.plot_spec_tab,text="Spec")
        #self.plot_tabs.add(self.scan_tab,text="Scan")
        
        # Canvas für SPEC - Plot
        self.plot_spec_tab.rowconfigure(0, weight=1)
        self.plot_spec_tab.columnconfigure(0, weight=1)
        
        self.canvas_spec = FigureCanvasTkAgg(self.fig_spec, master=self.plot_spec_tab)
        self.canvas_spec.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
                
        # Toggle-Button
        self.toggle_plot_btn = ttk.Button(
            self.plot_spec_tab,
            text="Linear",
            command=self._toggle_plot_scale
        )
        self.toggle_plot_btn.grid(row=1, column=0, sticky="ne", padx=10, pady=(0,10))
        #------------------
        
        #Canvas für Scan-Plot
        
        
# ─── Scan-Tab neu aufbauen ──────────────────────────────────────────────
        # Scan-Tab zum Notebook hinzufügen
        self.scan_tab = ttk.Frame(self.plot_tabs)
        self.plot_tabs.add(self.scan_tab, text="Scan")
        # Grid-Layout: Plot (row0), Filter+Tabelle (row1), Save-Buttons (row2)
        self.scan_tab.rowconfigure(0, weight=2)  # Plot
        self.scan_tab.rowconfigure(1, weight=1)  # Filter
        self.scan_tab.rowconfigure(2, weight=0)  # Tabelle
        self.scan_tab.rowconfigure(3, weight=1)  # Save-Buttons
        self.scan_tab.columnconfigure(0, weight=1)
        
        
        
        # 1) Plot
        self.canvas_scan = FigureCanvasTkAgg(self.fig_scan, master=self.scan_tab)
        self.canvas_scan.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=8, pady=4)
        
        # ─── Peak-Einstellungen & Export ─────────────────────────────────────────
        settings_frame = tk.Frame(self.scan_tab)
        settings_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0,4))
        
        # Min. Pegel Slider
        tk.Scale(
            settings_frame,
            variable=self.min_peak_var,
            from_=-120, to=0, resolution=0.5,
            orient="horizontal",
            label="Min. Pegel [dBm]",
            command=lambda v: self._on_peak_params_changed()
        ).pack(side="left", padx=4)
        
        tk.Scale(
            settings_frame,
            variable=self.min_distance_var,
            from_=1, to=20, resolution=1,
            orient="horizontal",
            label="Min. Abstand [Pkt]",
            command=lambda v: self._on_peak_params_changed()
        ).pack(side="left", padx=4)
        """
        # Mindest-Pegel
        tk.Label(settings_frame, text="Min. Pegel [dBm]:").pack(side="left")
        tk.Entry(settings_frame, textvariable=self.min_peak_var, width=6).pack(side="left", padx=(0,8))
        # Mindest-Abstand
        tk.Label(settings_frame, text="Min. Abstand [Pkt]:").pack(side="left")
        tk.Entry(settings_frame, textvariable=self.min_distance_var, width=4).pack(side="left", padx=(0,8))
        """
        # Umschalter Table->Peaks
        ttk.Checkbutton(
            settings_frame,
            text="Nur Peaks anzeigen",
            variable=self.show_peaks_only,
            command=self._refresh_scan_table
        ).pack(side="left", padx=(0,8))
        # Export-Button
        tk.Button(
            settings_frame,
            text="save peaks only",
            command=self._export_peaks_numpy
        ).pack(side="right")
        #Save Scan button
        tk.Button(
            settings_frame,
            text="Save Scan (.npz/json)",
            command=self.save_full_scan
        ).pack(side="right", padx=4)
        
        # 2a) Filter-Eingabe
        """
        filter_frame = tk.Frame(self.scan_tab)
        filter_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=(4,0))
        tk.Label(filter_frame, text="Filter:").pack(side="left")
        self.filter_var = tk.StringVar()
        filter_entry = tk.Entry(filter_frame, textvariable=self.filter_var)
        filter_entry.pack(side="left", fill="x", expand=True, padx=(4,0))
        save_frame = tk.Frame(self.scan_tab)
        save_frame.grid(row=3, column=0, sticky="e", padx=8, pady=4)
        tk.Button(save_frame, text="Save Scan", command=self._save_scan).pack(side="right", padx=4)
        filter_entry.bind("<KeyRelease>", self._filter_scan_table)
        	"""
        # 2b) Tabelle
        self.scan_table = ttk.Treeview(
            self.scan_tab,
            columns=("frequency", "peak", "wavelength"),
            show="headings",
        )
        self.scan_table.heading("frequency",  text="Freq (Hz)")
        self.scan_table.heading("peak",       text="Peak (dBm)")
        self.scan_table.heading("wavelength", text="WL (nm)")
        # Spaltenbreiten und Alignment nach Belieben:
        self.scan_table.column("frequency", anchor="e", width=80)
        self.scan_table.column("peak",      anchor="e", width=60)
        self.scan_table.column("wavelength",anchor="e", width=60)

        self.scan_table.grid(row=3, column=0, sticky="nsew", padx=8, pady=(32,4))

        # 3) Save-Buttons
        


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
            if not self.debug_modus.get():
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
        self.repeat_abort.set()
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
    def set_param(self, cmd, value):
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
        self.set_param("RES", res)
        self.set_param("VBW", vbw)
        self.set_param("MPT", mpt)
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
        else:
            # Beide gestoppt
            self.single_btn.config(text="Single Sweep", state="normal")
            self.repeat_btn.config(text="Repeat Sweep", state="normal")


    # ─── Single Sweep ──────────────────────────────────────────────────────────
    def single_sweep(self):
        # Beim Start eines Single-Sweeps die Wavegen-Frequenz abfragen und speichern
        try:
            resp = self.wavegen_controller.query("SOUR1:FREQ?")
            self.single_sweep_freq = float(resp)
        except Exception:
            self.single_sweep_freq = None

        # In der Statuszeile anzeigen, falls erfolgreich
        if self.single_sweep_freq is not None:
            self.status_var.set(f"Single Sweep @ {self.single_sweep_freq:.6f} Hz")

        # Wenn gerade ein Sweep läuft, abbrechen
        if self.sweep_running:
            self.repeat_abort.set()
            self.set_button_states("stopped")
            self.status_var.set("Sweep stopped.")
            return

        # Sweep-Flags setzen und Buttons umschalten
        self.sweep_running = True
        self.repeat_abort.clear()
        self.set_button_states("single")
        self.progressbar["value"] = 0

        # Single-Sweep im Hintergrund starten
        threading.Thread(target=self.single_sweep_thread, daemon=True).start()


    def single_sweep_thread(self):
        try:
            osa = self.controller.osa
            self.status_var.set("Sweep running…")
            self.progressbar["value"] = 10
    
            # 1) Gerät zurücksetzen und Sweep starten
            for cmd in ("*CLS", "SSI"):
                if self.repeat_abort.is_set():
                    self.master.after(0, lambda: self.status_var.set("Sweep aborted"))
                    return
                self.master.after(0, lambda: append_event(self.event_log, self.log_text, "SEND", cmd))
                osa.write(cmd)
    
            # 2) Auf Fertigmeldung warten
            self.master.after(0, lambda: append_event(self.event_log, self.log_text, "SEND", "*OPC?"))
            osa.query("*OPC?")
            self.master.after(0, lambda: append_event(self.event_log, self.log_text, "RESPONSE", "1"))
    
            if self.repeat_abort.is_set():
                self.master.after(0, lambda: self.status_var.set("Sweep aborted"))
                return
    
            # 3) Sweep-Daten abholen
            self.master.after(0, lambda: append_event(self.event_log, self.log_text, "SEND", "DCA?"))
            dca = osa.query("DCA?")
            self.master.after(0, lambda: append_event(self.event_log, self.log_text, "RESPONSE", dca.strip()))
            staw, stow, npts = map(float, dca.split(","))
            wl = np.linspace(staw, stow, int(npts))
    
            if self.repeat_abort.is_set():
                self.master.after(0, lambda: self.status_var.set("Sweep aborted"))
                return
    
            self.master.after(0, lambda: append_event(self.event_log, self.log_text, "SEND", "DMA?"))
            dbm = np.fromstring(osa.query("DMA?"), dtype=float, sep="\r\n")
            self.master.after(0, lambda: append_event(self.event_log, self.log_text, "RESPONSE", "<binary>"))
            lin = 10 ** (dbm / 10)
    
            # 4) Peak berechnen und anzeigen
            idx = int(np.nanargmax(dbm))
            val, wl0 = dbm[idx], wl[idx]
            try:
                self.master.after(0, lambda: append_event(self.event_log, self.log_text, "SEND", "SOUR1:FREQ?"))
                resp = self.wavegen_controller.query("SOUR1:FREQ?")
                self.master.after(0, lambda: append_event(self.event_log, self.log_text, "RESPONSE", resp.strip()))
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
            self.repeat_abort.set()
            self.set_button_states("stopped")
            self.status_var.set("Repeat stopped.")
            return
        self.repeat_abort.clear()
        self.repeat_running = True
        self.set_button_states("repeat")
        self.progressbar.config(mode="indeterminate")
        self.progressbar.start()
        threading.Thread(target=self.repeat_polling_loop, daemon=True).start()

    def repeat_polling_loop(self):
        osa = self.controller.osa
    
        # OSA in Repeat-Mode schalten
        self.master.after(0, lambda: append_event(self.event_log, self.log_text, "SEND", "*CLS"))
        osa.write("*CLS")
        self.master.after(0, lambda: append_event(self.event_log, self.log_text, "SEND", "SRT"))
        osa.write("SRT")
        self.master.after(0, lambda: self.status_var.set("Repeat (live polling)…"))
    
        while not self.repeat_abort.is_set():
            try:
                # Abbruchscheck
                if self.repeat_abort.is_set():
                    break
    
                # 1) Sweep-Beschreibung holen
                self.master.after(0, lambda: append_event(self.event_log, self.log_text, "SEND", "DCA?"))
                dca = osa.query("DCA?")
                self.master.after(0, lambda: append_event(self.event_log, self.log_text, "RESPONSE", dca.strip()))
                staw, stow, npts = map(float, dca.split(","))
                wl = np.linspace(staw, stow, int(npts))
    
                # 2) Power-Daten holen
                self.master.after(0, lambda: append_event(self.event_log, self.log_text, "SEND", "DMA?"))
                raw = osa.query("DMA?")
                self.master.after(0, lambda: append_event(self.event_log, self.log_text, "RESPONSE", "<binary>"))
                dbm = np.fromstring(raw, dtype=float, sep="\r\n")
                lin = 10 ** (dbm / 10)
    
                # 3) Wavegen-Frequenz (nur wenn verbunden)
                if getattr(self.wavegen_controller, "gen", None) is not None:
                    self.master.after(0, lambda: append_event(self.event_log, self.log_text, "SEND", "SOUR1:FREQ?"))
                    resp = self.wavegen_controller.query("SOUR1:FREQ?")
                    self.master.after(0, lambda: append_event(self.event_log, self.log_text, "RESPONSE", resp.strip()))
                    freq_text = f"{float(resp):.3f} Hz"
                else:
                    freq_text = "Wavegen DC"
    
            except VisaIOError as e:
                self.master.after(0, lambda e=e: self.error_var.set(f"I/O error during repeat: {e}"))
                break
            except Exception as e:
                self.master.after(0, lambda e=e: self.error_var.set(f"Repeat polling error: {e}"))
                break
    
            # 4) Peak berechnen und anzeigen (inkl. freq_text)
            idx = int(np.nanargmax(dbm))
            cur_val, cur_wl = dbm[idx], wl[idx]
            text = f"Peak: {cur_val:.2f} dBm @ {cur_wl:.3f} nm, {freq_text}"
            self.master.after(0, lambda: append_event(self.event_log, self.log_text, "PEAK", text))
            # aktuelle Peak-Anzeige
            self.master.after(0, lambda t=text: self.current_peak_var.set(t))
            # Max-Peak aktualisieren
            if cur_val > self._max_peak_dbm:
                self._max_peak_dbm = cur_val
                self.master.after(0, lambda t=text: self.max_peak_var.set(t))
    
            # 5) Plot updaten
            self.master.after(0, lambda w=wl, ln=lin, db=dbm: self.plot_results(w, ln, db, live=True))
    
            # kurze Pause
            time.sleep(0.3)
    
        # Repeat-Mode beenden
        self.master.after(0, lambda: append_event(self.event_log, self.log_text, "SEND", "SST"))
        try:
            osa.write("SST")
        except:
            pass
    
        self.master.after(0, lambda: self.status_var.set("Repeat stopped."))
        
        
    # ─── Scan Mode ────────────────────────────────────────────────────────────
    def toggle_scan_mode(self):
        if self.connection_state.get() != "connected" and not self.debug_modus.get():
            messagebox.showerror("Error", "Please connect OSA first!")
            return
    
        # Modus umschalten
        self.scan_mode = not self.scan_mode
        if self.scan_mode:
            # Enter Scan Mode → OSA in Repeat schalten + live polling starten
            append_event(self.event_log, self.log_text, "INFO", "Enter Scan Mode")
            self.scanmode_btn.config(text="Scan Mode ON", bg="yellow")
            self.single_btn.config(state="normal")
    
            # OSA in Repeat-Mode schalten
            append_event(self.event_log, self.log_text, "SEND", "SRT")
            if not self.debug_modus.get(): 
                self.controller.osa.write("SRT")
    
            # Mit Wavegen verbinden, falls nötig
            if getattr(self.wavegen_controller, "gen", None) is None:
                try:
                    ip = self.wg_ip.get().strip()
                    self.wavegen_controller.connect(ip)
                    self.wg_connect_btn.config(text="Disconnect WG", bg="green")
                except Exception as e:
                    messagebox.showerror("Wavegen Error", f"Connection failed: {e}")
                    # Modus wieder ausschalten
                    if not self.debug_modus.get():
                        self.scan_mode = False
                        self.scanmode_btn.config(text="Scan Mode OFF", bg="lightgray")
                        self.single_btn.config(state="normal")
                        self.repeat_btn.config(state="normal")
                        return
    
            # Aktuelle Frequenz abfragen (mit Logging)
            append_event(self.event_log, self.log_text, "SEND", "SOUR1:FREQ?")
            try:
                resp = self.wavegen_controller.query("SOUR1:FREQ?")
                append_event(self.event_log, self.log_text, "RESPONSE", resp.strip())
                f0 = round(float(resp), 3)
            except Exception as e:
                append_event(self.event_log, self.log_text, "ERROR", f"Freq query failed: {e}")
                f0 = 0.0
    
            # In das Feld eintragen
            self.curr_freq_var.set(f0)
    
            # Scan-Felder vorbelegen
            self.scan_start.delete(0, tk.END)
            self.scan_start.insert(0, f"{f0-1:.3f}")
            self.scan_end.delete(0, tk.END)
            self.scan_end.insert(0, f"{f0+1:.3f}")
    
            # Live-Polling starten
            self.repeat_running = True
            self.repeat_abort.clear()
            threading.Thread(target=self.repeat_polling_loop, daemon=True).start()
    
            # Scan-Frame anzeigen
            self.scan_frame.grid()
    
        else:
            # Exit Scan Mode → Live-Polling stoppen
            append_event(self.event_log, self.log_text, "INFO", "Exit Scan Mode")
            self.scanmode_btn.config(text="Scan Mode OFF", bg="lightgray")
            self.scan_frame.grid_remove()
    
            # Live-Polling abbrechen
            self.repeat_abort.set()
            self.repeat_running = False
    
            # Buttons wieder aktivieren
            self.single_btn.config(state="normal")

    def toggle_scan_run_pause(self):
        # falls noch nie gestartet oder nach Stop: neu starten
        if not self.scan_running and not self.pause_event.is_set():
            self.pause_event.clear()
            self.scan_abort.clear()
            self.scan_running = True
            self.scan_btn.config(text="Run/Pause", bg="green", fg="white")
            threading.Thread(target=self._scan_thread, daemon=True).start()
            return
    
        # wenn gerade läuft → Pause
        if self.scan_running and not self.pause_event.is_set():
            self.pause_event.set()
            self.scan_btn.config(text="Run/Paused", bg="yellow", fg="black")
            return
    
        # wenn pausiert → Resume
        if self.scan_running and self.pause_event.is_set():
            self.pause_event.clear()
            self.scan_btn.config(text="Run/Pause", bg="green", fg="white")
            return

    # ─── Scan mit Wavegen ─────────────────────────────────────────────────────
    def start_scan(self):
        append_event(self.event_log, self.log_text, "Button", "Start Scan")
        if not self.scan_mode:
            messagebox.showerror("Error", "Enable Scan Mode first!")
            return

        # Live-Polling unterbrechen
        self.repeat_abort.set()
        self.repeat_running = False
        self.master.after(0, lambda: self.status_var.set("Scan started"))

        # Jetzt pro Frequenz einen Single Sweep
        try:
            self._scan_f0 = float(self.scan_start.get())
            self._scan_f1 = float(self.scan_end.get())
            self._scan_df = float(self.scan_step.get())
        except ValueError:
            messagebox.showerror("Scan error", "Invalid frequency parameters")
            return
        
        # Scan-Flags initialisieren
        self.scan_running = True
        self.scan_abort.clear()
        time.sleep(0.5)
        threading.Thread(target=self._scan_thread, daemon=True).start()

    def _scan_thread(self):
        self.master.after(0, lambda:append_event(self.event_log, self.log_text, "INFO", "Scan_thread started"))
        osa = self.controller.osa
        f = self._scan_f0
        df = self._scan_df
        while not self.scan_abort.is_set() and f <= self._scan_f1:
            # --- hier warten, solange wir im Pausen-Modus sind ---
            while self.pause_event.is_set() and not self.scan_abort.is_set():
                time.sleep(0.1)
            self.master.after(0, lambda: append_event(self.event_log, self.log_text, "SEND", f"SOUR1:FREQ {f}"))
            try:
                self.wavegen_controller.write(f"SOUR1:FREQ {f}")
                time.sleep(0.1)
            except:
                pass
            self.master.after(0, lambda v=f: self.curr_freq_var.set(round(v,3)))

            self.master.after(0, lambda: append_event(self.event_log, self.log_text, "SEND", "*CLS"))
            osa.write("*CLS")
            self.master.after(0, lambda: append_event(self.event_log, self.log_text, "SEND", "SSI"))
            osa.write("SSI")
            try:
                osa.query("*OPC?")
            except:
                pass

            try:
                self.master.after(0, lambda: append_event(self.event_log, self.log_text, "SEND", "DCA?"))
                dca = osa.query("DCA?")
                self.master.after(0, lambda: append_event(self.event_log, self.log_text, "RESPONSE", dca.strip()))
                staw, stow, npts = map(float, dca.split(","))
                wl = np.linspace(staw, stow, int(npts))
                self.master.after(0, lambda: append_event(self.event_log, self.log_text, "SEND", "DMA?"))
                dbm = np.fromstring(osa.query("DMA?"), dtype=float, sep="\r\n")
                self.master.after(0, lambda: append_event(self.event_log, self.log_text, "RESPONSE", "<binary>"))
                lin = 10 ** (dbm / 10)
            except Exception as e:
                self.master.after(0, lambda e=e: self.error_var.set(f"Data read error: {e}"))
                f += df
                continue

            idx = int(np.nanargmax(dbm))
            val, wl0 = dbm[idx], wl[idx]
            self.master.after(0, lambda v=val, w=wl0, f=f: self._set_peak(v, w, f))
            self.master.after(0, lambda w=wl, ln=lin, db=dbm: self.plot_results(w, ln, db, live=True))
            self._scan_freqs.append(f)
            self._scan_peaks.append(val)
            self._scan_wl.append(wl0)
            self.master.after(0, lambda f=f, p=val, w=wl0: self.scan_table.insert("", "end",
                  values=(f"{f:.3f}", f"{p:.2f}", f"{w:.3f}")))
            self.master.after(0, self.update_scan_plot)
            f += df

        self.scan_running = False
        self.master.after(0, self.start_repeat_sweep)
        
        
    # ─── Scan stoppen und Repeat zurück ───────────────────────────────────────
    def stop_scan(self):
        # Scan-Thread abbrechen
        self.scan_abort.set()
        self.scan_running = False
        # danach wieder in den Repeat-Modus gehen
        self.start_repeat_sweep()

    # ─── Plot-Update ─────────────────────────────────────────────────────────
    def plot_results(self, wavelengths, data_lin, data_dbm, live=False):
        self.master.after(0, lambda: append_event(self.event_log, self.log_text, "INFO", "called plot_results "))
        max_lin = np.nanmax(data_lin) if len(data_lin) else 1
        if max_lin < 1e-6:
            unit, factor = "pW", 1e9
        elif max_lin < 1e-3:
            unit, factor = "nW", 1e6
        elif max_lin < 1:
            unit, factor = "µW", 1e3
        else:
            unit, factor = "mW", 1
        scaled_lin = data_lin * factor
        txt = " (Live)" if live else ""

        # 0) Daten sichern für plot wechsel button
        self.last_wavelengths = wavelengths
        self.last_power_dbm   = data_dbm
        self.last_power_lin   = scaled_lin
        
        self.ax_spec.clear()
        if self.current_plot_scale == "linear":
            self.ax_spec.plot(wavelengths, scaled_lin)  
            self.ax_spec.set_title(f"OSA Linear Scale{txt}")
            self.ax_spec.set_ylabel(f"Power ({unit})")
        else:
            self.ax_spec.plot(wavelengths, data_dbm)
            self.ax_spec.set_title(f"OSA dBm Scale{' (Live)' if live else ''}")
            self.ax_spec.set_ylabel("Power (dBm)")

        # X-Achse in beiden Fällen
        self.ax_spec.set_xlabel("Wavelength (nm)")
        self.ax_spec.xaxis.set_major_locator(MaxNLocator(5))
        self.ax_spec.xaxis.set_minor_locator(AutoMinorLocator(2))
        self.ax_spec.grid(which='major', axis='x', linestyle='-')
        self.ax_spec.grid(which='minor', axis='x', linestyle=':', alpha=0.7)

        self.fig_spec.tight_layout()
        self.canvas_spec.draw()
        
    def _toggle_plot_scale(self):
        if self.current_plot_scale == "dBm":
            # auf Linear umschalten
            self.current_plot_scale = "linear"
            self.toggle_plot_btn.config(text="⇐ dBm")
            append_event(self.event_log, self.log_text, "Button", "changed Plot to linear")
            # Notebook auf den Linear-Tab switchen
            #self.notebook.select(self.linear_tab)
            # Linear-Plot aktualisieren
            self.plot_results(self.last_wavelengths, self.last_power_lin, self.last_power_dbm)
            
        else:
            # zurück auf dBm
            self.current_plot_scale = "dBm"
            self.toggle_plot_btn.config(text="⇒ Linear")
            append_event(self.event_log, self.log_text, "Button", "changed Plot to dBm")
            #self.notebook.select(self.plot_spec_tab)
            self.plot_results(self.last_wavelengths, self.last_power_lin, self.last_power_dbm)
            
    def update_scan_plot(self):
        # 1) Achse leeren
        self.ax_scan.clear()
    
        # 2) Scan-Limits lesen und als X-Achse setzen
        try:
            f0 = float(self.scan_start.get())
            f1 = float(self.scan_end.get())
            self.ax_scan.set_xlim(f0, f1)
        except ValueError:
            # falls ungültig, bleiben die Limits automatisch
            pass
    
        # 3) Daten plotten
        self.ax_scan.plot(self._scan_freqs, self._scan_peaks, linestyle='--', marker='o')
    
        # 4) Peaks nach Slider-Werten markieren
        height = self.min_peak_var.get()
        dist   = self.min_distance_var.get()
        peaks_idx, _ = find_peaks(
            self._scan_peaks,
            height=height,
            distance=dist
        )
        for i in peaks_idx:
            f, p, wl = self._scan_freqs[i], self._scan_peaks[i], self._scan_wl[i]
            self.ax_scan.plot(f, p, 'ro')
            self.ax_scan.text(f, p+0.5, f"{wl:.2f} nm",
                              ha='center', va='bottom', fontsize=6)
    
        # 5) Achsenbeschriftungen und Grid
        self.ax_scan.set_xlabel("Frequenz (Hz)")
        self.ax_scan.set_ylabel("Peak (dBm)")
        self.ax_scan.grid(True)
    
        # 6) zeichnen
        self.fig_scan.tight_layout()
        self.canvas_scan.draw()

    def _filter_scan_table(self, event=None):
        """Filtert die Einträge in self.scan_table nach filter_var."""
        text = self.filter_var.get().lower()
        # Lösche alles
        for row in self.scan_table.get_children():
            self.scan_table.delete(row)
        # Füge nur passende Einträge wieder ein
        for f, p in zip(self._scan_freqs, self._scan_peaks):
            if text in f"{f:.3f}".lower() or text in f"{p:.2f}".lower():
                self.scan_table.insert("", "end", values=(f"{f:.3f}", f"{p:.2f}"))
                
    def _detect_peaks(self):
        """Füllt self.peaks_idx mit den Indizes der Detektierten Peaks."""
        y = np.array(self._scan_peaks)
        height = self.min_peak_var.get()
        dist   = self.min_distance_var.get()
        self.peaks_idx, _ = find_peaks(y, height=height, distance=dist)
    
    def _refresh_scan_table(self):
        """Füllt die Tabelle je nach show_peaks_only mit allen oder nur mit Peak-Einträgen."""
        # 1) zunächst Peaks neu detektieren
        self._detect_peaks()
    
        # 2) Tabelle löschen
        for iid in self.scan_table.get_children():
            self.scan_table.delete(iid)
    
        # 3) Daten einfügen
        if self.show_peaks_only.get():
            # nur die erkannten Peaks
            for i in self.peaks_idx:
                f  = self._scan_freqs[i]
                p  = self._scan_peaks[i]
                wl = self._scan_wl[i]
                self.scan_table.insert("", "end", values=(
                    f"{f:.3f}", f"{p:.2f}", f"{wl:.3f}"
                ))
        else:
            # alle Messpunkte
            for f, p, wl in zip(self._scan_freqs, self._scan_peaks, self._scan_wl):
                self.scan_table.insert("", "end", values=(
                    f"{f:.3f}", f"{p:.2f}", f"{wl:.3f}"
                ))
                
    def _on_peak_params_changed(self, _=None):
        # hier kommt deine Logik: Tabelle aktualisieren, Plot neuzeichnen …
        self._refresh_scan_table()
        self.update_scan_plot()

    def _export_peaks_numpy(self):
        """Schreibt das Peak-Array [freq, dbm, wl] als .npy Datei."""
        self._detect_peaks()
        # Array zusammenbauen
        freqs = np.array(self._scan_freqs)[self.peaks_idx]
        pows  = np.array(self._scan_peaks)[self.peaks_idx]
        wls   = np.array(self._scan_wl)[self.peaks_idx]
        arr   = np.column_stack((freqs, pows, wls))
        # Speichern
        fn = filedialog.asksaveasfilename(
            defaultextension=".npy",
            filetypes=[("NumPy array","*.npy")],
            title="Peak-Array speichern"
        )
        if fn:
            np.save(fn, arr)
            messagebox.showinfo("Export", f"Peaks gespeichert in:\n{fn}")


    def _save_scan(self):
        """Speichert die NumPy-Daten und den Scan-Plot als PNG."""
        # 1) Daten speichern
        fn_data = filedialog.asksaveasfilename(
            defaultextension=".npy",
            filetypes=[("NumPy array", "*.npy")],
            title="Save scan data as .npy"
        )
        if fn_data:
            arr = np.column_stack((self._scan_freqs, self._scan_peaks,self._scan_wl,))
            np.save(fn_data, arr)
        # 2) Plot speichern
        fn_plot = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG image", "*.png")],
            title="Save scan plot as .png"
        )
        if fn_plot:
            self.fig_scan.savefig(fn_plot, dpi=300, bbox_inches="tight")


    # ─── Wavegen Control ─────────────────────────────────────────────────────
    def toggle_wavegen_connection(self):
        if getattr(self.wavegen_controller, "gen", None) is None:
            try:
                ip = self.wg_ip.get().strip()
                self.wavegen_controller.connect(ip)
                self.wg_connect_btn.config(text="Disconnect WG", bg="green", fg="white")
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

    # ─── Peak-Handling ───────────────────────────────────────────────────────
    def _set_peak(self, val_dbm, wl_nm, freq_hz=0.0):
        text = f"Peak: {val_dbm:.2f} dBm @ {wl_nm:.3f} nm, {freq_hz:.3f} Hz" 
        self.master.after(0, lambda: append_event(self.event_log, self.log_text, "PEAK", text)) ##??? MIT AFTER?
        self.master.after(0, lambda: self.current_peak_var.set(text)) ##??? MIT AFTER?
        if val_dbm > self._max_peak_dbm:
            self._max_peak_dbm = val_dbm
            self.master.after(0, lambda: self.max_peak_var.set(text)) ##??? MIT AFTER?

    def _reset_max_peak(self):
        self._max_peak_dbm = -np.inf
        self.max_peak_var.set("-- dBm @ -- nm, -- Hz")

    # ─── Scan Frequency Adjustment ────────────────────────────────────────────
    def adjust_scan_freq(self, step):
        new_f = self.curr_freq_var.get() + step
        self.curr_freq_var.set(new_f)
        append_event(self.event_log, self.log_text, "SEND", f"SOUR1:FREQ {new_f}")
        self.wavegen_controller.write(f"SOUR1:FREQ {new_f}")

    def scale_scan_freq(self, factor):
        new_f = self.curr_freq_var.get() * factor
        self.curr_freq_var.set(new_f)
        append_event(self.event_log, self.log_text, "SEND", f"SOUR1:FREQ {new_f}")
        self.wavegen_controller.write(f"SOUR1:FREQ {new_f}")

    # ─── Log speichern ───────────────────────────────────────────────────────
    def _save_event_log(self):
        save_event_log(self.event_log)
        
    def toggle_debugmodus(self):
        enabled = self.debug_modus.get()
        self.debug_modus.set(not enabled)
        # Button-Beschriftung & Farbe anpassen
        if not enabled:
            self.debug_btn.config(text="Debugmodus ON",  bg="yellow", fg="black")
        else:
            self.debug_btn.config(text="Debugmodus OFF", bg="SystemButtonFace",       fg="black")

    # ─── Wrapper für Daten speichern ─────────────────────────────────────────

    def save_sweep(self):
        # 1) Daten vorhanden?
        if self.last_wavelengths.size == 0:
            messagebox.showwarning("No Data", "Run a sweep first!")
            return

        # 2) Single-Sweep-Freq holen (oder per Dialog nachfragen)
        try:
            resp = self.wavegen_controller.query("SOUR1:FREQ?")
            freq = f"{float(resp):.6f}"
        except Exception:
            freq_val = simpledialog.askfloat(
                "Frequency Required",
                "Could not read wavegen frequency.\nPlease enter frequency in Hz:",
                minvalue=0.0
            )
            if freq_val is None:
                messagebox.showwarning("No Frequency", "Frequency is required for single sweep.")
                return
            freq = f"{freq_val:.6f}"

        # 3) Pulsbreite vom Wavegen holen (in s → umrechnen in ns)
        try:
            resp_pw = self.wavegen_controller.query("SOUR1:PULS:WIDT?")
            pw_s = float(resp_pw)
            pw_ns = pw_s * 1e9
            pulse_width = f"{pw_ns:.3f}"
        except Exception:
            pw_val = simpledialog.askfloat(
                "Pulse width required",
                "Could not read pulse width from wavegen.\nPlease enter pulse width in ns:",
                minvalue=0.0
            )
            if pw_val is None:
                messagebox.showwarning("No Pulsewidth", "Pulse width is required for single sweep.")
                return
            pulse_width = f"{pw_val:.3f}"

        # 4) Aus dBm → mW und dann in hübsche Einheit skalieren
        raw_lin = 10 ** (self.last_power_dbm / 10)  # jetzt in mW
        lin_unit, lin_data = get_lin_unit_and_data(raw_lin)

        # 5) Array für’s Speichern
        arr = np.vstack([
            self.last_wavelengths,
            self.last_power_dbm,
            lin_data
        ]).T

        # 6) Spalten- und Einheiten-Listen
        cols  = ["wavelength", "power_dbm", "power"]
        units = ["nm", "dBm", lin_unit]

        # 7) Metadaten bauen
        meta = meta_daten(
            resolution    = self.resolution.get(),
            integration   = self.integration.get(),
            span          = self.span.get(),
            frequency     = freq,
            points        = self.points.get(),
            offset        = self.level_offset.get(),
            reference_lvl = self.reference_lvl.get(),
            central_wl    = self.central_wl.get(),
            pulse_width   = pulse_width,
            voltage       = self.voltage.get(),
            fiberlen      = self.fiberlen.get(),
            scan_start    = "-",
            scan_stop     = "-",
            scan_step     = "-",
            instrument    = "Anritsu MS9740A",
            notes         = "Single Sweep"
        )
        # Einheit für Parameter überschreiben
        meta["param_units"]["power"] = lin_unit
        meta["param_units"]["pulse_width"] = "ns"

        # 8) Speichern
        save_with_metadata(
            arr         = arr,
            columns     = cols,
            units       = units,
            metadata    = meta,
            subfolder   = "Spektrum",
            fmt         = "npy",
            json_notes  = "Sweep Data"
        )


    def save_full_scan(self):
        # Full-Scan: Metadaten frequency = "-", Scan-Parameter bleiben echt
        if not self._scan_freqs:
            messagebox.showwarning("No Scan","First do a scan!")
            return

        arr = np.column_stack((self._scan_freqs,
                               self._scan_peaks,
                               self._scan_wl))
        cols  = ["frequency","peak","wavelength"]
        units = ["Hz","dBm","nm"]
        meta = meta_daten(
            resolution    = self.resolution.get(),
            integration   = self.integration.get(),
            span          = self.span.get(),
            frequency     = "-",                         # beim Scan keine Single-Freq
            points        = self.points.get(),
            offset        = self.level_offset.get(),
            reference_lvl = self.reference_lvl.get(),
            central_wl    = self.central_wl.get(),
            voltage       = self.voltage.get(),
            fiberlen      = self.fiberlen.get(),
            scan_start    = self.scan_start.get(),
            scan_stop     = self.scan_end.get(),
            scan_step     = self.scan_step.get(),
            instrument    = "Anritsu MS9740A",
            notes         = f"Full scan {self.scan_start.get()}–{self.scan_end.get()} Hz"
        )
        save_with_metadata(
            arr=arr,
            columns=cols,
            units=units,
            metadata=meta,
            subfolder="FreqScan",
            fmt="npz",
            json_notes="Full Frequency Scan"
        )


    # ─── Wrapper für linearen Plot speichern ─────────────────────────────────
    def save_linear_plot(self):
        save_linear_plot(
            self.fig_spec,
            resolution    = self.resolution.get(),
            integration   = self.integration.get(),
            span          = self.span.get(),
            frequency     = self.curr_freq_var.get(),
            points        = self.points.get(),
            offset        = self.level_offset.get(),
            reference_lvl = self.reference_lvl.get(),
            central_wl    = self.central_wl.get(),
            notes         = "Linear OSA Plot"
        )

    # ─── Wrapper für dBm-Plot speichern ────────────────────────────────────────
    def save_dbm_plot(self):
        save_dbm_plot(
            self.fig_spec,
            resolution    = self.resolution.get(),
            integration   = self.integration.get(),
            span          = self.span.get(),
            frequency     = self.curr_freq_var.get(),
            points        = self.points.get(),
            offset        = self.level_offset.get(),
            reference_lvl = self.reference_lvl.get(),
            central_wl    = self.central_wl.get(),
            notes         = "dBm OSA Plot"
        )

    # ─── Aufräumen bei Schließen ─────────────────────────────────────────────
    def on_closing(self):
        self.repeat_abort.set()
        try:
            if self.controller.osa:
                append_event(self.event_log, self.log_text, "SEND", "SST")
                self.controller.osa.write("SST")
        except:
            pass
        self.master.destroy()

