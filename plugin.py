from pathlib import Path

import pytest

from zephil.frdm_rw612 import FRDMRW612
from zephil.transport import SerialTransport

# To support a new board, add its class here.
BOARDS = {
    "frdm_rw612": FRDMRW612,
}


def pytest_addoption(parser):
    group = parser.getgroup("zephil", "Zephyr HIL Integration")
    group.addoption(
        "--board",
        choices=sorted(BOARDS),
        help="Target board for HIL testing",
    )
    group.addoption(
        "--port",
        help="The port to which the device is attached (eg: /dev/ttyACM0)",
    )
    group.addoption(
        "--baud",
        type=int,
        default=115200,
        help="Serial port baud rate (default: 115200)",
    )
    group.addoption(
        "--fw-image",
        help="Firmware image to program to device",
    )
    group.addoption(
        "--logfile",
        default="zephil.log",
        help="Path to the serial log file (default: zephil.log)",
    )


def pytest_configure(config):
    if config.getoption("board") and not config.getoption("port"):
        raise pytest.UsageError("--board also needs --port")


@pytest.fixture(scope="session")
def _zephil_serial_log(request):
    """One file that collects the serial output of the whole test run."""
    logfile = request.config.getoption("logfile")
    if not logfile:
        yield None
        return

    path = Path(logfile)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Line buffered, so the file can be followed while the tests run.
    with path.open("w", buffering=1) as log:
        yield log


@pytest.fixture(scope="module")
def dut(request):
    """The board under test: flashed if --fw-image was given, and connected."""
    option = request.config.getoption
    name = option("board")
    if not name:
        pytest.skip("No --board specified for HIL test.")

    print(f"\n[Zephil] Setting up DUT: {name} on {option('port')}@{option('baud')}")
    board = BOARDS[name](
        transport=SerialTransport(port=option("port"), baudrate=option("baud")),
        fw_image=option("fw_image"),
        # Requested here, not as an argument, so a skipped run leaves no file.
        log=request.getfixturevalue("_zephil_serial_log"),
        name=name,
    )
    with board.started():
        yield board
