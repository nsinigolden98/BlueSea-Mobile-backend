//! VTpass plan catalog. GENERATED from `payments/vtpass.py` dicts —
//! do not hand-edit; re-run the generator. Each entry is
//! (display name shown to clients, VTpass variation code, price in naira).

pub struct Plan {
    pub display: &'static str,
    pub code: &'static str,
    pub price_naira: i64,
}

pub const MTN_PLANS: &[Plan] = &[
    Plan { display: "1.5GB Weekly Plan (7 Days) - N1,000", code: "mtn-1500mb-1000", price_naira: 1000 },
    Plan { display: "1.8GB + 6mins + 5 SMS, Monthly - N1500", code: "mtn-1800mb-1500", price_naira: 1500 },
    Plan { display: "110MB Daily Plan (1 Day) - N100", code: "mtn-10mb-100", price_naira: 100 },
    Plan { display: "12.5GB  14 days - N4,500", code: "mtn-12gb-7d-4500", price_naira: 4500 },
    Plan { display: "150GB 2-Month Plan - N40,000", code: "mtn-150gb-40000", price_naira: 40000 },
    Plan { display: "15GB Weekly Plan - N4,000", code: "mtn-15gb-7d-4000", price_naira: 4000 },
    Plan { display: "16.5GB + 10mins Monthly Plan - N,6500", code: "mtn-data-6500", price_naira: 6500 },
    Plan { display: "18GB - 14 days - N6,000", code: "mtn-14d-18gb-6000", price_naira: 6000 },
    Plan { display: "2.5GB Daily Plan - 750 Naira", code: "mtn-2.5-750", price_naira: 750 },
    Plan { display: "2.7GB + 2mins + 2GB All Night Streaming + 200MB YouTube Music, Monthly Plan - N2000", code: "mtn-2.7gb-2000", price_naira: 2000 },
    Plan { display: "20GB Monthly Plan - N7,500", code: "mtn-20gb-7500", price_naira: 7500 },
    Plan { display: "20GB Weekly Plan - 5,000 Naira", code: "mtn-20-5000", price_naira: 5000 },
    Plan { display: "230MB Daily Plan (1 Day) - N200", code: "mtn-230mb-200", price_naira: 200 },
    Plan { display: "28GB - 14 days - N8,000", code: "mtn-14d-28gb-8000", price_naira: 8000 },
    Plan { display: "2GB + 2 Mins Monthly Plan - N1,500", code: "mtn-xtra-1000", price_naira: 1500 },
    Plan { display: "2GB Daily Plan (2 Days) - N750", code: "mtn-2gb-ex-750", price_naira: 750 },
    Plan { display: "3.5GB Weekly Plan (7 Days) - N1,500", code: "mtn-3.5gb-1500", price_naira: 1500 },
    Plan { display: "30GB Monthly Broadband Plan - N9,000", code: "mtn-hynetflex-9000-30", price_naira: 9000 },
    Plan { display: "36GB Monthly Plan - N11,000", code: "mtn-32gb-11000", price_naira: 11000 },
    Plan { display: "40GB - 14 days - N10,000", code: "mtn-14d-40gb-10000", price_naira: 10000 },
    Plan { display: "450GB 3-Month Broadband Plan - N75,000", code: "mtn-hynetflex-75000-90", price_naira: 75000 },
    Plan { display: "480GB 3-Month Plan - N90,000", code: "mtn-480gb-90000", price_naira: 90000 },
    Plan { display: "500MB + 1GB YouTube (7 Days) - N500", code: "mtn-500mb-500", price_naira: 500 },
    Plan { display: "500MB Daily Plan (1 Day) - N350", code: "mtn-500mb-ex-350", price_naira: 350 },
    Plan { display: "600MB Xtra Bundle + 2mins -7 Days - N500", code: "mtn-xtrabundle-500", price_naira: 500 },
    Plan { display: "60GB Monthly Broadband Plan - N14,500", code: "mtn-hynetflex-14500-30", price_naira: 14500 },
    Plan { display: "65GB Monthly Plan (30 Days) - N16,000", code: "mtn-65gb-ex-16000", price_naira: 16000 },
    Plan { display: "75GB Monthly Plan - N18,000", code: "mtn-75gb-20000", price_naira: 18000 },
    Plan { display: "7GB Monthly Plan - N3,500", code: "mtn-5.5gb-3500", price_naira: 3500 },
    Plan { display: "MTN 1.5TB - N225,000 Broadband Router", code: "mtn-1500gb-yearly", price_naira: 225000 },
    Plan { display: "MTN 14.5GB Monthly Plan - N5,000", code: "mtn-14.5gb-5000", price_naira: 5000 },
    Plan { display: "MTN 260GB + 2GB daily upon exhausting main bundle - N45,000", code: "mtn-260gb-monthly", price_naira: 45000 },
    Plan { display: "MTN N,2500 3.5GB +5mins Monthly Plan", code: "mtn-3.5gb-2500", price_naira: 2500 },
    Plan { display: "MTN N1,000 3.2GB - 2 days", code: "mtn-3.2gb-1000", price_naira: 1000 },
    Plan { display: "MTN N1,000 3.5GB - (1 day)", code: "mtn-3.5gb-1-1000", price_naira: 1000 },
    Plan { display: "MTN N1,200 4GB - (2 days)", code: "mtn-4gb-2-1200", price_naira: 1200 },
    Plan { display: "MTN N1,500 5.5GB - (2 days)", code: "mtn-5.5gb-2-1500", price_naira: 1500 },
    Plan { display: "MTN N1,800 7GB - (2 Days)", code: "mtn-7gb-1800", price_naira: 1800 },
    Plan { display: "MTN N10,000 34GB - (30 days)", code: "mtn-34gb-30-10000", price_naira: 10000 },
    Plan { display: "MTN N24,000 120GB  - 30days", code: "mtn-120gb-24000", price_naira: 24000 },
    Plan { display: "MTN N2500 6GB - 7 days", code: "mtn-7gb-3000", price_naira: 2500 },
    Plan { display: "MTN N3,000 6.75GB Monthly", code: "mtn-6.75gb-3000", price_naira: 3000 },
    Plan { display: "MTN N3,500 11GB  - 7 days", code: "mtn-11gb-3500", price_naira: 3500 },
    Plan { display: "MTN N30,000 150GB + 2GB daily - 5G Router Data (30 Days)", code: "mtn-150gb-30000", price_naira: 30000 },
    Plan { display: "MTN N35,000 165GB Monthly Data Plan (30 Days)", code: "mtn-165gb-35000", price_naira: 35000 },
    Plan { display: "MTN N37,500 200GB + 5GB Youtube/MSTeams/Zoom - 5G Broadband Data (30 Days)", code: "mtn-200gb-37500", price_naira: 37500 },
    Plan { display: "MTN N4,500 10GB + 10mins  - 30 days", code: "mtn-8gb-ex-3000", price_naira: 4500 },
    Plan { display: "MTN N500 1GB + 1.5mins - 1 day", code: "mtn-1gb-350", price_naira: 500 },
    Plan { display: "MTN N900 2.5GB - 2 days", code: "mtn-2-5gb-900", price_naira: 900 },
    Plan { display: "N800 1GB + 1GB YouTube Night + 100MB YouTube Music - Weekly", code: "mtn-1gb-600", price_naira: 800 },
];

