import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from printer_manager.instance import printer_manager
from asgiref.sync import sync_to_async
from .models import Printer, PrintJob
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

active_loops = {}  # Keeps track of one loop per printer

class PrinterStatusConsumer(AsyncWebsocketConsumer):
    def __init__(self):
        super().__init__()
        self.email_send = False

    async def connect(self):
        pk = self.scope['url_route']['kwargs']['pk'] 

        try:
            printer = await sync_to_async(Printer.objects.get)(pk=pk)
            self.printer_name = printer.name
        except Printer.DoesNotExist:
            await self.close()
            return

        self.room_group_name = f"printer_{self.printer_name}"

        if self.printer_name not in printer_manager.printers:
            print(f"[WS] Printer '{self.printer_name}' not in memory. Will report as 'Disconnected'.")

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Only one loop per printer, start it in the background
        if self.printer_name not in active_loops:
            active_loops[self.printer_name] = True
            asyncio.create_task(self.start_broadcast_loop())

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        active_loops.pop(self.printer_name, None)  # Force-stop loop on disconnect

    async def start_broadcast_loop(self):
        last_status = None

        while self.printer_name in active_loops:
            try:
                printer_exists = await sync_to_async(Printer.objects.filter(name=self.printer_name).exists)()
                if not printer_exists:
                    print(f"[WS] Printer '{self.printer_name}' no longer exists. Closing socket.")
                    active_loops.pop(self.printer_name, None)  # Stop the loop
                    await self.close()
                    return
            except Exception as e:
                print(f"[WS] DB check failed: {e}")

            printer_data = await sync_to_async(printer_manager.list_printer)(self.printer_name)

            if printer_data:
                time_remaining = printer_manager.monitorprinter_time_remaining.get(self.printer_name)
                printer_status = printer_manager.monitorprinter_status.get(self.printer_name)

                # Handle completed jobs
                if time_remaining == "Printing Completed" and printer_status == "Not SD printing":
                    active_job = await self.get_active_job(self.printer_name)
                    if active_job:
                        completed_data = await self.mark_job_completed(active_job["job_id"])
                        if completed_data:
                            printer_data.update(completed_data)
                            await self.send_email(completed_data["job_id"])
                            self.email_send = True

                # Handle ongoing jobs
                elif printer_status in ["SD printing", "Uploading to SD card"]:
                    job_data = await self.get_active_job(self.printer_name)
                    if job_data:
                        printer_data.update(job_data)
                        self.email_send = False
                
                # Handle failed jobs
                else:
                    failed_job = await self.get_failed_job(self.printer_name)
                    if failed_job:
                        printer_data.update(failed_job)
                        await self.send_email(failed_job["job_id"])
                        self.email_send = True

                current_status = json.dumps(printer_data)
                if current_status != last_status:
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            "type": "printer.status",
                            "message": current_status
                        }
                    )
                    last_status = current_status

            else:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "printer.status",
                        "message": json.dumps({"status": "Disconnected"})
                    }
                )

            await asyncio.sleep(1)

    async def printer_status(self, event):
        await self.send(text_data=event["message"])

    async def job_status(self, event):
        await self.send(text_data=event["message"])

    @sync_to_async
    def get_active_job(self, printer_name):
        job = PrintJob.objects.select_related("user").filter(
            printer__name=printer_name, status__in=["Printing", "Completed"]).first()
        if job:
            return {
                "job_status": "Printing",
                "job_id": job.id,
                "job_owner_id": job.user.id,
            }
        return None

    @sync_to_async
    def mark_job_completed(self, job_id):
        job = PrintJob.objects.select_related("user").filter(id=job_id).first()
        if job:
            job.status = "Completed"
            job.save()
            return {
                "job_status": "Completed",
                "job_id": job.id,
                "job_owner_id": job.user.id}
        return None
    
    @sync_to_async
    def get_failed_job(self, printer_name):
        job = PrintJob.objects.select_related("user").filter(
            printer__name=printer_name, status="Failed").first()
        if job:
            return {
                "job_status": "Failed",
                "job_id": job.id,
                "job_owner_id": job.user.id,
            }
        return None
    
    @sync_to_async
    def send_email(self, job_id):
        if self.email_send:
            return

        job = PrintJob.objects.select_related("user").filter(id=job_id).first()
        if not job or not job.user or not job.user.email:
            return
        
        filename = job.file.name.split("/")[-1]
        email_message_completed = render_to_string('emails/print_job_completed.html', {
            'username': job.user.username,
            'filename': job.file.name,
            'printer': job.printer.name,
        })

        email_message_failed = render_to_string('emails/print_job_failed.html', {
            'username': job.user.username,
            'filename': job.file.name,
            'printer': job.printer.name,
        })
        # Send email only if the user has an email address
        if job.user.email:
            try:
                if job.status == "Completed":
                    send_mail(
                        subject=f"Your print {filename} is ready for pickup",
                        message= email_message_completed,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[job.user.email],
                    )
                if job.status == "Failed":
                    send_mail(
                        subject=f"Your print {filename} has failed",
                        message= email_message_failed,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[job.user.email],
                    )

            except Exception as e:
                print(f"Email failed: {e}")
