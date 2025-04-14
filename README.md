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

---

## Setup & Usage

### 5. Run Migrations

```bash
python manage.py migrate
```

An initial superuser is auto-created:

- **Username:** `admin`
- **Password:** `12345`

Change credentials anytime via the admin panel or User Management tab.

---

### 6. Start Development Server

```bash
python manage.py runserver
```

Then open:  
[http://127.0.0.1:8000](http://127.0.0.1:8000)

---

### 7. Login to Admin Panel

Access at:  
[http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

Login with:

- **Username:** `admin`
- **Password:** `12345`

You can manage users, jobs, and printers here.

---

### 8. Verify WebSocket & HTTP

- Open DevTools > Network > WS tab
- Confirm WebSocket connects and shows messages
- Navigate through UI and verify printer statuses and jobs update in real time

---

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

