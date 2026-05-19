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

mtn_dict = {
    "N100 100MB - 24 hrs": ("mtn-10mb-100", 100),
    "N200 200MB - 2 days": ("mtn-50mb-200", 200),
    "N1000 1.5GB - 30 days": ("mtn-100mb-1000", 1000),
    "N2000 4.5GB - 30 days": ("mtn-500mb-2000", 2000),
    "N1500 6GB - 7 days": ("mtn-20hrs-1500", 1500),
    "N2500 6GB - 30 days": ("mtn-3gb-2500", 2500),
    "N3000 8GB - 30 days": ("mtn-data-3000", 3000),
    "N3500 10GB - 30 days": ("mtn-1gb-3500", 3500),
    "N5000 15GB - 30 days": ("mtn-100hr-5000", 5000),
    "N6000 20GB - 30 days": ("mtn-3gb-6000", 6000),
    "N10000 40GB - 30 days": ("mtn-40gb-10000", 10000),
    "N15000 75GB - 30 days": ("mtn-75gb-15000", 15000),
    "N20000 110GB - 30 days": ("mtn-110gb-20000", 20000),
    "N1500 3GB - 30 days": ("mtn-3gb-1500", 1500),
    "N10000 25GB SME - 1 month": ("mtn-25gb-sme-10000", 10000),
    "N50000 165GB SME - 2 months": ("mtn-165gb-sme-50000", 50000),
    "N100000 360GB SME - 3 months": ("mtn-360gb-sme-100000", 100000),
    "N450000 4.5TB - 1 year": ("mtn-4-5tb-450000", 450000),
    "N110000 1TB - 1 year": ("mtn-1tb-110000", 110000),
    "N600 2.5GB - 2 days": ("mtn-2-5gb-600", 600),
    "N22000 120GB + 80mins - 30 days": ("mtn-120gb-22000", 22000),
    "N20000 100GB - 2 months": ("mtn-100gb-20000", 20000),
    "N30000 160GB - 2 months": ("mtn-160gb-30000", 30000),
    "N50000 400GB - 3 months": ("mtn-400gb-50000", 50000),
    "N75000 600GB - 3 months": ("mtn-600gb-75000", 75000),
    "N300 Xtratalk Weekly": ("mtn-xtratalk-300", 300),
    "N500 Xtratalk Weekly": ("mtn-xtratalk-500", 500),
    "N1000 Xtratalk Monthly": ("mtn-xtratalk-1000", 1000),
    "N2000 Xtratalk Monthly": ("mtn-xtratalk-2000", 2000),
    "N5000 Xtratalk Monthly": ("mtn-xtratalk-5000", 5000),
    "N10000 Xtratalk Monthly": ("mtn-xtratalk-10000", 10000),
    "N15000 Xtratalk Monthly": ("mtn-xtratalk-15000", 15000),
    "N20000 Xtratalk Monthly": ("mtn-xtratalk-20000", 20000),
    "N800 3GB - 2 days": ("mtn-3gb-800", 800),
    "N2000 7GB - 7 days": ("mtn-7gb-2000", 2000),
    "N200 Xtradata": ("mtn-xtradata-200", 200),
}

airtel_dict = {
    "N50 25MB - 1 day": ("airt-50", 50),
    "N100 75MB - 1 day": ("airt-100", 100),
    "N200 200MB - 3 days": ("airt-200", 200),
    "N300 350MB - 7 days": ("airt-300", 300),
    "N500 750MB - 14 days": ("airt-500", 500),
    "N1000 1.5GB - 30 days": ("airt-1000", 1000),
    "N1500 3GB - 30 days": ("airt-1500", 1500),
    "N2000 4.5GB - 30 days": ("airt-2000", 2000),
    "N3000 8GB - 30 days": ("airt-3000", 3000),
    "N4000 11GB - 30 days": ("airt-4000", 4000),
    "N5000 15GB - 30 days": ("airt-5000", 5000),
    "N1500 6GB Binge - 7 days": ("airt-1500-2", 1500),
    "N10000 40GB - 30 days": ("airt-10000", 10000),
    "N15000 75GB - 30 days": ("airt-15000", 15000),
    "N20000 110GB - 30 days": ("airt-20000", 20000),
    "N600 1GB - 14 days": ("airt-600", 600),
    "N1000 1.5GB - 7 days": ("airt-1000-7", 1000),
    "N2000 7GB - 7 days": ("airt-2000-7", 2000),
    "N5000 25GB - 7 days": ("airt-5000-7", 5000),
    "N400 1.5GB - 1 day": ("airt-400-1", 400),
    "N800 3.5GB - 2 days": ("airt-800-2", 800),
    "N6000 23GB - 30 days": ("airt-6000-30", 6000),
}

