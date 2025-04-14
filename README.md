# 3D_reservation_server

A simple Django-based server to manage multiple 3D printers connected via USB.  
The system supports queuing, file uploads, user roles, and real-time printer monitoring via WebSockets.

## Features

- User role management (admin, teacher, student)
    - **Admin**: Can add printers, manage users, and oversee all print jobs.
    - **Teacher**: Can submit print jobs and has a print job limit that resets after each completed print.
    - **Student**: Can submit print jobs but has a fixed print job limit that does not reset automatically.
- Print queue per printer
- Live status updates via WebSocket
- USB printer connection and monitoring
- Admin UI for managing users and jobs
- Optional email notifications for job status

---

### 1. Clone the Repository

```bash
git clone https://github.com/your_username/your_project_name.git
cd your_project_name
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure `.env` File

Create a `.env` file in the root folder:

```ini
DJANGO_SETTINGS_MODULE=django_project.settings
DEBUG=True
DJANGO_ENV=development
DATABASE_URL=sqlite:///db.sqlite3
SECRET_KEY=your_secret_key
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
```

## Setup & Usage

### 5. Run Migrations

```bash
python manage.py migrate
```

An initial superuser is auto-created:

- **Username:** `admin`
- **Password:** `12345`

Change credentials anytime via the admin panel or User Management tab.

### 6. Start Development Server

```bash
python manage.py runserver
```

Then open:  
[http://127.0.0.1:8000](http://127.0.0.1:8000)


### 7. Login to Admin Panel

Access at:  
[http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

Login with:

- **Username:** `admin`
- **Password:** `12345`

You can manage users, jobs, and printers here.


### 8. Verify WebSocket & HTTP

- Open DevTools > Network > WS tab
- Confirm WebSocket connects and shows messages
- Navigate through UI and verify printer statuses and jobs update in real time


## Printer Control

- Add USB printers with name, port, and baudrate
- Upload `.gcode` files to queue or print immediately
- Monitor job status, temps, progress, and remaining time
- Cancel, reconnect, and remove printers dynamically
- CLI available via `printer_shell.py`

---

## Project Structure

| Directory / File        | Description                                  |
|-------------------------|----------------------------------------------|
| `accounts/`             | Custom user model, roles, and login views    |
| `printers/`             | Models, forms, and views for printer jobs    |
| `printer_manager/`      | Core logic for USB printer control           |
| `templates/`            | Django HTML templates                        |
| `media/gcode_files/`    | Directory for uploaded `.gcode` files        |
| `static/`               | CSS for login.html                           |
| `printer_shell.py`      | CLI tool for serial printer control          |

---

## Tips

- Run `printer_shell.py` with `sudo` to access USB ports:
  ```bash
  sudo python printer_shell.py
  ```
- Set `DEBUG=False` in `.env` for production
- For real email alerts, configure SMTP in `settings.py`

# Production Deployment Guide for 3D_reservation_server

This guide walks you through setting up your Django 3D Printer Server on a Linux server using **Daphne**, **Redis**, and **Nginx**.

---

## Step 1: Install Necessary Packages on the Server

### 1. Update your server

```bash
sudo apt update && sudo apt upgrade
```


### 2. Install required packages

```bash
sudo apt install python3-pip python3-venv git nginx redis
```


### 3. Clone the Repository

```bash
git clone https://github.com/your_username/your_project_name.git
cd your_project_name
```


### 4. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```


### 5. Install Dependencies

```bash
pip install -r requirements.txt
```


### 6. Configure `.env` File

Create a `.env` file in the root folder:

```ini
DJANGO_SETTINGS_MODULE=django_project.settings
DEBUG=False
DJANGO_ENV=production
DATABASE_URL=sqlite:///db.sqlite3
SECRET_KEY=your_secret_key
DJANGO_ALLOWED_HOSTS=your_server_ip_adress,localhost
```


### 7. Run Migrations

```bash
python manage.py migrate
```

An initial superuser is auto-created:

- **Username:** `admin`
- **Password:** `12345`

Change credentials anytime via the admin panel or User Management tab.


### Step 8: Collect Static Files for Production

Run the following command to collect static files into the STATIC_ROOT:

```bash
python manage.py collectstatic
```

This will copy all static files from your app into the directory specified in STATIC_ROOT for production.


### Step 9: Set Permissions for media/ and static/ Directories

Set correct permissions to allow Nginx to serve static and media files:

```bash
sudo chown -R pi:www-data /home/pi/3D_reservation_server/staticfiles
sudo chown -R pi:www-data /home/pi/3D_reservation_server/media
sudo chmod -R 755 /home/pi/3D_reservation_server/staticfiles
sudo chmod -R 755 /home/pi/3D_reservation_server/media
```

Ensure proper permissions for the media and static directories. This allows Nginx to serve static files and handle file uploads.


## Step 2: Run Daphne as a Service

### 10. Create systemd service for Daphne

```bash
sudo nano /etc/systemd/system/daphne.service
```

Paste the following:

```ini
[Unit]
Description=Daphne ASGI Server
After=network.target

[Service]
User=pi
Group=www-data
WorkingDirectory=/home/pi/3D_reservation_server
EnvironmentFile=/home/pi/3D_reservation_server/.env
Environment="DJANGO_SETTINGS_MODULE=django_project.settings"

ExecStart=/home/pi/3D_reservation_server/venv/bin/daphne -b 127.0.0.1 -p 8000 django_project.asgi:application

RuntimeDirectory=daphne
RuntimeDirectoryMode=0755

[Install]
WantedBy=multi-user.target
```

### 11. Start and enable Daphne

```bash
sudo systemctl daemon-reload
sudo systemctl start daphne
sudo systemctl enable daphne
```


## Step 3: Configure Nginx

### 12. Create Nginx config file

```bash
sudo nano /etc/nginx/sites-available/django
```

Add:

```nginx
server {
    listen 80;
    server_name your_server_ip_adress your_website_name;

    location /static/ {
        alias /home/pi/3D_reservation_server/staticfiles/;
    }

    location /media/ {
        alias /home/pi/3D_reservation_server/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

### 13. Enable the site and restart Nginx

```bash
sudo ln -s /etc/nginx/sites-available/django /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---
