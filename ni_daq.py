try:
    import nidaqmx
    from nidaqmx.constants import LineGrouping
except ImportError:
    print("The 'nidaqmx' library is not installed or NI-DAQmx driver is missing.")
    print("Please install it using: pip install nidaqmx")
    nidaqmx = None

class NI_USB_6001:
    """
    A wrapper class for the National Instruments USB-6001 DAQ device
    using the nidaqmx library.

    This class simplifies reading analog inputs and reading/writing digital I/O.

    Prerequisites:
    1. NI-DAQmx driver must be installed from National Instruments.
    2. The 'nidaqmx' Python package must be installed (`pip install nidaqmx`).
    """

    def __init__(self, device_name: str = "Dev1"):
        """
        Initializes the DAQ controller.

        Args:
            device_name (str): The name of the DAQ device as configured in
                               NI MAX (e.g., "Dev1").
        """
        if nidaqmx is None:
            raise ImportError("nidaqmx library is required but not found.")
        
        self.device_name = device_name
        self._verify_device()

    def _verify_device(self):
        """Checks if the specified device exists in the system."""
        try:
            system = nidaqmx.system.System.local()
            if self.device_name not in system.devices:
                available = list(d.name for d in system.devices)
                raise NameError(f"Device '{self.device_name}' not found. "
                                f"Available devices: {available}")
        except nidaqmx.errors.DaqError as e:
            raise ConnectionError(f"Could not connect to NI-DAQmx system. Is the driver installed and running? Error: {e}")

    def read_analog_voltage(self, channel: int, min_val: float = -10.0, max_val: float = 10.0) -> float:
        """
        Reads a single voltage sample from a specified analog input channel.

        Args:
            channel (int): The analog input channel number (0-7).
            min_val (float): The minimum expected voltage (per NI-6001 spec).
            max_val (float): The maximum expected voltage (per NI-6001 spec).

        Returns:
            float: The measured voltage.
        """
        if not (0 <= channel <= 7):
            raise ValueError("Analog channel must be between 0 and 7.")
            
        channel_string = f"{self.device_name}/ai{channel}"
        
        with nidaqmx.Task() as task:
            task.ai_channels.add_ai_voltage_chan(
                channel_string,
                min_val=min_val,
                max_val=max_val
            )
            voltage = task.read()
            return voltage

    def read_digital_line(self, port: int, line: int) -> bool:
        """
        Reads the state of a single digital line.

        Args:
            port (int): The port number (0, 1, or 2).
            line (int): The line number within the port.

        Returns:
            bool: True if the line is high, False if low.
        """
        line_string = f"{self.device_name}/port{port}/line{line}"
        
        with nidaqmx.Task() as task:
            task.di_channels.add_di_chan(line_string, line_grouping=LineGrouping.CHAN_PER_LINE)
            state = task.read()
            return state

    def write_digital_line(self, port: int, line: int, state: bool):
        """
        Writes a state to a single digital line.

        Args:
            port (int): The port number (0, 1, or 2).
            line (int): The line number within the port.
            state (bool): The state to write (True for high, False for low).
        """
        line_string = f"{self.device_name}/port{port}/line{line}"
        
        with nidaqmx.Task() as task:
            task.do_channels.add_do_chan(line_string, line_grouping=LineGrouping.CHAN_PER_LINE)
            task.write(state)

    def read_digital_port(self, port: int) -> int:
        """
        Reads the state of an entire digital port as a bitmask.

        Args:
            port (int): The port number (0, 1, or 2).

        Returns:
            int: An integer representing the state of the port lines (e.g., for port0,
                 line 0 is the LSB, line 7 is the MSB).
        """
        port_string = f"{self.device_name}/port{port}"
        
        with nidaqmx.Task() as task:
            task.di_channels.add_di_chan(port_string, line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
            value = task.read()
            return value

    def write_digital_port(self, port: int, value: int):
        """
        Writes a bitmask value to an entire digital port.

        Args:
            port (int): The port number (0, 1, or 2).
            value (int): The integer bitmask to write to the port.
        """
        port_string = f"{self.device_name}/port{port}"
        
        with nidaqmx.Task() as task:
            task.do_channels.add_do_chan(port_string, line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
            task.write(value)