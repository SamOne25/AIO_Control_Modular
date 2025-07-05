import numpy as np
import time
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import List
import json
import os
from pathlib import Path



#------SCOPE------------------------------------------------------------------
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
    if absmax < 1e-9:
        return "pW", data * 1e9
    elif absmax < 1e-6:
        return "nW", data * 1e6
    elif absmax < 1e-3:
        return "µW", data * 1e3
    return "mW", data



def append_event(event_log: List[str], text_widget: tk.Text,
                 direction: str, message: str) -> None:
    """
    Fügt einen Eintrag zu event_log hinzu und schreibt ihn in das Text-Widget.
    :param event_log: Liste aller bisherigen Log-Einträge
    :param text_widget: tk.Text-Widget, in das die Zeilen geschrieben werden
    :param direction: z.B. "SEND", "RESPONSE", "PEAK"
    :param message: der eigentliche Text des Events
    """
    ts = time.strftime('%H:%M:%S')
    entry = f"[{ts}] {direction}: {message}\n"
    event_log.append(entry)
    text_widget.insert("end", entry)
    text_widget.see("end")


def save_event_log(event_log: List[str]) -> None:
    """
    Öffnet einen Save-Dialog und schreibt event_log in die ausgewählte Datei.
    """
    fname = filedialog.asksaveasfilename(defaultextension=".txt",
                                         filetypes=[("Text files","*.txt")])
    if not fname:
        return
    try:
        with open(fname, "w") as f:
            f.writelines(event_log)
        messagebox.showinfo("Event Log", f"{len(event_log)} Einträge gespeichert:\n{fname}")
    except Exception as e:
        messagebox.showerror("Save Error", f"Konnte Log nicht speichern:\n{e}")
        
def meta_daten(
    resolution: str,
    integration: str,
    span: str,
    frequency: str,
    points: str,
    offset: str,
    reference_lvl: str,
    central_wl: str,
    *,
    voltage: str = None,
    fiberlen: str = None,
    scan_start: str = None,
    scan_stop: str = None,
    scan_step: str = None,
    instrument: str = None,
    notes: str = None,
    **additional
) -> dict:
    now = datetime.now()
    # 1) Basis-Metadaten
    meta = {
        "timestamp":     now.isoformat(sep=" "),
        "resolution":    str(resolution),
        "integration":   str(integration),
        "span":          str(span),
        "frequency":     str(frequency),
        "points":        str(points),
        "offset":        str(offset),
        "reference_lvl": str(reference_lvl),
        "central_wl":    str(central_wl),
    }

    # 2) Optionale Parameter  
    for key, val in [
        ("voltage",    voltage),
        ("fiberlen",   fiberlen),
        ("scan_start", scan_start),
        ("scan_stop",  scan_stop),
        ("scan_step",  scan_step),
        ("instrument", instrument),
        ("notes",      notes),
    ]:
        if val is not None:
            meta[key] = str(val)

    # 3) Einheitentabelle für die Parameter  
    meta["param_units"] = {
        "resolution":    "nm",
        "integration":   "Hz",
        "span":          "nm",
        "frequency":     "Hz",
        "points":        "",    # rein nummerisch
        "offset":        "dB",
        "reference_lvl": "dBm",
        "central_wl":    "nm",
        "voltage":       "V",
        "fiberlen":      "km",
        "scan_start":    "Hz",
        "scan_stop":     "Hz",
        "scan_step":     "Hz",
    }

    # 4) Beliebige Zusatzfelder
    for key, val in additional.items():
        if val is not None:
            meta[key] = str(val)

    return meta



def _get_next_index(folder: Path, prefix: str, ext: str) -> int:
    existing = list(folder.glob(f"{prefix}_*{ext}"))
    idxs = []
    for fn in existing:
        stem = fn.stem[len(prefix)+1:]  # remove "prefix_"
        parts = stem.split("_",1)
        if parts[0].isdigit():
            idxs.append(int(parts[0]))
    return max(idxs, default=0) + 1

