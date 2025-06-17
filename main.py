"""
main.py

Entry point for the AIO_Control_Modular application.
Initializes device controllers, data model, and launches the GUI.
"""

import tkinter as tk

from controllers.scope_controller import ScopeController
from controllers.wavegen_controller import WavegenController
from controllers.osa_controller import OSAController
from models.measurement_data import MeasurementData
from gui.main_gui import MainGUI


def main():
    """
    Main function to initialize device controllers and start the GUI event loop.
    """

    # -------------------------------------------------------------------------
    # 1. Configure VISA addresses for your instruments here.
    #    Update the strings below to match your actual device connection strings.
    # -------------------------------------------------------------------------
    SCOPE_ADDRESS    = "TCPIP0::192.168.1.133::INSTR"
    WAVEGEN_ADDRESS  = "TCPIP0::192.168.1.122::INSTR"
    OSA_ADDRESS      = "TCPIP0::192.168.1.112::INSTR"

    # -------------------------------------------------------------------------
    # 2. Instantiate each device controller
    # -------------------------------------------------------------------------
    scope_ctrl   = ScopeController(SCOPE_ADDRESS)
    wavegen_ctrl = WavegenController(WAVEGEN_ADDRESS)
    osa_ctrl     = OSAController(OSA_ADDRESS)

    # -------------------------------------------------------------------------
    # 3. Create the data model to store measurements
    # -------------------------------------------------------------------------
    data_model = MeasurementData()

    # -------------------------------------------------------------------------
    # 4. Initialize and launch the main GUI
    # -------------------------------------------------------------------------
    root = tk.Tk()
    root.title("AIO Control Modular")
    root.geometry("1024x768")
    app = MainGUI(root, scope_ctrl, wavegen_ctrl, osa_ctrl, data_model)
    root.mainloop()

    # -------------------------------------------------------------------------
    # 5. Clean up / close instrument connections on exit
    # -------------------------------------------------------------------------
    try:
        scope_ctrl.close()
    except Exception:
        pass

    try:
        wavegen_ctrl.close()
    except Exception:
        pass

    try:
        osa_ctrl.close()
    except Exception:
        pass


if __name__ == "__main__":
    main()
