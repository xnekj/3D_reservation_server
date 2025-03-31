from django.db import models
from accounts.models import CustomUser

class Printer(models.Model):
    name = models.CharField(max_length=255, unique=True)
    port = models.CharField(max_length=255, unique=True)
    baudrate = models.IntegerField(default=115200)

    def __str__(self):
        return self.name

class PrintJob(models.Model):
    printer = models.ForeignKey(Printer, on_delete=models.CASCADE)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    file = models.FileField(upload_to='gcode_files/')
    status = models.CharField(
        max_length=50, choices=[("Queued", "Queued"), ("Printing", "Printing"), ("Completed", "Completed")], default="Queued"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.file.name} - {self.printer.name} ({self.user.username})"