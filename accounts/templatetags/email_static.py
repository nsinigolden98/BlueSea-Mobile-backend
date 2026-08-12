from django import template
from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage

register = template.Library()


@register.simple_tag
def email_static(path):
    """Return an absolute URL for a static asset, suitable for use in emails.

    Email clients cannot resolve relative STATIC_URL values, so we prefix the
    configured SITE_URL. Using staticfiles_storage.url keeps manifest-hashed
    filenames correct in production while leaving STATIC_URL relative for the app.
    """
    relative = staticfiles_storage.url(path).lstrip("/")
    return f"{settings.SITE_URL}/{relative}"
