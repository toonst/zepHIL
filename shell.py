import logging
import re
import time
from dataclasses import dataclass, field
from inspect import signature

logger = logging.getLogger(__name__)


class Shell:
    """
    Helper class that provides methods used to interact with shell application.
    """

    def __init__(
        self, dut, prompt: str = 'uart:~$', timeout: float = 20.0
    ) -> None:
        self.dut = dut
        self.prompt: str = prompt.rstrip('\r\n')
        self.base_timeout: float = timeout

    def wait_for_prompt(self, timeout: float | None = None) -> bool:
        """
        Send every 0.5 second "enter" command to the device until shell prompt
        statement will occur (return True) or timeout will be exceeded (return
        False).
        """
        timeout = timeout or self.base_timeout
        timeout_time = time.time() + timeout
        self.dut.clear_buffer()
        while time.time() < timeout_time:
            self.dut.send_all(b'\n')
            try:
                line = self.dut.readline(timeout=0.5)
            except TimeoutError:
                # ignore read timeout and try to send enter once again
                continue
            if self.prompt in line:
                # logger.debug('Got prompt')
                return True
        return False

    def exec_command(
        self, command: str, timeout: float | None = None, print_output: bool = True
    ) -> list[str]:
        """
        Send shell command to a device and return response. Passed command
        is extended by double enter sings - first one to execute this command
        on a device, second one to receive next prompt what is a signal that
        execution was finished. Method returns printout of the executed command.
        """
        timeout = timeout or self.base_timeout
        command_ext = f'{command}\n\n'
        regex_prompt = re.escape(self.prompt)
        regex_command = f'.*{re.escape(command)}'
        self.dut.clear_buffer()
        self.dut.send_all(command_ext.encode())
        lines: list[str] = []
        # wait for device command print - it should be done immediately after sending command to device
        try:
            lines.extend(
                self.dut.readlines_until(
                    regex=regex_command, timeout_s=1.0
                )
            )
        except TimeoutError:
            # If we miss the echo, we might still get the prompt.
            # Proceeding to wait for prompt.
            pass

        # wait for device command execution
        lines.extend(
            self.dut.readlines_until(
                regex=regex_prompt, timeout_s=timeout
            )
        )
        return lines

    def get_filtered_output(self, command_lines: list[str]) -> list[str]:
        """
        Filter out prompts and log messages

        Take the output of exec_command, which can contain log messages and command prompts,
        and filter them to obtain only the command output.
        """
        regex_filter = re.compile(
            '|'.join([re.escape(self.prompt), '<dbg>', '<inf>', '<wrn>', '<err>'])
        )
        return list(filter(lambda l: not regex_filter.search(l), command_lines))

    def reset(self):
        self.exec_command('kernel reboot cold')
        self.dut.readlines_until('Booting Zephyr OS', timeout_s=self.base_timeout)

    def set_setting(self, key, value):
        self.exec_command(f'settings set {key} {value}')


@dataclass
class ShellMCUbootArea:
    name: str
    version: str
    image_size: str
    magic: str = 'unset'
    swap_type: str = 'none'
    copy_done: str = 'unset'
    image_ok: str = 'unset'

    @classmethod
    def from_kwargs(cls, **kwargs) -> 'ShellMCUbootArea':
        cls_fields = {field for field in signature(cls).parameters}
        native_args = {}
        for name, val in kwargs.items():
            if name in cls_fields:
                native_args[name] = val
        return cls(**native_args)


@dataclass
class ShellMCUbootCommandParsed:
    """
    Helper class to keep data from `mcuboot` shell command.
    """

    areas: list[ShellMCUbootArea] = field(default_factory=list)

    @classmethod
    def create_from_cmd_output(cls, cmd_output: list[str]) -> 'ShellMCUbootCommandParsed':
        """
        Factory to create class from the output of `mcuboot` shell command.
        """
        areas: list[dict] = []
        re_area = re.compile(r'(.+ area.*):\s*$')
        re_key = re.compile(r'(?P<key>.+):(?P<val>.+)')
        for line in cmd_output:
            if m := re_area.search(line):
                areas.append({'name': m.group(1)})
            elif areas:
                if m := re_key.search(line):
                    areas[-1][m.group('key').strip().replace(' ', '_')] = m.group('val').strip()
        data_areas: list[ShellMCUbootArea] = []
        for area in areas:
            data_areas.append(ShellMCUbootArea.from_kwargs(**area))

        return cls(data_areas)