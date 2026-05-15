import uuid
from datetime import datetime
import requests
from django.conf import settings

BASE_URL = settings.VTPASS_BASE_URL

headers = {
    "api-key": settings.VTPASS_API_KEY,
    "public-key": settings.VTPASS_PUBLIC_KEY,
    "secret-key": settings.VTPASS_SECRET_KEY,
    "Content-Type": "application/json",
}

# vtpass.py

# NEW ID-BASED STRUCTURE
mtn_dict = {
    "mtn-10mb-100": {"price": 100, "description": "110MB Daily Plan (1 Day) - N100", "variation_code": "mtn-10mb-100"},
    "mtn-230mb-200": {"price": 200, "description": "230MB Daily Plan (1 Day) - N200", "variation_code": "mtn-230mb-200"},
    "mtn-1500mb-1000": {"price": 1000, "description": "1.5GB Weekly Plan (7 Days) - N1,000", "variation_code": "mtn-1500mb-1000"},
    "mtn-5.5gb-3500": {"price": 3500, "description": "7GB Monthly Plan - N3,500", "variation_code": "mtn-5.5gb-3500"},
    "mtn-3.5gb-1500": {"price": 1500, "description": "3.5GB Weekly Plan (7 Days) - N1,500", "variation_code": "mtn-3.5gb-1500"},
    "mtn-data-6500": {"price": 6500, "description": "16.5GB Monthly Plan", "variation_code": "mtn-data-6500"},
    "mtn-20gb-7500": {"price": 7500, "description": "20GB Monthly Plan", "variation_code": "mtn-20gb-7500"},
    "mtn-32gb-11000": {"price": 11000, "description": "36GB Monthly Plan", "variation_code": "mtn-32gb-11000"},
    "mtn-75gb-20000": {"price": 18000, "description": "75GB Monthly Plan", "variation_code": "mtn-75gb-20000"},
    "mtn-2.7gb-2000": {"price": 2000, "description": "2.7GB + 2mins + 2GB All Night Streaming", "variation_code": "mtn-2.7gb-2000"},
    "mtn-1800mb-1500": {"price": 1500, "description": "1.8GB + 6mins + 5 SMS", "variation_code": "mtn-1800mb-1500"},
    "mtn-120gb-24000": {"price": 24000, "description": "MTN N24,000 120GB - 30days", "variation_code": "mtn-120gb-24000"},
    "mtn-480gb-90000": {"price": 90000, "description": "480GB 3-Month Plan - N90,000", "variation_code": "mtn-480gb-90000"},
    "mtn-1gb-350": {"price": 500, "description": "MTN N500 1GB + 1.5mins - 1 day", "variation_code": "mtn-1gb-350"},
    "mtn-1gb-600": {"price": 800, "description": "1GB+5mins Weekly Plan", "variation_code": "mtn-1gb-600"},
    "mtn-xtrabundle-500": {"price": 500, "description": "600MB Xtra Bundle Weekly Data", "variation_code": "mtn-xtrabundle-500"},
    "mtn-xtra-1000": {"price": 1500, "description": "2GB + 2 Mins Monthly Plan - N1,500", "variation_code": "mtn-xtra-1000"},
    "mtn-11gb-5000": {"price": 5500, "description": "12.5GB Monthly Plan - N5,500", "variation_code": "mtn-11gb-5000"},
    "mtn-2-5gb-900": {"price": 900, "description": "MTN N900 2.5GB - 2 days", "variation_code": "mtn-2-5gb-900"},
    "mtn-150gb-40000": {"price": 40000, "description": "150GB 2-Month Plan", "variation_code": "mtn-150gb-40000"},
    "mtn-11gb-3500": {"price": 3500, "description": "MTN N3,500 11GB - 7 days", "variation_code": "mtn-11gb-3500"},
    "mtn-500mb-ex-350": {"price": 350, "description": "500MB Daily Plan (1 Day) - N350", "variation_code": "mtn-500mb-ex-350"},
    "mtn-2-5gb-ex-600": {"price": 600, "description": "1.5GB Daily Plan (2 Days) - N600", "variation_code": "mtn-2-5gb-ex-600"},
    "mtn-2gb-ex-750": {"price": 750, "description": "2GB Daily Plan (2 Days) - N750", "variation_code": "mtn-2gb-ex-750"},
    "mtn-1500mb-ex-1200": {"price": 3000, "description": "2.7GB Xtra Bundle Monthly Plan", "variation_code": "mtn-1500mb-ex-1200"},
    "mtn-8gb-ex-3000": {"price": 4500, "description": "MTN N4,500 10GB + 10mins - 30 days", "variation_code": "mtn-8gb-ex-3000"},
    "mtn-25gb-9000": {"price": 9000, "description": "MTN N9,000 25GB + Youtube - 30 days", "variation_code": "mtn-25gb-9000"},
    "mtn-65gb-ex-16000": {"price": 16000, "description": "65GB Monthly Plan (30 Days) - N16,000", "variation_code": "mtn-65gb-ex-16000"},
    "mtn-500mb-500": {"price": 500, "description": "500MB + 1GB YouTube (7 Days) - N500", "variation_code": "mtn-500mb-500"},
    "mtn-3.2gb-1000": {"price": 1000, "description": "MTN N1000 3.2GB - 2 days", "variation_code": "mtn-3.2gb-1000"},
    "mtn-7gb-3000": {"price": 2500, "description": "MTN N2500 6GB - 7 days", "variation_code": "mtn-7gb-3000"},
    "mtn-3.5gb-2500": {"price": 2500, "description": "MTN N2500 3.5GB +5mins Monthly Plan", "variation_code": "mtn-3.5gb-2500"},
    "mtn-hynetflex-14500-30": {"price": 14500, "description": "60GB Monthly HyNetFlex Plan", "variation_code": "mtn-hynetflex-14500-30"},
    "mtn-hynetflex-75000-90": {"price": 75000, "description": "450GB 3-Month Broadband Plan", "variation_code": "mtn-hynetflex-75000-90"},
    "mtn-hynetflex-9000-30": {"price": 9000, "description": "30GB Monthly Broadband Plan", "variation_code": "mtn-hynetflex-9000-30"},
    "mtn-2.5-750": {"price": 750, "description": "2.5GB Daily Plan - 750 Naira", "variation_code": "mtn-2.5-750"},
    "mtn-20-5000": {"price": 5000, "description": "20GB Weekly Plan - 5,000 Naira", "variation_code": "mtn-20-5000"},
    "mtn-7gb-1800": {"price": 1800, "description": "MTN N1800 7GB - (2 Days)", "variation_code": "mtn-7gb-1800"},
    "mtn-150gb-30000": {"price": 30000, "description": "MTN N30,000 150GB + 2GB daily", "variation_code": "mtn-150gb-30000"},
    "mtn-165gb-35000": {"price": 35000, "description": "MTN N35,000 165GB Monthly Data Plan", "variation_code": "mtn-165gb-35000"},
    "mtn-200gb-37500": {"price": 37500, "description": "MTN N37,500 200GB + 5GB Youtube", "variation_code": "mtn-200gb-37500"},
    "mtn-260gb-monthly": {"price": 45000, "description": "MTN 260GB + 2GB daily - N45,000", "variation_code": "mtn-260gb-monthly"},
    "mtn-1500gb-yearly": {"price": 225000, "description": "MTN 1.5TB - N225,000 Broadband", "variation_code": "mtn-1500gb-yearly"},
    "mtn-6.75gb-3000": {"price": 3000, "description": "MTN N3000 6.75GB Monthly Plan", "variation_code": "mtn-6.75gb-3000"},
    "mtn-14.5gb-5000": {"price": 5000, "description": "MTN 14.5GB Monthly Plan Monthly", "variation_code": "mtn-14.5gb-5000"},
    "mtn-5.5gb-2-1500": {"price": 1500, "description": "MTN N1500 5.5GB - (2 days)", "variation_code": "mtn-5.5gb-2-1500"},
    "mtn-4gb-2-1200": {"price": 1200, "description": "MTN N1200 4GB - (2 days)", "variation_code": "mtn-4gb-2-1200"},
    "mtn-3.5gb-1-1000": {"price": 1000, "description": "MTN N1000 3.5GB - (1 day)", "variation_code": "mtn-3.5gb-1-1000"},
    "mtn-34gb-30-10000": {"price": 10000, "description": "MTN N10000 34GB - (30 days)", "variation_code": "mtn-34gb-30-10000"},
}


