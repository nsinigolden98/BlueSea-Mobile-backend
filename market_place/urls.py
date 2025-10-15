from django.urls import path
from .views import (
    MarketPlaceView,
    )

urlpatterns = [
    path('market/', MarketPlaceView.as_view(), name='market'),
    ]