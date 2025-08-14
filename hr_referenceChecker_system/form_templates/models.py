from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.core.validators import MinLengthValidator
import json


class QuestionType(models.TextChoices):
    TEXT = 'TEXT', 'Text Input'
    TEXTAREA = 'TEXTAREA', 'Text Area'
    SELECT = 'SELECT', 'Single Choice'
    RADIO = 'RADIO', 'Radio Buttons'
    CHECKBOX = 'CHECKBOX', 'Multiple Choice'
    RATING = 'RATING', 'Rating Scale'
    DATE = 'DATE', 'Date'
    EMAIL = 'EMAIL', 'Email'
    PHONE = 'PHONE', 'Phone Number'


class Template(models.Model):
    """
    Model for reference form templates
    """
    title = models.CharField(max_length=255, validators=[MinLengthValidator(3)])
    description = models.TextField(blank=True, help_text="Brief description of this template")
    instructions = models.TextField(
        blank=True, 
        help_text="Instructions shown to referees before filling the form"
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Form Template'
        verbose_name_plural = 'Form Templates'
    
    def __str__(self):
        return self.title
    
    def get_questions_count(self):
        """Get the number of questions in this template"""
        return self.questions.count()
    
    def get_assigned_forms_count(self):
        """Get the number of forms assigned using this template"""
        return self.form_set.count()
    
    def get_questions(self):
        """Get all questions for this template ordered by order"""
        return self.questions.all().order_by('order')
    
    def add_question(self, question_data):
        """Add a question to this template"""
        # Auto-assign order if not provided
        if 'order' not in question_data:
            last_question = self.questions.order_by('-order').first()
            question_data['order'] = (last_question.order + 1) if last_question else 1
        
        return Question.objects.create(template=self, **question_data)
    
    def remove_question(self, question_id):
        """Remove a question from this template"""
        self.questions.filter(id=question_id).delete()
    
    def duplicate(self, new_title=None, new_user=None):
        """Create a duplicate of this template with all its questions"""
        if not new_title:
            new_title = f"{self.title} (Copy)"
        
        # Create new template
        new_template = Template.objects.create(
            title=new_title,
            description=self.description,
            instructions=self.instructions,
            created_by=new_user or self.created_by,
            is_active=False  # Start as inactive
        )
        
        # Duplicate all questions
        for question in self.questions.all():
            question.duplicate(new_template)
        
        return new_template
    
    # Keep your existing clone method for backward compatibility
    def clone(self, new_title=None):
        """Legacy method - use duplicate instead"""
        return self.duplicate(new_title)


class Question(models.Model):
    """
    Model for individual questions within a template
    Combines the flexibility of your polymorphic approach with the simplicity of a single model
    """
    template = models.ForeignKey(Template, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField(validators=[MinLengthValidator(5)])
    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        default=QuestionType.TEXT
    )
    is_required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    
    # For choice-based questions (SELECT, RADIO, CHECKBOX)
    choices = models.JSONField(
        default=list, 
        blank=True,
        help_text="List of choices for select/radio/checkbox questions"
    )
    
    # For rating questions
    rating_scale = models.PositiveIntegerField(
        default=5,
        help_text="Maximum rating value (e.g., 5 for 1-5 scale)"
    )
    rating_labels = models.JSONField(
        default=dict,
        blank=True,
        help_text="Labels for rating scale (e.g., {'1': 'Poor', '5': 'Excellent'})"
    )
    
    # Text question settings (from your TextQuestion)
    max_length = models.IntegerField(null=True, blank=True)
    placeholder = models.CharField(max_length=255, blank=True)
    
    # Help text for the question
    help_text = models.TextField(
        blank=True,
        help_text="Additional help text shown below the question"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = 'Template Question'
        verbose_name_plural = 'Template Questions'
    
    def __str__(self):
        return f"{self.template.title} - Q{self.order}: {self.question_text[:50]}"
    
    # Keep your validation methods
    def validate_answer(self, answer):
        """Validate if the provided answer is acceptable"""
        if self.question_type == QuestionType.TEXT or self.question_type == QuestionType.TEXTAREA:
            return self._validate_text_answer(answer)
        elif self.question_type in [QuestionType.SELECT, QuestionType.RADIO]:
            return self._validate_single_choice_answer(answer)
        elif self.question_type == QuestionType.CHECKBOX:
            return self._validate_multiple_choice_answer(answer)
        elif self.question_type == QuestionType.RATING:
            return self._validate_rating_answer(answer)
        elif self.question_type == QuestionType.EMAIL:
            return self._validate_email_answer(answer)
        elif self.question_type == QuestionType.PHONE:
            return self._validate_phone_answer(answer)
        elif self.question_type == QuestionType.DATE:
            return self._validate_date_answer(answer)
        else:
            return True, ""
    
    def _validate_text_answer(self, answer):
        """Validate text answer"""
        if self.is_required and not answer.strip():
            return False, "This field is required"
        if self.max_length and len(answer) > self.max_length:
            return False, f"Answer must be {self.max_length} characters or less"
        return True, ""
    
    def _validate_single_choice_answer(self, answer):
        """Validate single choice answer"""
        if self.is_required and not answer:
            return False, "This field is required"
        if answer and answer not in self.get_choices_list():
            return False, "Invalid option selected"
        return True, ""
    
    def _validate_multiple_choice_answer(self, answer):
        """Validate multiple choice answer"""
        if self.is_required and not answer:
            return False, "This field is required"
        
        if isinstance(answer, str):
            answer = [answer]
        
        for ans in answer:
            if ans not in self.get_choices_list():
                return False, "Invalid option selected"
        return True, ""
    
    def _validate_rating_answer(self, answer):
        """Validate rating answer"""
        if self.is_required and answer is None:
            return False, "This field is required"
        
        try:
            rating = int(answer)
            if rating < 1 or rating > self.rating_scale:
                return False, f"Rating must be between 1 and {self.rating_scale}"
        except (ValueError, TypeError):
            return False, "Invalid rating value"
        
        return True, ""
    
    def _validate_email_answer(self, answer):
        """Validate email answer"""
        if self.is_required and not answer.strip():
            return False, "This field is required"
        if answer and '@' not in answer:
            return False, "Please enter a valid email address"
        return True, ""
    
    def _validate_phone_answer(self, answer):
        """Validate phone answer"""
        if self.is_required and not answer.strip():
            return False, "This field is required"
        # Basic phone validation - you can enhance this
        if answer and not any(char.isdigit() for char in answer):
            return False, "Please enter a valid phone number"
        return True, ""
    
    def _validate_date_answer(self, answer):
        """Validate date answer"""
        if self.is_required and not answer:
            return False, "This field is required"
        # Django will handle date validation in forms
        return True, ""
    
    # Keep your HTML rendering methods
    def render_html(self):
        """Render HTML for this question"""
        if self.question_type == QuestionType.TEXT:
            return self._render_text_input()
        elif self.question_type == QuestionType.TEXTAREA:
            return self._render_textarea()
        elif self.question_type == QuestionType.SELECT:
            return self._render_select()
        elif self.question_type == QuestionType.RADIO:
            return self._render_radio()
        elif self.question_type == QuestionType.CHECKBOX:
            return self._render_checkbox()
        elif self.question_type == QuestionType.RATING:
            return self._render_rating()
        elif self.question_type == QuestionType.EMAIL:
            return self._render_email_input()
        elif self.question_type == QuestionType.PHONE:
            return self._render_phone_input()
        elif self.question_type == QuestionType.DATE:
            return self._render_date_input()
        else:
            return self._render_text_input()
    
    def _render_text_input(self):
        """Render text input"""
        required = "required" if self.is_required else ""
        placeholder = f'placeholder="{self.placeholder}"' if self.placeholder else ""
        maxlength = f'maxlength="{self.max_length}"' if self.max_length else ""
        return f'<input type="text" name="question_{self.id}" {required} {placeholder} {maxlength} class="form-control">'
    
    def _render_textarea(self):
        """Render textarea"""
        required = "required" if self.is_required else ""
        placeholder = f'placeholder="{self.placeholder}"' if self.placeholder else ""
        maxlength = f'maxlength="{self.max_length}"' if self.max_length else ""
        return f'<textarea name="question_{self.id}" {required} {placeholder} {maxlength} class="form-control" rows="4"></textarea>'
    
    def _render_select(self):
        """Render select dropdown"""
        required = "required" if self.is_required else ""
        html = f'<select name="question_{self.id}" {required} class="form-select">'
        if not self.is_required:
            html += '<option value="">-- Select an option --</option>'
        for option in self.get_choices_list():
            html += f'<option value="{option}">{option}</option>'
        html += '</select>'
        return html
    
    def _render_radio(self):
        """Render radio buttons"""
        required = "required" if self.is_required else ""
        html = ""
        for i, option in enumerate(self.get_choices_list()):
            html += f'''
            <div class="form-check">
                <input class="form-check-input" type="radio" 
                       name="question_{self.id}" value="{option}" id="q{self.id}_opt{i}" {required}>
                <label class="form-check-label" for="q{self.id}_opt{i}">
                    {option}
                </label>
            </div>
            '''
        return html
    
    def _render_checkbox(self):
        """Render checkboxes"""
        html = ""
        for i, option in enumerate(self.get_choices_list()):
            html += f'''
            <div class="form-check">
                <input class="form-check-input" type="checkbox" 
                       name="question_{self.id}" value="{option}" id="q{self.id}_opt{i}">
                <label class="form-check-label" for="q{self.id}_opt{i}">
                    {option}
                </label>
            </div>
            '''
        return html
    
    def _render_rating(self):
        """Render rating scale"""
        required = "required" if self.is_required else ""
        html = f'<div class="rating-scale">'
        for i in range(1, self.rating_scale + 1):
            label = self.rating_labels.get(str(i), str(i))
            html += f'''
            <div class="form-check form-check-inline">
                <input class="form-check-input" type="radio" 
                       name="question_{self.id}" value="{i}" id="q{self.id}_rate{i}" {required}>
                <label class="form-check-label" for="q{self.id}_rate{i}">
                    {label}
                </label>
            </div>
            '''
        html += f'</div><small class="form-text text-muted">Scale: 1 (Low) - {self.rating_scale} (High)</small>'
        return html
    
    def _render_email_input(self):
        """Render email input"""
        required = "required" if self.is_required else ""
        placeholder = f'placeholder="{self.placeholder or "email@example.com"}"'
        return f'<input type="email" name="question_{self.id}" {required} {placeholder} class="form-control">'
    
    def _render_phone_input(self):
        """Render phone input"""
        required = "required" if self.is_required else ""
        placeholder = f'placeholder="{self.placeholder or "+60123456789"}"'
        return f'<input type="tel" name="question_{self.id}" {required} {placeholder} class="form-control">'
    
    def _render_date_input(self):
        """Render date input"""
        required = "required" if self.is_required else ""
        return f'<input type="date" name="question_{self.id}" {required} class="form-control">'
    
    # Utility methods
    def get_choices_list(self):
        """Get choices as a list (for form rendering)"""
        if isinstance(self.choices, list):
            return self.choices
        return []
    
    def set_choices_from_text(self, choices_text):
        """Set choices from newline-separated text"""
        if choices_text:
            choices_list = [choice.strip() for choice in choices_text.split('\n') if choice.strip()]
            self.choices = choices_list
        else:
            self.choices = []
    
    def get_choices_as_text(self):
        """Get choices as newline-separated text (for form editing)"""
        if isinstance(self.choices, list):
            return '\n'.join(self.choices)
        return ''
    
    def duplicate(self, new_template):
        """Create a duplicate of this question for a new template"""
        return Question.objects.create(
            template=new_template,
            question_text=self.question_text,
            question_type=self.question_type,
            is_required=self.is_required,
            order=self.order,
            choices=self.choices.copy() if self.choices else [],
            rating_scale=self.rating_scale,
            rating_labels=self.rating_labels.copy() if self.rating_labels else {},
            max_length=self.max_length,
            placeholder=self.placeholder,
            help_text=self.help_text
        )
    
    # Legacy methods for backward compatibility with your existing code
    def add_option(self, option):
        """Add an option to this question (for choice-based questions)"""
        if self.question_type in [QuestionType.SELECT, QuestionType.RADIO, QuestionType.CHECKBOX]:
            if option not in self.choices:
                self.choices.append(option)
                self.save()
    
    def remove_option(self, option):
        """Remove an option from this question"""
        if self.question_type in [QuestionType.SELECT, QuestionType.RADIO, QuestionType.CHECKBOX]:
            if option in self.choices:
                self.choices.remove(option)
                self.save()
    
    def save(self, *args, **kwargs):
        # Auto-assign order if not set
        if not self.order and self.template_id:
            last_question = Question.objects.filter(template=self.template).order_by('-order').first()
            self.order = (last_question.order + 1) if last_question else 1
        super().save(*args, **kwargs)