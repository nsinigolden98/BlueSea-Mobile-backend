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

DSTV_PLANS = [
    ("DStv Padi N1,850", "DStv Padi N1,850"),
    ("DStv Yanga N2,565", "DStv Yanga N2,565"),
    ("Dstv Confam N4,615", "Dstv Confam N4,615"),
    ("DStv  Compact N7900", "DStv  Compact N7900"),
    ("DStv Premium N18,400", "DStv Premium N18,400"),
    ("DStv Asia N6,200", "DStv Asia N6,200"),
    ("DStv Compact Plus N12,400", "DStv Compact Plus N12,400"),
    ("DStv Premium-French N25,550", "DStv Premium-French N25,550"),
    ("DStv Premium-Asia N20,500", "DStv Premium-Asia N20,500"),
    ("DStv Confam + ExtraView N7,115", "DStv Confam + ExtraView N7,115"),
    ("DStv Yanga + ExtraView N5,065", "DStv Yanga + ExtraView N5,065"),
    ("DStv Padi + ExtraView N4,350", "DStv Padi + ExtraView N4,350"),
    ("DStv Compact + Asia N14,100", "DStv Compact + Asia N14,100"),
    ("DStv Compact + Extra View N10,400", "DStv Compact + Extra View N10,400"),
    ("DStv Compact + French Touch N10,200", "DStv Compact + French Touch N10,200"),
    ("DStv Premium - Extra View N20,900", "DStv Premium - Extra View N20,900"),
    ("DStv Compact Plus - Asia N18,600", "DStv Compact Plus - Asia N18,600"),
    (
        "DStv Compact + French Touch + ExtraView N12,700",
        "DStv Compact + French Touch + ExtraView N12,700",
    ),
    (
        "DStv Compact + Asia + ExtraView N16,600",
        "DStv Compact + Asia + ExtraView N16,600",
    ),
    (
        "DStv Compact Plus + French Plus N20,500",
        "DStv Compact Plus + French Plus N20,500",
    ),
    (
        "DStv Compact Plus + French Touch N14,700",
        "DStv Compact Plus + French Touch N14,700",
    ),
    (
        "DStv Compact Plus - Extra View N14,900",
        "DStv Compact Plus - Extra View N14,900",
    ),
    (
        "DStv Compact Plus + FrenchPlus + Extra View N23,000",
        "DStv Compact Plus + FrenchPlus + Extra View N23,000",
    ),
    ("DStv Compact + French Plus N16,000", "DStv Compact + French Plus N16,000"),
    (
        "DStv Compact Plus + Asia + ExtraView N21,100",
        "DStv Compact Plus + Asia + ExtraView N21,100",
    ),
    (
        "DStv Premium + Asia + Extra View N23,000",
        "DStv Premium + Asia + Extra View N23,000",
    ),
    (
        "DStv Premium + French + Extra View N28,000",
        "DStv Premium + French + Extra View N28,000",
    ),
    ("DStv HDPVR Access Service N2,500", "DStv HDPVR Access Service N2,500"),
    ("DStv French Plus Add-on N8,100", "DStv French Plus Add-on N8,100"),
    ("DStv Asian Add-on N6,200", "DStv Asian Add-on N6,200"),
    ("DStv French Touch Add-on N2,300", "DStv French Touch Add-on N2,300"),
    ("ExtraView Access N2,500", "ExtraView Access N2,500"),
    ("DStv French 11 N3,260", "DStv French 11 N3,260"),
    ("DStv Asian Bouquet E36 N12,400", "DStv Asian Bouquet E36 N12,400"),
    ("DStv Yanga + Showmax N6,550", "DStv Yanga + Showmax N6,550"),
    (
        "DStv Great Wall Standalone Bouquet + Showmax N6,625",
        "DStv Great Wall Standalone Bouquet + Showmax N6,625",
    ),
    ("DStv Compact Plus + Showmax N26,450", "DStv Compact Plus + Showmax N26,450"),
    ("Dstv Confam + Showmax N10,750", "Dstv Confam + Showmax N10,750"),
    ("DStv  Compact + Showmax N17,150", "DStv  Compact + Showmax N17,150"),
    ("DStv Padi + Showmax N7,100", "DStv Padi + Showmax N7,100"),
    (
        "DStv Premium W/Afr +  ASIAE36 + Showmax N57,500",
        "DStv Premium W/Afr +  ASIAE36 + Showmax N57,500",
    ),
    ("DStv Asia + Showmax N15,900", "DStv Asia + Showmax N15,900"),
    (
        "DStv Premium + French + Showmax N57,500",
        "DStv Premium + French + Showmax N57,500",
    ),
    ("DStv Premium + Showmax N37,000", "DStv Premium + Showmax N37,000"),
    (
        "DStv Premium Streaming Subscription - N37,000",
        "DStv Premium Streaming Subscription - N37,000",
    ),
    ("DStv Prestige - N850,000", "DStv Prestige - N850,000"),
    (
        "DStv Yanga OTT Streaming Subscription - N5,100",
        "DStv Yanga OTT Streaming Subscription - N5,100",
    ),
    (
        "DStv Compact Plus Streaming Subscription - N25,000",
        "DStv Compact Plus Streaming Subscription - N25,000",
    ),
    (
        "DStv Compact Streaming Subscription - N15,700",
        "DStv Compact Streaming Subscription - N15,700",
    ),
    (
        "DStv Comfam Streaming Subscription - N9,300",
        "DStv Comfam Streaming Subscription - N9,300",
    ),
    ("DStv Indian N12,400", "DStv Indian N12,400"),
    (
        "DStv Premium East Africa and Indian N16530",
        "DStv Premium East Africa and Indian N16530",
    ),
    ("DStv FTA Plus N1,600", "DStv FTA Plus N1,600"),
    ("DStv PREMIUM HD N39,000", "DStv PREMIUM HD N39,000"),
    ("DStv Access N2000", "DStv Access N2000"),
    ("DStv Family", "DStv Family"),
    ("DStv India Add-on N12,400", "DStv India Add-on N12,400"),
    ("DSTV MOBILE N790", "DSTV MOBILE N790"),
    ("DStv Movie Bundle Add-on N2500", "DStv Movie Bundle Add-on N2500"),
    ("DStv PVR Access Service N4000", "DStv PVR Access Service N4000"),
    ("DStv Premium W/Afr + Showmax N37,000", "DStv Premium W/Afr + Showmax N37,000"),
    ("Showmax Standalone - N3,500", "Showmax Standalone - N3,500"),
    ("DStv Prestige Membership - N850,000", "DStv Prestige Membership - N850,000"),
    (
        "DStv Compact Plus + French + Xtraview - N39,000",
        "DStv Compact Plus + French + Xtraview - N39,000",
    ),
    ("DStv Compact Plus + French - N34,000", "DStv Compact Plus + French - N34,000"),
    ("DStv Box Office", "DStv Box Office"),
    ("DStv Box Office (New Premier)", "DStv Box Office (New Premier)"),
]

