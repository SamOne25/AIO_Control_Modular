import pyvisa

class ScopeController:
    def __init__(self, address):
        self.rm = pyvisa.ResourceManager()
        self.scope = self.rm.open_resource(address)
        print(f"Connected to Scope at {address}")

    def close(self):
        self.scope.close()
        print("Scope connection closed.")
