from django.db import models
from django.core.validators import RegexValidator


class Referee(models.Model):
    """
    Model for storing referee information
    """
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    relationship = models.CharField(max_length=100, help_text="e.g., Former Manager, Colleague, etc.")
    applicant_name = models.CharField(max_length=255, help_text="Name of the person being referenced")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Referee'
        verbose_name_plural = 'Referees'
    
    def __str__(self):
        return f"{self.name} - {self.applicant_name}"
    
    def get_assigned_forms(self):
        """Get all forms assigned to this referee"""
        return self.form_set.all()
    
    def update_contact(self, email=None, phone=None):
        """Update referee contact information"""
        if email:
            self.email = email
        if phone:
            self.phone = phone
        self.save()