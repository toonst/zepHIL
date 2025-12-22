import pytest
import os
from pytest_zephil.board import Board
from pytest_zephil.shell import Shell

def pytest_addoption(parser):
    """Register command line options."""
    group = parser.getgroup("zephil", "Zephyr HIL Integration")
    group.addoption(
        "--board",
        action="store",
        dest="board",
        default=None,
        help="Target board for HIL testing (e.g. frdm_rw612)"
    )
    group.addoption(
        "--port",
        action="store",
        dest="port",
        help="The port to which the device is attached (eg: /dev/ttyACM0)"
    )
    group.addoption(
        "--baud",
        action="store",
        dest="baud",
        type=int,
        default=115200,
        help="Serial port baud rate (default: 115200)"
    )
    group.addoption(
        "--fw-image",
        action="store",
        dest="fw_image",
        help="Firmware binary to program to device"
    )
    group.addoption(
        "--serial-number",
        action="store",
        dest="serial_number",
        help="Serial number to identify on-board debugger"
    )
    group.addoption(
        "--bmp-port",
        action="store",
        dest="bmp_port",
        help="Serial port of a BlackMagicProbe programmer"
    )

@pytest.fixture(scope="session")
def board_name(request):
    return request.config.getoption("board")

@pytest.fixture(scope="session")
def port(request):
    return request.config.getoption("port")

@pytest.fixture(scope="session")
def baud(request):
    return request.config.getoption("baud")

@pytest.fixture(scope="session")
def fw_image(request):
    return request.config.getoption("fw_image")

@pytest.fixture(scope="session")
def serial_number(request):
    return request.config.getoption("serial_number")

@pytest.fixture(scope="session")
def bmp_port(request):
    if request.config.getoption("bmp_port") is not None:
        return request.config.getoption("bmp_port")
    else:
        return os.environ.get('CI_BLACKMAGICPROBE_PORT')

@pytest.fixture(scope="module")
def dut(request, port, baud, fw_image, serial_number, bmp_port):
    board_name = request.getfixturevalue("board_name")

    # Here we should ideally check board_name to determine if it's a supported board
    # For now, we will just instantiate our generic Board.
    # In a real scenario, you'd likely have a factory function or a dict mapping names to Board subclasses.
    if not board_name:
        pytest.skip("No --board specified for HIL test.")
    if not port:
        pytest.skip("No --port specified for HIL test.")

    print(f"\n[Zephil] Setting up DUT: {board_name} on {port}@{baud}")

    dut = Board(port=port, baudrate=baud, fw_image=fw_image,
                           serial_number=serial_number, bmp_port=bmp_port)

    with dut.started():
        yield dut

@pytest.fixture(scope="module")
def shell(dut):
    """Fixture that provides a Shell instance attached to the DUT."""
    return Shell(dut)