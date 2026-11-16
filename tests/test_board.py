import io
import re

import pytest

from zephil.board import Board
from zephil.transport import SerialTransport


def make_board(**kwargs):
    return Board(SerialTransport(port="/dev/fake", baudrate=115200), **kwargs)


@pytest.fixture
def board(device):
    with make_board(timeout=2).connected() as board:
        yield board


def test_shell_run_returns_what_the_command_printed(board):
    assert board.shell_run("version") == ["Zephyr version 3.7.0"]


def test_shell_run_can_be_repeated(board):
    assert board.shell_run("version") == board.shell_run("version")


def test_shell_run_leaves_out_log_messages(board, device):
    device.commands["status"] = [
        "[00:00:01.000,000] <inf> app: started",
        "ready",
    ]

    assert board.shell_run("status") == ["ready"]


def test_shell_run_times_out_when_no_prompt_comes_back(board, device):
    device.commands["hang"] = None

    with pytest.raises(TimeoutError):
        board.shell_run("hang", timeout=0.2)


def test_shell_set_setting_runs_the_settings_command(board, device):
    board.shell_set_setting("wifi/ssid", "home")

    assert device.ran == ["settings set wifi/ssid home"]


def test_shell_wait_for_prompt_finds_a_running_shell(board):
    board.shell_wait_for_prompt()


def test_shell_wait_for_prompt_gives_up_on_a_silent_board(board, device):
    device.responsive = False

    with pytest.raises(TimeoutError, match="shell"):
        board.shell_wait_for_prompt(timeout=0.2)


def test_wait_for_line_stops_at_the_first_match(board, device):
    board.discard_output()
    device.emit(b"one\r\ntwo\r\nthree\r\n")

    assert board.wait_for_line("tw") == ["uart:~$ one", "two"]
    assert board.wait_for_line("three") == ["three"]


def test_wait_for_line_ignores_an_unfinished_line(board, device):
    board.discard_output()
    device.emit(b"no line ending yet")

    with pytest.raises(TimeoutError, match="line ending"):
        board.wait_for_line("line ending", timeout=0.2)


def test_shell_reboot_restarts_the_board_and_waits_for_the_shell(board, device):
    board.shell_reboot()

    assert device.boots == 2
    assert board.shell_run("version") == ["Zephyr version 3.7.0"]


def test_shell_reboot_times_out_when_the_board_does_not_come_back(board, device):
    board.timeout = 0.2
    device.responsive = False

    with pytest.raises(TimeoutError):
        board.shell_reboot()


def test_output_is_logged_with_a_timestamp(device):
    log = io.StringIO()

    with make_board(log=log).connected() as board:
        board.shell_run("version")

    timestamp = r"\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3}\]"
    logged = log.getvalue().splitlines()
    assert re.fullmatch(rf"{timestamp} \*\*\* Booting Zephyr OS .*", logged[0])
    assert any(
        re.fullmatch(f"{timestamp} Zephyr version 3.7.0", line) for line in logged
    )


def test_a_broken_connection_is_reported(board, device):
    device.read_error = OSError("device disconnected")

    with pytest.raises(ConnectionError) as error:
        board.wait_for_line("anything")

    assert error.value.__cause__ is device.read_error


def test_the_port_is_closed_afterwards(device):
    with make_board().connected() as board:
        assert device.is_open

    assert not device.is_open
    with pytest.raises(RuntimeError, match="not connected"):
        board.write(b"\n")


def test_a_plain_board_cannot_flash(board):
    with pytest.raises(NotImplementedError):
        board.flash("zephyr.hex")
