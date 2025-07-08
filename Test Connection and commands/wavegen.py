# -*- coding: utf-8 -*-
"""
Created on Tue Jul  8 14:12:49 2025

@author: Sam
"""

import pyvisa
rm = pyvisa.ResourceManager()  
# Ersetze die IP durch Deine Wavegen-Adresse
wg = rm.open_resource("TCPIP0::192.168.1.122::INSTR")  
wg.timeout = 5000  # in ms, nach Bedarf anpassen

# Identifikation abfragen
print(wg.query("*IDN?"))

# Beispiel: Frequenz auslesen
print(wg.query("SOUR1:FREQ?"))

# Beispiel: Frequenz auf 1 kHz setzen
#wg.write("SOUR1:FREQuency:MODE LIST")
#cmd_freq = ("SOUR1:LIST:FREQuency 1000,1001,1002")
#wg.write(cmd_freq)
#wg.write("TRIGger1:SOURce IMMediate")
#wg.write("SOUR1:BURSt:STATe ON")
#wg.write("SOUR1:BURSt:MODE TRIGgered")
#wg.write("SOUR1:BURSt:NCYC 1")
#wg.write("SOUR1:LIST:STATe ON")
"""
        # 3) List-Mode einschalten (falls noch nicht geschehen)
        self.wavegen_controller.write("SOUR1:FREQuency:MODE LIST")
        append_event(self.event_log, self.log_text, "SEND", "SOUR1:FREQuency:MODE LIST")
    
        # 4) Frequenzliste schicken
        cmd_freq = "SOUR1:LIST:FREQuency " + ",".join(str(f) for f in freqs)
        self.wavegen_controller.write(cmd_freq)
        append_event(self.event_log, self.log_text, "SEND", cmd_freq)
    
        # 5) Dwell-Time setzen
        self.wavegen_controller.write(f"SOUR1:LIST:DWELl {dwell}")
        append_event(self.event_log, self.log_text, "SEND", dwell)
    
        # 6) Internen Trigger wählen
        self.wavegen_controller.write("TRIGger1:SOURce IMMediate")
        append_event(self.event_log, self.log_text, "SEND", "TRIGger1:SOURce IMMediate")
    
        # 7) Burst-Modus konfigurieren
        self.wavegen_controller.write("SOUR1:BURSt:STATe ON")
        append_event(self.event_log, self.log_text, "SEND", "SOUR1:BURSt:STATe ON")
        self.wavegen_controller.write("SOUR1:BURSt:MODE TRIGgered")
        append_event(self.event_log, self.log_text, "SEND", "SOUR1:BURSt:MODE TRIGgered")
        self.wavegen_controller.write("SOUR1:BURSt:NCYC 1")
        append_event(self.event_log, self.log_text, "SEND", "SOUR1:BURSt:NCYC 1")

    
        # 8) Liste starten
        self.wavegen_controller.write("SOUR1:LIST:STATe ON")
        append_event(self.event_log, self.log_text, "SEND", "SOUR1:LIST:STATe ON")
    
        # 9) Status aktualisieren
        self.status_var.set(f"Burst started: {n} frequences, dwell={dwell:.3f}s")
        append_event(self.event_log, self.log_text, "SEND", "Burst started: {n} frequences, dwell={dwell:.3f}s")
"""