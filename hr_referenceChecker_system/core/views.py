from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from referees.models import Referee
from form_templates.models import Template
from forms.models import Form, FormStatus
from responses.models import Response
from django.utils import timezone
from datetime import timedelta


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
    
class NotificationsView(LoginRequiredMixin, TemplateView):
    template_name = 'core/notifications.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get notifications from the context processor
        # This reuses the same logic from core/context_processors.py
        from core.context_processors import notifications
        notifications_data = notifications(self.request)
        
        # Calculate additional stats for the full page
        today = timezone.now().date()
        week_ago = timezone.now() - timedelta(days=7)
        
        # Get all notifications (not just latest 10)
        pending_forms = Form.objects.filter(status=FormStatus.PENDING)
        recent_submissions = Form.objects.filter(
            status=FormStatus.COMPLETED,
            submitted_at__gte=week_ago
        ).order_by('-submitted_at')
        overdue_forms = pending_forms.filter(
            created_at__lt=week_ago
        )
        
        # Build full notifications list
        all_notifications = []
        
        # Add recent submissions
        for form in recent_submissions:
            all_notifications.append({
                'type': 'success',
                'icon': 'fas fa-check-circle',
                'message': f'{form.referee.name} submitted {form.template.title}',
                'time': form.submitted_at,
                'is_new': (timezone.now() - form.submitted_at).days < 1
            })
        
        # Add overdue notifications
        for form in overdue_forms:
            days_overdue = (timezone.now() - form.created_at).days
            all_notifications.append({
                'type': 'warning',
                'icon': 'fas fa-exclamation-triangle',
                'message': f'{form.referee.name} has not submitted {form.template.title} ({days_overdue} days overdue)',
                'time': form.created_at,
                'is_new': False
            })
        
        # Sort by time (newest first)
        all_notifications.sort(key=lambda x: x['time'], reverse=True)
        
        # Calculate stats
        total_notifications = len(all_notifications)
        unread_notifications = len([n for n in all_notifications if n['is_new']])
        todays_notifications = len([n for n in all_notifications if n['time'].date() == today])
        this_weeks_notifications = len([n for n in all_notifications if n['time'] >= week_ago])
        
        context.update({
            'notifications': all_notifications,
            'total_notifications': total_notifications,
            'unread_notifications': unread_notifications,
            'todays_notifications': todays_notifications,
            'this_weeks_notifications': this_weeks_notifications,
        })
        
        return context
