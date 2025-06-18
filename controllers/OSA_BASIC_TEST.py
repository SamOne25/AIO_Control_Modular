# -*- coding: utf-8 -*-
"""
Created on Tue Jun 17 19:25:51 2025

@author: Sam
"""
import pyvisa

rm = pyvisa.ResourceManager()
osa = rm.open_resource(f"TCPIP0::192.168.1.112::INSTR")
print(osa.query("*IDN?"))
