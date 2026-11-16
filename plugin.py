from pathlib import Path

import pytest

from zephil.frdm_rw612 import FRDMRW612
from zephil.transport import SerialTransport

# To support a new board, add its class here.
BOARDS = {
    "frdm_rw612": FRDMRW612,
}


def pytest_addoption(parser):
    group = parser.getgroup("zephil", "Zephyr hardware-in-the-loop tests")
    group.addoption(
        "--board",
        choices=sorted(BOARDS),
        help="Board to test. Without it, tests that use `dut` are skipped.",
    )
    group.addoption(
        "--serial-port",
        help="Serial port of the board's shell (eg: /dev/ttyACM0)",
    )
    group.addoption(
        "--baud-rate",
        type=int,
        default=115200,
        help="Baud rate of the serial port (default: 115200)",
    )
    group.addoption(
        "--flash",
        metavar="HEX_FILE",
        help="Firmware to flash once, before the first test. "
        "Without it, the tests run on the firmware the board already has.",
    )
    group.addoption(
        "--serial-log",
        default="zephil.log",
        help="File that receives everything the board prints (default: zephil.log)",
    )


def pytest_configure(config):
    if config.getoption("board") and not config.getoption("serial_port"):
        raise pytest.UsageError("--board also needs --serial-port")


@pytest.fixture(scope="session")
def dut(request):
    """The board under test, connected for the whole test run."""
    option = request.config.getoption
    name = option("board")
    if not name:
        pytest.skip("No --board specified for HIL test.")

    port, baud_rate = option("serial_port"), option("baud_rate")
    print(f"\n[Zephil] Setting up DUT: {name} on {port}@{baud_rate}")

    log_path = Path(option("serial_log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    # Line buffered, so the file can be followed while the tests run.
    with log_path.open("w", buffering=1) as log:
        board = BOARDS[name](SerialTransport(port, baud_rate), log=log, name=name)
        with board.connected():
            if option("flash"):
                board.flash(option("flash"))
            else:
                board.shell_wait_for_prompt()
            yield board
