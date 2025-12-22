from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

from django.conf import settings
from django.conf.urls.static import static
import debug_toolbar

urlpatterns = [
    path('__debug__/', include('debug_toolbar.urls')),
    path('schema/', SpectacularAPIView.as_view(), name='schema'),

    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('payments/', include('payments.urls')),
    path('payments/group/', include('group_payment.urls')),
    # path('notifications/', include('notifications.urls')),
    path('market_place/', include('market_place.urls')),
    path('wallet/', include('wallet.urls')),
    path('transactions/', include('transactions.urls')),
    path('bonus/', include('bonus.urls')),
    path('market/', include('loyalty_market.urls')),
    path('user_preference/', include('user_preference.urls')),
    path('autotopup/', include('autotopup.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

