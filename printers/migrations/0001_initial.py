# Generated by Django 5.1.7 on 2025-03-22 14:47

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Printer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True)),
                ('port', models.CharField(max_length=255, unique=True)),
                ('baudrate', models.IntegerField(default=115200)),
            ],
        ),
    ]
