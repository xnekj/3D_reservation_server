import os
import sys
from cmd import Cmd

from printer_manager.printer_manager import PrinterManager

class PrinterShell(Cmd):
    intro = "Type 'help' or '?' to list commands.\n"
    prompt = "> "


    def __init__(self, manager):
        super().__init__()
        self.manager = manager

    def emptyline(self):
        """Prevents repeating the last command when Enter is pressed."""
        pass  # Does nothing instead of repeating the last command

    def do_list_serial(self, arg):
        "List all serial ports."
        self.manager.list_serial_ports()

    def do_connect(self, arg):
        "Connect to a printer: connect <printer_name> <port> [baudrate]"
        args = arg.split()
        if len(args) < 2:
            print("Usage: connect <printer_name> <port> [baudrate]")
            return
        name, port = args[:2]
        baudrate = int(args[2]) if len(args) > 2 else 115200
        self.manager.connect_printer(name, port, baudrate)
    
    def do_remove(self, arg):
        "Disconnect a printer: remove <printer_name>"
        args = arg.split()
        if len(args) < 1:
            print("Usage: remove_printer <printer_name>")
            return
        self.manager.remove_printer(args[0])

    def do_remove_model(self, arg):
        "Confirmation that you removed your printed model: remove_model <printer_name>"
        args = arg.split()
        if len(args) < 1:
            print("Usage: remove_model <printer_name>")
            return
        self.manager.remove_model(args[0])

    def do_list_printers(self, arg):
        "List all connected printers."
        self.manager.list_all_printers()

    def do_list_printer(self, arg):
        "List printer details: list_printer <printer_name>"
        args = arg.split()
        if len(args) < 1:
            print("Usage: list_printer <printer_name>")
            return
        self.manager.list_printer(args[0])

    def do_print(self,arg):
        "Print G-code file: print <printer_name> <filename>"
        args = arg.split()
        if len(args) < 2:
            print("Usage: print <printer_name> <filename>")
            return
        self.manager.print_gcode(args[0], args[1])

    def do_reconnect(self,arg):
        "Tries to recconect disconnected printers"
        args = arg.split()
        if len(arg) < 2:
            print("Usage: reconnect <printer_name>")
            return
        self.manager.reconnect_printer(args[0])

    def do_add_to_queue(self, arg):
        "Add file to queue: add_to_queue <printer_name> <filename>"
        args = arg.split()
        if len(args) < 2:
            print("Usage: add_to_queue <printer_name> <filename>")
            return
        self.manager.add_to_queue(args[0], args[1])
        
    def do_remove_from_queue(self, arg):
        "Remove file from queue: remove_from_queue <printer_name> <filename>"
        args = arg.split()
        if len(args) < 2:
            print("Usage: remove_from_queue <printer_name> <filename>")
            return
        self.manager.remove_from_queue(args[0], args[1])
    
    def do_exit(self, arg):
        "Exit the program."
        self.manager.save_printer_config()
        print("Exiting.")
        return True
    
    def do_EOF(self, arg):
        "Exit the program."
        print("")
        self.manager.save_printer_config()
        print("Exiting.")
        return True

    #debugging
    def do_send(self, arg):
        "Send G-code to a printer: send <printer_name> <gcode>"
        args = arg.split(maxsplit=1)
        if len(args) < 2:
            print("Usage: send <printer_name> <gcode>")
            return
        printer_name, gcode = args
        self.manager.send_gcode(printer_name, gcode)

    def do_upload(self, arg):
        "Upload a file to a printer: upload <printer_name> <filename>"
        args = arg.split()
        if len(args) < 2:
            print("Usage: upload <printer_name> <filename>")
            return
        self.manager.upload_file(args[0], args[1])
    
    
    def do_print_from_SD(self, arg):
        "Print file from SD card: print_from_SD <printer_name> <filename>"
        args = arg.split()
        if len(args) < 2:
            print("Usage: print_from_SD <printer_name> <filename>")
            return
        self.manager.print_file_from_sd(args[0], args[1])
    
if __name__ == "__main__":
    if os.geteuid() != 0:
        print("This script requires sudo privileges. Restarting with sudo...")
        os.execvp("sudo", ["sudo", sys.executable] + sys.argv)
    manager = PrinterManager()
    try:
        PrinterShell(manager).cmdloop()
    except (KeyboardInterrupt, EOFError):
        print("")
        manager.save_printer_config()
        print("Exiting.")
        sys.exit(0)
