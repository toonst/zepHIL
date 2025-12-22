from abc import ABC, abstractmethod
from contextlib import contextmanager
import re
import time

import serial

class Board(ABC):
    def __init__(self, port, baudrate, fw_image, serial_number=None,
                 bmp_port=None):
        if serial_number is not None:
            self.serial_number = serial_number
        if bmp_port is not None:
            self.bmp_port = bmp_port
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

    def receive_some(self) -> bytes:
        assert self.serial is not None
        # read_all() or read(size) depending on what is available; 
        # using read() with timeout set in __init__ serves similar purpose to receive_some
        return self.serial.read(self.serial.in_waiting or 1)

    def send_all(self, data: bytes):
        assert self.serial is not None
        self.serial.write(data)

    def wait_for_regex_in_line(self, regex, timeout_s=20, log=True):
        start_time = time.time()
        while True:
            if time.time() - start_time > timeout_s:
                raise TimeoutError(f"Timeout waiting for {regex}")

            # Check in already received data
            lines = self.received.splitlines(keepends=True)

            for idx, line in enumerate(lines):
                # Only check complete lines (ending in newline) unless it's the only content and we are looping
                # But original logic checked everything. Let's stick to decoding lines.
                decoded_line = line.replace(b'\r', b'').replace(b'\n', b'').decode('utf-8', errors='ignore')
                regex_search = re.search(regex, decoded_line)
                if regex_search:
                    # Drop this and any previous lines
                    self.received = b''.join(lines[idx+1:])
                    return regex_search

            # Drop all but last line (in case it is not complete)
            if len(lines) > 1:
                self.received = lines[-1]

            # Receive more data
            chunk = self.receive_some()
            if not chunk:
                # If read returns nothing (timeout), just continue loop to check total timeout
                continue

            if log:
                print(chunk.replace(b'\r', b'').decode('utf-8', errors='ignore'), end='', flush=True)

            self.received = self.received + chunk

    def send_cmd(self, cmd, wait_str=None):
        if wait_str == None:
            wait_str = self.PROMPT
        self.send_all('\r\n\r\n'.encode())
        self.wait_for_regex_in_line(self.PROMPT)
        self.send_all('{}\r\n'.format(cmd).encode())
        self.wait_for_regex_in_line(wait_str)

    @property
    def PROMPT(self):
        return 'uart:'

    def reset(self):
        self.send_cmd('kernel reboot cold', wait_str='Booting Zephyr OS')

    def set_setting(self, key, value):
        self.send_cmd(f'settings set {key} {value}', wait_str='saved')

    def program(self, fw_image):
        pass