pub const AIRTEL_PLANS: &[Plan] = &[
    Plan { display: "1,000 Naira - 4GB Plan + 2GB YouTube Night + 200MB YT/IG/TT(2 Days)", code: "airt-1000-2", price_naira: 1000 },
    Plan { display: "1.5GB Binge Plan + Youtube & Social Plan Data (2 Days) - 600 Naira", code: "airt-600", price_naira: 600 },
    Plan { display: "1.5GB Social Plan - 500 Naira", code: "airt-social-500-7", price_naira: 500 },
    Plan { display: "1.5GB Weekly Plan + Youtube & Social Plans (7 Days) - 1,000 Naira", code: "airt-1000-7", price_naira: 1000 },
    Plan { display: "100GB Monthly Plan + Youtube & Social Plan (30 Days) - 20,000 Naira", code: "airt-20000", price_naira: 20000 },
    Plan { display: "100GB Unlimited Uiltra 20 - Router Only (30 Days) - 20,000 Naira", code: "airt-mifi-20000-30", price_naira: 20000 },
    Plan { display: "10GB Monthly Plan + Youtube & Social Plan (30 Days) - 4,000 Naira", code: "airt-4000", price_naira: 4000 },
    Plan { display: "10GB Weekly Plan + Youtube & Social Platform (7 Days) - 3000 Naira", code: "airt-3000-7", price_naira: 3000 },
    Plan { display: "13GB MIFI 5 Data - MiFi Only (30 Days) - 5,000 Naira", code: "airt-mifi-5000-30", price_naira: 5000 },
    Plan { display: "13GB Monthly Plan + Youtube & Social Plan (30 Days) - 5,000 Naira", code: "airt-5000", price_naira: 5000 },
    Plan { display: "160GB Monthly Plan (30 Days) - 30,000 Naira", code: "airt-30000", price_naira: 30000 },
    Plan { display: "18GB Monthly Plan + Youtube & Social Plan (30 Days) - 6000 Naira", code: "airt-6000-30", price_naira: 6000 },
    Plan { display: "18GB Weekly Plan + Youtube & Social Platform (7 Days) - 5000 Naira", code: "airt-5000-7", price_naira: 5000 },
    Plan { display: "1GB Social Plan Plan (3 Days) - 300 Naira", code: "airt-social-300-3", price_naira: 300 },
    Plan { display: "1GB Weekly Plan (7 Days) - 800 Naira", code: "airt-800-7", price_naira: 800 },
    Plan { display: "200GB Monthly Plan (90 Days) - 50,000 Naira", code: "airt-50000", price_naira: 50000 },
    Plan { display: "200MB Social Plan (2 Days) - 100 Naira - 1Day", code: "airt-100", price_naira: 100 },
    Plan { display: "210GB Data (30 Days) - 40,000 Naira", code: "airt-40000", price_naira: 40000 },
    Plan { display: "230MB Daily Plan (2 Days) - 200 Naira - 200MB - 1Day", code: "airt-200", price_naira: 200 },
    Plan { display: "250MB Night Plan (12 - 5 AM) - 50 Naira  - 1Day", code: "airt-50", price_naira: 50 },
    Plan { display: "25GB Monthly Plan + Youtube & Social Plan (30 Days) - 8,000 Naira", code: "airt-8000", price_naira: 8000 },
    Plan { display: "2GB Binge Plan + Youtube & Social Plan Data (2 Days) - 750 Naira", code: "airt-750-2", price_naira: 750 },
    Plan { display: "2GB Monthly Plan + Youtube & Social Plan (30 Days) - 1,500 Naira", code: "airt-1500-30", price_naira: 1500 },
    Plan { display: "3.5GB Weekly Plan + Youtube & Social Platform (7 Days) - 1,500 Naira", code: "airt-1500-7", price_naira: 1500 },
    Plan { display: "300MB Daily Plan (1 Day) - 300 Naira", code: "airt-300-1", price_naira: 300 },
    Plan { display: "350GB Monthly Plan + Youtube & Social Plan (120 Days) - 60,000 Naira", code: "airt-60000", price_naira: 60000 },
    Plan { display: "35GB MIFI 10 Data - MiFi Only (30 Days) - 10,000 Naira", code: "airt-mifi-10000-30", price_naira: 10000 },
    Plan { display: "35GB Monthly Plan + Youtube & Social Plan (30 Days) - 10,000 Naira", code: "airt-10000", price_naira: 10000 },
    Plan { display: "3GB Monthly Plan + Youtube & Social Plan (30 Days)- 2,000 Naira", code: "airt-2000", price_naira: 2000 },
    Plan { display: "4GB Monthly Plan + Youtube & Social Plan (30 Days) - 2,500 Naira", code: "airt-2500", price_naira: 2500 },
    Plan { display: "500 Naira Binge Plan 1GB", code: "airt-binge-500-1", price_naira: 500 },
    Plan { display: "500MB Daily Plan (2 Days) - 350 Naira - 500MB - 2 Days", code: "airt-350-500", price_naira: 350 },
    Plan { display: "500MB Weekly Plan (7 Days) - 500 Naira", code: "airt-500", price_naira: 500 },
    Plan { display: "5GB Binge Plan + Youtube & Social Platforms Data (2 Day) - 1,500 Naira", code: "airt-1500-2", price_naira: 1500 },
    Plan { display: "60GB MIFI 15 Data - MiFi Only (30 Days) - 15,000 Naira", code: "airt-mifi-15000-30", price_naira: 15000 },
    Plan { display: "60GB Monthly Plan + Youtube & Social Plan (30 Days) - 15,000 Naira", code: "airt-15000", price_naira: 15000 },
    Plan { display: "680GB Data (365 Days) - 100,000 Naira", code: "airt-100000", price_naira: 100000 },
    Plan { display: "6GB Weekly Plan + Youtube & Social Platform (7 Days) - 2,500 Naira", code: "airt-2500-7", price_naira: 2500 },
    Plan { display: "75MB Daily Plan (1 Day) - 75 Naira", code: "airt-75-1", price_naira: 75 },
    Plan { display: "8GB Monthly Plan + Youtube & Social Plan (30 Days) - 3,000 Naira", code: "airt-3000", price_naira: 3000 },
    Plan { display: "Airtel Data - 100 Naira - 110MB - 1 Day", code: "airt-daily-100", price_naira: 100 },
    Plan { display: "Unlimited 20MBPS Data - Router Only (120 Days) - 150,000 Naira", code: "airt-mifi-150000-120", price_naira: 150000 },
    Plan { display: "Unlimited 20MBPS Data - Router Only (30 Days) - 30,000 Naira", code: "airt-mifi-30000-30", price_naira: 30000 },
    Plan { display: "Unlimited 60MBPS Data - Router Only (30 Days) - 50,000 Naira", code: "airt-mifi-50000-30", price_naira: 50000 },
    Plan { display: "Unlimited 60MBPS Data - Router Only (90 Days) - 135,000 Naira", code: "airt-mifi-135000-90", price_naira: 135000 },
    Plan { display: "Unlimited 60MBPS Data - Router Only (90 Days) - 80,000 Naira", code: "airt-mifi-80000-90", price_naira: 80000 },
];

