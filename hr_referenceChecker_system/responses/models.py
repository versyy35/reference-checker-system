from django.db import models
from django.utils import timezone
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO
import json


class Response(models.Model):
    """
    Model for storing form responses
    """
    form = models.OneToOneField('forms.Form', on_delete=models.CASCADE)
    submitted_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, help_text="Additional data like IP address, browser info, etc.")
    
    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'Form Response'
        verbose_name_plural = 'Form Responses'
    
    def __str__(self):
        return f"Response to {self.form.template.title} by {self.form.referee.name}"
    
    def get_answers(self):
        """Get all answers for this response"""
        return self.answer_set.all().order_by('question_id')
    
    def export_to_pdf(self):
        """Export this response to PDF format"""
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        
        # Title
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, height - 50, f"Reference Check: {self.form.template.title}")
        
        # Referee info
        p.setFont("Helvetica", 12)
        y_position = height - 100
        p.drawString(50, y_position, f"Referee: {self.form.referee.name}")
        y_position -= 20
        p.drawString(50, y_position, f"Email: {self.form.referee.email}")
        y_position -= 20
        p.drawString(50, y_position, f"Applicant: {self.form.referee.applicant_name}")
        y_position -= 20
        p.drawString(50, y_position, f"Submitted: {self.submitted_at.strftime('%Y-%m-%d %H:%M')}")
        y_position -= 40
        
        # Answers
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y_position, "Responses:")
        y_position -= 30
        
        p.setFont("Helvetica", 10)
        for answer in self.get_answers():
            # Question
            p.setFont("Helvetica-Bold", 10)
            question_text = answer.get_question_text()
            if len(question_text) > 80:
                question_text = question_text[:80] + "..."
            p.drawString(50, y_position, f"Q: {question_text}")
            y_position -= 15
            
            # Answer
            p.setFont("Helvetica", 10)
            answer_text = answer.answer_value
            if len(answer_text) > 100:
                answer_text = answer_text[:100] + "..."
            p.drawString(70, y_position, f"A: {answer_text}")
            y_position -= 25
            
            # Check if we need a new page
            if y_position < 100:
                p.showPage()
                y_position = height - 50
        
        p.save()
        buffer.seek(0)
        return buffer


class Answer(models.Model):
    """
    Model for storing individual answers to questions
    """
    response = models.ForeignKey(Response, on_delete=models.CASCADE)
    question_id = models.IntegerField(help_text="ID of the question this answers")
    question_type = models.CharField(max_length=50, help_text="Type of question (text, mcq, rating)")
    answer_value = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['question_id']
        unique_together = ['response', 'question_id']  # One answer per question per response
    
    def __str__(self):
        return f"Answer to question {self.question_id}"
    
    def get_question_text(self):
        """Get the text of the question this answer belongs to"""
        # This is a helper method to get question text for display
        # In a real implementation, you might want to store question text
        # to preserve it even if the original question is modified/deleted
        try:
            template = self.response.form.template
            questions = template.get_questions()
            for question in questions:
                if question.id == self.question_id:
                    return question.question_text
            return f"Question {self.question_id}"
        except:
            return f"Question {self.question_id}"
    
    def validate(self):
        """Validate this answer against the original question"""
        try:
            template = self.response.form.template
            questions = template.get_questions()
            for question in questions:
                if question.id == self.question_id:
                    is_valid, error_message = question.validate_answer(self.answer_value)
                    return is_valid, error_message
            return False, "Question not found"
        except Exception as e:
            return False, str(e)