# zepHIL

A pytest plugin for Hardware-in-the-Loop (HIL) tests on Zephyr boards.

Your tests get a `dut` fixture: a real board that you talk to through its
Zephyr shell over a serial port. zepHIL can also flash a firmware image first.

Unlike `twister`, zepHIL needs no `west`, no Zephyr repository and no build
directory. A board and, if you want to flash, a firmware file are enough.

## Requirements

- Python 3.10 or newer.
- A board whose firmware has the Zephyr shell enabled on a serial port.
- For flashing and hardware reset: a J-Link probe and the
  [J-Link software](https://www.segger.com/downloads/jlink/).

Supported boards: `frdm_rw612`.

## Installation

```bash
uv pip install .
```

pytest loads the plugin automatically once it is installed.

## Usage

```bash
pytest --board=frdm_rw612 --port=/dev/ttyACM0 --fw-image=zephyr.hex
```

| Option | Description | Default |
|---|---|---|
| `--board` | Board to test. Without it, tests that use `dut` are skipped. | |
| `--port` | Serial port of the board's shell. Required with `--board`. | |
| `--baud` | Serial baud rate. | `115200` |
| `--fw-image` | Firmware to flash. Without it, nothing is flashed. | |
| `--logfile` | File that receives everything the board prints. | `zephil.log` |

Use a `.hex` or `.elf` file for `--fw-image`. A `.bin` file does not say where
it belongs in memory, and zepHIL writes it to address 0.

### Writing tests

```python
def test_shell_version(dut):
    lines = dut.shell_exec_command("version")

    assert any("Zephyr version" in line for line in lines)


def test_shell_works_after_a_reboot(dut):
    dut.shell_reset()

    assert dut.shell_exec_command("version")
```

`dut` is set up once per test file: zepHIL flashes the firmware, opens the
serial port and waits 6 seconds for the board to boot.

### What `dut` can do

Through the shell:

| Method | What it does |
|---|---|
| `shell_exec_command(command)` | Runs a command. Returns the printed lines, including the echoed command and the final prompt. |
| `shell_get_filtered_output(lines)` | Removes prompt lines and log messages from those lines. |
| `shell_wait_for_prompt()` | Presses Enter until the prompt appears. Returns `False` on timeout. |
| `shell_reset()` | Reboots with `kernel reboot cold` and waits for the shell to come back. |
| `shell_set_setting(key, value)` | Runs `settings set <key> <value>`. |
| `readlines_until(regex)` | Waits for an output line that matches. Returns the lines up to it. |

Through the J-Link probe:

| Method | What it does |
|---|---|
| `reset()` | Resets the chip. |
| `erase()` | Erases the whole flash. |
| `program(fw_image)` | Flashes a firmware file. |
| `dump_memory(address, size)` | Reads memory and returns the bytes. |

zepHIL expects exactly one J-Link probe to be attached.

## Adding a board

1. Create a class for it. A board with a J-Link probe only needs its J-Link
   device name: see `frdm_rw612.py`.
2. Add the class to `BOARDS` in `plugin.py`.

## Development

```bash
uv sync
uv run pytest
```

The tests run against a simulated board, so no hardware is needed.

## Acknowledgement

This module was inspired by Zephyr's twister implementation and Golioth's
firmware SDK.
