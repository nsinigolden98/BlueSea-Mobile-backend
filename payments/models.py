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
    ("N100 100MB - 24 hrs", "N100 100MB - 24 hrs"),
    ("N200 200MB - 2 days", "N200 200MB - 2 days"),
    ("N1000 1.5GB - 30 days", "N1000 1.5GB - 30 days"),
    ("N2000 4.5GB - 30 days", "N2000 4.5GB - 30 days"),
    ("N1500 6GB - 7 days", "N1500 6GB - 7 days"),
    ("N2500 6GB - 30 days", "N2500 6GB - 30 days"),
    ("N3000 8GB - 30 days", "N3000 8GB - 30 days"),
    ("N3500 10GB - 30 days", "N3500 10GB - 30 days"),
    ("N5000 15GB - 30 days", "N5000 15GB - 30 days"),
    ("N6000 20GB - 30 days", "N6000 20GB - 30 days"),
    ("N10000 40GB - 30 days", "N10000 40GB - 30 days"),
    ("N15000 75GB - 30 days", "N15000 75GB - 30 days"),
    ("N20000 110GB - 30 days", "N20000 110GB - 30 days"),
    ("N1500 3GB - 30 days", "N1500 3GB - 30 days"),
    ("N10000 25GB SME - 1 month", "N10000 25GB SME - 1 month"),
    ("N50000 165GB SME - 2 months", "N50000 165GB SME - 2 months"),
    ("N100000 360GB SME - 3 months", "N100000 360GB SME - 3 months"),
    ("N450000 4.5TB - 1 year", "N450000 4.5TB - 1 year"),
    ("N110000 1TB - 1 year", "N110000 1TB - 1 year"),
    ("N600 2.5GB - 2 days", "N600 2.5GB - 2 days"),
    ("N22000 120GB + 80mins - 30 days", "N22000 120GB + 80mins - 30 days"),
    ("N20000 100GB - 2 months", "N20000 100GB - 2 months"),
    ("N30000 160GB - 2 months", "N30000 160GB - 2 months"),
    ("N50000 400GB - 3 months", "N50000 400GB - 3 months"),
    ("N75000 600GB - 3 months", "N75000 600GB - 3 months"),
    ("N300 Xtratalk Weekly", "N300 Xtratalk Weekly"),
    ("N500 Xtratalk Weekly", "N500 Xtratalk Weekly"),
    ("N1000 Xtratalk Monthly", "N1000 Xtratalk Monthly"),
    ("N2000 Xtratalk Monthly", "N2000 Xtratalk Monthly"),
    ("N5000 Xtratalk Monthly", "N5000 Xtratalk Monthly"),
    ("N10000 Xtratalk Monthly", "N10000 Xtratalk Monthly"),
    ("N15000 Xtratalk Monthly", "N15000 Xtratalk Monthly"),
    ("N20000 Xtratalk Monthly", "N20000 Xtratalk Monthly"),
    ("N800 3GB - 2 days", "N800 3GB - 2 days"),
    ("N2000 7GB - 7 days", "N2000 7GB - 7 days"),
    ("N200 Xtradata", "N200 Xtradata"),
]

AIRTEL_PLANS = [
    ("N50 25MB - 1 day", "N50 25MB - 1 day"),
    ("N100 75MB - 1 day", "N100 75MB - 1 day"),
    ("N200 200MB - 3 days", "N200 200MB - 3 days"),
    ("N300 350MB - 7 days", "N300 350MB - 7 days"),
    ("N500 750MB - 14 days", "N500 750MB - 14 days"),
    ("N1000 1.5GB - 30 days", "N1000 1.5GB - 30 days"),
    ("N1500 3GB - 30 days", "N1500 3GB - 30 days"),
    ("N2000 4.5GB - 30 days", "N2000 4.5GB - 30 days"),
    ("N3000 8GB - 30 days", "N3000 8GB - 30 days"),
    ("N4000 11GB - 30 days", "N4000 11GB - 30 days"),
    ("N5000 15GB - 30 days", "N5000 15GB - 30 days"),
    ("N1500 6GB Binge - 7 days", "N1500 6GB Binge - 7 days"),
    ("N10000 40GB - 30 days", "N10000 40GB - 30 days"),
    ("N15000 75GB - 30 days", "N15000 75GB - 30 days"),
    ("N20000 110GB - 30 days", "N20000 110GB - 30 days"),
    ("N600 1GB - 14 days", "N600 1GB - 14 days"),
    ("N1000 1.5GB - 7 days", "N1000 1.5GB - 7 days"),
    ("N2000 7GB - 7 days", "N2000 7GB - 7 days"),
    ("N5000 25GB - 7 days", "N5000 25GB - 7 days"),
    ("N400 1.5GB - 1 day", "N400 1.5GB - 1 day"),
    ("N800 3.5GB - 2 days", "N800 3.5GB - 2 days"),
    ("N6000 23GB - 30 days", "N6000 23GB - 30 days"),
]

