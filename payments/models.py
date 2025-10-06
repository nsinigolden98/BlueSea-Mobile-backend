from django.db import models
from django.contrib.auth import get_user_model
from group_payment.models import Group, GroupMember

User = get_user_model()

NETWORK_TYPES = [
        ('mtn', 'mtn'),
        ('airtel', 'airtel'),
        ('glo', 'glo'),
        ('etisalat', 'etisalat'),
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
    (
        "MTN N10,000 25GB SME Mobile Data ( 1 Month)",
        "MTN N10,000 25GB SME Mobile Data ( 1 Month)",
    ),
    (
        "MTN N50,000 165GB SME Mobile Data (2-Months)",
        "MTN N50,000 165GB SME Mobile Data (2-Months)",
    ),
    (
        "MTN N100,000 360GB SME Mobile Data (3 Months)",
        "MTN N100,000 360GB SME Mobile Data (3 Months)",
    ),
    (
        "MTN N450,000 4.5TB Mobile Data (1 Year)",
        "MTN N450,000 4.5TB Mobile Data (1 Year)",
    ),
    ("MTN N100,000 1TB Mobile Data (1 Year)", "MTN N100,000 1TB Mobile Data (1 Year)"),
    ("MTN N600 2.5GB - 2 days", "MTN N600 2.5GB - 2 days"),
    (
        "MTN N22000 120GB Monthly Plan + 80mins",
        "MTN N22000 120GB Monthly Plan + 80mins",
    ),
    ("MTN 100GB 2-Month Plan", "MTN 100GB 2-Month Plan"),
    ("MTN N30,000 160GB 2-Month Plan", "MTN N30,000 160GB 2-Month Plan"),
    ("MTN N50,000 400GB 3-Month Plan", "MTN N50,000 400GB 3-Month Plan"),
    ("MTN N75,000 600GB 3-Months Plan", "MTN N75,000 600GB 3-Months Plan"),
    ("MTN N300 Xtratalk Weekly Bundle", "MTN N300 Xtratalk Weekly Bundle"),
    ("MTN N500 Xtratalk Weekly Bundle", "MTN N500 Xtratalk Weekly Bundle"),
    ("MTN N1000 Xtratalk Monthly Bundle", "MTN N1000 Xtratalk Monthly Bundle"),
    ("MTN N2000 Xtratalk Monthly Bundle", "MTN N2000 Xtratalk Monthly Bundle"),
    ("MTN N5000 Xtratalk Monthly Bundle", "MTN N5000 Xtratalk Monthly Bundle"),
    ("MTN N10000 Xtratalk Monthly Bundle", "MTN N10000 Xtratalk Monthly Bundle"),
    ("MTN N15000 Xtratalk Monthly Bundle", "MTN N15000 Xtratalk Monthly Bundle"),
    ("MTN N20000 Xtratalk Monthly Bundle", "MTN N20000 Xtratalk Monthly Bundle"),
    ("MTN N800 3GB - 2 days", "MTN N800 3GB - 2 days"),
    ("MTN N2000 7GB - 7 days", "MTN N2000 7GB - 7 days"),
    ("MTN N200 Xtradata", "MTN N200 Xtradata"),
    ("MTN N200 Xtratalk - 3 days", "MTN N200 Xtratalk - 3 days"),
]

