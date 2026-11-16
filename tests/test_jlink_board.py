import pylink
import pytest

from zephil.frdm_rw612 import FRDMRW612
from zephil.transport import SerialTransport


def make_board(**kwargs):
    transport = SerialTransport(port="/dev/fake", baudrate=115200)
    return FRDMRW612(transport, timeout=2, **kwargs)


@pytest.fixture
def board(device):
    with make_board().connected() as board:
        yield board


def test_every_operation_connects_to_the_chip_and_disconnects(board, jlink):
    board.erase()

    jlink.open.assert_called_once_with(None)
    jlink.set_tif.assert_called_once_with(pylink.JLinkInterfaces.SWD)
    jlink.connect.assert_called_once_with("RW612")
    jlink.close.assert_called_once_with()


def test_the_probe_can_be_picked_by_serial_number(jlink):
    make_board(jlink_serial=801012345).erase()

    jlink.open.assert_called_once_with(801012345)


def test_the_probe_is_released_when_an_operation_fails(board, jlink):
    jlink.connect.side_effect = pylink.JLinkException("no target")

    with pytest.raises(pylink.JLinkException):
        board.erase()

    jlink.close.assert_called_once_with()


def test_reset_restarts_the_board_and_waits_for_the_shell(board, jlink, device):
    board.reset()

    jlink.reset.assert_called_once_with(halt=False)
    assert device.boots == 2
    assert board.shell_run("version") == ["Zephyr version 3.7.0"]


def test_erase(board, jlink):
    board.erase()

    jlink.erase.assert_called_once_with()


def test_flash_writes_the_firmware_and_waits_for_the_shell(board, jlink, device):
    board.flash("zephyr.hex")

    jlink.flash_file.assert_called_once_with("zephyr.hex", 0)
    jlink.erase.assert_not_called()
    assert device.boots == 2
    assert board.shell_run("version") == ["Zephyr version 3.7.0"]


def test_flash_can_erase_the_chip_first(board, jlink):
    board.flash("zephyr.hex", erase_first=True)

    names = [call[0] for call in jlink.method_calls]
    assert names.index("erase") < names.index("flash_file")


def test_flash_refuses_a_file_without_addresses(board, jlink):
    with pytest.raises(ValueError, match=".hex"):
        board.flash("zephyr.bin")

    jlink.flash_file.assert_not_called()


def test_flash_fails_when_the_new_firmware_does_not_boot(board, jlink, device):
    board.timeout = 0.2
    device.responsive = False

    with pytest.raises(TimeoutError):
        board.flash("zephyr.hex")


def test_read_memory_returns_the_bytes(board, jlink):
    jlink.memory_read8.return_value = [0xDE, 0xAD]

    assert board.read_memory(0x1000, 2) == b"\xde\xad"
    jlink.memory_read8.assert_called_once_with(0x1000, 2)
