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
    ("1.5GB Weekly Plan (7 Days) - N1,000", "mtn-1500mb-1000"),
    ("1.8GB + 6mins + 5 SMS, Monthly - N1500", "mtn-1800mb-1500"),
    ("110MB Daily Plan (1 Day) - N100", "mtn-10mb-100"),
    ("12.5GB  14 days - N4,500", "mtn-12gb-7d-4500"),
    ("150GB 2-Month Plan - N40,000", "mtn-150gb-40000"),
    ("15GB Weekly Plan - N4,000", "mtn-15gb-7d-4000"),
    ("16.5GB + 10mins Monthly Plan - N,6500", "mtn-data-6500"),
    ("18GB - 14 days - N6,000", "mtn-14d-18gb-6000"),
    ("2.5GB Daily Plan - 750 Naira", "mtn-2.5-750"),
    (
        "2.7GB + 2mins + 2GB All Night Streaming + 200MB YouTube Music, Monthly Plan - N2000",
        "mtn-2.7gb-2000",
    ),
    ("20GB Monthly Plan - N7,500", "mtn-20gb-7500"),
    ("20GB Weekly Plan - 5,000 Naira", "mtn-20-5000"),
    ("230MB Daily Plan (1 Day) - N200", "mtn-230mb-200"),
    ("28GB - 14 days - N8,000", "mtn-14d-28gb-8000"),
    ("2GB + 2 Mins Monthly Plan - N1,500", "mtn-xtra-1000"),
    ("2GB Daily Plan (2 Days) - N750", "mtn-2gb-ex-750"),
    ("3.5GB Weekly Plan (7 Days) - N1,500", "mtn-3.5gb-1500"),
    ("30GB Monthly Broadband Plan - N9,000", "mtn-hynetflex-9000-30"),
    ("36GB Monthly Plan - N11,000", "mtn-32gb-11000"),
    ("40GB - 14 days - N10,000", "mtn-14d-40gb-10000"),
    ("450GB 3-Month Broadband Plan - N75,000", "mtn-hynetflex-75000-90"),
    ("480GB 3-Month Plan - N90,000", "mtn-480gb-90000"),
    ("500MB + 1GB YouTube (7 Days) - N500", "mtn-500mb-500"),
    ("500MB Daily Plan (1 Day) - N350", "mtn-500mb-ex-350"),
    ("600MB Xtra Bundle + 2mins -7 Days - N500", "mtn-xtrabundle-500"),
    ("60GB Monthly Broadband Plan - N14,500", "mtn-hynetflex-14500-30"),
    ("65GB Monthly Plan (30 Days) - N16,000", "mtn-65gb-ex-16000"),
    ("75GB Monthly Plan - N18,000", "mtn-75gb-20000"),
    ("7GB Monthly Plan - N3,500", "mtn-5.5gb-3500"),
    ("MTN 1.5TB - N225,000 Broadband Router", "mtn-1500gb-yearly"),
    ("MTN 14.5GB Monthly Plan - N5,000", "mtn-14.5gb-5000"),
    (
        "MTN 260GB + 2GB daily upon exhausting main bundle - N45,000",
        "mtn-260gb-monthly",
    ),
    ("MTN N,2500 3.5GB +5mins Monthly Plan", "mtn-3.5gb-2500"),
    ("MTN N1,000 3.2GB - 2 days", "mtn-3.2gb-1000"),
    ("MTN N1,000 3.5GB - (1 day)", "mtn-3.5gb-1-1000"),
    ("MTN N1,200 4GB - (2 days)", "mtn-4gb-2-1200"),
    ("MTN N1,500 5.5GB - (2 days)", "mtn-5.5gb-2-1500"),
    ("MTN N1,800 7GB - (2 Days)", "mtn-7gb-1800"),
    ("MTN N10,000 34GB - (30 days)", "mtn-34gb-30-10000"),
    ("MTN N24,000 120GB  - 30days", "mtn-120gb-24000"),
    ("MTN N2500 6GB - 7 days", "mtn-7gb-3000"),
    ("MTN N3,000 6.75GB Monthly", "mtn-6.75gb-3000"),
    ("MTN N3,500 11GB  - 7 days", "mtn-11gb-3500"),
    ("MTN N30,000 150GB + 2GB daily - 5G Router Data (30 Days)", "mtn-150gb-30000"),
    ("MTN N35,000 165GB Monthly Data Plan (30 Days)", "mtn-165gb-35000"),
    (
        "MTN N37,500 200GB + 5GB Youtube/MSTeams/Zoom - 5G Broadband Data (30 Days)",
        "mtn-200gb-37500",
    ),
    ("MTN N4,500 10GB + 10mins  - 30 days", "mtn-8gb-ex-3000"),
    ("MTN N500 1GB + 1.5mins - 1 day", "mtn-1gb-350"),
    ("MTN N900 2.5GB - 2 days", "mtn-2-5gb-900"),
    ("N800 1GB + 1GB YouTube Night + 100MB YouTube Music - Weekly", "mtn-1gb-600"),
]