AIRTEL_PLANS= [
    (
        "Airtel Data Bundle - 50 Naira - 25MB  - 1Day",
        "Airtel Data Bundle - 50 Naira - 25MB  - 1Day",
    ),
    (
        "Airtel Data Bundle - 100 Naira - 75MB - 1Day",
        "Airtel Data Bundle - 100 Naira - 75MB - 1Day",
    ),
    (
        "Airtel Data Bundle - 200 Naira - 200MB - 3Days",
        "Airtel Data Bundle - 200 Naira - 200MB - 3Days",
    ),
    (
        "Airtel Data Bundle - 300 Naira - 350MB - 7 Days",
        "Airtel Data Bundle - 300 Naira - 350MB - 7 Days",
    ),
    (
        "Airtel Data Bundle - 500 Naira - 750MB - 14 Days",
        "Airtel Data Bundle - 500 Naira - 750MB - 14 Days",
    ),
    (
        "Airtel Data Bundle - 1,000 Naira - 1.5GB - 30 Days",
        "Airtel Data Bundle - 1,000 Naira - 1.5GB - 30 Days",
    ),
    (
        "Airtel Data Bundle - 1,500 Naira - 3GB - 30 Days",
        "Airtel Data Bundle - 1,500 Naira - 3GB - 30 Days",
    ),
    (
        "Airtel Data Bundle - 2,000 Naira - 4.5GB - 30 Days",
        "Airtel Data Bundle - 2,000 Naira - 4.5GB - 30 Days",
    ),
    (
        "Airtel Data Bundle - 3,000 Naira - 8GB - 30 Days",
        "Airtel Data Bundle - 3,000 Naira - 8GB - 30 Days",
    ),
    (
        "Airtel Data Bundle - 4,000 Naira - 11GB - 30 Days",
        "Airtel Data Bundle - 4,000 Naira - 11GB - 30 Days",
    ),
    (
        "Airtel Data Bundle - 5,000 Naira - 15GB - 30 Days",
        "Airtel Data Bundle - 5,000 Naira - 15GB - 30 Days",
    ),
    (
        "Airtel Binge Data - 1,500 Naira (7 Days) - 6GB",
        "Airtel Binge Data - 1,500 Naira (7 Days) - 6GB",
    ),
    (
        "Airtel Data Bundle - 10,000 Naira - 40GB - 30 Days",
        "Airtel Data Bundle - 10,000 Naira - 40GB - 30 Days",
    ),
    (
        "Airtel Data Bundle - 15,000 Naira - 75GB - 30 Days",
        "Airtel Data Bundle - 15,000 Naira - 75GB - 30 Days",
    ),
    (
        "Airtel Data Bundle - 20,000 Naira - 110GB - 30 Days",
        "Airtel Data Bundle - 20,000 Naira - 110GB - 30 Days",
    ),
    (
        "Airtel Data - 600 Naira - 1GB - 14 days",
        "Airtel Data - 600 Naira - 1GB - 14 days",
    ),
    (
        "Airtel Data - 1000 Naira - 1.5GB - 7 days",
        "Airtel Data - 1000 Naira - 1.5GB - 7 days",
    ),
    (
        "Airtel Data - 2000 Naira - 7GB - 7 days",
        "Airtel Data - 2000 Naira - 7GB - 7 days",
    ),
    (
        "Airtel Data - 5000 Naira - 25GB - 7 days",
        "Airtel Data - 5000 Naira - 25GB - 7 days",
    ),
    (
        "Airtel Data - 400 Naira - 1.5GB - 1 day",
        "Airtel Data - 400 Naira - 1.5GB - 1 day",
    ),
    (
        "Airtel Data - 800 Naira - 3.5GB - 2 days",
        "Airtel Data - 800 Naira - 3.5GB - 2 days",
    ),
    (
        "Airtel Data - 6000 Naira - 23GB - 30 days",
        "Airtel Data - 6000 Naira - 23GB - 30 days",
    ),
    ("600 Naira Voice Bundle", "600 Naira Voice Bundle"),
    ("1200 Naira Voice Bundle", "1200 Naira Voice Bundle"),
    ("3000 Naira Voice Bundle", "3000 Naira Voice Bundle"),
    ("6000 Naira Voice Bundle", "6000 Naira Voice Bundle"),
]