def save_with_metadata(
    *,
    arr: np.ndarray = None,
    fig = None,
    columns: list[str] = None,
    units:   list[str] = None,
    metadata: dict,
    subfolder: str,
    fmt: str = "npz",
    json_notes: str = None
) -> None:
    """
    - arr + columns+units → npz oder npy
    - fig → png
    - metadata + columns+units + 'fields' → .json
    - Speicherort: measurements/YYYYMMDD/<subfolder>/
    - Dateinamen: {prefix}_{idx:04d}_{timestamp}.{ext}
      prefix = "Spektrum" (Sweep) oder "FreqScan" (Scan)
    """
    # Basis-Verzeichnis
    today = datetime.now().strftime("%Y%m%d")
    root  = Path(__file__).parent.parent / "measurements" / today / subfolder
    root.mkdir(parents=True, exist_ok=True)

    # prefix wählen
    prefix = "Spektrum" if subfolder.lower().startswith("spek") else "FreqScan"
    timestamp = datetime.now().strftime("%H%M%S")
    idx = _get_next_index(root, prefix, "." + (fmt if arr is not None else "png"))
    name = f"{prefix}_{idx:04d}_{timestamp}"

    # 1) speichern arr oder fig
    if arr is not None:
        if fmt == "npz":
            fname = root / f"{name}.npz"
            np.savez(fname, data=arr,
                     columns=np.array(columns, dtype='<U50'),
                     units  =np.array(units,   dtype='<U10'))
        else:  # fmt == "npy"
            fname = root / f"{name}.npy"
            np.save(fname, arr)
    else:
        # fig speichern
        fname = root / f"{name}.png"
        fig.savefig(fname, dpi=600, bbox_inches="tight")

    # 2) JSON-Seitenwagen
    meta = metadata.copy()
    meta["date"] = datetime.now().strftime("%Y-%m-%d")
    meta["time"] = datetime.now().strftime("%H:%M:%S")
    # Spalten/Units
    meta["columns"] = columns
    meta["units"]   = dict(zip(columns, units))
    # für jede Spalte eine lesbare Zeile
    meta["fields"] = { str(i+1): f"{columns[i]}, [{units[i]}]"
                       for i in range(len(columns)) }
    if json_notes:
        meta["notes"] = json_notes

    json_fname = root / f"{name}.json"
    with open(json_fname, "w", encoding="utf-8") as jf:
        json.dump(meta, jf, indent=2)

    messagebox.showinfo(
        "Saved",
        f"• Data: {fname.name}\n"
        f"• Meta: {json_fname.name}"
    )


def save_scan_data(
    arr: np.ndarray,
    resolution: str,
    integration: str,
    span: str,
    frequency: str,
    points: str,
    offset: str,
    reference_lvl: str,
    central_wl: str,
    *,
    voltage: str = None,
    fiberlen: str = None,
    scan_start: str = None,
    scan_stop: str = None,
    scan_step: str = None,
    instrument: str = None,
    notes: str = None,
    base_folder: str = "data"
) -> None:
    """
    Speichert Dein Mess-Array als .npz + begleitende .json im <base_folder>.
    """
    # Ordner anlegen
    project_root = Path(__file__).parent
    data_dir     = project_root / base_folder
    data_dir.mkdir(parents=True, exist_ok=True)

    # nächste Nummer + Timestamp
    next_idx  = _get_next_index(data_dir, suffix="", ext="npz")
    ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{next_idx:04d}_{ts}"

    # Datei‐Dialog
    fname = filedialog.asksaveasfilename(
        initialdir=str(data_dir),
        initialfile=base_name,
        defaultextension=".npz",
        filetypes=[("NumPy Zip","*.npz")]
    )
    if not fname:
        return

    # Spalten + Einheiten
    columns = ["wavelength_nm", "power_dbm", "power_linear"]
    units   = ["nm", "dBm", "mW"]  # hier mW statt W

    # .npz speichern
    np.savez(
        fname,
        data=arr,
        columns=np.array(columns, dtype='<U50'),
        units=np.array(units,    dtype='<U10')
    )

    # Meta-Daten zusammenstellen
    params = meta_daten(
        resolution    = resolution,
        integration   = integration,
        span          = span,
        frequency     = frequency,
        points        = points,
        offset        = offset,
        reference_lvl = reference_lvl,
        central_wl    = central_wl,
        voltage       = voltage,
        fiberlen      = fiberlen,
        scan_start    = scan_start,
        scan_stop     = scan_stop,
        scan_step     = scan_step,
        instrument    = instrument,
        notes         = notes,
    )
    params["columns"] = columns
    params["units"]   = dict(zip(columns, units))

    # .json‐Datei parallel speichern
    base, _    = os.path.splitext(fname)
    json_fname = base + ".json"
    with open(json_fname, "w", encoding="utf-8") as jf:
        json.dump(params, jf, indent=2)

    messagebox.showinfo(
        "Saved",
        f"Scan data saved:\n• NPZ:  {os.path.basename(fname)}\n"
        f"• JSON: {os.path.basename(json_fname)}"
    )

