from django import forms
from .models import Printer
from printer_manager.instance import printer_manager
from django.core.exceptions import ValidationError
import re

class PrinterForm(forms.ModelForm):
    port = forms.ChoiceField(choices=[], label='Serial Port')

    class Meta:
        model = Printer
        fields = ['name', 'port', 'baudrate']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['port'].choices = printer_manager.list_serial_ports()

    def clean_name(self):
        name = self.cleaned_data['name']
        if " " in name:
            raise ValidationError("Spaces are not allowed in the printer name.")
        if not re.match(r'^[a-zA-Z0-9_.-]+$', name):
            raise ValidationError("Printer name must contain only ASCII letters, digits, hyphens, underscores, or periods.")
        if len(name) > 99:
            raise ValidationError("Printer name must be less than 100 characters.")
        
        return name