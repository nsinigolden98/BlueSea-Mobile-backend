from django.db import models


class MarketPlace(models.Model):
    product_name = models.CharField()
    product_description = models.CharField()
    image = models.ImageField(upload_to='images/')
    created_at = models.DateTimeField(auto_now_add=True)
