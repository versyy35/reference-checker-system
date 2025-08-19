# forms/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db.models import Q
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib.auth import get_user_model

from .models import Form, FormStatus
from .forms import FormAssignmentForm, BulkAssignmentForm, FormAssignmentSearchForm, FormStatusUpdateForm
from referees.models import Referee
from form_templates.models import Template
from responses.models import Response

User = get_user_model()


class FormAssignmentListView(LoginRequiredMixin, ListView):
    """
    Display list of all form assignments with search and filtering
    """
    model = Form
    template_name = 'forms/list.html'
    context_object_name = 'form_assignments'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Form.objects.all().select_related('template', 'referee').order_by('-created_at')
        
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
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['template_filter'] = self.request.GET.get('template', '')
        context['total_assignments'] = Form.objects.count()
        context['pending_assignments'] = Form.objects.filter(status=FormStatus.PENDING).count()
        context['completed_assignments'] = Form.objects.filter(status=FormStatus.COMPLETED).count()
        context['status_choices'] = FormStatus.choices
        context['templates'] = Template.objects.filter(is_active=True).order_by('title')
        return context


class FormAssignmentCreateView(LoginRequiredMixin, CreateView):
    """
    Create a new form assignment (single assignment)
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
            
            # Create notification for form assignment
            self.create_assignment_notification(self.object, self.request.user)
            
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
    
    def create_assignment_notification(self, form_assignment, assigned_by_user):
        """
        Create notification when a form is assigned
        """
        try:
            from core.models import Notification, NotificationType
            
            # Create notification for the user who assigned the form
            Notification.create_notification(
                user=assigned_by_user,
                title="Form Assigned",
                message=f"Successfully assigned {form_assignment.template.title} to {form_assignment.referee.name} for {form_assignment.referee.applicant_name}",
                notification_type=NotificationType.INFO,
                icon='fas fa-paper-plane',
                related_object=form_assignment
            )
            
            print(f"✅ Created assignment notification for {assigned_by_user.username}")
            
        except Exception as e:
            print(f"❌ Error creating assignment notification: {e}")
            pass
    
    def send_notification_email(self, form_assignment):
        """
        Send email notification to referee (placeholder for now)
        """
        # TODO: Implement actual email sending
        print(f"📧 Email would be sent to {form_assignment.referee.email}")
        pass


class BulkAssignmentCreateView(LoginRequiredMixin, CreateView):
    """
    Create multiple form assignments at once
    """
    form_class = BulkAssignmentForm
    template_name = 'forms/bulk_create.html'
    success_url = reverse_lazy('forms:list')
    
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
            
            # Create notification for bulk assignment
            if created_count > 0:
                self.create_bulk_assignment_notification(template, created_count, self.request.user)
        
        # Create success message
        message_parts = [f'✅ {created_count} form(s) assigned successfully!']
        if skipped_count > 0:
            message_parts.append(f'{skipped_count} assignment(s) skipped (already exist).')
        if email_errors > 0:
            message_parts.append(f'{email_errors} email notification(s) failed.')
        
        messages.success(self.request, ' '.join(message_parts))
        return redirect(self.success_url)
    
    def create_bulk_assignment_notification(self, template, count, assigned_by_user):
        """
        Create notification for bulk assignment
        """
        try:
            from core.models import Notification, NotificationType
            
            Notification.create_notification(
                user=assigned_by_user,
                title="Bulk Assignment Complete",
                message=f"Successfully assigned {template.title} to {count} referee{'s' if count != 1 else ''}",
                notification_type=NotificationType.SUCCESS,
                icon='fas fa-users',
                related_object=template
            )
            
            print(f"✅ Created bulk assignment notification for {assigned_by_user.username}")
            
        except Exception as e:
            print(f"❌ Error creating bulk assignment notification: {e}")
            pass
    
    def send_notification_email(self, assignment):
        """
        Send email notification to referee (placeholder for now)
        """
        # TODO: Implement actual email sending
        print(f"📧 Email would be sent to {assignment.referee.email}")
        pass


class FormAssignmentDetailView(LoginRequiredMixin, DetailView):
    """
    Display form assignment details
    """
    model = Form
    template_name = 'forms/detail.html'
    context_object_name = 'assignment'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['access_url'] = self.object.generate_access_url()
        context['is_expired'] = self.object.is_expired()
        return context


class FormAssignmentUpdateView(LoginRequiredMixin, UpdateView):
    """
    Update form assignment status
    """
    model = Form
    form_class = FormStatusUpdateForm
    template_name = 'forms/edit.html'
    success_url = reverse_lazy('forms:list')
    
    def form_valid(self, form):
        assignment = form.save()
        messages.success(
            self.request, 
            f'✅ Assignment status updated successfully!'
        )
        return redirect('forms:detail', pk=assignment.pk)


class FormAssignmentDeleteView(LoginRequiredMixin, DeleteView):
    """
    Delete a form assignment
    """
    model = Form
    template_name = 'forms/delete.html'
    success_url = reverse_lazy('forms:list')
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        assignment_title = f"{self.object.template.title} → {self.object.referee.name}"
        
        # Perform deletion
        self.object.delete()
        
        messages.success(
            request, 
            f'🗑️ Assignment "{assignment_title}" has been permanently deleted.'
        )
        
        return redirect(self.success_url)


class ResendNotificationView(LoginRequiredMixin, DetailView):
    """
    Resend notification email to referee
    """
    model = Form
    
    def post(self, request, *args, **kwargs):
        assignment = self.get_object()
        
        try:
            # TODO: Implement actual email sending
            print(f"📧 Reminder email would be sent to {assignment.referee.email}")
            
            messages.success(
                request,
                f'✅ Reminder email sent to {assignment.referee.name} successfully!'
            )
        except Exception as e:
            messages.error(
                request,
                f'❌ Failed to send reminder email: {str(e)}'
            )
        
        return redirect('forms:detail', pk=assignment.pk)


class FormAssignmentStatsView(LoginRequiredMixin, TemplateView):
    """
    Display assignment statistics
    """
    template_name = 'forms/stats.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Overall statistics
        context['total_assignments'] = Form.objects.count()
        context['pending_assignments'] = Form.objects.filter(status=FormStatus.PENDING).count()
        context['completed_assignments'] = Form.objects.filter(status=FormStatus.COMPLETED).count()
        
        # Calculate completion rate
        if context['total_assignments'] > 0:
            context['completion_rate'] = round(
                (context['completed_assignments'] / context['total_assignments']) * 100, 1
            )
        else:
            context['completion_rate'] = 0
        
        # Template statistics
        template_stats = []
        for template in Template.objects.all():
            total_assignments = Form.objects.filter(template=template).count()
            completed_assignments = Form.objects.filter(
                template=template, 
                status=FormStatus.COMPLETED
            ).count()
            
            template_stats.append({
                'title': template.title,
                'is_active': template.is_active,
                'total_assignments': total_assignments,
                'completed_assignments': completed_assignments,
            })
        
        context['template_stats'] = template_stats
        
        # Referee statistics
        referee_stats = []
        for referee in Referee.objects.all():
            total_assignments = Form.objects.filter(referee=referee).count()
            completed_assignments = Form.objects.filter(
                referee=referee, 
                status=FormStatus.COMPLETED
            ).count()
            
            referee_stats.append({
                'name': referee.name,
                'email': referee.email,
                'phone': referee.phone,
                'relationship': referee.relationship,
                'total_assignments': total_assignments,
                'completed_assignments': completed_assignments,
            })
        
        context['referee_stats'] = referee_stats
        
        return context