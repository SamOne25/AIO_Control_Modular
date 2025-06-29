import pyvisa
import numpy as np

class OSAController:
    def __init__(self):
        self.rm = None
        self.osa = None
        
        #-------------------------- Aritsu Paramterlist -----------------------------------
        self.resolutions   = ["1.0","0.5","0.2","0.1","0.07","0.05","0.03"]
        self.integrations  = ["1MHz","100kHz","10kHz","1kHz","100Hz","10Hz"]
        self.samp_points   = ["51","101","201","251","501","1001","2001","5001","10001","20001","50001"]
        self.spans         = ["1200","1000","500","200","100","50","20","10","5","2","1"]
        self.smt_points    = ["OFF", "3", "5", "7", "9", "11"]
        
        self.cmd_map = {"Span [nm]:":"SPN","Resolution [nm]:":"RES","Integration:":"VBW",
                        "Sampling Points:":"MPT","Smooth:":"SMT","Reference LvL [dBm]:":"RLV",
                        "Level Offset [dB]:":"LOFS"}
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



    