AIRTEL_PLANS = [
    (
        "1,000 Naira - 4GB Plan + 2GB YouTube Night + 200MB YT/IG/TT(2 Days)",
        "airt-1000-2",
    ),
    ("1.5GB Binge Plan + Youtube & Social Plan Data (2 Days) - 600 Naira", "airt-600"),
    ("1.5GB Social Plan - 500 Naira", "airt-social-500-7"),
    (
        "1.5GB Weekly Plan + Youtube & Social Plans (7 Days) - 1,000 Naira",
        "airt-1000-7",
    ),
    (
        "100GB Monthly Plan + Youtube & Social Plan (30 Days) - 20,000 Naira",
        "airt-20000",
    ),
    (
        "100GB Unlimited Uiltra 20 - Router Only (30 Days) - 20,000 Naira",
        "airt-mifi-20000-30",
    ),
    ("10GB Monthly Plan + Youtube & Social Plan (30 Days) - 4,000 Naira", "airt-4000"),
    (
        "10GB Weekly Plan + Youtube & Social Platform (7 Days) - 3000 Naira",
        "airt-3000-7",
    ),
    ("13GB MIFI 5 Data - MiFi Only (30 Days) - 5,000 Naira", "airt-mifi-5000-30"),
    ("13GB Monthly Plan + Youtube & Social Plan (30 Days) - 5,000 Naira", "airt-5000"),
    ("160GB Monthly Plan (30 Days) - 30,000 Naira", "airt-30000"),
    (
        "18GB Monthly Plan + Youtube & Social Plan (30 Days) - 6000 Naira",
        "airt-6000-30",
    ),
    (
        "18GB Weekly Plan + Youtube & Social Platform (7 Days) - 5000 Naira",
        "airt-5000-7",
    ),
    ("1GB Social Plan Plan (3 Days) - 300 Naira", "airt-social-300-3"),
    ("1GB Weekly Plan (7 Days) - 800 Naira", "airt-800-7"),
    ("200GB Monthly Plan (90 Days) - 50,000 Naira", "airt-50000"),
    ("200MB Social Plan (2 Days) - 100 Naira - 1Day", "airt-100"),
    ("210GB Data (30 Days) - 40,000 Naira", "airt-40000"),
    ("230MB Daily Plan (2 Days) - 200 Naira - 200MB - 1Day", "airt-200"),
    ("250MB Night Plan (12 - 5 AM) - 50 Naira  - 1Day", "airt-50"),
    ("25GB Monthly Plan + Youtube & Social Plan (30 Days) - 8,000 Naira", "airt-8000"),
    ("2GB Binge Plan + Youtube & Social Plan Data (2 Days) - 750 Naira", "airt-750-2"),
    (
        "2GB Monthly Plan + Youtube & Social Plan (30 Days) - 1,500 Naira",
        "airt-1500-30",
    ),
    (
        "3.5GB Weekly Plan + Youtube & Social Platform (7 Days) - 1,500 Naira",
        "airt-1500-7",
    ),
    ("300MB Daily Plan (1 Day) - 300 Naira", "airt-300-1"),
    (
        "350GB Monthly Plan + Youtube & Social Plan (120 Days) - 60,000 Naira",
        "airt-60000",
    ),
    ("35GB MIFI 10 Data - MiFi Only (30 Days) - 10,000 Naira", "airt-mifi-10000-30"),
    (
        "35GB Monthly Plan + Youtube & Social Plan (30 Days) - 10,000 Naira",
        "airt-10000",
    ),
    ("3GB Monthly Plan + Youtube & Social Plan (30 Days)- 2,000 Naira", "airt-2000"),
    ("4GB Monthly Plan + Youtube & Social Plan (30 Days) - 2,500 Naira", "airt-2500"),
    ("500 Naira Binge Plan 1GB", "airt-binge-500-1"),
    ("500MB Daily Plan (2 Days) - 350 Naira - 500MB - 2 Days", "airt-350-500"),
    ("500MB Weekly Plan (7 Days) - 500 Naira", "airt-500"),
    (
        "5GB Binge Plan + Youtube & Social Platforms Data (2 Day) - 1,500 Naira",
        "airt-1500-2",
    ),
    ("60GB MIFI 15 Data - MiFi Only (30 Days) - 15,000 Naira", "airt-mifi-15000-30"),
    (
        "60GB Monthly Plan + Youtube & Social Plan (30 Days) - 15,000 Naira",
        "airt-15000",
    ),
    ("680GB Data (365 Days) - 100,000 Naira", "airt-100000"),
    (
        "6GB Weekly Plan + Youtube & Social Platform (7 Days) - 2,500 Naira",
        "airt-2500-7",
    ),
    ("75MB Daily Plan (1 Day) - 75 Naira", "airt-75-1"),
    ("8GB Monthly Plan + Youtube & Social Plan (30 Days) - 3,000 Naira", "airt-3000"),
    ("Airtel Data - 100 Naira - 110MB - 1 Day", "airt-daily-100"),
    (
        "Unlimited 20MBPS Data - Router Only (120 Days) - 150,000 Naira",
        "airt-mifi-150000-120",
    ),
    (
        "Unlimited 20MBPS Data - Router Only (30 Days) - 30,000 Naira",
        "airt-mifi-30000-30",
    ),
    (
        "Unlimited 60MBPS Data - Router Only (30 Days) - 50,000 Naira",
        "airt-mifi-50000-30",
    ),
    (
        "Unlimited 60MBPS Data - Router Only (90 Days) - 135,000 Naira",
        "airt-mifi-135000-90",
    ),
    (
        "Unlimited 60MBPS Data - Router Only (90 Days) - 80,000 Naira",
        "airt-mifi-80000-90",
    ),
]

