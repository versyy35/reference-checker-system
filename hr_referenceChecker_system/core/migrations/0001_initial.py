# Create this file: core/migrations/0001_initial.py
# Run: python manage.py makemigrations core
# Then: python manage.py migrate

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('message', models.TextField()),
                ('notification_type', models.CharField(choices=[('success', 'Success'), ('warning', 'Warning'), ('info', 'Info'), ('danger', 'Danger')], default='info', max_length=20)),
                ('icon', models.CharField(default='fas fa-info-circle', max_length=50)),
                ('is_read', models.BooleanField(default=False)),
                ('is_dismissed', models.BooleanField(default=False)),
                ('object_id', models.PositiveIntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('content_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['user', 'is_read', 'is_dismissed'], name='core_notifi_user_id_d73ea9_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['created_at'], name='core_notifi_created_5c2415_idx'),
        ),
    ]