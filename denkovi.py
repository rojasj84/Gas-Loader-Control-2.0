import serial
import time
import threading

class DenkoviUSB16:
    """
    Controller for Denkovi USB 16 Relay Board (Virtual COM Port).
    Based on User Manual 04 Aug 2017.
    
    Requires: pip install pyserial
    """
    
    def __init__(self, port: str, baudrate: int = 9600):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self._lock = threading.RLock() # Re-entrant lock for thread safety

    def connect(self):
        """Opens the serial connection."""
        with self._lock:
            if self.ser is None:
                try:
                    self.ser = serial.Serial(
                        port=self.port,
                        baudrate=self.baudrate,
                        bytesize=serial.EIGHTBITS,
                        parity=serial.PARITY_NONE,
                        stopbits=serial.STOPBITS_ONE,
                        timeout=1.0
                    )
                    time.sleep(0.1) # Wait for connection to stabilize
                except serial.SerialException as e:
                    print(f"Error connecting to Denkovi board: {e}")
                    raise

    def disconnect(self):
        """Closes the serial connection."""
        with self._lock:
            if self.ser and self.ser.is_open:
                self.ser.close()
            self.ser = None

    def _send_command(self, cmd_bytes: bytes, read_bytes: int = 0) -> bytes:
        """Internal helper to send data and enforce protocol timing."""
        with self._lock:
            if not self.ser or not self.ser.is_open:
                raise IOError("Serial port is not connected.")
            
            # Manual Section 8.7: Minimum 5ms interval between commands
            time.sleep(0.006) 
            
            self.ser.write(cmd_bytes)
            self.ser.flush()
            
            if read_bytes > 0:
                response = self.ser.read(read_bytes)
                if len(response) != read_bytes:
                    # Warning: The board might not echo if communication is noisy
                    pass 
                return response
            return b''

    def get_status(self) -> dict:
        """
        Returns a dictionary of relay states {1: True, ..., 16: False}.
        Uses Command 8.2: 'ask//'
        """
        cmd = b'ask//'
        # Response is 2 bytes (Binary mask)
        response = self._send_command(cmd, read_bytes=2)
        
        if len(response) < 2:
            raise IOError("Failed to read status from board")

        byte1 = response[0]
        byte2 = response[1]
        
        states = {}
        
        # Byte 1: Bit 7=Relay1 ... Bit 0=Relay8
        for i in range(8):
            relay_num = i + 1
            is_on = (byte1 >> (7 - i)) & 1
            states[relay_num] = bool(is_on)
            
        # Byte 2: Bit 7=Relay9 ... Bit 0=Relay16
        for i in range(8):
            relay_num = i + 9
            is_on = (byte2 >> (7 - i)) & 1
            states[relay_num] = bool(is_on)
            
        return states

    def set_relay(self, relay_id: int, state: bool):
        """
        Sets a single relay ON or OFF.
        Uses Command 8.3: XX+// or XX-//
        """
        if not (1 <= relay_id <= 16):
            raise ValueError("Relay ID must be between 1 and 16.")
            
        s_relay = f"{relay_id:02d}" # "01" to "16"
        s_sign = "+" if state else "-"
        
        cmd_str = f"{s_relay}{s_sign}//"
        # Expects echo of the 5-byte command
        self._send_command(cmd_str.encode('ascii'), read_bytes=5)

    def set_all(self, state: bool):
        """Sets all relays ON or OFF."""
        if state:
            # Command 8.4: on// (4 bytes)
            self._send_command(b"on//", read_bytes=4)
        else:
            # Command 8.5: off// (5 bytes)
            self._send_command(b"off//", read_bytes=5)

    def set_multiple(self, updates: dict):
        """
        Updates specific relays without affecting others.
        Args:
            updates: dict {relay_id: bool, ...} e.g., {1: True, 5: False}
        """
        with self._lock:
            # 1. Get current state (Preserve existing relays)
            current_states = self.get_status()
            
            # 2. Apply updates locally
            for r_id, r_state in updates.items():
                if 1 <= r_id <= 16:
                    current_states[r_id] = r_state
            
            # 3. Construct binary mask for Command 8.6
            # Byte 1 (Relays 1-8)
            byte1 = 0
            for i in range(8):
                if current_states.get(i + 1, False):
                    byte1 |= (1 << (7 - i))
            
            # Byte 2 (Relays 9-16)
            byte2 = 0
            for i in range(8):
                if current_states.get(i + 9, False):
                    byte2 |= (1 << (7 - i))
                    
            # Command: 'x' [byte1] [byte2] '/' '/'
            cmd = bytearray([ord('x'), byte1, byte2, ord('/'), ord('/')])
            self._send_command(cmd, read_bytes=5)