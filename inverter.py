import minimalmodbus
from threading import Lock

class Inverter(minimalmodbus.Instrument):
    def __init__(self, name, device, slave_address):
        super().__init__(device, slave_address)
        self.serial.baudrate = 9600
        self.serial.timeout = 0.35
        self.offline = False
        self.loopCount = 0
        self.name = name

    def read_composed_date(self, register, functioncode):
        year = self.read_register(register[0], functioncode=functioncode)
        month = self.read_register(register[1], functioncode=functioncode)
        day = self.read_register(register[2], functioncode=functioncode)
        hour = self.read_register(register[3], functioncode=functioncode)
        minute = self.read_register(register[4], functioncode=functioncode)
        second = self.read_register(register[5], functioncode=functioncode)
        return f"20{year:02d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}"
