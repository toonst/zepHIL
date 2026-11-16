import io
import re

import pytest

from zephil.board import Board
from zephil.transport import SerialTransport


def make_board(**kwargs):
    return Board(SerialTransport(port="/dev/fake", baudrate=115200), **kwargs)


@pytest.fixture
def board(device):
    with make_board().started() as board:
        yield board


def test_exec_command_returns_the_lines_up_to_the_prompt(board):
    lines = board.shell_exec_command("version")

    assert lines == ["uart:~$ version", "Zephyr version 3.7.0", "uart:~$ "]


def test_exec_command_can_be_repeated(board):
    first = board.shell_exec_command("version")
    second = board.shell_exec_command("version")

    assert first == second


def test_exec_command_times_out_when_no_prompt_comes_back(board, device):
    device.commands["hang"] = None

    with pytest.raises(TimeoutError):
        board.shell_exec_command("hang", timeout=0.2)


def test_filtered_output_keeps_only_the_command_output(board, device):
    device.commands["status"] = [
        "[00:00:01.000,000] <inf> app: started",
        "ready",
    ]

    lines = board.shell_exec_command("status")

    assert board.shell_get_filtered_output(lines) == ["ready"]


def test_set_setting_runs_the_settings_command(board, device):
    board.shell_set_setting("wifi/ssid", "home")

    assert device.ran == ["settings set wifi/ssid home"]


def test_wait_for_prompt_finds_a_running_shell(board):
    assert board.shell_wait_for_prompt(timeout=2) is True


def test_wait_for_prompt_gives_up_on_a_silent_board(board, device):
    device.responsive = False

    assert board.shell_wait_for_prompt(timeout=0.2) is False


def test_readlines_until_stops_at_the_first_match(board, device):
    board.clear_buffer()
    device.emit(b"one\r\ntwo\r\nthree\r\n")

    assert board.readlines_until("tw", timeout_s=2) == ["uart:~$ one", "two"]
    assert board.readlines_until("three", timeout_s=2) == ["three"]


def test_readlines_until_ignores_an_unfinished_line(board, device):
    board.clear_buffer()
    device.emit(b"no line ending yet")

    with pytest.raises(TimeoutError, match="line ending"):
        board.readlines_until("line ending", timeout_s=0.2)


def test_shell_reset_reboots_and_waits_for_the_shell(board, device):
    board.shell_reset()

    assert device.boots == 2
    assert "Zephyr version 3.7.0" in board.shell_exec_command("version")


def test_shell_reset_times_out_when_the_board_does_not_reboot(board, device):
    board.shell_timeout = 0.2
    device.responsive = False

    with pytest.raises(TimeoutError):
        board.shell_reset()


def test_output_is_logged_with_a_timestamp(device):
    log = io.StringIO()

    with make_board(log=log).started() as board:
        board.shell_exec_command("version")

    timestamp = r"\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3}\]"
    logged = log.getvalue().splitlines()
    assert re.fullmatch(rf"{timestamp} \*\*\* Booting Zephyr OS .*", logged[0])
    assert any(
        re.fullmatch(f"{timestamp} Zephyr version 3.7.0", line) for line in logged
    )


def test_a_broken_connection_is_reported(board, device):
    device.read_error = OSError("device disconnected")

    with pytest.raises(ConnectionError) as error:
        board.readlines_until("anything", timeout_s=2)

    assert error.value.__cause__ is device.read_error


def test_the_port_is_closed_afterwards(device):
    with make_board().started() as board:
        assert device.is_open

    assert not device.is_open
    with pytest.raises(RuntimeError, match="not started"):
        board.send_all(b"\n")


def test_firmware_is_flashed_before_connecting(device):
    events = []

    class FlashableBoard(Board):
        def program(self, fw_image):
            events.append(("program", fw_image, device.is_open))

    transport = SerialTransport(port="/dev/fake", baudrate=115200)
    with FlashableBoard(transport, fw_image="zephyr.hex").started():
        pass

    assert events == [("program", "zephyr.hex", False)]


def test_a_plain_board_cannot_flash(device):
    board = make_board(fw_image="zephyr.hex")

    with pytest.raises(NotImplementedError), board.started():
        pass
