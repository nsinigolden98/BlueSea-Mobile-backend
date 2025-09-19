from django.urls import path,include
from . import views

app_name = 'GroupPayment'


urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('verify-email/', views.VerifyEmail.as_view(), name='verify-email'),
    path('resend-otp/', views.ResendOtp.as_view(), name='resend-otp'),
]