from tkinter import ttk
from gui.widgets.scope_gui import ScopeGUI
from gui.widgets.wavegen_gui import WavegenGUI
from gui.widgets.osa_gui import OSAGUI
from utils.plot_viewer import PlotViewer

class MainGUI(ttk.Frame):
    def __init__(self, parent, scope_ctrl, wavegen_ctrl, osa_ctrl):
        super().__init__(parent)
        self.pack(fill="both", expand=True)

        # Tab Control
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        # Tabs
        scope_tab   = ScopeGUI(notebook, controller=scope_ctrl)
        wavegen_tab = WavegenGUI(notebook, controller=wavegen_ctrl)
        osa_tab     = OSAGUI(notebook, controller=osa_ctrl, wavegen_controller=wavegen_ctrl)
        plot_tab    = PlotViewer(notebook)  # <- das war der Fehler: vorher war 'tab_control'

        # Tabs hinzufügen
        notebook.add(osa_tab, text="OSA")
        notebook.add(scope_tab, text="Oscilloscope")
        notebook.add(wavegen_tab, text="Wavegen")
        notebook.add(plot_tab, text="Plot Viewer")  # <- jetzt korrekt eingefügt
