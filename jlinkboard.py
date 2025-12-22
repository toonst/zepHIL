import pylink

from .board import Board

class JLinkBoard(Board):
    def __init__(self, chip_name, transport, *args, **kwargs):
        super().__init__(transport, *args, **kwargs)
        self.chip_name = chip_name
        self.jlink = None
        self.serial_number = 1234 # To Do: fix this, autmatically detect

    def _connect(self):
        self.jlink = pylink.JLink()
        self.jlink.open(int(self.serial_number))
        self.jlink.set_tif(pylink.JLinkInterfaces.SWD)
        self.jlink.connect(self.chip_name)
        return self.jlink

    def reset(self):
        jlink = self._connect()
        jlink.reset(halt=False)

    def erase(self):
        jlink = self._connect()
        jlink.erase()

    def program(self, fw_image, full_erase=False):
        jlink = self._connect()
        jlink.reset()
        if full_erase:
            jlink.erase()
        jlink.flash_file(fw_image, 0)
        jlink.reset(halt=False)
        
    def dump_memory(self, start_address, size):
        jlink = self._connect()
        memory_data = bytearray(jlink.read_mem(start_address, size))
        return memory_data
