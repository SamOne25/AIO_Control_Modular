import tkinter as tk
from tkinter import ttk
from gui.main_gui import MainGUI
from controllers.scope_controller import ScopeController
from controllers.wavegen_controller import WavegenController
from controllers.osa_controller import OSAController

def main():
    root = tk.Tk()
    root.title("AIO Control Modular")
    root.geometry("1200x900")

    # Controller erzeugen (können optional später mit Parametern instanziiert werden)
    scope_ctrl = ScopeController()
    wavegen_ctrl = WavegenController()
    osa_ctrl = OSAController()

    # Main-GUI starten
    app = MainGUI(root, scope_ctrl, wavegen_ctrl, osa_ctrl)
    app.pack(fill="both", expand=True)
    root.mainloop()

if __name__ == "__main__":
    main()
