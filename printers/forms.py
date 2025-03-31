from django import forms
from .models import Printer
from printer_manager.instance import printer_manager

class PrinterForm(forms.ModelForm):
    port = forms.ChoiceField(choices=[], label='Serial Port')

    class Meta:
        model = Printer
        fields = ['name', 'port', 'baudrate']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['port'].choices = printer_manager.list_serial_ports()