# Updated Airtel Dictionary using IDs as keys
airtel_dict = {
    "airt-50": {"price": 50, "description": "250MB Night Plan - 50 Naira", "variation_code": "airt-50"},
    "airt-100": {"price": 100, "description": "200MB Social Plan - 100 Naira", "variation_code": "airt-100"},
    "airt-200": {"price": 200, "description": "230MB Daily Plan - 200 Naira", "variation_code": "airt-200"},
    "airt-daily-100": {"price": 100, "description": "110MB Daily Plan - 100 Naira", "variation_code": "airt-daily-100"},
    "airt-500": {"price": 500, "description": "500MB Weekly Plan - 500 Naira", "variation_code": "airt-500"},
    "airt-1000-7": {"price": 1000, "description": "1.5GB Weekly Plan - 1,000 Naira", "variation_code": "airt-1000-7"},
    "airt-1500-7": {"price": 1500, "description": "3.5GB Weekly Plan - 1,500 Naira", "variation_code": "airt-1500-7"},
    "airt-2000": {"price": 2000, "description": "3GB Monthly Plan - 2,000 Naira", "variation_code": "airt-2000"},
    "airt-3000": {"price": 3000, "description": "8GB Monthly Plan - 3,000 Naira", "variation_code": "airt-3000"},
    "airt-4000": {"price": 4000, "description": "10GB Monthly Plan - 4,000 Naira", "variation_code": "airt-4000"},
    "airt-5000": {"price": 5000, "description": "13GB Monthly Plan - 5,000 Naira", "variation_code": "airt-5000"},
    "airt-1500-2": {"price": 1500, "description": "5GB Binge Plan - 1,500 Naira", "variation_code": "airt-1500-2"},
    "airt-10000": {"price": 10000, "description": "35GB Monthly Plan - 10,000 Naira", "variation_code": "airt-10000"},
    "airt-15000": {"price": 15000, "description": "60GB Monthly Plan - 15,000 Naira", "variation_code": "airt-15000"},
    "airt-40000": {"price": 40000, "description": "210GB Data - 40,000 Naira", "variation_code": "airt-40000"},
    "airt-60000": {"price": 60000, "description": "350GB Data - 60,000 Naira", "variation_code": "airt-60000"},
    "airt-100000": {"price": 100000, "description": "680GB Data - 100,000 Naira", "variation_code": "airt-100000"},
    "airt-20000": {"price": 20000, "description": "100GB Monthly Plan - 20,000 Naira", "variation_code": "airt-20000"},
    "airt-2500": {"price": 2500, "description": "4GB Monthly Plan - 2,500 Naira", "variation_code": "airt-2500"},
    "airt-8000": {"price": 8000, "description": "25GB Monthly Plan - 8,000 Naira", "variation_code": "airt-8000"},
    "airt-30000": {"price": 30000, "description": "160GB Monthly Plan - 30,000 Naira", "variation_code": "airt-30000"},
    "airt-50000": {"price": 50000, "description": "200GB Monthly Plan - 50,000 Naira", "variation_code": "airt-50000"},
    "airt-600": {"price": 600, "description": "1.5GB Binge Plan - 600 Naira", "variation_code": "airt-600"},
    "airt-1000-2": {"price": 1000, "description": "3.2GB Binge Plan - 1000 Naira", "variation_code": "airt-1000-2"},
    "airt-3000-7": {"price": 3000, "description": "10GB Weekly Plan - 3000 Naira", "variation_code": "airt-3000-7"},
    "airt-5000-7": {"price": 5000, "description": "18GB Weekly Plan - 5000 Naira", "variation_code": "airt-5000-7"},
    "airt-binge-500-1": {"price": 500, "description": "500 Naira Binge Plan", "variation_code": "airt-binge-500-1"},
    "airt-800-7": {"price": 800, "description": "1GB Weekly Plan - 800 Naira", "variation_code": "airt-800-7"},
    "airt-6000-30": {"price": 6000, "description": "18GB Monthly Plan - 6000 Naira", "variation_code": "airt-6000-30"},
    "airt-75-1": {"price": 75, "description": "75MB Daily Plan - 75 Naira", "variation_code": "airt-75-1"},
    "airt-300-1": {"price": 300, "description": "300MB Daily Plan - 300 Naira", "variation_code": "airt-300-1"},
    "airt-social-300-3": {"price": 300, "description": "1GB Social Plan - 300 Naira", "variation_code": "airt-social-300-3"},
    "airt-750-2": {"price": 750, "description": "2GB Binge Plan - 750 Naira", "variation_code": "airt-750-2"},
    "airt-1500-30": {"price": 1500, "description": "2GB Monthly Plan - 1,500 Naira", "variation_code": "airt-1500-30"},
    "airt-2500-7": {"price": 2500, "description": "6GB Weekly Plan - 2,500 Naira", "variation_code": "airt-2500-7"},
    "airt-mifi-5000-30": {"price": 5000, "description": "13GB MIFI Data - 5,000 Naira", "variation_code": "airt-mifi-5000-30"},
    "airt-mifi-10000-30": {"price": 10000, "description": "35GB MIFI Data - 10,000 Naira", "variation_code": "airt-mifi-10000-30"},
    "airt-mifi-15000-30": {"price": 15000, "description": "60GB MIFI Data - 15,000 Naira", "variation_code": "airt-mifi-15000-30"},
    "airt-mifi-20000-30": {"price": 20000, "description": "100GB Router Data - 20,000 Naira", "variation_code": "airt-mifi-20000-30"},
    "airt-mifi-30000-30": {"price": 30000, "description": "Unlimited 20MBPS - 30,000 Naira", "variation_code": "airt-mifi-30000-30"},
    "airt-mifi-50000-30": {"price": 50000, "description": "Unlimited 60MBPS - 50,000 Naira", "variation_code": "airt-mifi-50000-30"},
    "airt-mifi-80000-90": {"price": 80000, "description": "Unlimited 90 Days - 80,000 Naira", "variation_code": "airt-mifi-80000-90"},
    "airt-mifi-135000-90": {"price": 135000, "description": "Unlimited 90 Days - 135,000 Naira", "variation_code": "airt-mifi-135000-90"},
    "airt-mifi-150000-120": {"price": 150000, "description": "Unlimited 120 Days - 150,000 Naira", "variation_code": "airt-mifi-150000-120"},
    "airt-social-500-7": {"price": 500, "description": "1.5GB Social Plan - 500 Naira", "variation_code": "airt-social-500-7"},
    "airt-350-500": {"price": 350, "description": "500MB Daily Plan - 350 Naira", "variation_code": "airt-350-500"},
}



