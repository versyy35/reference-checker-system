from django.db import models
from django.utils import timezone
from datetime import timedelta
import uuid
import secrets


class FormStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    COMPLETED = 'COMPLETED', 'Completed'


class Form(models.Model):
    """
    Model for assigned forms (Template + Referee combination)
    """
    template = models.ForeignKey('form_templates.Template', on_delete=models.CASCADE)
    referee = models.ForeignKey('referees.Referee', on_delete=models.CASCADE)
    unique_token = models.CharField(max_length=255, unique=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=FormStatus.choices,
        default=FormStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Form Assignment'
        verbose_name_plural = 'Form Assignments'
    
    def save(self, *args, **kwargs):
        if not self.unique_token:
            self.unique_token = self.generate_unique_token()
        super().save(*args, **kwargs)
    
    def generate_unique_token(self):
        """Generate a unique access token for this form"""
        return secrets.token_urlsafe(32)
    
    def generate_access_url(self, base_url="http://localhost:8000"):
        """Generate the public access URL for this form"""
        return f"{base_url}/form/{self.unique_token}/"
    
    def mark_completed(self):
        """Mark this form as completed"""
        self.status = FormStatus.COMPLETED
        self.submitted_at = timezone.now()
        self.save()
    
    def is_expired(self, expiry_days=30):
        """Check if the form has expired"""
        expiry_date = self.created_at + timedelta(days=expiry_days)
        return timezone.now() > expiry_date
    
    def __str__(self):
        return f"{self.template.title} - {self.referee.name}"