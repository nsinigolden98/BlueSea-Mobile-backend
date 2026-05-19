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
    ("mtn-10mb-100", "110MB Daily Plan (1 Day) - N100"),
    ("mtn-230mb-200", "230MB Daily Plan (1 Day) - N200"),
    ("mtn-1500mb-1000", "1.5GB Weekly Plan (7 Days) - N1,000"),
    ("mtn-5.5gb-3500", "7GB Monthly Plan - N3,500"),
    ("mtn-3.5gb-1500", "3.5GB Weekly Plan (7 Days) - N1,500"),
    ("mtn-data-6500", "16.5GB Monthly Plan"),
    ("mtn-20gb-7500", "20GB Monthly Plan"),
    ("mtn-32gb-11000", "36GB Monthly Plan"),
    ("mtn-75gb-20000", "75GB Monthly Plan"),
    ("mtn-2.7gb-2000", "2.7GB + 2mins + 2GB All Night Streaming + 200MB YouTube Music, Monthly Plan - N2000"),
    ("mtn-1800mb-1500", "1.8GB + 6mins + 5 SMS, Weekly plan - N1500"),
    ("mtn-120gb-24000", "MTN N24,000 120GB - 30days"),
    ("mtn-480gb-90000", "480GB 3-Month Plan - N90,000"),
    ("mtn-1gb-350", "MTN N500 1GB + 1.5mins - 1 day"),
    ("mtn-1gb-600", "1GB+5mins Weekly Plan"),
    ("mtn-xtrabundle-500", "600MB Xtra Bundle Weekly Data (7 Days) - N500"),
    ("mtn-xtra-1000", "2GB + 2 Mins Monthly Plan - N1,500"),
    ("mtn-11gb-5000", "12.5GB Monthly Plan - N5,500"),
    ("mtn-2-5gb-900", "MTN N900 2.5GB - 2 days"),
    ("mtn-150gb-40000", "150GB 2-Month Plan"),
    ("mtn-11gb-3500", "MTN N3,500 11GB - 7 days"),
    ("mtn-500mb-ex-350", "500MB Daily Plan (1 Day) - N350"),
    ("mtn-2-5gb-ex-600", "1.5GB Daily Plan (2 Days) - N600"),
    ("mtn-2gb-ex-750", "2GB Daily Plan (2 Days) - N750"),
    ("mtn-1500mb-ex-1200", "2.7GB Xtra Bundle Monthly Plan"),
    ("mtn-8gb-ex-3000", "MTN N4,500 10GB + 10mins - 30 days"),
    ("mtn-25gb-9000", "MTN N9,000 25GB + Youtube - 30 days"),
    ("mtn-65gb-ex-16000", "65GB Monthly Plan (30 Days) - N16,000"),
    ("mtn-500mb-500", "500MB + 1GB YouTube (7 Days) - N500"),
    ("mtn-3.2gb-1000", "MTN N1000 3.2GB - 2 days"),
    ("mtn-7gb-3000", "MTN N2500 6GB - 7 days"),
    ("mtn-3.5gb-2500", "MTN N2500 3.5GB +5mins Monthly Plan"),
    ("mtn-hynetflex-14500-30", "60GB Monthly HyNetFlex Plan - N14,500"),
    ("mtn-hynetflex-75000-90", "450GB 3-Month Broadband Plan - N75,000"),
    ("mtn-hynetflex-9000-30", "30GB Monthly Broadband Plan - N9,000"),
    ("mtn-2.5-750", "2.5GB Daily Plan - 750 Naira"),
    ("mtn-20-5000", "20GB Weekly Plan - 5,000 Naira"),
    ("mtn-7gb-1800", "MTN N1800 7GB - (2 Days)"),
    ("mtn-150gb-30000", "MTN N30,000 150GB + 2GB daily - 5G Router Data (30 Days)"),
    ("mtn-165gb-35000", "MTN N35,000 165GB Monthly Data Plan (30 Days)"),
    ("mtn-200gb-37500", "MTN N37,500 200GB + 5GB Youtube/MSTeams/Zoom - 5G Router Data (30 Days)"),
    ("mtn-260gb-monthly", "MTN 260GB + 2GB daily upon exhausting main bundle - N45,000"),
    ("mtn-1500gb-yearly", "MTN 1.5TB - N225,000 Broadband Router"),
    ("mtn-6.75gb-3000", "MTN N3000 6.75GB Monthly Plan"),
    ("mtn-14.5gb-5000", "MTN 14.5GB Monthly Plan Monthly"),
    ("mtn-5.5gb-2-1500", "MTN N1500 5.5GB - (2 days)"),
    ("mtn-4gb-2-1200", "MTN N1200 4GB - (2 days)"),
    ("mtn-3.5gb-1-1000", "MTN N1000 3.5GB - (1 day)"),
    ("mtn-34gb-30-10000", "MTN N10000 34GB - (30 days)"),
]

