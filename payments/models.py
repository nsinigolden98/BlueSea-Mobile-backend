from django.db import models
from django.contrib.auth import get_user_model
from group_payment.models import Group, GroupMember
from django.conf import settings
User = get_user_model()

NETWORK_TYPES = [
    ("mtn", "mtn"),
    ("airtel", "airtel"),
    ("glo", "glo"),
    ("etisalat", "etisalat"),
]

MTN_PLANS = [
    ("N100 100MB - 24 hrs", "mtn-10mb-100"),
    ("N200 200MB - 2 days", "mtn-230mb-200"),
    ("N1000 1.5GB - 30 days", "mtn-1500mb-1000"),
    ("N2000 4.5GB - 30 days", "mtn-2.7gb-2000"),
    ("N1500 6GB - 7 days", "mtn-3.5gb-1500"),
    ("N2500 6GB - 30 days", "mtn-3.5gb-2500"),
    ("N3000 8GB - 30 days", "mtn-6.75gb-3000"),
    ("N3500 10GB - 30 days", "mtn-5.5gb-3500"),
    ("N5000 15GB - 30 days", "mtn-14.5gb-5000"),
    ("N6000 20GB - 30 days", "mtn-data-6500"),
    ("N10000 40GB - 30 days", "mtn-34gb-30-10000"),
    ("N15000 75GB - 30 days", "mtn-75gb-20000"),
    ("N20000 110GB - 30 days", "mtn-20gb-7500"),
    ("N1500 3GB - 30 days", "mtn-xtra-1000"),
    ("N10000 25GB SME - 1 month", "mtn-25gb-9000"),
    ("N50000 165GB SME - 2 months", "mtn-165gb-35000"),
    ("N100000 360GB SME - 3 months", "mtn-480gb-90000"),
    ("N450000 4.5TB - 1 year", "mtn-1500gb-yearly"),
    ("N110000 1TB - 1 year", "mtn-1500gb-yearly"),
    ("N600 2.5GB - 2 days", "mtn-2-5gb-ex-600"),
    ("N22000 120GB + 80mins - 30 days", "mtn-120gb-24000"),
    ("N20000 100GB - 2 months", "mtn-150gb-40000"),
    ("N30000 160GB - 2 months", "mtn-150gb-30000"),
    ("N50000 400GB - 3 months", "mtn-480gb-90000"),
    ("N75000 600GB - 3 months", "mtn-hynetflex-75000-90"),
    ("N300 Xtratalk Weekly", "mtn-xtrabundle-500"),
    ("N500 Xtratalk Weekly", "mtn-xtrabundle-500"),
    ("N1000 Xtratalk Monthly", "mtn-xtra-1000"),
    ("N2000 Xtratalk Monthly", "mtn-2.7gb-2000"),
    ("N5000 Xtratalk Monthly", "mtn-14.5gb-5000"),
    ("N10000 Xtratalk Monthly", "mtn-34gb-30-10000"),
    ("N15000 Xtratalk Monthly", "mtn-75gb-20000"),
    ("N20000 Xtratalk Monthly", "mtn-20gb-7500"),
    ("N800 3GB - 2 days", "mtn-3.2gb-1000"),
    ("N2000 7GB - 7 days", "mtn-7gb-3000"),
    ("N200 Xtradata", "mtn-230mb-200"),
]

AIRTEL_PLANS = [
    ("N50 25MB - 1 day", "airt-50"),
    ("N100 75MB - 1 day", "airt-100"),
    ("N200 200MB - 3 days", "airt-200"),
    ("N300 350MB - 7 days", "airt-social-300-3"),
    ("N500 750MB - 14 days", "airt-500"),
    ("N1000 1.5GB - 30 days", "airt-1000-7"),
    ("N1500 3GB - 30 days", "airt-1500-30"),
    ("N2000 4.5GB - 30 days", "airt-2000"),
    ("N3000 8GB - 30 days", "airt-3000"),
    ("N4000 11GB - 30 days", "airt-4000"),
    ("N5000 15GB - 30 days", "airt-5000"),
    ("N1500 6GB Binge - 7 days", "airt-1500-2"),
    ("N10000 40GB - 30 days", "airt-10000"),
    ("N15000 75GB - 30 days", "airt-15000"),
    ("N20000 110GB - 30 days", "airt-20000"),
    ("N600 1GB - 14 days", "airt-600"),
    ("N1000 1.5GB - 7 days", "airt-1000-7"),
    ("N2000 7GB - 7 days", "airt-2500-7"),
    ("N5000 25GB - 7 days", "airt-5000-7"),
    ("N400 1.5GB - 1 day", "airt-350-500"),
    ("N800 3.5GB - 2 days", "airt-750-2"),
    ("N6000 23GB - 30 days", "airt-6000-30"),
]