pub const GLO_PLANS: &[Plan] = &[
    Plan { display: "1.1GB + 1.5GB Night - N1000 - 30 Days", code: "glo-monthly-1000", price_naira: 1000 },
    Plan { display: "1.1GB + 1GB Night - N500 - 7 Days - Camp-Boost", code: "glo-campus-booster-500", price_naira: 500 },
    Plan { display: "1.1GB 10 Days - Social Bundles N300", code: "glo-special-300-10days", price_naira: 300 },
    Plan { display: "1.1GB 14 Days - N750", code: "glo-750-14", price_naira: 750 },
    Plan { display: "1.55GB + 2GB Night - N600 - 2 Days - Special", code: "glo-600-special-2days", price_naira: 600 },
    Plan { display: "1.7GB + 2GB Night - N1000 - 7 Days", code: "glo-1000-7days", price_naira: 1000 },
    Plan { display: "1.8GB 15 Days - Social Bundles N500", code: "glo-special-500-15days", price_naira: 500 },
    Plan { display: "10.5GB + 2GB Night - N4000 - 30 Days", code: "glo-monthly-4000", price_naira: 4000 },
    Plan { display: "1000GB Yearly - Mega N150,000 Oneoff", code: "glo-yearly-mega", price_naira: 150000 },
    Plan { display: "105GB + 2GB - N20,000 - 30 Days", code: "glo-20000-30days", price_naira: 20000 },
    Plan { display: "10GB - 3,725 Naira - 14 days Night plan (Best Value)", code: "glo-dg-3460", price_naira: 3725 },
    Plan { display: "10GB - 4,950 Naira - 30 days (Best Value)", code: "glo-dg-4950", price_naira: 4950 },
    Plan { display: "120MB + 5MB Night - N100 - 1 Day", code: "glo-daily-100", price_naira: 100 },
    Plan { display: "135GB 30 Days - Mega N25000 Oneoff", code: "glo-25000-mega-30days", price_naira: 25000 },
    Plan { display: "135MB 3 Days - Social Bundles N50", code: "glo-social-50-3days", price_naira: 50 },
    Plan { display: "14.5GB + 2.5GB Night - N5000 - 30 Days", code: "glo-monthly-5000", price_naira: 5000 },
    Plan { display: "15GB (500MB per day) 30 Days - Always On N3500", code: "glo-always-on-3500", price_naira: 3500 },
    Plan { display: "165GB 30 Days - Mega N30000", code: "glo-mega-30000", price_naira: 30000 },
    Plan { display: "18.5GB + 2GB Night - N6000 - 30 Days", code: "glo-6000-30days", price_naira: 6000 },
    Plan { display: "1GB + 1GB Night - N500 - 2 Days Special", code: "glo-special-500", price_naira: 500 },
    Plan { display: "1GB - 330 Naira - 3 days (Best Value)", code: "glo-dg-295", price_naira: 330 },
    Plan { display: "1GB - 366 Naira - 14 days Night plan (Best Value)", code: "glo-dg-350", price_naira: 366 },
    Plan { display: "1GB - 366 Naira - 7 days (Best Value)", code: "glo-dg-345", price_naira: 366 },
    Plan { display: "1GB - 495 Naira - 30 days (Best Value)", code: "glo-dg-495", price_naira: 495 },
    Plan { display: "1GB 1 Day - N300 Oneoff", code: "glo-1000mb-300-oneoff", price_naira: 300 },
    Plan { display: "1GB 1 Day - Special N350", code: "glo-350-special-1day", price_naira: 350 },
    Plan { display: "1GB 1 Day - Youtube Special N250", code: "glo-youtube-250", price_naira: 250 },
    Plan { display: "2.2GB + 2GB Night - N1000 - 30 Days - Camp-Boost", code: "glo-campus-booster-1000", price_naira: 1000 },
    Plan { display: "2.2GB + 3GB - N1500 - 30 Days", code: "glo-monthly-1500", price_naira: 1500 },
    Plan { display: "2.5GB 2 Days - Weekend N500", code: "glo-weekend-500", price_naira: 500 },
    Plan { display: "200MB - 99 Naira - 14 days (Best Value)", code: "glo-dg-99", price_naira: 99 },
    Plan { display: "220GB 30 Days - Mega N40000 Oneoff", code: "glo-mega-40000", price_naira: 40000 },
    Plan { display: "22GB + 2GB Night - N5000 - 7 Days", code: "glo-5000-7days", price_naira: 5000 },
    Plan { display: "240MB + 5MB Night - N100 - 1 Day - Camp-Boost", code: "glo-campus-booster-100", price_naira: 100 },
    Plan { display: "250MB + 25MB Night - N200 - 2 Days", code: "glo-2days-200", price_naira: 200 },
    Plan { display: "26GB + 2GB - N8,000 - 30 Days", code: "glo-monthly-8000", price_naira: 8000 },
    Plan { display: "29GB + 3GB Night - N5000 - 30 Days - Camp-Boost", code: "glo-campus-booster-5000", price_naira: 5000 },
    Plan { display: "2GB - 990 Naira - 30 days (Best Value)", code: "glo-dg-990", price_naira: 990 },
    Plan { display: "3.1GB + 2GB - N1000 - 2 Days - Special", code: "glo-1000-special-2days", price_naira: 1000 },
    Plan { display: "3.25GB + 3GB Night - N2000 - 30 Days", code: "glo-monthly-2000", price_naira: 2000 },
    Plan { display: "300MB - GloMyG N100 1 Day", code: "glo-social-oneoff-100", price_naira: 100 },
    Plan { display: "30GB (1GB per day) 30 Days - Always On N5000", code: "glo-always-on-5000", price_naira: 5000 },
    Plan { display: "310GB 60 Days - Mega N50000", code: "glo-mega-50000", price_naira: 50000 },
    Plan { display: "335MB 7 Days - Social Bundles N100", code: "glo-special-100-7days", price_naira: 100 },
    Plan { display: "350MB Night - N60", code: "glo-night-60-1day", price_naira: 60 },
    Plan { display: "355GB 90 Days - Mega N60000", code: "glo-mega-60000", price_naira: 60000 },
    Plan { display: "38GB + 4GB Night - N10,000 - 30 Days", code: "glo-monthly-10000", price_naira: 10000 },
    Plan { display: "3GB - 1,005 Naira - 3 days (Best Value)", code: "glo-dg-890", price_naira: 1005 },
    Plan { display: "3GB - 1,110 Naira - 14 days Night plan (Best Value)", code: "glo-dg-1040-14", price_naira: 1110 },
    Plan { display: "3GB - 1,110 Naira - 7 days (Best Value)", code: "glo-dg-1040", price_naira: 1110 },
    Plan { display: "3GB - 1,485 Naira - 30 days (Best Value)", code: "glo-dg-1485", price_naira: 1485 },
    Plan { display: "3GB 2 Days - Youtube Special N600", code: "glo-youtube-600", price_naira: 600 },
    Plan { display: "3GB 5GB - 2,475 Naira - 30 days (Best Value)", code: "glo-dg-2475", price_naira: 2475 },
    Plan { display: "4.25GB + 3GB Night - N2500 - 30 Days", code: "glo-monthly-2500", price_naira: 2500 },
    Plan { display: "40MB + 5MB Night - N50 - 1 Day", code: "glo-daily-50", price_naira: 50 },
    Plan { display: "45GB (1.5 per day) 30 Days - Always On N7000", code: "glo-always-on-7000", price_naira: 7000 },
    Plan { display: "475GB 90 Days - Mega N75000 Oneoff", code: "glo-mega-75000", price_naira: 75000 },
    Plan { display: "4GB + 2GB Night - N1,500 - 7 Days - Special", code: "glo-special-1500", price_naira: 1500 },
    Plan { display: "500MB + 25MB Night - N200 - 2 Days - Camp-Boost", code: "glo-campus-booster-200", price_naira: 200 },
    Plan { display: "500MB - 250 Naira - 14 days (Best Value)", code: "glo-dg-250", price_naira: 250 },
    Plan { display: "500MB - 250 Naira - 30 days (Best Value)", code: "glo-dg-250-30", price_naira: 250 },
    Plan { display: "500MB 1 Day - N200 Oneoff", code: "glo-500mb-200-oneoff", price_naira: 200 },
    Plan { display: "5GB - 1,875 Naira - 14 days Night plan (Best Value)", code: "glo-dg-1730", price_naira: 1875 },
    Plan { display: "6.1GB (410MB per day) 15 Days - Always On N2000", code: "glo-always-on-2000", price_naira: 2000 },
    Plan { display: "6.5GB + 2.5GB - N2000 - 7 Days", code: "glo-2000-7days", price_naira: 2000 },
    Plan { display: "6.5GB + 3.5GB - N2,000 - 30 Days - Camp-Boost", code: "glo-campus-booster-2000", price_naira: 2000 },
    Plan { display: "62GB + 2GB - N15,000 - 30 Days", code: "glo-15000-30days", price_naira: 15000 },
    Plan { display: "750MB Night - N120", code: "glo-night-120-1day", price_naira: 120 },
    Plan { display: "8.5GB + 2GB Night - N3000 - 30 Days", code: "glo-monthly-3000", price_naira: 3000 },
    Plan { display: "875MB 1 Day - Weekend N200", code: "glo-sunday-200", price_naira: 200 },
    Plan { display: "Glo MyG N1000 3.5 GB 30 Days (Whatsapp, Instagram, Snapchat, Boomplay, Audiomac, GloTV, Tiktok)", code: "glo-social-oneoff-1000", price_naira: 1000 },
    Plan { display: "Glo MyG N300 1 GB 3 Days OneOff (Whatsapp, Instagram, Snapchat, Boomplay, Audiomac, GloTV, Tiktok)", code: "glo-social-oneoff-300", price_naira: 300 },
    Plan { display: "Glo MyG N500 1.5 GB 7 Days (Whatsapp, Instagram, Snapchat, Boomplay, Audiomac, GloTV, Tiktok)", code: "glo-social-oneoff-500", price_naira: 500 },
    Plan { display: "Glo TV Lite 2GB 7 Days", code: "glo-tv-900", price_naira: 900 },
    Plan { display: "Glo TV Max 6 GB 30 Days", code: "glo-tv-3200", price_naira: 3200 },
    Plan { display: "Glo TV VOD 2GB 7days Oneoff", code: "glo-tv-450", price_naira: 450 },
    Plan { display: "Glo TV VOD 500 MB 3days Oneoff", code: "glo-tv-150", price_naira: 150 },
    Plan { display: "Glo TV VOD 6GB 30days", code: "glo-tv-1400", price_naira: 1400 },
];