GLO_PLANS = [
    ("1.1GB + 1.5GB Night - N1000 - 30 Days", "glo-monthly-1000"),
    ("1.1GB + 1GB Night - N500 - 7 Days - Camp-Boost", "glo-campus-booster-500"),
    ("1.1GB 10 Days - Social Bundles N300", "glo-special-300-10days"),
    ("1.1GB 14 Days - N750", "glo-750-14"),
    ("1.55GB + 2GB Night - N600 - 2 Days - Special", "glo-600-special-2days"),
    ("1.7GB + 2GB Night - N1000 - 7 Days", "glo-1000-7days"),
    ("1.8GB 15 Days - Social Bundles N500", "glo-special-500-15days"),
    ("10.5GB + 2GB Night - N4000 - 30 Days", "glo-monthly-4000"),
    ("1000GB Yearly - Mega N150,000 Oneoff", "glo-yearly-mega"),
    ("105GB + 2GB - N20,000 - 30 Days", "glo-20000-30days"),
    ("10GB - 3,725 Naira - 14 days Night plan (Best Value)", "glo-dg-3460"),
    ("10GB - 4,950 Naira - 30 days (Best Value)", "glo-dg-4950"),
    ("120MB + 5MB Night - N100 - 1 Day", "glo-daily-100"),
    ("135GB 30 Days - Mega N25000 Oneoff", "glo-25000-mega-30days"),
    ("135MB 3 Days - Social Bundles N50", "glo-social-50-3days"),
    ("14.5GB + 2.5GB Night - N5000 - 30 Days", "glo-monthly-5000"),
    ("15GB (500MB per day) 30 Days - Always On N3500", "glo-always-on-3500"),
    ("165GB 30 Days - Mega N30000", "glo-mega-30000"),
    ("18.5GB + 2GB Night - N6000 - 30 Days", "glo-6000-30days"),
    ("1GB + 1GB Night - N500 - 2 Days Special", "glo-special-500"),
    ("1GB - 330 Naira - 3 days (Best Value)", "glo-dg-295"),
    ("1GB - 366 Naira - 14 days Night plan (Best Value)", "glo-dg-350"),
    ("1GB - 366 Naira - 7 days (Best Value)", "glo-dg-345"),
    ("1GB - 495 Naira - 30 days (Best Value)", "glo-dg-495"),
    ("1GB 1 Day - N300 Oneoff", "glo-1000mb-300-oneoff"),
    ("1GB 1 Day - Special N350", "glo-350-special-1day"),
    ("1GB 1 Day - Youtube Special N250", "glo-youtube-250"),
    ("2.2GB + 2GB Night - N1000 - 30 Days - Camp-Boost", "glo-campus-booster-1000"),
    ("2.2GB + 3GB - N1500 - 30 Days", "glo-monthly-1500"),
    ("2.5GB 2 Days - Weekend N500", "glo-weekend-500"),
    ("200MB - 99 Naira - 14 days (Best Value)", "glo-dg-99"),
    ("220GB 30 Days - Mega N40000 Oneoff", "glo-mega-40000"),
    ("22GB + 2GB Night - N5000 - 7 Days", "glo-5000-7days"),
    ("240MB + 5MB Night - N100 - 1 Day - Camp-Boost", "glo-campus-booster-100"),
    ("250MB + 25MB Night - N200 - 2 Days", "glo-2days-200"),
    ("26GB + 2GB - N8,000 - 30 Days", "glo-monthly-8000"),
    ("29GB + 3GB Night - N5000 - 30 Days - Camp-Boost", "glo-campus-booster-5000"),
    ("2GB - 990 Naira - 30 days (Best Value)", "glo-dg-990"),
    ("3.1GB + 2GB - N1000 - 2 Days - Special", "glo-1000-special-2days"),
    ("3.25GB + 3GB Night - N2000 - 30 Days", "glo-monthly-2000"),
    ("300MB - GloMyG N100 1 Day", "glo-social-oneoff-100"),
    ("30GB (1GB per day) 30 Days - Always On N5000", "glo-always-on-5000"),
    ("310GB 60 Days - Mega N50000", "glo-mega-50000"),
    ("335MB 7 Days - Social Bundles N100", "glo-special-100-7days"),
    ("350MB Night - N60", "glo-night-60-1day"),
    ("355GB 90 Days - Mega N60000", "glo-mega-60000"),
    ("38GB + 4GB Night - N10,000 - 30 Days", "glo-monthly-10000"),
    ("3GB - 1,005 Naira - 3 days (Best Value)", "glo-dg-890"),
    ("3GB - 1,110 Naira - 14 days Night plan (Best Value)", "glo-dg-1040-14"),
    ("3GB - 1,110 Naira - 7 days (Best Value)", "glo-dg-1040"),
    ("3GB - 1,485 Naira - 30 days (Best Value)", "glo-dg-1485"),
    ("3GB 2 Days - Youtube Special N600", "glo-youtube-600"),
    ("3GB 5GB - 2,475 Naira - 30 days (Best Value)", "glo-dg-2475"),
    ("4.25GB + 3GB Night - N2500 - 30 Days", "glo-monthly-2500"),
    ("40MB + 5MB Night - N50 - 1 Day", "glo-daily-50"),
    ("45GB (1.5 per day) 30 Days - Always On N7000", "glo-always-on-7000"),
    ("475GB 90 Days - Mega N75000 Oneoff", "glo-mega-75000"),
    ("4GB + 2GB Night - N1,500 - 7 Days - Special", "glo-special-1500"),
    ("500MB + 25MB Night - N200 - 2 Days - Camp-Boost", "glo-campus-booster-200"),
    ("500MB - 250 Naira - 14 days (Best Value)", "glo-dg-250"),
    ("500MB - 250 Naira - 30 days (Best Value)", "glo-dg-250-30"),
    ("500MB 1 Day - N200 Oneoff", "glo-500mb-200-oneoff"),
    ("5GB - 1,875 Naira - 14 days Night plan (Best Value)", "glo-dg-1730"),
    ("6.1GB (410MB per day) 15 Days - Always On N2000", "glo-always-on-2000"),
    ("6.5GB + 2.5GB - N2000 - 7 Days", "glo-2000-7days"),
    ("6.5GB + 3.5GB - N2,000 - 30 Days - Camp-Boost", "glo-campus-booster-2000"),
    ("62GB + 2GB - N15,000 - 30 Days", "glo-15000-30days"),
    ("750MB Night - N120", "glo-night-120-1day"),
    ("8.5GB + 2GB Night - N3000 - 30 Days", "glo-monthly-3000"),
    ("875MB 1 Day - Weekend N200", "glo-sunday-200"),
    (
        "Glo MyG N1000 3.5 GB 30 Days (Whatsapp, Instagram, Snapchat, Boomplay, Audiomac, GloTV, Tiktok)",
        "glo-social-oneoff-1000",
    ),
    (
        "Glo MyG N300 1 GB 3 Days OneOff (Whatsapp, Instagram, Snapchat, Boomplay, Audiomac, GloTV, Tiktok)",
        "glo-social-oneoff-300",
    ),
    (
        "Glo MyG N500 1.5 GB 7 Days (Whatsapp, Instagram, Snapchat, Boomplay, Audiomac, GloTV, Tiktok)",
        "glo-social-oneoff-500",
    ),
    ("Glo TV Lite 2GB 7 Days", "glo-tv-900"),
    ("Glo TV Max 6 GB 30 Days", "glo-tv-3200"),
    ("Glo TV VOD 2GB 7days Oneoff", "glo-tv-450"),
    ("Glo TV VOD 500 MB 3days Oneoff", "glo-tv-150"),
    ("Glo TV VOD 6GB 30days", "glo-tv-1400"),
]

