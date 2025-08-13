from forms.models import Form, FormStatus
from django.utils import timezone
from datetime import timedelta


def notifications(request):
    """
    Add notification data to all templates
    """
    if not request.user.is_authenticated:
        return {}
    
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
    
    # Build notification list
    notifications_list = []
    
    # Add recent submissions
    for form in recent_submissions[:5]:  # Latest 5
        notifications_list.append({
            'type': 'success',
            'icon': 'fas fa-check-circle',
            'message': f'{form.referee.name} submitted {form.template.title}',
            'time': form.submitted_at,
            'is_new': True
        })
    
    # Add overdue notifications
    for form in overdue_forms[:3]:  # Top 3 overdue
        days_overdue = (timezone.now() - form.created_at).days
        notifications_list.append({
            'type': 'warning',
            'icon': 'fas fa-exclamation-triangle',
            'message': f'{form.referee.name} has not submitted {form.template.title} ({days_overdue} days overdue)',
            'time': form.created_at,
            'is_new': False
        })
    
    # Sort by time (newest first)
    notifications_list.sort(key=lambda x: x['time'], reverse=True)
    
    return {
        'notifications': notifications_list[:10],  # Show latest 10
        'notification_count': len(notifications_list),
        'pending_count': pending_forms.count(),
        'overdue_count': overdue_forms.count(),
    }