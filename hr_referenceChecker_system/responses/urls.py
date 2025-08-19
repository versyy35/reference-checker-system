from django.urls import path
from . import views

app_name = 'responses'  # This creates the 'responses:' namespace

urlpatterns = [
    # Main responses list
    path('', views.ResponseListView.as_view(), name='list'),
    
    # Individual response detail
    path('<int:pk>/', views.ResponseDetailView.as_view(), name='detail'),
    
    # Simple text export for single response
    path('<int:pk>/export/', views.ResponseExportSimpleView.as_view(), name='export_pdf'),
    
    # Bulk text export
    path('bulk-export/', views.BulkExportSimpleView.as_view(), name='bulk_export'),
]