import os
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

LINE_STYLES = ["-", "--", "-.", ":"]
LEGEND_LOCATIONS = [
    "best", "upper right", "upper left", "lower left", "lower right",
    "right", "center left", "center right", "lower center", "upper center", "center"
]

class PlotViewer(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.curve_tabs = []
        self.curve_config = []
        self._build_gui()
        self._create_plot()
        self._add_curve_tab(initial=True)

    def _build_gui(self):
        # Left-hand controls
        main_frame = ttk.Frame(self)
        main_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        # Global plot settings
        global_frame = ttk.LabelFrame(main_frame, text="Global Plot Settings")
        global_frame.pack(fill=tk.X, pady=5)

        # Plot type selector
        ttk.Label(global_frame, text="Plot Type").grid(row=0, column=0, sticky="w")
        self.plot_type = tk.StringVar(value="1 Plot")
        pt_cb = ttk.Combobox(global_frame, textvariable=self.plot_type,
                             values=["1 Plot", "Subplot"], state="readonly")
        pt_cb.grid(row=0, column=1, sticky="ew")
        self.plot_type.trace_add('write', lambda *a: self._update_subplots_ui())

        # Number of subplots (hidden unless "Subplot" chosen)
        self.num_subplots = tk.IntVar(value=2)
        self.num_subplots_cb = ttk.Combobox(
            global_frame,
            textvariable=self.num_subplots,
            values=[str(i) for i in range(2, 11)],
            state="readonly"
        )
        self.num_subplots_cb.grid(row=0, column=2, sticky="ew")
        self.num_subplots_cb.grid_remove()
        self.num_subplots.trace_add('write', lambda *a: self._rebuild_subplots())

        # Plot title
        ttk.Label(global_frame, text="Plot Title").grid(row=1, column=0, sticky="w")
        self.title_entry = ttk.Entry(global_frame)
        self.title_entry.insert(0, "My Plot")
        self.title_entry.grid(row=1, column=1, columnspan=2, sticky="ew")

        # X label
        ttk.Label(global_frame, text="X Label").grid(row=2, column=0, sticky="w")
        self.xlabel_entry = ttk.Entry(global_frame)
        self.xlabel_entry.insert(0, "X")
        self.xlabel_entry.grid(row=2, column=1, columnspan=2, sticky="ew")

        # Y label
        ttk.Label(global_frame, text="Y Label").grid(row=3, column=0, sticky="w")
        self.ylabel_entry = ttk.Entry(global_frame)
        self.ylabel_entry.insert(0, "Y")
        self.ylabel_entry.grid(row=3, column=1, columnspan=2, sticky="ew")

        # Tick font size
        ttk.Label(global_frame, text="Tick Font Size").grid(row=4, column=0, sticky="w")
        self.tick_font_size = tk.StringVar(value="10")
        ttk.Combobox(global_frame, textvariable=self.tick_font_size,
                     values=["8", "10", "12", "14", "16"], state="readonly")\
            .grid(row=4, column=1, sticky="ew")

        # Label font size
        ttk.Label(global_frame, text="Label Font Size").grid(row=5, column=0, sticky="w")
        self.label_font_size = tk.StringVar(value="12")
        ttk.Combobox(global_frame, textvariable=self.label_font_size,
                     values=["10", "12", "14", "16", "18"], state="readonly")\
            .grid(row=5, column=1, sticky="ew")

        # Legend location
        ttk.Label(global_frame, text="Legend Location").grid(row=6, column=0, sticky="w")
        self.legend_loc = tk.StringVar(value="best")
        ttk.Combobox(global_frame, textvariable=self.legend_loc,
                     values=LEGEND_LOCATIONS, state="readonly")\
            .grid(row=6, column=1, sticky="ew")
        # trace to update plot on change
        self.legend_loc.trace_add('write', lambda *a: self._update_plot())

        # Grid density slider 0–2
        ttk.Label(global_frame, text="Grid Density").grid(row=7, column=0, sticky="w")
        self.grid_density = tk.IntVar(value=1)
        tk.Scale(global_frame, from_=0, to=2, orient=tk.HORIZONTAL,
                 variable=self.grid_density,
                 command=lambda v: self._update_plot())\
            .grid(row=7, column=1, columnspan=2, sticky="ew")

        # Add Curve button
        ttk.Button(global_frame, text="Add Curve", command=self._add_curve_tab)\
            .grid(row=8, column=0, columnspan=3, pady=5, sticky="ew")

        # Save buttons
        ttk.Button(global_frame, text="Save Plot Image", command=self._save_plot_image)\
            .grid(row=9, column=0, pady=5, sticky="ew")
        ttk.Button(global_frame, text="Save Data Array", command=self._save_data_array)\
            .grid(row=9, column=1, pady=5, sticky="ew")

        # Curve settings notebook
        self.curve_tab_frame = ttk.LabelFrame(main_frame, text="Curve Settings")
        self.curve_tab_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        self.curve_notebook = ttk.Notebook(self.curve_tab_frame)
        self.curve_notebook.pack(fill=tk.BOTH, expand=True)

    def _create_plot(self):
        # Single figure and initial axis
        self.fig = plt.figure()
        ax = self.fig.add_subplot(111)
        self.axes = [ax]
        # One canvas on right side
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    def _update_subplots_ui(self):
        # Show/hide the "Number of subplots" combobox
        if self.plot_type.get() == "Subplot":
            self.num_subplots_cb.grid()
        else:
            self.num_subplots_cb.grid_remove()
        # Show or hide each curve's Subplot frame
        for cfg in self.curve_config:
            frame = cfg["subplt_frame"]
            if self.plot_type.get() == "Subplot":
                frame.pack(fill=tk.X, pady=5)
            else:
                frame.pack_forget()
        # Rebuild the subplots layout
        self._rebuild_subplots()

    def _rebuild_subplots(self):
        n = self.num_subplots.get() if self.plot_type.get() == "Subplot" else 1
        self.fig.clf()
        if n == 1:
            ax = self.fig.add_subplot(111)
            self.axes = [ax]
        else:
            axs = self.fig.subplots(n, 1, sharex=True)
            # ensure a list of axes
            self.axes = list(np.atleast_1d(axs))
        self._update_plot()

    def _add_curve_tab(self, initial=False):
        frame = ttk.Frame(self.curve_notebook)
        idx = len(self.curve_tabs)
        self.curve_notebook.add(frame, text=f"Curve {idx+1}")
        self.curve_tabs.append(frame)

        # Configuration dict for this curve
        cfg = {
            "file": None,
            "data": None,
            "x_idx": tk.StringVar(value="Column 1"),
            "y_idx": tk.StringVar(value="Column 2"),
            "label": tk.StringVar(value=f"Curve {idx+1}"),
            "color": tk.StringVar(value=self._random_color()),
            "style": tk.StringVar(value="-"),
            "visible": True,
            "frame": frame,
            "info_label": None,
            "x_dropdown": None,
            "y_dropdown": None,
            # Subplot-specific widgets
            "subplt_frame": None,
            "subplot_pos": tk.IntVar(value=1),
            "subplot_title": tk.StringVar(value=""),
            "subplot_show_title": tk.BooleanVar(value=False),
            "subplot_xlabel": tk.StringVar(value=""),
            "subplot_show_xlabel": tk.BooleanVar(value=False),
            "subplot_ylabel": tk.StringVar(value=""),
            "subplot_show_ylabel": tk.BooleanVar(value=False),
        }
        self.curve_config.append(cfg)

        # Subplot frame (hidden if not in Subplot mode)
        subplt = ttk.LabelFrame(frame, text="Subplot")
        cfg["subplt_frame"] = subplt
        # Position dropdown
        ttk.Label(subplt, text="Position").grid(row=0, column=0, sticky="w")
        pos_cb = ttk.Combobox(
            subplt,
            textvariable=cfg["subplot_pos"],
            values=[str(i+1) for i in range(self.num_subplots.get())],
            state="readonly"
        )
        pos_cb.grid(row=0, column=1, sticky="ew")
        # Title + checkbox
        ttk.Label(subplt, text="Title").grid(row=1, column=0, sticky="w")
        ttk.Entry(subplt, textvariable=cfg["subplot_title"]).grid(row=1, column=1, sticky="ew")
        ttk.Checkbutton(subplt, text="Show Title", variable=cfg["subplot_show_title"])\
            .grid(row=1, column=2)
        # X-Label + checkbox
        ttk.Label(subplt, text="X-Label").grid(row=2, column=0, sticky="w")
        ttk.Entry(subplt, textvariable=cfg["subplot_xlabel"]).grid(row=2, column=1, sticky="ew")
        ttk.Checkbutton(subplt, text="Show X-Label", variable=cfg["subplot_show_xlabel"])\
            .grid(row=2, column=2)
        # Y-Label + checkbox
        ttk.Label(subplt, text="Y-Label").grid(row=3, column=0, sticky="w")
        ttk.Entry(subplt, textvariable=cfg["subplot_ylabel"]).grid(row=3, column=1, sticky="ew")
        ttk.Checkbutton(subplt, text="Show Y-Label", variable=cfg["subplot_show_ylabel"])\
            .grid(row=3, column=2)

        # Pack or hide depending on mode
        if self.plot_type.get() == "Subplot":
            subplt.pack(fill=tk.X, pady=5)

        # Buttons: Load & Delete
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=2)
        ttk.Button(
            btn_frame,
            text="Load .npy File",
            command=lambda fr=frame: self._load_file(self.curve_tabs.index(fr))
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            btn_frame,
            text="Delete Curve",
            command=lambda fr=frame: self._delete_curve_tab(self.curve_tabs.index(fr))
        ).pack(side=tk.LEFT, padx=2)

        # Column selectors appear on load (above legend)
        # Legend label entry
        ttk.Label(frame, text="Legend Label").pack()
        ent = ttk.Entry(frame, textvariable=cfg["label"])
        ent.pack()
        cfg["label"].trace_add('write', lambda *a: self._update_plot())

        # Color chooser
        ttk.Label(frame, text="Line Color").pack()
        ttk.Button(
            frame,
            text="Choose Color",
            command=lambda fr=frame: self._choose_color(self.curve_tabs.index(fr))
        ).pack(pady=2)
        cfg["color"].trace_add('write', lambda *a: self._update_plot())

        # Line style combobox
        ttk.Label(frame, text="Line Style").pack()
        style_cb = ttk.Combobox(
            frame,
            textvariable=cfg["style"],
            values=LINE_STYLES,
            state="readonly"
        )
        style_cb.pack()
        cfg["style"].trace_add('write', lambda *a: self._update_plot())

        # Hide/Show button above info label
        hide_btn = tk.Button(
            frame,
            text="Hide Curve",
            command=lambda fr=frame: self._toggle_visibility(self.curve_tabs.index(fr))
        )
        hide_btn.pack(pady=4)
        cfg["hide_btn"] = hide_btn
        cfg["default_btn_bg"] = hide_btn.cget("background")

        # Info label at very bottom
        info = ttk.Label(
            frame,
            text="No file loaded.",
            wraplength=200,
            justify=tk.LEFT
        )
        info.pack(side=tk.BOTTOM, pady=4)
        cfg["info_label"] = info

    def _random_color(self):
        return "#%06x" % np.random.randint(0, 0xFFFFFF)

    def _delete_curve_tab(self, idx):
        if len(self.curve_config) == 1:
            # Only clear data if it's the last curve
            cfg = self.curve_config[0]
            cfg["data"] = None
            if cfg["x_dropdown"]:
                cfg["x_dropdown"].destroy(); cfg["x_dropdown"] = None
            if cfg["y_dropdown"]:
                cfg["y_dropdown"].destroy(); cfg["y_dropdown"] = None
            cfg["info_label"].config(text="No file loaded.")
            self._update_plot()
            return
        frame = self.curve_tabs.pop(idx)
        self.curve_notebook.forget(frame)
        self.curve_config.pop(idx)
        # Renumber remaining
        for i, fr in enumerate(self.curve_tabs):
            self.curve_notebook.tab(fr, text=f"Curve {i+1}")
            self.curve_config[i]["label"].set(f"Curve {i+1}")
        self._update_plot()

    def _choose_color(self, idx):
        col = colorchooser.askcolor()[1]
        if col:
            self.curve_config[idx]["color"].set(col)

    def _load_file(self, idx):
        cfg = self.curve_config[idx]
        path = filedialog.askopenfilename(filetypes=[("NumPy Array","*.npy")])
        try:
            data = np.load(path)
            if data.ndim != 2:
                raise ValueError("Array must be 2D.")
            cfg["file"], cfg["data"] = path, data
            cols = [f"Column {i+1}" for i in range(data.shape[1])]
            # Remove old dropdowns
            if cfg["x_dropdown"]:
                cfg["x_dropdown"].destroy()
            if cfg["y_dropdown"]:
                cfg["y_dropdown"].destroy()
            # X selector
            ttk.Label(cfg["frame"], text="X Values:").pack()
            x_cb = ttk.Combobox(
                cfg["frame"],
                values=cols,
                textvariable=cfg["x_idx"],
                state="readonly"
            )
            x_cb.pack()
            # Y selector
            ttk.Label(cfg["frame"], text="Y Values:").pack()
            y_cb = ttk.Combobox(
                cfg["frame"],
                values=cols,
                textvariable=cfg["y_idx"],
                state="readonly"
            )
            y_cb.pack()
            cfg["x_dropdown"], cfg["y_dropdown"] = x_cb, y_cb

            # Show just filename in label
            fname = os.path.basename(path)
            cfg["info_label"].config(
                text=f"Successful loaded file {fname} (rows: {data.shape[0]}; columns: {data.shape[1]})",
                foreground="green"
            )
            cfg["x_idx"].trace_add('write', lambda *a: self._update_plot())
            cfg["y_idx"].trace_add('write', lambda *a: self._update_plot())
            self._update_plot()
        except Exception as e:
            fname = os.path.basename(path) if path else "<none>"
            cfg["info_label"].config(
                text=f"failed to load file: {fname}",
                foreground="red"
            )
            messagebox.showerror("Load Error", str(e))

    def _toggle_visibility(self, idx):
        cfg = self.curve_config[idx]
        cfg["visible"] = not cfg["visible"]
        btn = cfg["hide_btn"]
        if cfg["visible"]:
            btn.config(text="Hide Curve", background=cfg["default_btn_bg"])
        else:
            btn.config(text="Show Curve", background="yellow")
        self._update_plot()

    def _apply_grid_to_axis(self, ax):
        d = self.grid_density.get()
        if d == 0:
            ax.grid(False)
            ax.minorticks_off()
        elif d == 1:
            ax.grid(True, which='major')
            ax.minorticks_off()
        else:
            ax.grid(True, which='major')
            ax.minorticks_on()
            ax.grid(True, which='minor', linestyle=':', linewidth=0.5)

    def _save_plot_image(self):
        path = filedialog.asksaveasfilename(defaultextension='.png',
                                            filetypes=[('PNG Image','*.png')])
        if path:
            self.fig.savefig(path)
            messagebox.showinfo("Saved", f"Plot image → {path}")

    def _save_data_array(self):
        path = filedialog.asksaveasfilename(defaultextension='.npy',
                                            filetypes=[('NumPy Array','*.npy')])
        if not path:
            return
        x = None
        ys = []
        for cfg in self.curve_config:
            if not cfg["visible"] or cfg.get("data") is None:
                continue
            data = cfg["data"]
            xi = int(cfg["x_idx"].get().split()[-1]) - 1
            yi = int(cfg["y_idx"].get().split()[-1]) - 1
            if x is None:
                x = data[:, xi]
            ys.append(data[:, yi])
        if x is None:
            messagebox.showwarning("Save Data", "No data to save.")
            return
        arr = np.column_stack([x] + ys)
        np.save(path, arr)
        messagebox.showinfo("Saved", f"Data array → {path}")

    def _update_plot(self):
        # Clear all axes
        for ax in self.axes:
            ax.clear()

        # Plot each curve on its axis or on single plot
        for cfg in self.curve_config:
            if not cfg["visible"] or cfg.get("data") is None:
                continue
            try:
                xi = int(cfg["x_idx"].get().split()[-1]) - 1
                yi = int(cfg["y_idx"].get().split()[-1]) - 1
                x, y = cfg["data"][:, xi], cfg["data"][:, yi]
                if self.plot_type.get() == "1 Plot":
                    ax = self.axes[0]
                else:
                    ax = self.axes[cfg["subplot_pos"].get() - 1]
                ax.plot(x, y,
                        label=cfg["label"].get(),
                        color=cfg["color"].get(),
                        linestyle=cfg["style"].get())
            except Exception:
                continue

        # Apply settings and legends
        if self.plot_type.get() == "1 Plot":
            ax0 = self.axes[0]
            self._apply_grid_to_axis(ax0)
            ax0.set_title(self.title_entry.get(),
                          fontsize=int(self.label_font_size.get()))
            ax0.set_xlabel(self.xlabel_entry.get(),
                           fontsize=int(self.label_font_size.get()))
            ax0.set_ylabel(self.ylabel_entry.get(),
                           fontsize=int(self.label_font_size.get()))
            ax0.tick_params(labelsize=int(self.tick_font_size.get()))
            h, l = ax0.get_legend_handles_labels()
            if h:
                ax0.legend(loc=self.legend_loc.get())
        else:
            for ax in self.axes:
                self._apply_grid_to_axis(ax)
                # apply per-curve subplot labels
                for cfg in self.curve_config:
                    if cfg["subplot_pos"].get() - 1 == self.axes.index(ax):
                        if cfg["subplot_show_title"].get():
                            ax.set_title(cfg["subplot_title"].get())
                        if cfg["subplot_show_xlabel"].get():
                            ax.set_xlabel(cfg["subplot_xlabel"].get())
                        if cfg["subplot_show_ylabel"].get():
                            ax.set_ylabel(cfg["subplot_ylabel"].get())
                h, l = ax.get_legend_handles_labels()
                if h:
                    ax.legend(loc=self.legend_loc.get())

        # Redraw
        self.canvas.draw()


if __name__ == '__main__':
    root = tk.Tk()
    root.title("PlotViewer V2")
    PlotViewer(root).pack(fill=tk.BOTH, expand=True)
    root.mainloop()
