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

# Updated May 2026 — codes sourced from VTPass variation exports
mtn_dict = {
    "110MB Daily Plan (1 Day) - N100": ("mtn-10mb-100", 100),
    "230MB Daily Plan (1 Day) - N200": ("mtn-230mb-200", 200),
    "500MB Daily Plan (1 Day) - N350": ("mtn-500mb-ex-350", 350),
    "MTN N500 1GB + 1.5mins - 1 day": ("mtn-1gb-350", 500),
    "2.5GB Daily Plan - N750": ("mtn-2.5-750", 750),
    "MTN N1000 3.5GB - (1 day)": ("mtn-3.5gb-1-1000", 1000),
    "MTN N900 2.5GB - 2 days": ("mtn-2-5gb-900", 900),
    "1.5GB Daily Plan (2 Days) - N600": ("mtn-2-5gb-ex-600", 600),
    "2GB Daily Plan (2 Days) - N750": ("mtn-2gb-ex-750", 750),
    "MTN N1200 4GB - (2 days)": ("mtn-4gb-2-1200", 1200),
    "MTN N1500 5.5GB - (2 days)": ("mtn-5.5gb-2-1500", 1500),
    "MTN N1800 7GB - (2 Days)": ("mtn-7gb-1800", 1800),
    "MTN N1000 3.2GB - 2 days": ("mtn-3.2gb-1000", 1000),
    "1.5GB Weekly Plan (7 Days) - N1,000": ("mtn-1500mb-1000", 1000),
    "3.5GB Weekly Plan (7 Days) - N1,500": ("mtn-3.5gb-1500", 1500),
    "600MB Xtra Bundle Weekly Data (7 Days) - N500": ("mtn-xtrabundle-500", 500),
    "500MB + 1GB YouTube (7 Days) - N500": ("mtn-500mb-500", 500),
    "1GB+5mins Weekly Plan - N800": ("mtn-1gb-600", 800),
    "MTN N2500 6GB - 7 days": ("mtn-7gb-3000", 2500),
    "MTN N3,500 11GB - 7 days": ("mtn-11gb-3500", 3500),
    "20GB Weekly Plan - N5,000": ("mtn-20-5000", 5000),
    "1.8GB + 6mins + 5 SMS, Weekly plan - N1500": ("mtn-1800mb-1500", 1500),
    "2GB + 2 Mins Monthly Plan - N1,500": ("mtn-xtra-1000", 1500),
    "2.7GB Xtra Bundle Monthly Plan - N3,000": ("mtn-1500mb-ex-1200", 3000),
    "2.7GB + 2mins + 2GB Night + 200MB YouTube Monthly - N2000": ("mtn-2.7gb-2000", 2000),
    "MTN N2500 3.5GB +5mins Monthly Plan": ("mtn-3.5gb-2500", 2500),
    "MTN N3000 6.75GB Monthly Plan": ("mtn-6.75gb-3000", 3000),
    "MTN N4,500 10GB + 10mins - 30 days": ("mtn-8gb-ex-3000", 4500),
    "MTN 14.5GB Monthly Plan - N5,000": ("mtn-14.5gb-5000", 5000),
    "12.5GB Monthly Plan - N5,500": ("mtn-11gb-5000", 5500),
    "16.5GB Monthly Plan - N6,500": ("mtn-data-6500", 6500),
    "7GB Monthly Plan - N3,500": ("mtn-5.5gb-3500", 3500),
    "MTN N9,000 25GB + Youtube - 30 days": ("mtn-25gb-9000", 9000),
    "MTN N10000 34GB - (30 days)": ("mtn-34gb-30-10000", 10000),
    "20GB Monthly Plan - N7,500": ("mtn-20gb-7500", 7500),
    "36GB Monthly Plan - N11,000": ("mtn-32gb-11000", 11000),
    "65GB Monthly Plan - N16,000": ("mtn-65gb-ex-16000", 16000),
    "75GB Monthly Plan - N18,000": ("mtn-75gb-20000", 18000),
    "MTN N24,000 120GB - 30 days": ("mtn-120gb-24000", 24000),
    "MTN N35,000 165GB Monthly Data Plan": ("mtn-165gb-35000", 35000),
    "MTN N37,500 200GB + 5GB Youtube/MSTeams/Zoom - 5G Router": ("mtn-200gb-37500", 37500),
    "MTN 260GB + 2GB daily - N45,000": ("mtn-260gb-monthly", 45000),
    "150GB 2-Month Plan - N40,000": ("mtn-150gb-40000", 40000),
    "480GB 3-Month Plan - N90,000": ("mtn-480gb-90000", 90000),
    "30GB Monthly Broadband Plan - N9,000": ("mtn-hynetflex-9000-30", 9000),
    "60GB Monthly HyNetFlex Plan - N14,500": ("mtn-hynetflex-14500-30", 14500),
    "MTN N30,000 150GB + 2GB daily - 5G Router (30 Days)": ("mtn-150gb-30000", 30000),
    "450GB 3-Month Broadband Plan - N75,000": ("mtn-hynetflex-75000-90", 75000),
    "MTN 1.5TB - N225,000 Broadband Router": ("mtn-1500gb-yearly", 225000),
}

