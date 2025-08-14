from django.urls import path
from . import views

app_name = 'form_templates'

urlpatterns = [
    path('', views.TemplateListView.as_view(), name='list'),
    path('add/', views.TemplateCreateView.as_view(), name='create'),
    path('<int:pk>/', views.TemplateDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.TemplateUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.TemplateDeleteView.as_view(), name='delete'),
    path('<int:pk>/duplicate/', views.TemplateDuplicateView.as_view(), name='duplicate'),
]