GLO_PLANS = [
    ("N100 105MB - 2 days", "N100 105MB - 2 days"),
    ("N200 350MB - 4 days", "N200 350MB - 4 days"),
    ("N500 1.05GB - 14 days", "N500 1.05GB - 14 days"),
    ("N1000 2.5GB - 30 days", "N1000 2.5GB - 30 days"),
    ("N2000 5.8GB - 30 days", "N2000 5.8GB - 30 days"),
    ("N2500 7.7GB - 30 days", "N2500 7.7GB - 30 days"),
    ("N3000 10GB - 30 days", "N3000 10GB - 30 days"),
    ("N4000 13.25GB - 30 days", "N4000 13.25GB - 30 days"),
    ("N5000 18.25GB - 30 days", "N5000 18.25GB - 30 days"),
    ("N8000 29.5GB - 30 days", "N8000 29.5GB - 30 days"),
    ("N10000 50GB - 30 days", "N10000 50GB - 30 days"),
    ("N15000 93GB - 30 days", "N15000 93GB - 30 days"),
    ("N18000 119GB - 30 days", "N18000 119GB - 30 days"),
    ("N1500 4.1GB - 30 days", "N1500 4.1GB - 30 days"),
    ("N20000 138GB - 30 days", "N20000 138GB - 30 days"),
    ("N70 200MB SME - 14 days", "N70 200MB SME - 14 days"),
    ("N320 1GB SME - 30 days", "N320 1GB SME - 30 days"),
    ("N960 3GB SME - 30 days", "N960 3GB SME - 30 days"),
    ("N3100 10GB SME - 30 days", "N3100 10GB SME - 30 days"),
    ("N640 2GB SME - 30 days", "N640 2GB SME - 30 days"),
    ("N160 500MB SME - 14 days", "N160 500MB SME - 14 days"),
    ("N1600 5GB SME - 30 days", "N1600 5GB SME - 30 days"),
    ("N50 45MB + 5MB Night - 1 day", "N50 45MB + 5MB Night - 1 day"),
    ("N100 115MB + 35MB Night - 1 day", "N100 115MB + 35MB Night - 1 day"),
    ("N200 240MB + 110MB Night - 2 days", "N200 240MB + 110MB Night - 2 days"),
    ("N500 800MB + 1GB Night - 2 weeks", "N500 800MB + 1GB Night - 2 weeks"),
    ("N1000 1.9GB + 2GB Night - 30 days", "N1000 1.9GB + 2GB Night - 30 days"),
    ("N1500 3.5GB + 4GB Night - 30 days", "N1500 3.5GB + 4GB Night - 30 days"),
    ("N2000 5.2GB + 4GB Night - 30 days", "N2000 5.2GB + 4GB Night - 30 days"),
    ("N2500 6.8GB + 4GB Night - 30 days", "N2500 6.8GB + 4GB Night - 30 days"),
    ("N3000 10GB + 4GB Night - 30 days", "N3000 10GB + 4GB Night - 30 days"),
    ("N4000 14GB + 4GB Night - 30 days", "N4000 14GB + 4GB Night - 30 days"),
    ("N5000 20GB + 4GB Night - 30 days", "N5000 20GB + 4GB Night - 30 days"),
    ("N8000 27.5GB + 2GB Night - 30 days", "N8000 27.5GB + 2GB Night - 30 days"),
    ("N10000 46GB + 4GB Night - 30 days", "N10000 46GB + 4GB Night - 30 days"),
    ("N15000 86GB + 7GB Night - 30 days", "N15000 86GB + 7GB Night - 30 days"),
    ("N18000 109GB + 10GB Night - 30 days", "N18000 109GB + 10GB Night - 30 days"),
    ("N20000 126GB + 12GB Night - 30 days", "N20000 126GB + 12GB Night - 30 days"),
    ("N300 1GB Special", "N300 1GB Special"),
    ("N500 2GB Special", "N500 2GB Special"),
]

