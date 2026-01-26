from django.db import models
class MarketPlace(models.Model):
    product_name = models.CharField(max_length=100)
    product_description = models.CharField(max_length=200) # why not use textField 
    image = models.ImageField(upload_to='images/')
    created_at = models.DateTimeField(auto_now_add=True)