GOTV_PLANS = [
    ("GOtv Lite N410", "GOtv Lite N410"),
    ("GOtv Max N3,600", "GOtv Max N3,600"),
    ("GOtv Jolli N2,460", "GOtv Jolli N2,460"),
    ("GOtv Jinja N1,640", "GOtv Jinja N1,640"),
    ("GOtv Lite (3 Months) N1,080", "GOtv Lite (3 Months) N1,080"),
    ("GOtv Lite (1 Year) N3,180", "GOtv Lite (1 Year) N3,180"),
    ("GOtv Supa Plus - monthly N15,700", "GOtv Supa Plus - monthly N15,700"),
]

SUB_TYPE = [
    ("change", "change"),
    ("renew","renew"),
    ]

SHOWMAX_PLANS =[
    ("Full - N8,400 - 3 Months", "Full - N8,400 - 3 Months"),
    ("Mobile Only - N3,800 - 3 Months", "Mobile Only - N3,800 - 3 Months"),
    (
        "Sports Mobile Only - N12,000 - 3 Months",
        "Sports Mobile Only - N12,000 - 3 Months",
    ),
    ("Sports Only - N3,200", "Sports Only - N3,200"),
    ("Sports Only 3 months - N9,600", "Sports Only 3 months - N9,600"),
    (
        "Full Sports Mobile Only - 3 months - N16,200",
        "Full Sports Mobile Only - 3 months - N16,200",
    ),
    ("Mobile Only - N6,700 - 6 Months", "Mobile Only - N6,700 - 6 Months"),
    ("Full - 6 months - 14,700", "Full - 6 months - 14,700"),
    (
        "Full Sports Mobile Only - 6 months - N32,400",
        "Full Sports Mobile Only - 6 months - N32,400",
    ),
    (
        "Sports Mobile Only - 6 months - N24,000",
        "Sports Mobile Only - 6 months - N24,000",
    ),
    ("Sports Only - 6 months - N18,200", "Sports Only - 6 months - N18,200"),
]

