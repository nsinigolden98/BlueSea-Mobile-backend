from django.urls import path
from . import views

app_name = 'accounts'


urlpatterns = [
    path('sign-up/', views.RegisterView.as_view(), name='sign-up'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('verify-email/', views.VerifyEmail.as_view(), name='verify-email'),
    path('resend-otp/', views.ResendOtp.as_view(), name='resend-otp'),
    path('auth/google/', views.GoogleLoginView.as_view(), name='google-login'),
    path('auth/apple/', views.AppleLoginView.as_view(), name='apple-login'),
    path('reset-password/', views.PasswordResetView.as_view(), name='reset-password'),
    # path('edit-password/', views.EditPasswordView.as_view(), name='edit-password'),
]