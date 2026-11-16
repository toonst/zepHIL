# zepHIL

A pytest plugin for Hardware-in-the-Loop (HIL) tests on Zephyr boards.

Your tests get a `dut` fixture: a real board that you talk to through its
Zephyr shell over a serial port. zepHIL can also flash firmware onto it.

Unlike `twister`, zepHIL needs no `west`, no Zephyr repository and no build
directory. A board and, if you want to flash, a `.hex` file are enough.

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

Test the firmware that is already on the board:

```bash
pytest --board=frdm_rw612 --serial-port=/dev/ttyACM0
```

Flash firmware first, once, before the first test:

```bash
pytest --board=frdm_rw612 --serial-port=/dev/ttyACM0 --flash=zephyr.hex
```

| Option | Description | Default |
|---|---|---|
| `--board` | Board to test. Without it, tests that use `dut` are skipped. | |
| `--serial-port` | Serial port of the board's shell. Required with `--board`. | |
| `--baud-rate` | Baud rate of the serial port. | `115200` |
| `--flash` | `.hex` file to flash before the first test. | nothing is flashed |
| `--serial-log` | File that receives everything the board prints. | `zephil.log` |

### Writing tests

```python
def test_version(dut):
    lines = dut.run("version")

    assert "Zephyr version" in lines[0]


def test_shell_works_after_a_reboot(dut):
    dut.reboot()

    assert dut.run("version")


def test_update_keeps_the_settings(dut):
    dut.set_setting("app/name", "kitchen")

    dut.flash("build/update.hex")

    assert dut.run("app name") == ["kitchen"]
```

All tests share one `dut`: the board stays connected for the whole test run.
A test that flashes other firmware leaves it on the board for the tests that
follow.

### What `dut` can do

| Method | What it does |
|---|---|
| `run(command)` | Runs a shell command and returns the lines it printed. Log messages are left out. |
| `set_setting(key, value)` | Runs `settings set <key> <value>`. |
| `wait_for_line(pattern)` | Waits for an output line that matches the regex. Returns the lines up to it. |
| `wait_for_shell()` | Presses Enter until the shell prompt appears. |
| `reboot()` | Reboots with the shell command `kernel reboot cold`. |
| `reset()` | Resets the chip through the J-Link probe. |
| `flash(hex_file)` | Flashes firmware through the J-Link probe. |
| `erase()` | Erases the whole flash through the J-Link probe. |
| `read_memory(address, size)` | Reads memory through the J-Link probe and returns the bytes. |

`reboot()`, `reset()` and `flash()` return once the board has booted and its
shell answers again. A method that waits raises `TimeoutError` after 20
seconds. `run` and the `wait_for_...` methods take a `timeout` argument to
change that.

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