# Updated May 2026
airtel_dict = {
    "250MB Night Plan (12-5 AM) - N50 - 1 Day": ("airt-50", 50),
    "200MB Social Plan (2 Days) - N100": ("airt-100", 100),
    "Airtel Data - 110MB - N100 - 1 Day": ("airt-daily-100", 100),
    "230MB Daily Plan - N200": ("airt-200", 200),
    "500MB Weekly Plan (7 Days) - N500": ("airt-500", 500),
    "500 Naira Binge Plan": ("airt-binge-500-1", 500),
    "1.5GB Binge Plan + Youtube & Social (2 Days) - N600": ("airt-600", 600),
    "3.2GB Binge Plan + Youtube & Social (2 Days) - N1,000": ("airt-1000-2", 1000),
    "1.5GB Weekly Plan + Youtube & Social (7 Days) - N1,000": ("airt-1000-7", 1000),
    "3.5GB Weekly Plan + Youtube & Social (7 Days) - N1,500": ("airt-1500-7", 1500),
    "5GB Binge Plan + Youtube & Social (2 Days) - N1,500": ("airt-1500-2", 1500),
    "3GB Monthly Plan + Youtube & Social (30 Days) - N2,000": ("airt-2000", 2000),
    "4GB Monthly Plan + Youtube & Social (30 Days) - N2,500": ("airt-2500", 2500),
    "10GB Weekly Plan + Youtube & Social (7 Days) - N3,000": ("airt-3000-7", 3000),
    "8GB Monthly Plan + Youtube & Social (30 Days) - N3,000": ("airt-3000", 3000),
    "10GB Monthly Plan + Youtube & Social (30 Days) - N4,000": ("airt-4000", 4000),
    "18GB Weekly Plan + Youtube & Social (7 Days) - N5,000": ("airt-5000-7", 5000),
    "13GB Monthly Plan + Youtube & Social (30 Days) - N5,000": ("airt-5000", 5000),
    "25GB Monthly Plan + Youtube & Social (30 Days) - N8,000": ("airt-8000", 8000),
    "35GB Monthly Plan + Youtube & Social (30 Days) - N10,000": ("airt-10000", 10000),
    "60GB Monthly Plan + Youtube & Social (30 Days) - N15,000": ("airt-15000", 15000),
    "100GB Monthly Plan + Youtube & Social (30 Days) - N20,000": ("airt-20000", 20000),
    "160GB Monthly Plan (30 Days) - N30,000": ("airt-30000", 30000),
    "210GB Data (30 Days) - N40,000": ("airt-40000", 40000),
    "200GB Monthly Plan (90 Days) - N50,000": ("airt-50000", 50000),
    "350GB Monthly Plan (120 Days) - N60,000": ("airt-60000", 60000),
    "680GB Data (365 Days) - N100,000": ("airt-100000", 100000),
}