def save_linear_plot(
    fig,
    resolution: str,
    integration: str,
    span: str,
    frequency: str,
    points: str,
    offset: str,
    reference_lvl: str,
    central_wl: str,
    *,
    voltage: str = None,
    fiberlen: str = None,
    scan_start: str = None,
    scan_stop: str = None,
    scan_step: str = None,
    instrument: str = None,
    notes: str = "Linear plot",
    base_folder: str = "plots"
) -> None:
    """
    Speichert Deinen linearen Plot als .png + begleitende .json im <base_folder>.
    """
    project_root = Path(__file__).parent
    plots_dir    = project_root / base_folder
    plots_dir.mkdir(parents=True, exist_ok=True)

    idx       = _get_next_index(plots_dir, suffix="lin", ext="png")
    ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{idx:04d}_{ts}_lin"

    fname = filedialog.asksaveasfilename(
        initialdir=str(plots_dir),
        initialfile=base_name,
        defaultextension=".png",
        filetypes=[("PNG","*.png")]
    )
    if not fname:
        return

    fig.savefig(fname, dpi=600, bbox_inches="tight")

    columns = ["wavelength_nm", "power_dbm", "power_linear"]
    units   = ["nm", "dBm", "mW"]  # hier mW statt W

    params = meta_daten(
        resolution    = resolution,
        integration   = integration,
        span          = span,
        frequency     = frequency,
        points        = points,
        offset        = offset,
        reference_lvl = reference_lvl,
        central_wl    = central_wl,
        voltage       = voltage,
        fiberlen      = fiberlen,
        scan_start    = scan_start,
        scan_stop     = scan_stop,
        scan_step     = scan_step,
        instrument    = instrument,
        notes         = notes,
    )
    params["plot_type"] = "linear"
    params["columns"]   = columns
    params["units"]     = dict(zip(columns, units))

    base, _    = os.path.splitext(fname)
    json_fname = base + ".json"
    with open(json_fname, "w", encoding="utf-8") as jf:
        json.dump(params, jf, indent=2)

    messagebox.showinfo(
        "Saved",
        f"Linear plot saved:\n• PNG:  {os.path.basename(fname)}\n"
        f"• JSON: {os.path.basename(json_fname)}"
    )

def save_dbm_plot(
    fig,
    resolution: str,
    integration: str,
    span: str,
    frequency: str,
    points: str,
    offset: str,
    reference_lvl: str,
    central_wl: str,
    *,
    voltage: str = None,
    fiberlen: str = None,
    scan_start: str = None,
    scan_stop: str = None,
    scan_step: str = None,
    instrument: str = None,
    notes: str = "dBm plot",
    base_folder: str = "plots"
) -> None:
    """
    Speichert Deinen dBm-Plot als .png + begleitende .json im <base_folder>.
    """
    project_root = Path(__file__).parent
    plots_dir    = project_root / base_folder
    plots_dir.mkdir(parents=True, exist_ok=True)

    idx       = _get_next_index(plots_dir, suffix="dbm", ext="png")
    ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{idx:04d}_{ts}_dbm"

    fname = filedialog.asksaveasfilename(
        initialdir=str(plots_dir),
        initialfile=base_name,
        defaultextension=".png",
        filetypes=[("PNG","*.png")]
    )
    if not fname:
        return

    fig.savefig(fname, dpi=600, bbox_inches="tight")

    columns = ["wavelength_nm", "power_dbm", "power_linear"]
    units   = ["nm", "dBm", "mW"]  # hier mW statt W

    params = meta_daten(
        resolution    = resolution,
        integration   = integration,
        span          = span,
        frequency     = frequency,
        points        = points,
        offset        = offset,
        reference_lvl = reference_lvl,
        central_wl    = central_wl,
        voltage       = voltage,
        fiberlen      = fiberlen,
        scan_start    = scan_start,
        scan_stop     = scan_stop,
        scan_step     = scan_step,
        instrument    = instrument,
        notes         = notes,
    )
    params["plot_type"] = "dBm"
    params["columns"]   = columns
    params["units"]     = dict(zip(columns, units))

    base, _    = os.path.splitext(fname)
    json_fname = base + ".json"
    with open(json_fname, "w", encoding="utf-8") as jf:
        json.dump(params, jf, indent=2)

    messagebox.showinfo(
        "Saved",
        f"dBm plot saved:\n• PNG:  {os.path.basename(fname)}\n"
        f"• JSON: {os.path.basename(json_fname)}"
    )
    
