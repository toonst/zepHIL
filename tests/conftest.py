import threading
import time
from unittest.mock import create_autospec

import pylink
import pytest
import serial

pytest_plugins = ["pytester"]


class FakeDevice:
    """Stands in for `serial.Serial`, with a small Zephyr shell on the other end."""

    BANNER = b"*** Booting Zephyr OS build v3.7.0 ***\r\n"
    PROMPT = b"uart:~$ "

    def __init__(self):
        # Shell command -> the lines it prints. None means it never returns.
        self.commands = {"version": ["Zephyr version 3.7.0"]}
        self.responsive = True
        self.read_error = None
        self.boots = 0
        self.opens = 0
        self.ran = []
        self.is_open = False
        self._typed = bytearray()
        self._output = bytearray()
        self._lock = threading.Lock()

    def __call__(self, port, baudrate, timeout):
        """Called in place of `serial.Serial(...)`."""
        self.is_open = True
        self.opens += 1
        self.boot()
        return self

    def close(self):
        self.is_open = False

    @property
    def in_waiting(self):
        return len(self._output)

    def read(self, size=1):
        if self.read_error:
            raise self.read_error
        with self._lock:
            data = bytes(self._output[:size])
            del self._output[:size]
        if not data:
            time.sleep(0.005)
        return data

    def write(self, data):
        for char in data.decode():
            if not self.responsive:
                return
            if char != "\n":
                self._typed += char.encode()
                self.emit(char.encode())
            elif not self._run(self._typed.decode()):
                return

    def emit(self, data):
        """Make the device print `data`."""
        with self._lock:
            self._output += data

    def boot(self):
        if not self.responsive:
            return
        self.boots += 1
        self._typed.clear()
        self.emit(self.BANNER + self.PROMPT)

    def _run(self, command):
        """Run one typed line. Return False if the rest of the input is lost."""
        self._typed.clear()
        if command:
            self.ran.append(command)
        if command == "kernel reboot cold":
            # A real board resets at once: nothing more is printed or read.
            self.boot()
            return False

        self.emit(b"\r\n")
        output = self.commands.get(command, [])
        if output is None:
            self.responsive = False
            return False
        for line in output:
            self.emit(line.encode() + b"\r\n")
        self.emit(self.PROMPT)
        return True


@pytest.fixture
def device(monkeypatch):
    """A fake board on every serial port."""
    device = FakeDevice()
    monkeypatch.setattr(serial, "Serial", device)
    return device


@pytest.fixture
def jlink(monkeypatch, device):
    """A fake J-Link probe that records how it is used and restarts the board."""
    jlink = create_autospec(pylink.JLink, instance=True)
    jlink.reset.side_effect = lambda ms=0, halt=True: halt or device.boot()
    monkeypatch.setattr(pylink, "JLink", lambda: jlink)
    return jlink
