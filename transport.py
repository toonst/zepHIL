from abc import ABC, abstractmethod

import serial


class Transport(ABC):
    """A byte stream to and from the device."""

    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @property
    @abstractmethod
    def is_open(self) -> bool: ...

    @abstractmethod
    def read(self) -> bytes:
        """Return the bytes received so far.

        Waits a short moment when there are none, then returns b"".
        """

    @abstractmethod
    def write(self, data: bytes) -> None: ...


class SerialTransport(Transport):
    def __init__(self, port: str, baudrate: int, timeout: float = 0.1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial: serial.Serial | None = None

    def open(self) -> None:
        self.serial = serial.Serial(
            port=self.port, baudrate=self.baudrate, timeout=self.timeout
        )

    def close(self) -> None:
        if self.serial:
            self.serial.close()
            self.serial = None

    @property
    def is_open(self) -> bool:
        return self.serial is not None and self.serial.is_open

    def read(self) -> bytes:
        return self.serial.read(self.serial.in_waiting or 1)

    def write(self, data: bytes) -> None:
        self.serial.write(data)
