import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

LINE_STYLES = ["-", "--", "-.", ":"]

class PlotViewer(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        self.datasets = []
        self.curve_tabs = []
        self.curve_config = []

        self._build_gui()
        self._create_plot()
        self._add_curve_tab(initial=True)  # Ensure at least one tab exists

    def _build_gui(self):
        main_frame = ttk.Frame(self)
        main_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        global_frame = ttk.LabelFrame(main_frame, text="Global Plot Settings")
        global_frame.pack(fill=tk.X, pady=5)

        ttk.Label(global_frame, text="Plot Title").grid(row=0, column=0, sticky="w")
        self.title_entry = ttk.Entry(global_frame)
        self.title_entry.insert(0, "My Plot")
        self.title_entry.grid(row=0, column=1, sticky="ew")

        ttk.Label(global_frame, text="X Label").grid(row=1, column=0, sticky="w")
        self.xlabel_entry = ttk.Entry(global_frame)
        self.xlabel_entry.insert(0, "X")
        self.xlabel_entry.grid(row=1, column=1, sticky="ew")

        ttk.Label(global_frame, text="Y Label").grid(row=2, column=0, sticky="w")
        self.ylabel_entry = ttk.Entry(global_frame)
        self.ylabel_entry.insert(0, "Y")
        self.ylabel_entry.grid(row=2, column=1, sticky="ew")

        ttk.Label(global_frame, text="Tick Font Size").grid(row=3, column=0, sticky="w")
        self.tick_font_size = tk.StringVar(value="10")
        ttk.Combobox(global_frame, textvariable=self.tick_font_size, values=["8", "10", "12", "14", "16"]).grid(row=3, column=1)

        ttk.Label(global_frame, text="Label Font Size").grid(row=4, column=0, sticky="w")
        self.label_font_size = tk.StringVar(value="12")
        ttk.Combobox(global_frame, textvariable=self.label_font_size, values=["10", "12", "14", "16", "18"]).grid(row=4, column=1)

        ttk.Button(global_frame, text="Add Curve", command=self._add_curve_tab).grid(row=5, column=0, columnspan=2, pady=5)

        self.curve_tab_frame = ttk.LabelFrame(main_frame, text="Curve Settings")
        self.curve_tab_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.curve_notebook = ttk.Notebook(self.curve_tab_frame)
        self.curve_notebook.pack(fill=tk.BOTH, expand=True)

        ttk.Button(main_frame, text="Update Plot", command=self._update_plot).pack(pady=5)

    def _create_plot(self):
        self.fig, self.ax = plt.subplots()
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    def _add_curve_tab(self, initial=False):
        idx = len(self.curve_tabs)
        frame = ttk.Frame(self.curve_notebook)
        self.curve_notebook.add(frame, text=f"Curve {idx+1}")
        self.curve_tabs.append(frame)

        config = {
            "file": None,
            "data": None,
            "x_idx": tk.StringVar(value="0"),
            "y_idx": tk.StringVar(value="1"),
            "label": tk.StringVar(value=f"Curve {idx+1}"),
            "color": tk.StringVar(value="blue"),
            "style": tk.StringVar(value="-"),
            "x": None,
            "y": None,
            "x_dropdown": None,
            "y_dropdown": None,
            "frame": frame,
            "info_label": None,
        }
        self.curve_config.append(config)

        ttk.Button(frame, text="Load .npy File", command=lambda idx=idx: self._load_file(idx)).pack(pady=2)
        ttk.Label(frame, text="Legend Label").pack()
        ttk.Entry(frame, textvariable=config["label"]).pack()
        ttk.Label(frame, text="Line Color").pack()
        ttk.Button(frame, text="Choose Color", command=lambda idx=idx: self._choose_color(idx)).pack(pady=2)
        ttk.Label(frame, text="Line Style").pack()
        ttk.Combobox(frame, textvariable=config["style"], values=LINE_STYLES, state="readonly").pack()
        config["info_label"] = ttk.Label(frame, text="No file loaded.")
        config["info_label"].pack(pady=4)

        if not initial:
            ttk.Button(frame, text="Delete Curve", command=lambda idx=idx: self._delete_curve_tab(idx)).pack(pady=5)

    def _delete_curve_tab(self, idx):
        if idx == 0:
            messagebox.showinfo("Info", "Curve 1 cannot be deleted.")
            return
        self.curve_notebook.forget(self.curve_tabs[idx])
        self.curve_tabs.pop(idx)
        self.curve_config.pop(idx)
        self._update_plot()

    def _choose_color(self, idx):
        color = colorchooser.askcolor(title="Choose line color")[1]
        if color:
            self.curve_config[idx]["color"].set(color)

    def _load_file(self, idx):
        file_path = filedialog.askopenfilename(filetypes=[("NumPy Arrays", "*.npy")])
        if file_path:
            try:
                data = np.load(file_path)
                if data.shape[0] < data.shape[1]:
                    data = data.T
                if data.ndim == 2 and data.shape[0] >= 2:
                    self.curve_config[idx]["file"] = file_path
                    self.curve_config[idx]["data"] = data
                    options = [f"Column {i+1}" for i in range(data.shape[1])]

                    cfg = self.curve_config[idx]
                    cfg["x_idx"].set("Column 1")
                    cfg["y_idx"].set("Column 2")

                    # Ersetze ggf. alte Dropdowns
                    if cfg["x_dropdown"]:
                        cfg["x_dropdown"].destroy()
                    if cfg["y_dropdown"]:
                        cfg["y_dropdown"].destroy()

                    frame = self.curve_tabs[idx]
                    ttk.Label(frame, text="X Values:").pack()
                    x_menu = ttk.Combobox(frame, textvariable=cfg["x_idx"], values=options, state="readonly")
                    x_menu.pack()
                    ttk.Label(frame, text="Y Values:").pack()
                    y_menu = ttk.Combobox(frame, textvariable=cfg["y_idx"], values=options, state="readonly")
                    y_menu.pack()

                    cfg["x_dropdown"] = x_menu
                    cfg["y_dropdown"] = y_menu

                    if cfg["info_label"]:
                        text_msg = (f"Read in successful!"
                                    f"Dimensions → Rows: {data.shape[0]}, Columns: {data.shape[1]}")
                        cfg["info_label"].config(text=text_msg)

                    self._update_plot()
                else:
                    messagebox.showerror("Format Error", "Expected shape (2+, N) for column-based data")
            except Exception as e:
                messagebox.showerror("Load Error", f"Could not load file: {e}")

    def _update_plot(self):
        if not hasattr(self, 'canvas') or self.canvas is None:
            return
        self.ax.clear()
        for cfg in self.curve_config:
            data = cfg.get("data")
            if data is not None:
                try:
                    x_idx = int(cfg["x_idx"].get().replace("Column ", "")) - 1
                    y_idx = int(cfg["y_idx"].get().replace("Column ", "")) - 1
                    if x_idx < data.shape[0] and y_idx < data.shape[0]:
                        x = data[:, x_idx]
                        y = data[:, y_idx]
                        cfg["x"] = x
                        cfg["y"] = y
                        self.ax.plot(x, y,
                                     label=cfg["label"].get(),
                                     color=cfg["color"].get(),
                                     linestyle=cfg["style"].get())
                except Exception as e:
                    messagebox.showwarning("Plot Warning", f"Curve skipped: {e}")

        self.ax.set_title(self.title_entry.get(), fontsize=int(self.label_font_size.get()))
        self.ax.set_xlabel(self.xlabel_entry.get(), fontsize=int(self.label_font_size.get()))
        self.ax.set_ylabel(self.ylabel_entry.get(), fontsize=int(self.label_font_size.get()))
        self.ax.tick_params(labelsize=int(self.tick_font_size.get()))
        self.ax.grid(True)
        self.ax.legend()
        self.canvas.draw()
