import pytest
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

@pytest.fixture(scope="module")
def dut(request, port, baud, fw_image):
    board_name = request.getfixturevalue("board_name")

    if not board_name:
        pytest.skip("No --board specified for HIL test.")
    if not port:
        pytest.skip("No --port specified for HIL test.")

    print(f"\n[Zephil] Setting up DUT: {board_name} on {port}@{baud}")

    if board_name == "frdm_rw612":
        from pytest_zephil.frdm_rw612 import FRDMRW612
        dut = FRDMRW612(port=port, baudrate=baud, fw_image=fw_image)
    else:
        pytest.skip("Board not supported")

    with dut.started():
        yield dut

@pytest.fixture(scope="module")
def shell(dut):
    """Fixture that provides a Shell instance attached to the DUT."""
    return Shell(dut)