AIRTEL_PLANS = [
    ("airt-50", "250MB Night Plan (12 - 5 AM) - 50 Naira - 1Day"),
    ("airt-100", "200MB Social Plan (2 Days) - 100 Naira - 1Day"),
    ("airt-200", "230MB Daily Plan (2 Days) - 200 Naira - 200MB - 1Day"),
    ("airt-daily-100", "Airtel Data - 100 Naira - 110MB - 1 Day"),
    ("airt-500", "500MB Weekly Plan (7 Days) - 500 Naira"),
    ("airt-1000-7", "1.5GB Weekly Plan + Youtube & Social Plans (7 Days) - 1,000 Naira"),
    ("airt-1500-7", "3.5GB Weekly Plan + Youtube & Social Platform (7 Days) - 1,500 Naira"),
    ("airt-2000", "3GB Monthly Plan + Youtube & Social Plan (30 Days)- 2,000 Naira"),
    ("airt-3000", "8GB Monthly Plan + Youtube & Social Plan (30 Days) - 3,000 Naira"),
    ("airt-4000", "10GB Monthly Plan + Youtube & Social Plan (30 Days) - 4,000 Naira"),
    ("airt-5000", "13GB Monthly Plan + Youtube & Social Plan (30 Days) - 5,000 Naira"),
    ("airt-1500-2", "5GB Binge Plan + Youtube & Social Platforms Data (2 Day) - 1,500 Naira"),
    ("airt-10000", "35GB Monthly Plan + Youtube & Social Plan (30 Days) - 10,000 Naira"),
    ("airt-15000", "60GB Monthly Plan + Youtube & Social Plan (30 Days) - 15,000 Naira"),
    ("airt-40000", "210GB Data (30 Days) - 40,000 Naira"),
    ("airt-60000", "350GB Monthly Plan + Youtube & Social Plan (120 Days) - 60,000 Naira"),
    ("airt-100000", "680GB Data (365 Days) - 100,000 Naira"),
    ("airt-20000", "100GB Monthly Plan + Youtube & Social Plan (30 Days) - 20,000 Naira"),
    ("airt-2500", "4GB Monthly Plan + Youtube & Social Plan (30 Days) - 2,500 Naira"),
    ("airt-8000", "25GB Monthly Plan + Youtube & Social Plan (30 Days) - 8,000 Naira"),
    ("airt-30000", "160GB Monthly Plan (30 Days) - 30,000 Naira"),
    ("airt-50000", "200GB Monthly Plan (90 Days) - 50,000 Naira"),
    ("airt-600", "1.5GB Binge Plan + Youtube & Social Plan Data (2 Days) - 600 Naira"),
    ("airt-1000-2", "3.2GB Binge Plan + Youtube & Social Plans Data (2 Days)  - 1000 Naira"),
    ("airt-3000-7", "10GB Weekly Plan + Youtube & Social Platform (7 Days) - 3000 Naira"),
    ("airt-5000-7", "18GB Weekly Plan + Youtube & Social Platform (7 Days) - 5000 Naira"),
    ("airt-binge-500-1", "500 Naira Binge Plan -"),
    ("airt-800-7", "1GB Weekly Plan (7 Days) - 800 Naira"),
    ("airt-6000-30", "18GB Monthly Plan + Youtube & Social Plan (30 Days) - 600 Naira"),
    ("airt-75-1", "75MB Daily Plan (1 Day) - 75 Naira"),
    ("airt-300-1", "300MB Daily Plan (1 Day) - 300 Naira"),
    ("airt-social-300-3", "1GB Social Plan Plan (3 Days) - 300 Naira"),
    ("airt-750-2", "2GB Binge Plan + Youtube & Social Plan Data (2 Days) - 750 Naira"),
    ("airt-1500-30", "2GB Monthly Plan + Youtube & Social Plan (30 Days) - 1,500 Naira"),
    ("airt-2500-7", "6GB Weekly Plan + Youtube & Social Platform (7 Days) - 2,500 Naira"),
    ("airt-mifi-5000-30", "13GB MIFI 5 Data - MiFi Only (30 Days) - 5,000 Naira"),
    ("airt-mifi-10000-30", "35GB MIFI 10 Data - MiFi Only (30 Days) - 10,000 Naira"),
    ("airt-mifi-15000-30", "60GB MIFI 15 Data - MiFi Only (30 Days) - 15,000 Naira"),
    ("airt-mifi-20000-30", "100GB Monthly Plan + Youtube & Social Plan (30 Days) - 20,000 Naira"),
    ("airt-mifi-30000-30", "Unlimited 20MBPS Data - Router Only (30 Days) - 30,000 Naira"),
    ("airt-mifi-50000-30", "Unlimited 60MBPS Data - Router Only (30 Days) - 50,000 Naira"),
    ("airt-mifi-80000-90", "Unlimited 60MBPS Data - Router Only (90 Days) - 80,000 Naira"),
    ("airt-mifi-135000-90", "Unlimited 60MBPS Data - Router Only (90 Days) - 135,000 Naira"),
    ("airt-mifi-150000-120", "Unlimited 20MBPS Data - Router Only (120 Days) - 150,000 Naira"),
    ("airt-social-500-7", "1.5GB Social Plan - 500 Naira"),
    ("airt-350-500", "500MB Daily Plan (2 Days) - 350 Naira - 500MB - 2 Days"),
]

