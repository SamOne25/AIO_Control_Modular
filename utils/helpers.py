import tkinter as tk
import numpy as np

def get_best_unit(y: np.ndarray) -> str:
    if y is None or len(y) == 0:
        return "V"
    m = np.nanmax(np.abs(y))
    if m < 1e-3:
        return "uV"
    elif m < 1:
        return "mV"
    return "V"

def nice_divisor(value: float) -> float:
    if value <= 0:
        return 1.0
    exp = np.floor(np.log10(value))
    mant = value / (10 ** exp)
    if mant <= 1:
        nice = 1
    elif mant <= 2:
        nice = 2
    elif mant <= 5:
        nice = 5
    else:
        nice = 10
    return nice * (10 ** exp)

def format_rec_length(n: int) -> str:
    if n >= 1_000_000:
        v = n / 1_000_000
        return f"{int(v)}M" if v.is_integer() else f"{v:.1f}M"
    if n >= 1_000:
        v = n / 1_000
        return f"{int(v)}k" if v.is_integer() else f"{v:.1f}k"
    return str(n)

def convert_volts_to_display(val_v: float) -> tuple[float, str]:
    if abs(val_v) >= 1:
        return val_v, "V"
    if abs(val_v) >= 1e-3:
        return val_v * 1e3, "mV"
    return val_v * 1e6, "uV"


################################OSA###################################

def integration_string_to_hz(integ_str):
    mapping = {
        "1MHz": 1_000_000,
        "100kHz": 100_000,
        "10kHz": 10_000,
        "1kHz": 1_000,
        "100Hz": 100,
        "10Hz": 10
    }
    return mapping.get(integ_str, 1000)


SMT_OPTIONS = ["OFF", "3", "5", "7", "9", "11"]



class CreateToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self.showtip)
        widget.bind("<Leave>", self.hidetip)

    def showtip(self, _=None):
        if self.tipwindow or not self.text:
            return
        bbox = self.widget.bbox("insert")
        if bbox:
            x, y, cx, cy = bbox
            x = x + self.widget.winfo_rootx() + 25
            y = y + cy + self.widget.winfo_rooty() + 25
        else:
            x = self.widget.winfo_rootx() + 20
            y = self.widget.winfo_rooty() + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=("tahoma", 8),
            justify="left",
        )
        label.pack(ipadx=4, ipady=2)

    def hidetip(self, _=None):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None

def get_lin_unit_and_data(data):
    absmax = np.nanmax(np.abs(data))
    if absmax >= 1e-3:
        return "mW", data * 1e3
    if absmax >= 1e-6:
        return "µW", data * 1e6
    if absmax >= 1e-9:
        return "nW", data * 1e9
    return "W", data

