import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import MaxNLocator, AutoMinorLocator

from controllers.osa_controller import OSAController
from utils.helpers import CreateToolTip, integration_string_to_hz, SMT_OPTIONS

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

        # Sweep-Kontrolle
        self.sweep_running  = False
        self.repeat_running = False
        self.abort_flag     = threading.Event()

        # Matplotlib-Figures
        self.fig_dbm, self.ax_dbm = plt.subplots(figsize=(6,4), dpi=150)
        self.fig_lin, self.ax_lin = plt.subplots(figsize=(6,4), dpi=150)
        self.last_wavelengths = None
        self.last_power_dbm   = None
        self.last_power_lin   = None

        # Peak-Anzeige unter der Progressbar
        self.current_peak_var = tk.StringVar(value="Peak: -- dBm @ -- nm, -- Hz")

        # Scan-Kontrolle
        self.scan_running = False

        # GUI aufbauen
        self.build_gui()
        self.update_conn_btn()

    def build_gui(self):
        main = tk.Frame(self)
        main.pack(fill="both", expand=True, padx=12, pady=8)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=3)
        main.rowconfigure(1, weight=1)

        # ─── Top bar ───
        top = tk.Frame(main)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0,10))
        tk.Label(top, text="OSA IP:").grid(row=0, column=0, sticky="e")
        tk.Entry(top, textvariable=self.osa_ip, width=16).grid(row=0, column=1, sticky="w")
        self.connect_btn = tk.Button(top, text="Connect", width=12, command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=2, padx=(10,0))
        ttk.Button(top, text="Wavegen ein-/ausblenden", command=self.toggle_wavegen_panel)\
            .grid(row=0, column=3, padx=(10,0))

        # ─── Sweep Parameters (2×4) ───
        param = tk.LabelFrame(main, text="Sweep Parameters", padx=8, pady=10)
        param.grid(row=1, column=0, sticky="nsew", pady=6)
        for c in range(2):
            param.columnconfigure(c*2,   weight=0)
            param.columnconfigure(c*2+1, weight=1)

        cmd_map = {
            "Span [nm]:":           "SPN",
            "Resolution [nm]:":     "RES",
            "Integration:":         "VBW",
            "Sampling Points:":     "MPT",
            "Smooth:":              "SMT",
        }
        spin_map = {
            "Reference LvL [dBm]:": "RLV",
            "Level Offset [dB]:":   "LOFS",
        }
        specs = [
            ("Central WL [nm]:",     "entry", self.central_wl,      800,        1700),
            ("Span [nm]:",           "combo", self.span,            self.spans, None),
            ("Resolution [nm]:",     "combo", self.resolution,      self.resolutions, None),
            ("Integration:",         "combo", self.integration,     self.integrations, None),
            ("Sampling Points:",     "combo", self.points,          self.samp_points, None),
            ("Reference LvL [dBm]:", "spin",  self.reference_lvl,     -90,         30),
            ("Level Offset [dB]:",   "spin",  self.level_offset,     -30,         30),
            ("Smooth:",              "combo", self.smooth_points,   SMT_OPTIONS, None),
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
                cb = ttk.Combobox(param, values=opt1, textvariable=var, width=10, state="readonly")
                cb.grid(row=row, column=col+1, sticky="w", padx=4, pady=4)
                cb.bind("<<ComboboxSelected>>",
                        lambda e, v=var, cmd=cmd_map[txt]: self.set_single_param(cmd, v.get()))
            else:  # spin
                sb = tk.Spinbox(param, from_=opt1, to=opt2, increment=1.0,
                                textvariable=var, width=10,
                                command=lambda v=var, cmd=spin_map[txt]: self.set_single_param(cmd, v.get()))
                sb.grid(row=row, column=col+1, sticky="w", padx=4, pady=4)
                sb.bind("<FocusOut>", lambda e, v=var, cmd=spin_map[txt]: self.set_single_param(cmd, v.get()))
            if idx % 2 == 1:
                row += 1

        # ─── Quality buttons ───
        quality = tk.LabelFrame(param, text="Quality", padx=4, pady=4)
        quality.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(10,0))
        for i, q in enumerate(("low","med","high")):
            ttk.Button(quality, text=q.capitalize(), command=lambda q=q: self.apply_quality(q))\
                .grid(row=0, column=i, padx=6, pady=2)
        row += 1

        # ─── Sweep buttons + progress ───
        btns = tk.Frame(param)
        btns.grid(row=row, column=0, columnspan=4, pady=(8,4))
        self.single_btn = ttk.Button(btns, text="Single Sweep", command=self.start_single_sweep)
        self.repeat_btn = ttk.Button(btns, text="Repeat Sweep", command=self.start_repeat_sweep)
        self.single_btn.pack(side="left", padx=6)
        self.repeat_btn.pack(side="left", padx=6)
        row += 1

        self.progressbar = ttk.Progressbar(param, mode="determinate", length=200)
        self.progressbar.grid(row=row, column=0, columnspan=4, pady=(4,0))
        row += 1

        # ─── Peak display ───
        tk.Label(param, textvariable=self.current_peak_var, fg="darkgreen")\
            .grid(row=row, column=0, columnspan=4, pady=(4,0))
        row += 1

        # ─── Status / Error ───
        tk.Label(param, textvariable=self.status_var, fg="blue")\
            .grid(row=row, column=0, columnspan=4)
        row += 1
        tk.Label(param, textvariable=self.error_var, fg="red")\
            .grid(row=row, column=0, columnspan=4)
        row += 1

        # ─── Scan Controls ───
        scan = tk.LabelFrame(param, text="Scan via Wavegen", padx=6, pady=6)
        scan.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(10,0))
        tk.Label(scan, text="Start (Hz):").grid(row=0, column=0, padx=4, pady=2, sticky="e")
        self.scan_start = tk.Entry(scan, width=10); self.scan_start.insert(0,"4000")
        self.scan_start.grid(row=0, column=1, padx=4, pady=2)
        tk.Label(scan, text="End (Hz):").grid(row=0, column=2, padx=4, pady=2, sticky="e")
        self.scan_end = tk.Entry(scan, width=10);   self.scan_end.insert(0,"5000")
        self.scan_end.grid(row=0, column=3, padx=4, pady=2)
        tk.Label(scan, text="Step (Hz):").grid(row=1, column=0, padx=4, pady=2, sticky="e")
        self.scan_step = tk.Entry(scan, width=10); self.scan_step.insert(0,"100")
        self.scan_step.grid(row=1, column=1, padx=4, pady=2)
        tk.Label(scan, text="Pause (s):").grid(row=1, column=2, padx=4, pady=2, sticky="e")
        self.scan_pause = tk.Entry(scan, width=10); self.scan_pause.insert(0,"0.5")
        self.scan_pause.grid(row=1, column=3, padx=4, pady=2)
        tk.Button(scan, text="Start Scan", command=self.start_scan).grid(row=2, column=0, padx=6, pady=4)
        tk.Button(scan, text="Stop Scan",  command=self.stop_scan).grid(row=2, column=1, padx=6, pady=4)
        row += 1

        # ─── Save Frame ───
        save_frame = tk.LabelFrame(param, text="Save", padx=8, pady=6)
        save_frame.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(10,0))
        ttk.Button(save_frame, text="Save Data (.npy)",   command=self.save_data_npy)\
            .grid(row=0, column=0, padx=6)
        ttk.Button(save_frame, text="Save Linear Plot",  command=self.save_linear_plot)\
            .grid(row=0, column=1, padx=6)
        ttk.Button(save_frame, text="Save dBm Plot",     command=self.save_dbm_plot)\
            .grid(row=0, column=2, padx=6)
        row += 1

        # ─── Wavegen embed frame ───
        self.wavegen_embed = tk.LabelFrame(param, text="Wavegen Control", padx=5, pady=5)
        self.wavegen_embed.grid(row=row, column=0, columnspan=4, sticky="nsew", pady=(10,0))
        self.wavegen_embed.grid_remove()
        param.rowconfigure(row, weight=1)
        row += 1

        # ─── Plots ───
        plots = tk.Frame(main)
        plots.grid(row=1, column=1, rowspan=2, sticky="nsew", padx=10)
        plots.columnconfigure(0, weight=1)
        plots.rowconfigure(0, weight=1)

        self.plot_tabs = ttk.Notebook(plots)
        self.plot_tabs.grid(row=0, column=0, sticky="nsew", pady=6)

        self.dbm_tab = ttk.Frame(self.plot_tabs)
        self.plot_tabs.add(self.dbm_tab, text="dBm Scale")
        self.canvas_dbm = FigureCanvasTkAgg(self.fig_dbm, self.dbm_tab)
        self.canvas_dbm.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)

        self.lin_tab = ttk.Frame(self.plot_tabs)
        self.plot_tabs.add(self.lin_tab, text="Linear Scale")
        self.canvas_lin = FigureCanvasTkAgg(self.fig_lin, self.lin_tab)
        self.canvas_lin.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)

    def update_conn_btn(self):
        if self.connection_state.get()=="connected":
            self.connect_btn.config(text="Disconnect", bg="green", fg="white")
        else:
            self.connect_btn.config(text="Connect",    bg="red",   fg="white")

    def toggle_connection(self):
        if self.connection_state.get()=="disconnected":
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
            self.controller.osa.write("LOG 5")
            self.status_var.set(f"Connected: {idn.strip()}")
            self.connection_state.set("connected")
            self.read_all_params()
        except Exception as e:
            messagebox.showerror("OSA Error", f"Connection failed: {e}")
            self.connection_state.set("disconnected")
            self.controller.osa = None

    def disconnect_osa(self):
        self.abort_flag.set()
        try:
            if self.controller.osa:
                self.controller.osa.write("SST")
                self.controller.osa.close()
        except:
            pass
        self.controller.osa = None
        self.connection_state.set("disconnected")
        self.status_var.set("Status: Not connected")

    def read_all_params(self):
        try:
            osa = self.controller.osa
            if not osa: return
            self.central_wl.set(   float(osa.query("CNT?")) )
            self.span.set(         str(int(float(osa.query("SPN?")))) )
            self.resolution.set(   str(float(osa.query("RES?"))) )
            self.integration.set(  osa.query("VBW?").strip() )
            self.points.set(       str(int(osa.query("MPT?"))) )
            try: self.reference_lvl.set(float(osa.query("RLV?")))
            except: pass
            try: self.level_offset.set(float(osa.query("LOFS?")))
            except: pass
            self.status_var.set("Parameters loaded.")
        except Exception as e:
            self.error_var.set(f"Read failed: {e}")

    def set_single_param(self, cmd, value):
        if self.connection_state.get()!="connected": return
        try:
            osa = self.controller.osa
            if cmd=="VBW":
                hz = integration_string_to_hz(value)
                osa.write(f"{cmd} {hz}")
                actual = osa.query("VBW?").strip()
                if int(round(float(actual)))!=int(round(hz)):
                    raise ValueError(actual)
            elif cmd in ("RLV","LOFS"):
                osa.write(f"{cmd} {float(value)}")
                actual = float(osa.query(f"{cmd}?"))
                if abs(actual-float(value))>0.1:
                    raise ValueError(actual)
            else:
                osa.write(f"{cmd} {value}")
                actual = osa.query(f"{cmd}?").strip()
                if abs(float(actual)-float(value))>0.1:
                    raise ValueError(actual)
            self.error_var.set("")
        except Exception as e:
            self.error_var.set(f"{cmd} set failed: {e}")

    def apply_quality(self, quality):
        if quality=="high": res, v, m = "0.03","10Hz","1001"
        elif quality=="med": res, v, m = "0.07","100Hz","501"
        else:               res, v, m = "0.1","100Hz","501"
        self.resolution.set(res)
        self.integration.set(v)
        self.points.set(m)
        self.set_single_param("RES", res)
        self.set_single_param("VBW", v)
        self.set_single_param("MPT", m)
        self.status_var.set(f"Quality: {quality}")

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
            self.progressbar["value"]=10
            osa.write('*CLS'); osa.write('SSI')
            osa.query('*OPC?')
            self.progressbar["value"]=80
            staw,stow,npts = np.fromstring(osa.query("DCA?"), sep=",")
            wl = np.linspace(staw,stow,int(npts))
            dbm = np.fromstring(osa.query("DMA?"), dtype=float, sep="\r\n")
            lin = 10**(dbm/10)
            self.last_wavelengths, self.last_power_dbm, self.last_power_lin = wl, dbm, lin
            self.plot_results(wl, lin, dbm, live=False)
            self.progressbar["value"]=100
            self.status_var.set("Sweep done.")
        except Exception as e:
            self.error_var.set(f"Sweep failed: {e}")
            self.status_var.set("Sweep error")
        finally:
            self.sweep_running=False
            self.set_button_states("stopped")

    def start_repeat_sweep(self):
        if self.repeat_running:
            self.abort_flag.set()
            self.set_button_states("stopped")
            self.status_var.set("Repeat stopped.")
            return
        self.abort_flag.clear()
        self.repeat_running=True
        self.set_button_states("repeat")
        self.progressbar.config(mode="indeterminate")
        self.progressbar.start()
        threading.Thread(target=self.repeat_polling_loop, daemon=True).start()

    def repeat_polling_loop(self):
        try:
            osa = self.controller.osa
            osa.write('SRT')  # korrekt
            self.master.after(0, lambda: self.status_var.set("Repeat (live polling)…"))
            while not self.abort_flag.is_set():
                staw,stow,npts = np.fromstring(osa.query("DCA?"), sep=",")
                wl = np.linspace(staw,stow,int(npts))
                dbm = np.fromstring(osa.query("DMA?"), dtype=float, sep="\r\n")
                lin = 10**(dbm/10)
                self.last_wavelengths, self.last_power_dbm, self.last_power_lin = wl, dbm, lin
                self.master.after(0, lambda w=wl,ln=lin,d=dbm: self.plot_results(w,ln,d,live=True))
                time.sleep(0.3)
            osa.write('SST')
            self.master.after(0, lambda: self.status_var.set("Repeat stopped."))
        finally:
            self.master.after(0, self._finish_repeat)

    def _finish_repeat(self):
        self.progressbar.stop()
        self.progressbar.config(mode="determinate")
        self.repeat_running=False
        self.set_button_states("stopped")

    def set_button_states(self, mode="stopped"):
        if mode=="single":
            self.single_btn.config(text="Stop",state="normal")
            self.repeat_btn.config(text="Repeat Sweep",state="disabled")
        elif mode=="repeat":
            self.single_btn.config(text="Single Sweep",state="disabled")
            self.repeat_btn.config(text="Stop",state="normal")
        else:
            self.single_btn.config(text="Single Sweep",state="normal")
            self.repeat_btn.config(text="Repeat Sweep",state="normal")

    def start_scan(self):
        if self.scan_running: return
        try:
            f0 = float(self.scan_start.get()); f1 = float(self.scan_end.get())
            df = float(self.scan_step.get()); pause = float(self.scan_pause.get())
        except Exception as e:
            messagebox.showerror("Scan error", f"Invalid parameters: {e}")
            return
        self.scan_running=True
        threading.Thread(target=self._scan_thread, args=(f0,f1,df,pause), daemon=True).start()

    def _scan_thread(self, f0, f1, df, pause):
        while self.scan_running and f0<=f1:
            self.wavegen_controller.write(f"SOUR1:FREQ {f0}")
            time.sleep(pause)
            osa = self.controller.osa
            osa.write('*CLS'); osa.write('SSI'); osa.query('*OPC?')
            staw,stow,npts = np.fromstring(osa.query("DCA?"), sep=",")
            wl = np.linspace(staw,stow,int(npts))
            dbm = np.fromstring(osa.query("DMA?"), dtype=float, sep="\r\n")
            idx = int(np.nanargmax(dbm))
            val, wl_peak = dbm[idx], wl[idx]
            self.master.after(0, lambda v=val,w=wl_peak,fr=f0:
                self.current_peak_var.set(f"Peak: {v:.2f} dBm @ {w:.3f} nm, {fr:.3f} Hz"))
            f0 += df
        self.scan_running=False
        self.status_var.set("Scan done.")

    def stop_scan(self):
        self.scan_running=False
        self.status_var.set("Scan stopped.")

    def plot_results(self, wavelengths, data_lin, data_dbm, live=False):
        max_lin = np.nanmax(data_lin) if len(data_lin) else 1
        if max_lin<1e-6: unit,factor="nW",1e9
        elif max_lin<1e-3: unit,factor="µW",1e6
        elif max_lin<1:    unit,factor="mW",1e3
        else:              unit,factor="W",1
        y_lin = data_lin*factor
        txt = " (Live)" if live else ""

        idx = int(np.nanargmax(data_dbm))
        p_dbm = data_dbm[idx]; wl_peak = wavelengths[idx]
        try: fr = self.wavegen_gui.current_frequency[1]
        except: fr = 0.0
        self.current_peak_var.set(f"Peak: {p_dbm:.2f} dBm @ {wl_peak:.3f} nm, {fr:.3f} Hz")

        self.ax_lin.clear(); self.ax_lin.plot(wavelengths,y_lin)
        self.ax_lin.set_title(f"OSA Linear Scale{txt}")
        self.ax_lin.set_xlabel("Wavelength (nm)"); self.ax_lin.set_ylabel(f"Power ({unit})")
        self.ax_lin.xaxis.set_major_locator(MaxNLocator(5))
        self.ax_lin.xaxis.set_minor_locator(AutoMinorLocator(2))
        self.ax_lin.grid(which='major',axis='x',linestyle='-')
        self.ax_lin.grid(which='minor',axis='x',linestyle=':',alpha=0.7)
        self.fig_lin.tight_layout(); self.canvas_lin.draw()

        self.ax_dbm.clear(); self.ax_dbm.plot(wavelengths,data_dbm)
        self.ax_dbm.set_title(f"OSA dBm Scale{txt}")
        self.ax_dbm.set_xlabel("Wavelength (nm)"); self.ax_dbm.set_ylabel("Power (dBm)")
        self.ax_dbm.xaxis.set_major_locator(MaxNLocator(5))
        self.ax_dbm.xaxis.set_minor_locator(AutoMinorLocator(2))
        self.ax_dbm.grid(which='major',axis='x',linestyle='-')
        self.ax_dbm.grid(which='minor',axis='x',linestyle=':',alpha=0.7)
        self.fig_dbm.tight_layout(); self.canvas_dbm.draw()

    def save_data_npy(self):
        if self.last_wavelengths is None:
            messagebox.showwarning("No Data","Run a sweep first!")
            return
        file = filedialog.asksaveasfilename(defaultextension=".npy",filetypes=[("NumPy","*.npy")])
        if file:
            arr = np.vstack((self.last_wavelengths,self.last_power_dbm,self.last_power_lin)).T
            np.save(file,arr); messagebox.showinfo("Saved",f"Data saved: {file}")

    def save_linear_plot(self):
        file = filedialog.asksaveasfilename(defaultextension=".png",filetypes=[("PNG","*.png")])
        if file:
            self.fig_lin.savefig(file,dpi=600,bbox_inches='tight'); messagebox.showinfo("Saved","Linear plot saved.")

    def save_dbm_plot(self):
        file = filedialog.asksaveasfilename(defaultextension=".png",filetypes=[("PNG","*.png")])
        if file:
            self.fig_dbm.savefig(file,dpi=600,bbox_inches='tight'); messagebox.showinfo("Saved","dBm plot saved.")

    def toggle_wavegen_panel(self):
        if self.wavegen_embed.winfo_ismapped():
            self.wavegen_embed.grid_remove()
        else:
            if not hasattr(self,'wavegen_gui'):
                from gui.widgets.wavegen_gui import WavegenGUI
                self.wavegen_gui = WavegenGUI(
                    self.wavegen_embed,
                    controller=self.wavegen_controller
                )
                self.wavegen_gui.pack(fill="both", expand=True)
            self.wavegen_embed.grid()

    def open_wavegen_window(self):
        if hasattr(self,'wg_window') and self.wg_window.winfo_exists():
            self.wg_window.lift()
            return
        root = self.master
        self.wg_window = tk.Toplevel(root)
        self.wg_window.title("Waveform Generator")
        self.wg_window.geometry("900x600")
        self.wg_window.protocol("WM_DELETE_WINDOW", self._on_wavegen_close)
        from gui.widgets.wavegen_gui import WavegenGUI
        self.wg_frame = WavegenGUI(self.wg_window, controller=self.wavegen_controller)
        self.wg_frame.pack(fill="both", expand=True, padx=10, pady=10)

    def _on_wavegen_close(self):
        self.wg_window.destroy()
        del self.wg_window, self.wg_frame

    def on_closing(self):
        self.abort_flag.set()
        try:
            if self.controller.osa:
                self.controller.osa.write("SST")
        except:
            pass
        self.master.destroy()
