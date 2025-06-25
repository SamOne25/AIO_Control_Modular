import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time

from controllers.wavegen_controller import WavegenController
from controllers.osa_controller import OSAController
from utils.tooltip import Tooltip

class WavegenGUI(ttk.Frame):
    def __init__(self, parent, controller=None, osa_controller: OSAController=None):
        super().__init__(parent)
        self.controller = controller if controller else WavegenController()
        self.osa_ctrl = osa_controller  # optional OSAController for integrated scan
        self.generator_on = {1: False, 2: False}
        self.current_frequency = {1: 0.0, 2: 0.0}
        self.entries_ch = {1: {}, 2: {}}
        self.independent = True
        self.phase_deg = 0.0
        self.delay_ns_var = tk.DoubleVar(value=0.0)
        self.func_choices = [
            "SINusoid", "SQUare", "RAMP", "PULSe",
            "TRIangle", "NOISe", "PRBS", "DC"
        ]
        self.func_var_ch = {
            1: tk.StringVar(value="PULSe"),
            2: tk.StringVar(value="PULSe")
        }
        self._build_gui()

    def _build_gui(self):
        main = tk.Frame(self)
        main.pack(fill="both", expand=True, padx=10, pady=10)

        # Top row: IP, Connect, Mode
        top = tk.Frame(main)
        top.pack(fill="x", pady=(0,10))
        tk.Label(top, text="IP Address:").grid(row=0, column=0, sticky="e", padx=5)
        self.ip_entry = tk.Entry(top, width=15)
        self.ip_entry.insert(0, "192.168.1.122")
        self.ip_entry.grid(row=0, column=1, padx=5)
        Tooltip(self.ip_entry, "Valid IP, e.g. 192.168.1.122")
        self.connect_button = tk.Button(top, text="Connect", bg="red",
                                        command=self.toggle_connection)
        self.connect_button.grid(row=0, column=2, padx=5)
        self.mode_button = tk.Button(top, text="Independent", width=12,
                                     command=self.toggle_mode)
        self.mode_button.grid(row=0, column=3, padx=5)

        # Notebook for two channels
        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill="both", expand=True)
        self.ch1_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.ch1_frame, text="Channel 1")
        self.create_channel_tab(1, self.ch1_frame)
        self.ch2_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.ch2_frame, text="Channel 2")
        self.create_channel_tab(2, self.ch2_frame)

        # Coupled mode subframe (in ch1)
        self.coupled_subframe = tk.LabelFrame(
            self.ch1_frame, text="Coupled Mode Settings", padx=5, pady=5
        )
        self.coupled_subframe.grid(row=6, column=0, columnspan=4,
                                   sticky="ew", pady=(10,0), padx=5)
        tk.Label(self.coupled_subframe, text="Delay (ns):").grid(
            row=0, column=0, sticky="e", padx=5, pady=2
        )
        self.delay_spin = tk.Spinbox(
            self.coupled_subframe, from_=0.0, to=1e6, increment=0.1,
            textvariable=self.delay_ns_var, width=10,
            command=self.update_phase_from_delay
        )
        self.delay_spin.grid(row=0, column=1, padx=5, pady=2)
        Tooltip(self.delay_spin, "Delay between channels in ns (0–1e6)")
        tk.Label(self.coupled_subframe, text="ns").grid(
            row=0, column=2, sticky="w"
        )
        tk.Label(self.coupled_subframe, text="Phase Shift (°):").grid(
            row=1, column=0, sticky="e", padx=5, pady=2
        )
        self.phase_label = tk.Label(self.coupled_subframe, text="0.00")
        self.phase_label.grid(row=1, column=1, padx=5, pady=2)
        tk.Label(self.coupled_subframe, text="°").grid(
            row=1, column=2, sticky="w"
        )
        self.ch2_control_button = tk.Button(
            self.coupled_subframe, text="Channel 2 OFF", bg="red",
            command=lambda: self.toggle_generator(2)
        )
        self.ch2_control_button.grid(row=2, column=0, columnspan=3,
                                     pady=(5,5))
        self.coupled_subframe.grid_remove()

        # Scan Controls
        scan_frame = tk.LabelFrame(main, text="Scan Controls", padx=5, pady=5)
        scan_frame.pack(fill="x", pady=(10,0))
        tk.Label(scan_frame, text="Start Freq (Hz):").grid(
            row=0, column=0, sticky="e", padx=5, pady=2
        )
        self.start_entry = tk.Entry(scan_frame, width=10)
        self.start_entry.insert(0, "4000")
        self.start_entry.grid(row=0, column=1, padx=5, pady=2)
        Tooltip(self.start_entry, "Start frequency in Hz (≥0.1)")
        tk.Label(scan_frame, text="End Freq (Hz):").grid(
            row=0, column=2, sticky="e", padx=5, pady=2
        )
        self.end_entry = tk.Entry(scan_frame, width=10)
        self.end_entry.insert(0, "5000")
        self.end_entry.grid(row=0, column=3, padx=5, pady=2)
        Tooltip(self.end_entry, "End frequency in Hz (≥ start)")
        tk.Label(scan_frame, text="Step (Hz):").grid(
            row=1, column=0, sticky="e", padx=5, pady=2
        )
        self.step_entry = tk.Entry(scan_frame, width=10)
        self.step_entry.insert(0, "1")
        self.step_entry.grid(row=1, column=1, padx=5, pady=2)
        Tooltip(self.step_entry, "Step in Hz (>0)")
        tk.Label(scan_frame, text="Pause (s):").grid(
            row=1, column=2, sticky="e", padx=5, pady=2
        )
        self.pause_entry = tk.Entry(scan_frame, width=10)
        self.pause_entry.insert(0, "0.5")
        self.pause_entry.grid(row=1, column=3, padx=5, pady=2)
        Tooltip(self.pause_entry, "Pause between steps in s (≥0)")
        tk.Label(scan_frame, text="Meas WL (nm):").grid(
            row=2, column=0, sticky="e", padx=5, pady=2
        )
        self.osa_wl_entry = tk.Entry(scan_frame, width=10)
        self.osa_wl_entry.insert(0, "1550")
        self.osa_wl_entry.grid(row=2, column=1, padx=5, pady=2)
        Tooltip(self.osa_wl_entry, "Wavelength for power-meter (nm)")
        tk.Button(scan_frame, text="Start Scan", command=self.start_scan)\
            .grid(row=3, column=0, padx=5, pady=5)
        tk.Button(scan_frame, text="Stop Scan", command=self.stop_scan)\
            .grid(row=3, column=1, padx=5, pady=5)
        tk.Button(scan_frame, text="Resume Scan", command=self.resume_scan)\
            .grid(row=3, column=2, padx=5, pady=5)

        # Status
        self.status_label = tk.Label(self, text="Ready")
        self.status_label.pack(side="bottom", fill="x", padx=10, pady=5)

        self.update_mode()

    def toggle_connection(self):
        if self.controller.gen is None:
            try:
                ip = self.ip_entry.get().strip()
                self.controller.connect(ip)
                self.status("Generator connected")
                self.connect_button.config(text="Disconnect", bg="green")
                self.read_settings(1)
                if self.independent:
                    self.read_settings(2)
                self.update_output_buttons()
            except Exception as e:
                messagebox.showerror("Error", f"Connection failed: {e}")
                self.controller.disconnect()
                self.connect_button.config(text="Connect", bg="red")
        else:
            try:
                self.controller.disconnect()
                self.status("Disconnected")
                self.connect_button.config(text="Connect", bg="red")
                self.gen_button1.config(text="Channel 1 OFF", bg="red")
                self.gen_button2.config(text="Channel 2 OFF", bg="red")
                self.generator_on = {1: False, 2: False}
            except Exception as e:
                messagebox.showerror("Error", f"Disconnection failed: {e}")

    def toggle_mode(self):
        self.independent = not self.independent
        self.mode_button.config(text="Independent" if self.independent else "Coupled")
        self.update_mode()

    def update_mode(self):
        if self.independent:
            try: self.notebook.add(self.ch2_frame, text="Channel 2")
            except: pass
            self.coupled_subframe.grid_remove()
        else:
            try: self.notebook.forget(self.ch2_frame)
            except: pass
            self.coupled_subframe.grid()

    def create_channel_tab(self, chan, frame):
        labels = [
            ("Frequency (Hz):", "4000"),
            ("Amplitude (Vpp):", "5"),
            ("Offset (V):", "2.5"),
            ("Pulse Width (ns):", "30")
        ]
        for i, (lbl, default) in enumerate(labels):
            tk.Label(frame, text=lbl).grid(
                row=i, column=0, sticky="e", padx=5, pady=2
            )
            entry = tk.Entry(frame, width=12)
            entry.insert(0, default)
            entry.grid(row=i, column=1, padx=5, pady=2)
            self.entries_ch[chan][lbl] = entry
            if lbl.startswith("Pulse Width"):
                Tooltip(entry, "Pulse width in ns (integer)")
        tk.Label(frame, text="Waveform:").grid(
            row=4, column=0, sticky="e", padx=5, pady=2
        )
        func_menu = ttk.OptionMenu(frame,
            self.func_var_ch[chan],
            self.func_var_ch[chan].get(),
            *self.func_choices
        )
        func_menu.grid(row=4, column=1, padx=5, pady=2, sticky="ew")

        tk.Button(frame, text=f"Channel {chan} SET",
                  command=lambda c=chan: self.set_settings(c))\
            .grid(row=0, column=2, padx=5, pady=2, sticky="ew")
        gen_btn = tk.Button(frame, text=f"Channel {chan} OFF", bg="red",
                            command=lambda c=chan: self.toggle_generator(c))
        gen_btn.grid(row=1, column=2, padx=5, pady=2, sticky="ew")
        if chan==1: self.gen_button1 = gen_btn
        else:      self.gen_button2 = gen_btn

        if chan==2:
            tk.Button(frame, text="Apply From Channel 1",
                      command=self.apply_from_ch1)\
                .grid(row=2, column=2, padx=5, pady=2, sticky="ew")

        # Adjust Frequency: paired up/down
        adj = tk.LabelFrame(frame, text="Adjust Frequency", padx=5, pady=5)
        adj.grid(row=5, column=0, columnspan=3,
                 sticky="ew", padx=5, pady=10)
        steps = [(-10,10),(-1,1),(-0.1,0.1),(-0.01,0.01),(-0.001,0.001)]
        for col,(neg,pos) in enumerate(steps):
            lbl_n = f"{int(neg):+}Hz" if abs(neg)>=1 else f"{neg:+.3f}Hz"
            lbl_p = f"{int(pos):+}Hz" if abs(pos)>=1 else f"{pos:+.3f}Hz"
            tk.Button(adj, text=lbl_n, width=8,
                      command=lambda s=neg,c=chan: self.adjust_frequency(c,s))\
                .grid(row=0, column=col, padx=2, pady=2)
            tk.Button(adj, text=lbl_p, width=8,
                      command=lambda s=pos,c=chan: self.adjust_frequency(c,s))\
                .grid(row=1, column=col, padx=2, pady=2)
        # ×10 and ÷10 stacked at end
        col = len(steps)
        tk.Button(adj, text="×10", width=8,
                  command=lambda c=chan: self.scale_frequency(c,10))\
            .grid(row=0, column=col, padx=(20,2), pady=2)
        tk.Button(adj, text="÷10", width=8,
                  command=lambda c=chan: self.scale_frequency(c,0.1))\
            .grid(row=1, column=col, padx=(20,2), pady=2)

    def set_settings(self, channel):
        if self.controller.gen is None:
            self.toggle_connection()
            if self.controller.gen is None:
                return
        try:
            e = self.entries_ch[channel]
            freq = float(e["Frequency (Hz):"].get())
            volt = float(e["Amplitude (Vpp):"].get())
            offs = float(e["Offset (V):"].get())
            width_ns = int(round(float(e["Pulse Width (ns):"].get())))
            func = self.func_var_ch[channel].get()

            self.controller.write(f"SOUR{channel}:FUNC {func}")
            self.controller.write(f"SOUR{channel}:VOLT {volt}")
            self.controller.write(f"SOUR{channel}:VOLT:OFFS {offs}")
            if func == "PULSe":
                self.controller.write(f"SOUR{channel}:PULS:WIDT {width_ns*1e-9}")
            self.controller.write(f"OUTP{channel}:LOAD 50")
            self.controller.write(f"SOUR{channel}:FREQ {freq}")
            self.current_frequency[channel] = freq
            self.status(f"Ch{channel} settings applied: {freq:.3f} Hz")
            if not self.independent and channel==1:
                self.update_phase_from_delay()
            self.update_output_buttons()
        except Exception as e:
            messagebox.showerror("Error", f"Set settings failed (Ch{channel}): {e}")

    def read_settings(self, channel):
        if self.controller.gen is None:
            self.toggle_connection()
            if self.controller.gen is None:
                return
        try:
            func = self.controller.query(f"SOUR{channel}:FUNC?").strip()
            freq = float(self.controller.query(f"SOUR{channel}:FREQ?").strip())
            volt = float(self.controller.query(f"SOUR{channel}:VOLT?").strip())
            offs = float(self.controller.query(f"SOUR{channel}:VOLT:OFFS?").strip())
            width_resp = float(self.controller.query(f"SOUR{channel}:PULS:WIDT?").strip())
            width_ns = int(round(width_resp * 1e9))

            e = self.entries_ch[channel]
            e["Frequency (Hz):"].delete(0, tk.END);    e["Frequency (Hz):"].insert(0, f"{freq:.3f}")
            e["Amplitude (Vpp):"].delete(0, tk.END);    e["Amplitude (Vpp):"].insert(0, f"{volt:.3f}")
            e["Offset (V):"].delete(0, tk.END);         e["Offset (V):"].insert(0, f"{offs:.3f}")
            e["Pulse Width (ns):"].delete(0, tk.END);   e["Pulse Width (ns):"].insert(0, f"{width_ns}")
            self.func_var_ch[channel].set(func)
            self.current_frequency[channel] = freq

            self.status(f"Ch{channel} settings read")
            state = self.controller.query(f"OUTP{channel}?").strip()
            is_on = state in ("1","ON")
            btn = self.gen_button1 if channel==1 else self.gen_button2
            btn.config(text=f"Channel {channel} {'ON' if is_on else 'OFF'}",
                       bg="green" if is_on else "red")
            self.generator_on[channel] = is_on
            if not self.independent and channel==1:
                self.update_phase_from_delay()
        except Exception as e:
            messagebox.showerror("Error", f"Read settings failed (Ch{channel}): {e}")

    def apply_from_ch1(self):
        if self.controller.gen is None:
            return
        try:
            e1 = self.entries_ch[1]
            freq = float(e1["Frequency (Hz):"].get())
            volt = float(e1["Amplitude (Vpp):"].get())
            offs = float(e1["Offset (V):"].get())
            width_ns = int(round(float(e1["Pulse Width (ns):"].get())))
            func = self.func_var_ch[1].get()

            e2 = self.entries_ch[2]
            e2["Frequency (Hz):"].delete(0, tk.END);    e2["Frequency (Hz):"].insert(0, f"{freq:.3f}")
            e2["Amplitude (Vpp):"].delete(0, tk.END);    e2["Amplitude (Vpp):"].insert(0, f"{volt:.3f}")
            e2["Offset (V):"].delete(0, tk.END);         e2["Offset (V):"].insert(0, f"{offs:.3f}")
            e2["Pulse Width (ns):"].delete(0, tk.END);   e2["Pulse Width (ns):"].insert(0, f"{width_ns}")
            self.func_var_ch[2].set(func)

            self.controller.write(f"SOUR2:FUNC {func}")
            self.controller.write(f"SOUR2:VOLT {volt}")
            self.controller.write(f"SOUR2:VOLT:OFFS {offs}")
            self.controller.write(f"SOUR2:PULS:WIDT {width_ns*1e-9}")
            self.controller.write(f"OUTP2:LOAD 50")
            self.controller.write(f"SOUR2:FREQ {freq}")
            self.current_frequency[2] = freq
            self.status("Ch2 params applied from Ch1")
            self.update_output_buttons()
        except Exception as e:
            messagebox.showerror("Error", f"Apply failed: {e}")

    def toggle_generator(self, channel):
        if self.controller.gen is None:
            self.toggle_connection()
            if self.controller.gen is None:
                return
        try:
            is_on = not self.generator_on[channel]
            cmd = "ON" if is_on else "OFF"
            self.controller.write(f"OUTP{channel} {cmd}")
            btn = self.gen_button1 if channel==1 else self.gen_button2
            btn.config(text=f"Channel {channel} {cmd}",
                       bg="green" if is_on else "red")
            self.generator_on[channel] = is_on
            self.status(f"Channel {channel} {cmd}")
        except Exception as e:
            messagebox.showerror("Error", f"Toggle error (Ch{channel}): {e}")

    def update_output_buttons(self):
        for ch in (1,2):
            try:
                state = self.controller.query(f"OUTP{ch}?").strip()
                is_on = state in ("1","ON")
                btn = self.gen_button1 if ch==1 else self.gen_button2
                btn.config(text=f"Channel {ch} {'ON' if is_on else 'OFF'}",
                           bg="green" if is_on else "red")
                self.generator_on[ch] = is_on
            except:
                pass

    def adjust_frequency(self, channel, step):
        try:
            current = float(self.entries_ch[channel]["Frequency (Hz):"].get())
            new_f = current + step
            if new_f > 30e6:
                raise ValueError("Max freq 30 MHz exceeded")
            self.entries_ch[channel]["Frequency (Hz):"].delete(0, tk.END)
            self.entries_ch[channel]["Frequency (Hz):"].insert(0, f"{new_f:.3f}")
            if self.controller.gen:
                self.controller.write(f"SOUR{channel}:FREQ {new_f}")
                self.current_frequency[channel] = new_f
                self.status(f"Ch{channel} freq adjusted to {new_f:.3f} Hz")
                if not self.independent and channel==1:
                    self.update_phase_from_delay()
        except Exception as e:
            messagebox.showerror("Error", f"Adjust freq failed (Ch{channel}): {e}")

    def scale_frequency(self, channel, factor):
        try:
            current = float(self.entries_ch[channel]["Frequency (Hz):"].get())
            new_f = current * factor
            if new_f > 30e6:
                messagebox.showerror("Error", ">30 MHz not allowed")
                return
            self.entries_ch[channel]["Frequency (Hz):"].delete(0, tk.END)
            self.entries_ch[channel]["Frequency (Hz):"].insert(0, f"{new_f:.3f}")
            if self.controller.gen:
                self.controller.write(f"SOUR{channel}:FREQ {new_f}")
                self.current_frequency[channel] = new_f
                self.status(f"Ch{channel} freq set to {new_f:.3f} Hz")
        except Exception as e:
            messagebox.showerror("Error", f"Scale freq failed (Ch{channel}): {e}")

    def update_phase_from_delay(self):
        try:
            delay_ns = self.delay_ns_var.get()
            freq_hz  = self.current_frequency[1]
            phase = (delay_ns*1e-9)*freq_hz*360.0 % 360.0
            self.phase_deg = phase
            self.phase_label.config(text=f"{phase:.2f}")
            if self.controller.gen:
                self.controller.write(f"SOUR2:PHASe {phase}")
        except Exception as e:
            messagebox.showerror("Error", f"Phase update failed: {e}")

    def start_scan(self):
        try:
            f0    = float(self.start_entry.get())
            f1    = float(self.end_entry.get())
            step  = float(self.step_entry.get())
            pause = float(self.pause_entry.get())
            wl    = float(self.osa_wl_entry.get())
        except Exception as e:
            messagebox.showerror("Error", f"Invalid scan params: {e}")
            return

        def worker():
            results = []
            f = f0
            while f <= f1:
                # set wavegen
                self.controller.write(f"SOUR1:FREQ {f}")
                time.sleep(pause)
                # measure OSA if available
                if self.osa_ctrl and getattr(self.osa_ctrl, "osa", None):
                    osa = self.osa_ctrl.osa
                    osa.write(f"PWR {wl}")
                    osa.query("*OPC?")
                    p = float(osa.query("PWRR?"))
                    results.append((f, p))
                f += step
            if results:
                mf, mp = max(results, key=lambda x: x[1])
                messagebox.showinfo("Scan done",
                    f"Max {mp:.2f} dBm at {mf:.3f} Hz")
        threading.Thread(target=worker, daemon=True).start()

    def stop_scan(self):
        self.scan_running = False
        self.status("Scan stopped")

    def resume_scan(self):
        self.scan_paused = False
        self.status("Scan resumed")

    def status(self, msg):
        try:
            self.status_label.config(text=msg)
        except:
            pass
