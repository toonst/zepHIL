from abc import ABC, abstractmethod
import serial

class Transport(ABC):
    @abstractmethod
    def open(self):
        """Open the transport connection."""
        pass

    @abstractmethod
    def close(self):
        """Close the transport connection."""
        pass

    @property
    @abstractmethod
    def is_open(self) -> bool:
        """Check if transport is open."""
        pass

    @abstractmethod
    def read(self, size: int = 1) -> bytes:
        """Read bytes from the transport."""
        pass

    @abstractmethod
    def write(self, data: bytes) -> int:
        """Write bytes to the transport."""
        pass
    
    @property
    @abstractmethod
    def in_waiting(self) -> int:
        """Return the number of bytes waiting in the input buffer."""
        pass
    
    @abstractmethod
    def flush_input(self):
        """Flush the input buffer."""
        pass

class SerialTransport(Transport):
    def __init__(self, port: str, baudrate: int, timeout: float = 0.1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial = None

    def open(self):
        self.serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout
        )
        return self

    def close(self):
        if self.serial and self.serial.is_open:
            self.serial.close()
        self.serial = None

    @property
    def is_open(self) -> bool:
        return self.serial is not None and self.serial.is_open

    def read(self, size: int = 1) -> bytes:
        if not self.serial:
            raise RuntimeError("Serial transport not open")
        return self.serial.read(size)

    def write(self, data: bytes) -> int:
        if not self.serial:
            raise RuntimeError("Serial transport not open")
        return self.serial.write(data)
        
    @property
    def in_waiting(self) -> int:
        if not self.serial:
            return 0
        return self.serial.in_waiting
    
    def flush_input(self):
        if self.serial:
            self.serial.reset_input_buffer()
