from django.views.generic import DetailView, CreateView, ListView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import PasswordChangeView
from printers.models import CustomUser, PrintJob
from django.urls import reverse, reverse_lazy
from django.views import View
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
import os

from .forms import CustomUserChangeForm, AdminSetPasswordForm, CustomUserCreationForm
from .decorators import role_required
from printer_manager.instance import printer_manager


@login_required
def login_redirect_view(request):
    if request.user.must_change_password:
        return redirect('password_change')
    return redirect('printer_list')

class CustomPasswordChangeView(PasswordChangeView):
    success_url = reverse_lazy('profile')

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.user.must_change_password = False
        self.request.user.save()
        messages.success(self.request, "Your password has been changed.", extra_tags="password_changed")
        return response

@login_required
@role_required(['student', 'teacher', 'admin'])
def delete_from_queue(request, pk):
    job = get_object_or_404(PrintJob, pk=pk)

    if request.user != job.user:
        return HttpResponseForbidden("You are not allowed to delete this print job.")

    if job.status != "Queued":
        messages.error(request, "Only queued jobs can be removed from profile.", extra_tags='print_error')
        return redirect('profile')

    printer = job.printer
    file_path = job.file.path
    filename = os.path.abspath(file_path)

    try:
        # Remove from printer queue
        printer_manager.remove_from_queue(printer.name, filename, raise_on_error=True)

        # Remove the uploaded file
        if job.file and os.path.isfile(file_path):
            os.remove(file_path)

        # Restore print limit if needed
        if job.user.is_superuser or job.user.role in ['teacher', 'admin']:
            job.user.print_jobs_limit += 1
            job.user.save()

        # Delete the job from DB
        job.delete()

        messages.success(request, "Queued print job removed from your profile.", extra_tags='queue_success')

    except Exception as e:
        messages.error(request, f"Failed to remove print job: {e}", extra_tags='queue_error')

    return redirect('profile')

class ProfileDetailedView(LoginRequiredMixin, DetailView):
    model = CustomUser
    template_name = 'profile.html'

    def get_object(self, queryset=None):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user_jobs = PrintJob.objects.filter(user=self.request.user).order_by('created_at')

        paginator = Paginator(user_jobs, 7)
        page_number = self.request.GET.get('page')
        context['page_obj'] = paginator.get_page(page_number)

        return context

class UserManagementView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = CustomUser
    template_name = 'registration/user_management.html'
    context_object_name = 'users'
    paginate_by = 8

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.role == 'admin'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        users_page = context['users']

        context['form'] = CustomUserCreationForm()

        context['edit_forms'] = {
            str(user.id): CustomUserChangeForm(instance=user)
            for user in users_page
        }

        context['password_forms'] = {
            str(user.id): AdminSetPasswordForm()
            for user in users_page
        }

        return context

class CreateUserView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.role == 'admin'

    def post(self, request):
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "User created successfully.", extra_tags='user_success')
        else:
            if form.errors.get('username'):
                messages.error(request, "Username is already in use. Please choose a different username.", extra_tags='user_error')
            else:
                messages.error(request, "Failed to create user.", extra_tags='user_error')
        return redirect('user_management')


class EditUserView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.role == 'admin'

    def post(self, request, pk):
        user = CustomUser.objects.get(pk=pk)
        form = CustomUserChangeForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
        return redirect('user_management')


class AdminPasswordChangeModalView(LoginRequiredMixin, UserPassesTestMixin, View):

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.role == 'admin'

    def post(self, request, pk):
        user = get_object_or_404(CustomUser, pk=pk)
        form = AdminSetPasswordForm(request.POST)
        if form.is_valid():
            user.set_password(form.cleaned_data['password1'])
            user.save()

            if request.user == user:
                logout(request)
                return redirect(reverse('login'))
            
        return redirect('user_management')
    

class DeleteUserView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.role == 'admin'

    def post(self, request, pk):
        user = get_object_or_404(CustomUser, pk=pk)

        # Prevent admins from deleting each other
        if user.role == 'admin' and not request.user.is_superuser:
            messages.error(request, "Only superusers can delete admin accounts.", extra_tags='user_error')
            return redirect('user_management')

        user.delete()
        messages.success(request, f"User '{user.username}' has been deleted.", extra_tags='user_success')
        return redirect('user_management')

