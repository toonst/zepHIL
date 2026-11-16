import pytest

HIL_TEST = """
def test_version(dut):
    assert "Zephyr version 3.7.0" in dut.shell_exec_command("version")
"""


def test_dut_runs_shell_commands_on_the_board(pytester, device):
    pytester.makepyfile(HIL_TEST)

    result = pytester.runpytest("--board=frdm_rw612", "--port=/dev/fake")

    result.assert_outcomes(passed=1)
    assert "Zephyr version 3.7.0" in (pytester.path / "zephil.log").read_text()


def test_one_log_file_covers_every_test_module(pytester, device):
    pytester.makepyfile(test_one=HIL_TEST, test_two=HIL_TEST)

    result = pytester.runpytest(
        "--board=frdm_rw612", "--port=/dev/fake", "--logfile=logs/serial.log"
    )

    result.assert_outcomes(passed=2)
    log = (pytester.path / "logs" / "serial.log").read_text()
    assert log.count("Zephyr version 3.7.0") == 2


def test_fw_image_is_flashed(pytester, device, jlink):
    pytester.makepyfile(HIL_TEST)

    result = pytester.runpytest(
        "--board=frdm_rw612", "--port=/dev/fake", "--fw-image=zephyr.hex"
    )

    result.assert_outcomes(passed=1)
    jlink.flash_file.assert_called_once_with("zephyr.hex", 0)


def test_hil_tests_are_skipped_without_a_board(pytester):
    pytester.makepyfile(HIL_TEST)

    result = pytester.runpytest()

    result.assert_outcomes(skipped=1)
    assert not (pytester.path / "zephil.log").exists()


def test_an_unknown_board_is_an_error(pytester):
    result = pytester.runpytest("--board=nope", "--port=/dev/fake")

    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*--board*invalid choice*"])


def test_a_board_without_a_port_is_an_error(pytester):
    result = pytester.runpytest("--board=frdm_rw612")

    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*--board also needs --port*"])
