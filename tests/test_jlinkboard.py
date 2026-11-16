import pylink
import pytest

from zephil.frdm_rw612 import FRDMRW612


@pytest.fixture
def board():
    return FRDMRW612(transport=None)


def test_every_operation_connects_to_the_chip_and_disconnects(board, jlink):
    board.reset()

    jlink.open.assert_called_once_with(None)
    jlink.set_tif.assert_called_once_with(pylink.JLinkInterfaces.SWD)
    jlink.connect.assert_called_once_with("RW612")
    jlink.close.assert_called_once_with()


def test_the_probe_can_be_picked_by_serial_number(jlink):
    FRDMRW612(transport=None, serial_number=801012345).reset()

    jlink.open.assert_called_once_with(801012345)


def test_the_probe_is_released_when_an_operation_fails(board, jlink):
    jlink.connect.side_effect = pylink.JLinkException("no target")

    with pytest.raises(pylink.JLinkException):
        board.reset()

    jlink.close.assert_called_once_with()


def test_reset_lets_the_chip_run(board, jlink):
    board.reset()

    jlink.reset.assert_called_once_with(halt=False)


def test_erase(board, jlink):
    board.erase()

    jlink.erase.assert_called_once_with()


def test_program_flashes_the_image_and_restarts_the_chip(board, jlink):
    board.program("zephyr.hex")

    jlink.flash_file.assert_called_once_with("zephyr.hex", 0)
    jlink.erase.assert_not_called()
    assert jlink.reset.call_args_list[-1].kwargs == {"halt": False}


def test_program_can_erase_the_chip_first(board, jlink):
    board.program("zephyr.hex", full_erase=True)

    names = [call[0] for call in jlink.method_calls]
    assert names.index("erase") < names.index("flash_file")


def test_dump_memory_returns_the_bytes(board, jlink):
    jlink.memory_read8.return_value = [0xDE, 0xAD]

    assert board.dump_memory(0x1000, 2) == bytearray(b"\xde\xad")
    jlink.memory_read8.assert_called_once_with(0x1000, 2)