# Updated May 2026
glo_dict = {
    "40MB + 5MB Night - N50 - 1 Day": ("glo-daily-50", 50),
    "120MB + 5MB Night - N100 - 1 Day": ("glo-daily-100", 100),
    "240MB + 5MB Night - N100 - 1 Day - Campus": ("glo-campus-booster-100", 100),
    "300MB - GloMyG N100 1 Day": ("glo-social-oneoff-100", 100),
    "200MB (Best Value) - N99 - 14 days": ("glo-dg-99", 99),
    "Glo TV VOD 500MB 3days - N150": ("glo-tv-150", 150),
    "250MB + 25MB Night - N200 - 2 Days": ("glo-2days-200", 200),
    "875MB 1 Day - Weekend N200": ("glo-sunday-200", 200),
    "500MB + 25MB Night - N200 - 2 Days - Campus": ("glo-campus-booster-200", 200),
    "500MB (Best Value) - N250 - 14 days": ("glo-dg-250", 250),
    "500MB (Best Value) - N250 - 30 Days": ("glo-dg-250-30", 250),
    "1GB (Best Value) - N295 - 3 days": ("glo-dg-295", 295),
    "Glo MyG N300 1GB 3 Days": ("glo-social-oneoff-300", 300),
    "1GB (Best Value) - N345 - 7 days": ("glo-dg-345", 345),
    "1GB (Best Value) - N350 - 14 days": ("glo-dg-350", 350),
    "Glo TV VOD 2GB 7days - N450": ("glo-tv-450", 450),
    "1GB (Best Value) - N495 - 30 days": ("glo-dg-495", 495),
    "1GB + 1GB Night - N500 - 2 Days Special": ("glo-special-500", 500),
    "2.5GB 2 Days - Weekend N500": ("glo-weekend-500", 500),
    "1.1GB + 1GB Night - N500 - 7 Days - Campus": ("glo-campus-booster-500", 500),
    "Glo MyG N500 1.5GB 7 Days": ("glo-social-oneoff-500", 500),
    "5GB (Best Value) - N1,485 - 3 days": ("glo-dg-1485", 1485),
    "1.1GB 14 Days - N750": ("glo-750-14", 750),
    "3GB (Best Value) - N890 - 3 days": ("glo-dg-890", 890),
    "3GB (Best Value) - N1,040 - 7 days": ("glo-dg-1040", 1040),
    "3GB (Best Value) - N1,040 - 14 days": ("glo-dg-1040-14", 1040),
    "1.1GB + 1.5GB Night - N1000 - 30 Days": ("glo-monthly-1000", 1000),
    "1.7GB + 2GB Night - N1000 - 7 Days": ("glo-1000-7days", 1000),
    "2.2GB + 2GB Night - N1000 - 30 Days - Campus": ("glo-campus-booster-1000", 1000),
    "Glo MyG N1000 3.5GB 30 Days": ("glo-social-oneoff-1000", 1000),
    "5GB (Best Value) - N1,730 - 7 days": ("glo-dg-1730", 1730),
    "2GB (Best Value) - N990 - 30 days": ("glo-dg-990", 990),
    "5GB (Best Value) - N1,485 - 30 days": ("glo-dg-1485-30", 1485),
    "Glo TV VOD 6GB 30days - N1,400": ("glo-tv-1400", 1400),
    "4GB + 2GB Night - N1,500 - 7 Days Special": ("glo-special-1500", 1500),
    "2.2GB + 3GB - N1500 - 30 Days": ("glo-monthly-1500", 1500),
    "6.5GB + 2.5GB - N2000 - 7 Days": ("glo-2000-7days", 2000),
    "3.25GB + 3GB Night - N2000 - 30 Days": ("glo-monthly-2000", 2000),
    "6.5GB + 3.5GB - N2,000 - 30 Days - Campus": ("glo-campus-booster-2000", 2000),
    "5GB (Best Value) - N2,475 - 30 days": ("glo-dg-2475", 2475),
    "4.25GB + 3GB Night - N2500 - 30 Days": ("glo-monthly-2500", 2500),
    "8.5GB + 2GB Night - N3000 - 30 Days": ("glo-monthly-3000", 3000),
    "10GB (Best Value) - N3,460 - 14 days": ("glo-dg-3460", 3460),
    "10.5GB + 2GB Night - N4000 - 30 Days": ("glo-monthly-4000", 4000),
    "10GB (Best Value) - N4,950 - 30 days": ("glo-dg-4950", 4950),
    "14.5GB + 2.5GB Night - N5000 - 30 Days": ("glo-monthly-5000", 5000),
    "29GB + 3GB Night - N5000 - 30 Days - Campus": ("glo-campus-booster-5000", 5000),
    "Glo TV Lite 2GB 7 Days - N900": ("glo-tv-900", 900),
    "26GB + 2GB - N8,000 - 30 Days": ("glo-monthly-8000", 8000),
    "38GB + 4GB Night - N10,000 - 30 Days": ("glo-monthly-10000", 10000),
    "Glo TV Max 6GB 30 Days - N3,200": ("glo-tv-3200", 3200),
    "165GB 30 Days - Mega N30,000": ("glo-mega-30000", 30000),
    "220GB 30 Days - Mega N40,000": ("glo-mega-40000", 40000),
    "310GB 60 Days - Mega N50,000": ("glo-mega-50000", 50000),
    "355GB 90 Days - Mega N60,000": ("glo-mega-60000", 60000),
    "475GB 90 Days - Mega N75,000": ("glo-mega-75000", 75000),
}

