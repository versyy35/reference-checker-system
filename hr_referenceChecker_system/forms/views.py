from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import View, CreateView, DetailView, ListView, UpdateView, DeleteView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Count
from django.http import HttpResponse, Http404
from django.utils import timezone
from django.core.paginator import Paginator

from .models import Form, FormStatus
from .forms import FormAssignmentForm, BulkAssignmentForm, FormAssignmentSearchForm, FormStatusUpdateForm, ReminderEmailForm
from referees.models import Referee
from form_templates.models import Template


class FormListView(LoginRequiredMixin, ListView):
    """
    List view for form assignments with filtering and search
    """
    model = Form
    template_name = 'forms/list.html'
    context_object_name = 'form_assignments'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Form.objects.select_related(
            'template', 'referee'
        ).order_by('-created_at')
        
        # Apply filters from search form
        search_query = self.request.GET.get('search', '').strip()
        status_filter = self.request.GET.get('status', '').strip()
        template_filter = self.request.GET.get('template', '').strip()
        
        if search_query:
            queryset = queryset.filter(
                Q(template__title__icontains=search_query) |
                Q(referee__name__icontains=search_query) |
                Q(referee__email__icontains=search_query) |
                Q(referee__applicant_name__icontains=search_query)
            )
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if template_filter:
            queryset = queryset.filter(template_id=template_filter)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add search form
        search_form_data = {
            'search': self.request.GET.get('search', ''),
            'status': self.request.GET.get('status', ''),
            'template': self.request.GET.get('template', ''),
        }
        context['search_form'] = FormAssignmentSearchForm(initial=search_form_data)
        
        # Add filter values for template
        context['search_query'] = self.request.GET.get('search', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['template_filter'] = self.request.GET.get('template', '')
        
        # Add statistics
        total_assignments = Form.objects.count()
        pending_assignments = Form.objects.filter(status=FormStatus.PENDING).count()
        completed_assignments = Form.objects.filter(status=FormStatus.COMPLETED).count()
        
        # Add status choices for template
        context['status_choices'] = FormStatus.choices
        context['templates'] = Template.objects.filter(is_active=True).order_by('title')
        
        context.update({
            'total_assignments': total_assignments,
            'pending_assignments': pending_assignments,
            'completed_assignments': completed_assignments,
        })
        
        return context


class FormCreateView(LoginRequiredMixin, CreateView):
    """
    Create view for single form assignments
    """
    model = Form
    form_class = FormAssignmentForm
    template_name = 'forms/create.html'
    success_url = reverse_lazy('forms:list')
    
    def form_valid(self, form):
        """Process form submission"""
        # Set initial status
        form.instance.status = FormStatus.PENDING
        
        # Save the form assignment
        response = super().form_valid(form)
        
        # Send email if requested
        send_email = form.cleaned_data.get('send_email', False)
        if send_email:
            try:
                self.object.send_email_notification()
                messages.success(
                    self.request,
                    f'Form assigned to {self.object.referee.name} and email notification sent!'
                )
            except Exception as e:
                messages.warning(
                    self.request,
                    f'Form assigned successfully but email failed to send: {str(e)}'
                )
        else:
            messages.success(
                self.request,
                f'Form assigned to {self.object.referee.name}!'
            )
        
        # Create notification
        self.create_assignment_notification()
        
        return response
    
    def create_assignment_notification(self):
        """Create notification for staff about new assignment"""
        try:
            from core.models import Notification, NotificationType
            from django.contrib.auth import get_user_model
            
            User = get_user_model()
            staff_users = User.objects.filter(is_active=True, is_staff=True)
            
            for staff_user in staff_users:
                Notification.create_notification(
                    user=staff_user,
                    title="New Form Assignment",
                    message=f'"{self.object.template.title}" assigned to {self.object.referee.name} for {self.object.referee.applicant_name}',
                    notification_type=NotificationType.INFO,
                    icon='fas fa-clipboard-list',
                    related_object=self.object
                )
        except Exception as e:
            print(f"Error creating assignment notification: {e}")


class BulkAssignView(LoginRequiredMixin, View):
    """
    View for bulk assigning forms to multiple referees
    """
    template_name = 'forms/bulk_create.html'
    form_class = BulkAssignmentForm
    
    def get(self, request):
        """Display the bulk assignment form"""
        form = self.form_class()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        """Process the bulk assignment"""
        form = self.form_class(request.POST)
        
        if form.is_valid():
            template = form.cleaned_data['template']
            referees = form.cleaned_data['referees']
            send_email = form.cleaned_data.get('send_email', False)
            
            # Create form assignments for each selected referee
            created_forms = []
            skipped_forms = []
            
            for referee in referees:
                # Check if this referee already has an assignment for this template
                existing_form = Form.objects.filter(
                    template=template,
                    referee=referee,
                    status=FormStatus.PENDING
                ).first()
                
                if existing_form:
                    skipped_forms.append(referee.name)
                    continue
                
                # Create new form assignment
                form_assignment = Form.objects.create(
                    template=template,
                    referee=referee,
                    status=FormStatus.PENDING
                )
                created_forms.append(form_assignment)
                
                # Send email notification if requested
                if send_email:
                    try:
                        form_assignment.send_email_notification()
                    except Exception as e:
                        messages.warning(
                            request,
                            f'Assignment created for {referee.name} but email failed to send: {str(e)}'
                        )
            
            # Show results
            if created_forms:
                messages.success(
                    request,
                    f'Successfully assigned "{template.title}" to {len(created_forms)} referee(s).'
                )
                
                # Create notifications for staff
                self.create_bulk_assignment_notifications(request.user, template, created_forms)
            
            if skipped_forms:
                messages.warning(
                    request,
                    f'Skipped {len(skipped_forms)} referee(s) who already have pending assignments: {", ".join(skipped_forms[:3])}{"..." if len(skipped_forms) > 3 else ""}'
                )
            
            if created_forms:
                return redirect('forms:list')
            else:
                messages.error(request, 'No new assignments were created.')
        
        return render(request, self.template_name, {'form': form})
    
    def create_bulk_assignment_notifications(self, user, template, form_assignments):
        """Create notifications for bulk assignments"""
        try:
            from core.models import Notification, NotificationType
            from django.contrib.auth import get_user_model
            
            User = get_user_model()
            staff_users = User.objects.filter(is_active=True, is_staff=True)
            
            for staff_user in staff_users:
                Notification.create_notification(
                    user=staff_user,
                    title="Bulk Assignment Created",
                    message=f'{user.get_full_name() or user.username} assigned "{template.title}" to {len(form_assignments)} referees',
                    notification_type=NotificationType.INFO,
                    icon='fas fa-users'
                )
        except Exception as e:
            print(f"Error creating bulk assignment notifications: {e}")


class FormDetailView(LoginRequiredMixin, DetailView):
    """
    Detail view for individual form assignments
    """
    model = Form
    template_name = 'forms/detail.html'
    context_object_name = 'assignment'
    
    def get_object(self):
        return get_object_or_404(
            Form.objects.select_related('template', 'referee'),
            pk=self.kwargs['pk']
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Check if form has expired (older than 30 days)
        if self.object.created_at:
            days_old = (timezone.now() - self.object.created_at).days
            context['is_expired'] = days_old > 30
        else:
            context['is_expired'] = False
        
        # Generate access URL for the form
        context['access_url'] = self.object.generate_access_url()
        
        return context


class FormUpdateView(LoginRequiredMixin, UpdateView):
    """
    Update view for form assignments (mainly for status updates)
    """
    model = Form
    form_class = FormStatusUpdateForm
    template_name = 'forms/edit.html'
    context_object_name = 'object'
    
    def get_success_url(self):
        return reverse('forms:detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        """Process status update"""
        old_status = Form.objects.get(pk=self.object.pk).status
        new_status = form.cleaned_data['status']
        
        response = super().form_valid(form)
        
        if old_status != new_status:
            messages.success(
                self.request,
                f'Assignment status updated from {old_status} to {new_status}'
            )
            
            # Create notification for status change
            self.create_status_change_notification(old_status, new_status)
        
        return response
    
    def create_status_change_notification(self, old_status, new_status):
        """Create notification for status changes"""
        try:
            from core.models import Notification, NotificationType
            from django.contrib.auth import get_user_model
            
            User = get_user_model()
            staff_users = User.objects.filter(is_active=True, is_staff=True)
            
            for staff_user in staff_users:
                Notification.create_notification(
                    user=staff_user,
                    title="Assignment Status Changed",
                    message=f'Assignment for {self.object.referee.name} changed from {old_status} to {new_status}',
                    notification_type=NotificationType.INFO,
                    icon='fas fa-edit',
                    related_object=self.object
                )
        except Exception as e:
            print(f"Error creating status change notification: {e}")


class FormDeleteView(LoginRequiredMixin, DeleteView):
    """
    Delete view for form assignments
    """
    model = Form
    template_name = 'forms/delete.html'
    success_url = reverse_lazy('forms:list')
    context_object_name = 'object'
    
    def get_object(self):
        return get_object_or_404(
            Form.objects.select_related('template', 'referee'),
            pk=self.kwargs['pk']
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add additional context for the delete confirmation
        context['questions_count'] = self.object.template.questions.count()
        
        # Check if there are any responses
        try:
            from responses.models import Response
            context['has_responses'] = Response.objects.filter(form=self.object).exists()
        except:
            context['has_responses'] = False
        
        return context
    
    def delete(self, request, *args, **kwargs):
        """Handle deletion with notification"""
        self.object = self.get_object()
        template_title = self.object.template.title
        referee_name = self.object.referee.name
        
        # Create notification before deletion
        self.create_deletion_notification(template_title, referee_name)
        
        # Delete the object
        response = super().delete(request, *args, **kwargs)
        
        messages.success(
            request,
            f'Assignment of "{template_title}" to {referee_name} has been deleted.'
        )
        
        return response
    
    def create_deletion_notification(self, template_title, referee_name):
        """Create notification for assignment deletion"""
        try:
            from core.models import Notification, NotificationType
            from django.contrib.auth import get_user_model
            
            User = get_user_model()
            staff_users = User.objects.filter(is_active=True, is_staff=True)
            
            for staff_user in staff_users:
                Notification.create_notification(
                    user=staff_user,
                    title="Assignment Deleted",
                    message=f'Assignment of "{template_title}" to {referee_name} was deleted by {self.request.user.get_full_name() or self.request.user.username}',
                    notification_type=NotificationType.WARNING,
                    icon='fas fa-trash'
                )
        except Exception as e:
            print(f"Error creating deletion notification: {e}")


class ResendEmailView(LoginRequiredMixin, View):
    """
    View for resending email notifications
    """
    def post(self, request, pk):
        """Resend email notification"""
        form_assignment = get_object_or_404(Form, pk=pk)
        
        if form_assignment.status != FormStatus.PENDING:
            messages.error(
                request,
                'Email can only be resent for pending assignments.'
            )
            return redirect('forms:detail', pk=pk)
        
        try:
            form_assignment.send_email_notification(is_reminder=True)
            messages.success(
                request,
                f'Reminder email sent to {form_assignment.referee.name}!'
            )
            
            # Create notification
            self.create_reminder_notification(form_assignment)
            
        except Exception as e:
            messages.error(
                request,
                f'Failed to send reminder email: {str(e)}'
            )
        
        return redirect('forms:detail', pk=pk)
    
    def create_reminder_notification(self, form_assignment):
        """Create notification for reminder emails"""
        try:
            from core.models import Notification, NotificationType
            from django.contrib.auth import get_user_model
            
            User = get_user_model()
            staff_users = User.objects.filter(is_active=True, is_staff=True)
            
            for staff_user in staff_users:
                Notification.create_notification(
                    user=staff_user,
                    title="Reminder Email Sent",
                    message=f'Reminder email sent to {form_assignment.referee.name} for "{form_assignment.template.title}"',
                    notification_type=NotificationType.INFO,
                    icon='fas fa-envelope'
                )
        except Exception as e:
            print(f"Error creating reminder notification: {e}")


class FormStatsView(LoginRequiredMixin, View):
    """
    View for form assignment statistics
    """
    template_name = 'forms/stats.html'
    
    def get(self, request):
        """Display statistics"""
        # Basic statistics
        total_assignments = Form.objects.count()
        pending_assignments = Form.objects.filter(status=FormStatus.PENDING).count()
        completed_assignments = Form.objects.filter(status=FormStatus.COMPLETED).count()
        
        # Calculate completion rate
        completion_rate = 0
        if total_assignments > 0:
            completion_rate = round((completed_assignments / total_assignments) * 100)
        
        # Template statistics
        template_stats = Template.objects.annotate(
            total_assignments=Count('form'),
            completed_assignments=Count('form', filter=Q(form__status=FormStatus.COMPLETED))
        ).filter(total_assignments__gt=0).order_by('-total_assignments')
        
        # Referee statistics
        referee_stats = Referee.objects.annotate(
            total_assignments=Count('form'),
            completed_assignments=Count('form', filter=Q(form__status=FormStatus.COMPLETED))
        ).filter(total_assignments__gt=0).order_by('-total_assignments')
        
        context = {
            'total_assignments': total_assignments,
            'pending_assignments': pending_assignments,
            'completed_assignments': completed_assignments,
            'completion_rate': completion_rate,
            'template_stats': template_stats[:10],  # Top 10 templates
            'referee_stats': referee_stats[:10],    # Top 10 referees
        }
        
        return render(request, self.template_name, context)