pub const NINEMOBILE_PLANS: &[Plan] = &[
    Plan { display: "9mobile 10 GB SME plan", code: "9mobile-sme-data-10gb", price_naira: 1400 },
    Plan { display: "9mobile 100 GB SME plan", code: "9mobile-sme-data-100gb", price_naira: 14000 },
    Plan { display: "9mobile 100mb SME plan", code: "9mobile-sme-data-100mb", price_naira: 14 },
    Plan { display: "9mobile 15 GB SME plan", code: "9mobile-sme-data-15gb", price_naira: 2100 },
    Plan { display: "9mobile 1GB SME plan", code: "9mobile-sme-data-1gb", price_naira: 140 },
    Plan { display: "9mobile 2 GB SME plan", code: "9mobile-sme-data-2gb", price_naira: 280 },
    Plan { display: "9mobile 20 GB SME plan", code: "9mobile-sme-data-20gb", price_naira: 2800 },
    Plan { display: "9mobile 200mb SME plan", code: "9mobile-sme-data-200mb", price_naira: 28 },
    Plan { display: "9mobile 25 GB SME plan", code: "9mobile-sme-data-25gb", price_naira: 3500 },
    Plan { display: "9mobile 2GB - 1,000 Naira - 30 Days", code: "eti-1000", price_naira: 1000 },
    Plan { display: "9mobile 3 GB SME plan", code: "9mobile-sme-data-3gb", price_naira: 420 },
    Plan { display: "9mobile 4 GB SME plan", code: "9mobile-sme-data-4gb", price_naira: 560 },
    Plan { display: "9mobile 5 GB SME plan", code: "9mobile-sme-data-5gb", price_naira: 700 },
    Plan { display: "9mobile 50 GB SME plan", code: "9mobile-sme-data-50gb", price_naira: 7000 },
    Plan { display: "9mobile 500mb SME plan", code: "9mobile-sme-data-500mb", price_naira: 70 },
    Plan { display: "9mobile 50mb SME plan", code: "9mobile-sme-data-50mb", price_naira: 4 },
    Plan { display: "T2 11.4GB - 5,000 Naira - 30 Days", code: "eti-5000", price_naira: 5000 },
    Plan { display: "T2 150MB  + 100MB Night Data - 150 Naira - 1 day", code: "eti-150", price_naira: 150 },
    Plan { display: "T2 2.3GB - 1,200 Naira - 30 Days", code: "eti-1200", price_naira: 1200 },
    Plan { display: "T2 4.5GB - 2000 Naira - 30 Days", code: "eti-2000", price_naira: 2000 },
    Plan { display: "T2 40MB - 50 Naira - 1 day", code: "eti-50", price_naira: 50 },
    Plan { display: "T2 5.2GB - 2,500 Naira - 30 days", code: "eti-2500", price_naira: 2500 },
    Plan { display: "T2 6.2G - 3,000 Naira - 30 days", code: "eti-3000", price_naira: 3000 },
    Plan { display: "T2 650MB - 500 Naira - 3 days", code: "eti-500", price_naira: 500 },
    Plan { display: "T2 8.4GB - 4,000 Naira - 30 days", code: "eti-4000", price_naira: 4000 },
    Plan { display: "T2 83MB - 100 Naira - 1 day", code: "eti-100", price_naira: 100 },
    Plan { display: "T2 N200 - 250MB Anytime Data Plan (7 Days)", code: "t2-250mb-200", price_naira: 200 },
];