# Glo Dictionary refactored to use Frontend IDs as Keys
glo_dict = {
    # Daily / Weekly
    "glo-daily-50": {"price": 50, "description": "40MB + 5MB Night - 1 Day", "variation_code": "glo-daily-50"},
    "glo-daily-100": {"price": 100, "description": "120MB + 5MB Night - 1 Day", "variation_code": "glo-daily-100"},
    "glo-2days-200": {"price": 200, "description": "250MB + 25MB Night - 2 Days", "variation_code": "glo-2days-200"},
    "glo-special-500": {"price": 500, "description": "1GB + 1GB Night - 2 Days", "variation_code": "glo-special-500"},
    
    # Monthly
    "glo-monthly-1000": {"price": 1000, "description": "1.1GB + 1.5GB Night - 30 Days", "variation_code": "glo-monthly-1000"},
    "glo-monthly-1500": {"price": 1500, "description": "2.2GB + 3GB Night - 30 Days", "variation_code": "glo-monthly-1500"},
    "glo-monthly-2000": {"price": 2000, "description": "3.25GB + 3GB Night - 30 Days", "variation_code": "glo-monthly-2000"},
    "glo-monthly-2500": {"price": 2500, "description": "4.25GB + 3GB Night - 30 Days", "variation_code": "glo-monthly-2500"},
    "glo-monthly-3000": {"price": 3000, "description": "8.5GB + 2GB Night - 30 Days", "variation_code": "glo-monthly-3000"},
    "glo-monthly-5000": {"price": 5000, "description": "14.5GB + 2.5GB Night - 30 Days", "variation_code": "glo-monthly-5000"},
    "glo-monthly-10000": {"price": 10000, "description": "38GB + 4GB Night - 30 Days", "variation_code": "glo-monthly-10000"},
    
    # Data Guy (DG) / SME Plans
    "glo-dg-295": {"price": 295, "description": "1GB - 3 days", "variation_code": "glo-dg-295"},
    "glo-dg-890": {"price": 890, "description": "3GB - 3 days", "variation_code": "glo-dg-890"},
    "glo-dg-495": {"price": 495, "description": "1GB - 30 days", "variation_code": "glo-dg-495"},
    "glo-dg-990": {"price": 990, "description": "2GB - 30 days", "variation_code": "glo-dg-990"},
    
    # Mega Plans
    "glo-mega-30000": {"price": 30000, "description": "165GB - 30 Days", "variation_code": "glo-mega-30000"},
    "glo-mega-50000": {"price": 50000, "description": "310GB - 60 Days", "variation_code": "glo-mega-50000"},
    
    # Always On
    "glo-always-on-2000": {"price": 2000, "description": "6.1GB - 15 Days", "variation_code": "glo-always-on-2000"},
}


