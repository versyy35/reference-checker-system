from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Count, Case, When
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .models import Form, FormStatus
from referees.models import Referee
from form_templates.models import Template
from .forms import FormAssignmentForm, BulkAssignmentForm


class FormAssignmentListView(LoginRequiredMixin, ListView):
    """
    Display list of all form assignments with search and filtering
    """
    model = Form
    template_name = 'forms/list.html'
    context_object_name = 'form_assignments'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Form.objects.select_related('template', 'referee').order_by('-created_at')
        
        # Search functionality
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(template__title__icontains=search_query) |
                Q(referee__name__icontains=search_query) |
                Q(referee__email__icontains=search_query) |
                Q(referee__applicant_name__icontains=search_query)
            )
        
        # Filter by status
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by template
        template_filter = self.request.GET.get('template')
        if template_filter:
            queryset = queryset.filter(template_id=template_filter)
        
        # Filter by referee
        referee_filter = self.request.GET.get('referee')
        if referee_filter:
            queryset = queryset.filter(referee_id=referee_filter)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['template_filter'] = self.request.GET.get('template', '')
        context['referee_filter'] = self.request.GET.get('referee', '')
        
        # Statistics
        context['total_assignments'] = Form.objects.count()
        context['pending_assignments'] = Form.objects.filter(status=FormStatus.PENDING).count()
        context['completed_assignments'] = Form.objects.filter(status=FormStatus.COMPLETED).count()
        
        # Filter options
        context['templates'] = Template.objects.filter(is_active=True).order_by('title')
        context['referees'] = Referee.objects.filter(is_active=True).order_by('name')
        context['status_choices'] = FormStatus.choices
        
        return context


class FormAssignmentCreateView(LoginRequiredMixin, CreateView):
    """
    Create a new form assignment (assign template to referee)
    """
    model = Form
    form_class = FormAssignmentForm
    template_name = 'forms/create.html'
    success_url = reverse_lazy('forms:list')
    
    def form_valid(self, form):
        template = form.cleaned_data['template']
        referee = form.cleaned_data['referee']
        send_email = form.cleaned_data.get('send_email', True)
        
        # Check if assignment already exists
        existing = Form.objects.filter(template=template, referee=referee).first()
        if existing:
            messages.error(
                self.request, 
                f'❌ "{template.title}" is already assigned to {referee.name}. '
                f'Status: {existing.get_status_display()}'
            )
            return self.form_invalid(form)
        
        # Create the assignment
        with transaction.atomic():
            self.object = form.save()
            
            # Send email notification if requested
            if send_email:
                try:
                    self.send_notification_email(self.object)
                    messages.success(
                        self.request, 
                        f'✅ Form "{template.title}" assigned to {referee.name} successfully! '
                        f'Notification email sent to {referee.email}.'
                    )
                except Exception as e:
                    messages.warning(
                        self.request, 
                        f'✅ Form assigned successfully, but email notification failed: {str(e)}'
                    )
            else:
                messages.success(
                    self.request, 
                    f'✅ Form "{template.title}" assigned to {referee.name} successfully!'
                )
        
        return redirect(self.success_url)
    
    def send_notification_email(self, form_assignment):
        """Send email notification to referee"""
        subject = f'Reference Request - {form_assignment.template.title}'
        
        # Render email template
        html_message = render_to_string('emails/form_assignment.html', {
            'form_assignment': form_assignment,
            'access_url': form_assignment.generate_access_url(
                base_url=self.request.build_absolute_uri('/')[:-1]
            ),
            'site_name': 'HR Reference Checker - HELP International School'
        })
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[form_assignment.referee.email],
            fail_silently=False,
        )
    
    def form_invalid(self, form):
        messages.error(self.request, '❌ Please correct the errors below.')
        return super().form_invalid(form)


class BulkAssignmentCreateView(LoginRequiredMixin, CreateView):
    """
    Create multiple form assignments at once
    """
    form_class = BulkAssignmentForm
    template_name = 'forms/bulk_create.html'
    success_url = reverse_lazy('forms:list')
    
    def get_form_kwargs(self):
        """Remove 'instance' from kwargs since BulkAssignmentForm is not a ModelForm"""
        kwargs = super().get_form_kwargs()
        kwargs.pop('instance', None)  # Remove instance if it exists
        return kwargs
    
    def form_valid(self, form):
        template = form.cleaned_data['template']
        referees = form.cleaned_data['referees']
        send_email = form.cleaned_data.get('send_email', True)
        
        created_count = 0
        skipped_count = 0
        email_errors = 0
        
        with transaction.atomic():
            for referee in referees:
                # Check if assignment already exists
                existing = Form.objects.filter(template=template, referee=referee).first()
                if existing:
                    skipped_count += 1
                    continue
                
                # Create assignment
                assignment = Form.objects.create(template=template, referee=referee)
                created_count += 1
                
                # Send email notification
                if send_email:
                    try:
                        self.send_notification_email(assignment)
                    except Exception:
                        email_errors += 1
        
        # Create success message
        message_parts = [f'✅ {created_count} form(s) assigned successfully!']
        if skipped_count > 0:
            message_parts.append(f'{skipped_count} assignment(s) skipped (already exist).')
        if email_errors > 0:
            message_parts.append(f'{email_errors} email notification(s) failed.')
        
        messages.success(self.request, ' '.join(message_parts))
        return redirect(self.success_url)
    
    def send_notification_email(self, form_assignment):
        """Send email notification to referee"""
        subject = f'Reference Request - {form_assignment.template.title}'
        
        html_message = render_to_string('emails/form_assignment.html', {
            'form_assignment': form_assignment,
            'access_url': form_assignment.generate_access_url(
                base_url=self.request.build_absolute_uri('/')[:-1]
            ),
            'site_name': 'HR Reference Checker - HELP International School'
        })
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[form_assignment.referee.email],
            fail_silently=False,
        )


