# zepHIL

A pytest plugin for Hardware-in-the-Loop (HIL) testing of Zephyr devices. 

By design, this plugin **does not depend on `west`**, nor does it require a full Zephyr repository or build directory (unlike `twister`). It is designed for lightweight, standalone integration testing where you have a firmware binary and a physical board.

The HIL test setup assumes a single board running Zephyr OS connected via Serial (for shell interaction) and optionally J-Link (for flashing/control).

## Installation

You can install the plugin directly from the source:

```bash
uv pip install .
```

Or install in editable mode for development:

```bash
uv pip install -e ".[dev]"
```

## Usage

### Command Line Arguments

`zephil` adds several command-line options to pytest for configuring the hardware connection:

| Option | Description | Required | Example |
|---|---|---|---|
| `--board` | Target board identifier | Yes | `frdm_rw612` |
| `--port` | Serial port for shell interaction | Yes | `/dev/tty.usbmodem12345` |
| `--baud` | Serial baud rate | No (Default: 115200) | `115200` |
| `--fw-image` | Path to firmware binary to flash | No | `build/zephyr/zephyr.bin` |

### Writing Tests

The plugin provides the `dut` (Device Under Test) fixture which represents the board and handles shell interaction.

```python
def test_shell_version(dut):
    """Example test checking the Zephyr version."""
    # Send 'version' command and get output
    output = dut.shell_exec_command("version")
    
    # Assert expected output
    assert any("Zephyr version" in line for line in output)

def test_device_reboot(dut):
    """Example accessing the lower-level board object."""
    # Use the high-level shell abstraction to reboot via shell command
    dut.shell_reset()
    
    # Or use the low-level board object directly (if supported by backend)
    # dut.reset() 
```

### Running Tests

```bash
pytest --board=frdm_rw612 --port=/dev/tty.usbmodem1234 --fw-image=zephyr.bin
```

# Acknowledgement
This module was inspired by Zephyr's twister implementation and Golioth's
firmware SDK.