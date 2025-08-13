from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'authentication'

urlpatterns = [
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='auth/password_reset.html'
    ), name='password_reset'),
]
