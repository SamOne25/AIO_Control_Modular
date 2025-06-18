import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from controllers.scope_controller import ScopeController
from utils.helpers import get_best_unit, nice_divisor, format_rec_length, convert_volts_to_display

UNITS = {"V": 1, "mV": 1e-3, "uV": 1e-6}
SCALE_FACTOR = {"V": 1, "mV": 1e3, "uV": 1e6}
AVAILABLE_COLORS = ["yellow", "cyan", "magenta", "green", "red", "blue", "orange", "black"]

class ScopeGUI(ttk.Frame):
    def __init__(self, parent, controller=None):
        super().__init__(parent)
        self.controller = controller if controller else ScopeController()
        self.running = False

        self.channel_order = self.controller.get_channel_list()
        self.include_channels = {ch: tk.BooleanVar(value=(ch in ["CH2", "CH3"])) for ch in self.channel_order}
        self.channel_names = {ch: tk.StringVar(value=ch) for ch in self.channel_order}
        self.channel_colors = {
            ch: tk.StringVar(value={"CH1": "yellow", "CH2": "cyan", "CH3": "magenta", "CH4": "green"}[ch])
            for ch in self.channel_order
        }

        self.trigger_source_var = tk.StringVar(value="CH1")
        self.scope_threshold = tk.StringVar(value="1.0")
        self.scope_threshold_unit = tk.StringVar(value="V")
        self.prog_trigger_enabled = tk.BooleanVar(value=False)
        self.prog_trigger_channel_var = tk.StringVar(value="CH1")
        self.prog_threshold = tk.StringVar(value="1.0")
        self.prog_threshold_unit = tk.StringVar(value="V")
        self.normalize_data = tk.BooleanVar(value=False)
        self.timebase_ns = tk.DoubleVar(value=10.0)
        self.refresh_interval = tk.IntVar(value=200)
        self.rec_length_cached = 2000
        self.acq_mode_var = tk.StringVar(value="SAMPLE")
        self.avg_count_var = tk.StringVar(value="16")

        self.channel_btns = {}
        self.channel_tabs = {}
        self.channel_figs = {}
        self.channel_axes = {}
        self.channel_canvases = {}
        self.latest_data = {}

        self._build_gui()
        self.after(self.refresh_interval.get(), self._plot_timer)
        self.after(1000, self._gui_timer)

    def _build_gui(self):
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(top, text="Oscilloscope IP:").pack(side=tk.LEFT, padx=3)
        self.scope_ip = tk.StringVar(value="192.168.1.133")
        tk.Entry(top, textvariable=self.scope_ip, width=16).pack(side=tk.LEFT, padx=3)
        self.connect_btn = tk.Button(top, text="Connect", bg="red", fg="white", width=12, command=self.toggle_connect)
        self.connect_btn.pack(side=tk.LEFT, padx=6)
        self.run_stop_btn = tk.Button(top, text="Run", bg="green", fg="white", width=8, state=tk.DISABLED, command=self.toggle_run_stop)
        self.run_stop_btn.pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="Read Parameters", width=14, command=self.verify_parameters).pack(side=tk.LEFT, padx=6)

        ctr = ttk.Frame(self)
        ctr.pack(fill=tk.X, padx=5, pady=(0,2))
        ttk.Label(ctr, text="Plot Refresh [ms]:").pack(side=tk.LEFT, padx=5)
        tk.Spinbox(ctr, from_=50, to=1000, increment=50, textvariable=self.refresh_interval, width=6).pack(side=tk.LEFT, padx=5)
        tk.Checkbutton(ctr, text="Normalize Data", variable=self.normalize_data).pack(side=tk.LEFT, padx=5)

        ctrl = ttk.Frame(self)
        ctrl.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Channel Settings Frame
        chf = ttk.LabelFrame(ctrl, text="Channel Settings")
        chf.grid(row=0, column=0, rowspan=5, columnspan=3, padx=4, pady=4, sticky="nw")
        tk.Label(chf, text="Ch", font=("Arial",10,"bold")).grid(row=0,column=0)
        tk.Label(chf, text="Name",font=("Arial",10,"bold")).grid(row=0,column=1)
        tk.Label(chf, text="Color",font=("Arial",10,"bold")).grid(row=0,column=2)
        for i,ch in enumerate(self.channel_order, start=1):
            btn = tk.Button(chf, text=ch, width=8, relief=tk.RAISED, command=lambda c=ch: self.toggle_channel(c))
            btn.grid(row=i, column=0, padx=5, pady=2, sticky="w")
            self.channel_btns[ch] = btn
            ttk.Entry(chf, textvariable=self.channel_names[ch], width=10).grid(row=i, column=1, padx=5, pady=2, sticky="w")
            ttk.OptionMenu(
                chf, self.channel_colors[ch], self.channel_colors[ch].get(), *AVAILABLE_COLORS,
                command=lambda *_: self.update_channel_button_color(ch)
            ).grid(row=i, column=2, padx=5, pady=2, sticky="w")

        # Trigger Settings Frame
        tf = ttk.LabelFrame(ctrl, text="Trigger Settings")
        tf.grid(row=0, column=3, rowspan=5, columnspan=6, padx=4, pady=4, sticky="nw")
        tk.Label(tf, text="Source:", font=("Arial",10)).grid(row=0,column=0, padx=5, pady=4, sticky="w")
        self.combo_trigger_source = ttk.Combobox(tf, values=self.channel_order, textvariable=self.trigger_source_var, width=8, state="readonly")
        self.combo_trigger_source.grid(row=0, column=1, padx=5, pady=4, sticky="w")
        self.combo_trigger_source.bind("<<ComboboxSelected>>", lambda e: self.set_scope_trigger_source())
        tk.Label(tf, text="Level:", font=("Arial",10)).grid(row=1,column=0, padx=5, pady=2, sticky="w")
        self.spin_scope_threshold = tk.Spinbox(tf, from_=-1000.0, to=1000.0, increment=0.1, textvariable=self.scope_threshold, width=8)
        self.spin_scope_threshold.grid(row=1,column=1, padx=5, pady=2, sticky="w")
        self.spin_scope_threshold.bind("<Return>", lambda e: self.set_scope_threshold())
        self.spin_scope_threshold.bind("<FocusOut>", lambda e: self.set_scope_threshold())
        tk.Label(tf, textvariable=self.scope_threshold_unit).grid(row=1, column=2, padx=5, pady=2, sticky="w")

        pf = ttk.LabelFrame(tf, text="Program Trigger")
        pf.grid(row=2, column=0, columnspan=4, padx=5, pady=(10,5), sticky="nw")
        self.prog_trig_btn = tk.Button(pf, text="OFF", width=8, bg="red", fg="white", command=self.toggle_prog_trigger)
        self.prog_trig_btn.grid(row=0, column=0, padx=5, pady=4, sticky="w")
        tk.Label(pf, text="Ch:", font=("Arial",10)).grid(row=0,column=1, padx=5, pady=4, sticky="w")
        ttk.Combobox(pf, values=self.channel_order, textvariable=self.prog_trigger_channel_var, width=6, state="readonly").grid(row=0,column=2, padx=5, pady=4, sticky="w")
        tk.Label(pf, text="Lvl:", font=("Arial",10)).grid(row=1,column=0, padx=5, pady=2, sticky="w")
        tk.Spinbox(pf, from_=-10.0, to=10.0, increment=0.1, textvariable=self.prog_threshold, width=8).grid(row=1,column=1, padx=5, pady=2, sticky="w")
        ttk.OptionMenu(pf, self.prog_threshold_unit, self.prog_threshold_unit.get(), "V", "mV", "uV").grid(row=1, column=2, padx=5, pady=2, sticky="w")

        sf = ttk.LabelFrame(ctrl, text="Settings")
        sf.grid(row=0, column=9, rowspan=5, columnspan=5, padx=4, pady=4, sticky="ne")
        tk.Label(sf, text="Rec Length:").grid(row=0, column=0, padx=5, pady=4, sticky="w")
        self.rec_length_label = tk.Label(sf, text=format_rec_length(self.rec_length_cached))
        self.rec_length_label.grid(row=0, column=1, padx=5, sticky="w")
        tk.Label(sf, text="Timebase [ns/div]:").grid(row=1,column=0, padx=5, pady=4, sticky="w")
        tb_frame = ttk.Frame(sf)
        tb_frame.grid(row=1, column=1, padx=5, pady=4, sticky="w")
        tb_entry = tk.Entry(tb_frame, textvariable=self.timebase_ns, width=6)
        tb_entry.pack(side=tk.LEFT)
        tb_entry.bind("<Return>", lambda e: self.set_timebase(self.timebase_ns.get()))
        tb_entry.bind("<FocusOut>", lambda e: self.set_timebase(self.timebase_ns.get()))
        tk.Button(tb_frame, text="⏪", command=self.decrease_timebase).pack(side=tk.LEFT, padx=(3,0))
        tk.Button(tb_frame, text="⏩", command=self.increase_timebase).pack(side=tk.LEFT, padx=(3,0))
        tk.Label(sf, text="Delay [ns]:").grid(row=2, column=0, padx=5, pady=4, sticky="w")
        self.delay_label = tk.Label(sf, text="0.00")
        self.delay_label.grid(row=2, column=1, padx=5, sticky="w")
        tk.Label(sf, text="Acq Mode:").grid(row=3, column=0, padx=5, pady=4, sticky="w")
        acq_vals = ["SAMPLE", "PEAK", "AVERAGE", "ENVELOPE"]
        self.combo_acq_mode = ttk.Combobox(sf, values=acq_vals, textvariable=self.acq_mode_var, width=10, state="readonly")
        self.combo_acq_mode.grid(row=3, column=1, padx=5, sticky="w")
        self.combo_acq_mode.bind("<<ComboboxSelected>>", lambda e: self.set_acquisition_mode())
        tk.Label(sf, text="# Avg:").grid(row=4, column=0, padx=5, pady=4, sticky="w")
        avg_vals = ["2","4","8","16","32","64","128","256"]
        self.combo_avg_count = ttk.Combobox(sf, values=avg_vals, textvariable=self.avg_count_var, width=6, state="disabled")
        self.combo_avg_count.grid(row=4, column=1, padx=5, sticky="w")
        self.combo_avg_count.bind("<<ComboboxSelected>>", lambda e: self.set_avg_count())

        svf = ttk.LabelFrame(ctrl, text="Save")
        svf.grid(row=0, column=14, rowspan=5, columnspan=2, padx=4, pady=4, sticky="ne")
        for i,ch in enumerate(self.channel_order):
            ttk.Button(svf, text=f"Save {ch}", command=lambda c=ch: self.save_channel_plot(c)).grid(row=i, column=0, padx=5, pady=2, sticky="w")
        ttk.Button(svf, text="Save All Data", command=self.save_numpy_data).grid(row=len(self.channel_order), column=0, padx=5, pady=4, sticky="w")

        self.tab_control = ttk.Notebook(self)
        self.tab_control.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.main_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.main_tab, text="All Channels")
        self.fig_main, self.ax_main = plt.subplots(figsize=(8,5))
        self.ax_main.set_title("Oscilloscope Live – All Channels")
        self.ax_main.set_xlabel("Time (ns)")
        self.ax_main.set_ylabel("Normalized")
        self.ax_main.grid()
        self.canvas_main = FigureCanvasTkAgg(self.fig_main, master=self.main_tab)
        self.canvas_main.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        ttk.Button(self.main_tab, text="Save All PNG", command=self.save_main_plot).pack(side=tk.BOTTOM, pady=5)
        self.update_channel_tabs()

    def toggle_connect(self):
        if self.controller.is_connected():
            self.running = False
            self.controller.disconnect()
        else:
            ip = self.scope_ip.get().strip()
            ok = self.controller.connect(ip)
            if ok:
                self.running = True
                self.rec_length_label.config(text=format_rec_length(self.controller.rec_length_cached))
            else:
                messagebox.showerror("Fehler", "Keine Verbindung zum Oszilloskop möglich!")
        self.update_connect_button()

    def update_connect_button(self):
        if self.controller.is_connected():
            self.connect_btn.config(bg="green", text="Disconnect")
            self.run_stop_btn.config(state=tk.NORMAL)
        else:
            self.connect_btn.config(bg="red", text="Connect")
            self.run_stop_btn.config(state=tk.DISABLED, bg="green", text="Run")

    def toggle_run_stop(self):
        if self.running:
            self.running = False
            self.run_stop_btn.config(bg="green", text="Run")
        else:
            if self.controller.is_connected():
                self.running = True
                self.run_stop_btn.config(bg="red", text="Stop")

    def verify_parameters(self):
        try:
            tb = float(self.controller.scope.query("HORizontal:MAIN:SCAle?")) * 1e9
            self.timebase_ns.set(tb)
        except Exception:
            pass
        try:
            rl = int(self.controller.scope.query("HORizontal:RECordlength?"))
            self.rec_length_cached = rl
            self.rec_length_label.config(text=format_rec_length(rl))
        except Exception:
            pass
        try:
            mode = self.controller.scope.query("ACQ:MODE?").strip()
            self.acq_mode_var.set(mode)
        except Exception:
            pass
        if self.acq_mode_var.get() == "AVERAGE":
            try:
                cnt = int(self.controller.scope.query("ACQ:AVER:COUN?"))
                self.avg_count_var.set(str(cnt))
            except Exception:
                pass
        try:
            src = self.trigger_source_var.get()
            lvl = float(self.controller.scope.query(f"TRIGger:A:LEVel:{src}?"))
            val, unit = convert_volts_to_display(lvl)
            self.scope_threshold.set(f"{val:.3f}")
            self.scope_threshold_unit.set(unit)
        except Exception:
            pass

    def set_scope_trigger_source(self):
        try:
            src = self.trigger_source_var.get()
            lvl = self.controller.set_trigger_source(src)
            val, unit = convert_volts_to_display(lvl)
            self.scope_threshold.set(f"{val:.3f}")
            self.scope_threshold_unit.set(unit)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to set trigger source:\n{e}")

    def set_scope_threshold(self):
        try:
            src = self.trigger_source_var.get()
            volts = float(self.scope_threshold.get()) * UNITS[self.scope_threshold_unit.get()]
            self.controller.set_trigger_level(src, volts)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to set trigger level:\n{e}")

    def set_acquisition_mode(self):
        try:
            mode = self.acq_mode_var.get()
            self.controller.set_acquisition_mode(mode)
            if mode == "AVERAGE":
                self.combo_avg_count.config(state="readonly")
                self.set_avg_count()
            else:
                self.combo_avg_count.config(state="disabled")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to set acquisition mode:\n{e}")

    def set_avg_count(self):
        try:
            cnt = int(self.avg_count_var.get())
            self.controller.set_average_count(cnt)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to set average count:\n{e}")

    def set_timebase(self, val_ns):
        try:
            self.controller.set_timebase(val_ns)
            tb = self.controller.scope.query("HORizontal:MAIN:SCAle?")
            self.timebase_ns.set(float(tb) * 1e9)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to set timebase:\n{e}")

    def decrease_timebase(self):
        new_tb = max(self.timebase_ns.get() / 2, 0.1)
        self.set_timebase(new_tb)

    def increase_timebase(self):
        new_tb = min(self.timebase_ns.get() * 2, 1e6)
        self.set_timebase(new_tb)

    def toggle_prog_trigger(self):
        st = not self.prog_trigger_enabled.get()
        self.prog_trigger_enabled.set(st)
        self.prog_trig_btn.config(bg="green" if st else "red", text="ON" if st else "OFF")

    def toggle_channel(self, ch):
        st = not self.include_channels[ch].get()
        self.include_channels[ch].set(st)
        self.update_channel_button_color(ch)
        self.update_channel_tabs()

    def update_channel_button_color(self, ch):
        btn = self.channel_btns[ch]
        if self.include_channels[ch].get():
            btn.config(bg=self.channel_colors[ch].get(), fg="white")
        else:
            btn.config(bg="SystemButtonFace", fg="black")

    def update_channel_tabs(self):
        for ch in list(self.channel_tabs):
            self.tab_control.forget(self.channel_tabs[ch])
            for d in (self.channel_tabs, self.channel_figs, self.channel_axes, self.channel_canvases):
                d.pop(ch, None)
        for ch in self.channel_order:
            if self.include_channels[ch].get():
                frame = ttk.Frame(self.tab_control)
                fig, ax = plt.subplots(figsize=(8,5))
                ax.set_title(f"Oscilloscope – {self.channel_names[ch].get()}")
                ax.set_xlabel("Time (ns)")
                ax.set_ylabel("V/div")
                ax.grid()
                canvas = FigureCanvasTkAgg(fig, master=frame)
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                ttk.Button(frame, text="Save PNG", command=lambda c=ch: self.save_channel_plot(c)).pack(side=tk.BOTTOM, pady=5)
                self.channel_tabs[ch]     = frame
                self.channel_figs[ch]     = fig
                self.channel_axes[ch]     = ax
                self.channel_canvases[ch] = canvas
                self.tab_control.add(frame, text=ch)

    def _plot_timer(self):
        if self.running:
            self.acquisition_step()
        self.after(self.refresh_interval.get(), self._plot_timer)

    def _gui_timer(self):
        self.update_connect_button()
        for ch, btn in self.channel_btns.items():
            t, _ = self.latest_data.get(ch, (None, None))
            btn.config(relief=tk.SUNKEN if t is not None else tk.RAISED)
        self.after(1000, self._gui_timer)

    def acquisition_step(self):
        for ch in self.channel_order:
            if not self.include_channels[ch].get():
                continue
            t, v = self.controller.get_waveform(ch)
            if t is not None and v is not None:
                if self.normalize_data.get():
                    m = np.max(np.abs(v))
                    v = v / m if m else v
                self.latest_data[ch] = (t, v)
            else:
                self.latest_data[ch] = (None, None)
        self.update_plot()

    def update_plot(self):
        self.ax_main.clear()
        self.ax_main.set_title("Oscilloscope Live – All Channels")
        self.ax_main.set_xlabel("Time (ns)")
        self.ax_main.set_ylabel("Normalized")
        self.ax_main.grid(which='major', color='gray', linestyle='--')
        max_t = 0.0
        scales = {}
        units = {}
        for ch,(t,v) in self.latest_data.items():
            if t is None: continue
            max_t = max(max_t, np.max(t))
            unit_ch = get_best_unit(v)
            scale_ch = SCALE_FACTOR[unit_ch]
            v_scaled = v * scale_ch
            v_div_ch = nice_divisor(np.nanmax(np.abs(v_scaled))/5)
            scales[ch] = v_div_ch
            units[ch] = unit_ch
        if max_t <= 0:
            max_t = self.timebase_ns.get() * 10
        self.ax_main.set_xlim(0, max_t)
        xticks = np.arange(0, max_t + self.timebase_ns.get(), self.timebase_ns.get())
        self.ax_main.set_xticks(xticks)
        self.ax_main.set_ylim(-5,5)
        self.ax_main.set_yticks(np.arange(-5,6))
        for ch,(t,v) in self.latest_data.items():
            if t is None or ch not in scales: continue
            v_norm = (v * SCALE_FACTOR[units[ch]]) / scales[ch]
            self.ax_main.plot(
                t, v_norm,
                label=self.channel_names[ch].get(),
                color=self.channel_colors[ch].get()
            )
        for idx,ch in enumerate(scales):
            disp_val, disp_unit = convert_volts_to_display(scales[ch] * UNITS[units[ch]])
            self.ax_main.text(
                0.02, 0.02+idx*0.05,
                f"{disp_val:.2f} {disp_unit}/div",
                transform=self.ax_main.transAxes,
                color=self.channel_colors[ch].get(),
                fontsize=10, verticalalignment='bottom'
            )
        if scales:
            self.ax_main.legend(loc="upper right")
        self.canvas_main.draw()
        for ch in self.channel_order:
            ax = self.channel_axes.get(ch)
            canvas = self.channel_canvases.get(ch)
            if not ax or not canvas: continue
            ax.clear()
            ax.set_title(f"Oscilloscope – {self.channel_names[ch].get()}")
            ax.set_xlabel("Time (ns)")
            ax.set_ylabel("V/div")
            ax.grid(which='major', color='gray', linestyle='--')
            t, v = self.latest_data.get(ch,(None,None))
            if t is None:
                canvas.draw()
                continue
            unit_ch = get_best_unit(v)
            v_scaled = v * SCALE_FACTOR[unit_ch]
            v_div_ch = nice_divisor(np.nanmax(np.abs(v_scaled))/5)
            ax.set_xlim(0, np.max(t))
            xticks_ch = np.arange(0, np.max(t)+self.timebase_ns.get(), self.timebase_ns.get())
            ax.set_xticks(xticks_ch)
            ax.set_ylim(-v_div_ch*5, v_div_ch*5)
            ax.set_yticks(np.arange(-5,6)*v_div_ch)
            ax.plot(t, v_scaled, color=self.channel_colors[ch].get())
            disp_val, disp_unit = convert_volts_to_display(v_div_ch)
            ax.text(
                0.02, 0.02,
                f"{disp_val:.2f} {disp_unit}/div",
                transform=ax.transAxes,
                color=self.channel_colors[ch].get(),
                fontsize=10, verticalalignment='bottom'
            )
            canvas.draw()

    def save_main_plot(self):
        path = filedialog.asksaveasfilename(defaultextension=".png")
        if path:
            self.fig_main.savefig(path, dpi=300)
            messagebox.showinfo("Saved", f"Main plot saved to:\n{path}")

    def save_channel_plot(self, ch):
        fig = self.channel_figs.get(ch)
        if not fig:
            return
        path = filedialog.asksaveasfilename(defaultextension=".png")
        if path:
            fig.savefig(path, dpi=300)
            messagebox.showinfo("Saved", f"{ch} plot saved to:\n{path}")

    def save_numpy_data(self):
        if not self.latest_data:
            messagebox.showwarning("No Data", "No data to save.")
            return
        valid = [(t,v) for t,v in self.latest_data.values() if t is not None]
        if not valid:
            messagebox.showwarning("No Data", "No valid data to save.")
            return
        max_len = max(len(t) for t,_ in valid)
        time_base = next(t for t,_ in valid if len(t)==max_len)
        arr = np.full((max_len, len(self.channel_order)+1), np.nan)
        arr[:,0] = time_base
        for i,ch in enumerate(self.channel_order, start=1):
            t,v = self.latest_data.get(ch,(None,None))
            if t is None: continue
            unit_ch = get_best_unit(v)
            v_scaled = v * SCALE_FACTOR[unit_ch]
            arr[:,i] = v_scaled if len(t)==max_len else np.interp(time_base, t, v_scaled)
        path = filedialog.asksaveasfilename(defaultextension=".npy")
        if path:
            np.save(path, arr)
            messagebox.showinfo("Saved", f"Data saved to:\n{path}")
