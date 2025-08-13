# User model will be added later
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom User model for HR Reference Checker System
    """
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    def __str__(self):
        return self.email
    
    class Meta:
        db_table = 'auth_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'