GLO_PLANS = [
    ("glo-daily-50", "40MB + 5MB Night - N50 - 1 Day"),
    ("glo-daily-100", "120MB + 5MB Night - N100 - 1 Day"),
    ("glo-2days-200", "250MB + 25MB Night - N200 - 2 Days"),
    ("glo-monthly-1000", "1.1GB + 1.5GB Night - N1000 - 30 Days"),
    ("glo-monthly-1500", "2.2GB + 3GB - N1500 - 30 Days"),
    ("glo-monthly-2000", "3.25GB + 3GB Night - N2000 - 30 Days"),
    ("glo-monthly-2500", "4.25GB + 3GB Night - N2500 - 30 Days"),
    ("glo-monthly-3000", "8.5GB + 2GB Night - N3000 - 30 Days"),
    ("glo-monthly-4000", "10.5GB + 2GB Night - N4000 - 30 Days"),
    ("glo-monthly-5000", "14.5GB + 2.5GB Night - N5000 - 30 Days"),
    ("glo-monthly-8000", "26GB + 2GB - N8,000 - 30 Days"),
    ("glo-monthly-10000", "38GB + 4GB Night - N10,000 - 30 Days"),
    ("glo-sunday-200", "875MB 1 Day - Weekend N200"),
    ("glo-special-500", "1GB + 1GB Night - N500 - 2 Days Special"),
    ("glo-special-1500", "4GB + 2GB Night - N1,500 - 7 Days - Special"),
    ("glo-weekend-500", "2.5GB 2 Days - Weekend N500"),
    ("glo-mega-30000", "165GB 30 Days - Mega N30000"),
    ("glo-mega-40000", "220GB 30 Days - Mega N40000 Oneoff"),
    ("glo-mega-50000", "310GB 60 Days - Mega N50000"),
    ("glo-mega-60000", "355GB 90 Days - Mega N60000"),
    ("glo-mega-75000", "475GB 90 Days - Mega N75000 Oneoff"),
    ("glo-tv-150", "Glo TV VOD 500 MB 3days Oneoff"),
    ("glo-tv-450", "Glo TV VOD 2GB 7days Oneoff"),
    ("glo-tv-1400", "Glo TV VOD 6GB 30days"),
    ("glo-tv-900", "Glo TV Lite 2GB 7 Days"),
    ("glo-tv-3200", "Glo TV Max 6 GB 30 Days"),
    ("glo-social-oneoff-100", "300MB - GloMyG N100 1 Day"),
    ("glo-social-oneoff-300", "Glo MyG N300 1 GB 3 Days OneOff (Whatsapp, Instagram, Snapchat, Boomplay, Audiomac, GloTV, Tiktok)"),
    ("glo-social-oneoff-500", "Glo MyG N500 1.5 GB 7 Days (Whatsapp, Instagram, Snapchat, Boomplay, Audiomac, GloTV, Tiktok)"),
    ("glo-social-oneoff-1000", "Glo MyG N1000 3.5 GB 30 Days (Whatsapp, Instagram, Snapchat, Boomplay, Audiomac, GloTV, Tiktok)"),
    ("glo-campus-booster-100", "240MB + 5MB Night - N100 - 1 Day - Camp-Boost"),
    ("glo-campus-booster-200", "500MB + 25MB Night - N200 - 2 Days - Camp-Boost"),
    ("glo-campus-booster-500", "1.1GB + 1GB Night - N500 - 7 Days - Camp-Boost"),
    ("glo-campus-booster-1000", "2.2GB + 2GB Night - N1000 - 30 Days - Camp-Boost"),
    ("glo-campus-booster-2000", "6.5GB + 3.5GB - N2,000 - 30 Days - Camp-Boost"),
    ("glo-campus-booster-5000", "29GB + 3GB Night - N5000 - 30 Days - Camp-Boost"),
    ("glo-dg-295", "1GB (Best Value) - 295 Naira - 3 days"),
    ("glo-dg-890", "3GB (Best Value) - 890 Naira - 3 days"),
    ("glo-dg-1485", "5GB (Best Value) - 1,485 Naira - 3 days"),
    ("glo-dg-345", "1GB (Best Value) - 345 Naira - 7 days"),
    ("glo-dg-1040", "3GB (Best Value) - 1,040 Naira - 7 days"),
    ("glo-dg-1730", "5GB (Best Value) - 1,730 Naira - 7 days"),
    ("glo-dg-350", "1GB (Best Value) - 350 Naira - 14 days Night plan"),
    ("glo-dg-1040-14", "3GB (Best Value) - 1,040 Naira - 14 days Night plan"),
    ("glo-dg-1730-14", "5GB (Best Value)  - 1,730 Naira - 14 days Night plan"),
    ("glo-dg-3460", "10GB (Best Value) - 3,460 Naira - 14 days Night plan"),
    ("glo-dg-99", "200MB (Best Value) - 99 Naira - 14 days"),
    ("glo-dg-250", "500MB (Best Value) - 250 Naira - 14 days"),
    ("glo-dg-250-30", "500MB (Best Value) - N250 - 30 Days"),
    ("glo-dg-495", "1GB (Best Value) - 495 Naira - 30 days"),
    ("glo-dg-990", "2GB (Best Value) - 990 Naira - 30 days"),
    ("glo-dg-1485-30", "3GB (Best Value) - 1,485 Naira - 30 days"),
    ("glo-dg-2475", "5GB (Best Value) - 2,475 Naira - 30 days"),
    ("glo-dg-4950", "10GB (Best Value) - 4,950 Naira - 30 days"),
    ("glo-750-14", "1.1GB 14 Days - N750"),
    ("glo-1000-7days", "1.7GB + 2GB Night - N1000 - 7 Days"),
    ("glo-2000-7days", "6.5GB + 2.5GB - N2000 - 7 Days"),
    ("glo-5000-7days", "22GB + 2GB Night - N5000 - 7 Days"),
    ("glo-6000-30days", "18.5GB + 2GB Night - N6000 - 30 Days"),
    ("glo-15000-30days", "62GB + 2GB - N15,000 - 30 Days"),
    ("glo-20000-30days", "105GB + 2GB - N20,000 - 30 Days"),
    ("glo-350-special-1day", "1GB 1 Day - Special N350"),
    ("glo-600-special-2days", "1.55GB + 2GB Night - N600 - 2 Days - Special"),
    ("glo-1000-special-2days", "3.1GB + 2GB - N1000 - 2 Days - Special"),
    ("glo-25000-mega-30days", "135GB 30 Days - Mega N25000 Oneoff"),
    ("glo-yearly-mega", "1000GB Yearly - Mega N150,000 Oneoff"),
    ("glo-social-50-3days", "135MB 3 Days - Social Bundles N50"),
    ("glo-special-100-7days", "335MB 7 Days - Social Bundles N100"),
    ("glo-special-300-10days", "1.1GB 10 Days - Social Bundles N300"),
    ("glo-special-500-15days", "1.8GB 15 Days - Social Bundles N500"),
    ("glo-night-60-1day", "350MB Night - N60"),
    ("glo-night-120-1day", "750MB Night - N120"),
    ("glo-500mb-200-oneoff", "500MB 1 Day - N200 Oneoff"),
    ("glo-1000mb-300-oneoff", "1GB 1 Day - N300 Oneoff"),
    ("glo-always-on-2000", "6.1GB (410MB per day) 15 Days - Always On N2000"),
    ("glo-always-on-3500", "15GB (500MB per day) 30 Days - Always On N3500"),
    ("glo-always-on-5000", "30GB (1GB per day) 30 Days - Always On N5000"),
    ("glo-always-on-7000", "45GB (1.5 per day) 30 Days - Always On N7000"),
    ("glo-youtube-250", "1GB 1 Day - Youtube Special N250"),
    ("glo-youtube-600", "3GB 2 Days - Youtube Special N600"),
]

