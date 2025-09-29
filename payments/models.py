from django.db import models
from decimal import Decimal
from django.conf import settings

NETWORK_TYPES = [
        ('mtn', 'mtn'),
        ('airtel', 'airtel'),
        ('glo', 'glo'),
        ('etisalat', 'etisalat'),
    ]  
class AirtimeTopUp(models.Model):
    amount = models.IntegerField()
    network = models.CharField(max_length = 10, choices= NETWORK_TYPES)
    #phone_number = models.IntegerField()
    phone_number = models.CharField(max_length= 15)
    reference_id = models.DateTimeField(auto_now_add=True)
    
    