STARTIMES_PLANS = [
    ("Nova - 900 Naira - 1 Month", "Nova - 900 Naira - 1 Month"),
    ("Basic - 1,700 Naira - 1 Month", "Basic - 1,700 Naira - 1 Month"),
    ("Smart - 2,200 Naira - 1 Month", "Smart - 2,200 Naira - 1 Month"),
    ("Classic - 2,500 Naira - 1 Month", "Classic - 2,500 Naira - 1 Month"),
    ("Super - 4,200 Naira - 1 Month", "Super - 4,200 Naira - 1 Month"),
    ("Nova - 300 Naira - 1 Week", "Nova - 300 Naira - 1 Week"),
    ("Basic - 600 Naira - 1 Week", "Basic - 600 Naira - 1 Week"),
    ("Smart - 700 Naira - 1 Week", "Smart - 700 Naira - 1 Week"),
    ("Classic - 1200 Naira - 1 Week ", "Classic - 1200 Naira - 1 Week "),
    ("Super - 1,500 Naira - 1 Week", "Super - 1,500 Naira - 1 Week"),
    ("Nova - 90 Naira - 1 Day", "Nova - 90 Naira - 1 Day"),
    ("Basic - 160 Naira - 1 Day", "Basic - 160 Naira - 1 Day"),
    ("Smart - 200 Naira - 1 Day", "Smart - 200 Naira - 1 Day"),
    ("Classic - 320 Naira - 1 Day ", "Classic - 320 Naira - 1 Day "),
    ("Super - 400 Naira - 1 Day", "Super - 400 Naira - 1 Day"),
    ("ewallet Amount", "ewallet Amount"),
    (
        "Chinese (Dish) - 19,000 Naira - 1 month",
        "Chinese (Dish) - 19,000 Naira - 1 month",
    ),
    (
        "Nova (Antenna) - 1,900 Naira - 1 Month",
        "Nova (Antenna) - 1,900 Naira - 1 Month",
    ),
    ("Classic (Dish) - 2300 Naira - 1 Week", "Classic (Dish) - 2300 Naira - 1 Week"),
    ("Classic (Dish) - 6800 Naira - 1 Month", "Classic (Dish) - 6800 Naira - 1 Month"),
    ("Nova (Dish) - 650 Naira - 1 Week", "Nova (Dish) - 650 Naira - 1 Week"),
    (
        "Super (Antenna) - 3,000 Naira - 1 Week",
        "Super (Antenna) - 3,000 Naira - 1 Week",
    ),
    (
        "Super (Antenna) - 8,800 Naira - 1 Month",
        "Super (Antenna) - 8,800 Naira - 1 Month",
    ),
    ("Global (Dish) - 19000 Naira - 1 Month", "Global (Dish) - 19000 Naira - 1 Month"),
    ("Global (Dish) - 6500 Naira - 1Week", "Global (Dish) - 6500 Naira - 1Week"),
]

class AirtimeTopUp(models.Model):
    amount = models.IntegerField()
    network = models.CharField(max_length = 10, choices= NETWORK_TYPES)
    phone_number = models.CharField()
    request_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class DSTVPayment(models.Model):
    billersCode = models.CharField()
    dstv_plan = models.CharField(max_length = 100, choices= DSTV_PLANS)
    subscription_type = models.CharField(max_length = 20, choices= SUB_TYPE)
    phone_number = models.CharField()
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
class GOTVPayment(models.Model):
    billersCode = models.CharField()
    gotv_plan = models.CharField(max_length = 100, choices= GOTV_PLANS)
    subscription_type = models.CharField(max_length = 20, choices= SUB_TYPE)
    phone_number = models.CharField()
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
class StartimesPayment(models.Model):
    billersCode = models.CharField()
    startimes_plan = models.CharField(max_length = 100, choices= STARTIMES_PLANS)
    phone_number = models.CharField()
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
class ShowMaxPayment(models.Model):
    showmax_plan = models.CharField(max_length = 100, choices= SHOWMAX_PLANS)
    phone_number = models.CharField()
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
class ElectricityPayment(models.Model):
    billerCode = models.CharField()
    amount = models.IntegerField()
    biller_name = models.CharField(max_length = 30, choices= BILLER_NAME)
    meter_type = models.CharField(max_length = 20, choices= METER_TYPES)
    phone_number = models.CharField()
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
class WAECRegitration(models.Model):
    phone_number = models.CharField()
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
class WAECResultChecker(models.Model):
    phone_number = models.CharField()
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
class JAMBRegistration(models.Model):
    billerCode = models.CharField()
    exam_type = models.CharField(max_length = 20, choices= EXAM_TYPES)
    phone_number = models.CharField()
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    
    