GLO_PLANS = [
    ("N100 105MB - 2 days", "glo-daily-100"),
    ("N200 350MB - 4 days", "glo-2days-200"),
    ("N500 1.05GB - 14 days", "glo-special-500"),
    ("N1000 2.5GB - 30 days", "glo-monthly-1000"),
    ("N2000 5.8GB - 30 days", "glo-monthly-2000"),
    ("N2500 7.7GB - 30 days", "glo-monthly-2500"),
    ("N3000 10GB - 30 days", "glo-monthly-3000"),
    ("N4000 13.25GB - 30 days", "glo-monthly-4000"),
    ("N5000 18.25GB - 30 days", "glo-monthly-5000"),
    ("N8000 29.5GB - 30 days", "glo-monthly-8000"),
    ("N10000 50GB - 30 days", "glo-monthly-10000"),
    ("N15000 93GB - 30 days", "glo-15000-30days"),
    ("N18000 119GB - 30 days", "glo-20000-30days"),
    ("N1500 4.1GB - 30 days", "glo-monthly-1500"),
    ("N20000 138GB - 30 days", "glo-20000-30days"),
    ("N70 200MB SME - 14 days", "glo-dg-99"),
    ("N320 1GB SME - 30 days", "glo-dg-295"),
    ("N960 3GB SME - 30 days", "glo-dg-890"),
    ("N3100 10GB SME - 30 days", "glo-dg-4950"),
    ("N640 2GB SME - 30 days", "glo-dg-495"),
    ("N160 500MB SME - 14 days", "glo-dg-250"),
    ("N1600 5GB SME - 30 days", "glo-dg-2475"),
    ("N50 45MB + 5MB Night - 1 day", "glo-daily-50"),
    ("N100 115MB + 35MB Night - 1 day", "glo-campus-booster-100"),
    ("N200 240MB + 110MB Night - 2 days", "glo-campus-booster-200"),
    ("N500 800MB + 1GB Night - 2 weeks", "glo-campus-booster-500"),
    ("N1000 1.9GB + 2GB Night - 30 days", "glo-campus-booster-1000"),
    ("N1500 3.5GB + 4GB Night - 30 days", "glo-special-1500"),
    ("N2000 5.2GB + 4GB Night - 30 days", "glo-campus-booster-2000"),
    ("N2500 6.8GB + 4GB Night - 30 days", "glo-2000-7days"),
    ("N3000 10GB + 4GB Night - 30 days", "glo-monthly-3000"),
    ("N4000 14GB + 4GB Night - 30 days", "glo-monthly-4000"),
    ("N5000 20GB + 4GB Night - 30 days", "glo-campus-booster-5000"),
    ("N8000 27.5GB + 2GB Night - 30 days", "glo-monthly-8000"),
    ("N10000 46GB + 4GB Night - 30 days", "glo-monthly-10000"),
    ("N15000 86GB + 7GB Night - 30 days", "glo-15000-30days"),
    ("N18000 109GB + 10GB Night - 30 days", "glo-20000-30days"),
    ("N20000 126GB + 12GB Night - 30 days", "glo-20000-30days"),
    ("N300 1GB Special", "glo-social-oneoff-300"),
    ("N500 2GB Special", "glo-special-500"),
]