pub const DSTV_PLANS: &[Plan] = &[
    Plan { display: "DStv  Compact + Showmax N21,250", code: "dstv-compact-showmax", price_naira: 21250 },
    Plan { display: "DStv  Compact N19,000", code: "dstv79", price_naira: 19000 },
    Plan { display: "DStv Asia + Showmax N19,400", code: "dstv-asia-showmax", price_naira: 19400 },
    Plan { display: "DStv Compact + Extra View N25,000", code: "dstv30", price_naira: 25000 },
    Plan { display: "DStv Compact + French Plus N43,500", code: "dstv47", price_naira: 43500 },
    Plan { display: "DStv Compact + French Touch + ExtraView N32,000", code: "com-frenchtouch-extra", price_naira: 32000 },
    Plan { display: "DStv Compact + French Touch N26,000", code: "com-frenchtouch", price_naira: 26000 },
    Plan { display: "DStv Compact Plus + Extra View N36,000", code: "dstv45", price_naira: 36000 },
    Plan { display: "DStv Compact Plus + French Plus N54,500", code: "dstv43", price_naira: 54500 },
    Plan { display: "DStv Compact Plus + French Touch N37,000", code: "complus-frenchtouch", price_naira: 37000 },
    Plan { display: "DStv Compact Plus + FrenchPlus + Extra View N60,500", code: "complus-french-extraview", price_naira: 60500 },
    Plan { display: "DStv Compact Plus + Showmax N32,250", code: "dstv-compact-plus-showmax", price_naira: 32250 },
    Plan { display: "DStv Compact Plus Movie Bundle Add-on E36 - N3,500", code: "dstv-compact-plus-movie", price_naira: 3500 },
    Plan { display: "DStv Compact Plus N30,000", code: "dstv7", price_naira: 30000 },
    Plan { display: "DStv Confam + ExtraView N17,000", code: "confam-extra", price_naira: 17000 },
    Plan { display: "DStv French 11 N10,800", code: "french11", price_naira: 10800 },
    Plan { display: "DStv French Plus Add-on N24,500", code: "frenchplus-addon", price_naira: 24500 },
    Plan { display: "DStv French Touch Add-on N7,000", code: "frenchtouch-addon", price_naira: 7000 },
    Plan { display: "DStv Great Wall Standalone Bouquet + Showmax N8,300", code: "dstv-greatwall-showmax", price_naira: 8300 },
    Plan { display: "DStv Great Wall Standalone Bouquet N3,800", code: "dstv-greatwall", price_naira: 3800 },
    Plan { display: "DStv India Add-on N14,900", code: "dstv-indian-add-on", price_naira: 14900 },
    Plan { display: "DStv Indian N14,900", code: "dstv-indian", price_naira: 14900 },
    Plan { display: "DStv Movie Bundle Add-on N3500", code: "dstv-movie-bundle-add-on", price_naira: 3500 },
    Plan { display: "DStv Padi + ExtraView N10,400", code: "padi-extra", price_naira: 10400 },
    Plan { display: "DStv Padi + Showmax N8,900", code: "dstv-padi-showmax", price_naira: 8900 },
    Plan { display: "DStv Padi N4,400", code: "dstv-padi", price_naira: 4400 },
    Plan { display: "DStv Premium + Extra View N50,500", code: "dstv33", price_naira: 50500 },
    Plan { display: "DStv Premium + French + Extra View N75,000", code: "dstv62", price_naira: 75000 },
    Plan { display: "DStv Premium + French + Showmax N69,000", code: "dstv-premium-french-showmax", price_naira: 69000 },
    Plan { display: "DStv Premium + Showmax N44,500", code: "dstv-premium-showmax", price_naira: 44500 },
    Plan { display: "DStv Premium N44,500", code: "dstv3", price_naira: 44500 },
    Plan { display: "DStv Premium W/Afr + Showmax N50,500", code: "dstv-premium-wafr-showmax", price_naira: 50500 },
    Plan { display: "DStv Premium-Asia N50,500", code: "dstv10", price_naira: 50500 },
    Plan { display: "DStv Premium-French N69,000", code: "dstv9", price_naira: 69000 },
    Plan { display: "DStv Showmax Premier League Add-on N3,600", code: "dstv-showmax-premier-league", price_naira: 3600 },
    Plan { display: "DStv Yanga + ExtraView N12,000", code: "yanga-extra", price_naira: 12000 },
    Plan { display: "DStv Yanga + Showmax N8,250", code: "dstv-yanga-showmax", price_naira: 8250 },
    Plan { display: "DStv Yanga N6,000", code: "dstv-yanga", price_naira: 6000 },
    Plan { display: "Dstv Confam + Showmax N13,250", code: "dstv-confam-showmax", price_naira: 13250 },
    Plan { display: "Dstv Confam N11,000", code: "dstv-confam", price_naira: 11000 },
];

