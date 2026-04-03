from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.contrib import messages
from django.template.loader import render_to_string
from django.core.mail import send_mail , EmailMessage
from django.contrib import messages
from django.utils.html import strip_tags
from django.conf import settings
import secrets
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import constant_time_compare, salted_hmac
from datetime import timedelta
import random
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


UserModel = get_user_model()


# class EmailOrUsernameBackend(ModelBackend):
#     def authenticate(self, request, username=None, password=None, **kwargs):
#         try:
#             user = UserModel.objects.get(
#                 Q(username__iexact=username) | Q(email__iexact=username)
#             )
#         except UserModel.DoesNotExist:
#             return None

#         if user.check_password(password):
#             return user
#         return None


def send_email_verification(subject, template, email, context):
    try:
        # Render the HTML version
        html_content = render_to_string(template, context)

        # Create plain text manually for better readability (instead of using strip_tags)
        otp = context.get('verification_code', '------')
        text_content = f"""
BlueSea VTU - Verify Your Email Address

Please use the OTP below to verify your email address and complete your account registration.

OTP: {otp}

Note: This OTP is valid for only 15 minutes from when you received it.

If you didn't request this email, you can safely ignore it.

Need help? Contact our support at support@bluesea.com
        """.strip()

        # email message, both plain text and HTML
        email_msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.FROM_EMAIL,
            to=[email],
        )
        email_msg.attach_alternative(html_content, "text/html")
        email_msg.send()
        return True

    except Exception as e:
        print(str(e))
        return False

    

def generate_verification_code():
    return secrets.token_hex(16)

def generate_reset_code():
    return random.randint(100000,999999)


class CustomPasswordResetTokenGenerator(PasswordResetTokenGenerator):
    TOKEN_EXPIRATION = timedelta(hours=1)

    def _make_hash_value(self, user, timestamp):
        
        return (
            str(user.pk) + str(timestamp) +
            str(user.is_active)
        )

    def check_token(self, user, token):
        if not (user and token):
            return False

        
        try:
            uidb64, token = token.split('-')
        except ValueError:
            return False

        try:
            timestamp = int(uidb64)
        except (TypeError, ValueError):
            return False

        if (self._num_seconds(self._now()) - timestamp) > self.TOKEN_EXPIRATION.total_seconds():
            return False

        return constant_time_compare(self._make_token_with_timestamp(user, timestamp), token)

password_reset_token_generator = CustomPasswordResetTokenGenerator()


def gen_simple_token(data):
    return signing.dumps(data)