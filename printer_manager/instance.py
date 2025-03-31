from .printer_manager import PrinterManager

printer_manager = PrinterManager()

#added because of desync issue due to separate printer_manager instances across different modules.