ETISALAT_PLANS = [
    ("9mobile 10 GB SME plan", "9mobile-sme-data-10gb"),
    ("9mobile 100 GB SME plan", "9mobile-sme-data-100gb"),
    ("9mobile 100mb SME plan", "9mobile-sme-data-100mb"),
    ("9mobile 15 GB SME plan", "9mobile-sme-data-15gb"),
    ("9mobile 1GB SME plan", "9mobile-sme-data-1gb"),
    ("9mobile 2 GB SME plan", "9mobile-sme-data-2gb"),
    ("9mobile 20 GB SME plan", "9mobile-sme-data-20gb"),
    ("9mobile 200mb SME plan", "9mobile-sme-data-200mb"),
    ("9mobile 25 GB SME plan", "9mobile-sme-data-25gb"),
    ("9mobile 2GB - 1,000 Naira - 30 Days", "eti-1000"),
    ("9mobile 3 GB SME plan", "9mobile-sme-data-3gb"),
    ("9mobile 4 GB SME plan", "9mobile-sme-data-4gb"),
    ("9mobile 5 GB SME plan", "9mobile-sme-data-5gb"),
    ("9mobile 50 GB SME plan", "9mobile-sme-data-50gb"),
    ("9mobile 500mb SME plan", "9mobile-sme-data-500mb"),
    ("9mobile 50mb SME plan", "9mobile-sme-data-50mb"),
    ("T2 11.4GB - 5,000 Naira - 30 Days", "eti-5000"),
    ("T2 150MB  + 100MB Night Data - 150 Naira - 1 day", "eti-150"),
    ("T2 2.3GB - 1,200 Naira - 30 Days", "eti-1200"),
    ("T2 4.5GB - 2000 Naira - 30 Days", "eti-2000"),
    ("T2 40MB - 50 Naira - 1 day", "eti-50"),
    ("T2 5.2GB - 2,500 Naira - 30 days", "eti-2500"),
    ("T2 6.2G - 3,000 Naira - 30 days", "eti-3000"),
    ("T2 650MB - 500 Naira - 3 days", "eti-500"),
    ("T2 8.4GB - 4,000 Naira - 30 days", "eti-4000"),
    ("T2 83MB - 100 Naira - 1 day", "eti-100"),
    ("T2 N200 - 250MB Anytime Data Plan (7 Days)", "t2-250mb-200"),
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
    ("DStv  Compact + Showmax N21,250", "dstv-compact-showmax"),
    ("DStv  Compact N19,000", "dstv79"),
    ("DStv Asia + Showmax N19,400", "dstv-asia-showmax"),
    ("DStv Compact + Extra View N25,000", "dstv30"),
    ("DStv Compact + French Plus N43,500", "dstv47"),
    ("DStv Compact + French Touch + ExtraView N32,000", "com-frenchtouch-extra"),
    ("DStv Compact + French Touch N26,000", "com-frenchtouch"),
    ("DStv Compact Plus + Extra View N36,000", "dstv45"),
    ("DStv Compact Plus + French Plus N54,500", "dstv43"),
    ("DStv Compact Plus + French Touch N37,000", "complus-frenchtouch"),
    ("DStv Compact Plus + FrenchPlus + Extra View N60,500", "complus-french-extraview"),
    ("DStv Compact Plus + Showmax N32,250", "dstv-compact-plus-showmax"),
    ("DStv Compact Plus Movie Bundle Add-on E36 - N3,500", "dstv-compact-plus-movie"),
    ("DStv Compact Plus N30,000", "dstv7"),
    ("DStv Confam + ExtraView N17,000", "confam-extra"),
    ("DStv French 11 N10,800", "french11"),
    ("DStv French Plus Add-on N24,500", "frenchplus-addon"),
    ("DStv French Touch Add-on N7,000", "frenchtouch-addon"),
    ("DStv Great Wall Standalone Bouquet + Showmax N8,300", "dstv-greatwall-showmax"),
    ("DStv Great Wall Standalone Bouquet N3,800", "dstv-greatwall"),
    ("DStv India Add-on N14,900", "dstv-indian-add-on"),
    ("DStv Indian N14,900", "dstv-indian"),
    ("DStv Movie Bundle Add-on N3500", "dstv-movie-bundle-add-on"),
    ("DStv Padi + ExtraView N10,400", "padi-extra"),
    ("DStv Padi + Showmax N8,900", "dstv-padi-showmax"),
    ("DStv Padi N4,400", "dstv-padi"),
    ("DStv Premium + Extra View N50,500", "dstv33"),
    ("DStv Premium + French + Extra View N75,000", "dstv62"),
    ("DStv Premium + French + Showmax N69,000", "dstv-premium-french-showmax"),
    ("DStv Premium + Showmax N44,500", "dstv-premium-showmax"),
    ("DStv Premium N44,500", "dstv3"),
    ("DStv Premium W/Afr + Showmax N50,500", "dstv-premium-wafr-showmax"),
    ("DStv Premium-Asia N50,500", "dstv10"),
    ("DStv Premium-French N69,000", "dstv9"),
    ("DStv Showmax Premier League Add-on N3,600", "dstv-showmax-premier-league"),
    ("DStv Yanga + ExtraView N12,000", "yanga-extra"),
    ("DStv Yanga + Showmax N8,250", "dstv-yanga-showmax"),
    ("DStv Yanga N6,000", "dstv-yanga"),
    ("Dstv Confam + Showmax N13,250", "dstv-confam-showmax"),
    ("Dstv Confam N11,000", "dstv-confam"),
]

