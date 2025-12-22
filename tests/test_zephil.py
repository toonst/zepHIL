import pytest
from pytest_zephil.board import Board
from pytest_zephil.shell import Shell, ShellMCUbootArea, ShellMCUbootCommandParsed
from unittest.mock import MagicMock

def test_zephil_fixture(pytester, mocker):
    """Make sure the plugin is installed and fixture works."""
    
    # Mock serial.Serial before running pytest
    mock_serial_instance = MagicMock()
    mock_serial_instance.read.return_value = b""
    mock_serial_instance.in_waiting = 0
    mock_serial_instance.__enter__.return_value = mock_serial_instance
    mock_serial_instance.__exit__.return_value = None

    mocker.patch('serial.Serial', return_value=mock_serial_instance)
    mocker.patch('time.sleep', return_value=None)

    # Create a temporary conftest file using the plugin
    pytester.makepyfile(r"""
import pytest
import re # Added import
from pytest_zephil.board import Board
from pytest_zephil.shell import Shell, ShellMCUbootArea, ShellMCUbootCommandParsed
import time
from unittest.mock import MagicMock

# Mock time.sleep
def mock_sleep(seconds):
    pass
time.sleep = mock_sleep

def test_dut_fixture_type(dut):
    assert isinstance(dut, Board)
    assert dut.serial is not None

def test_shell_fixture_type(shell):
    assert isinstance(shell, Shell)
    assert isinstance(shell.dut, Board)

def test_shell_interaction(shell):
    # Mock the dut's readlines_until to simulate response
    shell.dut.readlines_until = MagicMock(side_effect=[
        # First call for command echo
        ["version"],
        # Second call for prompt after command execution
        ["Zephyr version 3.7.0", "uart:~$"]
    ])
    shell.dut.clear_buffer = MagicMock()
    shell.dut.send_all = MagicMock()
    
    lines = shell.exec_command("version")
    
    assert shell.dut.clear_buffer.called
    assert shell.dut.send_all.called
    assert shell.dut.readlines_until.call_count == 2
    
    assert "Zephyr version 3.7.0" in lines
    assert "uart:~$" in lines # Prompt should be in raw output

def test_shell_get_filtered_output(shell):
    assert shell.prompt == "uart:~$" # Assert the exact prompt value
    output = [
        "uart:~$",
        "Zephyr version 3.7.0",
        "uart:~$" + " <dbg> debug message",
        "Some other line",
        "uart:~$" + " command_echo",
        "      <inf> info message"
    ]
    filtered = shell.get_filtered_output(output)
    expected = [
        "Zephyr version 3.7.0",
        "Some other line"
    ]
    assert filtered == expected

def test_mcuboot_command_parsed():
    cmd_output = [
        "primary area 0:",
        "    version: 1.0.0",
        "    image size: 12345",
        "    magic: good",
        "secondary area 0:",
        "    version: 0.0.0",
        "    image size: 0",
        "    magic: bad",
        "    swap type: none",
        "    copy done: unset",
        "    image ok: unset",
    ]
    parsed = ShellMCUbootCommandParsed.create_from_cmd_output(cmd_output)
    
    assert len(parsed.areas) == 2
    
    assert parsed.areas[0].name == "primary area 0"
    assert parsed.areas[0].version == "1.0.0"
    assert parsed.areas[0].image_size == "12345"
    assert parsed.areas[0].magic == "good"
    assert parsed.areas[0].swap_type == "none" # Default value

    assert parsed.areas[1].name == "secondary area 0"
    assert parsed.areas[1].version == "0.0.0"
    assert parsed.areas[1].image_size == "0"
    assert parsed.areas[1].magic == "bad"
    assert parsed.areas[1].swap_type == "none"
    assert parsed.areas[1].copy_done == "unset"
    assert parsed.areas[1].image_ok == "unset"

""")

    # Run pytest with the plugin's argument and necessary board options
    result = pytester.runpytest("--board=frdm_rw612", "--port=/dev/ttyUSB0", "--baud=115200")

    # Check results
    result.assert_outcomes(passed=5)