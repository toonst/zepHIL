import pytest

HIL_TEST = """
def test_version(dut):
    assert dut.shell_run("version") == ["Zephyr version 3.7.0"]
"""
OPTIONS = ["--board=frdm_rw612", "--serial-port=/dev/fake"]


def test_dut_runs_shell_commands_on_the_board(pytester, device):
    pytester.makepyfile(HIL_TEST)

    result = pytester.runpytest(*OPTIONS)

    result.assert_outcomes(passed=1)
    assert "Zephyr version 3.7.0" in (pytester.path / "zephil.log").read_text()


def test_the_board_is_connected_once_for_the_whole_run(pytester, device):
    pytester.makepyfile(test_one=HIL_TEST, test_two=HIL_TEST)

    result = pytester.runpytest(*OPTIONS, "--serial-log=logs/serial.log")

    result.assert_outcomes(passed=2)
    assert device.opens == 1
    log = (pytester.path / "logs" / "serial.log").read_text()
    assert log.count("Zephyr version 3.7.0") == 2


def test_nothing_is_flashed_by_default(pytester, device, jlink):
    pytester.makepyfile(HIL_TEST)

    result = pytester.runpytest(*OPTIONS)

    result.assert_outcomes(passed=1)
    jlink.flash_file.assert_not_called()


def test_flash_option_flashes_once_for_the_whole_run(pytester, device, jlink):
    pytester.makepyfile(test_one=HIL_TEST, test_two=HIL_TEST)

    result = pytester.runpytest(*OPTIONS, "--flash=zephyr.hex")

    result.assert_outcomes(passed=2)
    jlink.flash_file.assert_called_once_with("zephyr.hex", 0)


def test_a_test_can_flash_other_firmware(pytester, device, jlink):
    pytester.makepyfile(
        """
        def test_update(dut):
            dut.flash("update.hex")
            assert dut.shell_run("version")
        """
    )

    result = pytester.runpytest(*OPTIONS)

    result.assert_outcomes(passed=1)
    jlink.flash_file.assert_called_once_with("update.hex", 0)


def test_hil_tests_are_skipped_without_a_board(pytester):
    pytester.makepyfile(HIL_TEST)

    result = pytester.runpytest()

    result.assert_outcomes(skipped=1)
    assert not (pytester.path / "zephil.log").exists()


def test_an_unknown_board_is_an_error(pytester):
    result = pytester.runpytest("--board=nope", "--serial-port=/dev/fake")

    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*--board*invalid choice*"])


def test_a_board_without_a_serial_port_is_an_error(pytester):
    result = pytester.runpytest("--board=frdm_rw612")

    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*--board also needs --serial-port*"])
