from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    path('refresh-captcha/', views.refresh_captcha, name='refresh_captcha'),
    path('user-management/', views.user_management, name='user_management'),
    path('operation-logs/', views.operation_logs, name='operation_logs'),
]