# Updated 9mobile (Etisalat) Dictionary using IDs as keys
etisalat_dict = {
    "eti-100": {"price": 100, "description": "83MB - 1 Day", "variation_code": "eti-100"},
    "eti-150": {"price": 150, "description": "150MB + 100MB Night - 1 Day", "variation_code": "eti-150-1"}, # VTpass usually uses eti-150-1
    "eti-500": {"price": 500, "description": "650MB - 7 Days", "variation_code": "eti-500"},
    "eti-1000": {"price": 1000, "description": "2GB - 30 Days", "variation_code": "eti-1000"},
    "eti-1200": {"price": 1200, "description": "2.3GB - 30 Days", "variation_code": "eti-1200"},
    "eti-2000": {"price": 2000, "description": "4.5GB - 30 Days", "variation_code": "eti-2000"},
    "eti-2500": {"price": 2500, "description": "5.2GB - 30 Days", "variation_code": "eti-2500"},
    "eti-3000": {"price": 3000, "description": "6.2GB - 30 Days", "variation_code": "eti-3000"},
    "eti-4000": {"price": 4000, "description": "8.4GB - 30 Days", "variation_code": "eti-4000"},
    "eti-5000": {"price": 5000, "description": "11.4GB - 30 Days", "variation_code": "eti-5000"},
    "eti-50": {"price": 50, "description": "40MB - 1 Day", "variation_code": "eti-50"},
    "t2-250mb-200": {"price": 200, "description": "250MB Anytime - 7 Days", "variation_code": "eti-200"}, # Mapping frontend ID to VTpass code
}