ETISALAT_PLANS = [
    ("N100 100MB - 1 day", "N100 100MB - 1 day"),
    ("N200 650MB - 1 day", "N200 650MB - 1 day"),
    ("N500 500MB - 30 days", "N500 500MB - 30 days"),
    ("N1000 1.5GB - 30 days", "N1000 1.5GB - 30 days"),
    ("N2000 4.5GB - 30 days", "N2000 4.5GB - 30 days"),
    ("N5000 15GB - 30 days", "N5000 15GB - 30 days"),
    ("N10000 40GB - 30 days", "N10000 40GB - 30 days"),
    ("N15000 75GB - 30 days", "N15000 75GB - 30 days"),
    ("N27500 30GB - 90 days", "N27500 30GB - 90 days"),
    ("N55000 60GB - 180 days", "N55000 60GB - 180 days"),
    ("N110000 120GB - 365 days", "N110000 120GB - 365 days"),
    ("N300 1GB + 100MB - 1 day", "N300 1GB + 100MB - 1 day"),
    ("N2500 11GB - 30 days", "N2500 11GB - 30 days"),
    ("N7000 35GB - 30 days", "N7000 35GB - 30 days"),
    ("N20000 125GB - 30 days", "N20000 125GB - 30 days"),
    ("N1000 4GB - 30 days", "N1000 4GB - 30 days"),
    ("N1500 7GB - 7 days", "N1500 7GB - 7 days"),
    ("N150 200MB - 1 day", "N150 200MB - 1 day"),
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
    ("renew", "renew"),
]

SHOWMAX_PLANS = [
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
    network = models.CharField(max_length=10, choices=NETWORK_TYPES)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class MTNDataTopUp(models.Model):
    plan = models.CharField(max_length=50, choices=MTN_PLANS)
    billersCode = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AirtelDataTopUp(models.Model):
    plan = models.CharField(max_length=100, choices=AIRTEL_PLANS)
    billersCode = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class GloDataTopUp(models.Model):
    plan = models.CharField(max_length=100, choices=GLO_PLANS)
    billersCode = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class EtisalatDataTopUp(models.Model):
    plan = models.CharField(max_length=100, choices=ETISALAT_PLANS)
    billersCode = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class DSTVPayment(models.Model):
    billersCode = models.CharField(max_length=20)
    dstv_plan = models.CharField(max_length=100, choices=DSTV_PLANS)
    subscription_type = models.CharField(max_length=20, choices=SUB_TYPE)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class GOTVPayment(models.Model):
    billersCode = models.CharField(max_length=20)
    gotv_plan = models.CharField(max_length=100, choices=GOTV_PLANS)
    subscription_type = models.CharField(max_length=20, choices=SUB_TYPE)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class StartimesPayment(models.Model):
    billersCode = models.CharField(max_length=20)
    startimes_plan = models.CharField(max_length=100, choices=STARTIMES_PLANS)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ShowMaxPayment(models.Model):
    showmax_plan = models.CharField(max_length=100, choices=SHOWMAX_PLANS)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ElectricityPayment(models.Model):
    billerCode = models.CharField(max_length=20)
    amount = models.IntegerField()
    biller_name = models.CharField(max_length=30, choices=BILLER_NAME)
    meter_type = models.CharField(max_length=20, choices=METER_TYPES)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class WAECRegitration(models.Model):
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class WAECResultChecker(models.Model):
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class JAMBRegistration(models.Model):
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
    service_details = models.JSONField()  # for phone number, meter number, etc.
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

    group_payment = models.ForeignKey(
        GroupPayment, on_delete=models.CASCADE, related_name="contributions"
    )
    member = models.ForeignKey(GroupMember, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.member.user.get_full_name()} - ₦{self.amount}"


class Airtime2Cash(models.Model):
    amount = models.IntegerField()
    network = models.CharField(max_length=10, choices=NETWORK_TYPES)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ElectricityPaymentCustomers(models.Model):
    biller = models.CharField(max_length=30, choices=BILLER_NAME)
    meter_number = models.CharField(max_length=15)
    meter_type = models.CharField(max_length=20, choices=METER_TYPES)


class Withdrawal(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("failed", "Failed"),
        ("successful", "Successful"),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="withdrawal"
    )
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
