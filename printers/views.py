from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, CreateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.http import HttpResponseForbidden
from django.core.paginator import Paginator
from django.http import JsonResponse
import os
import time

from .models import Printer, PrintJob
from .forms import PrinterForm
from printer_manager.instance import printer_manager


class PrinterListView(ListView):
    model = Printer
    template_name = 'printer_list.html'
    context_object_name = 'printers'

class PrinterCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Printer
    form_class = PrinterForm
    template_name = 'printer_add.html'
    success_url = reverse_lazy('printer_list')

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.role == 'admin'

    def form_valid(self, form):
        printer = form.save(commit=False)

        try:
            printer_manager.connect_printer(printer.name, printer.port, printer.baudrate)
            printer = form.save()
            response = redirect(self.success_url)
        except Exception as e:
            messages.error(self.request, f"Failed to connect printer: {str(e)}", extra_tags="connection_error")
            response = self.form_invalid(form)
        
        return response

class PrinterDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Printer
    template_name = 'printer_delete.html'
    success_url = reverse_lazy('printer_list')

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.role == 'admin'

    def post(self, request, *args, **kwargs): 
        return self.delete(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        printer = self.object

        try:
            printer_manager.remove_printer(printer.name)
            printer.delete()
            response = redirect(self.success_url)
        except Exception as e:
            messages.error(request, f"Failed to remove printer: {str(e)}", extra_tags="removal_error")
            context = self.get_context_data()
            response = self.render_to_response(context)

        return response

class PrinterDetailView(LoginRequiredMixin, DetailView):
    model = Printer
    template_name = 'printer_detail.html'
    context_object_name = 'printer'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        printer = self.get_object()

        # Get the currently printing job for this printer
        context['current_job'] = PrintJob.objects.filter(printer=printer, status__in=["Printing", "Completed", "Failed"]).first()

        # Get the queue
        queue_list = PrintJob.objects.filter(printer=printer, status="Queued").order_by('created_at')

        paginator = Paginator(queue_list, 5)  # 5 jobs per page
        page_number = self.request.GET.get('page')
        context['page_obj'] = paginator.get_page(page_number)

        # Add model_removed flag from printer_manager
        context['model_removed'] = printer_manager.model_removed.get(printer.name, False)

        # Add printer_connected flag
        context['printer_connected'] = printer.name in printer_manager.printers
        return context

def start_print(request, pk):
    printer = get_object_or_404(Printer, pk=pk)
    gcode_file = request.FILES.get("file")

    if request.user.print_jobs_limit <= 0:
        messages.error(request, "You have reached your print job limit.", extra_tags='print_error')
        return redirect('printer_detail', pk=pk)
    
    queue_length = len(printer_manager.queues.get(printer.name, []))
    if queue_length >= 10:
        messages.error(request, "Queue is full. A maximum of 10 print jobs are allowed per printer.", extra_tags='print_error')
        return redirect('printer_detail', pk=pk)

    fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'gcode_files'))
    filename = fs.save(gcode_file.name, gcode_file)
    file_path = fs.path(filename)
    
    job = PrintJob.objects.create(
        printer=printer,
        user=request.user,
        file=f"gcode_files/{filename}",
        status="Queued"
    )

    try:
        if printer_manager.model_removed.get(printer.name, False):
            printer_manager.print_gcode(printer.name, file_path, raise_on_error=True)
            
            # Poll the error flag for a short time, because error is in thread
            # and may not be set immediately
            for _ in range(60):  # check every 0.5s for 30s
                if printer_manager.job_status_error.get(printer.name):
                    job.status = "Failed"
                    job.save()
                    raise Exception(f"Error during print job on '{printer.name}'. Please check the printer status.")
                time.sleep(0.5)
            
            job.status = "Printing"
            job.save()
            printer_manager.model_removed[printer.name] = False
            messages.success(request, f"Printing started: {gcode_file.name}", extra_tags='print_success')
        else:
            printer_manager.add_to_queue(printer.name, file_path, raise_on_error=True)
            messages.success(request, f"Model added to queue: {gcode_file.name}", extra_tags='print_success')

        request.user.print_jobs_limit -= 1
        request.user.save()

    except Exception as e:
        messages.error(request, f"Print failed: {e}", extra_tags='print_error')
        

    return JsonResponse({
    "redirect": reverse('printer_detail', kwargs={"pk": printer.pk})
})

def delete_printjob(request, pk):
    job = get_object_or_404(PrintJob, pk=pk)
    printer = job.printer

    if request.user != job.user:
        return HttpResponseForbidden("You are not allowed to delete this print job.")

    printer_name = printer.name

    try:
        # Restore print job limit
        if job.user.is_superuser or job.user.role in ['teacher', 'admin']:
            job.user.print_jobs_limit += 1
            job.user.save()

        # Delete the job
        job.delete()

        # Delete the uploaded file if it exists
        if job.file and os.path.isfile(job.file.path):
            os.remove(job.file.path)

        # Remove from printer manager
        printer_manager.remove_model(printer_name, raise_on_error=True)
                    
        # Start next job if one is queued
        queued_job = PrintJob.objects.filter(printer=printer, status="Queued").order_by('created_at').first()
        if queued_job:

            for _ in range(60):  # check every 0.5s for 30s
                if printer_manager.job_status_error.get(printer.name):
                    queued_job.status = "Failed"
                    queued_job.save()
                    raise Exception(f"Error during print job on '{printer.name}'. Please check the printer status.")
                time.sleep(0.5)

            queued_job.status = "Printing"
            queued_job.save()
            filename = os.path.basename(queued_job.file.path)
            messages.success(request, f"Printing started: {filename}", extra_tags='print_success')
        else:
            messages.success(request, "Model removed. You can now upload a new one.", extra_tags='print_success')

    except Exception as e:
        messages.error(request, f"Error removing model: {e}", extra_tags='print_error')

    return JsonResponse({
    "redirect": reverse('printer_detail', kwargs={"pk": printer.pk})
    })

def reconnect_printer(request, pk):
    printer = get_object_or_404(Printer, pk=pk)
    printer_name = printer.name

    try:
        printer_manager.reconnect_printer(printer_name, raise_on_error=True)
        messages.success(request, "Printer reconnected.", extra_tags='print_success')
    except Exception as e:
        messages.error(request, f"Error reconnecting printer: {e}, please check the connection.", extra_tags='print_error')

    return redirect('printer_detail', pk=pk)