glo_dict = {
    "N100 105MB - 2 days": ("glo100", 100),
    "N200 350MB - 4 days": ("glo200", 200),
    "N500 1.05GB - 14 days": ("glo500", 500),
    "N1000 2.5GB - 30 days": ("glo1000", 1000),
    "N2000 5.8GB - 30 days": ("glo2000", 2000),
    "N2500 7.7GB - 30 days": ("glo2500", 2500),
    "N3000 10GB - 30 days": ("glo3000", 3000),
    "N4000 13.25GB - 30 days": ("glo4000", 4000),
    "N5000 18.25GB - 30 days": ("glo5000", 5000),
    "N8000 29.5GB - 30 days": ("glo8000", 8000),
    "N10000 50GB - 30 days": ("glo10000", 10000),
    "N15000 93GB - 30 days": ("glo15000", 15000),
    "N18000 119GB - 30 days": ("glo18000", 18000),
    "N1500 4.1GB - 30 days": ("glo1500", 1500),
    "N20000 138GB - 30 days": ("glo20000", 20000),
    "N70 200MB SME - 14 days": ("glo-dg-70", 70),
    "N320 1GB SME - 30 days": ("glo-dg-320", 320),
    "N960 3GB SME - 30 days": ("glo-dg-960", 960),
    "N3100 10GB SME - 30 days": ("glo-dg-3100", 3100),
    "N640 2GB SME - 30 days": ("glo-dg-640", 640),
    "N160 500MB SME - 14 days": ("glo-dg-160-14", 160),
    "N1600 5GB SME - 30 days": ("glo-dg-1600", 1600),
    "N50 45MB + 5MB Night - 1 day": ("glo-daily-50", 50),
    "N100 115MB + 35MB Night - 1 day": ("glo-daily-100", 100),
    "N200 240MB + 110MB Night - 2 days": ("glo-2days-200", 200),
    "N500 800MB + 1GB Night - 2 weeks": ("glo-2weeks-500", 500),
    "N1000 1.9GB + 2GB Night - 30 days": ("glo-monthly-1000", 1000),
    "N1500 3.5GB + 4GB Night - 30 days": ("glo-monthly-1500", 1500),
    "N2000 5.2GB + 4GB Night - 30 days": ("glo-monthly-2000", 2000),
    "N2500 6.8GB + 4GB Night - 30 days": ("glo-monthly-2500", 2500),
    "N3000 10GB + 4GB Night - 30 days": ("glo-monthly-3000", 3000),
    "N4000 14GB + 4GB Night - 30 days": ("glo-monthly-4000", 4000),
    "N5000 20GB + 4GB Night - 30 days": ("glo-monthly-5000", 5000),
    "N8000 27.5GB + 2GB Night - 30 days": ("glo-monthly-8000", 8000),
    "N10000 46GB + 4GB Night - 30 days": ("glo-monthly-10000", 10000),
    "N15000 86GB + 7GB Night - 30 days": ("glo-monthly-15000", 15000),
    "N18000 109GB + 10GB Night - 30 days": ("glo-monthly-18000", 18000),
    "N20000 126GB + 12GB Night - 30 days": ("glo-monthly-20000", 20000),
    "N300 1GB Special": ("glo-special-300", 300),
    "N500 2GB Special": ("glo-special-500", 500),
}

etisalat_dict = {
    "N100 100MB - 1 day": ("eti-100", 100),
    "N200 650MB - 1 day": ("eti-200", 200),
    "N500 500MB - 30 days": ("eti-500", 500),
    "N1000 1.5GB - 30 days": ("eti-1000", 1000),
    "N2000 4.5GB - 30 days": ("eti-2000", 2000),
    "N5000 15GB - 30 days": ("eti-5000", 5000),
    "N10000 40GB - 30 days": ("eti-10000", 10000),
    "N15000 75GB - 30 days": ("eti-15000", 15000),
    "N27500 30GB - 90 days": ("eti-27500", 27500),
    "N55000 60GB - 180 days": ("eti-55000", 55000),
    "N110000 120GB - 365 days": ("eti-110000", 110000),
    "N300 1GB + 100MB - 1 day": ("eti-300", 300),
    "N2500 11GB - 30 days": ("eti-2500", 2500),
    "N7000 35GB - 30 days": ("eti-7000", 7000),
    "N20000 125GB - 30 days": ("eti-20000", 20000),
    "N1000 4GB - 30 days": ("eti-1000", 1000),
    "N1500 7GB - 7 days": ("eti-1500-7", 1500),
    "N150 200MB - 1 day": ("eti-150-1", 150),
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
