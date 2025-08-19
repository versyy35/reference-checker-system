# Update responses/views.py - Add notification creation to form submission

from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import View, TemplateView
from django.contrib import messages
from django.http import Http404, JsonResponse
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import get_user_model

from forms.models import Form, FormStatus

User = get_user_model()


class PublicFormView(TemplateView):
    """
    Public view for referees to access and fill out their assigned forms
    """
    template_name = 'responses/public_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        token = kwargs.get('token')
        
        # Get the form assignment by token
        try:
            form_assignment = get_object_or_404(Form, unique_token=token)
        except Http404:
            context['error'] = 'invalid_token'
            return context
        
        # Check if form is already completed
        if form_assignment.status == FormStatus.COMPLETED:
            context['error'] = 'already_completed'
            context['form_assignment'] = form_assignment
            return context
        
        # Check if form has expired (optional - you can remove this if not needed)
        if form_assignment.is_expired():
            context['error'] = 'expired'
            context['form_assignment'] = form_assignment
            return context
        
        # Form is valid and can be filled
        context['form_assignment'] = form_assignment
        context['template'] = form_assignment.template
        context['referee'] = form_assignment.referee
        
        # Get all questions for this template using the correct relationship
        context['questions'] = form_assignment.template.questions.all().order_by('order')
        
        # Check if this is the form display (after clicking start)
        context['show_form'] = self.request.GET.get('show_form', False)
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle form submission"""
        token = kwargs.get('token')
        
        try:
            form_assignment = get_object_or_404(Form, unique_token=token)
        except Http404:
            messages.error(request, 'Invalid or expired form link.')
            return redirect('/')
        
        # Check if already completed
        if form_assignment.status == FormStatus.COMPLETED:
            messages.warning(request, 'This form has already been completed.')
            return self.get(request, *args, **kwargs)
        
        # Check what action is being performed
        action = request.POST.get('action', 'start')
        
        if action == 'start':
            # Just show the form with questions
            return redirect(f"{request.path}?show_form=true")
        
        elif action == 'submit':
            # Process the actual form submission
            return self.process_form_submission(request, form_assignment, *args, **kwargs)
        
        return self.get(request, *args, **kwargs)
    
    def process_form_submission(self, request, form_assignment, *args, **kwargs):
        """Process the actual form submission with answers"""
        from responses.models import Response, Answer
        
        questions = form_assignment.template.questions.all()
        answers_data = {}
        errors = []
        
        print(f"Processing submission for {questions.count()} questions")
        
        # Validate and collect answers
        for question in questions:
            field_name = f'question_{question.id}'
            answer = request.POST.get(field_name, '').strip()
            
            print(f"Question {question.id} ({question.question_type}): '{answer}'")
            
            # Check if required question is answered
            if question.is_required and not answer:
                errors.append(f'Question "{question.question_text}" is required.')
                continue
            
            # Validate based on question type
            if question.question_type == 'EMAIL' and answer:
                import re
                if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', answer):
                    errors.append(f'Please enter a valid email address for "{question.question_text}".')
                    continue
            
            elif question.question_type == 'NUMBER' and answer:
                try:
                    float(answer)
                except ValueError:
                    errors.append(f'Please enter a valid number for "{question.question_text}".')
                    continue
            
            answers_data[question.id] = answer
        
        # If there are errors, return to form with errors
        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect(f"{request.path}?show_form=true")
        
        # Save responses
        try:
            # Create Response record
            response = Response.objects.create(
                form=form_assignment,
                metadata={
                    'ip_address': self.get_client_ip(request),
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'submitted_via': 'web_form'
                }
            )
            
            # Create Answer records for each question
            for question_id, answer_value in answers_data.items():
                question = questions.get(id=question_id)
                Answer.objects.create(
                    response=response,
                    question_id=question_id,
                    question_type=question.question_type,
                    answer_value=answer_value
                )
            
            # Mark the form as completed
            form_assignment.mark_completed()
            
            # 🎯 CREATE NOTIFICATION FOR ALL ACTIVE USERS
            self.create_form_submission_notification(form_assignment)
            
            messages.success(request, 'Thank you! Your reference has been submitted successfully.')
            
        except Exception as e:
            messages.error(request, f'An error occurred while saving your responses: {str(e)}')
            return redirect(f"{request.path}?show_form=true")
        
        # Redirect to show completion message
        return self.get(request, *args, **kwargs)
    
    def create_form_submission_notification(self, form_assignment):
        """
        Create notifications for all active staff when a form is submitted
        """
        try:
            from core.models import Notification, NotificationType
            
            # Get all active staff users (you can customize this filter)
            staff_users = User.objects.filter(is_active=True, is_staff=True)
            
            for user in staff_users:
                Notification.create_notification(
                    user=user,
                    title="Form Submitted",
                    message=f"{form_assignment.referee.name} submitted {form_assignment.template.title} for {form_assignment.referee.applicant_name}",
                    notification_type=NotificationType.SUCCESS,
                    icon='fas fa-check-circle',
                    related_object=form_assignment
                )
            
            print(f"✅ Created notifications for {staff_users.count()} staff members")
            
        except Exception as e:
            print(f"❌ Error creating notifications: {e}")
            # Don't fail the form submission if notification creation fails
            pass
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip