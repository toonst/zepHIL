import pytest
from unittest.mock import MagicMock, patch
import pylink
from zephil.jlinkboard import JLinkBoard
from zephil.frdm_rw612 import FRDMRW612

@pytest.fixture
def mock_jlink_connection():
    """
    Fixture to mock pylink.JLink for JLinkBoard tests.
    """
    with patch('pylink.JLink') as mock_jlink_class:
        mock_jlink_instance = MagicMock()
        mock_jlink_class.return_value = mock_jlink_instance
        yield mock_jlink_instance

@pytest.fixture
def jlink_board_dut(mock_jlink_connection):
    """
    Fixture for a JLinkBoard instance.
    """
    # Create an instance of FRDMRW612, which inherits from JLinkBoard
    # We need to provide dummy values for Board's __init__
    board = FRDMRW612(port="/dev/ttyUSB0", baudrate=115200, fw_image="dummy.bin", serial_number="123456789")
    yield board

def test_jlink_reset(jlink_board_dut, mock_jlink_connection):
    """
    Test that JLinkBoard's reset calls jlink.reset(halt=False).
    """
    # Ensure the dut is an instance of FRDMRW612, which uses JLinkBoard
    assert isinstance(jlink_board_dut, FRDMRW612)
    
    # Call the reset method
    jlink_board_dut.reset()
    
    # Assert that the mock JLink's reset method was called once with halt=False
    mock_jlink_connection.reset.assert_called_once_with(halt=False)