dstv_dict = {
    "DStv Padi N1,850": ("dstv-padi", 1850),
    "DStv Yanga N2,565": ("dstv-yanga", 2565),
    "Dstv Confam N4,615": ("dstv-confam", 4615),
    "DStv  Compact N7900": ("dstv79", 7900),
    "DStv Premium N18,400": ("dstv3", 18400),
    "DStv Asia N6,200": ("dstv6", 6200),
    "DStv Compact Plus N12,400": ("dstv7", 12400),
    "DStv Premium-French N25,550": ("dstv9", 25550),
    "DStv Premium-Asia N20,500": ("dstv10", 20500),
    "DStv Confam + ExtraView N7,115": ("confam-extra", 7115),
    "DStv Yanga + ExtraView N5,065": ("yanga-extra", 5065),
    "DStv Padi + ExtraView N4,350": ("padi-extra", 4350),
    "DStv Compact + Asia N14,100": ("com-asia", 14100),
    "DStv Compact + Extra View N10,400": ("dstv30", 10400),
    "DStv Compact + French Touch N10,200": ("com-frenchtouch", 10200),
    "DStv Premium - Extra View N20,900": ("dstv33", 20900),
    "DStv Compact Plus - Asia N18,600": ("dstv40", 18600),
    "DStv Compact + French Touch + ExtraView N12,700": ("com-frenchtouch-extra", 12700),
    "DStv Compact + Asia + ExtraView N16,600": ("com-asia-extra", 16600),
    "DStv Compact Plus + French Plus N20,500": ("dstv43", 20500),
    "DStv Compact Plus + French Touch N14,700": ("complus-frenchtouch", 14700),
    "DStv Compact Plus - Extra View N14,900": ("dstv45", 14900),
    "DStv Compact Plus + FrenchPlus + Extra View N23,000": (
        "complus-french-extraview",
        23000,
    ),
    "DStv Compact + French Plus N16,000": ("dstv47", 16000),
    "DStv Compact Plus + Asia + ExtraView N21,100": ("dstv48", 21100),
    "DStv Premium + Asia + Extra View N23,000": ("dstv61", 23000),
    "DStv Premium + French + Extra View N28,000": ("dstv62", 28050),
    "DStv HDPVR Access Service N2,500": ("hdpvr-access-service", 2500),
    "DStv French Plus Add-on N8,100": ("frenchplus-addon", 8100),
    "DStv Asian Add-on N6,200": ("asia-addon", 6200),
    "DStv French Touch Add-on N2,300": ("frenchtouch-addon", 2300),
    "ExtraView Access N2,500": ("extraview-access", 2500),
    "DStv French 11 N3,260": ("french11", 3260),
    "DStv Asian Bouquet E36 N12,400": ("dstv80", 12400),
    "DStv Yanga + Showmax N6,550": ("dstv-yanga-showmax", 6550),
    "DStv Great Wall Standalone Bouquet + Showmax N6,625": (
        "dstv-greatwall-showmax",
        6625,
    ),
    "DStv Compact Plus + Showmax N26,450": ("dstv-compact-plus-showmax", 26450),
    "Dstv Confam + Showmax N10,750": ("dstv-confam-showmax", 10750),
    "DStv  Compact + Showmax N17,150": ("dstv-compact-showmax", 17150),
    "DStv Padi + Showmax N7,100": ("dstv-padi-showmax", 7100),
    "DStv Premium W/Afr +  ASIAE36 + Showmax N57,500": (
        "dstv-premium-asia-showmax",
        57500,
    ),
    "DStv Asia + Showmax N15,900": ("dstv-asia-showmax", 15900),
    "DStv Premium + French + Showmax N57,500": ("dstv-premium-french-showmax", 57500),
    "DStv Premium + Showmax N37,000": ("dstv-premium-showmax", 37000),
    "DStv Premium Streaming Subscription - N37,000": ("dstv-premium-str", 37000),
    "DStv Prestige - N850,000": ("dstv-prestige", 850000),
    "DStv Yanga OTT Streaming Subscription - N5,100": ("dstv-yanga-stream", 5100),
    "DStv Compact Plus Streaming Subscription - N25,000": (
        "dstv-compact-plus-streem",
        25000,
    ),
    "DStv Compact Streaming Subscription - N15,700": ("dstv-compact-stream", 15700),
    "DStv Comfam Streaming Subscription - N9,300": ("dstv-confam-stream", 9300),
    "DStv Indian N12,400": ("dstv-indian", 12400),
    "DStv Premium East Africa and Indian N16530": ("dstv-premium-indian", 16530),
    "DStv FTA Plus N1,600": ("dstv-fta-plus", 1600),
    "DStv PREMIUM HD N39,000": ("dstv-premium-hd", 39000),
    "DStv Access N2000": ("dstv-access-1", 2000),
    "DStv Family": ("dstv-family-1", 4000),
    "DStv India Add-on N12,400": ("dstv-indian-add-on", 12400),
    "DSTV MOBILE N790": ("dstv-mobile-1", 790),
    "DStv Movie Bundle Add-on N2500": ("dstv-movie-bundle-add-on", 2500),
    "DStv PVR Access Service N4000": ("dstv-pvr-access", 4000),
    "DStv Premium W/Afr + Showmax N37,000": ("dstv-premium-wafr-showmax", 42000),
    "Showmax Standalone - N3,500": ("showmax3500", 3500),
    "DStv Prestige Membership - N850,000": ("dstv-prestige-850", 850000),
    "DStv Compact Plus + French + Xtraview - N39,000": (
        "dstv-complus-frch-xtra",
        39000,
    ),
    "DStv Compact Plus + French - N34,000": ("dstv-complus-frch", 34000),
    "DStv Box Office": ("dstv-box-office", 800),
    "DStv Box Office (New Premier)": ("dstv-box-office-premier", 1100),
}

