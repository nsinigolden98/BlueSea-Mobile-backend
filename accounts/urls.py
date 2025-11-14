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
    path('password/reset/request/', views.PasswordResetView.as_view(), name='password-reset-request'),
    path('password/reset/verify-otp/', views.VerifyResetOTPView.as_view(), name='password-reset-verify'),
    path('password/reset/confirm/', views.ResetUserPassword.as_view(), name='password-reset-confirm'),
    
    path('pin/set/', views.set_transaction_pin, name='set-transaction-pin'),
    path('pin/verify/', views.verify_pin, name='verify-transaction-pin'),
    path('pin/reset/', views.change_transaction_pin, name='reset-transaction-pin'),
]