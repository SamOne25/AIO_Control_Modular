# gui/main_gui.py

"""
main_gui.py

Assembles individual device GUI widgets into a tabbed interface.
"""

import tkinter as tk
from tkinter import ttk

from gui.widgets.scope_gui import ScopeGUI
from gui.widgets.wavegen_gui import WavegenGUI
from gui.widgets.osa_gui import OSAGUI


class MainGUI:
    """
    Main application GUI: provides tabs for Scope, Wavegen, and OSA.
    """

    def __init__(self, master, scope_ctrl, wavegen_ctrl, osa_ctrl, data_model):
        """
        Initialize the main window and embed each device frame.
        """
        self.master = master
        self.data_model = data_model

        # Create a Notebook for tabbed layout
        self.notebook = ttk.Notebook(master)
        self.notebook.pack(fill="both", expand=True)

        # Scope tab
        self.scope_frame = ScopeGUI(self.notebook, scope_ctrl)
        self.notebook.add(self.scope_frame, text="Oscilloscope")

        # Waveform Generator tab
        self.wavegen_frame = WavegenGUI(self.notebook, wavegen_ctrl)
        self.notebook.add(self.wavegen_frame, text="Wavegen")

        # OSA tab
        self.osa_frame = OSAGUI(self.notebook, osa_ctrl)
        self.notebook.add(self.osa_frame, text="OSA")

        # (Optional) you can add controls here to orchestrate a full sweep,
        # store data_model records, and update charts in real time.


if __name__ == "__main__":
    # Quick standalone launch for testing
    import pyvisa
    from controllers.scope_controller import ScopeController
    from controllers.wavegen_controller import WavegenController
    from controllers.osa_controller import OSAController
    from models.measurement_data import MeasurementData

    # Dummy VISA addresses for standalone test
    scope = ScopeController("TCPIP0::192.168.0.10::INSTR")
    wavegen = WavegenController("TCPIP0::192.168.0.11::INSTR")
    osa = OSAController("TCPIP0::192.168.0.12::INSTR")
    data = MeasurementData()

    root = tk.Tk()
    root.title("AIO Control Modular - Test Mode")
    root.geometry("1024x768")
    app = MainGUI(root, scope, wavegen, osa, data)
    root.mainloop()

    # Cleanup
    scope.close()
    wavegen.close()
    osa.close()
