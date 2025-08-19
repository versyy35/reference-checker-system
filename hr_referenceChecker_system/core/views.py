from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from referees.models import Referee
from form_templates.models import Template
from forms.models import Form, FormStatus
from responses.models import Response
from django.utils import timezone
from datetime import timedelta
import json


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
        
        try:
            from core.models import Notification
            
            # Get all notifications for the user
            all_notifications = Notification.objects.filter(
                user=self.request.user,
                is_dismissed=False
            ).order_by('-created_at')
            
            # Calculate stats
            today = timezone.now().date()
            week_ago = timezone.now() - timedelta(days=7)
            
            total_notifications = all_notifications.count()
            unread_notifications = all_notifications.filter(is_read=False).count()
            todays_notifications = all_notifications.filter(created_at__date=today).count()
            this_weeks_notifications = all_notifications.filter(created_at__gte=week_ago).count()
            
            # Format notifications for template
            formatted_notifications = []
            for notification in all_notifications:
                formatted_notifications.append({
                    'id': notification.id,
                    'type': notification.notification_type,
                    'icon': notification.icon,
                    'message': notification.message,
                    'time': notification.created_at,
                    'is_new': not notification.is_read,
                    'title': notification.title,
                })
            
            context.update({
                'notifications': formatted_notifications,
                'total_notifications': total_notifications,
                'unread_notifications': unread_notifications,
                'todays_notifications': todays_notifications,
                'this_weeks_notifications': this_weeks_notifications,
            })
            
        except ImportError:
            # Fallback if model doesn't exist yet
            context.update({
                'notifications': [],
                'total_notifications': 0,
                'unread_notifications': 0,
                'todays_notifications': 0,
                'this_weeks_notifications': 0,
            })
        
        return context


@login_required
@require_POST
def mark_notification_read(request, notification_id):
    """
    AJAX view to mark a single notification as read
    """
    try:
        from core.models import Notification
        
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.mark_as_read()
        
        # Get updated count
        unread_count = Notification.get_unread_count(request.user)
        
        return JsonResponse({
            'success': True,
            'unread_count': unread_count,
            'message': 'Notification marked as read'
        })
        
    except ImportError:
        return JsonResponse({
            'success': False,
            'error': 'Notification system not available'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def mark_all_notifications_read(request):
    """
    AJAX view to mark all notifications as read
    """
    try:
        from core.models import Notification
        
        Notification.mark_all_as_read(request.user)
        
        return JsonResponse({
            'success': True,
            'unread_count': 0,
            'message': 'All notifications marked as read'
        })
        
    except ImportError:
        return JsonResponse({
            'success': False,
            'error': 'Notification system not available'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def clear_all_notifications(request):
    """
    AJAX view to clear (dismiss) all notifications
    """
    try:
        from core.models import Notification
        
        Notification.clear_all(request.user)
        
        return JsonResponse({
            'success': True,
            'unread_count': 0,
            'message': 'All notifications cleared'
        })
        
    except ImportError:
        return JsonResponse({
            'success': False,
            'error': 'Notification system not available'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def dismiss_notification(request, notification_id):
    """
    AJAX view to dismiss a single notification
    """
    try:
        from core.models import Notification
        
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.dismiss()
        
        # Get updated count
        unread_count = Notification.get_unread_count(request.user)
        
        return JsonResponse({
            'success': True,
            'unread_count': unread_count,
            'message': 'Notification dismissed'
        })
        
    except ImportError:
        return JsonResponse({
            'success': False,
            'error': 'Notification system not available'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)