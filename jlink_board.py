from contextlib import contextmanager

from zephil.board import Board


class JLinkBoard(Board):
    """A board that is flashed and reset through a SEGGER J-Link probe."""

    # The name J-Link uses for the chip. Every board subclass sets this.
    jlink_device: str

    def __init__(self, *args, jlink_serial: int | None = None, **kwargs):
        """`jlink_serial` picks a probe; leave it out when only one is attached."""
        super().__init__(*args, **kwargs)
        self.jlink_serial = jlink_serial

    @contextmanager
    def _jlink(self):
        # Imported here because it is slow and only needed to reach the probe.
        import pylink

        jlink = pylink.JLink()
        jlink.open(self.jlink_serial)
        try:
            jlink.set_tif(pylink.JLinkInterfaces.SWD)
            jlink.connect(self.jlink_device)
            yield jlink
        finally:
            jlink.close()

    def reset(self) -> None:
        """Reset the chip through the probe and wait until the shell is back."""
        self.discard_output()
        with self._jlink() as jlink:
            jlink.reset(halt=False)
        self.wait_for_boot()

    def flash(self, hex_file: str, erase_first: bool = False) -> None:
        """Write firmware to the board and wait until its shell is up."""
        if not hex_file.endswith(".hex"):
            # Other formats may not say where the firmware belongs in memory.
            raise ValueError(f"Expected a .hex file, got {hex_file}")
        self.discard_output()
        with self._jlink() as jlink:
            jlink.reset()
            if erase_first:
                jlink.erase()
            jlink.flash_file(hex_file, 0)
            jlink.reset(halt=False)
        self.wait_for_boot()

    def erase(self) -> None:
        """Erase the whole flash. The board has no firmware afterwards."""
        with self._jlink() as jlink:
            jlink.erase()

    def read_memory(self, address: int, size: int) -> bytes:
        with self._jlink() as jlink:
            return bytes(jlink.memory_read8(address, size))
