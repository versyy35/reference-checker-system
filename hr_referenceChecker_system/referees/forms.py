from django import forms
from .models import Referee


class RefereeForm(forms.ModelForm):
    """
    Form for creating and editing referees
    """
    class Meta:
        model = Referee
        fields = ['name', 'email', 'phone', 'relationship', 'applicant_name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter referee full name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'referee@example.com'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+60123456789'
            }),
            'relationship': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Former Manager, Colleague, Supervisor'
            }),
            'applicant_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Name of person being referenced'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set is_active to True by default for new referees
        if not self.instance.pk:
            self.fields['is_active'].initial = True
    
    def clean_email(self):
        """
        Validate email is unique among active referees
        """
        email = self.cleaned_data.get('email')
        if email:
            # Check if email exists for other active referees
            existing = Referee.objects.filter(email=email, is_active=True)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise forms.ValidationError(
                    'A referee with this email address already exists.'
                )
        return email
    
    def clean_phone(self):
        """
        Clean and validate phone number
        """
        phone = self.cleaned_data.get('phone')
        if phone:
            # Remove any spaces, dashes, or parentheses
            cleaned_phone = ''.join(filter(lambda x: x.isdigit() or x == '+', phone))
            
            # Basic validation - should have at least 10 digits
            digits_only = ''.join(filter(str.isdigit, cleaned_phone))
            if len(digits_only) < 10:
                raise forms.ValidationError(
                    'Please enter a valid phone number with at least 10 digits'
                )
            
            # If doesn't start with +, add it
            if not cleaned_phone.startswith('+'):
                cleaned_phone = '+' + cleaned_phone
                
        return phone  # Return original format for now