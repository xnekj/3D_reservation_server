from django.contrib import admin

from .models import Printer, PrintJob

admin.site.register(Printer)

admin.site.register(PrintJob)
