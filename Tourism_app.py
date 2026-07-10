"""
travelwise_ai.py
=================================================
TravelWise AI - Smart Tourism Decision Assistant (India Edition)
=================================================
A single-file Streamlit application covering every Indian state & Union
Territory with curated destinations, live weather (Open-Meteo), live
geocoding (Open-Meteo Geocoding), live place summaries (Wikipedia REST API),
an AI-style crowd estimation engine and an overall "Travel Score".

Run locally:
    pip install streamlit requests pandas plotly
    streamlit run travelwise_ai.py

Deploy on streamlit.io:
    - Push this file + a requirements.txt containing:
        streamlit
        requests
        pandas
        plotly
    - No API keys needed. Fully free & open APIs.
"""

import difflib
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

# =========================================================================
# 1. PAGE CONFIG (must be first Streamlit call)
# =========================================================================
st.set_page_config(
    page_title="TravelWise AI | Discover India",
    page_icon="🇮🇳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================================================================
# 2. CUSTOM CSS / FANCY UI
# =========================================================================
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"]  {
    font-family: 'Inter', 'Poppins', sans-serif;
}

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.stApp {
    background: radial-gradient(circle at 10% 0%, #10131f 0%, #05070d 55%, #050608 100%);
    color: #eef1f8;
}

/* ---------- HERO BANNER ---------- */
.hero-banner {
    background: linear-gradient(120deg, #FF9933 0%, #ffffff 50%, #138808 100%);
    border-radius: 24px;
    padding: 2.4rem 2.2rem;
    margin-bottom: 1.6rem;
    box-shadow: 0 20px 60px rgba(255,153,51,0.18);
    position: relative;
    overflow: hidden;
}
.hero-inner {
    background: rgba(5, 8, 14, 0.86);
    border-radius: 18px;
    padding: 2rem 2rem;
}
.hero-title {
    font-family:'Poppins', sans-serif;
    font-weight: 800;
    font-size: 2.6rem;
    background: linear-gradient(90deg,#FF9933,#ffffff 45%,#138808);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.2rem;
}
.hero-sub {
    color: #b9c2d6;
    font-size: 1.05rem;
    font-weight: 400;
    margin-bottom: 0;
}

/* ---------- CARDS ---------- */
.tw-card {
    background: rgba(255,255,255,0.045);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 18px;
    padding: 1.3rem 1.4rem;
    backdrop-filter: blur(6px);
    transition: all 0.25s ease;
    margin-bottom: 1rem;
}
.tw-card:hover {
    border-color: rgba(255,153,51,0.5);
    transform: translateY(-3px);
    box-shadow: 0 12px 30px rgba(0,0,0,0.35);
}
.tw-card h4 {
    margin-top:0;
    font-family:'Poppins',sans-serif;
    color:#ffffff;
}

.place-hero {
    background: linear-gradient(135deg, rgba(255,153,51,0.15), rgba(19,136,8,0.12));
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 22px;
    padding: 1.8rem 2rem;
    margin-bottom: 1.4rem;
}
.place-name {
    font-family:'Poppins',sans-serif;
    font-weight: 800;
    font-size: 2.1rem;
    color: #ffffff;
    margin-bottom: 0.1rem;
}
.place-loc {
    color: #9fb0c9;
    font-size: 1rem;
    margin-bottom: 0.8rem;
}

/* ---------- BADGES ---------- */
.badge {
    display:inline-block;
    padding: 0.28rem 0.85rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-right: 0.4rem;
    margin-bottom: 0.4rem;
    letter-spacing: 0.2px;
}
.badge-cat { background: rgba(255,153,51,0.18); color:#ffb066; border:1px solid rgba(255,153,51,0.4);}
.badge-tier { background: rgba(56,189,248,0.15); color:#7dd3fc; border:1px solid rgba(56,189,248,0.35);}
.badge-tag { background: rgba(255,255,255,0.08); color:#d8dee9; border:1px solid rgba(255,255,255,0.12);}

/* ---------- METRIC MINI CARDS ---------- */
.metric-box {
    background: rgba(255,255,255,0.045);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 0.9rem 1rem;
    text-align: center;
}
.metric-box .val { font-size: 1.5rem; font-weight: 700; color:#fff; font-family:'Poppins',sans-serif;}
.metric-box .lbl { font-size: 0.78rem; color:#9fb0c9; text-transform: uppercase; letter-spacing: 0.6px;}

/* ---------- SECTION TITLES ---------- */
.section-title {
    font-family:'Poppins',sans-serif;
    font-weight:700;
    font-size:1.35rem;
    color:#fff;
    margin: 1.4rem 0 0.6rem 0;
    border-left: 4px solid #FF9933;
    padding-left: 0.6rem;
}

/* ---------- BUTTONS ---------- */
div.stButton > button {
    background: linear-gradient(90deg,#FF9933,#e07b00);
    color: white;
    border: none;
    border-radius: 10px;
    font-weight: 600;
    padding: 0.5rem 1.1rem;
    transition: 0.2s;
}
div.stButton > button:hover {
    background: linear-gradient(90deg,#138808,#0c5c05);
    color: white;
    transform: translateY(-1px);
}

/* chip buttons */
.chip-row div.stButton > button {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.15);
    color: #eef1f8;
    border-radius: 999px;
    padding: 0.35rem 0.9rem;
    font-size: 0.85rem;
    font-weight: 500;
}
.chip-row div.stButton > button:hover {
    background: rgba(255,153,51,0.25);
    border-color: #FF9933;
}

/* sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0b0e17 0%, #05070d 100%);
    border-right: 1px solid rgba(255,255,255,0.06);
}

hr { border-color: rgba(255,255,255,0.08); }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# =========================================================================
# 3. INDIA DESTINATION DATABASE (curated)
# =========================================================================
STATE_REGION = {
    "Himachal Pradesh": "North", "Punjab": "North", "Haryana": "North", "Delhi": "North",
    "Jammu and Kashmir": "North", "Ladakh": "North", "Uttarakhand": "North", "Chandigarh": "North",
    "Uttar Pradesh": "North",
    "Andhra Pradesh": "South", "Karnataka": "South", "Kerala": "South", "Tamil Nadu": "South",
    "Telangana": "South", "Puducherry": "South", "Lakshadweep": "South",
    "West Bengal": "East", "Odisha": "East", "Bihar": "East", "Jharkhand": "East",
    "Maharashtra": "West", "Gujarat": "West", "Goa": "West", "Rajasthan": "West",
    "Dadra and Nagar Haveli and Daman and Diu": "West",
    "Madhya Pradesh": "Central", "Chhattisgarh": "Central",
    "Assam": "Northeast", "Arunachal Pradesh": "Northeast", "Manipur": "Northeast",
    "Meghalaya": "Northeast", "Mizoram": "Northeast", "Nagaland": "Northeast",
    "Sikkim": "Northeast", "Tripura": "Northeast",
    "Andaman and Nicobar Islands": "Islands",
}

CATEGORY_ICON = {
    "Hill Station": "⛰️", "Beach": "🏖️", "Historical": "🏛️", "Spiritual": "🛕",
    "Wildlife": "🐅", "Nature": "🌿", "City": "🏙️", "Desert": "🏜️",
    "Backwaters": "🚤", "Adventure": "🧗", "Heritage": "🏰", "Lake": "🏞️",
    "Village": "🏘️", "Island": "🏝️",
}

PLACES = [
    # Andhra Pradesh
    {"name": "Araku Valley", "state": "Andhra Pradesh", "lat": 18.3273, "lon": 82.8770,
     "category": "Hill Station", "tier": "Popular", "best_months": [10, 11, 12, 1, 2],
     "desc": "A lush hill station in the Eastern Ghats famed for coffee plantations, tribal culture and the Borra Caves.",
     "tags": ["Coffee Plantations", "Borra Caves", "Tribal Museum"]},
    {"name": "Tirupati", "state": "Andhra Pradesh", "lat": 13.6288, "lon": 79.4192,
     "category": "Spiritual", "tier": "Very Popular", "best_months": [9, 10, 11, 12, 1, 2],
     "desc": "Home to the Sri Venkateswara Temple, one of the world's most visited religious sites.",
     "tags": ["Venkateswara Temple", "Tirumala Hills"]},
    {"name": "Visakhapatnam", "state": "Andhra Pradesh", "lat": 17.6868, "lon": 83.2185,
     "category": "Beach", "tier": "Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "A vibrant port city with golden beaches, a submarine museum and coastal charm.",
     "tags": ["RK Beach", "Kailasagiri", "Submarine Museum"]},

    # Arunachal Pradesh
    {"name": "Tawang", "state": "Arunachal Pradesh", "lat": 27.5860, "lon": 91.8594,
     "category": "Hill Station", "tier": "Moderate", "best_months": [3, 4, 5, 10, 11],
     "desc": "A remote Himalayan town famed for its centuries-old Buddhist monastery and dramatic mountain passes.",
     "tags": ["Tawang Monastery", "Sela Pass", "Madhuri Lake"]},
    {"name": "Ziro Valley", "state": "Arunachal Pradesh", "lat": 27.5586, "lon": 93.8323,
     "category": "Nature", "tier": "Offbeat", "best_months": [3, 4, 9, 10],
     "desc": "A UNESCO-listed valley home to the Apatani tribe, paddy-cum-fish farms and rolling pine hills.",
     "tags": ["Apatani Villages", "Ziro Music Festival"]},
    {"name": "Bomdila", "state": "Arunachal Pradesh", "lat": 27.2645, "lon": 92.4159,
     "category": "Hill Station", "tier": "Offbeat", "best_months": [3, 4, 5, 10, 11],
     "desc": "A quiet hill town with monasteries and sweeping views of the Himalayas.",
     "tags": ["Bomdila Monastery", "Apple Orchards"]},

    # Assam
    {"name": "Kaziranga National Park", "state": "Assam", "lat": 26.5775, "lon": 93.1714,
     "category": "Wildlife", "tier": "Popular", "best_months": [11, 12, 1, 2, 3, 4],
     "desc": "A UNESCO World Heritage site and stronghold of the great one-horned rhinoceros.",
     "tags": ["One-Horned Rhino", "Jeep Safari", "Elephant Safari"]},
    {"name": "Guwahati", "state": "Assam", "lat": 26.1445, "lon": 91.7362,
     "category": "City", "tier": "Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "The gateway to the Northeast, home to the sacred Kamakhya Temple on the Brahmaputra.",
     "tags": ["Kamakhya Temple", "Brahmaputra Cruise"]},
    {"name": "Majuli Island", "state": "Assam", "lat": 26.9500, "lon": 94.1667,
     "category": "Village", "tier": "Offbeat", "best_months": [10, 11, 12, 1, 2],
     "desc": "The world's largest river island, a hub of neo-Vaishnavite culture and satras.",
     "tags": ["River Island", "Satras", "Mask Making"]},

    # Bihar
    {"name": "Bodh Gaya", "state": "Bihar", "lat": 24.6959, "lon": 84.9911,
     "category": "Spiritual", "tier": "Very Popular", "best_months": [10, 11, 12, 1, 2],
     "desc": "The sacred site where Buddha attained enlightenment under the Bodhi Tree.",
     "tags": ["Mahabodhi Temple", "Bodhi Tree"]},
    {"name": "Patna", "state": "Bihar", "lat": 25.5941, "lon": 85.1376,
     "category": "Historical", "tier": "Popular", "best_months": [10, 11, 12, 1, 2],
     "desc": "An ancient city on the Ganges with a rich Mauryan and colonial heritage.",
     "tags": ["Golghar", "Patna Museum"]},
    {"name": "Nalanda", "state": "Bihar", "lat": 25.1358, "lon": 85.4436,
     "category": "Historical", "tier": "Moderate", "best_months": [10, 11, 12, 1, 2],
     "desc": "Ruins of one of the world's oldest residential universities, dating back to the 5th century.",
     "tags": ["Nalanda University Ruins", "Archaeological Museum"]},

    # Chhattisgarh
    {"name": "Chitrakote Falls", "state": "Chhattisgarh", "lat": 19.1889, "lon": 81.7386,
     "category": "Nature", "tier": "Offbeat", "best_months": [10, 11, 12, 1, 2],
     "desc": "Often called the 'Niagara of India', a horseshoe-shaped waterfall on the Indravati River.",
     "tags": ["Waterfall", "Indravati River"]},
    {"name": "Bastar", "state": "Chhattisgarh", "lat": 19.0748, "lon": 82.0230,
     "category": "Village", "tier": "Offbeat", "best_months": [10, 11, 12, 1, 2],
     "desc": "A tribal heartland known for its Dussehra festival, handicrafts and forests.",
     "tags": ["Tribal Culture", "Bastar Dussehra"]},
    {"name": "Raipur", "state": "Chhattisgarh", "lat": 21.2514, "lon": 81.6296,
     "category": "City", "tier": "Moderate", "best_months": [10, 11, 12, 1, 2],
     "desc": "The bustling capital of Chhattisgarh with temples and rapid modern growth.",
     "tags": ["Mahant Ghasidas Museum"]},

    # Goa
    {"name": "Baga Beach", "state": "Goa", "lat": 15.5553, "lon": 73.7517,
     "category": "Beach", "tier": "Very Popular", "best_months": [11, 12, 1, 2, 3],
     "desc": "Goa's liveliest beach strip with water sports, shacks and buzzing nightlife.",
     "tags": ["Nightlife", "Water Sports", "Beach Shacks"]},
    {"name": "Old Goa", "state": "Goa", "lat": 15.5009, "lon": 73.9116,
     "category": "Heritage", "tier": "Popular", "best_months": [11, 12, 1, 2, 3],
     "desc": "A UNESCO World Heritage precinct of grand Portuguese-era churches and basilicas.",
     "tags": ["Basilica of Bom Jesus", "Se Cathedral"]},
    {"name": "Dudhsagar Falls", "state": "Goa", "lat": 15.3144, "lon": 74.3144,
     "category": "Nature", "tier": "Moderate", "best_months": [7, 8, 9, 10, 11],
     "desc": "A spectacular four-tiered waterfall cascading through the Western Ghats.",
     "tags": ["Waterfall", "Jeep Safari"]},

    # Gujarat
    {"name": "Rann of Kutch", "state": "Gujarat", "lat": 23.7337, "lon": 69.8597,
     "category": "Desert", "tier": "Very Popular", "best_months": [11, 12, 1, 2],
     "desc": "A surreal white salt desert that hosts the vibrant Rann Utsav festival.",
     "tags": ["White Desert", "Rann Utsav", "Full Moon Nights"]},
    {"name": "Gir National Park", "state": "Gujarat", "lat": 21.1290, "lon": 70.7935,
     "category": "Wildlife", "tier": "Popular", "best_months": [12, 1, 2, 3],
     "desc": "The only place on Earth where you can spot wild Asiatic lions.",
     "tags": ["Asiatic Lion", "Jungle Safari"]},
    {"name": "Somnath", "state": "Gujarat", "lat": 20.8880, "lon": 70.4012,
     "category": "Spiritual", "tier": "Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "Home to the first of the twelve Jyotirlinga shrines of Lord Shiva, by the Arabian Sea.",
     "tags": ["Somnath Temple", "Sea View"]},

    # Haryana
    {"name": "Kurukshetra", "state": "Haryana", "lat": 29.9695, "lon": 76.8783,
     "category": "Spiritual", "tier": "Moderate", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "The legendary battlefield of the Mahabharata and site of the Bhagavad Gita's discourse.",
     "tags": ["Brahma Sarovar", "Jyotisar"]},
    {"name": "Surajkund", "state": "Haryana", "lat": 28.4646, "lon": 77.2789,
     "category": "Heritage", "tier": "Moderate", "best_months": [10, 11, 12, 1, 2],
     "desc": "An ancient reservoir famed today for its International Crafts Mela.",
     "tags": ["Crafts Mela", "Ancient Reservoir"]},
    {"name": "Morni Hills", "state": "Haryana", "lat": 30.6270, "lon": 77.0940,
     "category": "Hill Station", "tier": "Offbeat", "best_months": [3, 4, 9, 10, 11],
     "desc": "Haryana's only hill station, offering lakes, forests and quiet trails.",
     "tags": ["Tikkar Tal", "Trekking"]},

    # Himachal Pradesh
    {"name": "Manali", "state": "Himachal Pradesh", "lat": 32.2432, "lon": 77.1892,
     "category": "Hill Station", "tier": "Very Popular", "best_months": [3, 4, 5, 6, 9, 10, 12, 1],
     "desc": "A snow-capped paradise in the Kullu Valley, beloved for adventure sports and honeymoons.",
     "tags": ["Solang Valley", "Rohtang Pass", "Adventure Sports"]},
    {"name": "Shimla", "state": "Himachal Pradesh", "lat": 31.1048, "lon": 77.1734,
     "category": "Hill Station", "tier": "Very Popular", "best_months": [3, 4, 5, 6, 9, 10, 12],
     "desc": "The colonial-era 'Queen of Hills', India's most iconic summer capital.",
     "tags": ["The Ridge", "Mall Road", "Toy Train"]},
    {"name": "Spiti Valley", "state": "Himachal Pradesh", "lat": 32.2246, "lon": 78.0724,
     "category": "Adventure", "tier": "Moderate", "best_months": [5, 6, 7, 8, 9],
     "desc": "A high-altitude cold desert of monasteries, moonscapes and starlit skies.",
     "tags": ["Key Monastery", "Chandratal Lake"]},

    # Jharkhand
    {"name": "Netarhat", "state": "Jharkhand", "lat": 23.4700, "lon": 84.2660,
     "category": "Hill Station", "tier": "Offbeat", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "Known as the 'Queen of Chotanagpur', famed for stunning sunrises and sunsets.",
     "tags": ["Sunrise Point", "Magnolia Point"]},
    {"name": "Betla National Park", "state": "Jharkhand", "lat": 23.8859, "lon": 84.1911,
     "category": "Wildlife", "tier": "Offbeat", "best_months": [11, 12, 1, 2, 3],
     "desc": "One of India's earliest Project Tiger reserves, rich in Sal forests and wildlife.",
     "tags": ["Tiger Reserve", "Palamau Fort"]},
    {"name": "Deoghar", "state": "Jharkhand", "lat": 24.4823, "lon": 86.6961,
     "category": "Spiritual", "tier": "Popular", "best_months": [10, 11, 12, 1, 2, 7, 8],
     "desc": "Home to the revered Baidyanath Jyotirlinga temple complex.",
     "tags": ["Baidyanath Temple", "Shravani Mela"]},

    # Karnataka
    {"name": "Coorg", "state": "Karnataka", "lat": 12.4244, "lon": 75.7382,
     "category": "Hill Station", "tier": "Very Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "The 'Scotland of India' - misty coffee estates, waterfalls and Kodava culture.",
     "tags": ["Coffee Estates", "Abbey Falls", "Raja's Seat"]},
    {"name": "Hampi", "state": "Karnataka", "lat": 15.3350, "lon": 76.4600,
     "category": "Historical", "tier": "Very Popular", "best_months": [10, 11, 12, 1, 2],
     "desc": "A UNESCO World Heritage site of surreal boulder landscapes and Vijayanagara ruins.",
     "tags": ["Virupaksha Temple", "Stone Chariot"]},
    {"name": "Mysuru", "state": "Karnataka", "lat": 12.2958, "lon": 76.6394,
     "category": "Heritage", "tier": "Popular", "best_months": [10, 11, 12, 1, 2],
     "desc": "The royal City of Palaces, famous for Dasara celebrations and grand architecture.",
     "tags": ["Mysore Palace", "Dasara Festival"]},

    # Kerala
    {"name": "Munnar", "state": "Kerala", "lat": 10.0889, "lon": 77.0595,
     "category": "Hill Station", "tier": "Very Popular", "best_months": [9, 10, 11, 12, 1, 2],
     "desc": "Rolling tea gardens, misty peaks and cool climate in the Western Ghats.",
     "tags": ["Tea Gardens", "Eravikulam National Park"]},
    {"name": "Alleppey", "state": "Kerala", "lat": 9.4981, "lon": 76.3388,
     "category": "Backwaters", "tier": "Very Popular", "best_months": [9, 10, 11, 12, 1, 2],
     "desc": "The 'Venice of the East', famed for houseboat cruises through tranquil backwaters.",
     "tags": ["Houseboats", "Backwaters", "Snake Boat Race"]},
    {"name": "Wayanad", "state": "Kerala", "lat": 11.6854, "lon": 76.1320,
     "category": "Nature", "tier": "Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "Dense forests, spice plantations and ancient caves in Kerala's green highlands.",
     "tags": ["Edakkal Caves", "Chembra Peak"]},

    # Madhya Pradesh
    {"name": "Khajuraho", "state": "Madhya Pradesh", "lat": 24.8318, "lon": 79.9199,
     "category": "Historical", "tier": "Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "A UNESCO World Heritage site famed for intricately carved medieval temples.",
     "tags": ["Temple Carvings", "Light & Sound Show"]},
    {"name": "Bandhavgarh National Park", "state": "Madhya Pradesh", "lat": 23.6, "lon": 80.9,
     "category": "Wildlife", "tier": "Popular", "best_months": [11, 12, 1, 2, 3, 4],
     "desc": "One of India's best parks for spotting wild tigers amid ancient ruins.",
     "tags": ["Tiger Safari", "Bandhavgarh Fort"]},
    {"name": "Pachmarhi", "state": "Madhya Pradesh", "lat": 22.4670, "lon": 78.4336,
     "category": "Hill Station", "tier": "Moderate", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "The 'Satpura Queen' - a hill station of waterfalls, caves and biosphere forests.",
     "tags": ["Bee Falls", "Pandav Caves"]},

    # Maharashtra
    {"name": "Mumbai", "state": "Maharashtra", "lat": 19.0760, "lon": 72.8777,
     "category": "City", "tier": "Very Popular", "best_months": [10, 11, 12, 1, 2],
     "desc": "India's dazzling financial capital, a blend of colonial heritage and Bollywood glamour.",
     "tags": ["Gateway of India", "Marine Drive", "Bollywood"]},
    {"name": "Lonavala", "state": "Maharashtra", "lat": 18.7546, "lon": 73.4062,
     "category": "Hill Station", "tier": "Popular", "best_months": [6, 7, 8, 9, 10, 11],
     "desc": "A lush monsoon getaway near Mumbai and Pune with waterfalls and forts.",
     "tags": ["Tiger's Leap", "Bhushi Dam"]},
    {"name": "Ajanta Ellora (Aurangabad)", "state": "Maharashtra", "lat": 19.8762, "lon": 75.3433,
     "category": "Historical", "tier": "Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "Gateway to the awe-inspiring rock-cut Ajanta & Ellora cave temples.",
     "tags": ["Ajanta Caves", "Ellora Caves", "Bibi Ka Maqbara"]},

    # Manipur
    {"name": "Loktak Lake", "state": "Manipur", "lat": 24.5500, "lon": 93.7800,
     "category": "Lake", "tier": "Offbeat", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "The largest freshwater lake in Northeast India, famous for floating phumdis.",
     "tags": ["Floating Islands", "Keibul Lamjao Park"]},
    {"name": "Imphal", "state": "Manipur", "lat": 24.8170, "lon": 93.9368,
     "category": "Historical", "tier": "Moderate", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "The scenic capital of Manipur, rich in WWII history and unique markets.",
     "tags": ["Ima Keithel Market", "Kangla Fort"]},

    # Meghalaya
    {"name": "Cherrapunji", "state": "Meghalaya", "lat": 25.2702, "lon": 91.7323,
     "category": "Nature", "tier": "Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "One of the wettest places on Earth, famous for living root bridges and waterfalls.",
     "tags": ["Living Root Bridges", "Nohkalikai Falls"]},
    {"name": "Shillong", "state": "Meghalaya", "lat": 25.5788, "lon": 91.8933,
     "category": "Hill Station", "tier": "Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "The 'Scotland of the East' with rolling hills, lakes and a lively music scene.",
     "tags": ["Umiam Lake", "Elephant Falls"]},
    {"name": "Mawlynnong", "state": "Meghalaya", "lat": 25.2000, "lon": 91.9167,
     "category": "Village", "tier": "Offbeat", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "Known as the cleanest village in Asia, with living root bridges nearby.",
     "tags": ["Cleanest Village", "Sky Walk"]},

    # Mizoram
    {"name": "Aizawl", "state": "Mizoram", "lat": 23.7271, "lon": 92.7176,
     "category": "Hill Station", "tier": "Offbeat", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "A vibrant hillside capital city set amid steep ridges and valleys.",
     "tags": ["Solomon's Temple", "Durtlang Hills"]},
    {"name": "Reiek", "state": "Mizoram", "lat": 23.7333, "lon": 92.5167,
     "category": "Nature", "tier": "Offbeat", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "A scenic peak near Aizawl offering panoramic views and a heritage village.",
     "tags": ["Reiek Tlang", "Heritage Village"]},

    # Nagaland
    {"name": "Kohima", "state": "Nagaland", "lat": 25.6751, "lon": 94.1086,
     "category": "Hill Station", "tier": "Popular", "best_months": [10, 11, 12, 1, 2],
     "desc": "Famous for the Hornbill Festival and pivotal WWII battlefield history.",
     "tags": ["Hornbill Festival", "War Cemetery"]},
    {"name": "Dzukou Valley", "state": "Nagaland", "lat": 25.5667, "lon": 94.1667,
     "category": "Nature", "tier": "Offbeat", "best_months": [6, 7, 8, 9, 10],
     "desc": "A pristine valley famed for seasonal blooms and epic trekking trails.",
     "tags": ["Trekking", "Seasonal Flowers"]},

    # Odisha
    {"name": "Puri", "state": "Odisha", "lat": 19.8135, "lon": 85.8312,
     "category": "Spiritual", "tier": "Very Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "Home to the sacred Jagannath Temple and the famous Rath Yatra festival.",
     "tags": ["Jagannath Temple", "Rath Yatra", "Puri Beach"]},
    {"name": "Konark", "state": "Odisha", "lat": 19.8876, "lon": 86.0945,
     "category": "Historical", "tier": "Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "Site of the UNESCO-listed Sun Temple, shaped like a colossal stone chariot.",
     "tags": ["Sun Temple", "Konark Dance Festival"]},
    {"name": "Bhitarkanika", "state": "Odisha", "lat": 20.7167, "lon": 86.9000,
     "category": "Wildlife", "tier": "Offbeat", "best_months": [11, 12, 1, 2],
     "desc": "A mangrove wilderness famous for saltwater crocodiles and migratory birds.",
     "tags": ["Mangroves", "Crocodile Sanctuary"]},

    # Punjab
    {"name": "Amritsar", "state": "Punjab", "lat": 31.6340, "lon": 74.8723,
     "category": "Spiritual", "tier": "Very Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "Home to the resplendent Golden Temple and the moving Wagah Border ceremony.",
     "tags": ["Golden Temple", "Wagah Border"]},
    {"name": "Anandpur Sahib", "state": "Punjab", "lat": 31.2360, "lon": 76.5020,
     "category": "Spiritual", "tier": "Moderate", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "A sacred Sikh town where the Khalsa Panth was founded in 1699.",
     "tags": ["Takht Sri Kesgarh Sahib", "Virasat-e-Khalsa"]},
    {"name": "Patiala", "state": "Punjab", "lat": 30.3398, "lon": 76.3869,
     "category": "Heritage", "tier": "Moderate", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "A royal city known for its grand forts, gardens and famous Patiala peg.",
     "tags": ["Qila Mubarak", "Sheesh Mahal"]},

    # Rajasthan
    {"name": "Jaipur", "state": "Rajasthan", "lat": 26.9124, "lon": 75.7873,
     "category": "Heritage", "tier": "Very Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "The vibrant Pink City, home to majestic forts, palaces and bazaars.",
     "tags": ["Amber Fort", "Hawa Mahal", "City Palace"]},
    {"name": "Udaipur", "state": "Rajasthan", "lat": 24.5854, "lon": 73.7125,
     "category": "Lake", "tier": "Very Popular", "best_months": [9, 10, 11, 12, 1, 2, 3],
     "desc": "The romantic 'City of Lakes', dotted with palaces reflecting on still waters.",
     "tags": ["Lake Pichola", "City Palace"]},
    {"name": "Jaisalmer", "state": "Rajasthan", "lat": 26.9157, "lon": 70.9083,
     "category": "Desert", "tier": "Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "The 'Golden City' rising from the Thar Desert, famed for camel safaris.",
     "tags": ["Jaisalmer Fort", "Camel Safari", "Sam Sand Dunes"]},

    # Sikkim
    {"name": "Gangtok", "state": "Sikkim", "lat": 27.3389, "lon": 88.6065,
     "category": "Hill Station", "tier": "Very Popular", "best_months": [3, 4, 5, 10, 11],
     "desc": "Sikkim's charming capital with monasteries, cable cars and Himalayan views.",
     "tags": ["MG Road", "Rumtek Monastery"]},
    {"name": "Nathula Pass", "state": "Sikkim", "lat": 27.3860, "lon": 88.8410,
     "category": "Adventure", "tier": "Moderate", "best_months": [5, 6, 9, 10],
     "desc": "A historic Himalayan pass on the old Silk Route bordering Tibet.",
     "tags": ["Indo-China Border", "Silk Route"]},
    {"name": "Pelling", "state": "Sikkim", "lat": 27.2167, "lon": 88.2167,
     "category": "Hill Station", "tier": "Popular", "best_months": [3, 4, 5, 10, 11],
     "desc": "Offers some of the best views of Mt. Kanchenjunga along with ancient monasteries.",
     "tags": ["Kanchenjunga Views", "Pemayangtse Monastery"]},

    # Tamil Nadu
    {"name": "Ooty", "state": "Tamil Nadu", "lat": 11.4064, "lon": 76.6932,
     "category": "Hill Station", "tier": "Very Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "The 'Queen of Hill Stations' in the Nilgiris, famed for its toy train and gardens.",
     "tags": ["Nilgiri Toy Train", "Botanical Garden"]},
    {"name": "Madurai", "state": "Tamil Nadu", "lat": 9.9252, "lon": 78.1198,
     "category": "Spiritual", "tier": "Popular", "best_months": [10, 11, 12, 1, 2],
     "desc": "An ancient temple city centred around the magnificent Meenakshi Amman Temple.",
     "tags": ["Meenakshi Temple", "Thirumalai Nayakkar Palace"]},
    {"name": "Kanyakumari", "state": "Tamil Nadu", "lat": 8.0883, "lon": 77.5385,
     "category": "Beach", "tier": "Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "India's southernmost tip, where three seas meet in a spectacular sunrise/sunset.",
     "tags": ["Vivekananda Rock", "Thiruvalluvar Statue"]},

    # Telangana
    {"name": "Hyderabad", "state": "Telangana", "lat": 17.3850, "lon": 78.4867,
     "category": "Heritage", "tier": "Very Popular", "best_months": [10, 11, 12, 1, 2],
     "desc": "The 'City of Pearls', famous for the Charminar, biryani and IT hubs.",
     "tags": ["Charminar", "Golconda Fort", "Hyderabadi Biryani"]},
    {"name": "Warangal", "state": "Telangana", "lat": 17.9689, "lon": 79.5941,
     "category": "Historical", "tier": "Moderate", "best_months": [10, 11, 12, 1, 2],
     "desc": "The former Kakatiya capital, known for its ornate fort and thousand-pillar temple.",
     "tags": ["Warangal Fort", "Thousand Pillar Temple"]},
    {"name": "Nagarjuna Sagar", "state": "Telangana", "lat": 16.5738, "lon": 79.3117,
     "category": "Nature", "tier": "Offbeat", "best_months": [10, 11, 12, 1, 2],
     "desc": "Home to one of the world's largest masonry dams and Buddhist heritage island.",
     "tags": ["Nagarjuna Sagar Dam", "Nagarjunakonda Island"]},

    # Tripura
    {"name": "Agartala", "state": "Tripura", "lat": 23.8315, "lon": 91.2868,
     "category": "Historical", "tier": "Moderate", "best_months": [10, 11, 12, 1, 2],
     "desc": "Tripura's capital, home to the grand Ujjayanta Palace.",
     "tags": ["Ujjayanta Palace", "Neermahal"]},
    {"name": "Unakoti", "state": "Tripura", "lat": 24.2833, "lon": 92.0333,
     "category": "Historical", "tier": "Offbeat", "best_months": [10, 11, 12, 1, 2],
     "desc": "A mysterious hillside of giant rock-cut carvings and ancient legends.",
     "tags": ["Rock Carvings", "Waterfalls"]},

    # Uttar Pradesh
    {"name": "Agra", "state": "Uttar Pradesh", "lat": 27.1767, "lon": 78.0081,
     "category": "Historical", "tier": "Very Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "Home to the Taj Mahal, one of the Seven Wonders of the World.",
     "tags": ["Taj Mahal", "Agra Fort", "Fatehpur Sikri"]},
    {"name": "Varanasi", "state": "Uttar Pradesh", "lat": 25.3176, "lon": 82.9739,
     "category": "Spiritual", "tier": "Very Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "One of the world's oldest living cities, sacred ghats line the Ganges at dawn.",
     "tags": ["Ganga Aarti", "Kashi Vishwanath Temple"]},
    {"name": "Lucknow", "state": "Uttar Pradesh", "lat": 26.8467, "lon": 80.9462,
     "category": "Heritage", "tier": "Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "The 'City of Nawabs', celebrated for its architecture, etiquette and cuisine.",
     "tags": ["Bara Imambara", "Chikankari"]},

    # Uttarakhand
    {"name": "Nainital", "state": "Uttarakhand", "lat": 29.3919, "lon": 79.4542,
     "category": "Hill Station", "tier": "Very Popular", "best_months": [3, 4, 5, 6, 9, 10, 11],
     "desc": "A charming lake town in the Kumaon Hills, a favourite colonial-era retreat.",
     "tags": ["Naini Lake", "Mall Road"]},
    {"name": "Rishikesh", "state": "Uttarakhand", "lat": 30.0869, "lon": 78.2676,
     "category": "Spiritual", "tier": "Very Popular", "best_months": [9, 10, 11, 2, 3, 4],
     "desc": "The 'Yoga Capital of the World', also a hub for river rafting on the Ganges.",
     "tags": ["River Rafting", "Laxman Jhula", "Yoga Ashrams"]},
    {"name": "Mussoorie", "state": "Uttarakhand", "lat": 30.4598, "lon": 78.0664,
     "category": "Hill Station", "tier": "Popular", "best_months": [3, 4, 5, 6, 9, 10, 11],
     "desc": "The 'Queen of Hills' with cascading waterfalls and views of the Doon Valley.",
     "tags": ["Kempty Falls", "Camel's Back Road"]},

    # West Bengal
    {"name": "Darjeeling", "state": "West Bengal", "lat": 27.0410, "lon": 88.2663,
     "category": "Hill Station", "tier": "Very Popular", "best_months": [3, 4, 5, 10, 11],
     "desc": "Famed for its toy train, tea gardens and stunning views of Kanchenjunga.",
     "tags": ["Tea Gardens", "Toy Train", "Tiger Hill"]},
    {"name": "Kolkata", "state": "West Bengal", "lat": 22.5726, "lon": 88.3639,
     "category": "City", "tier": "Very Popular", "best_months": [10, 11, 12, 1, 2],
     "desc": "The 'City of Joy', a cultural capital rich in colonial architecture and art.",
     "tags": ["Victoria Memorial", "Howrah Bridge", "Durga Puja"]},
    {"name": "Sundarbans", "state": "West Bengal", "lat": 21.9497, "lon": 88.9468,
     "category": "Wildlife", "tier": "Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "The world's largest mangrove forest and home of the Royal Bengal Tiger.",
     "tags": ["Royal Bengal Tiger", "Mangrove Boat Safari"]},

    # Andaman and Nicobar Islands
    {"name": "Port Blair", "state": "Andaman and Nicobar Islands", "lat": 11.6234, "lon": 92.7265,
     "category": "Island", "tier": "Popular", "best_months": [10, 11, 12, 1, 2, 3, 4, 5],
     "desc": "The gateway to the Andamans, home to the historic Cellular Jail.",
     "tags": ["Cellular Jail", "Corbyn's Cove"]},
    {"name": "Havelock Island", "state": "Andaman and Nicobar Islands", "lat": 12.0333, "lon": 92.9833,
     "category": "Beach", "tier": "Very Popular", "best_months": [10, 11, 12, 1, 2, 3, 4, 5],
     "desc": "Home to Radhanagar Beach, ranked among Asia's finest, and world-class diving.",
     "tags": ["Radhanagar Beach", "Scuba Diving"]},

    # Chandigarh
    {"name": "Chandigarh", "state": "Chandigarh", "lat": 30.7333, "lon": 76.7794,
     "category": "City", "tier": "Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "India's meticulously planned city, famous for the Rock Garden and Sukhna Lake.",
     "tags": ["Rock Garden", "Sukhna Lake"]},

    # Dadra and Nagar Haveli and Daman and Diu
    {"name": "Diu", "state": "Dadra and Nagar Haveli and Daman and Diu", "lat": 20.7144, "lon": 70.9874,
     "category": "Beach", "tier": "Moderate", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "A tranquil former Portuguese colony with pristine beaches and old forts.",
     "tags": ["Diu Fort", "Nagoa Beach"]},
    {"name": "Silvassa", "state": "Dadra and Nagar Haveli and Daman and Diu", "lat": 20.2738, "lon": 73.0169,
     "category": "Nature", "tier": "Offbeat", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "A green enclave dotted with gardens, lakes and tribal culture.",
     "tags": ["Vanganga Lake Garden", "Tribal Museum"]},

    # Delhi
    {"name": "New Delhi", "state": "Delhi", "lat": 28.6139, "lon": 77.2090,
     "category": "Historical", "tier": "Very Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "India's capital, a fascinating mix of Mughal monuments and modern governance.",
     "tags": ["India Gate", "Red Fort", "Humayun's Tomb"]},
    {"name": "Qutub Minar", "state": "Delhi", "lat": 28.5245, "lon": 77.1855,
     "category": "Historical", "tier": "Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "A UNESCO World Heritage 73m minaret, the tallest brick minaret in the world.",
     "tags": ["Qutub Complex", "Iron Pillar"]},

    # Jammu and Kashmir
    {"name": "Srinagar", "state": "Jammu and Kashmir", "lat": 34.0837, "lon": 74.7973,
     "category": "Lake", "tier": "Very Popular", "best_months": [4, 5, 6, 9, 10],
     "desc": "The summer capital of J&K, famed for houseboats and shikara rides on Dal Lake.",
     "tags": ["Dal Lake", "Shikara Ride", "Mughal Gardens"]},
    {"name": "Gulmarg", "state": "Jammu and Kashmir", "lat": 34.0484, "lon": 74.3805,
     "category": "Hill Station", "tier": "Very Popular", "best_months": [12, 1, 2, 3, 5, 6],
     "desc": "India's premier ski resort with the world's highest cable car, the Gondola.",
     "tags": ["Gondola Ride", "Skiing"]},
    {"name": "Pahalgam", "state": "Jammu and Kashmir", "lat": 34.0161, "lon": 75.3152,
     "category": "Nature", "tier": "Popular", "best_months": [4, 5, 6, 9, 10],
     "desc": "The 'Valley of Shepherds', surrounded by meadows, pine forests and rivers.",
     "tags": ["Betaab Valley", "Aru Valley"]},

    # Ladakh
    {"name": "Leh", "state": "Ladakh", "lat": 34.1526, "lon": 77.5771,
     "category": "Adventure", "tier": "Very Popular", "best_months": [5, 6, 7, 8, 9],
     "desc": "A high-altitude desert town of monasteries, palaces and epic mountain roads.",
     "tags": ["Leh Palace", "Magnetic Hill"]},
    {"name": "Pangong Lake", "state": "Ladakh", "lat": 33.7500, "lon": 78.6667,
     "category": "Lake", "tier": "Popular", "best_months": [5, 6, 7, 8, 9],
     "desc": "A mesmerising high-altitude lake that changes colour through the day.",
     "tags": ["Changing Colours", "Camping"]},
    {"name": "Nubra Valley", "state": "Ladakh", "lat": 34.6800, "lon": 77.5700,
     "category": "Desert", "tier": "Moderate", "best_months": [5, 6, 7, 8, 9],
     "desc": "A cold desert valley famous for double-humped camels and sand dunes.",
     "tags": ["Bactrian Camels", "Diskit Monastery"]},

    # Lakshadweep
    {"name": "Kavaratti", "state": "Lakshadweep", "lat": 10.5669, "lon": 72.6420,
     "category": "Island", "tier": "Moderate", "best_months": [10, 11, 12, 1, 2, 3, 4, 5],
     "desc": "The capital island of Lakshadweep with turquoise lagoons perfect for snorkelling.",
     "tags": ["Lagoon", "Coral Reefs"]},
    {"name": "Agatti Island", "state": "Lakshadweep", "lat": 10.8467, "lon": 72.1833,
     "category": "Island", "tier": "Offbeat", "best_months": [10, 11, 12, 1, 2, 3, 4, 5],
     "desc": "The gateway island to Lakshadweep, ringed by dazzling coral reefs.",
     "tags": ["Scuba Diving", "Coral Reefs"]},

    # Puducherry
    {"name": "Puducherry", "state": "Puducherry", "lat": 11.9416, "lon": 79.8083,
     "category": "Heritage", "tier": "Popular", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "A former French colony with a charming promenade, cafes and colonial villas.",
     "tags": ["French Quarter", "Promenade Beach"]},
    {"name": "Auroville", "state": "Puducherry", "lat": 12.0067, "lon": 79.8100,
     "category": "Village", "tier": "Moderate", "best_months": [10, 11, 12, 1, 2, 3],
     "desc": "An experimental universal township centred around the golden Matrimandir.",
     "tags": ["Matrimandir", "Sustainable Living"]},
]

ALL_STATES = sorted(set(p["state"] for p in PLACES))

WEATHER_CODES = {
    0: ("Clear sky", "☀️"), 1: ("Mainly clear", "🌤️"), 2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁️"), 45: ("Fog", "🌫️"), 48: ("Rime fog", "🌫️"),
    51: ("Light drizzle", "🌦️"), 53: ("Moderate drizzle", "🌦️"), 55: ("Dense drizzle", "🌧️"),
    56: ("Freezing drizzle", "🌧️"), 57: ("Freezing drizzle", "🌧️"),
    61: ("Slight rain", "🌧️"), 63: ("Moderate rain", "🌧️"), 65: ("Heavy rain", "⛈️"),
    66: ("Freezing rain", "🌧️"), 67: ("Heavy freezing rain", "🌧️"),
    71: ("Slight snow", "🌨️"), 73: ("Moderate snow", "🌨️"), 75: ("Heavy snow", "❄️"),
    77: ("Snow grains", "❄️"), 80: ("Slight rain showers", "🌦️"),
    81: ("Moderate rain showers", "🌧️"), 82: ("Violent rain showers", "⛈️"),
    85: ("Slight snow showers", "🌨️"), 86: ("Heavy snow showers", "❄️"),
    95: ("Thunderstorm", "⛈️"), 96: ("Thunderstorm + hail", "⛈️"), 99: ("Severe thunderstorm", "⛈️"),
}
BAD_WEATHER_CODES = {45, 48, 51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99}


def weather_desc(code):
    return WEATHER_CODES.get(code, ("Unknown", "🌡️"))


# =========================================================================
# 4. HELPER / LOGIC FUNCTIONS
# =========================================================================
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def months_to_str(months):
    if not months:
        return "Year-round"
    months = sorted(set(months))
    groups, start, prev = [], months[0], months[0]
    for m in months[1:]:
        if m == prev + 1 or (prev == 12 and m == 1):
            prev = m
        else:
            groups.append((start, prev))
            start = prev = m
    groups.append((start, prev))
    parts = []
    for s, e in groups:
        parts.append(MONTH_NAMES[s - 1] if s == e else f"{MONTH_NAMES[s - 1]}–{MONTH_NAMES[e - 1]}")
    return ", ".join(parts)


def get_shoulder_months(best_months):
    shoulder = set()
    for m in best_months:
        prev_m = 12 if m == 1 else m - 1
        next_m = 1 if m == 12 else m + 1
        if prev_m not in best_months:
            shoulder.add(prev_m)
        if next_m not in best_months:
            shoulder.add(next_m)
    return shoulder - set(best_months)


@st.cache_data(ttl=3600, show_spinner=False)
def geocode_india(query):
    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": query, "count": 8, "language": "en", "format": "json"},
            timeout=10,
        )
        data = r.json()
        results = data.get("results", []) or []
        india_results = [x for x in results if x.get("country_code") == "IN"]
        return india_results
    except Exception:
        return []


@st.cache_data(ttl=1800, show_spinner=False)
def get_weather(lat, lon):
    try:
        params = {
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,is_day",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,sunrise,sunset,uv_index_max",
            "timezone": "auto",
            "forecast_days": 7,
        }
        r = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


@st.cache_data(ttl=86400, show_spinner=False)
def get_wiki_summary(title):
    try:
        safe_title = title.replace(" ", "_")
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(safe_title)}"
        r = requests.get(url, timeout=10, headers={"User-Agent": "TravelWiseAI/1.0"})
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def find_place(query):
    """Search curated DB first (exact -> contains -> fuzzy). Returns (place, alternatives)."""
    q = query.strip().lower()
    if not q:
        return None, []
    for p in PLACES:
        if p["name"].lower() == q:
            return p, []
    contains = [p for p in PLACES if q in p["name"].lower() or q in p["state"].lower()]
    if contains:
        return contains[0], contains[1:6]
    names = [p["name"] for p in PLACES]
    close = difflib.get_close_matches(query, names, n=6, cutoff=0.45)
    if close:
        match = next(p for p in PLACES if p["name"] == close[0])
        others = [p for p in PLACES if p["name"] in close[1:]]
        return match, others
    return None, []


def build_custom_place(geo_result):
    """Build a lightweight place dict for a location found via geocoding but not curated."""
    return {
        "name": geo_result.get("name", "Unknown"),
        "state": geo_result.get("admin1", "India"),
        "lat": geo_result.get("latitude"),
        "lon": geo_result.get("longitude"),
        "category": "Destination",
        "tier": "Moderate",
        "best_months": [10, 11, 12, 1, 2, 3],
        "desc": None,
        "tags": [],
        "is_custom": True,
    }


def crowd_level(place, weather_json):
    now = datetime.now()
    month = now.month
    is_weekend = now.weekday() >= 5
    tier_base = {"Very Popular": 68, "Popular": 50, "Moderate": 35, "Offbeat": 18}
    base = tier_base.get(place.get("tier", "Moderate"), 40)

    best = place.get("best_months", [])
    shoulder = get_shoulder_months(best) if best else set()

    if best and month in best:
        season_factor = 1.35
    elif month in shoulder:
        season_factor = 1.05
    else:
        season_factor = 0.65

    weekend_factor = 1.18 if is_weekend else 1.0
    holiday_factor = 1.12 if month in (5, 6, 10, 11, 12, 1) else 1.0

    weather_factor = 1.0
    note = ""
    if weather_json and weather_json.get("current"):
        code = weather_json["current"].get("weather_code")
        if code in BAD_WEATHER_CODES:
            weather_factor = 0.8
            note = "Current weather conditions may slightly reduce footfall."

    score = base * season_factor * weekend_factor * holiday_factor * weather_factor
    score = round(min(max(score, 5), 98))

    if score < 30:
        label, color = "Low", "#22c55e"
    elif score < 55:
        label, color = "Moderate", "#eab308"
    elif score < 78:
        label, color = "High", "#f97316"
    else:
        label, color = "Very High", "#ef4444"
    return score, label, color, note


def weather_comfort_score(weather_json):
    if not weather_json or not weather_json.get("current"):
        return 50
    temp = weather_json["current"].get("temperature_2m", 25)
    precip = weather_json["current"].get("precipitation", 0) or 0
    ideal = 24
    diff = abs(temp - ideal)
    score = max(0, 100 - diff * 4)
    if precip > 0:
        score -= min(precip * 10, 30)
    return round(max(0, min(100, score)))


def season_fit_score(place):
    month = datetime.now().month
    best = place.get("best_months", [])
    if not best:
        return 60
    if month in best:
        return 95
    elif month in get_shoulder_months(best):
        return 65
    return 35


def overall_travel_score(weather_s, season_s, crowd_s):
    inv_crowd = 100 - crowd_s
    total = weather_s * 0.35 + season_s * 0.35 + inv_crowd * 0.30
    return round(total)


def score_verdict(total):
    if total >= 80:
        return "Excellent time to visit!", "🌟", "#22c55e"
    elif total >= 60:
        return "Good time to visit", "👍", "#84cc16"
    elif total >= 40:
        return "Fair — plan carefully", "⚠️", "#eab308"
    return "Not ideal right now", "❌", "#ef4444"


# =========================================================================
# 5. UI RENDER HELPERS
# =========================================================================
def render_hero():
    st.markdown(
        """
        <div class="hero-banner">
          <div class="hero-inner">
            <div class="hero-title">🇮🇳 TravelWise AI</div>
            <p class="hero-sub">Your smart tourism decision assistant for exploring India — live weather,
            AI-estimated crowd levels, and personalised travel scores for every state & destination.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_badges(place):
    icon = CATEGORY_ICON.get(place.get("category"), "📍")
    html = f'<span class="badge badge-cat">{icon} {place.get("category","Destination")}</span>'
    html += f'<span class="badge badge-tier">🔥 {place.get("tier","Moderate")}</span>'
    for tag in place.get("tags", [])[:5]:
        html += f'<span class="badge badge-tag">{tag}</span>'
    st.markdown(html, unsafe_allow_html=True)


def render_metric_box(col, label, value):
    col.markdown(
        f"""<div class="metric-box"><div class="val">{value}</div><div class="lbl">{label}</div></div>""",
        unsafe_allow_html=True,
    )


def render_crowd_gauge(score, label, color):
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": "%", "font": {"size": 34, "color": "white"}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "white", "tickfont": {"color": "white"}},
                "bar": {"color": color},
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 30], "color": "rgba(34,197,94,0.25)"},
                    {"range": [30, 55], "color": "rgba(234,179,8,0.25)"},
                    {"range": [55, 78], "color": "rgba(249,115,22,0.25)"},
                    {"range": [78, 100], "color": "rgba(239,68,68,0.25)"},
                ],
            },
        )
    )
    fig.update_layout(
        height=230, margin=dict(l=20, r=20, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", font={"color": "white"},
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown(
        f"<div style='text-align:center; font-weight:700; color:{color}; font-size:1.1rem;'>Crowd Level: {label}</div>",
        unsafe_allow_html=True,
    )


def render_forecast_chart(weather_json):
    daily = weather_json.get("daily", {})
    if not daily:
        st.info("Forecast data unavailable right now.")
        return
    dates = daily.get("time", [])
    tmax = daily.get("temperature_2m_max", [])
    tmin = daily.get("temperature_2m_min", [])
    precip = daily.get("precipitation_sum", [])

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=dates, y=tmax, name="Max Temp (°C)", line=dict(color="#FF9933", width=3)))
    fig.add_trace(go.Scatter(x=dates, y=tmin, name="Min Temp (°C)", line=dict(color="#38bdf8", width=3)))
    fig.add_trace(
        go.Bar(x=dates, y=precip, name="Precipitation (mm)", marker_color="rgba(56,189,248,0.35)"),
        secondary_y=True,
    )
    fig.update_layout(
        height=340, margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "white"}, legend=dict(orientation="h", y=1.15),
        xaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
    )
    fig.update_yaxes(title_text="Temp (°C)", gridcolor="rgba(255,255,255,0.08)", secondary_y=False)
    fig.update_yaxes(title_text="Precip (mm)", gridcolor="rgba(255,255,255,0.02)", secondary_y=True)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def select_place_cb(name):
    st.session_state.query = name
    st.session_state.nav = "🔍 Search Destination"


def render_place_card_button(p, key_suffix=""):
    icon = CATEGORY_ICON.get(p.get("category"), "📍")
    with st.container():
        st.markdown(
            f"""<div class="tw-card"><h4>{icon} {p['name']}</h4>
            <p style="color:#9fb0c9; margin-bottom:0.4rem;">{p['state']}</p>
            <span class="badge badge-cat">{p.get('category','')}</span>
            <span class="badge badge-tier">{p.get('tier','')}</span></div>""",
            unsafe_allow_html=True,
        )
        st.button(f"View {p['name']} →", key=f"btn_{p['name']}_{key_suffix}",
                  on_click=select_place_cb, args=(p["name"],))


# =========================================================================
# 6. MAIN DETAIL RENDERER
# =========================================================================
def render_place_details(place):
    is_custom = place.get("is_custom", False)

    with st.spinner("Fetching live data..."):
        weather_json = get_weather(place["lat"], place["lon"]) if place.get("lat") else None
        wiki_title = place["name"].split("(")[0].strip()
        wiki = get_wiki_summary(f"{wiki_title}, India") or get_wiki_summary(wiki_title)

    # --- Hero ---
    icon = CATEGORY_ICON.get(place.get("category"), "📍")
    st.markdown(
        f"""<div class="place-hero">
        <div class="place-name">{icon} {place['name']}</div>
        <div class="place-loc">📍 {place['state']}, India</div>
        """,
        unsafe_allow_html=True,
    )
    render_badges(place)
    st.markdown("</div>", unsafe_allow_html=True)

    # --- Description ---
    col_img, col_text = st.columns([1, 2])
    thumb = None
    extract = place.get("desc")
    if wiki:
        thumb = wiki.get("thumbnail", {}).get("source") if wiki.get("thumbnail") else None
        extract = wiki.get("extract") or extract
    with col_img:
        if thumb:
            st.image(thumb, use_container_width=True)
        else:
            st.markdown(
                f"""<div class="tw-card" style="text-align:center; padding:3rem 1rem;">
                <div style="font-size:3rem;">{icon}</div><p>No image available</p></div>""",
                unsafe_allow_html=True,
            )
    with col_text:
        st.markdown(f"<div class='tw-card'><h4>About {place['name']}</h4><p>{extract or 'No description available for this destination yet.'}</p></div>", unsafe_allow_html=True)
        if wiki and wiki.get("content_urls"):
            st.markdown(f"[Read more on Wikipedia]({wiki['content_urls']['desktop']['page']})")

    # --- Live Weather ---
    st.markdown("<div class='section-title'>🌤️ Live Weather</div>", unsafe_allow_html=True)
    if weather_json and weather_json.get("current"):
        cur = weather_json["current"]
        desc, wicon = weather_desc(cur.get("weather_code"))
        c1, c2, c3, c4, c5 = st.columns(5)
        render_metric_box(c1, "Condition", f"{wicon} {desc}")
        render_metric_box(c2, "Temperature", f"{cur.get('temperature_2m','–')}°C")
        render_metric_box(c3, "Feels Like", f"{cur.get('apparent_temperature','–')}°C")
        render_metric_box(c4, "Humidity", f"{cur.get('relative_humidity_2m','–')}%")
        render_metric_box(c5, "Wind", f"{cur.get('wind_speed_10m','–')} km/h")
        st.write("")
        st.markdown("<div class='section-title'>📅 7-Day Forecast</div>", unsafe_allow_html=True)
        render_forecast_chart(weather_json)
    else:
        st.warning("Live weather data is temporarily unavailable for this location.")

    # --- Crowd & Score ---
    st.markdown("<div class='section-title'>👥 AI Crowd Estimate & Travel Score</div>", unsafe_allow_html=True)
    crowd_score, crowd_label, crowd_color, crowd_note = crowd_level(place, weather_json)
    w_score = weather_comfort_score(weather_json)
    s_score = season_fit_score(place)
    total = overall_travel_score(w_score, s_score, crowd_score)
    verdict, vicon, vcolor = score_verdict(total)

    cg1, cg2 = st.columns([1, 1])
    with cg1:
        render_crowd_gauge(crowd_score, crowd_label, crowd_color)
        if crowd_note:
            st.caption(f"ℹ️ {crowd_note}")
        st.caption("Crowd levels are AI-estimated using seasonality, weekday/weekend patterns, "
                    "holiday periods and live weather — not real-time footfall sensors.")
    with cg2:
        st.markdown(
            f"""<div class="tw-card" style="text-align:center; padding:1.6rem;">
            <div style="font-size:2.4rem;">{vicon}</div>
            <div style="font-size:1.6rem; font-weight:800; color:{vcolor}; font-family:'Poppins',sans-serif;">{total}/100</div>
            <div style="color:#d8dee9; font-weight:600; margin-top:0.2rem;">{verdict}</div>
            </div>""",
            unsafe_allow_html=True,
        )
        b1, b2, b3 = st.columns(3)
        render_metric_box(b1, "Weather Fit", f"{w_score}%")
        render_metric_box(b2, "Season Fit", f"{s_score}%")
        render_metric_box(b3, "Crowd Score", f"{100-crowd_score}%")

    # --- Best time to visit ---
    st.markdown("<div class='section-title'>🗓️ Best Time To Visit</div>", unsafe_allow_html=True)
    st.markdown(
        f"""<div class="tw-card"><b>Ideal months:</b> {months_to_str(place.get('best_months', []))}<br>
        <span style="color:#9fb0c9;">Visiting during these months typically offers the most pleasant weather
        and best overall experience for {place['name']}.</span></div>""",
        unsafe_allow_html=True,
    )

    # --- Map ---
    st.markdown("<div class='section-title'>🗺️ Location</div>", unsafe_allow_html=True)
    if place.get("lat") and place.get("lon"):
        st.map(pd.DataFrame({"lat": [place["lat"]], "lon": [place["lon"]]}), zoom=8, use_container_width=True)

    # --- More places in same state ---
    if not is_custom:
        others = [p for p in PLACES if p["state"] == place["state"] and p["name"] != place["name"]]
        if others:
            st.markdown(f"<div class='section-title'>✨ More to Explore in {place['state']}</div>", unsafe_allow_html=True)
            cols = st.columns(min(3, len(others)))
            for i, p in enumerate(others[:6]):
                with cols[i % len(cols)]:
                    render_place_card_button(p, key_suffix="rel")


# =========================================================================
# 7. SIDEBAR
# =========================================================================
def render_sidebar():
    with st.sidebar:
        st.markdown("## 🇮🇳 TravelWise AI")
        st.caption("Smart Tourism Decision Assistant — India Edition")
        st.markdown("---")
        if "nav" not in st.session_state:
            st.session_state.nav = "🔍 Search Destination"
        st.radio(
            "Navigate",
            ["🔍 Search Destination", "🗂️ Browse by State", "ℹ️ About"],
            key="nav",
        )
        st.markdown("---")
        st.markdown("### 📊 Coverage")
        c1, c2 = st.columns(2)
        c1.metric("States/UTs", len(ALL_STATES))
        c2.metric("Destinations", len(PLACES))
        st.markdown("---")
        st.markdown(
            """
            **Data Sources**
            - 🌦️ Weather & Geocoding: Open-Meteo
            - 📖 Place info: Wikipedia
            - 🧠 Crowd & Score: TravelWise AI heuristic engine

            *No API keys required — 100% free & open.*
            """
        )


# =========================================================================
# 8. MAIN APP
# =========================================================================
def main():
    render_sidebar()
    render_hero()

    if "query" not in st.session_state:
        st.session_state.query = ""

    nav = st.session_state.nav

    if nav == "🔍 Search Destination":
        st.text_input(
            "Search any destination in India",
            key="query",
            placeholder="e.g. Manali, Goa, Munnar, Varanasi, Leh...",
            label_visibility="collapsed",
        )

        st.markdown("<div class='chip-row'>", unsafe_allow_html=True)
        trending = ["Agra", "Goa", "Manali", "Munnar", "Jaipur", "Varanasi", "Leh", "Darjeeling"]
        chip_cols = st.columns(len(trending))
        for i, t in enumerate(trending):
            with chip_cols[i]:
                st.button(t, key=f"chip_{t}", on_click=select_place_cb, args=(t,))
        st.markdown("</div>", unsafe_allow_html=True)

        query = st.session_state.query
        if query:
            place, alternatives = find_place(query)
            if place is None:
                geo_results = geocode_india(query)
                if geo_results:
                    place = build_custom_place(geo_results[0])
                    st.info(f"Showing live results for **{place['name']}, {place['state']}** "
                            f"(not in our curated list, but found via live geocoding).")
                else:
                    st.error(f"❌ Couldn't find '{query}' in India. Try another spelling, or browse by state.")
                    place = None

            if place:
                render_place_details(place)
                if alternatives:
                    st.markdown("<div class='section-title'>Did you mean?</div>", unsafe_allow_html=True)
                    cols = st.columns(min(3, len(alternatives)))
                    for i, p in enumerate(alternatives[:6]):
                        with cols[i % len(cols)]:
                            render_place_card_button(p, key_suffix="alt")
        else:
            st.markdown("<div class='section-title'>🌟 Trending Destinations</div>", unsafe_allow_html=True)
            featured_names = trending
            featured = [p for p in PLACES if p["name"] in featured_names]
            cols = st.columns(4)
            for i, p in enumerate(featured):
                with cols[i % 4]:
                    render_place_card_button(p, key_suffix="feat")

    elif nav == "🗂️ Browse by State":
        st.markdown("<div class='section-title'>🗂️ Browse Destinations by State / UT</div>", unsafe_allow_html=True)
        col_a, col_b = st.columns([1, 3])
        with col_a:
            region_filter = st.selectbox("Filter by region", ["All"] + sorted(set(STATE_REGION.values())))
        states_to_show = ALL_STATES if region_filter == "All" else [
            s for s in ALL_STATES if STATE_REGION.get(s) == region_filter
        ]
        with col_b:
            state = st.selectbox("Select a State / UT", states_to_show)

        state_places = [p for p in PLACES if p["state"] == state]
        st.markdown(f"### {state} — {len(state_places)} curated destinations")
        cols = st.columns(3)
        for i, p in enumerate(state_places):
            with cols[i % 3]:
                render_place_card_button(p, key_suffix="browse")

    else:  # About
        st.markdown("<div class='section-title'>ℹ️ About TravelWise AI</div>", unsafe_allow_html=True)
        st.markdown(
            """
            <div class="tw-card">
            <p><b>TravelWise AI</b> is a smart tourism decision assistant built exclusively for exploring
            <b>India</b> — covering all 28 states and 8 union territories with curated destinations.</p>
            <p>For every place you search, the app combines:</p>
            <ul>
                <li>🌦️ <b>Live weather & 7-day forecast</b> (Open-Meteo)</li>
                <li>📖 <b>Rich place information</b> (Wikipedia)</li>
                <li>👥 <b>AI-estimated crowd levels</b>, based on seasonality, weekday/weekend
                    patterns, Indian holiday season trends, and live weather conditions</li>
                <li>🧮 <b>An overall Travel Score</b> combining weather comfort, seasonal fit
                    and crowd levels to tell you if now is a good time to visit</li>
            </ul>
            <p style="color:#9fb0c9;"><i>Disclaimer: Crowd levels are heuristic AI estimates for
            planning guidance only, not live footfall sensor data.</i></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        "<hr><p style='text-align:center; color:#5b6577; font-size:0.85rem;'>"
        "Made with ❤️ for incredible India · TravelWise AI © 2024 · Powered by Open-Meteo & Wikipedia</p>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()