from django.urls import path
from . import views

app_name = 'forms'

urlpatterns = [
    # Form assignment management
    path('', views.FormAssignmentListView.as_view(), name='list'),
    path('assign/', views.FormAssignmentCreateView.as_view(), name='assign'),
    path('bulk-assign/', views.BulkAssignmentCreateView.as_view(), name='bulk_assign'),
    path('<int:pk>/', views.FormAssignmentDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.FormAssignmentUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.FormAssignmentDeleteView.as_view(), name='delete'),
    path('<int:pk>/resend/', views.ResendNotificationView.as_view(), name='resend'),
    path('stats/', views.FormAssignmentStatsView.as_view(), name='stats'),
]