class FormAssignmentDetailView(LoginRequiredMixin, DetailView):
    """
    Display form assignment details and access information
    """
    model = Form
    template_name = 'forms/detail.html'
    context_object_name = 'assignment'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['access_url'] = self.object.generate_access_url(
            base_url=self.request.build_absolute_uri('/')[:-1]
        )
        context['is_expired'] = self.object.is_expired()
        return context


class FormAssignmentUpdateView(LoginRequiredMixin, UpdateView):
    """
    Update form assignment (mainly for resending emails or changing status)
    """
    model = Form
    template_name = 'forms/edit.html'
    fields = ['status']
    success_url = reverse_lazy('forms:list')
    
    def form_valid(self, form):
        messages.success(
            self.request, 
            f'✅ Assignment for {self.object.referee.name} updated successfully!'
        )
        return super().form_valid(form)


class FormAssignmentDeleteView(LoginRequiredMixin, DeleteView):
    """
    Delete a form assignment
    """
    model = Form
    template_name = 'forms/delete.html'
    success_url = reverse_lazy('forms:list')
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        assignment_info = f'{self.object.template.title} - {self.object.referee.name}'
        
        # Prevent deletion of completed forms
        if self.object.status == FormStatus.COMPLETED:
            messages.error(
                request, 
                f'❌ Cannot delete completed assignment: {assignment_info}'
            )
            return redirect(self.success_url)
        
        # Perform deletion
        self.object.delete()
        messages.success(
            request, 
            f'🗑️ Assignment "{assignment_info}" has been deleted.'
        )
        
        return redirect(self.success_url)


class ResendNotificationView(LoginRequiredMixin, View):
    """
    Resend email notification for a form assignment
    """
    def get(self, request, *args, **kwargs):
        """Redirect GET requests to the detail page"""
        return redirect('forms:detail', pk=kwargs['pk'])
    
    def post(self, request, *args, **kwargs):
        assignment = get_object_or_404(Form, pk=kwargs['pk'])
        
        if assignment.status == FormStatus.COMPLETED:
            messages.error(request, '❌ Cannot resend notification for completed forms.')
            return redirect('forms:detail', pk=assignment.pk)
        
        try:
            # Send notification email
            subject = f'Reference Request - {assignment.template.title}'
            
            html_message = render_to_string('emails/form_assignment.html', {
                'form_assignment': assignment,
                'access_url': assignment.generate_access_url(
                    base_url=request.build_absolute_uri('/')[:-1]
                ),
                'site_name': 'HR Reference Checker - HELP International School',
                'is_reminder': True
            })
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject=f'Reminder: {subject}',
                message=plain_message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[assignment.referee.email],
                fail_silently=False,
            )
            
            messages.success(
                request, 
                f'✅ Reminder email sent to {assignment.referee.email} successfully!'
            )
        except Exception as e:
            messages.error(
                request, 
                f'❌ Failed to send reminder email: {str(e)}'
            )
        
        return redirect('forms:detail', pk=assignment.pk)


class FormAssignmentStatsView(LoginRequiredMixin, ListView):
    """
    Display form assignment statistics and analytics
    """
    model = Form
    template_name = 'forms/stats.html'
    context_object_name = 'assignments'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Overall statistics
        total_assignments = Form.objects.count()
        context['total_assignments'] = total_assignments
        context['pending_assignments'] = Form.objects.filter(status=FormStatus.PENDING).count()
        context['completed_assignments'] = Form.objects.filter(status=FormStatus.COMPLETED).count()
        
        if total_assignments > 0:
            context['completion_rate'] = round(
                (context['completed_assignments'] / total_assignments) * 100, 1
            )
        else:
            context['completion_rate'] = 0
        
        # Template statistics
        context['template_stats'] = Template.objects.annotate(
            total_assignments=Count('form'),
            completed_assignments=Count(
                Case(When(form__status=FormStatus.COMPLETED, then=1))
            )
        ).filter(total_assignments__gt=0).order_by('-total_assignments')
        
        # Referee statistics
        context['referee_stats'] = Referee.objects.annotate(
            total_assignments=Count('form'),
            completed_assignments=Count(
                Case(When(form__status=FormStatus.COMPLETED, then=1))
            )
        ).filter(total_assignments__gt=0).order_by('-total_assignments')
        
        return context