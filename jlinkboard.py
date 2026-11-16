from contextlib import contextmanager

from zephil.board import Board


class JLinkBoard(Board):
    """A board that is flashed and reset through a SEGGER J-Link probe."""

    # The J-Link device name. Every board subclass sets this.
    chip_name: str

    def __init__(self, *args, serial_number: int | None = None, **kwargs):
        """`serial_number` picks a probe; leave it out when only one is attached."""
        super().__init__(*args, **kwargs)
        self.serial_number = serial_number

    @contextmanager
    def _jlink(self):
        # Imported here because it is slow and only needed to reach the probe.
        import pylink

        jlink = pylink.JLink()
        jlink.open(self.serial_number)
        try:
            jlink.set_tif(pylink.JLinkInterfaces.SWD)
            jlink.connect(self.chip_name)
            yield jlink
        finally:
            jlink.close()

    def reset(self) -> None:
        with self._jlink() as jlink:
            jlink.reset(halt=False)

    def erase(self) -> None:
        with self._jlink() as jlink:
            jlink.erase()

    def program(self, fw_image: str, full_erase: bool = False) -> None:
        with self._jlink() as jlink:
            jlink.reset()
            if full_erase:
                jlink.erase()
            jlink.flash_file(fw_image, 0)
            jlink.reset(halt=False)

    def dump_memory(self, start_address: int, size: int) -> bytearray:
        with self._jlink() as jlink:
            return bytearray(jlink.memory_read8(start_address, size))
