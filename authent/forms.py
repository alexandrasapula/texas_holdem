from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class LoginForm(forms.Form):
    username = forms.CharField(label = "Username", max_length=150, widget=forms.TextInput(attrs={"placeholder": "Enter username", "class": "form-control"}),)
    password = forms.CharField(label= "Password", widget=forms.PasswordInput(attrs={"placeholder": "Enter password", "class": "form-control"}),)


class SignupForm(forms.ModelForm):
    password = forms.CharField(label= "Password", widget=forms.PasswordInput(attrs={"placeholder": "Enter password", "class": "form-control"}),)
    password_confirm = forms.CharField(label= "Confirm password", widget=forms.PasswordInput(attrs={"placeholder": "Confirm password", "class": "form-control"}),)
    class Meta:
        model = User
        fields = ("username", "email")
        widgets = {
            "username": forms.TextInput(attrs={"placeholder": "Enter username", "class": "form-control"}),
            "email": forms.EmailInput(attrs={"placeholder": "enter email", "class": "form-control"})
        }
    
    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and User.objects.filter(email=email).exists():
            raise ValidationError("User with this email is exists")
        return email
    
    def clean(self):
        cleaned_data=super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")
        if password and password_confirm and password != password_confirm:
            self.add_error("password_confirm", "Passwords do not match")
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user