pub const GOTV_PLANS: &[Plan] = &[
    Plan { display: "GOtv Jinja N3,900", code: "gotv-jinja", price_naira: 3900 },
    Plan { display: "GOtv Jolli N5,800", code: "gotv-jolli", price_naira: 5800 },
    Plan { display: "GOtv Max N8,500", code: "gotv-max", price_naira: 8500 },
    Plan { display: "GOtv Smallie - monthly N1900", code: "gotv-smallie", price_naira: 1900 },
    Plan { display: "GOtv Smallie - quarterly N5,100", code: "gotv-smallie-3months", price_naira: 5100 },
    Plan { display: "GOtv Smallie - yearly N15,000", code: "gotv-smallie-1year", price_naira: 15000 },
    Plan { display: "GOtv Supa - monthly N11,400", code: "gotv-supa", price_naira: 11400 },
    Plan { display: "GOtv Supa Plus - monthly N16,800", code: "gotv-supa-plus", price_naira: 16800 },
];

pub const SHOWMAX_PLANS: &[Plan] = &[
    Plan { display: "Full - N8,400 - 3 Months", code: "full_3", price_naira: 8400 },
    Plan { display: "Mobile Only - N3,800 - 3 Months", code: "mobile_only_3", price_naira: 3800 },
    Plan { display: "Sports Mobile Only - N12,000 - 3 Months", code: "sports_mobile_only_3", price_naira: 12000 },
    Plan { display: "Sports Only - N3,200", code: "sports-only-1", price_naira: 3200 },
    Plan { display: "Sports Only 3 months - N9,600", code: "sports-only-3", price_naira: 9600 },
    Plan { display: "Full Sports Mobile Only - 3 months - N16,200", code: "full-sports-mobile-only-3", price_naira: 16200 },
    Plan { display: "Mobile Only - N6,700 - 6 Months", code: "mobile-only-6", price_naira: 6700 },
    Plan { display: "Full - 6 months - 14,700", code: "full-only-6", price_naira: 14700 },
    Plan { display: "Full Sports Mobile Only - 6 months - N32,400", code: "full-sports-mobile-only-6", price_naira: 32400 },
    Plan { display: "Sports Mobile Only - 6 months - N24,000", code: "sports-mobile-only-6", price_naira: 24000 },
    Plan { display: "Sports Only - 6 months - N18,200", code: "sports-only-6", price_naira: 18200 },
];

