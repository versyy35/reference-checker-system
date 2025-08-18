from django import forms
from django.core.exceptions import ValidationError

from .models import Form
from referees.models import Referee
from form_templates.models import Template


class FormAssignmentForm(forms.ModelForm):
    """
    Form for creating individual form assignments
    """
    send_email = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text="Send email notification to referee"
    )
    
    class Meta:
        model = Form
        fields = ['template', 'referee']
        widgets = {
            'template': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'referee': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Only show active templates and referees
        self.fields['template'].queryset = Template.objects.filter(is_active=True).order_by('title')
        self.fields['referee'].queryset = Referee.objects.filter(is_active=True).order_by('name')
        
        # Add empty option
        self.fields['template'].empty_label = "Select a template"
        self.fields['referee'].empty_label = "Select a referee"
        
        # Update help text
        self.fields['template'].help_text = "Choose the form template to assign"
        self.fields['referee'].help_text = "Choose the referee who will fill the form"
    
    def clean(self):
        cleaned_data = super().clean()
        template = cleaned_data.get('template')
        referee = cleaned_data.get('referee')
        
        if template and referee:
            # Check if assignment already exists
            existing = Form.objects.filter(template=template, referee=referee).first()
            if existing:
                raise ValidationError(
                    f'This template is already assigned to {referee.name}. '
                    f'Status: {existing.get_status_display()}'
                )
        
        return cleaned_data


class BulkAssignmentForm(forms.Form):
    """
    Form for creating multiple assignments at once
    """
    template = forms.ModelChoiceField(
        queryset=Template.objects.filter(is_active=True).order_by('title'),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        }),
        empty_label="Select a template",
        help_text="Choose the template to assign to multiple referees"
    )
    
    referees = forms.ModelMultipleChoiceField(
        queryset=Referee.objects.filter(is_active=True).order_by('name'),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        }),
        help_text="Select multiple referees to assign this template to"
    )
    
    send_email = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text="Send email notifications to all selected referees"
    )
    
    def clean_referees(self):
        referees = self.cleaned_data.get('referees')
        if not referees or len(referees) == 0:
            raise ValidationError('Please select at least one referee.')
        return referees


class FormAssignmentSearchForm(forms.Form):
    """
    Form for searching and filtering form assignments
    """
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by template name, referee name, or email'
        })
    )
    
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Statuses')] + list(Form._meta.get_field('status').choices),
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    template = forms.ModelChoiceField(
        required=False,
        queryset=Template.objects.filter(is_active=True).order_by('title'),
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        empty_label="All Templates"
    )
    
    referee = forms.ModelChoiceField(
        required=False,
        queryset=Referee.objects.filter(is_active=True).order_by('name'),
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        empty_label="All Referees"
    )


class FormStatusUpdateForm(forms.ModelForm):
    """
    Form for updating form status manually
    """
    class Meta:
        model = Form
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'form-select'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].help_text = "Update the current status of this assignment"


class ReminderEmailForm(forms.Form):
    """
    Form for sending reminder emails
    """
    custom_message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Optional: Add a custom message to include in the reminder email'
        }),
        help_text="This message will be added to the standard reminder email"
    )
    
    def clean_custom_message(self):
        message = self.cleaned_data.get('custom_message', '')
        if len(message) > 500:
            raise ValidationError('Custom message must be 500 characters or less.')
        return message