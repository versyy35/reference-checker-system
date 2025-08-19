# Replace the existing core/context_processors.py with this updated version

from forms.models import Form, FormStatus
from django.utils import timezone
from datetime import timedelta


def notifications(request):
    """
    Add notification data to all templates using the new persistent notification system
    """
    if not request.user.is_authenticated:
        return {}
    
    try:
        # Import here to avoid circular imports
        from core.models import Notification
        
        # Get unread notifications for the current user
        notifications_list = Notification.get_recent_notifications(request.user, limit=10)
        unread_count = Notification.get_unread_count(request.user)
        
        # Convert to the format expected by templates
        formatted_notifications = []
        for notification in notifications_list:
            formatted_notifications.append({
                'id': notification.id,
                'type': notification.notification_type,
                'icon': notification.icon,
                'message': notification.message,
                'time': notification.created_at,
                'is_new': not notification.is_read,
                'title': notification.title,
            })
        
        return {
            'notifications': formatted_notifications,
            'notification_count': unread_count,
            'has_notifications': unread_count > 0,
        }
        
    except Exception as e:
        # Fallback to old system if new model doesn't exist yet
        # This ensures the site doesn't break during migration
        
        # Get pending forms (not submitted)
        pending_forms = Form.objects.filter(status=FormStatus.PENDING)
        
        # Get recently submitted forms (last 7 days)
        week_ago = timezone.now() - timedelta(days=7)
        recent_submissions = Form.objects.filter(
            status=FormStatus.COMPLETED,
            submitted_at__gte=week_ago
        ).order_by('-submitted_at')
        
        # Count overdue forms (pending for more than 7 days)
        overdue_forms = pending_forms.filter(
            created_at__lt=week_ago
        )
        
        # Build notification list (fallback)
        notifications_list = []
        
        # Add recent submissions
        for form in recent_submissions[:5]:  # Latest 5
            notifications_list.append({
                'id': f'submission_{form.id}',
                'type': 'success',
                'icon': 'fas fa-check-circle',
                'message': f'{form.referee.name} submitted {form.template.title}',
                'time': form.submitted_at,
                'is_new': True,
                'title': 'Form Submitted',
            })
        
        # Add overdue notifications
        for form in overdue_forms[:3]:  # Top 3 overdue
            days_overdue = (timezone.now() - form.created_at).days
            notifications_list.append({
                'id': f'overdue_{form.id}',
                'type': 'warning',
                'icon': 'fas fa-exclamation-triangle',
                'message': f'{form.referee.name} has not submitted {form.template.title} ({days_overdue} days overdue)',
                'time': form.created_at,
                'is_new': False,
                'title': 'Form Overdue',
            })
        
        # Sort by time (newest first)
        notifications_list.sort(key=lambda x: x['time'], reverse=True)
        
        return {
            'notifications': notifications_list[:10],  # Show latest 10
            'notification_count': len([n for n in notifications_list if n['is_new']]),
            'has_notifications': len(notifications_list) > 0,
        }