pub const STARTIMES_PLANS: &[Plan] = &[
    Plan { display: "Basic (Antenna) - 1400 Naira - 1 Week", code: "basic-weekly", price_naira: 1400 },
    Plan { display: "Basic (Antenna) - 4,000 Naira - 1 Month", code: "basic", price_naira: 4000 },
    Plan { display: "Basic (Dish) - 1,700 Naira - 1 Week", code: "smart-weekly", price_naira: 1700 },
    Plan { display: "Basic (Dish) - 5,100 Naira - 1 Month", code: "smart", price_naira: 5100 },
    Plan { display: "Chinese (Dish) - 21,000 Naira - 1 month", code: "uni-1", price_naira: 21000 },
    Plan { display: "Classic (Antenna) - 2000 Naira - 1 Week", code: "classic-weekly", price_naira: 2000 },
    Plan { display: "Classic (Antenna) - 6000 Naira - 1 Month", code: "classic", price_naira: 6000 },
    Plan { display: "Classic (Dish) - 2300 Naira - 1 Week", code: "special-weekly", price_naira: 2300 },
    Plan { display: "Classic (Dish) - 2500 Naira - 1 Week", code: "classic-weekly-dish", price_naira: 2500 },
    Plan { display: "Classic (Dish) - 7400 Naira - 1 Month", code: "special-monthly", price_naira: 7400 },
    Plan { display: "Global (Dish) - 21000 Naira - 1 Month", code: "global-monthly-dish", price_naira: 21000 },
    Plan { display: "Global (Dish) - 7000 Naira - 1Week", code: "global-weekly-dish", price_naira: 7000 },
    Plan { display: "Nova (Antenna) - 2,100 Naira - 1 Month", code: "uni-2", price_naira: 2100 },
    Plan { display: "Nova (Antenna) - 700 Naira - 1 Week", code: "nova-weekly", price_naira: 700 },
    Plan { display: "Nova (Dish) - 2100 Naira - 1 Month", code: "nova", price_naira: 2100 },
    Plan { display: "Nova (Dish) - 700 Naira - 1 Week", code: "nova-dish-weekly", price_naira: 700 },
    Plan { display: "Startimes SHS - 12,000 Naira - Monthly", code: "shs-monthly-12000", price_naira: 12000 },
    Plan { display: "Startimes SHS - 19,800 Naira - Monthly", code: "shs-monthly-19800", price_naira: 19800 },
    Plan { display: "Startimes SHS - 2,800 Naira - Weekly", code: "shs-weekly-2800", price_naira: 2800 },
    Plan { display: "Startimes SHS - 21,000 Naira - Monthly", code: "shs-monthly-21000", price_naira: 21000 },
    Plan { display: "Startimes SHS - 39,000 Naira - Monthly", code: "shs-monthly-39000", price_naira: 39000 },
    Plan { display: "Startimes SHS - 4,620 Naira - Weekly", code: "shs-weekly-4620", price_naira: 4620 },
    Plan { display: "Startimes SHS - 4,900 Naira - Weekly", code: "shs-weekly-4900", price_naira: 4900 },
    Plan { display: "Startimes SHS - 9,100 Naira - Weekly", code: "shs-weekly-9100", price_naira: 9100 },
    Plan { display: "Super (Antenna) - 3,200 Naira - 1 Week", code: "super-antenna-weekly", price_naira: 3200 },
    Plan { display: "Super (Antenna) - 9,500 Naira - 1 Month", code: "super-antenna-monthly", price_naira: 9500 },
    Plan { display: "Super (Dish) - 3,300 Naira - 1 Week", code: "super-weekly", price_naira: 3300 },
    Plan { display: "Super (Dish) - 9,800 Naira - 1 Month", code: "super", price_naira: 9800 },
];

