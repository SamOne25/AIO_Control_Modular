import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import math

from controllers.wavegen_controller import WavegenController
from utils.tooltip import Tooltip



class WavegenGUI(ttk.Frame):
    def __init__(self, parent, controller=None):
        super().__init__(parent)
        self.controller = controller if controller else WavegenController()
        self.generator_on = {1: False, 2: False}
        self.current_frequency = {1: 0.0, 2: 0.0}
        self.entries_ch = {1: {}, 2: {}}
        self.independent = True
        self.phase_deg = 0.0
        self.delay_ns_var = tk.DoubleVar(value=0.0)
        self.func_choices = ["SINusoid", "SQUare", "RAMP", "PULSe", "TRIangle", "NOISe", "PRBS", "DC"]
        self.func_var_ch = {1: tk.StringVar(value="PULSe"), 2: tk.StringVar(value="PULSe")}
               

    def _build_gui(self):
        main_frame = tk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        top_frame = tk.Frame(main_frame)
        top_frame.pack(fill="x", pady=(0, 10))
        tk.Label(top_frame, text="IP Address:").grid(row=0, column=0, sticky="e", padx=5, pady=2)
        self.ip_entry = tk.Entry(top_frame)
        self.ip_entry.insert(0, "192.168.1.122")
        self.ip_entry.grid(row=0, column=1, padx=5, pady=2)
        Tooltip(self.ip_entry, "Valid IP address, e.g. 192.168.1.122")

        self.connect_button = tk.Button(top_frame, text="Connect", bg="red", command=self.toggle_connection)
        self.connect_button.grid(row=0, column=2, padx=5, pady=2)

        self.mode_button = tk.Button(top_frame, text="Independent", command=self.toggle_mode, width=12)
        self.mode_button.grid(row=0, column=3, padx=5, pady=2)

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill="both", expand=True)

        self.ch1_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.ch1_frame, text="Channel 1")
        self.create_channel_tab(1, self.ch1_frame)

        self.ch2_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.ch2_frame, text="Channel 2")
        self.create_channel_tab(2, self.ch2_frame)

        self.coupled_subframe = tk.LabelFrame(self.ch1_frame, text="Coupled Mode Settings")
        self.coupled_subframe.grid(row=6, column=0, columnspan=4, pady=(10, 0), padx=5, sticky="ew")

        tk.Label(self.coupled_subframe, text="Delay (ns):").grid(row=0, column=0, sticky="e", padx=5, pady=2)
        self.delay_spin = tk.Spinbox(self.coupled_subframe, from_=0.0, to=1e6, increment=0.1,
                                     textvariable=self.delay_ns_var, width=10, command=self.update_phase_from_delay)
        self.delay_spin.grid(row=0, column=1, padx=5, pady=2)
        Tooltip(self.delay_spin, "Delay between channels in nanoseconds (0.0–1e6 ns)")
        tk.Label(self.coupled_subframe, text="ns").grid(row=0, column=2, sticky="w")

        tk.Label(self.coupled_subframe, text="Phase Shift (°):").grid(row=1, column=0, sticky="e", padx=5, pady=2)
        self.phase_label = tk.Label(self.coupled_subframe, text="0.00")
        self.phase_label.grid(row=1, column=1, padx=5, pady=2)
        tk.Label(self.coupled_subframe, text="°").grid(row=1, column=2, sticky="w")

        self.ch2_control_button = tk.Button(self.coupled_subframe, text="Channel 2 OFF", bg="red", command=lambda: self.toggle_generator(2))
        self.ch2_control_button.grid(row=2, column=0, columnspan=3, pady=(5, 5))
        self.coupled_subframe.grid_remove()

        scan_frame = tk.LabelFrame(main_frame, text="Scan Controls")
        scan_frame.pack(fill="x", pady=(10, 0))
        tk.Label(scan_frame, text="Start Frequency (Hz):").grid(row=0, column=0, sticky="e", padx=5, pady=2)
        self.start_entry = tk.Entry(scan_frame)
        self.start_entry.insert(0, "4000")
        self.start_entry.grid(row=0, column=1, padx=5, pady=2)
        Tooltip(self.start_entry, "Start frequency in Hz (float, ≥ 0.1 Hz)")
        tk.Label(scan_frame, text="End Frequency (Hz):").grid(row=0, column=2, sticky="e", padx=5, pady=2)
        self.end_entry = tk.Entry(scan_frame)
        self.end_entry.insert(0, "5000")
        self.end_entry.grid(row=0, column=3, padx=5, pady=2)
        Tooltip(self.end_entry, "End frequency in Hz (float, ≥ start frequency)")
        tk.Label(scan_frame, text="Step (Hz):").grid(row=1, column=0, sticky="e", padx=5, pady=2)
        self.step_entry = tk.Entry(scan_frame)
        self.step_entry.insert(0, "1")
        self.step_entry.grid(row=1, column=1, padx=5, pady=2)
        Tooltip(self.step_entry, "Step increment in Hz (float, > 0)")
        tk.Label(scan_frame, text="Pause (s):").grid(row=1, column=2, sticky="e", padx=5, pady=2)
        self.pause_entry = tk.Entry(scan_frame)
        self.pause_entry.insert(0, "0.5")
        self.pause_entry.grid(row=1, column=3, padx=5, pady=2)
        Tooltip(self.pause_entry, "Pause between steps in seconds (float, ≥ 0)")
        tk.Button(scan_frame, text="Start Scan", command=self.start_scan).grid(row=2, column=0, pady=5, padx=5)
        tk.Button(scan_frame, text="Stop Scan", command=self.stop_scan).grid(row=2, column=1, pady=5, padx=5)
        tk.Button(scan_frame, text="Resume Scan", command=self.resume_scan).grid(row=2, column=2, pady=5, padx=5)
        self.status_label = tk.Label(self, text="Ready")
        self.status_label.pack(side="bottom", fill="x", padx=10, pady=5)
        self.update_mode()

    # --- Alle Methoden 1:1 übernommen, Details wie im Original ---

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
                self.status("Disconnected from generator")
                self.connect_button.config(text="Connect", bg="red")
                self.gen_button1.config(text="Channel 1 OFF", bg="red")
                self.gen_button2.config(text="Channel 2 OFF", bg="red")
                self.generator_on = {1: False, 2: False}
            except Exception as e:
                messagebox.showerror("Error", f"Disconnection failed: {e}")

    def toggle_mode(self):
        self.independent = not self.independent
        text = "Independent" if self.independent else "Coupled"
        self.mode_button.config(text=text)
        self.update_mode()

    def update_mode(self):
        if self.independent:
            try:
                self.notebook.add(self.ch2_frame, text="Channel 2")
            except Exception:
                pass
            self.coupled_subframe.grid_remove()
        else:
            try:
                self.notebook.forget(self.ch2_frame)
            except Exception:
                pass
            self.coupled_subframe.grid()

    def create_channel_tab(self, chan, frame):
        labels = [
            ("Frequency (Hz):", "4000"),
            ("Amplitude (Vpp):", "5"),
            ("Offset (V):", "2.5"),
            ("Pulse Width (ns):", "30")
        ]
        for i, (label, default) in enumerate(labels):
            tk.Label(frame, text=label).grid(row=i, column=0, sticky="e", padx=5, pady=2)
            entry = tk.Entry(frame)
            entry.insert(0, default)
            entry.grid(row=i, column=1, padx=5, pady=2)
            self.entries_ch[chan][label] = entry
            if label == "Frequency (Hz):":
                Tooltip(entry, "Floating point, frequency in Hz (0.1–50e6)")
            elif label == "Amplitude (Vpp):":
                Tooltip(entry, "Floating point, amplitude in Vpp (0–10)")
            elif label == "Offset (V):":
                Tooltip(entry, "Floating point, offset in V (–5 to +5)")
            elif label == "Pulse Width (ns):":
                Tooltip(entry, "Floating point, pulse width in ns (≥ 1 ns, ≤ period)")
        tk.Label(frame, text="Waveform:").grid(row=4, column=0, sticky="e", padx=5, pady=2)
        func_menu = ttk.OptionMenu(frame, self.func_var_ch[chan], self.func_var_ch[chan].get(), *self.func_choices)
        func_menu.grid(row=4, column=1, padx=5, pady=2, sticky="ew")
        Tooltip(func_menu, "Waveform options: SINusoid, SQUare, RAMP, PULSe, TRIangle, NOISe, PRBS, DC")
        set_btn = tk.Button(frame, text=f"Channel {chan} SET", command=lambda c=chan: self.set_settings(c))
        set_btn.grid(row=0, column=2, rowspan=1, padx=5, pady=2, sticky="ew")
        gen_text = f"Channel {chan} OFF"
        gen_btn = tk.Button(frame, text=gen_text, bg="red", command=lambda c=chan: self.toggle_generator(c))
        gen_btn.grid(row=1, column=2, rowspan=1, padx=5, pady=2, sticky="ew")
        if chan == 1:
            self.gen_button1 = gen_btn
        else:
            self.gen_button2 = gen_btn
        if chan == 2:
            apply_btn = tk.Button(frame, text="Apply From Channel 1", command=self.apply_from_ch1)
            apply_btn.grid(row=2, column=2, padx=5, pady=2, sticky="ew")
        freq_adj_frame = tk.LabelFrame(frame, text="Adjust Frequency")
        freq_adj_frame.grid(row=5, column=0, columnspan=3, pady=10, padx=5, sticky="ew")
        steps = [-1000, -100, -10, -1, -0.1, -0.01, -0.001, 0.001, 0.01, 0.1, 1, 10, 100, 1000]
        for i, step in enumerate(steps):
            label = f"{step:+.3f}Hz" if abs(step) < 1 else f"{int(step):+}Hz"
            btn = tk.Button(freq_adj_frame, text=label, width=8, command=lambda s=step, c=chan: self.adjust_frequency(c, s))
            btn.grid(row=i // 7, column=i % 7, padx=2, pady=2)

    def set_settings(self, channel):
        if self.controller.gen is None:
            self.toggle_connection()
            if self.controller.gen is None:
                return
        try:
            freq = float(self.entries_ch[channel]["Frequency (Hz):"].get())
            volt = float(self.entries_ch[channel]["Amplitude (Vpp):"].get())
            offs = float(self.entries_ch[channel]["Offset (V):"].get())
            width_ns = float(self.entries_ch[channel]["Pulse Width (ns):"].get())
            width = width_ns * 1e-9
            func = self.func_var_ch[channel].get()
            self.controller.write(f"SOUR{channel}:FUNC {func}")
            self.controller.write(f"SOUR{channel}:VOLT {volt}")
            self.controller.write(f"SOUR{channel}:VOLT:OFFS {offs}")
            if func == "PULSe":
                self.controller.write(f"SOUR{channel}:PULS:WIDT {width}")
            self.controller.write(f"OUTP{channel}:LOAD 50")
            self.controller.write(f"SOUR{channel}:FREQ {freq}")
            self.current_frequency[channel] = freq
            self.status(f"Channel {channel} settings applied, Frequency: {freq:.6f} Hz")
            if not self.independent and channel == 1:
                self.update_phase_from_delay()
            self.update_output_buttons()
        except Exception as e:
            messagebox.showerror("Error", f"Set settings failed (Channel {channel}): {e}")

    def read_settings(self, channel):
        if self.controller.gen is None:
            self.toggle_connection()
            if self.controller.gen is None:
                return
        try:
            func = self.controller.query(f"SOUR{channel}:FUNC?").strip()
            freq = self.controller.query(f"SOUR{channel}:FREQ?").strip()
            volt = self.controller.query(f"SOUR{channel}:VOLT?").strip()
            offs = self.controller.query(f"SOUR{channel}:VOLT:OFFS?").strip()
            width_resp = self.controller.query(f"SOUR{channel}:PULS:WIDT?").strip()
            width_ns = float(width_resp) * 1e9
            self.entries_ch[channel]["Frequency (Hz):"].delete(0, tk.END)
            self.entries_ch[channel]["Frequency (Hz):"].insert(0, self.format_value(freq))
            self.entries_ch[channel]["Amplitude (Vpp):"].delete(0, tk.END)
            self.entries_ch[channel]["Amplitude (Vpp):"].insert(0, self.format_value(volt))
            self.entries_ch[channel]["Offset (V):"].delete(0, tk.END)
            self.entries_ch[channel]["Offset (V):"].insert(0, self.format_value(offs))
            self.entries_ch[channel]["Pulse Width (ns):"].delete(0, tk.END)
            self.entries_ch[channel]["Pulse Width (ns):"].insert(0, self.format_value(width_ns))
            self.func_var_ch[channel].set(func)
            self.current_frequency[channel] = float(freq)
            self.status(f"Channel {channel} settings read from device")
            outp_state = self.controller.query(f"OUTP{channel}?").strip()
            if outp_state in ("1", "ON"):
                self.generator_on[channel] = True
                if channel == 1:
                    self.gen_button1.config(text="Channel 1 ON", bg="green")
                else:
                    self.gen_button2.config(text="Channel 2 ON", bg="green")
            else:
                self.generator_on[channel] = False
                if channel == 1:
                    self.gen_button1.config(text="Channel 1 OFF", bg="red")
                else:
                    self.gen_button2.config(text="Channel 2 OFF", bg="red")
            if not self.independent and channel == 1:
                self.update_phase_from_delay()
        except Exception as e:
            messagebox.showerror("Error", f"Read settings failed (Channel {channel}): {e}")

    def apply_from_ch1(self):
        if self.controller.gen is None:
            return
        try:
            freq = float(self.entries_ch[1]["Frequency (Hz):"].get())
            volt = float(self.entries_ch[1]["Amplitude (Vpp):"].get())
            offs = float(self.entries_ch[1]["Offset (V):"].get())
            width_ns = float(self.entries_ch[1]["Pulse Width (ns):"].get())
            width = width_ns * 1e-9
            func = self.func_var_ch[1].get()
            self.entries_ch[2]["Frequency (Hz):"].delete(0, tk.END)
            self.entries_ch[2]["Frequency (Hz):"].insert(0, self.format_value(freq))
            self.entries_ch[2]["Amplitude (Vpp):"].delete(0, tk.END)
            self.entries_ch[2]["Amplitude (Vpp):"].insert(0, self.format_value(volt))
            self.entries_ch[2]["Offset (V):"].delete(0, tk.END)
            self.entries_ch[2]["Offset (V):"].insert(0, self.format_value(offs))
            self.entries_ch[2]["Pulse Width (ns):"].delete(0, tk.END)
            self.entries_ch[2]["Pulse Width (ns):"].insert(0, self.format_value(width_ns))
            self.func_var_ch[2].set(func)
            self.controller.write(f"SOUR2:FUNC {func}")
            self.controller.write(f"SOUR2:VOLT {volt}")
            self.controller.write(f"SOUR2:VOLT:OFFS {offs}")
            if func == "PULSe":
                self.controller.write(f"SOUR2:PULS:WIDT {width}")
            self.controller.write(f"OUTP2:LOAD 50")
            self.controller.write(f"SOUR2:FREQ {freq}")
            self.current_frequency[2] = freq
            self.status("Channel 2 parameters applied from Channel 1")
            self.update_output_buttons()
        except Exception as e:
            messagebox.showerror("Error", f"Apply from Channel 1 failed: {e}")

    def toggle_generator(self, channel):
        if self.controller.gen is None:
            self.toggle_connection()
            if self.controller.gen is None:
                return
        try:
            if not self.generator_on[channel]:
                self.controller.write(f"OUTP{channel} ON")
                self.generator_on[channel] = True
                if channel == 1:
                    self.gen_button1.config(text="Channel 1 ON", bg="green")
                else:
                    self.gen_button2.config(text="Channel 2 ON", bg="green")
                self.status(f"Channel {channel} ON")
            else:
                self.controller.write(f"OUTP{channel} OFF")
                self.generator_on[channel] = False
                if channel == 1:
                    self.gen_button1.config(text="Channel 1 OFF", bg="red")
                else:
                    self.gen_button2.config(text="Channel 2 OFF", bg="red")
                self.status(f"Channel {channel} OFF")
        except Exception as e:
            messagebox.showerror("Error", f"Generator toggle error (Channel {channel}): {e}")

    def update_output_buttons(self):
        for channel in (1, 2):
            try:
                outp_state = self.controller.query(f"OUTP{channel}?").strip()
                if outp_state in ("1", "ON"):
                    self.generator_on[channel] = True
                    if channel == 1:
                        self.gen_button1.config(text="Channel 1 ON", bg="green")
                    else:
                        self.gen_button2.config(text="Channel 2 ON", bg="green")
                else:
                    self.generator_on[channel] = False
                    if channel == 1:
                        self.gen_button1.config(text="Channel 1 OFF", bg="red")
                    else:
                        self.gen_button2.config(text="Channel 2 OFF", bg="red")
            except:
                pass

    def adjust_frequency(self, channel, step):
        try:
            current = float(self.entries_ch[channel]["Frequency (Hz):"].get())
            new_freq = current + step
            self.entries_ch[channel]["Frequency (Hz):"].delete(0, tk.END)
            self.entries_ch[channel]["Frequency (Hz):"].insert(0, self.format_value(new_freq))
            if self.controller.gen is not None:
                self.controller.write(f"SOUR{channel}:FREQ {new_freq}")
                self.current_frequency[channel] = new_freq
                self.status(f"Channel {channel} frequency adjusted to {new_freq:.6f} Hz")
                if not self.independent and channel == 1:
                    self.update_phase_from_delay()
        except Exception as e:
            messagebox.showerror("Error", f"Adjust frequency failed (Channel {channel}): {e}")

    def update_phase_from_delay(self):
        try:
            delay_ns = self.delay_ns_var.get()
            freq_hz = self.current_frequency[1]
            phase = (delay_ns * 1e-9) * freq_hz * 360.0
            phase = phase % 360.0
            self.phase_deg = phase
            self.phase_label.config(text=f"{phase:.2f}")
            if self.controller.gen is not None:
                self.controller.write(f"SOUR2:PHASe {phase}")
        except Exception as e:
            messagebox.showerror("Error", f"Phase update failed: {e}")

    def start_scan(self):
        if self.controller.gen is None:
            self.toggle_connection()
            if self.controller.gen is None:
                return
        try:
            f_start = float(self.start_entry.get())
            f_end = float(self.end_entry.get())
            f_step = float(self.step_entry.get())
            pause = float(self.pause_entry.get())
        except Exception as e:
            messagebox.showerror("Error", f"Invalid scan parameters: {e}")
            return

        def scan_thread():
            self.current_frequency[1] = f_start
            self.scan_running = True
            self.scan_paused = False
            while self.scan_running and self.current_frequency[1] <= f_end:
                if not self.scan_paused:
                    self.controller.write(f"SOUR1:FREQ {self.current_frequency[1]}")
                    if not self.independent:
                        self.update_phase_from_delay()
                    self.status(f"Scan Ch1: {self.current_frequency[1]:.6f} Hz")
                    time.sleep(pause)
                    self.current_frequency[1] += f_step
                else:
                    time.sleep(0.1)
            self.status("Scan completed")

        threading.Thread(target=scan_thread, daemon=True).start()

    def stop_scan(self):
        try:
            self.scan_running = False
            self.status("Scan stopped")
        except:
            pass

    def resume_scan(self):
        try:
            self.scan_paused = False
            self.status("Scan resumed")
        except:
            pass

    def format_value(self, value):
        try:
            num = float(value)
            if abs(num) >= 1000 or abs(num) < 0.01:
                return f"{num:.6g}"
            else:
                return f"{num:.4f}".rstrip('0').rstrip('.')
        except:
            return value

    def status(self, message):
        try:
            self.status_label.config(text=message)
        except:
            pass