gotv_dict = {
    "GOtv Lite N410": ("gotv-lite", 410),
    "GOtv Max N3,600": ("gotv-max", 3600),
    "GOtv Jolli N2,460": ("gotv-jolli", 2460),
    "GOtv Jinja N1,640": ("gotv-jinja", 1640),
    "GOtv Lite (3 Months) N1,080": ("gotv-lite-3months", 1080),
    "GOtv Lite (1 Year) N3,180": ("gotv-lite-1year", 3180),
    "GOtv Supa Plus - monthly N15,700": ("gotv-supa-plus", 15700),
}

showmax_dict = {
    "Full - N8,400 - 3 Months": ("full_3", 8400),
    "Mobile Only - N3,800 - 3 Months": ("mobile_only_3", 3800),
    "Sports Mobile Only - N12,000 - 3 Months": ("sports_mobile_only_3", 12000),
    "Sports Only - N3,200": ("sports-only-1", 3200),
    "Sports Only 3 months - N9,600": ("sports-only-3", 9600),
    "Full Sports Mobile Only - 3 months - N16,200": (
        "full-sports-mobile-only-3",
        16200,
    ),
    "Mobile Only - N6,700 - 6 Months": ("mobile-only-6", 6700),
    "Full - 6 months - 14,700": ("full-only-6", 14700),
    "Full Sports Mobile Only - 6 months - N32,400": (
        "full-sports-mobile-only-6",
        32400,
    ),
    "Sports Mobile Only - 6 months - N24,000": ("sports-mobile-only-6", 24000),
    "Sports Only - 6 months - N18,200": ("sports-only-6", 18200),
}

