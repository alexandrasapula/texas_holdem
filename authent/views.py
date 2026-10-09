from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from .forms import LoginForm, SignupForm


def auth_view(request):
    if request.user.is_authenticated:
        return redirect("lobby:lobby")
    login_form = LoginForm()
    signup_form = SignupForm()
    active_tab = "login"
    if request.method == "POST":
        active_tab = request.POST.get("form_type", "login")
        if active_tab == "login":
            login_form = LoginForm(request.POST)
            if login_form.is_valid():
                user = authenticate(request, username=login_form.cleaned_data["username"], password=login_form.cleaned_data["password"],)
                if user is not None:
                    login(request, user)
                    return redirect("lobby:lobby")
                login_form.add_error(None, "Wrong username or password")
        else:
            signup_form = SignupForm(request.POST)
            if signup_form.is_valid():
                user = signup_form.save()
                login(request, user)
                return redirect("lobby:lobby")
    context = {"login_form": login_form, "signup_form": signup_form, "active_tab": active_tab,}
    return render(request, "auth/auth.html", context)
