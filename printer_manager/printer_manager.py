import os
import json
from collections import deque
import threading
import time
from serial.tools import list_ports
import re

import serial

from .printer_commands import PrinterCommands

CONFIG_FILE = "printers_config.json"
DEBUG = True # Set to True for debugging, False for production

class PrinterManager:
    """Class to manage multiple 3D printers.
    This class handles printer connections, file uploads, and monitoring of printer status.
    It provides methods to connect, disconnect, and manage print jobs for multiple printers.
    It also includes methods to save and load printer configurations from a JSON file.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.printers = {}
        self.queues = {}
        self.printing_file = {}
        self.printing_sd_filename = {}
        self.line_number = 0

        #sdupload time
        self.sd_upload_time = {}
        self.sd_upload_time_remaining = {}
        self.monitorprinter_time_remaining_prusa = {}

        #monitoring
        self.monitorprinter_status = {}
        self.monitorprinter_hotend_temp = {}
        self.monitorprinter_bed_temp = {}
        
        #progress
        self.monitorprinter_current_byte = {}
        self.monitorprinter_total_byte = {}
        self.monitorprinter_procent = {}
        self.monitorprinter_procent_prusa = {}

        #time
        self.monitorprinter_time = {}        
        self.monitorprinter_time_remaining = {}
        self.monitorprinter_time_seconds = {}

        
        #bool
        self.model_removed = {}
        self.job_status_error = {}

        #threads
        self.monitor_threads = {}
        self.print_threads = {}
        self.monitor_events = {}

        #monitor printer 
        self.last_time_remaining_update = {}
        self.last_time_connected_update = {}
        

        self.load_printer_config()
        self.start_monitoring()
        self.reconnect_printers()

    def load_printer_config(self):
        """Load printer configuration from a JSON file."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as file:
                    config = json.load(file)
                    if not isinstance(config, dict):
                        raise ValueError("Invalid configuration format.")
                    
                    for printer_name, data in config.items():
                        if isinstance(data, dict):
                            self.printers[printer_name] = PrinterCommands(data.get("port", ""), data.get("baudrate", 115200))
                            self.queues[printer_name] = deque(data.get("queue", []))
                            self.monitorprinter_status[printer_name] = data.get("monitorprinter_status", "Unknown")
                            self.monitorprinter_current_byte[printer_name] = data.get("current_byte", 0)
                            self.monitorprinter_total_byte[printer_name] = data.get("total_byte", 0)
                            self.sd_upload_time[printer_name] = data.get("sd_upload_time")
                            self.sd_upload_time_remaining[printer_name] = data.get("sd_upload_time_remaining")
                            self.monitorprinter_time_seconds[printer_name] = data.get("time_seconds", 0)
                            self.model_removed[printer_name] = data.get("model_removed", False)
                            self.printing_file[printer_name] = data.get("current_file")
                            self.printing_sd_filename[printer_name] = data.get("current_sd_file")
                            self.job_status_error[printer_name] = data.get("job_status_error")
                        else:
                            print(f"Warning: Invalid data format for {printer_name}, skipping.")
                            
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"Error reading configuration file: {e}")
            except ValueError as e:
                print(f"Error loading configuration: {e}")

    def save_printer_config(self):
        """Save printer configuration to a JSON file."""
        config = {
            printer_name: {
                "port": printer.port,
                "baudrate": printer.baudrate,
                "queue": list(self.queues.get(printer_name, [])),
                "monitorprinter_status": self.monitorprinter_status.get(printer_name, "Unknown"),
                "current_byte": self.monitorprinter_current_byte.get(printer_name, 0),
                "total_byte": self.monitorprinter_total_byte.get(printer_name, 0),
                "sd_upload_time": self.sd_upload_time.get(printer_name),
                "sd_upload_time_remaining": self.sd_upload_time_remaining.get(printer_name),
                "time_seconds": self.monitorprinter_time_seconds.get(printer_name, 0),
                "model_removed": self.model_removed.get(printer_name, False),
                "current_file": self.printing_file.get(printer_name),
                "current_sd_file": self.printing_sd_filename.get(printer_name),
                "job_status_error": self.job_status_error.get(printer_name),
            }
            for printer_name, printer in self.printers.items()
        }
        with open(CONFIG_FILE, "w") as file:
            json.dump(config, file, indent=4)
        print("Configuration saved.")
 
    def reconnect_printers(self):
        """Reconnect to all printers that are marked as disconnected."""
        for printer_name, printer in self.printers.items():
            if self.monitorprinter_status.get(printer_name) == "Disconnected":
                print(f"Reconnecting to printer {printer_name}...")
                printer.connect()
                if printer.connected:
                    print(f"Successfully reconnected to {printer_name}.")
                    self.start_monitor_threads(printer_name)
                else:
                    print(f"Failed to reconnect to {printer_name}.")

    def reconnect_printer(self, printer_name, raise_on_error=False):
        """Reconnect to a specific printer."""
        try:
            if printer_name not in self.printers:
                raise ValueError(f"No printer connected with name '{printer_name}'.")
            
            if self.monitorprinter_status.get(printer_name) != "Disconnected":
                raise ValueError(f"Printer '{printer_name}' is already connected.")
            
            if self.monitorprinter_status.get(printer_name) == "Disconnected":
                self.printers[printer_name].connect(raise_on_error=raise_on_error)
                if self.printers[printer_name].connected:
                    print(f"Successfully reconnected to {printer_name}.")
                    self.start_monitor_threads(printer_name)
                else:    
                    print(f"Failed to reconnect to {printer_name}.")
        except (ValueError, ConnectionError) as e:
            print(f"Error reconnecting printer: {e}")
            if raise_on_error:
                raise

    def start_monitoring(self):
        """Start monitoring for all connected printers on program start."""
        for printer_name in self.printers:
            self.start_monitor_threads(printer_name)

    def start_monitor_threads(self, printer_name, polling=True):
        """Start the monitoring threads for a printer."""
        try:
            # Check if a monitor thread is already running for this printer
            thread = self.monitor_threads.get(printer_name)
            if thread and thread.is_alive():
                if DEBUG: print(f"Monitor thread for {printer_name} is already running.")
                return
            
            if DEBUG: print(f"Starting monitoring threads for {printer_name}...")
            self.monitor_events[printer_name] = threading.Event()

            thread_monitoring = threading.Thread(target=self.monitor_printer, args=(printer_name, polling), daemon=True)
            self.monitor_threads[printer_name] = thread_monitoring
            thread_monitoring.start()
            
        except (threading.ThreadError, serial.SerialException, ValueError) as e:
            print(f"Error starting monitoring threads for {printer_name}: {e}")

    def stop_monitor_threads(self, printer_name):
        """Function to stop the monitoring thread for a printer."""
        if printer_name in self.monitor_events:
            self.monitor_events[printer_name].set()  # Signal threads to stop

        thread = self.monitor_threads.get(printer_name)
        if thread and thread.is_alive():
            thread.join(timeout=5)  # Wait up to 5 seconds 
            if DEBUG: print(f"[STOPPED] Monitor thread for {printer_name} stopped.")

            # Ensure that no remaining commands are being sent
            printer = self.printers.get(printer_name)
            if printer and printer.serial and printer.serial.is_open:
                try:
                    printer.serial.reset_output_buffer()  # Clear pending writes
                    printer.serial.reset_input_buffer()   # Clear pending reads
                except serial.SerialException as e:
                    print(f"Error flushing buffers: {e}")

            # Wait for printer to finish processing
            time.sleep(10)  # Wait for 10 seconds
        else:
            print(f"No active monitor thread found for '{printer_name}'.")

    def list_serial_ports(self):
        """List all available serial ports."""
        ports = list_ports.comports()
        available_ports = []
        for port in ports:
            if port.description != "n/a":
                available_ports.append((port.device, f"{port.device} - {port.description}"))
                print(f"Device: {port.device}, Description: {port.description}, Hardware ID: {port.hwid}")
        if not available_ports:
            print("No serial devices found.")

        return available_ports if available_ports else [("", "No serial devices found")] # list of tuples for form field
        
    def list_printer(self, printer_name):
        """List all connected printers and put their data in a dictionary. For website."""
        printer_data = {}
        
        if not self.printers:
            print("No printers connected.")
            return printer_data

        if printer_name not in self.printers:
            print(f"No printer connected with name '{printer_name}'.")
            return {}

        printer_data = {
        "status": self.monitorprinter_status.get(printer_name, "Unknown"),
        "sd_upload_time": self.sd_upload_time.get(printer_name, "N/A"),
        "sd_upload_time_remaining": self.sd_upload_time_remaining.get(printer_name, "N/A"),
        "print_time": self.monitorprinter_time.get(printer_name, "N/A"),
        "estimated_time_remaining": self.monitorprinter_time_remaining.get(printer_name, "N/A"),
        "current_byte": self.monitorprinter_current_byte.get(printer_name, "N/A"),
        "total_byte": self.monitorprinter_total_byte.get(printer_name, "N/A"),
        "print_progress": self.monitorprinter_procent.get(printer_name, "N/A"),
        "hotend_temp": self.monitorprinter_hotend_temp.get(printer_name, "N/A"),
        "bed_temp": self.monitorprinter_bed_temp.get(printer_name, "N/A"),
        }

        return printer_data
    
    def list_all_printers(self):
        """List all connected printers and their data. Print to console."""
        if not self.printers:
            print("No printers connected.")
            return

        for printer_name, printer in self.printers.items():
            print(
            f"Printer: {printer_name}\n"
            f"  Port: {printer.port}\n"
            f"  Baudrate: {printer.baudrate}\n"
            f"  Queue: {self.queues.get(printer_name, [])}\n"
            f"  Status: {self.monitorprinter_status.get(printer_name, 'Unknown')}\n"
            "\n"
            f"  SD upload time: {self.sd_upload_time.get(printer_name, 'N/A')}\n"
            f"  SD upload time remaining: {self.sd_upload_time_remaining.get(printer_name, 'N/A')}\n"
            "\n"
            f"  Print time: {self.monitorprinter_time.get(printer_name, 'N/A')}\n"
            f"  Time in seconds: {self.monitorprinter_time_seconds.get(printer_name, 'N/A')}\n"
            f"  Estimated time remaining: {self.monitorprinter_time_remaining.get(printer_name, 'N/A')}\n"
            "\n"
            f"  Current byte: {self.monitorprinter_current_byte.get(printer_name, 'N/A')}\n"
            f"  Total byte: {self.monitorprinter_total_byte.get(printer_name, 'N/A')}\n"
            f"  Print progress: {self.monitorprinter_procent.get(printer_name, 'N/A')}\n"
            "\n"
            f"  Hotend temp: {self.monitorprinter_hotend_temp.get(printer_name, 0)}\n"
            f"  Bed temp: {self.monitorprinter_bed_temp.get(printer_name, 0)}\n"
            f"  Model removed: {self.model_removed.get(printer_name, False)}\n"
            "\n"
            f"  Monitor threads: {self.monitor_threads.get(printer_name)}\n"
            f"  Print threads: {self.print_threads.get(printer_name)}\n"
            f"  Current file: {self.printing_file.get(printer_name)}\n"
            f"  Current SD file: {self.printing_sd_filename.get(printer_name)}"
            "\n"
            )
 
    def list_sd_files(self, printer_name):
        """List all files on the SD card of a printer. Used in upload_file()."""
        sd_files = []

        printer = self.printers[printer_name]
           
        response = printer.send_gcode_command("M20")
        if response:
            sd_files = response[1:-1]
        else:
            sd_files = []

        return sd_files

    def connect_printer(self, printer_name, port, baudrate=115200, raise_on_error=False):
        """Connect to a printer and add it to the list of connected printers."""
        try:
             # Reset line number
            if printer_name in self.printers:
                raise ValueError(f"Printer '{printer_name}' is already connected.")
            
            for existing_printer in self.printers.values():
                if existing_printer.port == port:
                    raise ValueError(f"Port '{port}' is already connected to another printer.")

            printer = PrinterCommands(port, baudrate)
            if printer.connected:
                self.printers[printer_name] = printer

                #set dictionary values
                self.model_removed[printer_name] = True
                self.job_status_error[printer_name] = False

                self.queues[printer_name] = deque()
                self.save_printer_config()
                if DEBUG: print(f"Printer '{printer_name}' connected and configuration saved.")
                self.start_monitor_threads(printer_name)
                
       
            else:
                raise ValueError(f"Failed to connect to printer '{printer_name}' on port '{port}'.")
            
        except ValueError as e:
            print(f"Error connecting printer: {e}")
            if raise_on_error:
                raise (f"Error connecting printer '{port}'.")
            
    def remove_printer(self, printer_name, raise_on_error=False):
        """Remove a printer from the list of connected printers."""
        try:
            if printer_name not in self.printers:
                raise ValueError(f"No printer connected with name '{printer_name}'.")
            
            self.printers[printer_name].disconnect()
            del self.printers[printer_name]
            del self.queues[printer_name]
            self.save_printer_config()
            print(f"Printer '{printer_name}' disconnected and removed from configuration.")

        except ValueError as e:
            print(f"Error removing printer: {e}")
            if raise_on_error:
                raise ValueError(f"Error removing printer '{printer_name}'.")

    def send_gcode(self, printer_name, gcode):
        """Send a G-code command to a printer. Debugging only."""
        try:
            if printer_name not in self.printers:
                raise ValueError(f"No printer connected with name '{printer_name}'.")
            
            self.stop_monitor_threads(printer_name)
            printer = self.printers[printer_name]
            printer.send_gcode_command(gcode, print_response=True)
            self.start_monitor_threads(printer_name)

        except ValueError as e:
            print(f"Error sending G-code command: {e}")
    
    def add_to_queue(self, printer_name, filename, raise_on_error=False):
        """Add a file to the print queue for a printer."""
        try:
            if printer_name not in self.printers:
                raise ValueError(f"No printer connected with name '{printer_name}'.")

            if not os.path.exists(filename):
                raise ValueError(f"File '{filename}' not found.")
            
            self.queues[printer_name].append(filename)
            if DEBUG: print(f"Added '{filename}' to the queue for printer '{printer_name}'.")
            self.save_printer_config()
            
        except ValueError as e:
            print(f"Error adding file to queue: {e}")
            if raise_on_error:
                raise
    
    def remove_from_queue(self, printer_name, filename, raise_on_error=False):
        """Remove a file from the print queue for a printer.
        If the file is currently being printed, it cannot be removed."""
        try:
            if printer_name not in self.queues:
                raise ValueError(f"No queue found for printer '{printer_name}'.")

            if filename not in self.queues[printer_name]:
                raise ValueError(f"File '{filename}' not found in queue for printer '{printer_name}'.")
            
            if self.printing_file.get(printer_name) == filename:
                raise ValueError(f"Cannot remove file '{filename}' while it is being printed.")
             
            # Remove last occurrence from the right
            self.queues[printer_name].reverse()
            self.queues[printer_name].remove(filename)
            self.queues[printer_name].reverse()
            if DEBUG: print(f"Removed '{filename}' from the queue for printer '{printer_name}'.")
            self.save_printer_config()

        except (KeyError, ValueError, IndexError) as e:
            print(f"Error removing file from queue: {e}")
            if raise_on_error:
                raise
        finally:
            self.start_monitor_threads(printer_name)

    def add_checksum(self, gcode, line_number):
        """Add checksum to G-code command. Used in upload_file()."""
        # Ignore empty lines and full comment lines starting with ';'
        gcode = gcode.strip()
        if not gcode or gcode.startswith(';'):
            return ""
        
        # Ignore comments after ';' in a command line
        gcode = gcode.split(';')[0].strip()
        if not gcode:
            return ""
        
        line_str = f"N{line_number} {gcode}"
        
        # Calculate checksum 
        checksum = 0
        for char in line_str:
            if char == '*':
                break
            checksum ^= ord(char)  
        checksum &= 0xff  # Keep it within an 8-bit range
        
        return f"{line_str}*{checksum}"

    def upload_file(self, printer_name, filename):
        """Upload a file to the printer's SD card.
        This function handles the file upload process, including checksum calculation and progress monitoring."""
        self.stop_monitor_threads(printer_name)

        try:
            if not os.path.exists(filename):
                print(f"File '{filename}' not found.")
                raise ValueError(f"File '{filename}' not found.")
            
            with self.lock:
                printer = self.printers[printer_name]

                number = 0
                base_name = os.path.splitext(os.path.basename(filename))[0].replace(" ", "_")[:6]
                base_name = base_name.ljust(6, '0')
                sd_filename = f"{base_name.upper()}_{number}.GCO"

                sd_files = self.list_sd_files(printer_name)
                existing_numbers = set()


                if sd_files:
                    for name in sd_files:
                        split_name = name.split(' ')[0]
                        if split_name.startswith(base_name.upper()):
                            try:
                                existing_number = int(split_name[len(base_name) + 1:-4])
                                existing_numbers.add(existing_number)
                            except ValueError:
                                pass
                
                    for number in range(10):
                        if number not in existing_numbers:
                            sd_filename = f"{base_name.upper()}_{number}.GCO"
                            break
                    
                    for name in sd_files:
                        if name.split(' ')[0] == sd_filename:
                            raise ValueError(f"Too many files with the same base name '{base_name}'.")

                #measuring estimated sd trasfer time
                file_size_bytes = os.path.getsize(filename)
                baud_rate = printer.baudrate
                efficiency_factor = 0.35  # Adjust based on testing
                estimated_time = round((file_size_bytes * 8) / baud_rate) / efficiency_factor # in seconds

                line_number = 1
                self.monitorprinter_status[printer_name] = "Uploading to SD card"
                printer.send_gcode_command(f"M110 N0 {sd_filename}", print_response = DEBUG) # Set line number
                time.sleep(2) # Wait for printer to process the command - not waiting will sometimes break uploading. Potentially not needed.
                response = printer.send_gcode_command(f"M28 {sd_filename}", print_response = DEBUG) # Start writing to SD card
                if response and any("open failed" in line for line in response): # Check for file name error
                    self.start_monitor_threads(printer_name)
                    raise ValueError(f"Error during file upload.")
                
                time.sleep(2) # Wait for printer to process the command - just to be sure.
                
                start_time = time.time()

                with open(filename, "r") as file:
                    for line in file:
                        command = self.add_checksum(line.strip(), line_number)
                        if command:
                            response = printer.send_gcode_command(command, print_response=DEBUG)
                            line_number += 1
                            
                            elapsed_time = time.time() - start_time # Calculate elapsed time in seconds
                            if elapsed_time > 60:
                                self.sd_upload_time[printer_name] = f"{int(elapsed_time // 60)}m {int(elapsed_time % 60)}s"
                            else:
                                self.sd_upload_time[printer_name] = f"{int(elapsed_time)}s"

                            remaining_time = estimated_time - elapsed_time # Calculate remaining time in seconds
                            if remaining_time > 60:
                                self.sd_upload_time_remaining[printer_name] = f"{int(remaining_time // 60)}m {int(remaining_time % 60)}s"
                            elif remaining_time > 0:
                                self.sd_upload_time_remaining[printer_name] = f"{int(remaining_time)}s"
                            else:
                                self.sd_upload_time_remaining[printer_name] = "0s"

                            self.monitorprinter_status[printer_name] = f"Uploading to SD card"
                            if response and any("Error" in line for line in response):
                                self.start_monitor_threads(printer_name)
                                raise ValueError(f"Error during file upload.")
                        
                
                printer.send_gcode_command(f"M29 {sd_filename}", print_response=True) # Finish writing to SD card
                self.sd_upload_time_remaining[printer_name] = "0s"


                # Stop timing once SD upload is completed
                end_time = time.time()
                actual_time = end_time - start_time
                self.sd_upload_time[printer_name] = f"{round(actual_time // 60)}m {round(actual_time % 60)}s"
                self.sd_upload_time_remaining[printer_name] = "0s"
                
                self.printing_sd_filename[printer_name] = sd_filename
                self.printing_file[printer_name] = filename
                self.save_printer_config()

        except ValueError as e:
            print(f"Error uploading file to printer '{printer_name}': {e}")
            self.job_status_error[printer_name] = True
        finally: 
            self.start_monitor_threads(printer_name)

    def cancel_print(self, printer_name):
        """Cancel the current print job and return the printer to a safe state.
        This function stops the print job, turns off the hotend and bed, and moves the print head to a safe position.
        Used when printing is cancelled or interrupted."""

        self.stop_monitor_threads(printer_name)

        printer = self.printers[printer_name]

        self.job_status_error[printer_name] = True
        self.save_printer_config()

        if self.monitorprinter_status.get(printer_name) == "SD printing":
            
            printer.send_gcode_command("M108", print_response=True)  # Break out of wait-for-user during heating

            printer.send_gcode_command("M524", print_response=True)  # Abort SD print (if supported)

            # Attempt Prusa-style cancel for serial prints
            printer.send_gcode_command("M603", print_response=True)

            

        # If printing from SD, stop writing to SD
        printer.send_gcode_command(f"M29", print_response=True) # Stop writing to SD

        # Stop the print job
        printer.send_gcode_command(f"M104 S0", print_response=True) # Turn off hotend
        printer.send_gcode_command(f"M140 S0", print_response=True) # Turn off bed
        printer.send_gcode_command(f"M107", print_response=True) # Turn off fan
        printer.send_gcode_command(f"G91", print_response=True) # Set relative positioning
        printer.send_gcode_command(f"G1 Z10 F300", print_response=True) # Move Z up 10mm
        printer.send_gcode_command(f"G90", print_response=True) # Set absolute positioning
        printer.send_gcode_command(f"G28 X Y", print_response=True) # Home X and Y
        printer.send_gcode_command(f"M84", print_response=True) # Disable motors
        

        self.start_monitor_threads(printer_name)

    def remove_model(self, printer_name, raise_on_error=False):
        """Remove the current model from the printer's SD card and start the next print job in the queue."""
        self.stop_monitor_threads(printer_name)
        try:
            if printer_name not in self.printers:
                raise ValueError(f"No printer connected with name '{printer_name}'.")
            
            if ((printer_name in self.print_threads and self.print_threads[printer_name].is_alive()) 
                or (self.monitorprinter_status.get(printer_name) == "SD printing")):
                raise ValueError(f"Cannot remove model during printing.")
            
            if self.model_removed.get(printer_name) and not self.job_status_error.get(printer_name):
                raise ValueError(f"No model to remove from printer '{printer_name}'.")
            
            if not self.job_status_error.get(printer_name):
                sd_filename = self.printing_sd_filename.get(printer_name)

                if not sd_filename:
                    raise ValueError(f"No SD file found for printer '{printer_name}'.")

                self.delete_file_from_sd(printer_name, sd_filename)

            self.job_status_error[printer_name] = False
            self.monitorprinter_current_byte[printer_name] = 0
            self.monitorprinter_total_byte[printer_name] = 0
            self.monitorprinter_time[printer_name] = 0
            self.monitorprinter_time_remaining[printer_name] = 0
            self.monitorprinter_procent[printer_name] = 0
            self.sd_upload_time[printer_name] = 0
            self.printing_file[printer_name] = None
            self.printing_sd_filename[printer_name] = None
            self.model_removed[printer_name] = True
            self.save_printer_config()

            if self.queues[printer_name]:
                self.print_next_in_queue(printer_name, raise_on_error)
                return # Prevent from starting monitoring threads again.

        except (ValueError, IndexError) as e:
            print(f"Error removing model from printer '{printer_name}': {e}")
            if raise_on_error:
                raise
        
        self.start_monitor_threads(printer_name)

    def delete_file_from_sd(self, printer_name, sd_filename):
        """Delete a file from the printer's SD card. Used in remove_model()."""
        self.stop_monitor_threads(printer_name)
        
        printer = self.printers[printer_name]
        
        printer.send_gcode_command(f"M30 {sd_filename}", print_response=True)        

        self.start_monitor_threads(printer_name)

    def print_file_from_sd(self, printer_name, sd_filename):
        """Start printing a file from the printer's SD card."""
        self.stop_monitor_threads(printer_name)

        self.model_removed[printer_name] = False

        self.monitorprinter_status[printer_name] = "SD printing"

        printer = self.printers[printer_name]
        
        printer.send_gcode_command(f"M32 {sd_filename}")

        self.start_monitor_threads(printer_name)

    def print_next_in_queue(self, printer_name, raise_on_error=False):
        """Start the next print job in the queue for a printer.
        Create a new thread for the print job."""
        try:
            if printer_name not in self.printers:
                raise ValueError(f"No printer connected with name '{printer_name}'.")
            
            if not self.model_removed.get(printer_name, False):
                raise ValueError(f"Please remove model from printer '{printer_name}' before printing.")
            
            self.model_removed[printer_name] = False
            
            if ((printer_name in self.print_threads and self.print_threads[printer_name].is_alive()) 
                or (self.monitorprinter_status.get(printer_name) == "SD printing")):
                raise ValueError(f"Printer '{printer_name}' is already printing.")
        
            self.model_removed[printer_name] = False
            filename = self.queues[printer_name].popleft()
            self.save_printer_config()

            thread = threading.Thread(target=self.print_job, args=(printer_name, filename), daemon=True)
            self.print_threads[printer_name] = thread
            thread.start()

        except (IndexError, ValueError) as e:
            print(f"Error: Queue for printer '{printer_name}' is empty.")
            if raise_on_error:
                raise

    
    def print_job(self, printer_name, filename):
        """Handle a print job by uploading to SD, printing from SD"""
        try:
            if DEBUG: print(f"Starting print job for '{printer_name}' with file '{filename}'")
            self.model_removed[printer_name] = False
            self.upload_file(printer_name, filename)

            sd_filename = self.printing_sd_filename.get(printer_name)

            if not sd_filename:
                raise ValueError(f"Failed to upload '{filename}' to printer '{printer_name}'.")

            self.print_file_from_sd(printer_name, sd_filename)

        except Exception as e:
            print(f"Error during print job on '{printer_name}': {e}")
            self.job_status_error[printer_name] = True
            self.cancel_print(printer_name)

    def print_gcode(self, printer_name, filename, raise_on_error=False):
        """Add a file to the print queue and start printing."""
        try:
            if printer_name not in self.printers:
                raise ValueError(f"No printer connected with name '{printer_name}'.")
            
            self.add_to_queue(printer_name, filename)
            
            self.print_next_in_queue(printer_name, raise_on_error)

        except (ValueError, IndexError) as e:
            print(f"Error adding file to queue and starting print job: {e}")
            self.job_status_error[printer_name] = True
            if raise_on_error:
                raise

    def read_serial(self, printer_name, line):
        """Process incoming data from the printer and update its status.
        This method is invoked by monitor_printer() to handle serial input."""
        regex_temp = r"(?:ok\s+)?T:([\d\.]+)\s*/[\d\.]+\s+B:([\d\.]+)\s*/[\d\.]+" # Hotend and bed temp
        match_temp = re.match(regex_temp, line)
        
        regex_temp_2 = r"T:([\d\.]+).*?B:([\d\.]+)" #prusa temp
        match_temp_2 = re.match(regex_temp_2, line)

        regex_time = r"echo:Print time:\s*(?:(\d+)h\s*)?(?:(\d+)m\s*)?(?:(\d+)s)?" # Print time
        match_time = re.match(regex_time, line)

        regex_time_2 = r"echo:\s*(?:(\d+)\s*hour[s]?,?\s*)?(?:(\d+)\s*min[s]?,?\s*)?(?:(\d+)\s*sec[s]?)" # Print time second option
        match_time_2 = re.match(regex_time_2, line)

        regex_time_remaining = r"NORMAL MODE: Percent done: (\d+); print time remaining in mins: (-?\d+)"
        match_time_remaining = re.match(regex_time_remaining, line)

        regex_status = r"SD printing byte (\d+)/(\d+)" # Print status
        match_status = re.match(regex_status, line)

        regex_status_2 = r"Not SD printing" # Print status
        match_status_2 = re.match(regex_status_2, line)

        with self.lock:
            if match_time or match_time_2:
                # Default values
                hours = 0
                minutes = 0
                seconds = 0

                if match_time:
                    if match_time.group(1):
                        hours = int(match_time.group(1))
                    if match_time.group(2):
                        minutes = int(match_time.group(2))
                    if match_time.group(3):
                        seconds = int(match_time.group(3))

                if match_time_2:
                    if match_time_2.group(1):
                        hours = int(match_time_2.group(1))
                    if match_time_2.group(2):
                        minutes = int(match_time_2.group(2))
                    if match_time_2.group(3):
                        seconds = int(match_time_2.group(3))

                if self.monitorprinter_status.get(printer_name) == "SD printing":
                    if hours > 0:
                        self.monitorprinter_time[printer_name] = f"{hours}h {minutes}m {seconds}s"
                    elif minutes > 0:
                        self.monitorprinter_time[printer_name] = f"{minutes}m {seconds}s"
                    elif seconds >= 0:
                        self.monitorprinter_time[printer_name] = f"{seconds}s"

                    self.monitorprinter_time_seconds[printer_name] = hours*60*60 + minutes*60 + seconds

            if match_time_remaining:
                if match_time_remaining.group(1):
                    self.monitorprinter_procent_prusa[printer_name] = int(match_time_remaining.group(1).strip())
                if match_time_remaining.group(2):
                    mins_remaining = int(match_time_remaining.group(2))
                    if mins_remaining > 0:
                        self.monitorprinter_time_remaining_prusa[printer_name] = mins_remaining

            if match_temp:
                self.monitorprinter_hotend_temp[printer_name] = match_temp.group(1).strip()
                self.monitorprinter_bed_temp[printer_name] = match_temp.group(2).strip()
            
            if match_temp_2:
                self.monitorprinter_hotend_temp[printer_name] = match_temp_2.group(1).strip()
                self.monitorprinter_bed_temp[printer_name] = match_temp_2.group(2).strip()
            
            if match_status:
                self.monitorprinter_current_byte[printer_name] = int(match_status.group(1))
                self.monitorprinter_total_byte[printer_name] = int(match_status.group(2))
                self.monitorprinter_status[printer_name] = "SD printing"

            if match_status_2:
                self.monitorprinter_status[printer_name] = "Not SD printing"
                self.last_time_connected_update[printer_name] = time.time()

            self.get_print_progress(printer_name)

            # Check if the printer is still connected
            last_connected = self.last_time_connected_update.get(printer_name, 0)
            if time.time() - last_connected > 10 and self.monitorprinter_status.get(printer_name) == "Not SD printing":
                printer = self.printers.get(printer_name)
                printer.connected = False

    def monitor_printer(self, printer_name, polling):
        """Periodically check the printer status and read incoming data.
        This function runs in a separate thread for each printer."""
        try:
            printer = self.printers.get(printer_name)
            if not printer:
                raise ValueError(f"Printer '{printer_name}' not found.")
            
            if printer_name not in self.printers:
                raise ValueError(f"Printer '{printer_name}' not found.")

            with serial.Serial(printer.port, printer.baudrate, timeout=5) as ser:
                while printer_name in self.printers and not self.monitor_events[printer_name].is_set():
                    
                    if not printer.connected:
                        self.monitorprinter_status[printer_name] = "Disconnected"
                        self.monitorprinter_bed_temp[printer_name] = 0
                        self.monitorprinter_hotend_temp[printer_name] = 0
                        raise ValueError(f"Printer '{printer_name}' is disconnected.")
                    
                    # Process all incoming data before attempting to send anything
                    while ser.in_waiting:
                        line = ser.readline().decode("ascii", errors="ignore").strip()
                        self.read_serial(printer_name, line)
                        time.sleep(0.5)


                    if ser.in_waiting == 0 and polling:
                        try:
                            ser.write(b"M27\n")  # Request print status
                            time.sleep(1)

                            ser.write(b"M105\n")  # Request temperatures
                            time.sleep(1)

                            ser.write(b"M31\n")  # Request print time
                            time.sleep(1)

                        except serial.SerialException as e:
                            self.monitorprinter_status[printer_name] = "Disconnected"
                    
                    time.sleep(1)

        except serial.SerialException as e:
            print(f"Serial connection error: {e}")
            self.monitorprinter_status[printer_name] = "Disconnected"
        
        except OSError as e:
            print(f"OS error for '{printer_name}': {e}")
            self.monitorprinter_status[printer_name] = "Disconnected"

        except ValueError as e:
            print(f"Error monitoring printer '{printer_name}': {e}")

    def get_print_progress(self, printer_name):
        """Calculate the print progress and estimated time remaining.
        Its not very accurate, but it gives a rough estimate."""
        current_byte = self.monitorprinter_current_byte.get(printer_name)
        total_byte = self.monitorprinter_total_byte.get(printer_name)
        elapsed_time = self.monitorprinter_time_seconds.get(printer_name)
        
        if total_byte is None or total_byte is None or total_byte == 0 or elapsed_time == 0:
            self.monitorprinter_time_remaining[printer_name] = "0s"
            self.monitorprinter_procent[printer_name] = "0%"
            return

        if current_byte >= total_byte or self.monitorprinter_status[printer_name] == "Not SD printing":
            # after print is done, sometimes the current_byte is lower than total_byte - dont know why
            self.monitorprinter_current_byte[printer_name] = total_byte
            self.monitorprinter_procent[printer_name] = "100%"
            self.monitorprinter_time_remaining[printer_name] = "Printing Completed"
            return
        
        #procent calculation
        if self.monitorprinter_procent_prusa.get(printer_name):
            percent_completed  = self.monitorprinter_procent_prusa.get(printer_name)
        else:
            percent_completed = (current_byte / total_byte) * 100 
        self.monitorprinter_procent[printer_name] = f"{int(percent_completed)}%"

        #remaining time calculation
        if self.monitorprinter_time_remaining_prusa.get(printer_name):
            time_remaining = self.monitorprinter_time_remaining_prusa.get(printer_name) * 60 # Convert to seconds
            if time_remaining:
                estimated_time_remaining = time_remaining
            else:
                if percent_completed > 5: # Calculate estimated time remaining after 5% completion to avoid misleading results
                    estimated_total_time = (elapsed_time / percent_completed) * 100
                    estimated_time_remaining = estimated_total_time - elapsed_time # Remaining time in seconds - not very accurate
                    
            if estimated_time_remaining > 3600:
                self.monitorprinter_time_remaining[printer_name] = (f"{int(estimated_time_remaining) // 3600}h "
                                                                    f"{int(estimated_time_remaining % 3600 // 60)}m ")
            elif estimated_time_remaining > 60:
                self.monitorprinter_time_remaining[printer_name] = f"{int(estimated_time_remaining) // 60}m"
            elif estimated_time_remaining > 0 and self.monitorprinter_status[printer_name] == "SD printing":
                self.monitorprinter_time_remaining[printer_name] = f"{int(estimated_time_remaining)}s"
            else:
                self.monitorprinter_time_remaining[printer_name] = "Printing Completed"
        else:
            self.monitorprinter_time_remaining[printer_name] = "Calculating..."