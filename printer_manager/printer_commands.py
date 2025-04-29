import serial
import time

class PrinterCommands:
    def __init__(self, port, baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.connected = False
        self.connect()

    def connect(self, raise_on_error=False):
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=5)
            print(f"Connected to {self.port} at {self.baudrate} baud.")
            self.serial.write(b'M115\n') # Send a command to check the printer's firmware version
            time.sleep(1) # allow time for the printer to respond
            response = self.serial.readline().decode(errors="ignore").strip()
            if response:
                self.connected = True
            else:
                raise serial.SerialException("No response from printer.")
        except serial.SerialException as e:
            print(f"Error connecting to printer: {e}")
            self.connected = False
            if raise_on_error:
                raise ConnectionError(f"Failed to connect to port '{self.port}': {e}")

    def disconnect(self):
        if self.serial and self.serial.is_open:
            self.serial.close()
            print(f"Disconnected from {self.port}.")
        self.connected = False

    def send_gcode_command(self, gcode, print_response = False):
        if self.serial and self.serial.is_open:
            try:
                self.serial.write((gcode + '\n').encode())
                if print_response:
                    print(f"Sent: {gcode}")
                
                response_lines = []
                for _ in range(100_000_000):
                    response = self.serial.readline().decode(errors="ignore").strip()
                    if response == "ok":
                        break
                    if response:
                        if print_response:
                            print(f"Printer response: {response}")
                        response_lines.append(response)
                    else:
                        break

                return response_lines
            
            except serial.SerialException as e:
                print(f"Serial communication error: {e}")
                self.connected = False

            except Exception as e:
                print(f"Error sending G-code: {e}")
                
            except OSError as e:
                print(f"OS error: {e}")
                self.connected = False

        else:
            print("Printer not connected or serial port not open.")
        return None
    