ETISALAT_PLANS = [
    ("N100 100MB - 1 day", "9mobile-sme-data-100mb"),
    ("N200 650MB - 1 day", "9mobile-sme-data-200mb"),
    ("N500 500MB - 30 days", "9mobile-sme-data-500mb"),
    ("N1000 1.5GB - 30 days", "9mobile-sme-data-1gb"),
    ("N2000 4.5GB - 30 days", "9mobile-sme-data-2gb"),
    ("N5000 15GB - 30 days", "9mobile-sme-data-5gb"),
    ("N10000 40GB - 30 days", "9mobile-sme-data-10gb"),
    ("N15000 75GB - 30 days", "9mobile-sme-data-15gb"),
    ("N27500 30GB - 90 days", "9mobile-sme-data-25gb"),
    ("N55000 60GB - 180 days", "9mobile-sme-data-50gb"),
    ("N110000 120GB - 365 days", "9mobile-sme-data-100gb"),
    ("N300 1GB + 100MB - 1 day", "9mobile-sme-data-1gb"),
    ("N2500 11GB - 30 days", "9mobile-sme-data-20gb"),
    ("N7000 35GB - 30 days", "9mobile-sme-data-25gb"),
    ("N20000 125GB - 30 days", "9mobile-sme-data-100gb"),
    ("N1000 4GB - 30 days", "9mobile-sme-data-1gb"),
    ("N1500 7GB - 7 days", "9mobile-sme-data-10gb"),
    ("N150 200MB - 1 day", "9mobile-sme-data-200mb"),
]