pub fn find_plan<'a>(plans: &'a [Plan], display: &str) -> Option<&'a Plan> {
    plans.iter().find(|p| p.display == display)
}

#[cfg(test)]
mod tests {
    #[test]
    fn mtn_plans_count() {
        assert_eq!(super::MTN_PLANS.len(), 50);
    }
    #[test]
    fn airtel_plans_count() {
        assert_eq!(super::AIRTEL_PLANS.len(), 46);
    }
    #[test]
    fn glo_plans_count() {
        assert_eq!(super::GLO_PLANS.len(), 78);
    }
    #[test]
    fn ninemobile_plans_count() {
        assert_eq!(super::NINEMOBILE_PLANS.len(), 27);
    }
    #[test]
    fn dstv_plans_count() {
        assert_eq!(super::DSTV_PLANS.len(), 40);
    }
    #[test]
    fn gotv_plans_count() {
        assert_eq!(super::GOTV_PLANS.len(), 8);
    }
    #[test]
    fn showmax_plans_count() {
        assert_eq!(super::SHOWMAX_PLANS.len(), 11);
    }
    #[test]
    fn startimes_plans_count() {
        assert_eq!(super::STARTIMES_PLANS.len(), 28);
    }
    #[test]
    fn lookup() {
        let p = super::find_plan(super::MTN_PLANS, "1.5GB Weekly Plan (7 Days) - N1,000").unwrap();
        assert_eq!((p.code, p.price_naira), ("mtn-1500mb-1000", 1000));
        assert!(super::find_plan(super::MTN_PLANS, "nope").is_none());
    }
}