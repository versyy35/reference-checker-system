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
