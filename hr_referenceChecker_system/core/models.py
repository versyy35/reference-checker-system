# Add this to core/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings


class NotificationType(models.TextChoices):
    SUCCESS = 'success', 'Success'
    WARNING = 'warning', 'Warning'
    INFO = 'info', 'Info'
    DANGER = 'danger', 'Danger'


class Notification(models.Model):
    """
    Model for storing user notifications
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NotificationType.choices, default=NotificationType.INFO)
    icon = models.CharField(max_length=50, default='fas fa-info-circle')
    
    # Status fields
    is_read = models.BooleanField(default=False)
    is_dismissed = models.BooleanField(default=False)
    
    # Related object (optional)
    content_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', 'is_dismissed']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
    
    def dismiss(self):
        """Dismiss notification (hide from UI)"""
        self.is_dismissed = True
        self.save(update_fields=['is_dismissed'])
    
    @classmethod
    def create_notification(cls, user, title, message, notification_type=NotificationType.INFO, icon=None, related_object=None):
        """
        Create a new notification for a user
        """
        if icon is None:
            icon_map = {
                NotificationType.SUCCESS: 'fas fa-check-circle',
                NotificationType.WARNING: 'fas fa-exclamation-triangle',
                NotificationType.INFO: 'fas fa-info-circle',
                NotificationType.DANGER: 'fas fa-exclamation-circle',
            }
            icon = icon_map.get(notification_type, 'fas fa-info-circle')
        
        notification = cls.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            icon=icon,
        )
        
        # Link to related object if provided
        if related_object:
            from django.contrib.contenttypes.models import ContentType
            notification.content_type = ContentType.objects.get_for_model(related_object)
            notification.object_id = related_object.pk
            notification.save(update_fields=['content_type', 'object_id'])
        
        return notification
    
    @classmethod
    def mark_all_as_read(cls, user):
        """Mark all unread notifications for a user as read"""
        cls.objects.filter(user=user, is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
    
    @classmethod
    def clear_all(cls, user):
        """Clear (dismiss) all notifications for a user"""
        cls.objects.filter(user=user, is_dismissed=False).update(is_dismissed=True)
    
    @classmethod
    def get_unread_count(cls, user):
        """Get count of unread notifications for a user"""
        return cls.objects.filter(user=user, is_read=False, is_dismissed=False).count()
    
    @classmethod
    def get_recent_notifications(cls, user, limit=10):
        """Get recent notifications for a user"""
        return cls.objects.filter(user=user, is_dismissed=False).order_by('-created_at')[:limit]


# Helper function to create notifications for form events
def create_form_notification(user, form_assignment, event_type):
    """
    Create notifications for form-related events
    """
    if event_type == 'form_submitted':
        Notification.create_notification(
            user=user,
            title="Form Submitted",
            message=f"{form_assignment.referee.name} submitted {form_assignment.template.title}",
            notification_type=NotificationType.SUCCESS,
            icon='fas fa-check-circle',
            related_object=form_assignment
        )
    elif event_type == 'form_overdue':
        days_overdue = (timezone.now() - form_assignment.created_at).days
        Notification.create_notification(
            user=user,
            title="Form Overdue",
            message=f"{form_assignment.referee.name} has not submitted {form_assignment.template.title} ({days_overdue} days overdue)",
            notification_type=NotificationType.WARNING,
            icon='fas fa-exclamation-triangle',
            related_object=form_assignment
        )
    elif event_type == 'form_assigned':
        Notification.create_notification(
            user=user,
            title="Form Assigned",
            message=f"Successfully assigned {form_assignment.template.title} to {form_assignment.referee.name}",
            notification_type=NotificationType.INFO,
            icon='fas fa-paper-plane',
            related_object=form_assignment
        )