# Updated May 2026 — now 9mobile SME plans (etisalat rebranded to 9mobile)
etisalat_dict = {
    "9mobile 50MB SME - N4": ("9mobile-sme-data-50mb", 4),
    "9mobile 100MB SME - N14": ("9mobile-sme-data-100mb", 14),
    "9mobile 200MB SME - N28": ("9mobile-sme-data-200mb", 28),
    "9mobile 500MB SME - N70": ("9mobile-sme-data-500mb", 70),
    "9mobile 1GB SME - N140": ("9mobile-sme-data-1gb", 140),
    "9mobile 2GB SME - N280": ("9mobile-sme-data-2gb", 280),
    "9mobile 3GB SME - N420": ("9mobile-sme-data-3gb", 420),
    "9mobile 4GB SME - N560": ("9mobile-sme-data-4gb", 560),
    "9mobile 5GB SME - N700": ("9mobile-sme-data-5gb", 700),
    "9mobile 10GB SME - N1,400": ("9mobile-sme-data-10gb", 1400),
    "9mobile 15GB SME - N2,100": ("9mobile-sme-data-15gb", 2100),
    "9mobile 20GB SME - N2,800": ("9mobile-sme-data-20gb", 2800),
    "9mobile 25GB SME - N3,500": ("9mobile-sme-data-25gb", 3500),
    "9mobile 50GB SME - N7,000": ("9mobile-sme-data-50gb", 7000),
    "9mobile 100GB SME - N14,000": ("9mobile-sme-data-100gb", 14000),
}

# TV/Cable dicts — unchanged (not in variation exports)
dstv_dict = {
    "DStv Padi N1,850": ("dstv-padi", 1850),
    "DStv Yanga N2,565": ("dstv-yanga", 2565),
    "Dstv Confam N4,615": ("dstv-confam", 4615),
    "DStv Compact N7,900": ("dstv79", 7900),
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
    "DStv Compact Plus + FrenchPlus + Extra View N23,000": ("complus-french-extraview", 23000),
    "DStv Compact + French Plus N16,000": ("dstv47", 16000),
    "DStv Compact Plus + Asia + ExtraView N21,100": ("dstv48", 21100),
    "DStv Premium + Asia + Extra View N23,000": ("dstv61", 23000),
    "DStv Premium + French + Extra View N28,050": ("dstv62", 28050),
    "DStv HDPVR Access Service N2,500": ("hdpvr-access-service", 2500),
    "DStv French Plus Add-on N8,100": ("frenchplus-addon", 8100),
    "DStv Asian Add-on N6,200": ("asia-addon", 6200),
    "DStv French Touch Add-on N2,300": ("frenchtouch-addon", 2300),
    "ExtraView Access N2,500": ("extraview-access", 2500),
    "DStv French 11 N3,260": ("french11", 3260),
    "DStv Asian Bouquet E36 N12,400": ("dstv80", 12400),
    "DStv Yanga + Showmax N6,550": ("dstv-yanga-showmax", 6550),
    "DStv Great Wall Standalone + Showmax N6,625": ("dstv-greatwall-showmax", 6625),
    "DStv Compact Plus + Showmax N26,450": ("dstv-compact-plus-showmax", 26450),
    "Dstv Confam + Showmax N10,750": ("dstv-confam-showmax", 10750),
    "DStv Compact + Showmax N17,150": ("dstv-compact-showmax", 17150),
    "DStv Padi + Showmax N7,100": ("dstv-padi-showmax", 7100),
    "DStv Premium W/Afr + ASIAE36 + Showmax N57,500": ("dstv-premium-asia-showmax", 57500),
    "DStv Asia + Showmax N15,900": ("dstv-asia-showmax", 15900),
    "DStv Premium + French + Showmax N57,500": ("dstv-premium-french-showmax", 57500),
    "DStv Premium + Showmax N37,000": ("dstv-premium-showmax", 37000),
    "DStv Premium Streaming Subscription N37,000": ("dstv-premium-str", 37000),
    "DStv Prestige N850,000": ("dstv-prestige", 850000),
    "DStv Yanga OTT Streaming Subscription N5,100": ("dstv-yanga-stream", 5100),
    "DStv Compact Plus Streaming Subscription N25,000": ("dstv-compact-plus-streem", 25000),
    "DStv Compact Streaming Subscription N15,700": ("dstv-compact-stream", 15700),
    "DStv Confam Streaming Subscription N9,300": ("dstv-confam-stream", 9300),
    "DStv Indian N12,400": ("dstv-indian", 12400),
    "DStv Premium East Africa and Indian N16,530": ("dstv-premium-indian", 16530),
    "DStv FTA Plus N1,600": ("dstv-fta-plus", 1600),
    "DStv PREMIUM HD N39,000": ("dstv-premium-hd", 39000),
    "DStv Access N2,000": ("dstv-access-1", 2000),
    "DStv Family N4,000": ("dstv-family-1", 4000),
    "DStv India Add-on N12,400": ("dstv-indian-add-on", 12400),
    "DSTV MOBILE N790": ("dstv-mobile-1", 790),
    "DStv Movie Bundle Add-on N2,500": ("dstv-movie-bundle-add-on", 2500),
    "DStv PVR Access Service N4,000": ("dstv-pvr-access", 4000),
    "DStv Premium W/Afr + Showmax N42,000": ("dstv-premium-wafr-showmax", 42000),
    "Showmax Standalone N3,500": ("showmax3500", 3500),
    "DStv Prestige Membership N850,000": ("dstv-prestige-850", 850000),
    "DStv Compact Plus + French + Xtraview N39,000": ("dstv-complus-frch-xtra", 39000),
    "DStv Compact Plus + French N34,000": ("dstv-complus-frch", 34000),
    "DStv Box Office N800": ("dstv-box-office", 800),
    "DStv Box Office (New Premier) N1,100": ("dstv-box-office-premier", 1100),
}

