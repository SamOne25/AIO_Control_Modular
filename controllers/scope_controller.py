import pyvisa
import numpy as np
import time

UNITS            = {"V": 1, "mV": 1e-3, "uV": 1e-6}
SCALE_FACTOR     = {"V": 1, "mV": 1e3, "uV": 1e6}
TRIGGER_SOURCES  = ["CH1", "CH2", "CH3", "CH4"]

class ScopeController:
    def __init__(self):
        self.rm = pyvisa.ResourceManager()
        self.scope = None
        self.connected = False

        # Caches
        self.channel_order    = ["CH1", "CH2", "CH3", "CH4"]
        self.wfmpre_cache     = {}
        self.latest_data      = {}
        self.trigger_levels   = {}
        self.rec_length_cached = 2000
        self.timebase_s      = 1e-8  # Default (s/div)
        self.delay_time      = 0.0
        self.xinc            = 0.0

    def connect(self, ip):
        try:
            self.scope = self.rm.open_resource(f"TCPIP::{ip}::INSTR")
            self.scope.timeout = 2000
            self.scope.write("HEADER OFF")
            self.scope.write("DATA:ENC RIBinary")
            self.scope.write("DATA:WIDTH 2")
            self.scope.write("TRIG:A:MODE AUTO")
            self.scope.write("ACQ:STOPAFTER RUNST")
            self.scope.write("ACQ:STATE ON")
            self.connected = True
            self.init_parameters()
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            self.scope = None
            self.connected = False
            return False

    def disconnect(self):
        try:
            if self.scope:
                self.scope.write("ACQ:STATE OFF")
                self.scope.close()
        except Exception as e:
            print(f"Disconnect failed: {e}")
        self.scope = None
        self.connected = False

    def is_connected(self):
        return self.connected

    def query_idn(self):
        if self.scope:
            return self.scope.query("*IDN?")
        return "No scope connected!"

    def init_parameters(self):
        """Cache alle wichtigen Parameter bei Connect."""
        # Record length
        self.rec_length_cached = int(self.scope.query("HORizontal:RECordlength?"))
        # Timebase und Delay
        self.timebase_s = float(self.scope.query("HORizontal:MAIN:SCAle?"))
        self.delay_time = float(self.scope.query("HORizontal:MAIN:DELay:TIME?"))
        divisions = 10
        total_time = self.timebase_s * divisions
        self.xinc = total_time / self.rec_length_cached
        # Trigger Level per Channel
        for ch in self.channel_order:
            try:
                lvl = float(self.scope.query(f"TRIGger:A:LEVel:{ch}?"))
            except Exception:
                lvl = float(self.scope.query("TRIGger:A:LEVel?"))
            self.trigger_levels[ch] = lvl
        # Per Channel Kalibrierung
        for ch in self.channel_order:
            self.cache_channel_settings(ch)

    def cache_channel_settings(self, ch):
        """Holt YMULT, YZERO, YOFF für ch."""
        try:
            self.scope.write(f"DATA:SOURCE {ch}")
            self.scope.write("DATA:ENC RIBinary")
            self.scope.write("DATA:WIDTH 2")
            time.sleep(0.01)
            self.wfmpre_cache[ch] = {
                "ymult": float(self.scope.query("WFMPRE:YMULT?")),
                "yzero": float(self.scope.query("WFMPRE:YZERO?")),
                "yoff":  float(self.scope.query("WFMPRE:YOFF?")),
            }
        except Exception as e:
            print(f"{ch} cache error: {e}")
            self.wfmpre_cache[ch] = None

    def set_trigger_source(self, src):
        self.scope.write(f"TRIGger:A:EDGE:SOUR {src}")
        self.scope.write("TRIGger:A:MODE EDGE")
        # Level ggf. updaten:
        lvl = float(self.scope.query(f"TRIGger:A:LEVel:{src}?"))
        self.trigger_levels[src] = lvl
        return lvl

    def set_trigger_level(self, ch, value_v):
        self.scope.write(f"TRIGger:A:LEVel:{ch} {value_v}")
        self.trigger_levels[ch] = value_v

    def set_timebase(self, value_ns):
        self.scope.write(f"HORizontal:MAIN:SCAle {value_ns*1e-9}")
        self.timebase_s = float(self.scope.query("HORizontal:MAIN:SCAle?"))

    def set_acquisition_mode(self, mode):
        self.scope.write(f"ACQ:MODE {mode}")

    def set_average_count(self, count):
        self.scope.write("ACQ:MODE AVERAGE")
        self.scope.write(f"ACQ:AVER:COUN {count}")

    def run(self):
        self.scope.write("ACQ:STATE RUN")

    def stop(self):
        self.scope.write("ACQ:STATE STOP")

    def single(self):
        self.scope.write("ACQ:STATE SINGLE")

    def get_channel_list(self):
        return self.channel_order.copy()

    def get_waveform(self, ch):
        self.scope.write("DATA:START 1")
        stop = min(self.rec_length_cached, 2000)
        self.scope.write(f"DATA:STOP {stop}")
        self.scope.write(f"DATA:SOURCE {ch}")
        time.sleep(0.002)
        raw = self.scope.query_binary_values(
            "CURVe?", datatype="h", is_big_endian=True, container=np.array
        )
        p = self.wfmpre_cache.get(ch)
        if p:
            v = (raw - p["yoff"]) * p["ymult"] + p["yzero"]
            t = np.arange(len(v)) * self.xinc * 1e9
            return t, v
        else:
            return None, None
