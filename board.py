import queue
import re
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from typing import TextIO

from zephil.transport import Transport

BOOT_BANNER = "Booting Zephyr OS"
LOG_MESSAGE = "<dbg>|<inf>|<wrn>|<err>"


class Board:
    """A Zephyr device, driven through its shell over a transport."""

    def __init__(
        self,
        transport: Transport,
        log: TextIO | None = None,
        name: str = "board",
        shell_prompt: str = "uart:~$",
        timeout: float = 20.0,
    ):
        """`timeout` is how many seconds the board gets to answer or to boot."""
        self.transport = transport
        self.log = log
        self.name = name
        self.shell_prompt = shell_prompt
        self.timeout = timeout

        self._lines: queue.SimpleQueue[str] = queue.SimpleQueue()
        self._stop = threading.Event()
        self._read_error: Exception | None = None

    @contextmanager
    def connected(self):
        """Open the transport and collect the board's output while inside."""
        self._stop.clear()
        self._read_error = None
        reader = threading.Thread(target=self._read_loop, daemon=True)
        self.transport.open()
        reader.start()
        try:
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

    def write(self, data: bytes) -> None:
        if not self.transport.is_open:
            raise RuntimeError(f"{self.name} is not connected")
        self.transport.write(data)

    def discard_output(self) -> None:
        """Forget the lines received so far."""
        try:
            while True:
                self._lines.get_nowait()
        except queue.Empty:
            pass

    def wait_for_line(self, pattern: str, timeout: float | None = None) -> list[str]:
        """Wait for an output line that matches the regex `pattern`.

        Returns the lines received up to and including that line. Only
        complete lines are matched. Raises TimeoutError if none matches.
        """
        if timeout is None:
            timeout = self.timeout
        deadline = time.monotonic() + timeout
        lines = []
        while (line := self._next_line(deadline)) is not None:
            lines.append(line)
            if re.search(pattern, line):
                return lines
        raise TimeoutError(
            f"{self.name} printed no line matching {pattern!r} in {timeout} s"
        )

    def shell_wait_for_prompt(self, timeout: float | None = None) -> None:
        """Press Enter until the shell prompt shows up."""
        if timeout is None:
            timeout = self.timeout
        deadline = time.monotonic() + timeout
        self.discard_output()
        while time.monotonic() < deadline:
            self.write(b"\n")
            try:
                self.wait_for_line(re.escape(self.shell_prompt), timeout=0.5)
                return
            except TimeoutError:
                continue
        raise TimeoutError(f"The shell of {self.name} did not answer in {timeout} s")

    def wait_for_boot(self, timeout: float | None = None) -> None:
        """Wait for the boot banner, then for the shell.

        Call `discard_output()` before whatever restarts the board, so that
        an earlier banner is not mistaken for the new one.
        """
        self.wait_for_line(BOOT_BANNER, timeout)
        self.shell_wait_for_prompt(timeout)

    def shell_run(self, command: str, timeout: float | None = None) -> list[str]:
        """Run a shell command and return the lines it printed.

        The echoed command, the prompt and log messages are left out.
        """
        self.discard_output()
        # Enter is sent twice. The shell prints its prompt without a line
        # ending, so the second Enter is what completes the prompt line that
        # marks the end of the output.
        self.write(f"{command}\n\n".encode())

        lines = []
        try:
            # The echoed command can share its line with a prompt, so read
            # past it before looking for the prompt that ends the output.
            lines += self.wait_for_line(re.escape(command), timeout=1.0)
        except TimeoutError:
            pass
        lines += self.wait_for_line(re.escape(self.shell_prompt), timeout)

        noise = re.compile(f"{re.escape(self.shell_prompt)}|{LOG_MESSAGE}")
        return [line for line in lines if not noise.search(line)]

    def shell_set_setting(self, key: str, value: str) -> None:
        self.shell_run(f"settings set {key} {value}")

    def shell_reboot(self) -> None:
        """Reboot the board from its shell and wait until the shell is back."""
        self.discard_output()
        # A single Enter, and no waiting for a prompt: the board reboots
        # before it can print one.
        self.write(b"kernel reboot cold\n")
        self.wait_for_boot()

    def flash(self, hex_file: str) -> None:
        """Write firmware to the board and wait until its shell is up."""
        raise NotImplementedError(f"{type(self).__name__} cannot flash firmware")