GOTV_PLANS = [
    ("GOtv Jinja N3,900", "gotv-jinja"),
    ("GOtv Jolli N5,800", "gotv-jolli"),
    ("GOtv Max N8,500", "gotv-max"),
    ("GOtv Smallie - monthly N1900", "gotv-smallie"),
    ("GOtv Smallie - quarterly N5,100", "gotv-smallie-3months"),
    ("GOtv Smallie - yearly N15,000", "gotv-smallie-1year"),
    ("GOtv Supa - monthly N11,400", "gotv-supa"),
    ("GOtv Supa Plus - monthly N16,800", "gotv-supa-plus"),
]

SUB_TYPE = [("change", "change"), ("renew", "renew")]

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
    ("Basic (Antenna) - 1400 Naira - 1 Week", "basic-weekly"),
    ("Basic (Antenna) - 4,000 Naira - 1 Month", "basic"),
    ("Basic (Dish) - 1,700 Naira - 1 Week", "smart-weekly"),
    ("Basic (Dish) - 5,100 Naira - 1 Month", "smart"),
    ("Chinese (Dish) - 21,000 Naira - 1 month", "uni-1"),
    ("Classic (Antenna) - 2000 Naira - 1 Week", "classic-weekly"),
    ("Classic (Antenna) - 6000 Naira - 1 Month", "classic"),
    ("Classic (Dish) - 2300 Naira - 1 Week", "special-weekly"),
    ("Classic (Dish) - 2500 Naira - 1 Week", "classic-weekly-dish"),
    ("Classic (Dish) - 7400 Naira - 1 Month", "special-monthly"),
    ("Global (Dish) - 21000 Naira - 1 Month", "global-monthly-dish"),
    ("Global (Dish) - 7000 Naira - 1Week", "global-weekly-dish"),
    ("Nova (Antenna) - 2,100 Naira - 1 Month", "uni-2"),
    ("Nova (Antenna) - 700 Naira - 1 Week", "nova-weekly"),
    ("Nova (Dish) - 2100 Naira - 1 Month", "nova"),
    ("Nova (Dish) - 700 Naira - 1 Week", "nova-dish-weekly"),
    ("Startimes SHS - 12,000 Naira - Monthly", "shs-monthly-12000"),
    ("Startimes SHS - 19,800 Naira - Monthly", "shs-monthly-19800"),
    ("Startimes SHS - 2,800 Naira - Weekly", "shs-weekly-2800"),
    ("Startimes SHS - 21,000 Naira - Monthly", "shs-monthly-21000"),
    ("Startimes SHS - 39,000 Naira - Monthly", "shs-monthly-39000"),
    ("Startimes SHS - 4,620 Naira - Weekly", "shs-weekly-4620"),
    ("Startimes SHS - 4,900 Naira - Weekly", "shs-weekly-4900"),
    ("Startimes SHS - 9,100 Naira - Weekly", "shs-weekly-9100"),
    ("Super (Antenna) - 3,200 Naira - 1 Week", "super-antenna-weekly"),
    ("Super (Antenna) - 9,500 Naira - 1 Month", "super-antenna-monthly"),
    ("Super (Dish) - 3,300 Naira - 1 Week", "super-weekly"),
    ("Super (Dish) - 9,800 Naira - 1 Month", "super"),
]


