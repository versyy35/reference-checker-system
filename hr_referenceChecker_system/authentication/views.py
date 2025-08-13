from django.shortcuts import render
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.urls import reverse_lazy


class CustomLoginView(LoginView):
    """
    Custom login view with HELP International School branding
    """
    template_name = 'auth/login.html'
    redirect_authenticated_user = True
    success_url = reverse_lazy('core:dashboard')
    
    def form_valid(self, form):
        messages.success(self.request, f'Welcome back, {form.get_user().email}!')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Invalid email or password. Please try again.')
        return super().form_invalid(form)


