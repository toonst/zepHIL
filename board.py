import queue
import re
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from typing import TextIO

from zephil.transport import Transport


class Board:
    """A Zephyr device, driven through its shell over a transport."""

    # Seconds to wait for the firmware to boot once the transport is open.
    boot_delay = 6.0

    def __init__(
        self,
        transport: Transport,
        fw_image: str | None = None,
        log: TextIO | None = None,
        name: str = "board",
        shell_prompt: str = "uart:~$",
        shell_timeout: float = 20.0,
    ):
        self.transport = transport
        self.fw_image = fw_image
        self.log = log
        self.name = name
        self.shell_prompt = shell_prompt.rstrip("\r\n")
        self.shell_timeout = shell_timeout

        self._lines: queue.SimpleQueue[str] = queue.SimpleQueue()
        self._stop = threading.Event()
        self._read_error: Exception | None = None

    @contextmanager
    def started(self):
        """Flash the firmware if one was given, then connect to the board."""
        if self.fw_image:
            self.program(self.fw_image)

        self._stop.clear()
        self._read_error = None
        reader = threading.Thread(target=self._read_loop, daemon=True)
        self.transport.open()
        reader.start()
        try:
            time.sleep(self.boot_delay)
            yield self
        finally:
            self._stop.set()
            reader.join(timeout=2)
            self.transport.close()

    def _read_loop(self) -> None:
        """Split the incoming bytes into lines; log each line and queue it."""
        partial = b""
        try:
            while not self._stop.is_set():
                *lines, partial = (partial + self.transport.read()).split(b"\n")
                for raw in lines:
                    line = raw.replace(b"\r", b"").decode("utf-8", errors="replace")
                    if self.log is not None:
                        now = datetime.now().isoformat(sep=" ", timespec="milliseconds")
                        self.log.write(f"[{now}] {line}\n")
                    self._lines.put(line)
        except Exception as error:
            self._read_error = error

    def _next_line(self, deadline: float) -> str | None:
        """Return the next received line, or None once `deadline` has passed."""
        while True:
            remaining = deadline - time.monotonic()
            try:
                return self._lines.get(timeout=max(0.0, min(remaining, 0.1)))
            except queue.Empty:
                if self._read_error:
                    raise ConnectionError(
                        f"Lost the connection to {self.name}"
                    ) from self._read_error
                if remaining <= 0:
                    return None

    def send_all(self, data: bytes) -> None:
        if not self.transport.is_open:
            raise RuntimeError("Board not started")
        self.transport.write(data)

    def clear_buffer(self) -> None:
        """Forget the lines received so far."""
        try:
            while True:
                self._lines.get_nowait()
        except queue.Empty:
            pass

    def readlines_until(self, regex: str, timeout_s: float = 20.0) -> list[str]:
        """Return the received lines up to and including the first match of `regex`.

        Only complete lines are matched. Raises TimeoutError if none matches
        within `timeout_s` seconds.
        """
        deadline = time.monotonic() + timeout_s
        lines = []
        while (line := self._next_line(deadline)) is not None:
            lines.append(line)
            if re.search(regex, line):
                return lines
        raise TimeoutError(f"Timeout waiting for {regex}")

    def shell_wait_for_prompt(self, timeout: float | None = None) -> bool:
        """Press Enter until the shell prompt shows up. Return False on timeout."""
        if timeout is None:
            timeout = self.shell_timeout
        deadline = time.monotonic() + timeout
        self.clear_buffer()
        while time.monotonic() < deadline:
            self.send_all(b"\n")
            try:
                self.readlines_until(re.escape(self.shell_prompt), timeout_s=0.5)
                return True
            except TimeoutError:
                continue
        return False

    def shell_exec_command(
        self, command: str, timeout: float | None = None
    ) -> list[str]:
        """Run a shell command and return the lines printed up to the next prompt.

        Enter is sent twice. The shell prints its prompt without a line ending,
        so the second Enter is what completes the prompt line that marks the
        end of the output.
        """
        if timeout is None:
            timeout = self.shell_timeout
        self.clear_buffer()
        self.send_all(f"{command}\n\n".encode())

        lines = []
        try:
            # The echoed command can share its line with a prompt, so read
            # past it before looking for the prompt that ends the output.
            lines += self.readlines_until(re.escape(command), timeout_s=1.0)
        except TimeoutError:
            pass
        lines += self.readlines_until(re.escape(self.shell_prompt), timeout_s=timeout)
        return lines

    def shell_get_filtered_output(self, command_lines: list[str]) -> list[str]:
        """Drop the prompt lines and log messages from `shell_exec_command` output."""
        noise = re.compile(
            "|".join([re.escape(self.shell_prompt), "<dbg>", "<inf>", "<wrn>", "<err>"])
        )
        return [line for line in command_lines if not noise.search(line)]

    def shell_reset(self) -> None:
        """Reboot the board from the shell and wait until the shell is back."""
        self.clear_buffer()
        # A single Enter, and no waiting for a prompt: the board reboots
        # before it can print one.
        self.send_all(b"kernel reboot cold\n")
        self.readlines_until("Booting Zephyr OS", timeout_s=self.shell_timeout)
        if not self.shell_wait_for_prompt():
            raise TimeoutError("Timeout waiting for the shell after a reboot")

    def shell_set_setting(self, key: str, value: str) -> None:
        self.shell_exec_command(f"settings set {key} {value}")

    def program(self, fw_image: str) -> None:
        raise NotImplementedError(f"{type(self).__name__} cannot flash firmware")