GLO_PLANS= [
    ("Glo Data N100 -  105MB - 2 day", "Glo Data N100 -  105MB - 2 day"),
    ("Glo Data N200 -  350MB - 4 days", "Glo Data N200 -  350MB - 4 days"),
    ("Glo Data N500 -  1.05GB - 14 days", "Glo Data N500 -  1.05GB - 14 days"),
    ("Glo Data N1000 -  2.5GB - 30 days", "Glo Data N1000 -  2.5GB - 30 days"),
    ("Glo Data N2000 -  5.8GB - 30 days", "Glo Data N2000 -  5.8GB - 30 days"),
    ("Glo Data N2500 -  7.7GB - 30 days", "Glo Data N2500 -  7.7GB - 30 days"),
    ("Glo Data N3000 -  10GB - 30 days", "Glo Data N3000 -  10GB - 30 days"),
    ("Glo Data N4000 -  13.25GB - 30 days", "Glo Data N4000 -  13.25GB - 30 days"),
    ("Glo Data N5000 -  18.25GB - 30 days", "Glo Data N5000 -  18.25GB - 30 days"),
    ("Glo Data N8000 -  29.5GB - 30 days", "Glo Data N8000 -  29.5GB - 30 days"),
    ("Glo Data N10000 -  50GB - 30 days", "Glo Data N10000 -  50GB - 30 days"),
    ("Glo Data N15000 -  93GB - 30 days", "Glo Data N15000 -  93GB - 30 days"),
    ("Glo Data N18000 -  119GB - 30 days", "Glo Data N18000 -  119GB - 30 days"),
    ("Glo Data N1500 -  4.1GB - 30 days", "Glo Data N1500 -  4.1GB - 30 days"),
    ("Glo Data N20000 -  138GB - 30 days", "Glo Data N20000 -  138GB - 30 days"),
    ("Glo Data (SME) N70 -  200MB - 14 days", "Glo Data (SME) N70 -  200MB - 14 days"),
    ("Glo Data (SME) N320 - 1GB 30 days", "Glo Data (SME) N320 - 1GB 30 days"),
    ("Glo Data (SME) N960 - 3GB 30 days", "Glo Data (SME) N960 - 3GB 30 days"),
    ("Glo Data (SME) N3100 - 10GB - 30 Days", "Glo Data (SME) N3100 - 10GB - 30 Days"),
    ("Glo Data (SME) N640 - 2GB 30 days", "Glo Data (SME) N640 - 2GB 30 days"),
    ("Glo Data (SME) N160 - 500MB 14 days", "Glo Data (SME) N160 - 500MB 14 days"),
    ("Glo Data (SME) N1600 - 5GB 30 days", "Glo Data (SME) N1600 - 5GB 30 days"),
    ("45MB + 5MB Night N50 Oneoff", "45MB + 5MB Night N50 Oneoff"),
    ("115Mb + 35MB Night N100 Oneoff", "115Mb + 35MB Night N100 Oneoff"),
    ("240MB + 110MB Night N200 Oneoff", "240MB + 110MB Night N200 Oneoff"),
    ("800MB + 1GB Night N500 Oneoff", "800MB + 1GB Night N500 Oneoff"),
    ("1.9GB + 2GB Night N1000 Oneoff", "1.9GB + 2GB Night N1000 Oneoff"),
    ("3.5GB + 4GB Night N1500 Oneoff", "3.5GB + 4GB Night N1500 Oneoff"),
    ("5.2GB + 4GB Night N2000 Oneoff", "5.2GB + 4GB Night N2000 Oneoff"),
    ("6.8GB + 4GB Night N2500 Oneoff", "6.8GB + 4GB Night N2500 Oneoff"),
    ("10GB +4GB Night N3000 Oneoff", "10GB +4GB Night N3000 Oneoff"),
    ("14GB + 4GB Night N4000 Oneoff", "14GB + 4GB Night N4000 Oneoff"),
    ("20GB + 4GB Night N5000 Oneoff", "20GB + 4GB Night N5000 Oneoff"),
    ("27.5GB + 2GB Night N8000 Oneoff", "27.5GB + 2GB Night N8000 Oneoff"),
    ("46GB + 4GB N10000 Oneoff", "46GB + 4GB N10000 Oneoff"),
    ("86GB + 7GB N15000 Oneoff", "86GB + 7GB N15000 Oneoff"),
    ("109GB + 10Gb N18000 Oneoff", "109GB + 10Gb N18000 Oneoff"),
    ("126GB + 12GB N20000 Oneoff", "126GB + 12GB N20000 Oneoff"),
    ("N300 1GB Special", "N300 1GB Special"),
    ("N500 2GB Special", "N500 2GB Special"),
    ("N1500 7GB Special", "N1500 7GB Special"),
    ("N500 3GB Weekend", "N500 3GB Weekend"),
    ("N30000 225GB Glo Mega Oneoff", "N30000 225GB Glo Mega Oneoff"),
    ("N36000 300GB Glo Mega Oneoff", "N36000 300GB Glo Mega Oneoff"),
    ("N50000 425GB Glo Mega Oneoff", "N50000 425GB Glo Mega Oneoff"),
    ("N60000 525GB Glo Mega Oneoff", "N60000 525GB Glo Mega Oneoff"),
    ("N75000 675GB Glo Mega Oneoff", "N75000 675GB Glo Mega Oneoff"),
    ("N100000 1TB Glo Mega Oneoff", "N100000 1TB Glo Mega Oneoff"),
    ("Glo TV VOD 500 MB 3days Oneoff", "Glo TV VOD 500 MB 3days Oneoff"),
    ("Glo TV VOD 2GB 7days Oneoff", "Glo TV VOD 2GB 7days Oneoff"),
    ("Glo TV VOD 6GB 30days Oneoff", "Glo TV VOD 6GB 30days Oneoff"),
    ("Glo TV Lite 2GB Oneoff", "Glo TV Lite 2GB Oneoff"),
    ("Glo TV Max 6 GB Oneoff", "Glo TV Max 6 GB Oneoff"),
    ("WTF N25 100MB Oneoff", "WTF N25 100MB Oneoff"),
    ("WTF N50 200MB Oneoff", "WTF N50 200MB Oneoff"),
    ("WTF N100 500MB Oneoff", "WTF N100 500MB Oneoff"),
    ("Telegram N25 20MB Oneoff", "Telegram N25 20MB Oneoff"),
    ("Telegram N50 50MB Oneoff", "Telegram N50 50MB Oneoff"),
    ("Telegram N100 125MB Oneoff", "Telegram N100 125MB Oneoff"),
    ("Instagram N25 20MB Oneoff", "Instagram N25 20MB Oneoff"),
    ("Instagram N50 50MB Oneoff", "Instagram N50 50MB Oneoff"),
    ("Instagram N100 125MB Oneoff", "Instagram N100 125MB Oneoff"),
    ("Tiktok N25 20MB Oneoff", "Tiktok N25 20MB Oneoff"),
    ("Tiktok N50 50MB Oneoff", "Tiktok N50 50MB Oneoff"),
    ("Tiktok N100 125MB Oneoff", "Tiktok N100 125MB Oneoff"),
    ("Opera N25 25MB Oneoff", "Opera N25 25MB Oneoff"),
    ("Opera N50 100MB Oneoff", "Opera N50 100MB Oneoff"),
    ("Opera N100 300MB Oneoff", "Opera N100 300MB Oneoff"),
    ("Youtube N50 100MB Oneoff", "Youtube N50 100MB Oneoff"),
    ("Youtube N100 200MB Oneoff", "Youtube N100 200MB Oneoff"),
    ("Youtube N250 500MB Oneoff", "Youtube N250 500MB Oneoff"),
    ("Youtube N50 500MB Oneoff", "Youtube N50 500MB Oneoff"),
    ("Youtube N130 1.5GB Oneoff", "Youtube N130 1.5GB Oneoff"),
    ("Youtube N50 500MB Night Oneoff", "Youtube N50 500MB Night Oneoff"),
    ("Youtube N200 2GB Night Oneoff", "Youtube N200 2GB Night Oneoff"),
    (
        "Glo MyG N100 400 MB OneOff (Whatsapp, Instagram, Snapchat, Boomplay, Audiomac, GloTV, Tiktok)",
        "Glo MyG N100 400 MB OneOff (Whatsapp, Instagram, Snapchat, Boomplay, Audiomac, GloTV, Tiktok)",
    ),
    (
        "Glo MyG N300 1 GB OneOff (Whatsapp, Instagram, Snapchat, Boomplay, Audiomac, GloTV, Tiktok)",
        "Glo MyG N300 1 GB OneOff (Whatsapp, Instagram, Snapchat, Boomplay, Audiomac, GloTV, Tiktok)",
    ),
    (
        "Glo MyG N500 1.5 GB OneOff (Whatsapp, Instagram, Snapchat, Boomplay, Audiomac, GloTV, Tiktok)",
        "Glo MyG N500 1.5 GB OneOff (Whatsapp, Instagram, Snapchat, Boomplay, Audiomac, GloTV, Tiktok)",
    ),
    (
        "Glo MyG N1000 3.5 GB OneOff (Whatsapp, Instagram, Snapchat, Boomplay, Audiomac, GloTV, Tiktok)",
        "Glo MyG N1000 3.5 GB OneOff (Whatsapp, Instagram, Snapchat, Boomplay, Audiomac, GloTV, Tiktok)",
    ),
]

