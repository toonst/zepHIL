# pytest-zephil

A pytest plugin for Hardware-in-the-Loop (HIL) testing of Zephyr devices. By design, it does not depend on west, nor does it need a full Zephyr repository or build directory (as twister does).
The HIL test setup assumes a single board running Zephyr OS.

## Installation

```bash
pip install .
```

## Usage

```bash
pytest --zephyr-board=frdm_rw612
```

## Features

- **board_connection**: Fixture to interact with the device.
