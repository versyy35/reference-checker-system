from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from referees.models import Referee
from form_templates.models import Template
from forms.models import Form, FormStatus
from responses.models import Response


class HomeView(TemplateView):
    template_name = 'core/home.html'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get statistics
        context.update({
            'total_referees': Referee.objects.filter(is_active=True).count(),
            'total_templates': Template.objects.filter(is_active=True).count(),
            'assigned_forms': Form.objects.count(),
            'pending_forms': Form.objects.filter(status=FormStatus.PENDING).count(),
            'completed_forms': Form.objects.filter(status=FormStatus.COMPLETED).count(),
            'total_responses': Response.objects.count(),
        })
        
        return context
