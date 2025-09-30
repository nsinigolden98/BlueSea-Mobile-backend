from django.db import models

NETWORK_TYPES = [
        ('mtn', 'mtn'),
        ('airtel', 'airtel'),
        ('glo', 'glo'),
        ('etisalat', 'etisalat'),
    ]  
    
EXAM_TYPES = [
    ('utme-mock','utme-mock'),
    ('utme-no-mock','utme-no-mock')
    ]
    
METER_TYPES = [
    ('prepaid','prepaid'),
    ('postpaid','postpaid')
    ]

BILLER_NAME= [
('ikeja-electric', 'ikeja-electric') ,
('eko-electric', 'eko-electric') ,
('kano-electric', 'kano-electric') ,
('portharcourt-electric', 'portharcourt-electric') ,
('jos-electric', 'jos-electric') ,
('ibadan-electric', 'ibadan-electric') ,
('kaduna-electric', 'kaduna-electric') ,
('abuja-electric', 'abuja-electric') ,
('enugu-electric', 'enugu-electric') ,
('benin-electric', 'benin-electric') ,
('aba-electric', 'aba-electric') ,
('yola-electric', 'yola-electric') ,
]

class AirtimeTopUp(models.Model):
    amount = models.IntegerField()
    network = models.CharField(max_length = 10, choices= NETWORK_TYPES)
    phone_number = models.CharField()
    reference_id = models.DateTimeField(auto_now_add=True)

class ElectricityPayment(models.Model):
    billerCode = models.CharField()
    amount = models.IntegerField()
    biller_name = models.CharField(max_length = 30, choices= BILLER_NAME)
    meter_type = models.CharField(max_length = 20, choices= METER_TYPES)
    phone_number = models.CharField()
    reference_id = models.DateTimeField(auto_now_add=True)
    
class WAECRegitration(models.Model):
    phone_number = models.CharField()
    reference_id = models.DateTimeField(auto_now_add=True)
    
class WAECResultChecker(models.Model):
    phone_number = models.CharField()
    reference_id = models.DateTimeField(auto_now_add=True)
    
class JAMBRegistration(models.Model):
    billerCode = models.CharField()
    exam_type = models.CharField(max_length = 20, choices= EXAM_TYPES)
    phone_number = models.CharField()
    reference_id = models.DateTimeField(auto_now_add=True)
    
    
    