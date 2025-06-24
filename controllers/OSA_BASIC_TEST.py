# -*- coding: utf-8 -*-
"""
Created on Tue Jun 17 19:25:51 2025

@author: Sam
"""
import pyvisa
import time
import numpy as np

rm = pyvisa.ResourceManager()
osa = rm.open_resource(f"TCPIP0::192.168.1.112::INSTR")
print(osa.query("*IDN?"))

################Singlesweep####################

"""
# 1. OSA in den Messmodus schalten
osa.write('SYS OSA,ACT')

# 2. Single Sweep starten und auf Abschluss warten
osa.write('SSI')
osa.write('*WAI')  # wartet, bis der Sweep fertig ist :contentReference[oaicite:0]{index=0}

# 3a. Binär-Daten per DBA? abfragen und in Float-Liste wandeln
data_bin = osa.query_binary_values('DBA?', datatype='d', header_fmt='#', is_big_endian=True)
# data_bin ist nun eine Python-Liste aus Double-Präzisions-Werten :contentReference[oaicite:1]{index=1}

# 3b. Alternativ als ASCII-CSV (kommagetrennt) mit DQA?
raw_csv = osa.query('DQA?')
data_csv = [float(x) for x in raw_csv.strip().split(',')]

"""



#############RepeatSweep##################



"""
# Verbindung öffnen
#rm = pyvisa.ResourceManager()
#osa = rm.open_resource('TCPIP0::192.168.1.112::5025::SOCKET')

# 1. Grundeinstellungen: Start/Stop, Punkte, etc.
#osa.write('STA 1520')            # Startwellenlänge
#osa.write('STO 1580')            # Stop-Wellenlänge
#osa.write('MPT 1001')            # Datenpunkte
# …

# 2. Repeat-Intervall setzen (z. B. 2 s zwischen den Sweeps)
repeat_interval = 2.0
osa.write(f':SENS:SWE:TIME:INT {repeat_interval}')

# 3. Repeat-Sweep starten
osa.write('SRT')                 # Start Repeat Sweep :contentReference[oaicite:0]{index=0}

# 4. In einer Schleife: auf Ende des Sweeps warten und Daten abfragen

STA = osa.query('STA?')
STO = osa.query('STO?')
MPT = osa.query('MPT?')

try:
    while True:
        # blockierend auf Sweep-Ende warten
        # Variante A: durch *OPC? (Operation Complete)
        osa.query('*OPC?')       # gibt erst zurück, wenn der aktuelle Sweep fertig ist :contentReference[oaicite:1]{index=1}

        # Jetzt Daten holen – z. B. ASCII-CSV der Spur A
        raw = osa.query('DQA?')
        raw = raw.strip()              # entfernt führende/folgende Whitespace
        parts = raw.split(',')
        vals = np.array([float(p) for p in parts if p.strip() != ""])
        wavelengths = np.linspace(float(STA), float(STO), int(MPT))
        power_dbm = vals[4::2]            # every second value
        power_lin = 10 ** (power_dbm / 10)

        # Hier könntest du plotten, speichern oder weiterverarbeiten
        print("Neuer Sweep gemessen:", wavelengths.shape, power_dbm.shape)

        # Kurze Pause oder Abbruchbedingung
        time.sleep(0.1)

except KeyboardInterrupt:
    # 5. Repeat stoppen
    osa.write('SST')                 # SST = Sweep Stop
    print("Repeat Sweep gestoppt.")
"""

#!/usr/bin/env python3
import pyvisa
import numpy as np
import matplotlib.pyplot as plt
import time

def main():
    # OSA-Daten
    ip         = "192.168.1.112"
    cnt        = 1550.0    # Center [nm]
    spn        = 20.0      # Span   [nm]
    res        = 0.02      # Resolution [nm]
    mpt        = 1001      # Punkte
    vbw_hz     = 1000      # VBW in Hz (z.B. 1 kHz)
    interval_s = 1.0       # Pause zwischen den Plots

    # 1) Verbindung
    rm  = pyvisa.ResourceManager()
    osa = rm.open_resource(f"TCPIP0::{ip}::INSTR", timeout=300000)
    osa.write("SRE 0; SST")  # SRQ off, Stop any existing sweep

    # 2) Grundkonfiguration
    osa.write(f"CNT {cnt:.2f}; SPN {spn}; RES {res}; VBW {vbw_hz}; MPT {mpt}")

    # 3) Repeat Sweep starten
    osa.write("SRT")

    # 4) Plot vorbereiten
    plt.ion()
    fig, ax = plt.subplots(figsize=(8,4))
    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Power (dBm)")
    line, = ax.plot([], [], "-b")

    try:
        for cycle in range(5):
            # 4.1) Auf Sweep-Ende warten
            osa.query("*OPC?")

            # 4.2) Metadaten holen
            staw, stow, npts = osa.query_ascii_values("DCA?", separator=",")

            # 4.3) Daten als Binärblock (dBm) abholen
            data_dbm = osa.query_binary_values(
                "DBA?",
                datatype='d',       # 64-Bit Double
                header_fmt='ieee',  # IEEE-488.2 header
                is_big_endian=True
            )

            # 4.4) Achse und Plot updaten
            wl = np.linspace(staw, stow, int(npts))
            line.set_data(wl, data_dbm)
            ax.set_xlim(wl[0], wl[-1])
            y_min, y_max = np.nanmin(data_dbm), np.nanmax(data_dbm)
            ax.set_ylim(y_min - 1, y_max + 1)

            fig.canvas.draw()
            fig.canvas.flush_events()

            time.sleep(interval_s)

    except KeyboardInterrupt:
        print("Unterbrochen vom Benutzer")

    finally:
        # 5) Repeat stoppen und Verbindung schließen
        osa.write("SST")
        osa.close()
        plt.ioff()
        plt.show()

if __name__ == "__main__":
    main()

