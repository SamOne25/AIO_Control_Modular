import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox
import numpy as np
import json, os
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import random

# Verfügbare Linienstile und Marker
LINE_STYLES   = ["-", "--", "-.", ":", "None"]
MARKER_STYLES = ["None", "o", "s", "^", "v", "D", "*", ".", "x", "+"]

class PlotViewer(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.curve_tabs   = []
        self.curve_config = []
        self._build_gui()
        self._create_plot()
        self._add_curve_tab(initial=True)

    def _build_gui(self):
        main_frame = ttk.Frame(self)
        main_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        # Global Plot Settings
        global_frame = ttk.LabelFrame(main_frame, text="Global Plot Settings")
        global_frame.pack(fill=tk.X, pady=5)

        ttk.Label(global_frame, text="Plot Title").grid(row=0, column=0, sticky="w")
        self.title_entry = ttk.Entry(global_frame)
        self.title_entry.insert(0, "My Plot")
        self.title_entry.grid(row=0, column=1, sticky="ew")
        self.title_entry.bind("<KeyRelease>", lambda e: self._update_plot())

        ttk.Label(global_frame, text="X Label").grid(row=1, column=0, sticky="w")
        self.xlabel_entry = ttk.Entry(global_frame)
        self.xlabel_entry.insert(0, "X")
        self.xlabel_entry.grid(row=1, column=1, sticky="ew")
        self.xlabel_entry.bind("<KeyRelease>", lambda e: self._update_plot())

        ttk.Label(global_frame, text="Y Label").grid(row=2, column=0, sticky="w")
        self.ylabel_entry = ttk.Entry(global_frame)
        self.ylabel_entry.insert(0, "Y")
        self.ylabel_entry.grid(row=2, column=1, sticky="ew")
        self.ylabel_entry.bind("<KeyRelease>", lambda e: self._update_plot())

        ttk.Label(global_frame, text="Tick Font Size").grid(row=3, column=0, sticky="w")
        self.tick_font_size = tk.StringVar(value="10")
        cb_ticks = ttk.Combobox(global_frame, textvariable=self.tick_font_size,
                                values=["8","10","12","14","16"], state="readonly")
        cb_ticks.grid(row=3, column=1)
        cb_ticks.bind("<<ComboboxSelected>>", lambda e: self._update_plot())

        ttk.Label(global_frame, text="Label Font Size").grid(row=4, column=0, sticky="w")
        self.label_font_size = tk.StringVar(value="12")
        cb_labels = ttk.Combobox(global_frame, textvariable=self.label_font_size,
                                 values=["10","12","14","16","18"], state="readonly")
        cb_labels.grid(row=4, column=1)
        cb_labels.bind("<<ComboboxSelected>>", lambda e: self._update_plot())

        ttk.Button(global_frame, text="Add Curve", command=self._add_curve_tab) \
            .grid(row=5, column=0, columnspan=2, pady=5)

        # Curve Settings Tabs
        self.curve_tab_frame = ttk.LabelFrame(main_frame, text="Curve Settings")
        self.curve_tab_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        self.curve_notebook = ttk.Notebook(self.curve_tab_frame)
        self.curve_notebook.pack(fill=tk.BOTH, expand=True)

        # Metadata Frame
        self.meta_frame = ttk.LabelFrame(main_frame, text="Metadata")
        self.meta_frame.pack(fill=tk.X, pady=(5,10))

    def _create_plot(self):
        self.fig, self.ax = plt.subplots()
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    def _add_curve_tab(self, initial=False):
            idx = len(self.curve_tabs)
            frame = ttk.Frame(self.curve_notebook)
            self.curve_notebook.add(frame, text=f"Curve {idx+1}")
            self.curve_tabs.append(frame)
    
            # 1) Farbe: erste immer 'blue', danach random
            default_color = "blue" if idx == 0 else f"#{random.randint(0,0xFFFFFF):06x}"
    
            cfg = {
                "file": None,
                "data": None,
                "x_idx": tk.StringVar(value="Column 1"),
                "y_idx": tk.StringVar(value="Column 2"),
                "label": tk.StringVar(value=f"Curve {idx+1}"),
                "color": tk.StringVar(value=default_color),
                "style": tk.StringVar(value=LINE_STYLES[0]),
                "marker": tk.StringVar(value=MARKER_STYLES[0]),  # default "None"
                "frame": frame,
                "info_label": None,
                "x_dropdown": None,
                "y_dropdown": None
            }
            self.curve_config.append(cfg)
    
            # 2) Button-Frame für Load + Delete nebeneinander
            btn_frame = ttk.Frame(frame)
            btn_frame.pack(pady=4)
    
            ttk.Button(btn_frame, text="Load .npy File",
                       command=lambda i=idx: self._load_file(i)) \
                .pack(side=tk.LEFT)
    
            if not initial:
                ttk.Button(btn_frame, text="Delete Curve",
                           command=lambda i=idx: self._delete_curve_tab(i)) \
                    .pack(side=tk.LEFT, padx=6)
    
            # 3) Rest der Controls
            ttk.Label(frame, text="Legend Label").pack()
            ent_lbl = ttk.Entry(frame, textvariable=cfg["label"])
            ent_lbl.pack()
            ent_lbl.bind("<KeyRelease>", lambda e: self._update_plot())
    
            ttk.Label(frame, text="Line Color").pack()
            ttk.Button(frame, text="Choose Color",
                       command=lambda i=idx: self._choose_color(i)).pack(pady=2)
    
            ttk.Label(frame, text="Line Style").pack()
            cb_ls = ttk.Combobox(frame, textvariable=cfg["style"],
                                 values=LINE_STYLES, state="readonly")
            cb_ls.pack()
            cb_ls.bind("<<ComboboxSelected>>", lambda e: self._update_plot())
    
            ttk.Label(frame, text="Marker Style").pack()
            cb_mk = ttk.Combobox(frame, textvariable=cfg["marker"],
                                 values=MARKER_STYLES, state="readonly")
            cb_mk.pack()
            cb_mk.bind("<<ComboboxSelected>>", lambda e: self._update_plot())
    
            cfg["info_label"] = ttk.Label(frame, text="No file loaded.")
            cfg["info_label"].pack(pady=4)


    def _delete_curve_tab(self, idx):
        if idx == 0:
            messagebox.showinfo("Info", "Curve 1 cannot be deleted.")
            return
        self.curve_notebook.forget(self.curve_tabs[idx])
        self.curve_tabs.pop(idx)
        self.curve_config.pop(idx)
        self._update_plot()

    def _choose_color(self, idx):
        col = colorchooser.askcolor(title="Choose line color")[1]
        if col:
            self.curve_config[idx]["color"].set(col)
            self._update_plot()

    
    def _load_file(self, idx):
        cfg = self.curve_config[idx]
    
        # ─── Alte Array-Daten und UI-Elemente löschen ────────────────────
        cfg["file"] = None
        cfg["data"] = None
    
        if cfg["x_dropdown"]:
            cfg["x_dropdown"].destroy()
            cfg["x_dropdown"] = None
        if cfg["y_dropdown"]:
            cfg["y_dropdown"].destroy()
            cfg["y_dropdown"] = None
    
        # Info-Label zurücksetzen
        cfg["info_label"].config(text="No file loaded.")
    
        # Metadaten-Anzeige leeren
        for w in self.meta_frame.winfo_children():
            w.destroy()
    
        # a) Datei auswählen
        fp = filedialog.askopenfilename(
            filetypes=[("NumPy Array (.npy)", "*.npy"),
                       ("NumPy ZIP (.npz)", "*.npz")]
        )
        if not fp:
            return
    
        # b) Daten laden
        base, ext = os.path.splitext(fp)
        ext = ext.lower()
        if ext == ".npz":
            npz = np.load(fp, allow_pickle=True)
            if "data" not in npz:
                messagebox.showerror("Format Error", "NPZ has no 'data' array")
                return
            data = npz["data"]
        else:
            data = np.load(fp)
    
        # c) Transponieren falls nötig
        if not (data.ndim == 2 and data.shape[1] >= 2):
            messagebox.showerror("Format Error", "Data must be 2D with ≥2 columns")
            return
        if data.shape[0] < data.shape[1]:
            data = data.T
    
        # d) config updaten
        cfg["file"] = fp
        cfg["data"] = data
    
        # e) Spaltennamen aus JSON/NPZ holen (oder fallback)
        cols = None
        json_path = base + ".json"
        if os.path.exists(json_path):
            try:
                meta = json.load(open(json_path, "r", encoding="utf-8"))
                cols = meta.get("columns")
            except:
                pass
        if not cols and ext == ".npz":
            try:
                cols = npz["columns"].tolist()
            except:
                pass
        if not cols:
            cols = [f"Column {i+1}" for i in range(data.shape[1])]
        cfg["columns"] = cols
    
        # f) X-Dropdown + sofortiges Update von xlabel
        ttk.Label(cfg["frame"], text="X Values:").pack()
        xcb = ttk.Combobox(cfg["frame"],
                           textvariable=cfg["x_idx"],
                           values=cols, state="readonly")
        xcb.pack()
        cfg["x_idx"].set(cols[0])
        xcb.bind("<<ComboboxSelected>>", lambda e: (
            self.xlabel_entry.delete(0, "end"),
            self.xlabel_entry.insert(0, cfg["x_idx"].get()),
            self._update_plot()
        ))
        cfg["x_dropdown"] = xcb
    
        # g) Y-Dropdown + sofortiges Update von ylabel
        ttk.Label(cfg["frame"], text="Y Values:").pack()
        ycb = ttk.Combobox(cfg["frame"],
                           textvariable=cfg["y_idx"],
                           values=cols, state="readonly")
        ycb.pack()
        cfg["y_idx"].set(cols[1] if len(cols)>1 else cols[0])
        ycb.bind("<<ComboboxSelected>>", lambda e: (
            self.ylabel_entry.delete(0, "end"),
            self.ylabel_entry.insert(0, cfg["y_idx"].get()),
            self._update_plot()
        ))
        cfg["y_dropdown"] = ycb
    
        # h) Info-Label aktualisieren
        cfg["info_label"].config(
            text=f"Loaded {os.path.basename(fp)}\n"
                 f"{data.shape[0]} rows × {data.shape[1]} cols"
        )
    
        # i) Metadaten anzeigen (falls JSON da ist)
        if os.path.exists(json_path):
            try:
                meta = json.load(open(json_path, "r", encoding="utf-8"))
                self._update_metadata(meta)
            except:
                pass
    
        # j) Plot updaten
        self._update_plot()



    def _update_plot(self):
        self.ax.clear()
        for cfg in self.curve_config:
            data = cfg.get("data")
            if data is None:
                continue
            try:
                cols = cfg["columns"]
                xi   = cols.index(cfg["x_idx"].get())
                yi   = cols.index(cfg["y_idx"].get())
                x    = data[:, xi]
                y    = data[:, yi]
                ls   = None if cfg["style"].get()=="None" else cfg["style"].get()
                mk   = None if cfg["marker"].get()=="None" else cfg["marker"].get()
                self.ax.plot(x, y,
                             label=cfg["label"].get(),
                             color=cfg["color"].get(),
                             linestyle=ls,
                             marker=mk)
            except Exception as e:
                messagebox.showwarning("Plot Warning", f"Curve skipped: {e}")

        lf = int(self.label_font_size.get())
        tf = int(self.tick_font_size.get())
        self.ax.set_title(self.title_entry.get(), fontsize=lf)
        self.ax.set_xlabel(self.xlabel_entry.get(), fontsize=lf)
        self.ax.set_ylabel(self.ylabel_entry.get(), fontsize=lf)
        self.ax.tick_params(labelsize=tf)
        self.ax.grid(True)
        self.ax.legend()
        self.canvas.draw()


    def _update_metadata(self, meta: dict):
        # clear
        for w in self.meta_frame.winfo_children():
            w.destroy()

        # extract units, remove date/time
        units_map = meta.pop("param_units", {})
        meta.pop("date",None)
        meta.pop("time",None)

        # display
        for row, (key,val) in enumerate(meta.items()):
            disp = key.replace("_"," ").capitalize()
            unit = units_map.get(key,"")
            if unit:
                disp = f"{disp} [{unit}]"
            ttk.Label(self.meta_frame, text=f"{disp}:")\
               .grid(row=row, column=0, sticky="w", padx=4, pady=1)
            ttk.Label(self.meta_frame, text=str(val))\
               .grid(row=row, column=1, sticky="w", padx=4, pady=1)




   