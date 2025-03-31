# Generated by Django 5.1.7 on 2025-03-24 18:53

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('printers', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PrintJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='gcode_files/')),
                ('status', models.CharField(choices=[('Queued', 'Queued'), ('Printing', 'Printing'), ('Completed', 'Completed')], default='Queued', max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('printer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='printers.printer')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
