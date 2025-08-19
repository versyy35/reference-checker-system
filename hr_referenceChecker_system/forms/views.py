# Update forms/views.py - Add notification creation to form assignments

# Add this method to your FormAssignmentCreateView class
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
        
        # 🎯 CREATE NOTIFICATION FOR FORM ASSIGNMENT
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


# Add this method to your BulkAssignmentCreateView class
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
        
        # 🎯 CREATE NOTIFICATION FOR BULK ASSIGNMENT
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


# 🎯 ADD A MANAGEMENT COMMAND TO CREATE OVERDUE NOTIFICATIONS
# Create this file: core/management/commands/check_overdue_forms.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from forms.models import Form, FormStatus
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Check for overdue forms and create notifications'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days after which a form is considered overdue (default: 7)',
        )

    def handle(self, *args, **options):
        overdue_days = options['days']
        cutoff_date = timezone.now() - timedelta(days=overdue_days)
        
        # Find overdue forms
        overdue_forms = Form.objects.filter(
            status=FormStatus.PENDING,
            created_at__lt=cutoff_date
        )
        
        if not overdue_forms.exists():
            self.stdout.write(self.style.SUCCESS('No overdue forms found.'))
            return
        
        try:
            from core.models import Notification, NotificationType
            
            staff_users = User.objects.filter(is_active=True, is_staff=True)
            notifications_created = 0
            
            for form in overdue_forms:
                days_overdue = (timezone.now() - form.created_at).days
                
                for user in staff_users:
                    # Check if notification already exists for this form
                    existing_notification = Notification.objects.filter(
                        user=user,
                        message__icontains=f"{form.referee.name} has not submitted {form.template.title}",
                        created_at__gte=timezone.now() - timedelta(days=1)  # Don't spam daily
                    ).exists()
                    
                    if not existing_notification:
                        Notification.create_notification(
                            user=user,
                            title="Form Overdue",
                            message=f"{form.referee.name} has not submitted {form.template.title} for {form.referee.applicant_name} ({days_overdue} days overdue)",
                            notification_type=NotificationType.WARNING,
                            icon='fas fa-exclamation-triangle',
                            related_object=form
                        )
                        notifications_created += 1
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Created {notifications_created} overdue notifications for {overdue_forms.count()} overdue forms'
                )
            )
            
        except ImportError:
            self.stdout.write(
                self.style.ERROR('Notification system not available. Please run migrations first.')
            )