gotv_dict = {
    "GOtv Lite N410": ("gotv-lite", 410),
    "GOtv Max N3,600": ("gotv-max", 3600),
    "GOtv Jolli N2,460": ("gotv-jolli", 2460),
    "GOtv Jinja N1,640": ("gotv-jinja", 1640),
    "GOtv Lite (3 Months) N1,080": ("gotv-lite-3months", 1080),
    "GOtv Lite (1 Year) N3,180": ("gotv-lite-1year", 3180),
    "GOtv Supa Plus Monthly N15,700": ("gotv-supa-plus", 15700),
}

showmax_dict = {
    "Full - N8,400 - 3 Months": ("full_3", 8400),
    "Mobile Only - N3,800 - 3 Months": ("mobile_only_3", 3800),
    "Sports Mobile Only - N12,000 - 3 Months": ("sports_mobile_only_3", 12000),
    "Sports Only - N3,200": ("sports-only-1", 3200),
    "Sports Only 3 months - N9,600": ("sports-only-3", 9600),
    "Full Sports Mobile Only - 3 months - N16,200": ("full-sports-mobile-only-3", 16200),
    "Mobile Only - N6,700 - 6 Months": ("mobile-only-6", 6700),
    "Full - 6 months - N14,700": ("full-only-6", 14700),
    "Full Sports Mobile Only - 6 months - N32,400": ("full-sports-mobile-only-6", 32400),
    "Sports Mobile Only - 6 months - N24,000": ("sports-mobile-only-6", 24000),
    "Sports Only - 6 months - N18,200": ("sports-only-6", 18200),
}

startimes_dict = {
    "Nova - N900 - 1 Month": ("nova", 900),
    "Basic - N1,700 - 1 Month": ("basic", 1700),
    "Smart - N2,200 - 1 Month": ("smart", 2200),
    "Classic - N2,500 - 1 Month": ("classic", 2500),
    "Super - N4,200 - 1 Month": ("super", 4200),
    "Nova - N300 - 1 Week": ("nova-weekly", 300),
    "Basic - N600 - 1 Week": ("basic-weekly", 600),
    "Smart - N700 - 1 Week": ("smart-weekly", 700),
    "Classic - N1,200 - 1 Week": ("classic-weekly", 1200),
    "Super - N1,500 - 1 Week": ("super-weekly", 1500),
    "Nova - N90 - 1 Day": ("nova-daily", 90),
    "Basic - N160 - 1 Day": ("basic-daily", 160),
    "Smart - N200 - 1 Day": ("smart-daily", 200),
    "Classic - N320 - 1 Day": ("classic-daily", 320),
    "Super - N400 - 1 Day": ("super-daily", 400),
    "ewallet Amount": ("ewallet", 0),
    "Chinese (Dish) - N19,000 - 1 month": ("uni-1", 19000),
    "Nova (Antenna) - N1,900 - 1 Month": ("uni-2", 1900),
    "Classic (Dish) - N2,300 - 1 Week": ("special-weekly", 2300),
    "Classic (Dish) - N6,800 - 1 Month": ("special-monthly", 6800),
    "Nova (Dish) - N650 - 1 Week": ("nova-dish-weekly", 650),
    "Super (Antenna) - N3,000 - 1 Week": ("super-antenna-weekly", 3000),
    "Super (Antenna) - N8,800 - 1 Month": ("super-antenna-monthly", 8800),
    "Global (Dish) - N19,000 - 1 Month": ("global-monthly-dish", 19000),
    "Global (Dish) - N6,500 - 1 Week": ("global-weekly-dish", 6500),
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
        f"{BASE_URL}/service-variations?serviceID=waec",
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