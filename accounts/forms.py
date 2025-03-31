from django.contrib.auth.forms import UserChangeForm
from django import forms
from .models import CustomUser

class CustomUserCreationForm(forms.ModelForm):
    password = forms.CharField(label="Password", widget=forms.TextInput)

    class Meta:
        model = CustomUser
        fields = ("username", "email", "role", "print_jobs_limit","must_change_password", "password")

    # Override the save method to set the password and hash it
    def save(self, commit=True):
        user = super().save(commit=False)
        raw_password = self.cleaned_data.get('password')
        if raw_password:
            user.set_password(raw_password)
        if commit:
            user.save()
        return user

class CustomUserChangeForm(UserChangeForm):
    password = None
    class Meta:
        model = CustomUser
        fields = ("username", "email", "role", "print_jobs_limit", "must_change_password")

class AdminSetPasswordForm(forms.Form):
    password1 = forms.CharField(label="New Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm Password", widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password1")
        p2 = cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data

