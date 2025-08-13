from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
import json


class Template(models.Model):
    """
    Model for form templates
    """
    title = models.CharField(max_length=255)
    description = models.TextField()
    #created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Form Template'
        verbose_name_plural = 'Form Templates'
    
    def __str__(self):
        return self.title
    
    def add_question(self, question_data):
        """Add a question to this template"""
        question_type = question_data.get('question_type')
        if question_type == 'text':
            return TextQuestion.objects.create(template=self, **question_data)
        elif question_type == 'mcq':
            return MCQQuestion.objects.create(template=self, **question_data)
        elif question_type == 'rating':
            return RatingQuestion.objects.create(template=self, **question_data)
        else:
            raise ValueError(f"Unknown question type: {question_type}")
    
    def remove_question(self, question_id):
        """Remove a question from this template"""
        self.question_set.filter(id=question_id).delete()
    
    def get_questions(self):
        """Get all questions for this template ordered by index"""
        questions = []
        questions.extend(self.textquestion_set.all())
        questions.extend(self.mcqquestion_set.all())
        questions.extend(self.ratingquestion_set.all())
        return sorted(questions, key=lambda x: x.order_index)
    
    def clone(self, new_title=None):
        """Create a copy of this template"""
        new_template = Template.objects.create(
            title=new_title or f"{self.title} (Copy)",
            description=self.description,
            created_by=self.created_by
        )
        
        # Copy all questions
        for question in self.get_questions():
            question.clone_to_template(new_template)
        
        return new_template


class Question(models.Model):
    """
    Abstract base class for all question types
    """
    template = models.ForeignKey(Template, on_delete=models.CASCADE)
    question_text = models.TextField()
    question_type = models.CharField(max_length=50)
    is_required = models.BooleanField(default=False)
    order_index = models.IntegerField()
    
    class Meta:
        abstract = True
        ordering = ['order_index']
    
    def validate_answer(self, answer):
        """Validate if the provided answer is acceptable"""
        raise NotImplementedError("Subclasses must implement validate_answer method")
    
    def render_html(self):
        """Render HTML for this question"""
        raise NotImplementedError("Subclasses must implement render_html method")


class TextQuestion(Question):
    """
    Text input question (short or long text)
    """
    max_length = models.IntegerField(null=True, blank=True)
    placeholder = models.CharField(max_length=255, blank=True)
    
    def save(self, *args, **kwargs):
        self.question_type = 'text'
        super().save(*args, **kwargs)
    
    def validate_answer(self, answer):
        """Validate text answer"""
        if self.is_required and not answer.strip():
            return False, "This field is required"
        if self.max_length and len(answer) > self.max_length:
            return False, f"Answer must be {self.max_length} characters or less"
        return True, ""
    
    def render_html(self):
        """Render HTML for text question"""
        input_type = "textarea" if self.max_length and self.max_length > 100 else "text"
        required = "required" if self.is_required else ""
        placeholder = f'placeholder="{self.placeholder}"' if self.placeholder else ""
        maxlength = f'maxlength="{self.max_length}"' if self.max_length else ""
        
        if input_type == "textarea":
            return f'<textarea name="question_{self.id}" {required} {placeholder} {maxlength} class="form-control"></textarea>'
        else:
            return f'<input type="text" name="question_{self.id}" {required} {placeholder} {maxlength} class="form-control">'
    
    def __str__(self):
        return f"Text: {self.question_text[:50]}..."


class MCQQuestion(Question):
    """
    Multiple choice question
    """
    options = models.JSONField(default=list)  # Store as JSON array
    allow_multiple = models.BooleanField(default=False)
    
    def save(self, *args, **kwargs):
        self.question_type = 'mcq'
        super().save(*args, **kwargs)
    
    def validate_answer(self, answer):
        """Validate MCQ answer"""
        if self.is_required and not answer:
            return False, "This field is required"
        
        if isinstance(answer, str):
            answer = [answer]
        
        if not self.allow_multiple and len(answer) > 1:
            return False, "Only one option can be selected"
        
        for ans in answer:
            if ans not in self.options:
                return False, "Invalid option selected"
        
        return True, ""
    
    def render_html(self):
        """Render HTML for MCQ question"""
        input_type = "checkbox" if self.allow_multiple else "radio"
        required = "required" if self.is_required else ""
        
        html = ""
        for i, option in enumerate(self.options):
            html += f'''
            <div class="form-check">
                <input class="form-check-input" type="{input_type}" 
                       name="question_{self.id}" value="{option}" id="q{self.id}_opt{i}" {required}>
                <label class="form-check-label" for="q{self.id}_opt{i}">
                    {option}
                </label>
            </div>
            '''
        return html
    
    def add_option(self, option):
        """Add an option to this question"""
        if option not in self.options:
            self.options.append(option)
            self.save()
    
    def remove_option(self, option):
        """Remove an option from this question"""
        if option in self.options:
            self.options.remove(option)
            self.save()
    
    def __str__(self):
        return f"MCQ: {self.question_text[:50]}..."


class RatingQuestion(Question):
    """
    Rating scale question (1-5, 1-10, etc.)
    """
    min_value = models.IntegerField(default=1)
    max_value = models.IntegerField(default=5)
    scale_label = models.CharField(max_length=100, default="Rating")
    
    def save(self, *args, **kwargs):
        self.question_type = 'rating'
        super().save(*args, **kwargs)
    
    def validate_answer(self, answer):
        """Validate rating answer"""
        if self.is_required and answer is None:
            return False, "This field is required"
        
        try:
            rating = int(answer)
            if rating < self.min_value or rating > self.max_value:
                return False, f"Rating must be between {self.min_value} and {self.max_value}"
        except (ValueError, TypeError):
            return False, "Invalid rating value"
        
        return True, ""
    
    def render_html(self):
        """Render HTML for rating question"""
        required = "required" if self.is_required else ""
        
        html = f'<div class="rating-scale">'
        for i in range(self.min_value, self.max_value + 1):
            html += f'''
            <div class="form-check form-check-inline">
                <input class="form-check-input" type="radio" 
                       name="question_{self.id}" value="{i}" id="q{self.id}_rate{i}" {required}>
                <label class="form-check-label" for="q{self.id}_rate{i}">
                    {i}
                </label>
            </div>
            '''
        html += f'</div><small class="form-text text-muted">{self.scale_label}: {self.min_value} (Low) - {self.max_value} (High)</small>'
        return html
    
    def __str__(self):
        return f"Rating: {self.question_text[:50]}..."