class AirtimeTopUp(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.CASCADE,
        related_name="airtime_topups",
    )
    amount = models.IntegerField()
    network = models.CharField(max_length=10, choices=NETWORK_TYPES)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class MTNDataTopUp(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.CASCADE,
        related_name="mtn_data_topups",
    )
    plan = models.CharField(max_length=120, choices=MTN_PLANS)
    billersCode = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AirtelDataTopUp(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.CASCADE,
        related_name="airtel_data_topups",
    )
    plan = models.CharField(max_length=100, choices=AIRTEL_PLANS)
    billersCode = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class GloDataTopUp(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.CASCADE,
        related_name="glo_data_topups",
    )
    plan = models.CharField(max_length=100, choices=GLO_PLANS)
    billersCode = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class EtisalatDataTopUp(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.CASCADE,
        related_name="etisalat_data_topups",
    )
    plan = models.CharField(max_length=100, choices=ETISALAT_PLANS)
    billersCode = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class DSTVPayment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.CASCADE,
        related_name="dstv_payments",
    )
    billersCode = models.CharField(max_length=20)
    dstv_plan = models.CharField(max_length=100, choices=DSTV_PLANS)
    subscription_type = models.CharField(max_length=20, choices=SUB_TYPE)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class GOTVPayment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.CASCADE,
        related_name="gotv_payments",
    )
    billersCode = models.CharField(max_length=20)
    gotv_plan = models.CharField(max_length=100, choices=GOTV_PLANS)
    subscription_type = models.CharField(max_length=20, choices=SUB_TYPE)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class StartimesPayment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.CASCADE,
        related_name="startimes_payments",
    )
    billersCode = models.CharField(max_length=20)
    startimes_plan = models.CharField(max_length=100, choices=STARTIMES_PLANS)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ShowMaxPayment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.CASCADE,
        related_name="showmax_payments",
    )
    showmax_plan = models.CharField(max_length=100, choices=SHOWMAX_PLANS)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ElectricityPayment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.CASCADE,
        related_name="electricity_payments",
    )
    billerCode = models.CharField(max_length=20)
    amount = models.IntegerField()
    biller_name = models.CharField(max_length=30, choices=BILLER_NAME)
    meter_type = models.CharField(max_length=20, choices=METER_TYPES)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class WAECRegitration(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.CASCADE,
        related_name="waec_registrations",
    )
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class WAECResultChecker(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.CASCADE,
        related_name="waec_result_checks",
    )
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class JAMBRegistration(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.CASCADE,
        related_name="jamb_registrations",
    )
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
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.CASCADE,
        related_name="airtime2cash_records",
    )
    amount = models.IntegerField()
    network = models.CharField(max_length=10, choices=NETWORK_TYPES)
    phone_number = models.CharField(max_length=11)
    request_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ElectricityPaymentCustomers(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.CASCADE,
        related_name="electricity_customer_lookups",
    )
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
    payment_reference = models.CharField(
        max_length=100, unique=True, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Withdrawal {self.amount} to {self.account_name} {self.account_number} - {self.status}"

    class Meta:
        ordering = ["-created_at"]
