import tkinter as tk

class MainGUI:
    def __init__(self, master):
        self.master = master
        master.title("AIO Control Modular")
        master.geometry("800x600")

if __name__ == "__main__":
    root = tk.Tk()
    app = MainGUI(root)
    root.mainloop()
