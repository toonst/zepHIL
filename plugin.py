import pytest
from zephil.transport import SerialTransport

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
        "--logfile",
        action="store",
        dest="logfile",
        default="zephil.log",
        help="Path to the serial log file"
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
def logfile(request):
    return request.config.getoption("logfile")

@pytest.fixture(scope="module")

def dut(request, port, baud, fw_image, logfile):

    board_name = request.getfixturevalue("board_name")



    if not board_name:

        pytest.skip("No --board specified for HIL test.")

    if not port:

        pytest.skip("No --port specified for HIL test.")



    print(f"\n[Zephil] Setting up DUT: {board_name} on {port}@{baud}")

    

    transport = SerialTransport(port=port, baudrate=baud)



    if board_name == "frdm_rw612":

        from zephil.frdm_rw612 import FRDMRW612

        dut = FRDMRW612(transport=transport, fw_image=fw_image, logfile=logfile, name=board_name)

    else:

        pytest.skip("Board not supported")



    with dut.started():

        yield dut