ETISALAT_PLANS = [
    (
        "9mobile Data - 100 Naira - 100MB - 1 day",
        "9mobile Data - 100 Naira - 100MB - 1 day",
    ),
    (
        "9mobile Data - 200 Naira - 650MB - 1 day",
        "9mobile Data - 200 Naira - 650MB - 1 day",
    ),
    (
        "9mobile Data - 500 Naira - 500MB - 30 Days",
        "9mobile Data - 500 Naira - 500MB - 30 Days",
    ),
    (
        "9mobile Data - 1000 Naira - 1.5GB - 30 days",
        "9mobile Data - 1000 Naira - 1.5GB - 30 days",
    ),
    (
        "9mobile Data - 2000 Naira - 4.5GB Data - 30 Days",
        "9mobile Data - 2000 Naira - 4.5GB Data - 30 Days",
    ),
    (
        "9mobile Data - 5000 Naira - 15GB Data - 30 Days",
        "9mobile Data - 5000 Naira - 15GB Data - 30 Days",
    ),
    (
        "9mobile Data - 10000 Naira - 40GB - 30 days",
        "9mobile Data - 10000 Naira - 40GB - 30 days",
    ),
    (
        "9mobile Data - 15000 Naira - 75GB - 30 Days",
        "9mobile Data - 15000 Naira - 75GB - 30 Days",
    ),
    (
        "9mobile Data - 27,500 Naira - 30GB - 90 days",
        "9mobile Data - 27,500 Naira - 30GB - 90 days",
    ),
    (
        "9mobile Data - 55,000 Naira - 60GB - 180 days",
        "9mobile Data - 55,000 Naira - 60GB - 180 days",
    ),
    (
        "9mobile Data - 110,000 Naira - 120GB - 365 days",
        "9mobile Data - 110,000 Naira - 120GB - 365 days",
    ),
    (
        "9mobile 1GB + 100MB (1 day) - 300 Naira",
        "9mobile 1GB + 100MB (1 day) - 300 Naira",
    ),
    (
        "9mobile 11GB (7GB+ 4GB Night) - 2,500 Naira - 30 days",
        "9mobile 11GB (7GB+ 4GB Night) - 2,500 Naira - 30 days",
    ),
    ("9mobile 35 GB - 7,000 Naira - 30 days", "9mobile 35 GB - 7,000 Naira - 30 days"),
    (
        "9mobile 125GB - 20,000 Naira - 30 days",
        "9mobile 125GB - 20,000 Naira - 30 days",
    ),
    (
        "9mobile 4GB (2GB + 2GB Night) - 1000 Naira",
        "9mobile 4GB (2GB + 2GB Night) - 1000 Naira",
    ),
    ("9mobile 7GB (6GB+1GB Night) - 7 days", "9mobile 7GB (6GB+1GB Night) - 7 days"),
    (
        "9mobile 200MB (100MB + 100MB night) + 300secs - 1 day",
        "9mobile 200MB (100MB + 100MB night) + 300secs - 1 day",
    ),
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
    #group_payment = models.BooleanField()
    request_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
class MTNDataTopUp(models.Model):
    plan = models.CharField(max_length = 50, choices= MTN_PLANS)
    billersCode = models.CharField(max_length = 20)
    phone_number = models.CharField(max_length= 20)
    request_id = models.CharField(max_length = 50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
class AirtelDataTopUp(models.Model):
    plan = models.CharField(max_length = 100, choices= AIRTEL_PLANS)
    billersCode = models.CharField(max_length = 20)
    phone_number = models.CharField(max_length= 20)
    request_id = models.CharField(max_length = 50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
class GloDataTopUp(models.Model):
    plan = models.CharField(max_length = 100, choices= GLO_PLANS)
    billersCode = models.CharField(max_length = 20)
    phone_number = models.CharField(max_length= 20)
    request_id = models.CharField(max_length = 50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
class EtisalatDataTopUp(models.Model):
    plan = models.CharField(max_length = 100, choices= ETISALAT_PLANS)
    billersCode = models.CharField(max_length = 20)
    phone_number = models.CharField(max_length= 20)
    request_id = models.CharField(max_length = 50, unique=True, blank=True, null=True)
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
    
class GroupPayment(models.Model):
    PAYMENT_TYPES = [
        ('airtime', 'Airtime'),
        ('data', 'Data'),
        ('electricity', 'Electricity'),
        ('dstv', 'DSTV'),
        ('gotv', 'GOTV'),
        ('startimes', 'Startimes'),
        ('showmax', 'ShowMax'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('reversed', 'Reversed'),
    ]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='payments')
    initiated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    service_details = models.JSONField()  # for phone number, meter number, etc.
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    vtu_reference = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.group.name} - {self.payment_type} - ₦{self.total_amount}"


class GroupPaymentContribution(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('reversed', 'Reversed'),
    ]

    group_payment = models.ForeignKey(GroupPayment, on_delete=models.CASCADE, related_name='contributions')
    member = models.ForeignKey(GroupMember, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.member.user.get_full_name()} - ₦{self.amount}"