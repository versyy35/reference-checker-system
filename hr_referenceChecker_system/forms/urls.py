from django.urls import path
from . import views

app_name = 'forms'

urlpatterns = [
    # Form assignments list
    path('', views.FormListView.as_view(), name='list'),
    
    # Single form assignment
    path('assign/', views.FormCreateView.as_view(), name='assign'),
    
    # Bulk form assignment - using the fixed view
    path('bulk-assign/', views.BulkAssignView.as_view(), name='bulk_assign'),
    
    # Form detail, edit, delete
    path('<int:pk>/', views.FormDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.FormUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.FormDeleteView.as_view(), name='delete'),
    
    # Form actions
    path('<int:pk>/resend/', views.ResendEmailView.as_view(), name='resend'),
    
    # Statistics
    path('stats/', views.FormStatsView.as_view(), name='stats'),
]