from abc import ABC, abstractmethod
from contextlib import contextmanager
import re
import time
import logging
import os
import queue
import threading

import serial

class Board(ABC):
    def __init__(self, port: str, baudrate: int, fw_image: str | None, logfile: str | None = None):
        self.port = port
        self.baudrate = baudrate
        self.fw_image = fw_image
        self.logfile = logfile
        self.received: bytes = b''
        self.serial: serial.Serial | None = None
        
        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        self._thread = None
        self._log_buffer = b''
        self.file_logger = None

    def _setup_logger(self):
        if not self.logfile:
            return

        log_file_path = os.path.normpath(self.logfile)
        log_dir = os.path.dirname(log_file_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        self.file_logger = logging.getLogger(f"zephil_{self.port}")
        self.file_logger.setLevel(logging.DEBUG)
        self.file_logger.propagate = False
        
        if not self.file_logger.handlers:
            file_handler = logging.FileHandler(log_file_path, mode='w')
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('[%(asctime)s] <%(levelname)s> %(name)s: %(message)s')
            file_handler.setFormatter(formatter)
            self.file_logger.addHandler(file_handler)

    def _handle_incoming_data(self, data):
        self._queue.put(data)
        
        if self.file_logger:
            self._log_buffer += data
            while b'\n' in self._log_buffer:
                line, rest = self._log_buffer.split(b'\n', 1)
                self._log_buffer = rest
                # decode and strip
                line_str = line.decode('utf-8', errors='replace').rstrip()
                self.file_logger.info(line_str)

    def _read_loop(self):
        while not self._stop_event.is_set():
            try:
                if self.serial and self.serial.is_open:
                    # Block for up to timeout (0.1s) waiting for at least one byte
                    data = self.serial.read(1)
                    if data:
                        # If we got data, read whatever else is immediately available
                        if self.serial.in_waiting:
                            data += self.serial.read(self.serial.in_waiting)
                        self._handle_incoming_data(data)
                else:
                    break
            except Exception:
                break

    @contextmanager
    def started(self):
        if self.fw_image:
            self.program(self.fw_image)
            
        self._setup_logger()

        # timeout=0.1 allows read() to return periodically so we can check logical timeouts
        with serial.Serial(port=self.port,
                           baudrate=self.baudrate,
                           timeout=0.1) as ser:
            self.serial = ser
            
            # Start background thread
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._read_loop, daemon=True)
            self._thread.start()

            # Wait for reboot
            time.sleep(6)
            
            try:
                yield self
            finally:
                self._stop_event.set()
                if self._thread:
                    self._thread.join(timeout=2)
                    self._thread = None

    def receive_some(self) -> bytes | None:
        if self.serial is None:
             raise RuntimeError("Board not started")
        
        try:
            return self._queue.get(block=True, timeout=0.1)
        except queue.Empty:
            return None

    def send_all(self, data: bytes) -> None:
        if self.serial is None:
             raise RuntimeError("Board not started")
        self.serial.write(data)

    def clear_buffer(self):
        """Clear internal buffer, serial input buffer, and the thread queue."""
        self.received = b''
        if self.serial:
            self.serial.reset_input_buffer()
        
        # Drain the queue
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass

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
