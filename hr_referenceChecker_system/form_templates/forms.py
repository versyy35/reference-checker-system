from django import forms
from django.forms import inlineformset_factory
from .models import Template, Question, QuestionType


class TemplateForm(forms.ModelForm):
    """
    Form for creating and editing templates
    """
    class Meta:
        model = Template
        fields = ['title', 'description', 'instructions', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter template title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Brief description of this template'
            }),
            'instructions': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Instructions shown to referees before filling the form'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set is_active to True by default for new templates
        if not self.instance.pk:
            self.fields['is_active'].initial = True
    
    def clean_title(self):
        """
        Validate template title is unique among active templates
        """
        title = self.cleaned_data.get('title')
        if title:
            # Check if title exists for other active templates
            existing = Template.objects.filter(title__iexact=title, is_active=True)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise forms.ValidationError(
                    'A template with this title already exists.'
                )
        return title


class QuestionForm(forms.ModelForm):
    """
    Form for creating and editing questions
    """
    choices_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter each choice on a new line'
        }),
        help_text="Enter each choice on a new line (for select/radio/checkbox questions)"
    )
    
    class Meta:
        model = Question
        fields = [
            'question_text', 'question_type', 'is_required', 'order',
            'rating_scale', 'help_text'
        ]
        widgets = {
            'question_text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter your question here'
            }),
            'question_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'is_required': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1
            }),
            'rating_scale': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 2,
                'max': 10,
                'value': 5
            }),
            'help_text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Optional help text for this question'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set default values
        if not self.instance.pk:
            self.fields['is_required'].initial = True
            self.fields['rating_scale'].initial = 5
        
        # Populate choices_text if editing existing question
        if self.instance.pk and self.instance.choices:
            self.fields['choices_text'].initial = self.instance.get_choices_as_text()
    
    def clean(self):
        cleaned_data = super().clean()
        question_type = cleaned_data.get('question_type')
        choices_text = cleaned_data.get('choices_text')
        
        # Validate choices for choice-based questions
        if question_type in [QuestionType.SELECT, QuestionType.RADIO, QuestionType.CHECKBOX]:
            if not choices_text or not choices_text.strip():
                raise forms.ValidationError(
                    f'{question_type} questions must have at least one choice.'
                )
            
            # Check minimum choices
            choices_list = [choice.strip() for choice in choices_text.split('\n') if choice.strip()]
            if len(choices_list) < 2:
                raise forms.ValidationError(
                    f'{question_type} questions must have at least 2 choices.'
                )
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Set choices from choices_text
        choices_text = self.cleaned_data.get('choices_text')
        if choices_text and instance.question_type in [QuestionType.SELECT, QuestionType.RADIO, QuestionType.CHECKBOX]:
            instance.set_choices_from_text(choices_text)
        elif instance.question_type not in [QuestionType.SELECT, QuestionType.RADIO, QuestionType.CHECKBOX]:
            instance.choices = []
        
        if commit:
            instance.save()
        return instance


# Formset for managing questions within a template
QuestionFormSet = inlineformset_factory(
    Template,
    Question,
    form=QuestionForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)


class TemplateSearchForm(forms.Form):
    """
    Form for searching and filtering templates
    """
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search templates by title or description'
        })
    )
    
    status = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All Statuses'),
            ('active', 'Active Only'),
            ('inactive', 'Inactive Only'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )