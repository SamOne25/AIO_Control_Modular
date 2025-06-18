from tkinter import ttk
from gui.widgets.scope_gui import ScopeGUI
from gui.widgets.wavegen_gui import WavegenGUI
from gui.widgets.osa_gui import OSAGUI

class MainGUI(ttk.Frame):
    def __init__(self, parent, scope_ctrl, wavegen_ctrl, osa_ctrl):
        super().__init__(parent)
        self.pack(fill="both", expand=True)
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        scope_tab = ScopeGUI(notebook, controller=scope_ctrl)
        wavegen_tab = WavegenGUI(notebook, controller=wavegen_ctrl)
        osa_tab = OSAGUI(notebook, controller=osa_ctrl)

        notebook.add(scope_tab, text="Oscilloscope")
        notebook.add(wavegen_tab, text="Wavegen")
        notebook.add(osa_tab, text="OSA")
