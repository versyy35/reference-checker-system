from django.urls import path
from . import views

app_name = 'referees'

urlpatterns = [
    path('', views.RefereeListView.as_view(), name='list'),
    path('add/', views.RefereeCreateView.as_view(), name='create'),
    path('<int:pk>/', views.RefereeDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.RefereeUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.RefereeDeleteView.as_view(), name='delete'),
]