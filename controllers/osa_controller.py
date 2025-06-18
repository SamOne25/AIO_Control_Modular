import pyvisa
import re
import numpy as np

class OSAController:
    def __init__(self):
        self.rm = None
        self.osa = None

    def connect(self, ip):
        if self.rm is None:
            self.rm = pyvisa.ResourceManager()
        self.osa = self.rm.open_resource(f"TCPIP0::{ip}::INSTR")
        self.osa.timeout = 300_000
        idn = self.osa.query("*IDN?")
        return idn

    def disconnect(self):
        try:
            if self.osa:
                self.osa.write("SST")
                self.osa.write("SND ON")
                self.osa.close()
        except Exception:
            pass
        self.osa = None

    def write(self, cmd):
        if self.osa:
            self.osa.write(cmd)

    def query(self, cmd):
        if self.osa:
            return self.osa.query(cmd)
        return None

    def query_binary(self, cmd):
        if self.osa:
            return self.osa.query_binary_values(cmd)
        return None