ETISALAT_PLANS = [
    ("eti-100", "T2 83MB - 100 Naira - 1 day"),
    ("eti-150", "T2 150MB  + 100MB Night Data - 150 Naira - 1 day"),
    ("eti-500", "T2 650MB - 500 Naira - 3 days"),
    ("eti-1000", "9mobile 2GB - 1,000 Naira - 30 Days"),
    ("eti-4000", "T2 8.4GB - 4,000 Naira - 30 days"),
    ("eti-2000", "T2 4.5GB - 2000 Naira - 30 Days"),
    ("eti-5000", "T2 11.4GB - 5,000 Naira - 30 Days"),
    ("eti-3000", "T2 6.2G - 3,000 Naira - 30 days"),
    ("eti-1200", "T2 2.3GB - 1,200 Naira - 30 Days"),
    ("eti-50", "T2 40MB - 50 Naira - 1 day"),
    ("eti-2500", "T2 5.2GB - 2,500 Naira - 30 days"),
    ("t2-250mb-200", "T2 N200 - 250MB Anytime Data Plan (7 Days)"),
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
    # max_length increased to 150 to safely accommodate longer modern frontend VTU plan IDs and future expansions
    plan = models.CharField(max_length=150, choices=MTN_PLANS)
    billersCode = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=11, db_index=True)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.phone_number} - {self.plan}"


class AirtelDataTopUp(models.Model):
    # max_length increased to 150 to safely accommodate longer modern frontend VTU plan IDs and future expansions
    plan = models.CharField(max_length=150, choices=AIRTEL_PLANS)
    billersCode = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=11, db_index=True)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.phone_number} - {self.plan}"


class GloDataTopUp(models.Model):
    # max_length increased to 150 to safely accommodate longer modern frontend VTU plan IDs and future expansions
    plan = models.CharField(max_length=150, choices=GLO_PLANS)
    billersCode = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=11, db_index=True)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.phone_number} - {self.plan}"


class EtisalatDataTopUp(models.Model):
    # max_length increased to 150 to safely accommodate longer modern frontend VTU plan IDs and future expansions
    plan = models.CharField(max_length=150, choices=ETISALAT_PLANS)
    billersCode = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=11, db_index=True)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.phone_number} - {self.plan}"


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