startimes_dict = {
    "Nova - 900 Naira - 1 Month": ("nova", 900),
    "Basic - 1,700 Naira - 1 Month": ("basic", 1700),
    "Smart - 2,200 Naira - 1 Month": ("smart", 2200),
    "Classic - 2,500 Naira - 1 Month": ("classic", 2500),
    "Super - 4,200 Naira - 1 Month": ("super", 4200),
    "Nova - 300 Naira - 1 Week": ("nova-weekly", 300),
    "Basic - 600 Naira - 1 Week": ("basic-weekly", 600),
    "Smart - 700 Naira - 1 Week": ("smart-weekly", 700),
    "Classic - 1200 Naira - 1 Week ": ("classic-weekly", 1200),
    "Super - 1,500 Naira - 1 Week": ("super-weekly", 1500),
    "Nova - 90 Naira - 1 Day": ("nova-daily", 90),
    "Basic - 160 Naira - 1 Day": ("basic-daily", 160),
    "Smart - 200 Naira - 1 Day": ("smart-daily", 200),
    "Classic - 320 Naira - 1 Day ": ("classic-daily", 320),
    "Super - 400 Naira - 1 Day": ("super-daily", 400),
    "ewallet Amount": ("ewallet", 0),
    "Chinese (Dish) - 19,000 Naira - 1 month": ("uni-1", 19000),
    "Nova (Antenna) - 1,900 Naira - 1 Month": ("uni-2", 1900),
    "Classic (Dish) - 2300 Naira - 1 Week": ("special-weekly", 2300),
    "Classic (Dish) - 6800 Naira - 1 Month": ("special-monthly", 6800),
    "Nova (Dish) - 650 Naira - 1 Week": ("nova-dish-weekly", 650),
    "Super (Antenna) - 3,000 Naira - 1 Week": ("super-antenna-weekly", 3000),
    "Super (Antenna) - 8,800 Naira - 1 Month": ("super-antenna-monthly", 8800),
    "Global (Dish) - 19000 Naira - 1 Month": ("global-monthly-dish", 19000),
    "Global (Dish) - 6500 Naira - 1Week": ("global-weekly-dish", 6500),
}


def generate_reference_id():
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    unique_part = str(uuid.uuid4()).split("-")[0].upper()
    reference_id = f"{now}-{unique_part}"
    return reference_id


def top_up(user_data):
    response = requests.post(f"{BASE_URL}/pay", headers=headers, json=user_data)
    return response.json()


def get_variations():
    response = requests.get(
        "https://sandbox.vtpass.com/api/service-variations?serviceID=waec",
        headers=headers,
    )
    return response.json()


def get_customer(user_data):
    response = requests.post(
        f"{BASE_URL}/merchant-verify", headers=headers, json=user_data
    )
    return response.json()


def get_receipt(request_id):
    response = requests.post(f"{BASE_URL}/requery", headers=headers, json=request_id)
    return response.json()


if __name__ == "__main__":
    print(get_variations())  # Added .json() to print the response body