EXAM_TYPES = [("utme-mock", "utme-mock"), ("utme-no-mock", "utme-no-mock")]
METER_TYPES = [("prepaid", "prepaid"), ("postpaid", "postpaid")]
BILLER_NAME = [
    ("ikeja-electric", "ikeja-electric"),
    ("eko-electric", "eko-electric"),
    ("kano-electric", "kano-electric"),
    ("portharcourt-electric", "portharcourt-electric"),
    ("jos-electric", "jos-electric"),
    ("ibadan-electric", "ibadan-electric"),
    ("kaduna-electric", "kaduna-electric"),
    ("abuja-electric", "abuja-electric"),
    ("enugu-electric", "enugu-electric"),
    ("benin-electric", "benin-electric"),
    ("aba-electric", "aba-electric"),
    ("yola-electric", "yola-electric"),
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
    ("DStv Compact + French Touch + ExtraView N12,700", "DStv Compact + French Touch + ExtraView N12,700"),
    ("DStv Compact + Asia + ExtraView N16,600", "DStv Compact + Asia + ExtraView N16,600"),
    ("DStv Compact Plus + French Plus N20,500", "DStv Compact Plus + French Plus N20,500"),
    ("DStv Compact Plus + French Touch N14,700", "DStv Compact Plus + French Touch N14,700"),
    ("DStv Compact Plus - Extra View N14,900", "DStv Compact Plus - Extra View N14,900"),
    ("DStv Compact Plus + FrenchPlus + Extra View N23,000", "DStv Compact Plus + FrenchPlus + Extra View N23,000"),
    ("DStv Compact + French Plus N16,000", "DStv Compact + French Plus N16,000"),
    ("DStv Compact Plus + Asia + ExtraView N21,100", "DStv Compact Plus + Asia + ExtraView N21,100"),
    ("DStv Premium + Asia + Extra View N23,000", "DStv Premium + Asia + Extra View N23,000"),
    ("DStv Premium + French + Extra View N28,000", "DStv Premium + French + Extra View N28,000"),
    ("DStv HDPVR Access Service N2,500", "DStv HDPVR Access Service N2,500"),
    ("DStv French Plus Add-on N8,100", "DStv French Plus Add-on N8,100"),
    ("DStv Asian Add-on N6,200", "DStv Asian Add-on N6,200"),
    ("DStv French Touch Add-on N2,300", "DStv French Touch Add-on N2,300"),
    ("ExtraView Access N2,500", "ExtraView Access N2,500"),
    ("DStv French 11 N3,260", "DStv French 11 N3,260"),
    ("DStv Asian Bouquet E36 N12,400", "DStv Asian Bouquet E36 N12,400"),
    ("DStv Yanga + Showmax N6,550", "DStv Yanga + Showmax N6,550"),
    ("DStv Great Wall Standalone Bouquet + Showmax N6,625", "DStv Great Wall Standalone Bouquet + Showmax N6,625"),
    ("DStv Compact Plus + Showmax N26,450", "DStv Compact Plus + Showmax N26,450"),
    ("Dstv Confam + Showmax N10,750", "Dstv Confam + Showmax N10,750"),
    ("DStv  Compact + Showmax N17,150", "DStv  Compact + Showmax N17,150"),
    ("DStv Padi + Showmax N7,100", "DStv Padi + Showmax N7,100"),
    ("DStv Premium W/Afr +  ASIAE36 + Showmax N57,500", "DStv Premium W/Afr +  ASIAE36 + Showmax N57,500"),
    ("DStv Asia + Showmax N15,900", "DStv Asia + Showmax N15,900"),
    ("DStv Premium + French + Showmax N57,500", "DStv Premium + French + Showmax N57,500"),
    ("DStv Premium + Showmax N37,000", "DStv Premium + Showmax N37,000"),
    ("DStv Premium Streaming Subscription - N37,000", "DStv Premium Streaming Subscription - N37,000"),
    ("DStv Prestige - N850,000", "DStv Prestige - N850,000"),
    ("DStv Yanga OTT Streaming Subscription - N5,100", "DStv Yanga OTT Streaming Subscription - N5,100"),
    ("DStv Compact Plus Streaming Subscription - N25,000", "DStv Compact Plus Streaming Subscription - N25,000"),
    ("DStv Compact Streaming Subscription - N15,700", "DStv Compact Streaming Subscription - N15,700"),
    ("DStv Comfam Streaming Subscription - N9,300", "DStv Comfam Streaming Subscription - N9,300"),
    ("DStv Indian N12,400", "DStv Indian N12,400"),
    ("DStv Premium East Africa and Indian N16530", "DStv Premium East Africa and Indian N16530"),
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
    ("DStv Compact Plus + French + Xtraview - N39,000", "DStv Compact Plus + French + Xtraview - N39,000"),
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

SUB_TYPE = [("change", "change"), ("renew", "renew")]

SHOWMAX_PLANS = [
    ("Full - N8,400 - 3 Months", "Full - N8,400 - 3 Months"),
    ("Mobile Only - N3,800 - 3 Months", "Mobile Only - N3,800 - 3 Months"),
    ("Sports Mobile Only - N12,000 - 3 Months", "Sports Mobile Only - N12,000 - 3 Months"),
    ("Sports Only - N3,200", "Sports Only - N3,200"),
    ("Sports Only 3 months - N9,600", "Sports Only 3 months - N9,600"),
    ("Full Sports Mobile Only - 3 months - N16,200", "Full Sports Mobile Only - 3 months - N16,200"),
    ("Mobile Only - N6,700 - 6 Months", "Mobile Only - N6,700 - 6 Months"),
    ("Full - 6 months - 14,700", "Full - 6 months - 14,700"),
    ("Full Sports Mobile Only - 6 months - N32,400", "Full Sports Mobile Only - 6 months - N32,400"),
    ("Sports Mobile Only - 6 months - N24,000", "Sports Mobile Only - 6 months - N24,000"),
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
    ("Chinese (Dish) - 19,000 Naira - 1 month", "Chinese (Dish) - 19,000 Naira - 1 month"),
    ("Nova (Antenna) - 1,900 Naira - 1 Month", "Nova (Antenna) - 1,900 Naira - 1 Month"),
    ("Classic (Dish) - 2300 Naira - 1 Week", "Classic (Dish) - 2300 Naira - 1 Week"),
    ("Classic (Dish) - 6800 Naira - 1 Month", "Classic (Dish) - 6800 Naira - 1 Month"),
    ("Nova (Dish) - 650 Naira - 1 Week", "Nova (Dish) - 650 Naira - 1 Week"),
    ("Super (Antenna) - 3,000 Naira - 1 Week", "Super (Antenna) - 3,000 Naira - 1 Week"),
    ("Super (Antenna) - 8,800 Naira - 1 Month", "Super (Antenna) - 8,800 Naira - 1 Month"),
    ("Global (Dish) - 19000 Naira - 1 Month", "Global (Dish) - 19000 Naira - 1 Month"),
    ("Global (Dish) - 6500 Naira - 1Week", "Global (Dish) - 6500 Naira - 1Week"),
]

class AirtimeTopUp(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE, related_name="airtime_topups")
    amount = models.IntegerField()
    network = models.CharField(max_length=10, choices=NETWORK_TYPES)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class MTNDataTopUp(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE, related_name="mtn_data_topups")
    plan = models.CharField(max_length=50, choices=MTN_PLANS)
    billersCode = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class AirtelDataTopUp(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE, related_name="airtel_data_topups")
    plan = models.CharField(max_length=100, choices=AIRTEL_PLANS)
    billersCode = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class GloDataTopUp(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE, related_name="glo_data_topups")
    plan = models.CharField(max_length=100, choices=GLO_PLANS)
    billersCode = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class EtisalatDataTopUp(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE, related_name="etisalat_data_topups")
    plan = models.CharField(max_length=100, choices=ETISALAT_PLANS)
    billersCode = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class DSTVPayment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE, related_name="dstv_payments")
    billersCode = models.CharField(max_length=20)
    dstv_plan = models.CharField(max_length=100, choices=DSTV_PLANS)
    subscription_type = models.CharField(max_length=20, choices=SUB_TYPE)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class GOTVPayment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE, related_name="gotv_payments")
    billersCode = models.CharField(max_length=20)
    gotv_plan = models.CharField(max_length=100, choices=GOTV_PLANS)
    subscription_type = models.CharField(max_length=20, choices=SUB_TYPE)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class StartimesPayment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE, related_name="startimes_payments")
    billersCode = models.CharField(max_length=20)
    startimes_plan = models.CharField(max_length=100, choices=STARTIMES_PLANS)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class ShowMaxPayment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE, related_name="showmax_payments")
    showmax_plan = models.CharField(max_length=100, choices=SHOWMAX_PLANS)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class ElectricityPayment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE, related_name="electricity_payments")
    billerCode = models.CharField(max_length=20)
    amount = models.IntegerField()
    biller_name = models.CharField(max_length=30, choices=BILLER_NAME)
    meter_type = models.CharField(max_length=20, choices=METER_TYPES)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class WAECRegitration(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE, related_name="waec_registrations")
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class WAECResultChecker(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE, related_name="waec_result_checks")
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class JAMBRegistration(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE, related_name="jamb_registrations")
    billerCode = models.CharField(max_length=30)
    exam_type = models.CharField(max_length=20, choices=EXAM_TYPES)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class GroupPayment(models.Model):
    PAYMENT_TYPES = [
        ("airtime", "Airtime"),
        ("data", "Data"),
        ("electricity", "Electricity"),
        ("dstv", "DSTV"),
        ("gotv", "GOTV"),
        ("startimes", "Startimes"),
        ("showmax", "ShowMax"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("reversed", "Reversed"),
    ]
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="payments")
    initiated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    service_details = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    vtu_reference = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["-created_at"]
    def __str__(self):
        return f"{self.group.name} - {self.payment_type} - ₦{self.total_amount}"

class GroupPaymentContribution(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("reversed", "Reversed"),
    ]
    group_payment = models.ForeignKey(GroupPayment, on_delete=models.CASCADE, related_name="contributions")
    member = models.ForeignKey(GroupMember, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-created_at"]
    def __str__(self):
        return f"{self.member.user.get_full_name()} - ₦{self.amount}"

class Airtime2Cash(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE, related_name="airtime2cash_records")
    amount = models.IntegerField()
    network = models.CharField(max_length=10, choices=NETWORK_TYPES)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class ElectricityPaymentCustomers(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE, related_name="electricity_customer_lookups")
    biller = models.CharField(max_length=30, choices=BILLER_NAME)
    meter_number = models.CharField(max_length=15)
    meter_type = models.CharField(max_length=20, choices=METER_TYPES)

class Withdrawal(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("failed", "Failed"),
        ("successful", "Successful"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="withdrawal")
    account_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=10)
    bank_code = models.CharField(max_length=10)
    bank_name = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    payment_reference = models.CharField(max_length=100, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    def __str__(self):
        return f"Withdrawal {self.amount} to {self.account_name} {self.account_number} - {self.status}"
    class Meta:
        ordering = ["-created_at"]