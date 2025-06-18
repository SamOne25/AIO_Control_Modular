import pyvisa

class WavegenController:
    def __init__(self):
        self.rm = pyvisa.ResourceManager()
        self.gen = None

    def connect(self, ip):
        self.gen = self.rm.open_resource(f"TCPIP0::{ip}::inst0::INSTR", timeout=5000)
        return self.gen

    def disconnect(self):
        if self.gen:
            self.gen.close()
            self.gen = None

    def write(self, cmd):
        if self.gen:
            self.gen.write(cmd)

    def query(self, cmd):
        if self.gen:
            return self.gen.query(cmd)
        return None
