from abc import ABC, abstractmethod
from contextlib import contextmanager
import re
import time
import logging
import os
import queue
import threading
from dataclasses import dataclass, field

from zephil.transport import Transport

logger = logging.getLogger(__name__)

class Board(ABC):
    def __init__(self, transport: Transport, fw_image: str | None, logfile: str | None = None, name: str = "board", shell_prompt: str = 'uart:~$', shell_timeout: float = 20.0):
        self.transport = transport
        self.fw_image = fw_image
        self.logfile = logfile
        self.name = name
        self.shell_prompt = shell_prompt.rstrip('\r\n')
        self.shell_timeout = shell_timeout
        self.received: bytes = b''

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

        self.file_logger = logging.getLogger(f"zephil_{self.name}")
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
                line_str = line.decode('utf-8', errors='replace').rstrip()
                self.file_logger.info(line_str)

    def _read_loop(self):
        while not self._stop_event.is_set():
            try:
                if self.transport.is_open:
                    # Block for up to timeout (0.1s) waiting for at least one byte
                    # The transport.read should ideally handle timeout or non-blocking
                    # But our SerialTransport wrapper uses serial's timeout.
                    data = self.transport.read(1)
                    if data:
                        # If we got data, read whatever else is immediately available
                        if self.transport.in_waiting:
                            data += self.transport.read(self.transport.in_waiting)
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

        try:
            self.transport.open()

            # Start background thread
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._read_loop, daemon=True)
            self._thread.start()

            # Wait for reboot
            time.sleep(6)

            yield self
        finally:
            self._stop_event.set()
            if self._thread:
                self._thread.join(timeout=2)
                self._thread = None
            self.transport.close()

    def receive_some(self) -> bytes | None:
        if not self.transport.is_open:
             raise RuntimeError("Board not started")

        try:
            return self._queue.get(block=True, timeout=0.1)
        except queue.Empty:
            return None

    def send_all(self, data: bytes) -> None:
        if not self.transport.is_open:
             raise RuntimeError("Board not started")
        self.transport.write(data)

    def clear_buffer(self):
        """Clear internal buffer, serial input buffer, and the thread queue."""
        self.received = b''
        if self.transport.is_open:
            self.transport.flush_input()

        # Drain the queue
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass

    def shell_wait_for_prompt(self, timeout: float | None = None) -> bool:
        """
        Send "enter" command to the device until shell prompt
        statement will occur (return True) or timeout will be exceeded (return
        False).
        """
        timeout = timeout or self.shell_timeout
        timeout_time = time.time() + timeout
        self.clear_buffer()
        regex_prompt = re.escape(self.shell_prompt)

        while time.time() < timeout_time:
            self.send_all(b'\n')
            try:
                self.readlines_until(regex=regex_prompt, timeout_s=0.5)
                # logger.debug('Got prompt')
                return True
            except TimeoutError:
                # ignore read timeout and try to send enter once again
                continue
        return False

    def shell_exec_command(
        self, command: str, timeout: float | None = None
    ) -> list[str]:
        """
        Send shell command to a device and return response. Passed command
        is extended by double enter sings - first one to execute this command
        on a device, second one to receive next prompt what is a signal that
        execution was finished.
        Method returns printout of the executed command.
        """
        timeout = timeout or self.shell_timeout
        command_ext = f'{command}\n\n'
        regex_prompt = re.escape(self.shell_prompt)
        regex_command = f'.*{re.escape(command)}'
        self.clear_buffer()
        self.send_all(command_ext.encode())
        lines: list[str] = []
        # wait for device command print - it should be done immediately after sending command to device
        try:
            lines.extend(
                self.readlines_until(
                    regex=regex_command, timeout_s=1.0
                )
            )
        except TimeoutError:
            # If we miss the echo, we might still get the prompt.
            # Proceeding to wait for prompt.
            pass

        # wait for device command execution
        lines.extend(
            self.readlines_until(
                regex=regex_prompt, timeout_s=timeout
            )
        )
        return lines

    def shell_get_filtered_output(self, command_lines: list[str]) -> list[str]:
        """
        Filter out prompts and log messages

        Take the output of exec_command, which can contain log messages and command prompts,
        and filter them to obtain only the command output.
        """
        regex_filter = re.compile(
            '|'.join([re.escape(self.shell_prompt), '<dbg>', '<inf>', '<wrn>', '<err>'])
        )
        return list(filter(lambda l: not regex_filter.search(l), command_lines))

    def shell_reset(self):
        self.shell_exec_command('kernel reboot cold')
        self.readlines_until('Booting Zephyr OS', timeout_s=self.shell_timeout)

    def shell_set_setting(self, key, value):
        self.shell_exec_command(f'settings set {key} {value}')

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
                self.received += chunk

    def program(self, fw_image):
        pass