# responses/views.py - Clean Version without ReportLab imports

from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import View, TemplateView, ListView, DetailView
from django.contrib import messages
from django.http import Http404, JsonResponse, HttpResponse
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Count, Prefetch

# Simple imports only - no ReportLab
from io import BytesIO
import json

from forms.models import Form, FormStatus
from form_templates.models import Template  # Changed from FormTemplate to Template
from responses.models import Response, Answer

User = get_user_model()


class ResponseListView(LoginRequiredMixin, ListView):
    """
    List view showing all templates that have received responses
    """
    model = Response
    template_name = 'responses/list.html'
    context_object_name = 'responses'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Response.objects.select_related(
            'form__template',
            'form__referee'
        ).order_by('-submitted_at')
        
        # Apply filters
        search_query = self.request.GET.get('search', '').strip()
        template_filter = self.request.GET.get('template', '').strip()
        date_from = self.request.GET.get('date_from', '').strip()
        date_to = self.request.GET.get('date_to', '').strip()
        
        if search_query:
            queryset = queryset.filter(
                Q(form__template__title__icontains=search_query) |
                Q(form__referee__name__icontains=search_query) |
                Q(form__referee__email__icontains=search_query) |
                Q(form__referee__applicant_name__icontains=search_query)
            )
        
        if template_filter:
            queryset = queryset.filter(form__template_id=template_filter)
        
        if date_from:
            try:
                from datetime import datetime
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
                queryset = queryset.filter(submitted_at__date__gte=date_from_obj.date())
            except ValueError:
                pass
        
        if date_to:
            try:
                from datetime import datetime
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
                queryset = queryset.filter(submitted_at__date__lte=date_to_obj.date())
            except ValueError:
                pass
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter values for the template
        context['search_query'] = self.request.GET.get('search', '')
        context['template_filter'] = self.request.GET.get('template', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        
        # Get all templates for filter dropdown
        context['templates'] = Template.objects.filter(
            id__in=Response.objects.values_list('form__template_id', flat=True).distinct()
        ).order_by('title')
        
        # Get statistics
        total_responses = Response.objects.count()
        unique_templates = Response.objects.values('form__template').distinct().count()
        recent_responses = Response.objects.filter(
            submitted_at__date=timezone.now().date()
        ).count()
        
        context.update({
            'total_responses': total_responses,
            'unique_templates': unique_templates,
            'recent_responses': recent_responses,
        })
        
        return context


class ResponseDetailView(LoginRequiredMixin, DetailView):
    """
    Detailed view of a single response with all answers
    """
    model = Response
    template_name = 'responses/detail.html'
    context_object_name = 'response'
    
    def get_object(self):
        response = get_object_or_404(
            Response.objects.select_related(
                'form__template',
                'form__referee'
            ).prefetch_related('answer_set'),
            pk=self.kwargs['pk']
        )
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        response = self.get_object()
        
        # Get all questions from the template
        template_questions = response.form.template.questions.all().order_by('order')
        
        # Get all answers for this response
        answers = {answer.question_id: answer for answer in response.answer_set.all()}
        
        # Combine questions with their answers
        questions_with_answers = []
        for question in template_questions:
            answer = answers.get(question.id)
            questions_with_answers.append({
                'question': question,
                'answer': answer,
                'has_answer': answer is not None,
                'answer_value': answer.answer_value if answer else None
            })
        
        context['questions_with_answers'] = questions_with_answers
        context['template'] = response.form.template
        context['form'] = response.form
        context['referee'] = response.form.referee
        
        return context


class ResponseExportSimpleView(LoginRequiredMixin, View):
    """
    Export a single response to a simple text-based format
    """
    
    def get(self, request, pk):
        response = get_object_or_404(
            Response.objects.select_related(
                'form__template',
                'form__referee'
            ).prefetch_related('answer_set'),
            pk=pk
        )
        
        # Create simple text export
        content = self.generate_text_export(response)
        
        # Create response
        response_obj = HttpResponse(content, content_type='text/plain; charset=utf-8')
        filename = 'response_{}_{}_{}_{}.txt'.format(
            response.form.referee.name.replace(' ', '_'),
            response.form.template.title.replace(' ', '_'),
            response.submitted_at.strftime('%Y%m%d'),
            response.pk
        )
        response_obj['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
        
        return response_obj
    
    def generate_text_export(self, response):
        """Generate a simple text export of the response"""
        lines = []
        lines.append("=" * 80)
        lines.append("REFERENCE RESPONSE EXPORT")
        lines.append("=" * 80)
        lines.append("")
        
        # Response Information
        lines.append("RESPONSE INFORMATION")
        lines.append("-" * 40)
        lines.append("Template: {}".format(response.form.template.title))
        lines.append("Referee: {}".format(response.form.referee.name))
        lines.append("Email: {}".format(response.form.referee.email))
        lines.append("Applicant: {}".format(response.form.referee.applicant_name))
        lines.append("Relationship: {}".format(response.form.referee.relationship))
        lines.append("Submitted: {}".format(response.submitted_at.strftime('%B %d, %Y at %H:%M')))
        lines.append("Response ID: {}".format(response.pk))
        lines.append("")
        
        # Template Description
        if response.form.template.description:
            lines.append("TEMPLATE DESCRIPTION")
            lines.append("-" * 40)
            lines.append(response.form.template.description)
            lines.append("")
        
        # Questions and Answers
        lines.append("QUESTIONS AND RESPONSES")
        lines.append("-" * 40)
        
        # Get questions with answers
        template_questions = response.form.template.questions.all().order_by('order')
        answers = {answer.question_id: answer for answer in response.answer_set.all()}
        
        for i, question in enumerate(template_questions, 1):
            answer = answers.get(question.id)
            
            lines.append("Question {}: {}".format(i, question.question_text))
            if question.is_required:
                lines.append("(Required)")
            lines.append("")
            
            if answer:
                lines.append("Answer: {}".format(answer.answer_value))
            else:
                lines.append("Answer: [No response provided]")
            
            lines.append("")
            lines.append("-" * 40)
            lines.append("")
        
        # Footer
        lines.append("Export generated on: {}".format(timezone.now().strftime('%B %d, %Y at %H:%M')))
        lines.append("=" * 80)
        
        return '\n'.join(lines)


class BulkExportSimpleView(LoginRequiredMixin, View):
    """
    Export multiple responses to a simple text-based format
    """
    
    def post(self, request):
        response_ids = request.POST.getlist('response_ids')
        
        if not response_ids:
            messages.error(request, 'Please select at least one response to export.')
            return redirect('responses:list')
        
        responses = Response.objects.filter(
            id__in=response_ids
        ).select_related(
            'form__template',
            'form__referee'
        ).prefetch_related('answer_set').order_by('-submitted_at')
        
        if not responses:
            messages.error(request, 'No valid responses found for export.')
            return redirect('responses:list')
        
        # Create combined text export
        content = self.generate_bulk_text_export(responses)
        
        # Create response
        response_obj = HttpResponse(content, content_type='text/plain; charset=utf-8')
        filename = 'bulk_responses_export_{}.txt'.format(
            timezone.now().strftime('%Y%m%d_%H%M')
        )
        response_obj['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
        
        return response_obj
    
    def generate_bulk_text_export(self, responses):
        """Generate a bulk text export of multiple responses"""
        lines = []
        lines.append("=" * 100)
        lines.append("BULK REFERENCE RESPONSES EXPORT")
        lines.append("=" * 100)
        lines.append("")
        lines.append("Generated on: {}".format(timezone.now().strftime('%B %d, %Y at %H:%M')))
        lines.append("Total Responses: {}".format(len(responses)))
        lines.append("")
        
        for response_num, response in enumerate(responses, 1):
            lines.append("+" * 100)
            lines.append("RESPONSE {} OF {}".format(response_num, len(responses)))
            lines.append("+" * 100)
            lines.append("")
            
            # Response Information
            lines.append("RESPONSE INFORMATION")
            lines.append("-" * 50)
            lines.append("Template: {}".format(response.form.template.title))
            lines.append("Referee: {}".format(response.form.referee.name))
            lines.append("Email: {}".format(response.form.referee.email))
            lines.append("Applicant: {}".format(response.form.referee.applicant_name))
            lines.append("Submitted: {}".format(response.submitted_at.strftime('%B %d, %Y at %H:%M')))
            lines.append("")
            
            # Questions and Answers
            lines.append("QUESTIONS AND RESPONSES")
            lines.append("-" * 50)
            
            template_questions = response.form.template.questions.all().order_by('order')
            answers = {answer.question_id: answer for answer in response.answer_set.all()}
            
            for i, question in enumerate(template_questions, 1):
                answer = answers.get(question.id)
                
                lines.append("Q{}: {}".format(i, question.question_text))
                if answer:
                    lines.append("A{}: {}".format(i, answer.answer_value))
                else:
                    lines.append("A{}: [No response]".format(i))
                lines.append("")
            
            if response_num < len(responses):
                lines.append("")
                lines.append("")
        
        lines.append("=" * 100)
        lines.append("END OF EXPORT")
        lines.append("=" * 100)
        
        return '\n'.join(lines)


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
        if hasattr(form_assignment, 'is_expired') and form_assignment.is_expired():
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
            return redirect("{}?show_form=true".format(request.path))
        
        elif action == 'submit':
            # Process the actual form submission
            return self.process_form_submission(request, form_assignment, *args, **kwargs)
        
        return self.get(request, *args, **kwargs)
    
    def process_form_submission(self, request, form_assignment, *args, **kwargs):
        """Process the actual form submission with answers"""
        questions = form_assignment.template.questions.all()
        answers_data = {}
        errors = []
        
        print("Processing submission for {} questions".format(questions.count()))
        
        # Validate and collect answers
        for question in questions:
            field_name = 'question_{}'.format(question.id)
            answer = request.POST.get(field_name, '').strip()
            
            print("Question {} ({}): '{}'".format(question.id, question.question_type, answer))
            
            # Check if required question is answered
            if question.is_required and not answer:
                errors.append('Question "{}" is required.'.format(question.question_text))
                continue
            
            # Validate based on question type
            if question.question_type == 'EMAIL' and answer:
                import re
                if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', answer):
                    errors.append('Please enter a valid email address for "{}".'.format(question.question_text))
                    continue
            
            elif question.question_type == 'NUMBER' and answer:
                try:
                    float(answer)
                except ValueError:
                    errors.append('Please enter a valid number for "{}".'.format(question.question_text))
                    continue
            
            answers_data[question.id] = answer
        
        # If there are errors, return to form with errors
        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect("{}?show_form=true".format(request.path))
        
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
            messages.error(request, 'An error occurred while saving your responses: {}'.format(str(e)))
            return redirect("{}?show_form=true".format(request.path))
        
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
                    message="{} submitted {} for {}".format(
                        form_assignment.referee.name,
                        form_assignment.template.title,
                        form_assignment.referee.applicant_name
                    ),
                    notification_type=NotificationType.SUCCESS,
                    icon='fas fa-check-circle',
                    related_object=form_assignment
                )
            
            print("✅ Created notifications for {} staff members".format(staff_users.count()))
            
        except Exception as e:
            print("❌ Error creating notifications: {}".format(e))
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