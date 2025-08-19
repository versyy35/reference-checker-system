from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('notifications/', views.NotificationsView.as_view(), name='notifications'),

    # AJAX notification endpoints
    path('notifications/mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/clear-all/', views.clear_all_notifications, name='clear_all_notifications'),
    path('notifications/dismiss/<int:notification_id>/', views.dismiss_notification, name='dismiss_notification'),
]
