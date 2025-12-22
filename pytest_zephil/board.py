from abc import ABC, abstractmethod
from contextlib import contextmanager
import re
import time

import serial

class Board(ABC):
    def __init__(self, port: str, baudrate: int, fw_image: str | None):
        self.port = port
        self.baudrate = baudrate
        self.fw_image = fw_image
        self.received: bytes = b''
        self.serial: serial.Serial | None = None

    @contextmanager
    def started(self):
        if self.fw_image:
            self.program(self.fw_image)
        # timeout=0.1 allows read() to return periodically so we can check logical timeouts
        with serial.Serial(port=self.port,
                           baudrate=self.baudrate,
                           timeout=0.1) as ser:
            self.serial = ser
            # Wait for reboot
            time.sleep(6)
            yield self

    def receive_some(self) -> bytes | None:
        if self.serial is None:
             raise RuntimeError("Board not started")
        # read_all() or read(size) depending on what is available; 
        # using read() with timeout set in __init__ serves similar purpose to receive_some
        return self.serial.read(self.serial.in_waiting or 1)

    def send_all(self, data: bytes) -> None:
        if self.serial is None:
             raise RuntimeError("Board not started")
        self.serial.write(data)

    def clear_buffer(self):
        """Clear internal buffer and serial input buffer."""
        self.received = b''
        if self.serial:
            self.serial.reset_input_buffer()

    def readline(self, timeout=None):
        """
        Read a single line from the serial port.
        Uses the internal buffer first.
        """
        start_time = time.time()
        while True:
            if timeout and time.time() - start_time > timeout:
                raise TimeoutError("Timeout reading line")

            if b'\n' in self.received:
                line_bytes, rest = self.received.split(b'\n', 1)
                self.received = rest
                return line_bytes.replace(b'\r', b'').decode('utf-8', errors='ignore')

            chunk = self.receive_some()
            if chunk:
                # print(chunk.replace(b'\r', b'').decode('utf-8', errors='ignore'), end='', flush=True)
                self.received += chunk
            else:
                # If no data and no timeout specified, or purely relying on serial timeout
                if timeout is None:
                     # Avoid tight loop if we rely on receive_some's internal blocking or lack thereof
                     # But receive_some (serial.read) has a 0.1s timeout from __init__
                     pass

    def readlines_until(self, regex=None, timeout_s=20):
        start_time = time.time()
        lines_captured = []
        while True:
            if time.time() - start_time > timeout_s:
                raise TimeoutError(f"Timeout waiting for {regex}")

            # Check lines in buffer
            # We strictly only process lines ending in \n to avoid matching partials
            while b'\n' in self.received:
                line_bytes, rest = self.received.split(b'\n', 1)
                # line_bytes does not contain \n.
                # But it might contain \r.
                decoded_line = line_bytes.replace(b'\r', b'').decode('utf-8', errors='ignore')
                lines_captured.append(decoded_line)
                
                # Update buffer
                self.received = rest
                
                if regex and re.search(regex, decoded_line):
                    return lines_captured

            # Read more
            chunk = self.receive_some()
            if chunk:
                # Optional: print raw chunk
                print(chunk.replace(b'\r', b'').decode('utf-8', errors='ignore'), end='', flush=True)
                self.received += chunk

    def program(self, fw_image):
        pass
