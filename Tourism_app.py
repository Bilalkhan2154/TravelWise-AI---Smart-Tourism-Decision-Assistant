# -*- coding: utf-8 -*-
"""
TravelWise AI - Smart Tourism Decision Assistant
=================================================
Single-file edition. Everything - curated destination data, live weather /
geocoding / climate / Wikipedia lookups, the query-parsing & scoring engine,
the HTML template, CSS and JS - lives in this one file.

Setup:
    pip install flask requests
    python travelwise_app.py
Then open http://127.0.0.1:5000

Data honesty, at a glance:
  - Current weather & 7-day forecast .... LIVE (Open-Meteo API, no key needed)
  - Best months for curated states ...... hand-researched domain knowledge
  - Best months for any other place ..... LIVE, computed from ~2 years of
                                           historical daily temp/rainfall
  - Cultural significance score ......... a curated, opinionated 0-100 judgment
                                           call, shown transparently as that
  - Crowd levels ......................... an ESTIMATED heuristic model, not a
                                           live sensor feed - labeled as such
  - Place descriptions / context ........ enriched with LIVE Wikipedia summaries
                                           + direct links (cached, with a clearly
                                           labeled fallback if unreachable)

Coverage: all 28 Indian states + all 8 Union Territories are curated (36
regions, 100+ places). Anything outside that (any city/country in the world)
is handled live via geocoding + historical climate modeling instead of ever
silently defaulting to a random curated state.

If there is no internet connection, every live call falls back to a clearly
labeled synthetic estimate so the app still runs end-to-end.
"""
import calendar
import hashlib
import re
import statistics
import urllib.parse
from datetime import date, timedelta

import requests
from flask import Flask, jsonify, render_template_string, request

MONTH_NAMES = list(calendar.month_name)

# =====================================================================
# 1. CURATED DESTINATION DATABASE — all 28 states + 8 union territories
# =====================================================================
# Every place has real-world coordinates (used to pull LIVE weather from
# Open-Meteo) plus hand-curated fields that a weather API can't tell you:
# how culturally/historically significant a place is, what season actually
# suits it, typical budget level, and known safety notes.
#
# cultural_weight (0-100): a rough, opinionated score of how much a place's
# value comes from history / religion / heritage / living tradition, versus
# being primarily a recreational or scenic stop. It's a judgment call, not
# a measurement - shown to the user as exactly that.

STATES = {

    # ---------------------------------------------------------------- GOA
    "goa": {
        "name": "Goa", "region": "West India", "aliases": ["goa"],
        "capital_coords": (15.4909, 73.8278),
        "monsoon_months": [6, 7, 8, 9], "best_months": [11, 12, 1, 2], "shoulder_months": [10, 3],
        "culture_note": (
            "A former Portuguese colony for over 400 years, Goa blends Konkani "
            "coastal culture with Latin Catholic heritage - whitewashed churches, "
            "feni distilleries, and a laid-back pace distinct from the rest of India."
        ),
        "places": [
            {"id": "baga", "name": "Baga Beach", "type": "Beach", "lat": 15.5553, "lon": 73.7517,
             "cultural_weight": 20, "tag": "popular", "price": 2200, "crowd_base": 60, "weekend_bump": 18,
             "desc": "The liveliest beach strip - beach shacks, water sports and nightlife."},
            {"id": "palolem", "name": "Palolem Beach", "type": "Beach", "lat": 15.0100, "lon": 74.0233,
             "cultural_weight": 20, "tag": "hidden-gem", "price": 1800, "crowd_base": 30, "weekend_bump": 10,
             "desc": "A crescent-shaped South Goa beach, calmer and more scenic than the north."},
            {"id": "old_goa", "name": "Old Goa (Basilica & Se Cathedral)", "type": "Heritage",
             "lat": 15.5009, "lon": 73.9116, "cultural_weight": 95, "tag": "popular", "price": 1500,
             "crowd_base": 45, "weekend_bump": 15, "desc": "UNESCO-listed 16th-century churches - the historic core of Portuguese Goa."},
            {"id": "fort_aguada", "name": "Fort Aguada", "type": "Heritage", "lat": 15.4919, "lon": 73.7736,
             "cultural_weight": 70, "tag": "popular", "price": 2000, "crowd_base": 40, "weekend_bump": 12,
             "desc": "A 17th-century Portuguese fort overlooking the Arabian Sea."},
        ],
    },

    # -------------------------------------------------------------- KERALA
    "kerala": {
        "name": "Kerala", "region": "South India", "aliases": ["kerala"],
        "capital_coords": (8.5241, 76.9366),
        "monsoon_months": [6, 7, 8], "best_months": [10, 11, 12, 1, 2, 3], "shoulder_months": [9],
        "culture_note": (
            "Kerala's identity is shaped by its backwaters, Ayurvedic medicine "
            "tradition, and classical arts like Kathakali and Theyyam - a state "
            "where nature and living ritual are closely intertwined."
        ),
        "places": [
            {"id": "munnar", "name": "Munnar", "type": "Hill Station", "lat": 10.0889, "lon": 77.0595,
             "cultural_weight": 35, "tag": "popular", "price": 4200, "crowd_base": 55, "weekend_bump": 20,
             "desc": "Rolling tea plantations and misty hills in the Western Ghats."},
            {"id": "wayanad", "name": "Wayanad", "type": "Nature", "lat": 11.6854, "lon": 76.1320,
             "cultural_weight": 40, "tag": "hidden-gem", "price": 3600, "crowd_base": 30, "weekend_bump": 10,
             "desc": "Wildlife sanctuaries and a quieter, greener alternative to Munnar."},
            {"id": "alleppey", "name": "Alleppey (Alappuzha)", "type": "Backwaters", "lat": 9.4981, "lon": 76.3388,
             "cultural_weight": 45, "tag": "popular", "price": 5200, "crowd_base": 48, "weekend_bump": 15,
             "desc": "Houseboat cruises through Kerala's famous backwater canals."},
            {"id": "varkala", "name": "Varkala", "type": "Beach", "lat": 8.7379, "lon": 76.7163,
             "cultural_weight": 35, "tag": "hidden-gem", "price": 2800, "crowd_base": 33, "weekend_bump": 18,
             "desc": "Red cliffside beach town with cafes overlooking the Arabian Sea."},
            {"id": "kovalam", "name": "Kovalam", "type": "Beach", "lat": 8.4004, "lon": 76.9787,
             "cultural_weight": 25, "tag": "caution", "price": 3900, "crowd_base": 50, "weekend_bump": 20,
             "desc": "A well-known beach near the capital, popular but touristy.",
             "safety_note": "Traveler reports of persistent touts near the main beach - stick to marked zones."},
            {"id": "bekal", "name": "Bekal", "type": "Heritage/Beach", "lat": 12.3958, "lon": 75.0329,
             "cultural_weight": 55, "tag": "hidden-gem", "price": 2600, "crowd_base": 22, "weekend_bump": 8,
             "desc": "A massive coastal fort with an uncrowded beach, in Kerala's far north."},
        ],
    },

    # ----------------------------------------------------------- RAJASTHAN
    "rajasthan": {
        "name": "Rajasthan", "region": "North India", "aliases": ["rajasthan"],
        "capital_coords": (26.9124, 75.7873),
        "monsoon_months": [7, 8], "best_months": [10, 11, 12, 1, 2, 3], "shoulder_months": [9],
        "culture_note": (
            "The land of Rajput kingdoms - forts, palaces and desert culture "
            "shape nearly every destination here. Summers (Apr-Jun) are "
            "extremely harsh, which is why the cool season draws almost all tourism."
        ),
        "places": [
            {"id": "jaipur", "name": "Jaipur", "type": "Heritage", "lat": 26.9124, "lon": 75.7873,
             "cultural_weight": 90, "tag": "popular", "price": 3200, "crowd_base": 55, "weekend_bump": 18,
             "desc": "The 'Pink City' - Amer Fort, City Palace and Hawa Mahal."},
            {"id": "udaipur", "name": "Udaipur", "type": "Heritage", "lat": 24.5854, "lon": 73.7125,
             "cultural_weight": 92, "tag": "popular", "price": 4000, "crowd_base": 48, "weekend_bump": 16,
             "desc": "The 'City of Lakes' - romantic palaces reflected in Lake Pichola."},
            {"id": "jodhpur", "name": "Jodhpur", "type": "Heritage", "lat": 26.2389, "lon": 73.0243,
             "cultural_weight": 88, "tag": "popular", "price": 3000, "crowd_base": 40, "weekend_bump": 14,
             "desc": "The 'Blue City' beneath the imposing Mehrangarh Fort."},
            {"id": "jaisalmer", "name": "Jaisalmer", "type": "Heritage/Desert", "lat": 26.9157, "lon": 70.9083,
             "cultural_weight": 93, "tag": "hidden-gem", "price": 2800, "crowd_base": 30, "weekend_bump": 10,
             "desc": "A living sandstone fort city on the edge of the Thar Desert."},
            {"id": "pushkar", "name": "Pushkar", "type": "Religious", "lat": 26.4899, "lon": 74.5511,
             "cultural_weight": 90, "tag": "hidden-gem", "price": 1800, "crowd_base": 35, "weekend_bump": 12,
             "desc": "A holy lake town; the Pushkar Camel Fair (Oct/Nov) draws huge crowds.",
             "festival_months": [11]},
        ],
    },

    # ------------------------------------------------------------ HIMACHAL
    "himachal": {
        "name": "Himachal Pradesh", "region": "North India", "aliases": ["himachal", "himachal pradesh"],
        "capital_coords": (31.1048, 77.1734),
        "monsoon_months": [7, 8], "best_months": [3, 4, 5, 9, 10, 11], "shoulder_months": [6],
        "culture_note": (
            "A Himalayan state where Hindu and Tibetan Buddhist traditions "
            "meet - Dharamshala is the seat of the Dalai Lama in exile, while "
            "remote valleys like Spiti preserve centuries-old monastery life."
        ),
        "places": [
            {"id": "manali", "name": "Manali", "type": "Hill Station/Adventure", "lat": 32.2432, "lon": 77.1892,
             "cultural_weight": 35, "tag": "popular", "price": 3200, "crowd_base": 50, "weekend_bump": 20,
             "desc": "Base for trekking and mountain-pass road trips in the Kullu valley."},
            {"id": "shimla", "name": "Shimla", "type": "Hill Station", "lat": 31.1048, "lon": 77.1734,
             "cultural_weight": 50, "tag": "popular", "price": 3000, "crowd_base": 55, "weekend_bump": 22,
             "desc": "The old British colonial hill capital, still lined with heritage architecture."},
            {"id": "dharamshala", "name": "Dharamshala / McLeod Ganj", "type": "Cultural/Religious",
             "lat": 32.2190, "lon": 76.3234, "cultural_weight": 80, "tag": "hidden-gem", "price": 2200,
             "crowd_base": 30, "weekend_bump": 10, "desc": "Home to the Tibetan government-in-exile and many monasteries."},
            {"id": "spiti", "name": "Spiti Valley", "type": "Nature/Cultural", "lat": 32.2465, "lon": 78.0349,
             "cultural_weight": 65, "tag": "caution", "price": 2500, "crowd_base": 15, "weekend_bump": 5,
             "desc": "A high-altitude cold desert valley with centuries-old Buddhist monasteries.",
             "safety_note": "Mountain passes are only open roughly May-Oct; check road status before travel."},
        ],
    },

    # ---------------------------------------------------------- TAMIL NADU
    "tamilnadu": {
        "name": "Tamil Nadu", "region": "South India", "aliases": ["tamil nadu", "tamilnadu"],
        "capital_coords": (13.0827, 80.2707),
        "monsoon_months": [10, 11], "best_months": [12, 1, 2, 3], "shoulder_months": [11],
        "culture_note": (
            "Home to one of the world's oldest living classical traditions - "
            "Tamil temple architecture, Bharatanatyam dance, and Dravidian "
            "heritage sites continuously in religious use for over a thousand years."
        ),
        "places": [
            {"id": "madurai", "name": "Madurai (Meenakshi Temple)", "type": "Religious", "lat": 9.9252, "lon": 78.1198,
             "cultural_weight": 97, "tag": "popular", "price": 1800, "crowd_base": 55, "weekend_bump": 15,
             "desc": "One of India's most significant living temple complexes."},
            {"id": "mahabalipuram", "name": "Mahabalipuram", "type": "Heritage", "lat": 12.6269, "lon": 80.1927,
             "cultural_weight": 92, "tag": "popular", "price": 2200, "crowd_base": 45, "weekend_bump": 18,
             "desc": "UNESCO shore temples and rock-cut monuments from the 7th century."},
            {"id": "ooty", "name": "Ooty", "type": "Hill Station", "lat": 11.4064, "lon": 76.6932,
             "cultural_weight": 30, "tag": "popular", "price": 2800, "crowd_base": 50, "weekend_bump": 20,
             "desc": "Tea-garden hill station in the Nilgiris, popular for the toy train."},
            {"id": "kodaikanal", "name": "Kodaikanal", "type": "Hill Station", "lat": 10.2381, "lon": 77.4892,
             "cultural_weight": 25, "tag": "hidden-gem", "price": 2600, "crowd_base": 32, "weekend_bump": 14,
             "desc": "A quieter hill station than Ooty, built around a star-shaped lake."},
        ],
    },

    # ---------------------------------------------------------- KARNATAKA
    "karnataka": {
        "name": "Karnataka", "region": "South India", "aliases": ["karnataka"],
        "capital_coords": (12.9716, 77.5946),
        "monsoon_months": [6, 7, 8, 9], "best_months": [10, 11, 12, 1, 2], "shoulder_months": [3],
        "culture_note": (
            "Ranges from the Vijayanagara Empire ruins at Hampi to the "
            "coffee-growing hill culture of Coorg - one of the most varied "
            "cultural footprints of any Indian state."
        ),
        "places": [
            {"id": "hampi", "name": "Hampi", "type": "Heritage", "lat": 15.3350, "lon": 76.4600,
             "cultural_weight": 97, "tag": "hidden-gem", "price": 1600, "crowd_base": 35, "weekend_bump": 12,
             "desc": "Sprawling UNESCO ruins of the 14th-century Vijayanagara Empire capital."},
            {"id": "mysore", "name": "Mysore", "type": "Heritage", "lat": 12.2958, "lon": 76.6394,
             "cultural_weight": 90, "tag": "popular", "price": 2400, "crowd_base": 45, "weekend_bump": 15,
             "desc": "The Mysore Palace and the famous Dasara festival celebrations.", "festival_months": [10]},
            {"id": "coorg", "name": "Coorg (Kodagu)", "type": "Nature", "lat": 12.3375, "lon": 75.8069,
             "cultural_weight": 35, "tag": "popular", "price": 3200, "crowd_base": 42, "weekend_bump": 18,
             "desc": "Misty coffee plantations and waterfalls in the Western Ghats."},
            {"id": "gokarna", "name": "Gokarna", "type": "Beach/Religious", "lat": 14.5479, "lon": 74.3188,
             "cultural_weight": 55, "tag": "hidden-gem", "price": 1900, "crowd_base": 28, "weekend_bump": 10,
             "desc": "A temple town with quiet beaches, an alternative to Goa's crowds."},
        ],
    },

    # -------------------------------------------------------- MAHARASHTRA
    "maharashtra": {
        "name": "Maharashtra", "region": "West India", "aliases": ["maharashtra"],
        "capital_coords": (19.0760, 72.8777),
        "monsoon_months": [6, 7, 8, 9], "best_months": [10, 11, 12, 1, 2], "shoulder_months": [3],
        "culture_note": (
            "From the rock-cut Buddhist, Hindu and Jain caves at Ellora to "
            "colonial-era hill stations, Maharashtra spans over a thousand "
            "years of religious and architectural history."
        ),
        "places": [
            {"id": "ellora", "name": "Ellora Caves", "type": "Heritage", "lat": 20.0269, "lon": 75.1780,
             "cultural_weight": 98, "tag": "hidden-gem", "price": 1800, "crowd_base": 30, "weekend_bump": 10,
             "desc": "34 rock-cut monasteries and temples spanning three religions."},
            {"id": "lonavala", "name": "Lonavala", "type": "Nature", "lat": 18.7537, "lon": 73.4068,
             "cultural_weight": 20, "tag": "popular", "price": 2600, "crowd_base": 55, "weekend_bump": 25,
             "desc": "Waterfalls and hill viewpoints - best just after the monsoon starts."},
            {"id": "mahabaleshwar", "name": "Mahabaleshwar", "type": "Hill Station", "lat": 17.9307, "lon": 73.6477,
             "cultural_weight": 25, "tag": "popular", "price": 2800, "crowd_base": 48, "weekend_bump": 20,
             "desc": "Strawberry farms and viewpoints in the Sahyadri hills."},
            {"id": "alibaug", "name": "Alibaug", "type": "Beach", "lat": 18.6414, "lon": 72.8722,
             "cultural_weight": 20, "tag": "popular", "price": 3400, "crowd_base": 50, "weekend_bump": 22,
             "desc": "A relaxed beach getaway a short ferry ride from Mumbai."},
            {"id": "mumbai", "name": "Mumbai (Gateway of India)", "type": "Cultural", "lat": 18.9220, "lon": 72.8347,
             "cultural_weight": 65, "tag": "popular", "price": 3800, "crowd_base": 60, "weekend_bump": 15,
             "desc": "India's financial capital - colonial architecture, Marine Drive and Bollywood."},
        ],
    },

    # ----------------------------------------------------------- LADAKH (UT)
    "ladakh": {
        "name": "Ladakh", "region": "North India (UT)", "aliases": ["ladakh"],
        "capital_coords": (34.1526, 77.5771),
        "monsoon_months": [], "best_months": [5, 6, 7, 8, 9], "shoulder_months": [4, 10],
        "culture_note": (
            "A high-altitude Tibetan Buddhist culture zone - Leh's monasteries "
            "and stupas are still active centers of worship. Roads to most of "
            "the region are only open roughly May-October."
        ),
        "places": [
            {"id": "leh", "name": "Leh", "type": "Cultural", "lat": 34.1526, "lon": 77.5771,
             "cultural_weight": 85, "tag": "popular", "price": 2400, "crowd_base": 40, "weekend_bump": 10,
             "desc": "Ancient palace and monastery town at 3,500m, gateway to Ladakh.",
             "safety_note": "Altitude sickness is common - plan 1-2 acclimatization days on arrival."},
            {"id": "pangong", "name": "Pangong Tso", "type": "Nature", "lat": 33.7460, "lon": 78.6621,
             "cultural_weight": 40, "tag": "hidden-gem", "price": 2000, "crowd_base": 25, "weekend_bump": 8,
             "desc": "A vast high-altitude lake that changes color through the day."},
            {"id": "nubra", "name": "Nubra Valley", "type": "Nature/Cultural", "lat": 34.6801, "lon": 77.6108,
             "cultural_weight": 55, "tag": "hidden-gem", "price": 2000, "crowd_base": 22, "weekend_bump": 6,
             "desc": "Cold desert valley with Bactrian camels and remote monasteries."},
        ],
    },

    # -------------------------------------------------------- WEST BENGAL
    "westbengal": {
        "name": "West Bengal", "region": "East India", "aliases": ["west bengal", "bengal"],
        "capital_coords": (22.5726, 88.3639),
        "monsoon_months": [6, 7, 8, 9], "best_months": [10, 11, 2, 3], "shoulder_months": [1],
        "culture_note": (
            "Kolkata's Durga Puja is one of the largest living festival "
            "traditions in the world; Darjeeling adds a distinct colonial-era "
            "tea culture in the hills to the north."
        ),
        "places": [
            {"id": "darjeeling", "name": "Darjeeling", "type": "Hill Station", "lat": 27.0410, "lon": 88.2663,
             "cultural_weight": 60, "tag": "popular", "price": 2600, "crowd_base": 45, "weekend_bump": 16,
             "desc": "Tea estates and Himalayan views from a former British hill station."},
            {"id": "kolkata", "name": "Kolkata", "type": "Cultural", "lat": 22.5726, "lon": 88.3639,
             "cultural_weight": 85, "tag": "popular", "price": 2400, "crowd_base": 50, "weekend_bump": 12,
             "desc": "Colonial architecture, literary history, and the Durga Puja festival.",
             "festival_months": [10]},
            {"id": "sundarbans", "name": "Sundarbans", "type": "Nature", "lat": 21.9497, "lon": 88.4212,
             "cultural_weight": 30, "tag": "hidden-gem", "price": 2800, "crowd_base": 20, "weekend_bump": 8,
             "desc": "The world's largest mangrove forest, home to the Bengal tiger.",
             "safety_note": "Only visit via licensed forest-department boat tours."},
        ],
    },

    # ------------------------------------------------------ ANDHRA PRADESH
    "andhrapradesh": {
        "name": "Andhra Pradesh", "region": "South India", "aliases": ["andhra pradesh", "andhra"],
        "capital_coords": (16.5062, 80.6480),
        "monsoon_months": [6, 7, 8, 9], "best_months": [10, 11, 12, 1, 2], "shoulder_months": [3],
        "culture_note": (
            "Home to one of Hinduism's richest and busiest pilgrimage sites at "
            "Tirupati, alongside a long Telugu coastal and temple tradition."
        ),
        "places": [
            {"id": "tirupati", "name": "Tirupati (Sri Venkateswara Temple)", "type": "Religious",
             "lat": 13.6288, "lon": 79.4192, "cultural_weight": 97, "tag": "popular", "price": 2000,
             "crowd_base": 70, "weekend_bump": 15, "desc": "One of the world's most-visited pilgrimage sites."},
            {"id": "visakhapatnam", "name": "Visakhapatnam", "type": "Beach", "lat": 17.6868, "lon": 83.2185,
             "cultural_weight": 30, "tag": "popular", "price": 2600, "crowd_base": 40, "weekend_bump": 15,
             "desc": "A laid-back port city with beaches and naval history."},
            {"id": "araku", "name": "Araku Valley", "type": "Hill Station", "lat": 18.3273, "lon": 82.8770,
             "cultural_weight": 35, "tag": "hidden-gem", "price": 2000, "crowd_base": 22, "weekend_bump": 8,
             "desc": "Coffee-growing tribal hill valley reached by a scenic train line."},
        ],
    },

    # ---------------------------------------------------- ARUNACHAL PRADESH
    "arunachalpradesh": {
        "name": "Arunachal Pradesh", "region": "Northeast India", "aliases": ["arunachal pradesh", "arunachal"],
        "capital_coords": (27.0844, 93.6053),
        "monsoon_months": [6, 7, 8], "best_months": [10, 11, 3, 4], "shoulder_months": [9],
        "culture_note": (
            "India's easternmost Himalayan state - remote Monpa and Apatani "
            "tribal culture, and one of the largest Buddhist monasteries outside Tibet at Tawang."
        ),
        "places": [
            {"id": "tawang", "name": "Tawang Monastery", "type": "Cultural/Religious", "lat": 27.5859, "lon": 91.8594,
             "cultural_weight": 85, "tag": "hidden-gem", "price": 2200, "crowd_base": 20, "weekend_bump": 6,
             "desc": "The largest Buddhist monastery in India, in a dramatic high-Himalayan setting.",
             "safety_note": "Requires an Inner Line Permit for Indian nationals; roads can close in winter."},
            {"id": "ziro", "name": "Ziro Valley", "type": "Cultural/Nature", "lat": 27.5936, "lon": 93.8322,
             "cultural_weight": 55, "tag": "hidden-gem", "price": 1800, "crowd_base": 15, "weekend_bump": 5,
             "desc": "Home to the Apatani tribe's distinctive wet-rice farming culture."},
        ],
    },

    # ------------------------------------------------------------- ASSAM
    "assam": {
        "name": "Assam", "region": "Northeast India", "aliases": ["assam"],
        "capital_coords": (26.1445, 91.7362),
        "monsoon_months": [6, 7, 8, 9], "best_months": [10, 11, 12, 1, 2, 3], "shoulder_months": [4],
        "culture_note": (
            "Gateway to the Northeast - Kamakhya Temple is one of Hinduism's "
            "most important Shakti Peethas, and Kaziranga protects the world's "
            "largest population of one-horned rhinos."
        ),
        "places": [
            {"id": "kaziranga", "name": "Kaziranga National Park", "type": "Nature", "lat": 26.5775, "lon": 93.1714,
             "cultural_weight": 25, "tag": "popular", "price": 2600, "crowd_base": 35, "weekend_bump": 12,
             "desc": "UNESCO World Heritage park, home to the one-horned rhinoceros."},
            {"id": "kamakhya", "name": "Kamakhya Temple, Guwahati", "type": "Religious", "lat": 26.1665, "lon": 91.7036,
             "cultural_weight": 90, "tag": "popular", "price": 2000, "crowd_base": 50, "weekend_bump": 14,
             "desc": "An ancient Shakti Peetha temple overlooking the Brahmaputra."},
            {"id": "majuli", "name": "Majuli Island", "type": "Cultural/Nature", "lat": 26.9520, "lon": 94.1697,
             "cultural_weight": 60, "tag": "hidden-gem", "price": 1600, "crowd_base": 15, "weekend_bump": 5,
             "desc": "The world's largest river island, and a center of neo-Vaishnavite culture."},
        ],
    },

    # ------------------------------------------------------------- BIHAR
    "bihar": {
        "name": "Bihar", "region": "East India", "aliases": ["bihar"],
        "capital_coords": (25.5941, 85.1376),
        "monsoon_months": [6, 7, 8, 9], "best_months": [10, 11, 12, 1, 2], "shoulder_months": [3],
        "culture_note": (
            "The cradle of Buddhism - the Buddha attained enlightenment at "
            "Bodh Gaya, and Nalanda hosted one of the world's first great "
            "residential universities over 1,500 years ago."
        ),
        "places": [
            {"id": "bodhgaya", "name": "Bodh Gaya (Mahabodhi Temple)", "type": "Religious", "lat": 24.6961, "lon": 84.9911,
             "cultural_weight": 98, "tag": "popular", "price": 1600, "crowd_base": 45, "weekend_bump": 10,
             "desc": "UNESCO site where the Buddha is believed to have attained enlightenment."},
            {"id": "nalanda", "name": "Nalanda", "type": "Heritage", "lat": 25.1358, "lon": 85.4436,
             "cultural_weight": 95, "tag": "hidden-gem", "price": 1400, "crowd_base": 25, "weekend_bump": 8,
             "desc": "Ruins of an ancient Buddhist monastic university, one of the world's first."},
            {"id": "rajgir", "name": "Rajgir", "type": "Heritage/Religious", "lat": 25.0285, "lon": 85.4212,
             "cultural_weight": 70, "tag": "hidden-gem", "price": 1500, "crowd_base": 20, "weekend_bump": 8,
             "desc": "An ancient capital sacred to both Buddhism and Jainism, ringed by hills."},
            {"id": "patna", "name": "Patna", "type": "Cultural", "lat": 25.5941, "lon": 85.1376,
             "cultural_weight": 55, "tag": "popular", "price": 1800, "crowd_base": 40, "weekend_bump": 10,
             "desc": "One of the world's oldest continuously inhabited cities, on the Ganges."},
        ],
    },

    # -------------------------------------------------------- CHHATTISGARH
    "chhattisgarh": {
        "name": "Chhattisgarh", "region": "Central India", "aliases": ["chhattisgarh", "chattisgarh"],
        "capital_coords": (21.2514, 81.6296),
        "monsoon_months": [6, 7, 8, 9], "best_months": [11, 12, 1, 2], "shoulder_months": [10],
        "culture_note": (
            "A heavily forested, tribal-heritage state - home to Gond and "
            "Bastar tribal art traditions and some of India's tallest waterfalls."
        ),
        "places": [
            {"id": "chitrakote", "name": "Chitrakote Falls", "type": "Nature", "lat": 19.1868, "lon": 81.6693,
             "cultural_weight": 20, "tag": "hidden-gem", "price": 1400, "crowd_base": 15, "weekend_bump": 6,
             "desc": "India's widest waterfall, often called the 'Niagara of India'."},
            {"id": "bastar", "name": "Bastar (Jagdalpur)", "type": "Tribal/Cultural", "lat": 19.0748, "lon": 82.0198,
             "cultural_weight": 60, "tag": "hidden-gem", "price": 1500, "crowd_base": 12, "weekend_bump": 4,
             "desc": "Deeply tribal region known for its Dussehra festival and Gond art."},
        ],
    },

    # -------------------------------------------------------------- GUJARAT
    "gujarat": {
        "name": "Gujarat", "region": "West India", "aliases": ["gujarat"],
        "capital_coords": (23.2156, 72.6369),
        "monsoon_months": [6, 7, 8, 9], "best_months": [11, 12, 1, 2, 3], "shoulder_months": [10],
        "culture_note": (
            "From the white salt desert of the Rann of Kutch to Somnath, one "
            "of Hinduism's twelve Jyotirlinga shrines, and Gandhi's Sabarmati Ashram."
        ),
        "places": [
            {"id": "rannofkutch", "name": "Rann of Kutch", "type": "Nature/Cultural", "lat": 23.8398, "lon": 69.8608,
             "cultural_weight": 60, "tag": "popular", "price": 2400, "crowd_base": 40, "weekend_bump": 20,
             "desc": "A vast white salt desert, famous for the winter Rann Utsav festival.",
             "festival_months": [12]},
            {"id": "somnath", "name": "Somnath Temple", "type": "Religious", "lat": 20.8880, "lon": 70.4012,
             "cultural_weight": 95, "tag": "popular", "price": 1800, "crowd_base": 45, "weekend_bump": 12,
             "desc": "One of the twelve Jyotirlinga shrines, rebuilt many times through history."},
            {"id": "gir", "name": "Gir National Park", "type": "Nature", "lat": 21.1290, "lon": 70.7935,
             "cultural_weight": 30, "tag": "hidden-gem", "price": 2600, "crowd_base": 30, "weekend_bump": 12,
             "desc": "The only place on Earth with wild Asiatic lions."},
            {"id": "ahmedabad", "name": "Ahmedabad (Sabarmati Ashram)", "type": "Heritage", "lat": 23.0225, "lon": 72.5714,
             "cultural_weight": 80, "tag": "popular", "price": 2000, "crowd_base": 40, "weekend_bump": 10,
             "desc": "Gandhi's ashram and a UNESCO-listed old city of stepwells and havelis."},
        ],
    },

    # -------------------------------------------------------------- HARYANA
    "haryana": {
        "name": "Haryana", "region": "North India", "aliases": ["haryana"],
        "capital_coords": (29.9695, 76.8783),
        "monsoon_months": [7, 8], "best_months": [10, 11, 2, 3], "shoulder_months": [9],
        "culture_note": (
            "Best known as the sacred battlefield of the Bhagavad Gita at "
            "Kurukshetra, alongside cool hill retreats close to Chandigarh."
        ),
        "places": [
            {"id": "kurukshetra", "name": "Kurukshetra", "type": "Religious", "lat": 29.9695, "lon": 76.8783,
             "cultural_weight": 90, "tag": "popular", "price": 1600, "crowd_base": 35, "weekend_bump": 10,
             "desc": "The legendary battlefield of the Mahabharata and site of the Bhagavad Gita."},
            {"id": "morni", "name": "Morni Hills", "type": "Hill Station", "lat": 30.6667, "lon": 77.0333,
             "cultural_weight": 15, "tag": "hidden-gem", "price": 2000, "crowd_base": 20, "weekend_bump": 15,
             "desc": "Haryana's only hill station, a quiet Shivalik retreat near Chandigarh."},
        ],
    },

    # ------------------------------------------------------------ JHARKHAND
    "jharkhand": {
        "name": "Jharkhand", "region": "East India", "aliases": ["jharkhand"],
        "capital_coords": (23.3441, 85.3096),
        "monsoon_months": [6, 7, 8, 9], "best_months": [10, 11, 2, 3], "shoulder_months": [1],
        "culture_note": (
            "A mineral-rich, heavily tribal state - home to the Baidyanath "
            "Jyotirlinga at Deoghar and cool forested plateau hill stations."
        ),
        "places": [
            {"id": "deoghar", "name": "Deoghar (Baidyanath Temple)", "type": "Religious", "lat": 24.4823, "lon": 86.6961,
             "cultural_weight": 90, "tag": "popular", "price": 1500, "crowd_base": 45, "weekend_bump": 12,
             "desc": "One of the twelve Jyotirlinga shrines, a major Shiva pilgrimage site."},
            {"id": "netarhat", "name": "Netarhat", "type": "Hill Station", "lat": 23.4700, "lon": 84.2667,
             "cultural_weight": 20, "tag": "hidden-gem", "price": 1600, "crowd_base": 15, "weekend_bump": 6,
             "desc": "The 'Queen of Chotanagpur' plateau, known for sunrise/sunset points."},
            {"id": "ranchi", "name": "Ranchi", "type": "Nature/Cultural", "lat": 23.3441, "lon": 85.3096,
             "cultural_weight": 30, "tag": "popular", "price": 1800, "crowd_base": 30, "weekend_bump": 10,
             "desc": "The 'City of Waterfalls', gateway to Jharkhand's tribal heartland."},
        ],
    },

    # -------------------------------------------------------- MADHYA PRADESH
    "madhyapradesh": {
        "name": "Madhya Pradesh", "region": "Central India", "aliases": ["madhya pradesh"],
        "capital_coords": (23.2599, 77.4126),
        "monsoon_months": [6, 7, 8, 9], "best_months": [10, 11, 12, 1, 2, 3], "shoulder_months": [4],
        "culture_note": (
            "The 'Heart of India' - UNESCO temple art at Khajuraho, one of "
            "Buddhism's oldest surviving monuments at Sanchi, and some of the "
            "country's best tiger reserves."
        ),
        "places": [
            {"id": "khajuraho", "name": "Khajuraho", "type": "Heritage", "lat": 24.8318, "lon": 79.9199,
             "cultural_weight": 96, "tag": "hidden-gem", "price": 2200, "crowd_base": 30, "weekend_bump": 10,
             "desc": "UNESCO-listed temples famous for their intricate medieval sculpture."},
            {"id": "sanchi", "name": "Sanchi Stupa", "type": "Heritage/Religious", "lat": 23.4793, "lon": 77.7398,
             "cultural_weight": 95, "tag": "hidden-gem", "price": 1600, "crowd_base": 20, "weekend_bump": 8,
             "desc": "One of the oldest Buddhist stone structures in India, commissioned by Ashoka."},
            {"id": "bandhavgarh", "name": "Bandhavgarh National Park", "type": "Nature", "lat": 23.7143, "lon": 80.9865,
             "cultural_weight": 20, "tag": "popular", "price": 3200, "crowd_base": 35, "weekend_bump": 14,
             "desc": "One of India's best parks for spotting wild tigers."},
            {"id": "ujjain", "name": "Ujjain (Mahakaleshwar)", "type": "Religious", "lat": 23.1765, "lon": 75.7885,
             "cultural_weight": 92, "tag": "popular", "price": 1600, "crowd_base": 45, "weekend_bump": 12,
             "desc": "One of Hinduism's seven sacred cities, home to a Jyotirlinga shrine."},
        ],
    },

    # ------------------------------------------------------------- MANIPUR
    "manipur": {
        "name": "Manipur", "region": "Northeast India", "aliases": ["manipur"],
        "capital_coords": (24.8170, 93.9368),
        "monsoon_months": [6, 7, 8], "best_months": [10, 11, 2, 3], "shoulder_months": [12],
        "culture_note": (
            "Known for the extraordinary floating islands of Loktak Lake and "
            "the classical Manipuri dance tradition."
        ),
        "places": [
            {"id": "loktak", "name": "Loktak Lake", "type": "Nature", "lat": 24.5500, "lon": 93.7833,
             "cultural_weight": 45, "tag": "hidden-gem", "price": 1400, "crowd_base": 15, "weekend_bump": 5,
             "desc": "The largest freshwater lake in Northeast India, famous for floating phumdi islands."},
            {"id": "imphal", "name": "Imphal (Kangla Fort)", "type": "Cultural", "lat": 24.8170, "lon": 93.9368,
             "cultural_weight": 60, "tag": "hidden-gem", "price": 1600, "crowd_base": 25, "weekend_bump": 6,
             "desc": "The historic seat of Manipur's kings and home to classical Manipuri dance."},
        ],
    },

    # ----------------------------------------------------------- MEGHALAYA
    "meghalaya": {
        "name": "Meghalaya", "region": "Northeast India", "aliases": ["meghalaya"],
        "capital_coords": (25.5788, 91.8933),
        "monsoon_months": [5, 6, 7, 8, 9], "best_months": [10, 11, 12, 3, 4], "shoulder_months": [2],
        "culture_note": (
            "The 'Abode of Clouds' - one of the wettest places on Earth, home "
            "to living root bridges grown by the Khasi and Jaintia tribes over generations."
        ),
        "places": [
            {"id": "cherrapunji", "name": "Cherrapunji (Sohra)", "type": "Nature", "lat": 25.2702, "lon": 91.7323,
             "cultural_weight": 40, "tag": "popular", "price": 1800, "crowd_base": 35, "weekend_bump": 14,
             "desc": "Famous for living root bridges and among the wettest places on the planet."},
            {"id": "shillong", "name": "Shillong", "type": "Cultural/Hill Station", "lat": 25.5788, "lon": 91.8933,
             "cultural_weight": 45, "tag": "popular", "price": 2000, "crowd_base": 40, "weekend_bump": 16,
             "desc": "The 'Scotland of the East', with a distinct Khasi hill culture."},
            {"id": "mawlynnong", "name": "Mawlynnong", "type": "Nature/Cultural", "lat": 25.2010, "lon": 91.9186,
             "cultural_weight": 35, "tag": "hidden-gem", "price": 1600, "crowd_base": 18, "weekend_bump": 8,
             "desc": "Often cited as one of Asia's cleanest villages, with its own root bridge."},
        ],
    },

    # ------------------------------------------------------------ MIZORAM
    "mizoram": {
        "name": "Mizoram", "region": "Northeast India", "aliases": ["mizoram"],
        "capital_coords": (23.7271, 92.7176),
        "monsoon_months": [6, 7, 8], "best_months": [11, 12, 1, 2, 3], "shoulder_months": [10],
        "culture_note": (
            "A rolling-hills state with a distinct Mizo Christian tribal "
            "culture, bamboo crafts, and some of the friendliest small-town warmth in India."
        ),
        "places": [
            {"id": "aizawl", "name": "Aizawl", "type": "Cultural", "lat": 23.7271, "lon": 92.7176,
             "cultural_weight": 50, "tag": "hidden-gem", "price": 1800, "crowd_base": 20, "weekend_bump": 8,
             "desc": "A hillside capital built along a ridge, with a strong Mizo cultural identity."},
        ],
    },

    # ------------------------------------------------------------ NAGALAND
    "nagaland": {
        "name": "Nagaland", "region": "Northeast India", "aliases": ["nagaland"],
        "capital_coords": (25.6751, 94.1086),
        "monsoon_months": [6, 7, 8], "best_months": [10, 11, 12], "shoulder_months": [3],
        "culture_note": (
            "Home to 16 major Naga tribes, each with distinct textiles and "
            "traditions - most visibly celebrated together at December's Hornbill Festival."
        ),
        "places": [
            {"id": "kohima", "name": "Kohima", "type": "Cultural", "lat": 25.6751, "lon": 94.1086,
             "cultural_weight": 75, "tag": "popular", "price": 2000, "crowd_base": 40, "weekend_bump": 10,
             "desc": "Hosts the famous Hornbill Festival celebrating all Naga tribes.",
             "festival_months": [12]},
            {"id": "dzukou", "name": "Dzukou Valley", "type": "Nature", "lat": 25.5667, "lon": 94.0333,
             "cultural_weight": 25, "tag": "hidden-gem", "price": 1500, "crowd_base": 15, "weekend_bump": 6,
             "desc": "A pristine trekking valley famous for seasonal wildflower blooms."},
        ],
    },

    # -------------------------------------------------------------- ODISHA
    "odisha": {
        "name": "Odisha", "region": "East India", "aliases": ["odisha", "orissa"],
        "capital_coords": (20.2961, 85.8245),
        "monsoon_months": [6, 7, 8, 9], "best_months": [10, 11, 12, 1, 2], "shoulder_months": [3],
        "culture_note": (
            "One of India's great living temple cultures - Puri's Jagannath "
            "Temple and Rath Yatra, and the intricately carved 13th-century Sun Temple at Konark."
        ),
        "places": [
            {"id": "puri", "name": "Puri (Jagannath Temple)", "type": "Religious", "lat": 19.8135, "lon": 85.8312,
             "cultural_weight": 97, "tag": "popular", "price": 1800, "crowd_base": 55, "weekend_bump": 15,
             "desc": "One of Hinduism's Char Dham sites; the Rath Yatra draws millions.",
             "festival_months": [7]},
            {"id": "konark", "name": "Konark Sun Temple", "type": "Heritage", "lat": 19.8876, "lon": 86.0945,
             "cultural_weight": 96, "tag": "popular", "price": 1600, "crowd_base": 40, "weekend_bump": 14,
             "desc": "A UNESCO 13th-century temple built in the shape of a colossal chariot."},
            {"id": "bhubaneswar", "name": "Bhubaneswar", "type": "Cultural/Heritage", "lat": 20.2961, "lon": 85.8245,
             "cultural_weight": 80, "tag": "hidden-gem", "price": 1600, "crowd_base": 30, "weekend_bump": 10,
             "desc": "The 'Temple City', dotted with hundreds of ancient Kalinga-style shrines."},
        ],
    },

    # -------------------------------------------------------------- PUNJAB
    "punjab": {
        "name": "Punjab", "region": "North India", "aliases": ["punjab"],
        "capital_coords": (31.6200, 74.8765),
        "monsoon_months": [7, 8], "best_months": [10, 11, 2, 3], "shoulder_months": [9],
        "culture_note": (
            "Home to Sikhism's holiest shrine, the Golden Temple - a living "
            "site of daily worship and one of the world's largest free community kitchens."
        ),
        "places": [
            {"id": "amritsar", "name": "Amritsar (Golden Temple)", "type": "Religious", "lat": 31.6200, "lon": 74.8765,
             "cultural_weight": 98, "tag": "popular", "price": 2000, "crowd_base": 55, "weekend_bump": 14,
             "desc": "Sikhism's holiest shrine, and its free community kitchen feeds 100,000+ daily."},
            {"id": "wagah", "name": "Wagah Border", "type": "Cultural", "lat": 31.6044, "lon": 74.5738,
             "cultural_weight": 50, "tag": "popular", "price": 1800, "crowd_base": 50, "weekend_bump": 18,
             "desc": "The daily flag-lowering ceremony at the India-Pakistan border."},
        ],
    },

    # -------------------------------------------------------------- SIKKIM
    "sikkim": {
        "name": "Sikkim", "region": "Northeast India", "aliases": ["sikkim"],
        "capital_coords": (27.3389, 88.6065),
        "monsoon_months": [6, 7, 8, 9], "best_months": [3, 4, 5, 10, 11], "shoulder_months": [12],
        "culture_note": (
            "A former Buddhist kingdom nestled below Kangchenjunga - Gangtok's "
            "monasteries and prayer flags reflect a still-living Himalayan Buddhist culture."
        ),
        "places": [
            {"id": "gangtok", "name": "Gangtok", "type": "Cultural/Hill Station", "lat": 27.3389, "lon": 88.6065,
             "cultural_weight": 60, "tag": "popular", "price": 2800, "crowd_base": 45, "weekend_bump": 14,
             "desc": "Sikkim's capital, ringed by monasteries with Kangchenjunga views."},
            {"id": "yumthang", "name": "Yumthang Valley", "type": "Nature", "lat": 27.8167, "lon": 88.6833,
             "cultural_weight": 20, "tag": "hidden-gem", "price": 2200, "crowd_base": 20, "weekend_bump": 8,
             "desc": "The 'Valley of Flowers of Sikkim', a high-altitude rhododendron sanctuary."},
            {"id": "nathula", "name": "Nathula Pass", "type": "Nature/Cultural", "lat": 27.3860, "lon": 88.8410,
             "cultural_weight": 35, "tag": "hidden-gem", "price": 2000, "crowd_base": 25, "weekend_bump": 10,
             "desc": "A historic Himalayan trade-route pass on the India-China border."},
        ],
    },

    # ----------------------------------------------------------- TELANGANA
    "telangana": {
        "name": "Telangana", "region": "South India", "aliases": ["telangana"],
        "capital_coords": (17.3850, 78.4867),
        "monsoon_months": [6, 7, 8, 9], "best_months": [10, 11, 12, 1, 2], "shoulder_months": [3],
        "culture_note": (
            "A crossroads of Deccan sultanate and Kakatiya-era Hindu heritage - "
            "Hyderabad's Charminar and the Warangal Fort both showcase centuries of layered history."
        ),
        "places": [
            {"id": "hyderabad", "name": "Hyderabad (Charminar)", "type": "Heritage", "lat": 17.3616, "lon": 78.4747,
             "cultural_weight": 88, "tag": "popular", "price": 2600, "crowd_base": 55, "weekend_bump": 15,
             "desc": "A 16th-century Deccan sultanate icon at the heart of the old city."},
            {"id": "warangal", "name": "Warangal Fort", "type": "Heritage", "lat": 17.9689, "lon": 79.5941,
             "cultural_weight": 85, "tag": "hidden-gem", "price": 1600, "crowd_base": 20, "weekend_bump": 8,
             "desc": "Ruins of the 13th-century Kakatiya dynasty capital."},
        ],
    },

    # ------------------------------------------------------------- TRIPURA
    "tripura": {
        "name": "Tripura", "region": "Northeast India", "aliases": ["tripura"],
        "capital_coords": (23.8315, 91.2868),
        "monsoon_months": [6, 7, 8, 9], "best_months": [10, 11, 2, 3], "shoulder_months": [1],
        "culture_note": (
            "A former princely state with palace architecture blending "
            "Mughal and European styles, and ancient rock-cut carvings at Unakoti."
        ),
        "places": [
            {"id": "agartala", "name": "Agartala (Ujjayanta Palace)", "type": "Heritage", "lat": 23.8315, "lon": 91.2868,
             "cultural_weight": 65, "tag": "hidden-gem", "price": 1600, "crowd_base": 25, "weekend_bump": 8,
             "desc": "The former royal palace of the Manikya dynasty, now a museum."},
            {"id": "unakoti", "name": "Unakoti", "type": "Heritage", "lat": 24.2667, "lon": 92.0333,
             "cultural_weight": 75, "tag": "hidden-gem", "price": 1400, "crowd_base": 12, "weekend_bump": 4,
             "desc": "Colossal rock-cut carvings of Hindu deities, dated to around the 7th-9th century."},
        ],
    },

    # -------------------------------------------------------- UTTAR PRADESH
    "uttarpradesh": {
        "name": "Uttar Pradesh", "region": "North India", "aliases": ["uttar pradesh"],
        "capital_coords": (26.8467, 80.9462),
        "monsoon_months": [6, 7, 8, 9], "best_months": [10, 11, 2, 3], "shoulder_months": [12, 1],
        "culture_note": (
            "Home to the Taj Mahal and Varanasi, one of the oldest continuously "
            "inhabited and most sacred cities in the world on the banks of the Ganges."
        ),
        "places": [
            {"id": "agra", "name": "Agra (Taj Mahal)", "type": "Heritage", "lat": 27.1751, "lon": 78.0421,
             "cultural_weight": 99, "tag": "popular", "price": 2600, "crowd_base": 70, "weekend_bump": 15,
             "desc": "The Taj Mahal - a UNESCO wonder and India's most iconic monument."},
            {"id": "varanasi", "name": "Varanasi", "type": "Religious", "lat": 25.3176, "lon": 82.9739,
             "cultural_weight": 98, "tag": "popular", "price": 1800, "crowd_base": 60, "weekend_bump": 12,
             "desc": "One of the world's oldest living cities, sacred to Hindus for millennia."},
            {"id": "lucknow", "name": "Lucknow", "type": "Heritage", "lat": 26.8467, "lon": 80.9462,
             "cultural_weight": 78, "tag": "hidden-gem", "price": 2000, "crowd_base": 35, "weekend_bump": 10,
             "desc": "The old Nawabi capital, famed for Awadhi cuisine and refined etiquette."},
            {"id": "mathura", "name": "Mathura-Vrindavan", "type": "Religious", "lat": 27.4924, "lon": 77.6737,
             "cultural_weight": 90, "tag": "popular", "price": 1600, "crowd_base": 50, "weekend_bump": 20,
             "desc": "The birthplace of Krishna, and site of famously joyous Holi celebrations.",
             "festival_months": [3]},
        ],
    },

    # ------------------------------------------------------------ UTTARAKHAND
    "uttarakhand": {
        "name": "Uttarakhand", "region": "North India", "aliases": ["uttarakhand", "uttaranchal"],
        "capital_coords": (30.3165, 78.0322),
        "monsoon_months": [7, 8], "best_months": [3, 4, 5, 9, 10, 11], "shoulder_months": [2],
        "culture_note": (
            "The 'Land of the Gods' - Haridwar and Rishikesh anchor Hindu "
            "pilgrimage on the Ganges, while Himalayan hill stations and the "
            "Valley of Flowers draw nature travelers."
        ),
        "places": [
            {"id": "rishikesh", "name": "Rishikesh", "type": "Religious/Adventure", "lat": 30.0869, "lon": 78.2676,
             "cultural_weight": 75, "tag": "popular", "price": 2000, "crowd_base": 50, "weekend_bump": 18,
             "desc": "The 'Yoga Capital of the World', on the banks of the Ganges."},
            {"id": "haridwar", "name": "Haridwar", "type": "Religious", "lat": 29.9457, "lon": 78.1642,
             "cultural_weight": 90, "tag": "popular", "price": 1800, "crowd_base": 55, "weekend_bump": 15,
             "desc": "One of Hinduism's seven holiest cities, host to the Kumbh Mela."},
            {"id": "nainital", "name": "Nainital", "type": "Hill Station", "lat": 29.3919, "lon": 79.4542,
             "cultural_weight": 30, "tag": "popular", "price": 2600, "crowd_base": 50, "weekend_bump": 22,
             "desc": "A colonial-era lake town in the Kumaon Himalayas."},
            {"id": "valleyofflowers", "name": "Valley of Flowers", "type": "Nature", "lat": 30.7280, "lon": 79.6050,
             "cultural_weight": 20, "tag": "hidden-gem", "price": 1600, "crowd_base": 15, "weekend_bump": 6,
             "desc": "A UNESCO alpine valley that bursts into wildflower bloom each monsoon.",
             "safety_note": "Only accessible roughly June-September; closed the rest of the year."},
        ],
    },

    # ============================== UNION TERRITORIES ==============================

    "delhi": {
        "name": "Delhi", "region": "North India (UT)", "aliases": ["delhi", "new delhi"],
        "capital_coords": (28.6139, 77.2090),
        "monsoon_months": [7, 8], "best_months": [10, 11, 2, 3], "shoulder_months": [12, 1],
        "culture_note": (
            "Seven historic cities layered into one - Mughal, Sultanate and "
            "British colonial capitals sit side by side across the modern metropolis."
        ),
        "places": [
            {"id": "redfort", "name": "Red Fort", "type": "Heritage", "lat": 28.6562, "lon": 77.2410,
             "cultural_weight": 95, "tag": "popular", "price": 2200, "crowd_base": 55, "weekend_bump": 15,
             "desc": "The Mughal Empire's red sandstone seat of power for over 200 years."},
            {"id": "qutubminar", "name": "Qutub Minar", "type": "Heritage", "lat": 28.5245, "lon": 77.1855,
             "cultural_weight": 92, "tag": "popular", "price": 2200, "crowd_base": 45, "weekend_bump": 14,
             "desc": "A UNESCO 73-metre minaret, the tallest brick minaret in the world."},
            {"id": "indiagate", "name": "India Gate", "type": "Cultural", "lat": 28.6129, "lon": 77.2295,
             "cultural_weight": 55, "tag": "popular", "price": 2400, "crowd_base": 60, "weekend_bump": 20,
             "desc": "A war memorial arch at the heart of Lutyens' colonial-era Delhi."},
        ],
    },

    "jammukashmir": {
        "name": "Jammu & Kashmir", "region": "North India (UT)",
        "aliases": ["jammu and kashmir", "jammu & kashmir", "jammu", "kashmir"],
        "capital_coords": (34.0837, 74.7973),
        "monsoon_months": [], "best_months": [4, 5, 6, 9, 10], "shoulder_months": [3, 11],
        "culture_note": (
            "The 'Paradise on Earth' - a syncretic Kashmiri culture of Sufi "
            "shrines, Hindu temples and Mughal gardens, alongside sacred Hindu "
            "pilgrimage at Vaishno Devi."
        ),
        "places": [
            {"id": "srinagar", "name": "Srinagar (Dal Lake)", "type": "Nature/Cultural", "lat": 34.0837, "lon": 74.7973,
             "cultural_weight": 70, "tag": "popular", "price": 3200, "crowd_base": 45, "weekend_bump": 14,
             "desc": "Houseboats and Mughal gardens ring the famous Dal Lake."},
            {"id": "gulmarg", "name": "Gulmarg", "type": "Nature/Adventure", "lat": 34.0484, "lon": 74.3805,
             "cultural_weight": 25, "tag": "popular", "price": 3600, "crowd_base": 40, "weekend_bump": 18,
             "desc": "India's premier ski resort, set in an alpine meadow."},
            {"id": "vaishnodevi", "name": "Vaishno Devi", "type": "Religious", "lat": 33.0306, "lon": 74.9496,
             "cultural_weight": 95, "tag": "popular", "price": 1800, "crowd_base": 60, "weekend_bump": 12,
             "desc": "One of Hinduism's most-visited shrines, reached via a Himalayan trek."},
        ],
    },

    "puducherry": {
        "name": "Puducherry", "region": "South India (UT)", "aliases": ["puducherry", "pondicherry"],
        "capital_coords": (11.9416, 79.8083),
        "monsoon_months": [10, 11], "best_months": [11, 12, 1, 2], "shoulder_months": [3],
        "culture_note": (
            "A former French colonial enclave - Franco-Tamil architecture, "
            "and the utopian experimental township of Auroville nearby."
        ),
        "places": [
            {"id": "puducherry_town", "name": "Puducherry (French Quarter)", "type": "Heritage", "lat": 11.9416, "lon": 79.8083,
             "cultural_weight": 70, "tag": "popular", "price": 2600, "crowd_base": 40, "weekend_bump": 16,
             "desc": "Pastel colonial villas, church spires, and a laid-back café culture."},
            {"id": "auroville", "name": "Auroville", "type": "Cultural", "lat": 12.0059, "lon": 79.8097,
             "cultural_weight": 55, "tag": "hidden-gem", "price": 2000, "crowd_base": 25, "weekend_bump": 8,
             "desc": "An experimental universal township built around the golden Matrimandir."},
        ],
    },

    "chandigarh": {
        "name": "Chandigarh", "region": "North India (UT)", "aliases": ["chandigarh"],
        "capital_coords": (30.7333, 76.7794),
        "monsoon_months": [7, 8], "best_months": [10, 11, 2, 3], "shoulder_months": [9],
        "culture_note": (
            "India's first fully planned modern city, designed by Le Corbusier "
            "- a showcase of mid-century modernist architecture and urban design."
        ),
        "places": [
            {"id": "rockgarden", "name": "Rock Garden", "type": "Cultural", "lat": 30.7527, "lon": 76.8058,
             "cultural_weight": 45, "tag": "popular", "price": 2000, "crowd_base": 40, "weekend_bump": 18,
             "desc": "A sculpture garden built entirely from industrial and urban waste."},
            {"id": "sukhnalake", "name": "Sukhna Lake", "type": "Nature", "lat": 30.7425, "lon": 76.8188,
             "cultural_weight": 20, "tag": "popular", "price": 2200, "crowd_base": 35, "weekend_bump": 16,
             "desc": "A man-made lake at the foothills of the Shivaliks, part of the original city plan."},
        ],
    },

    "andaman": {
        "name": "Andaman & Nicobar Islands", "region": "Bay of Bengal (UT)",
        "aliases": ["andaman and nicobar", "andaman & nicobar", "andaman", "nicobar"],
        "capital_coords": (11.6234, 92.7265),
        "monsoon_months": [5, 6, 7, 8, 9], "best_months": [11, 12, 1, 2, 3, 4], "shoulder_months": [10],
        "culture_note": (
            "A remote tropical archipelago - turquoise reefs and colonial "
            "history collide at the Cellular Jail, a memorial to India's freedom struggle."
        ),
        "places": [
            {"id": "havelock", "name": "Havelock Island (Swaraj Dweep)", "type": "Beach", "lat": 12.0339, "lon": 92.9970,
             "cultural_weight": 15, "tag": "popular", "price": 4200, "crowd_base": 40, "weekend_bump": 12,
             "desc": "Radhanagar Beach and some of India's best coral reef diving."},
            {"id": "portblair", "name": "Port Blair (Cellular Jail)", "type": "Heritage", "lat": 11.6234, "lon": 92.7265,
             "cultural_weight": 75, "tag": "hidden-gem", "price": 2800, "crowd_base": 30, "weekend_bump": 8,
             "desc": "A colonial-era prison memorializing India's independence movement."},
        ],
    },

    "lakshadweep": {
        "name": "Lakshadweep", "region": "Arabian Sea (UT)", "aliases": ["lakshadweep"],
        "capital_coords": (10.5669, 72.6420),
        "monsoon_months": [5, 6, 7, 8, 9], "best_months": [10, 11, 12, 1, 2, 3], "shoulder_months": [4],
        "culture_note": (
            "India's smallest UT - a cluster of coral atolls with a distinct "
            "Islamic-influenced island culture, and some of the clearest lagoon waters in Asia."
        ),
        "places": [
            {"id": "kavaratti", "name": "Kavaratti", "type": "Beach", "lat": 10.5669, "lon": 72.6420,
             "cultural_weight": 35, "tag": "hidden-gem", "price": 3600, "crowd_base": 15, "weekend_bump": 5,
             "desc": "The territory's capital atoll, with mosques and pristine lagoons.",
             "safety_note": "Permits are required for both Indian and foreign visitors."},
            {"id": "agatti", "name": "Agatti Island", "type": "Beach", "lat": 10.8500, "lon": 72.1833,
             "cultural_weight": 20, "tag": "hidden-gem", "price": 4000, "crowd_base": 12, "weekend_bump": 4,
             "desc": "The main gateway island, ringed by a shallow turquoise lagoon."},
        ],
    },

    "damandiu": {
        "name": "Dadra, Nagar Haveli, Daman & Diu", "region": "West India (UT)",
        "aliases": ["daman and diu", "daman & diu", "dadra and nagar haveli", "daman", "diu"],
        "capital_coords": (20.3974, 72.8328),
        "monsoon_months": [6, 7, 8, 9], "best_months": [11, 12, 1, 2], "shoulder_months": [10],
        "culture_note": (
            "Two small former Portuguese enclaves - quieter, less-visited "
            "cousins of Goa, with the same colonial-era fort-and-church heritage."
        ),
        "places": [
            {"id": "diu", "name": "Diu Fort", "type": "Heritage/Beach", "lat": 20.7144, "lon": 70.9874,
             "cultural_weight": 65, "tag": "hidden-gem", "price": 2000, "crowd_base": 20, "weekend_bump": 10,
             "desc": "A 16th-century Portuguese fort on a quiet island, with uncrowded beaches."},
            {"id": "daman", "name": "Daman", "type": "Heritage/Beach", "lat": 20.3974, "lon": 72.8328,
             "cultural_weight": 45, "tag": "hidden-gem", "price": 1800, "crowd_base": 22, "weekend_bump": 12,
             "desc": "A former Portuguese coastal enclave with forts and a relaxed pace."},
        ],
    },
}

# Build a flat lookup: alias (lowercase) -> state_key, and place alias -> (state_key, place_id)
STATE_ALIASES = {}
PLACE_ALIASES = {}
for skey, sval in STATES.items():
    for a in sval["aliases"]:
        STATE_ALIASES[a.lower()] = skey
    for p in sval["places"]:
        PLACE_ALIASES[p["name"].lower()] = (skey, p["id"])
        short = p["name"].split(" (")[0].split("/")[0].strip().lower()
        PLACE_ALIASES.setdefault(short, (skey, p["id"]))


# =====================================================================
# 2. LIVE WEATHER / GEOCODING / CLIMATE (Open-Meteo, no API key needed)
# =====================================================================
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
TIMEOUT = 6

WMO_CODES = {
    0: "Clear sky", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Light rain showers", 81: "Rain showers", 82: "Violent rain showers",
    85: "Light snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Severe thunderstorm with hail",
}


def weather_text(code):
    return WMO_CODES.get(code, "Unsettled weather")


def _seed_from(lat, lon, salt=""):
    h = hashlib.sha256(f"{lat:.3f}{lon:.3f}{salt}".encode()).hexdigest()
    return int(h[:8], 16)


def _synthetic_current(lat, lon):
    seed = _seed_from(lat, lon, "current")
    base_temp = 26 - abs(lat) * 0.35
    temp = round(base_temp + (seed % 700) / 100 - 3.5, 1)
    code = [0, 1, 2, 3, 61, 80][seed % 6]
    return {"source": "estimated_offline", "temperature_c": temp, "condition": weather_text(code),
            "humidity": 40 + seed % 45}


def _synthetic_forecast(lat, lon, days=7):
    out = []
    today = date.today()
    for i in range(days):
        seed = _seed_from(lat, lon, f"fc{i}")
        base_temp = 26 - abs(lat) * 0.35
        tmax = round(base_temp + (seed % 500) / 100, 1)
        tmin = round(tmax - 6 - (seed % 300) / 100, 1)
        code = [0, 1, 2, 3, 61, 80][seed % 6]
        out.append({"date": (today + timedelta(days=i)).isoformat(), "tmax": tmax, "tmin": tmin,
                    "precip_mm": round((seed % 40) / 4, 1), "condition": weather_text(code)})
    return {"source": "estimated_offline", "days": out}


def geocode(place_name):
    try:
        r = requests.get(GEOCODE_URL, params={"name": place_name, "count": 1}, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        results = data.get("results")
        if not results:
            return None
        top = results[0]
        return {"lat": top["latitude"], "lon": top["longitude"], "name": top.get("name", place_name),
                "country": top.get("country", ""), "admin1": top.get("admin1", "")}
    except Exception:
        return None


def get_current_and_forecast(lat, lon):
    try:
        r = requests.get(FORECAST_URL, params={
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
            "timezone": "auto", "forecast_days": 7,
        }, timeout=TIMEOUT)
        r.raise_for_status()
        j = r.json()
        cur = j["current"]
        current = {"source": "live", "temperature_c": cur["temperature_2m"],
                   "condition": weather_text(cur["weather_code"]), "humidity": cur["relative_humidity_2m"]}
        daily = j["daily"]
        days = []
        for i, d in enumerate(daily["time"]):
            days.append({"date": d, "tmax": daily["temperature_2m_max"][i], "tmin": daily["temperature_2m_min"][i],
                        "precip_mm": daily["precipitation_sum"][i], "condition": weather_text(daily["weather_code"][i])})
        return current, {"source": "live", "days": days}
    except Exception:
        return _synthetic_current(lat, lon), _synthetic_forecast(lat, lon)


def get_climate_profile(lat, lon):
    end = date.today() - timedelta(days=5)
    start = end - timedelta(days=730)
    try:
        r = requests.get(ARCHIVE_URL, params={
            "latitude": lat, "longitude": lon,
            "start_date": start.isoformat(), "end_date": end.isoformat(),
            "daily": "temperature_2m_mean,precipitation_sum", "timezone": "auto",
        }, timeout=TIMEOUT + 4)
        r.raise_for_status()
        j = r.json()
        temps_by_month = {m: [] for m in range(1, 13)}
        precip_by_month = {m: [] for m in range(1, 13)}
        for i, d in enumerate(j["daily"]["time"]):
            month = int(d.split("-")[1])
            t = j["daily"]["temperature_2m_mean"][i]
            p = j["daily"]["precipitation_sum"][i]
            if t is not None:
                temps_by_month[month].append(t)
            if p is not None:
                precip_by_month[month].append(p)
        monthly = {}
        for m in range(1, 13):
            avg_t = statistics.mean(temps_by_month[m]) if temps_by_month[m] else None
            avg_p = statistics.mean(precip_by_month[m]) if precip_by_month[m] else None
            monthly[m] = {"avg_temp_c": round(avg_t, 1) if avg_t is not None else None,
                          "avg_precip_mm": round(avg_p, 1) if avg_p is not None else None}
        scored = []
        for m, v in monthly.items():
            if v["avg_temp_c"] is None:
                continue
            temp_score = 100 - abs(v["avg_temp_c"] - 23) * 4
            rain_penalty = min(60, (v["avg_precip_mm"] or 0) * 3)
            scored.append((m, temp_score - rain_penalty))
        scored.sort(key=lambda x: -x[1])
        best_months = [m for m, _ in scored[:3]]
        return {"source": "live", "monthly": monthly, "best_months": sorted(best_months)}
    except Exception:
        seed = _seed_from(lat, lon, "climate")
        best_months = sorted({(seed % 12) + 1, ((seed // 7) % 12) + 1, ((seed // 13) % 12) + 1})
        return {"source": "estimated_offline", "monthly": {}, "best_months": best_months}


# =====================================================================
# 2b. LIVE WIKIPEDIA ENRICHMENT (no API key needed)
# =====================================================================
WIKI_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"
_WIKI_CACHE = {}


def wiki_title_guess(place_name):
    base = re.sub(r"\(.*?\)", "", place_name)
    base = base.split("/")[0]
    return base.strip()


def get_wikipedia_link(title):
    slug = urllib.parse.quote(title.replace(" ", "_"))
    return f"https://en.wikipedia.org/wiki/{slug}"


def get_wikipedia_summary(title):
    key = title.lower().strip()
    if key in _WIKI_CACHE:
        return _WIKI_CACHE[key]
    try:
        slug = urllib.parse.quote(title.replace(" ", "_"))
        r = requests.get(WIKI_SUMMARY_URL.format(slug), timeout=TIMEOUT,
                         headers={"User-Agent": "TravelWiseAI/1.0 (educational demo)"})
        if r.status_code == 200:
            j = r.json()
            result = {"source": "live", "title": j.get("title", title), "extract": j.get("extract", "").strip(),
                      "url": j.get("content_urls", {}).get("desktop", {}).get("page") or get_wikipedia_link(title)}
        else:
            raise ValueError(f"status {r.status_code}")
    except Exception:
        result = {"source": "unavailable", "title": title,
                  "extract": "Live Wikipedia summary unavailable right now - use the link to read more.",
                  "url": get_wikipedia_link(title)}
    _WIKI_CACHE[key] = result
    return result


# =====================================================================
# 3. QUERY PARSING + RECOMMENDATION ENGINE
# =====================================================================
STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "am", "i", "you", "we", "they", "he", "she", "it",
    "me", "my", "your", "please", "can", "could", "would", "should", "do", "does", "did",
    "want", "wants", "wanting", "need", "needs", "tell", "know", "give", "show",
    "suggest", "suggestion", "suggestions", "recommend", "recommendation", "plan", "planning",
    "trip", "travel", "traveling", "travelling", "holiday", "vacation", "visit", "visiting",
    "go", "going", "weekend", "today", "tonight", "tomorrow", "next", "this", "that",
    "good", "nice", "best", "great", "for", "with", "to", "in", "near", "about", "of", "on", "at",
    "and", "or", "avoid", "avoiding", "crowd", "crowds", "crowded", "less", "quiet", "peaceful",
    "calm", "uncrowded", "culture", "cultural", "heritage", "historic", "history", "historical",
    "religious", "religion", "tradition", "traditional", "budget", "cheap", "affordable", "low",
    "cost", "inexpensive", "luxury", "premium", "high", "end", "splurge", "upscale",
    "state", "states", "place", "places", "destination", "destinations", "india", "indian",
    "month", "months", "time", "season", "if", "what", "which", "where", "when", "how",
    "just", "only", "some", "any", "info", "information", "details",
}


def parse_query(raw):
    q = raw.lower()
    budget = "mid"
    if re.search(r"budget|cheap|affordable|low.cost|inexpensive", q):
        budget = "low"
    elif re.search(r"luxury|premium|high.end|splurge|upscale", q):
        budget = "high"

    weekend = bool(re.search(r"\bweekend\b|\bsaturday\b|\bsunday\b", q))
    today = bool(re.search(r"\btoday\b|\btonight\b", q))
    quiet = bool(re.search(r"avoid crowd|less crowd|quiet|peaceful|no crowd|calm|uncrowded", q))
    culture = bool(re.search(r"culture|heritage|temple|historic|history|religious|tradition", q))
    list_all = bool(re.search(
        r"all states|every state|all destinations?|all places|list.*(state|destination|place)|"
        r"what.*(states|places).*(cover|have|support|know)|show me everything|entire database|"
        r"full list|full directory",
        q,
    ))

    # try to find a known place or state name inside the query (longest match first)
    mentioned_place = None
    mentioned_state = None
    for alias, (skey, pid) in sorted(PLACE_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if alias in q:
            mentioned_place = (skey, pid)
            mentioned_state = skey
            break
    if not mentioned_state:
        for alias, skey in sorted(STATE_ALIASES.items(), key=lambda kv: -len(kv[0])):
            if alias in q:
                mentioned_state = skey
                break

    free_location = None
    if not mentioned_state and not list_all:
        # 1) heuristic: text after "to"/"in"/"near"/"about"/"visit"
        m = re.search(r"\b(?:to|in|near|about|visit)\s+([a-zA-Z\s]{3,30})", raw)
        if m:
            candidate = m.group(1).strip().rstrip(".,!?")
            candidate = re.sub(
                r"\s+(next|this|weekend|today|avoiding.*|for.*|with.*)$", "", candidate, flags=re.I
            ).strip()
            if candidate:
                free_location = candidate
        # 2) fallback: strip filler/stopwords from the WHOLE query and see what's left.
        #    This is what makes bare queries like "Bihar" or "Uttar Pradesh" work, and
        #    lets genuinely unlisted places (any city/country) reach the live geocoder
        #    instead of ever silently defaulting to a fixed curated state.
        if not free_location:
            words = re.findall(r"[A-Za-z]+", raw)
            kept = [w for w in words if w.lower() not in STOPWORDS]
            candidate = " ".join(kept).strip()
            if len(candidate) >= 3:
                free_location = candidate

    return {
        "raw": raw, "budget": budget, "weekend": weekend, "today": today,
        "quiet": quiet, "culture": culture, "list_all": list_all,
        "mentioned_place": mentioned_place, "mentioned_state": mentioned_state,
        "free_location": free_location,
    }


def price_norm(price, lo=1500, hi=5500):
    return max(0.0, min(1.0, (price - lo) / (hi - lo)))


def weather_fit_score(tmax):
    ideal_dist = abs(tmax - 23)
    return max(15, min(100, 100 - ideal_dist * 4))


def score_place(place, forecast_day, parsed, current_month):
    crowd = place["crowd_base"]
    if parsed["weekend"]:
        crowd += place["weekend_bump"]
    if current_month in place.get("festival_months", []):
        crowd += 30
    crowd = max(3, min(97, crowd))

    crowd_score = 100 - crowd
    tmax = forecast_day["tmax"] if forecast_day else 25
    w_score = weather_fit_score(tmax)

    if parsed["budget"] == "low":
        budget_fit = (1 - price_norm(place["price"])) * 100
    elif parsed["budget"] == "high":
        budget_fit = price_norm(place["price"]) * 100
    else:
        budget_fit = 70 - abs(price_norm(place["price"]) - 0.4) * 40

    cultural_weight = place["cultural_weight"]
    cultural_term = 0.40 if parsed["culture"] else 0.12

    crowd_weight = 0.40 if parsed["quiet"] else 0.26
    remaining = 1 - crowd_weight - cultural_term
    weather_weight = remaining * 0.35
    budget_weight = remaining * 0.65

    score = (crowd_score * crowd_weight + w_score * weather_weight +
             budget_fit * budget_weight + cultural_weight * cultural_term)
    if place.get("tag") == "caution":
        score -= 10

    return {"crowd": crowd, "crowd_score": crowd_score, "weather_score": round(w_score, 1),
            "budget_fit": round(budget_fit, 1), "score": round(score, 2)}


def day_offset_for(parsed):
    today_idx = date.today().weekday()
    if parsed["today"]:
        return 0
    if parsed["weekend"]:
        for i in range(7):
            if (today_idx + i) % 7 == 5:
                return i
    return 0


def build_state_response(skey, parsed):
    state = STATES[skey]
    offset = day_offset_for(parsed)
    current_month = date.today().month
    day_label = "today" if parsed["today"] else ("this weekend" if parsed["weekend"] else "in the coming days")

    scored_places = []
    for p in state["places"]:
        cur, fc = get_current_and_forecast(p["lat"], p["lon"])
        day = fc["days"][min(offset, len(fc["days"]) - 1)]
        s = score_place(p, day, parsed, current_month)
        wiki_url = get_wikipedia_link(wiki_title_guess(p["name"]))
        scored_places.append({**p, **s, "current": cur, "forecast": fc, "day_used": day, "wiki_url": wiki_url})

    scored_places.sort(key=lambda x: -x["score"])
    best = scored_places[0]

    if parsed["mentioned_place"] and parsed["mentioned_place"][0] == skey:
        target_id = parsed["mentioned_place"][1]
        avoid = next(p for p in scored_places if p["id"] == target_id)
    else:
        avoid = max(scored_places, key=lambda x: x["crowd"])

    is_peak = current_month in state["best_months"]
    is_monsoon = current_month in state.get("monsoon_months", [])

    return {
        "mode": "state", "state_key": skey, "state_name": state["name"],
        "region": state["region"], "culture_note": state["culture_note"],
        "day_label": day_label, "parsed": parsed,
        "best_months": state["best_months"],
        "best_months_names": [MONTH_NAMES[m] for m in state["best_months"]],
        "is_peak_season_now": is_peak, "is_monsoon_now": is_monsoon,
        "places": scored_places, "best": best, "avoid": avoid,
    }


def build_freeform_response(location_text, parsed):
    geo = geocode(location_text)
    if not geo:
        return {"mode": "not_found", "query_location": location_text, "parsed": parsed}

    cur, fc = get_current_and_forecast(geo["lat"], geo["lon"])
    climate = get_climate_profile(geo["lat"], geo["lon"])
    offset = day_offset_for(parsed)
    day = fc["days"][min(offset, len(fc["days"]) - 1)]
    day_label = "today" if parsed["today"] else ("this weekend" if parsed["weekend"] else "in the coming days")
    wiki = get_wikipedia_summary(wiki_title_guess(geo["name"]))

    return {
        "mode": "freeform", "resolved_name": geo["name"], "country": geo["country"],
        "admin1": geo.get("admin1", ""), "lat": geo["lat"], "lon": geo["lon"],
        "current": cur, "forecast": fc, "day_used": day, "climate": climate,
        "best_months_names": [MONTH_NAMES[m] for m in climate["best_months"]],
        "day_label": day_label, "parsed": parsed, "wiki": wiki,
    }


def build_directory_answer(parsed):
    states_out = []
    total_places = 0
    for skey, sval in STATES.items():
        places_out = []
        for p in sval["places"]:
            places_out.append({
                "id": p["id"], "name": p["name"], "type": p["type"],
                "cultural_weight": p["cultural_weight"], "tag": p["tag"],
                "wiki_url": get_wikipedia_link(wiki_title_guess(p["name"])),
            })
        total_places += len(places_out)
        states_out.append({"key": skey, "name": sval["name"], "region": sval["region"], "places": places_out})
    return {"mode": "directory", "states": states_out, "total_states": len(states_out),
            "total_places": total_places, "parsed": parsed}


def build_clarify_response(parsed):
    """Used only when a query truly gives us nothing to work with - no curated
    state/place match and no plausible free-text location. We ask, we don't guess."""
    sample = [STATES[k]["name"] for k in list(STATES.keys())[:8]]
    return {"mode": "clarify", "parsed": parsed, "sample_states": sample,
            "total_states": len(STATES)}


def recommend(raw_query):
    parsed = parse_query(raw_query)
    if parsed["list_all"]:
        return build_directory_answer(parsed)
    if parsed["mentioned_state"]:
        return build_state_response(parsed["mentioned_state"], parsed)
    if parsed["free_location"]:
        return build_freeform_response(parsed["free_location"], parsed)
    return build_clarify_response(parsed)


# =====================================================================
# 4. FLASK APP
# =====================================================================
app = Flask(__name__)

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TravelWise AI — Smart Tourism Decision Assistant</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{
  --bg: #0e2624; --bg-deep: #0a1e1c; --panel: #143634; --panel-alt: #1b433f;
  --line: rgba(241,236,225,0.10); --brass: #c98a3d; --brass-bright: #e3a75a;
  --backwater: #4fa697; --backwater-bright: #6fc4b4; --laterite: #c1573c; --laterite-bright: #dd6d50;
  --mist: #f1ece1; --text-dim: #9fbdb8; --text-dimmer: #6f8f8a; --radius: 14px;
  --shadow: 0 20px 50px rgba(0,0,0,0.35);
}
*{box-sizing:border-box;}
html{scroll-behavior:smooth;}
body{
  margin:0;
  background:
    radial-gradient(1200px 600px at 15% -10%, rgba(79,166,151,0.14), transparent 60%),
    radial-gradient(900px 500px at 100% 0%, rgba(201,138,61,0.10), transparent 55%),
    var(--bg);
  color:var(--mist); font-family:'IBM Plex Sans', sans-serif; -webkit-font-smoothing:antialiased;
}
.page{max-width:1180px; margin:0 auto; padding:0 28px 80px;}
.mono{font-family:'IBM Plex Mono', monospace;}
.display{font-family:'Fraunces', serif;}
header.top{display:flex; align-items:center; justify-content:space-between; padding:28px 0 20px; flex-wrap:wrap; gap:10px;}
.wordmark{display:flex; align-items:center; gap:10px;}
.wordmark .dot{width:10px;height:10px;border-radius:50%;background:var(--brass-bright); box-shadow:0 0 12px var(--brass-bright);}
.wordmark span{font-family:'Fraunces', serif; font-weight:600; font-size:1.25rem; letter-spacing:0.01em;}
.wordmark small{display:block; font-family:'IBM Plex Mono', monospace; font-size:0.62rem; color:var(--text-dimmer); letter-spacing:0.12em; text-transform:uppercase; margin-top:2px;}
nav.top-tags{display:flex; gap:18px; font-size:0.78rem; color:var(--text-dim); font-family:'IBM Plex Mono', monospace;}
@media (max-width: 640px){ nav.top-tags{display:none;} }
.hero{padding:44px 0 30px; position:relative;}
.eyebrow{display:inline-flex; align-items:center; gap:8px; font-family:'IBM Plex Mono', monospace; font-size:0.72rem; letter-spacing:0.1em; text-transform:uppercase; color:var(--backwater-bright); border:1px solid var(--line); padding:6px 12px; border-radius:100px; background:rgba(79,166,151,0.06);}
h1.hero-title{font-family:'Fraunces', serif; font-weight:600; font-size:clamp(2.1rem, 5vw, 3.4rem); line-height:1.05; margin:20px 0 14px; letter-spacing:-0.01em; max-width:760px;}
h1.hero-title em{font-style:italic; color:var(--brass-bright);}
.hero p.sub{color:var(--text-dim); font-size:1.05rem; max-width:600px; line-height:1.55; margin-bottom:34px;}
.ask-box{background:linear-gradient(180deg, var(--panel-alt), var(--panel)); border:1px solid var(--line); border-radius:20px; padding:22px; box-shadow:var(--shadow);}
.ask-box label{display:block; font-family:'IBM Plex Mono', monospace; font-size:0.68rem; color:var(--text-dimmer); text-transform:uppercase; letter-spacing:0.1em; margin-bottom:10px;}
.ask-row{display:flex; gap:10px;}
.ask-row input{flex:1; background:var(--bg-deep); border:1px solid var(--line); color:var(--mist); border-radius:12px; padding:15px 16px; font-size:0.98rem; font-family:'IBM Plex Sans', sans-serif; outline:none; transition:border-color 0.15s ease;}
.ask-row input:focus{border-color:var(--backwater-bright);}
.ask-row input::placeholder{color:var(--text-dimmer);}
.ask-row button{background:var(--brass); color:#1a1208; border:none; border-radius:12px; padding:0 22px; font-family:'IBM Plex Sans', sans-serif; font-weight:600; font-size:0.95rem; cursor:pointer; transition:background 0.15s ease, transform 0.1s ease;}
.ask-row button:hover{background:var(--brass-bright);}
.ask-row button:active{transform:scale(0.97);}
.ask-row button:disabled{opacity:0.6; cursor:progress;}
.chips{display:flex; flex-wrap:wrap; gap:8px; margin-top:14px;}
.chip{font-family:'IBM Plex Mono', monospace; font-size:0.74rem; color:var(--text-dim); border:1px solid var(--line); padding:7px 12px; border-radius:100px; cursor:pointer; background:rgba(255,255,255,0.02); transition:all 0.15s ease;}
.chip:hover{border-color:var(--backwater-bright); color:var(--mist); background:rgba(79,166,151,0.08);}
.wave{height:34px; margin:10px 0 6px; opacity:0.6;}
#responseArea{margin-top:30px;}
.rec-card{border:1px solid var(--line); border-radius:18px; overflow:hidden; background:var(--panel); box-shadow:var(--shadow); animation:riseIn 0.4s ease;}
@keyframes riseIn{from{opacity:0; transform:translateY(10px);} to{opacity:1; transform:translateY(0);}}
@media (prefers-reduced-motion: reduce){ .rec-card{animation:none;} }
.rec-head{padding:20px 24px; border-bottom:1px solid var(--line); display:flex; align-items:center; gap:12px;}
.rec-head .ai-badge{width:30px;height:30px;border-radius:9px;background:var(--backwater); display:flex; align-items:center; justify-content:center; font-family:'IBM Plex Mono',monospace; font-size:0.8rem; font-weight:600; color:#06201c; flex-shrink:0;}
.rec-head .q-text{font-size:0.92rem; color:var(--text-dim); font-style:italic;}
.rec-body{padding:24px;}
.verdict-line{display:flex; gap:12px; align-items:flex-start; padding:14px 16px; border-radius:12px; margin-bottom:12px;}
.verdict-line.avoid{background:rgba(193,87,60,0.12); border:1px solid rgba(193,87,60,0.35);}
.verdict-line.go{background:rgba(79,166,151,0.12); border:1px solid rgba(79,166,151,0.35);}
.verdict-line.info{background:rgba(201,138,61,0.10); border:1px solid rgba(201,138,61,0.3);}
.verdict-line .icon{font-size:1.1rem; margin-top:1px;}
.verdict-line p{margin:0; line-height:1.6; font-size:0.98rem;}
.verdict-line b{color:var(--mist);}
.stat-row{display:flex; flex-wrap:wrap; gap:10px; margin-top:16px;}
.stat-pill{font-family:'IBM Plex Mono', monospace; font-size:0.78rem; color:var(--text-dim); background:var(--bg-deep); border:1px solid var(--line); padding:8px 13px; border-radius:10px;}
.stat-pill b{color:var(--brass-bright); font-weight:600;}
.stat-pill.warn b{color:var(--laterite-bright);}
.why-toggle{margin-top:16px; font-size:0.8rem; color:var(--backwater-bright); cursor:pointer; font-family:'IBM Plex Mono', monospace; display:inline-block;}
.why-panel{display:none; margin-top:12px; padding:14px 16px; background:var(--bg-deep); border-radius:10px; border:1px solid var(--line); font-size:0.86rem; color:var(--text-dim); line-height:1.6;}
.why-panel.open{display:block;}
.why-panel table{width:100%; border-collapse:collapse; margin-top:8px;}
.why-panel td{padding:4px 6px; border-bottom:1px solid var(--line); font-family:'IBM Plex Mono',monospace; font-size:0.78rem;}
.why-panel td:first-child{color:var(--text-dimmer);}
.data-source{font-size:0.68rem; color:var(--text-dimmer); font-family:'IBM Plex Mono',monospace; margin-top:10px;}
.data-source.offline{color:var(--laterite-bright);}
.wiki-link{color:var(--backwater-bright); text-decoration:none; font-family:'IBM Plex Mono',monospace; font-size:0.74rem; display:inline-block; margin-top:8px;}
.wiki-link:hover{text-decoration:underline;}
.directory-line a{color:var(--backwater-bright); text-decoration:none;}
.directory-line a:hover{text-decoration:underline;}
.section-head{margin:64px 0 22px; display:flex; align-items:baseline; justify-content:space-between; flex-wrap:wrap; gap:10px;}
.section-head h2{font-family:'Fraunces', serif; font-weight:600; font-size:1.6rem; margin:0;}
.section-head p{color:var(--text-dimmer); font-size:0.88rem; margin:0; font-family:'IBM Plex Mono', monospace;}
.state-select{background:var(--bg-deep); color:var(--mist); border:1px solid var(--line); border-radius:10px; padding:9px 12px; font-family:'IBM Plex Mono', monospace; font-size:0.8rem; cursor:pointer;}
.grid{display:grid; grid-template-columns:repeat(auto-fill, minmax(270px, 1fr)); gap:16px;}
.dcard{background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:18px; cursor:pointer; transition:border-color 0.15s ease, transform 0.15s ease; display:flex; flex-direction:column; gap:12px;}
.dcard:hover{border-color:var(--backwater-bright); transform:translateY(-2px);}
.dcard.active{border-color:var(--brass-bright); box-shadow:0 0 0 1px var(--brass-bright);}
.dcard-top{display:flex; justify-content:space-between; align-items:flex-start;}
.dcard-top h3{font-family:'Fraunces', serif; font-size:1.15rem; margin:0 0 3px; font-weight:600;}
.dcard-top .region{font-size:0.76rem; color:var(--text-dimmer); font-family:'IBM Plex Mono',monospace;}
.tag{font-size:0.66rem; font-family:'IBM Plex Mono',monospace; padding:4px 9px; border-radius:100px; text-transform:uppercase; letter-spacing:0.05em; white-space:nowrap;}
.tag.hidden-gem{background:rgba(79,166,151,0.15); color:var(--backwater-bright); border:1px solid rgba(79,166,151,0.3);}
.tag.popular{background:rgba(201,138,61,0.15); color:var(--brass-bright); border:1px solid rgba(201,138,61,0.3);}
.tag.caution{background:rgba(193,87,60,0.15); color:var(--laterite-bright); border:1px solid rgba(193,87,60,0.3);}
.wx-wrap{display:flex; align-items:center; gap:10px;}
.wx-icon{width:40px; height:40px; flex-shrink:0; display:flex; align-items:center; justify-content:center; border-radius:10px; background:var(--bg-deep); font-size:1.2rem;}
.wx-meta{flex:1;}
.wx-meta .label{font-size:0.68rem; color:var(--text-dimmer); font-family:'IBM Plex Mono',monospace; text-transform:uppercase; letter-spacing:0.06em;}
.wx-meta .val{font-family:'IBM Plex Mono',monospace; font-size:1.1rem; font-weight:600;}
.wx-meta .cond{font-size:0.74rem; color:var(--text-dim);}
.cultural-bar-wrap{margin-top:2px;}
.cultural-bar-wrap .cb-label{font-size:0.68rem; color:var(--text-dimmer); font-family:'IBM Plex Mono',monospace; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:5px; display:flex; justify-content:space-between;}
.bar-track{height:8px; background:var(--bg-deep); border-radius:6px; overflow:hidden;}
.bar-fill{height:100%; border-radius:6px;}
.bar-fill.cultural{background:var(--laterite);}
.bar-fill.stars{background:var(--brass);}
.bar-fill.real{background:var(--backwater);}
.mini-stats{display:flex; justify-content:space-between; font-size:0.78rem; color:var(--text-dim); border-top:1px solid var(--line); padding-top:10px;}
.mini-stats .item b{display:block; color:var(--mist); font-family:'IBM Plex Mono',monospace; font-size:0.86rem;}
.safety-note{font-size:0.74rem; color:var(--laterite-bright); background:rgba(193,87,60,0.08); padding:6px 9px; border-radius:8px; line-height:1.4;}
.pick-label{color:var(--brass-bright); font-family:'IBM Plex Mono',monospace; font-size:0.68rem; text-transform:uppercase; letter-spacing:0.06em;}
.detail{background:var(--panel); border:1px solid var(--line); border-radius:18px; padding:24px; margin-top:18px;}
.detail-head{display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; flex-wrap:wrap; gap:10px;}
.detail-head h3{font-family:'Fraunces', serif; margin:0; font-size:1.3rem;}
.detail-head .sub{color:var(--text-dimmer); font-size:0.82rem; font-family:'IBM Plex Mono',monospace;}
.chart-wrap{margin-top:14px;}
svg.forecast{width:100%; height:180px; overflow:visible;}
.sentiment-compare{display:flex; gap:22px; margin-top:22px; flex-wrap:wrap;}
.sc-block{flex:1; min-width:220px;}
.sc-block .sc-label{font-size:0.72rem; color:var(--text-dimmer); font-family:'IBM Plex Mono',monospace; text-transform:uppercase; margin-bottom:6px;}
.sc-val{font-family:'IBM Plex Mono',monospace; font-size:0.82rem; margin-top:5px; color:var(--text-dim);}
.review-quote{font-size:0.86rem; color:var(--text-dim); font-style:italic; margin-top:14px; line-height:1.5; border-left:2px solid var(--backwater); padding-left:12px;}
.review-quote.wiki{border-left-color:var(--brass);}
.best-months-row{display:flex; flex-wrap:wrap; gap:6px; margin-top:10px;}
.month-chip{font-family:'IBM Plex Mono',monospace; font-size:0.72rem; padding:5px 10px; border-radius:100px; border:1px solid var(--line); color:var(--text-dim);}
.month-chip.best{border-color:var(--backwater-bright); color:var(--backwater-bright); background:rgba(79,166,151,0.08);}
.pipeline{display:flex; gap:0; margin-top:10px; overflow-x:auto; padding-bottom:6px;}
.pstep{flex:1; min-width:150px; padding:16px 14px; position:relative;}
.pstep .num{font-family:'Fraunces', serif; font-size:1.6rem; color:var(--text-dimmer); opacity:0.5;}
.pstep h4{font-size:0.86rem; margin:6px 0 4px; font-family:'IBM Plex Sans',sans-serif;}
.pstep p{font-size:0.74rem; color:var(--text-dimmer); line-height:1.4; margin:0;}
.pstep:not(:last-child)::after{content:'→'; position:absolute; right:-2px; top:22px; color:var(--text-dimmer); font-size:1rem;}
@media (max-width:800px){ .pstep:not(:last-child)::after{display:none;} }
.loading{color:var(--text-dimmer); font-family:'IBM Plex Mono',monospace; font-size:0.85rem; padding:20px 0;}
.directory-state{margin-top:14px;}
footer.foot{margin-top:70px; padding-top:24px; border-top:1px solid var(--line); display:flex; justify-content:space-between; flex-wrap:wrap; gap:10px; font-size:0.76rem; color:var(--text-dimmer); font-family:'IBM Plex Mono',monospace;}
</style>
</head>
<body>
<div class="page">

  <header class="top">
    <div class="wordmark">
      <div class="dot"></div>
      <div>
        <span>TravelWise AI</span>
        <small>Smart Tourism Decision Assistant</small>
      </div>
    </div>
    <nav class="top-tags">
      <span>India Pilot · {{ states|length }} states &amp; UTs</span>
      <span>·</span>
      <span>Live weather via Open-Meteo</span>
      <span>·</span>
      <span>Wikipedia-linked</span>
    </nav>
  </header>

  <section class="hero">
    <span class="eyebrow">● live weather &amp; climate data · every Indian state &amp; UT curated · Wikipedia-enriched · any-place fallback</span>
    <h1 class="hero-title">Know before <em>you</em> go.</h1>
    <p class="sub">Ask a plain question about your trip — any Indian state or UT, or any place in the world. TravelWise pulls live weather, weighs each destination's cultural significance, links you to Wikipedia for deeper reading, and tells you exactly where to go and when.</p>

    <div class="ask-box">
      <label>Ask TravelWise</label>
      <div class="ask-row">
        <input id="queryInput" type="text" placeholder="e.g. Bihar, Uttar Pradesh, or a budget trip to Goa avoiding crowds" />
        <button id="askBtn">Ask →</button>
      </div>
      <div class="chips">
        <span class="chip" data-q="Suggest a budget trip to Goa next weekend avoiding crowds">budget · Goa · avoid crowds</span>
        <span class="chip" data-q="Bihar">Bihar</span>
        <span class="chip" data-q="Uttar Pradesh">Uttar Pradesh</span>
        <span class="chip" data-q="I want a quiet cultural heritage trip in Rajasthan">heritage trip in Rajasthan</span>
        <span class="chip" data-q="Tell me about visiting Kyoto">tell me about Kyoto</span>
        <span class="chip" data-q="List all the states and places you cover">list all states &amp; places</span>
      </div>
    </div>

    <svg class="wave" viewBox="0 0 1200 40" preserveAspectRatio="none">
      <path d="M0,20 Q50,0 100,20 T200,20 T300,20 T400,20 T500,20 T600,20 T700,20 T800,20 T900,20 T1000,20 T1100,20 T1200,20" fill="none" stroke="#4fa697" stroke-width="1.4" opacity="0.5"/>
    </svg>
  </section>

  <div id="responseArea"></div>

  <div class="section-head">
    <h2>🧭 AI Tourist Expert</h2>
    <p>today's best picks, ranked across every curated state &amp; UT</p>
  </div>
  <div class="grid" id="expertGrid"><div class="loading">Consulting the AI tourist expert…</div></div>

  <div class="section-head">
    <h2>Destination explorer</h2>
    <select class="state-select" id="stateSelect">
      {% for s in states %}
      <option value="{{ s.key }}">{{ s.name }} — {{ s.region }}</option>
      {% endfor %}
    </select>
  </div>
  <p class="mono" id="cultureNote" style="color:var(--text-dim); font-size:0.85rem; line-height:1.6; margin-top:-8px;"></p>
  <div class="grid" id="destGrid"><div class="loading">Loading live weather…</div></div>

  <div class="detail" id="detailPanel"></div>

  <div class="section-head">
    <h2>Complete destination directory</h2>
    <p id="directoryCount">every state, UT &amp; place we cover, linked to Wikipedia</p>
  </div>
  <div id="directoryWrap"><div class="loading">Loading full directory…</div></div>

  <div class="section-head">
    <h2>How this works</h2>
    <p>data → decision, in five hops</p>
  </div>
  <div class="pipeline">
    <div class="pstep"><div class="num">01</div><h4>Resolve place</h4><p>Match your query against a curated database of every state/UT, or geocode any place worldwide.</p></div>
    <div class="pstep"><div class="num">02</div><h4>Fetch live weather</h4><p>Real current conditions + 7-day forecast from Open-Meteo, no API key needed.</p></div>
    <div class="pstep"><div class="num">03</div><h4>Model climate</h4><p>For unlisted places, ~2 years of historical data is aggregated by month to find the best season.</p></div>
    <div class="pstep"><div class="num">04</div><h4>Rank</h4><p>Hybrid engine balances estimated crowd levels, live weather fit, cultural weight and budget fit.</p></div>
    <div class="pstep"><div class="num">05</div><h4>Explain &amp; enrich</h4><p>Converts the ranked result into a plain recommendation, with a live Wikipedia link for further reading.</p></div>
  </div>

  <footer class="foot">
    <span>TravelWise AI — weather &amp; climate data live from Open-Meteo, background reading live from Wikipedia; crowd levels are a heuristic estimate, not a live sensor feed</span>
    <span id="footState">{{ states|length }} states &amp; UTs curated</span>
  </footer>
</div>

<script>
const DAY_NAMES = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
const MONTH_NAMES = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

let currentStateKey = 'kerala';
let currentStateData = null;

function weatherEmoji(condition){
  const c = (condition||'').toLowerCase();
  if(c.includes('thunder')) return '⛈️';
  if(c.includes('snow')) return '❄️';
  if(c.includes('fog')) return '🌫️';
  if(c.includes('drizzle')) return '🌦️';
  if(c.includes('shower') || c.includes('rain')) return '🌧️';
  if(c.includes('overcast')) return '☁️';
  if(c.includes('partly')) return '⛅';
  if(c.includes('clear')) return '☀️';
  return '🌤️';
}

/* ================= AI TOURIST EXPERT ================= */
async function loadExpert(){
  const grid = document.getElementById('expertGrid');
  try{
    const res = await fetch('/api/expert');
    const data = await res.json();
    const labels = {
      culture: ['🏛️', 'Best for Culture & Heritage'],
      hidden_gem: ['💎', 'Best Hidden Gem'],
      budget: ['💰', 'Best Budget Pick'],
      luxury: ['✨', 'Best Splurge / Luxury Pick'],
      season: ['🗓️', `Best Right Now (${data.month})`],
      quiet: ['🧘', 'Best for Avoiding Crowds'],
    };
    grid.innerHTML = Object.entries(data.picks).map(([key, p]) => {
      const [icon, label] = labels[key] || ['⭐', 'Recommended'];
      const extract = p.wiki && p.wiki.extract ? p.wiki.extract : p.desc;
      const shortExtract = extract.length > 170 ? extract.slice(0, 170) + '…' : extract;
      return `
      <div class="dcard" onclick="jumpToPlace('${p.state_key}','${p.id}')">
        <div class="dcard-top">
          <div><h3>${icon} ${p.name}</h3><div class="region">${p.state_name} · ${p.type}</div></div>
          <span class="tag ${p.tag}">${p.tag.replace('-', ' ')}</span>
        </div>
        <div class="pick-label">${label}</div>
        <div class="review-quote" style="margin-top:0;">${shortExtract}</div>
        <div class="cultural-bar-wrap">
          <div class="cb-label"><span>Cultural weight</span><span>${p.cultural_weight}/100</span></div>
          <div class="bar-track"><div class="bar-fill cultural" style="width:${p.cultural_weight}%"></div></div>
        </div>
        <div class="mini-stats">
          <div class="item"><span>Avg/night</span><b>₹${p.price}</b></div>
          <div class="item"><span>Est. crowd</span><b>${p.crowd_base}%</b></div>
        </div>
        <a href="${p.wiki.url}" target="_blank" rel="noopener" class="wiki-link" onclick="event.stopPropagation();">read on Wikipedia →</a>
      </div>`;
    }).join('');
  } catch(e){
    grid.innerHTML = '<div class="loading">Could not reach the AI tourist expert right now — try refreshing.</div>';
  }
}

function jumpToPlace(stateKey, placeId){
  document.getElementById('stateSelect').value = stateKey;
  loadState(stateKey).then(() => {
    selectDestination(placeId);
    document.getElementById('destGrid').scrollIntoView({behavior:'smooth', block:'start'});
  });
}

/* ================= DESTINATION EXPLORER ================= */
async function loadState(key){
  currentStateKey = key;
  document.getElementById('destGrid').innerHTML = '<div class="loading">Loading live weather…</div>';
  const res = await fetch(`/api/state/${key}`);
  const data = await res.json();
  currentStateData = data;
  document.getElementById('cultureNote').textContent = data.culture_note;
  document.getElementById('footState').textContent = `${data.name} · ${data.places.length} curated destinations`;
  renderGrid(data);
  if(data.places.length) selectDestination(data.places[0].id);
}

function renderGrid(data){
  const grid = document.getElementById('destGrid');
  grid.innerHTML = data.places.map(d => `
    <div class="dcard" id="card-${d.id}" onclick="selectDestination('${d.id}')">
      <div class="dcard-top">
        <div>
          <h3>${d.name}</h3>
          <div class="region">${d.type}</div>
        </div>
        <span class="tag ${d.tag}">${d.tag.replace('-', ' ')}</span>
      </div>
      <div class="wx-wrap">
        <div class="wx-icon">${weatherEmoji(d.current.condition)}</div>
        <div class="wx-meta">
          <div class="label">${d.current.source === 'live' ? 'Live now' : 'Estimated (offline)'}</div>
          <div class="val">${d.current.temperature_c}°C</div>
          <div class="cond">${d.current.condition}</div>
        </div>
      </div>
      <div class="cultural-bar-wrap">
        <div class="cb-label"><span>Cultural weight</span><span>${d.cultural_weight}/100</span></div>
        <div class="bar-track"><div class="bar-fill cultural" style="width:${d.cultural_weight}%"></div></div>
      </div>
      ${d.safety_note ? `<div class="safety-note">⚠ ${d.safety_note}</div>` : ''}
      <div class="mini-stats">
        <div class="item"><span>Avg/night</span><b>₹${d.price}</b></div>
        <div class="item"><span>Humidity</span><b>${d.current.humidity}%</b></div>
      </div>
    </div>`).join('');
}

async function selectDestination(id){
  document.querySelectorAll('.dcard').forEach(c=>c.classList.remove('active'));
  const card = document.getElementById('card-'+id);
  if(card) card.classList.add('active');

  const panel = document.getElementById('detailPanel');
  panel.innerHTML = '<div class="loading">Loading 7-day forecast &amp; Wikipedia summary…</div>';
  const res = await fetch(`/api/place/${currentStateKey}/${id}`);
  const data = await res.json();
  const d = data.place;
  const cur = data.current;
  const days = data.forecast.days;
  const wiki = data.wiki;

  const bestMonthsChips = Array.from({length:12}, (_,i)=>i+1).map(m => `
    <span class="month-chip ${data.best_months.includes(m) ? 'best' : ''}">${MONTH_NAMES[m]}</span>
  `).join('');

  panel.innerHTML = `
    <div class="detail-head">
      <div>
        <h3>${d.name} — 7-day forecast</h3>
        <div class="sub">${data.state_name} · ${d.type} · ₹${d.price}/night avg</div>
      </div>
      <span class="stat-pill">${cur.source === 'live' ? '● live weather' : '○ estimated (offline mode)'}</span>
    </div>
    <div class="chart-wrap">${forecastSvg(days, d.id)}</div>
    <div class="sentiment-compare">
      <div class="sc-block">
        <div class="sc-label">Cultural weight</div>
        <div class="bar-track"><div class="bar-fill cultural" style="width:${d.cultural_weight}%"></div></div>
        <div class="sc-val">${d.cultural_weight} / 100 — ${d.cultural_weight >= 70 ? 'primarily a heritage / cultural destination' : d.cultural_weight >= 40 ? 'a mix of culture and recreation' : 'primarily scenic / recreational'}</div>
      </div>
      <div class="sc-block">
        <div class="sc-label">Best months to visit (this state)</div>
        <div class="best-months-row">${bestMonthsChips}</div>
      </div>
    </div>
    <div class="review-quote">${d.desc}</div>
    <div class="review-quote wiki">
      ${wiki.extract}
      <br><a href="${wiki.url}" target="_blank" rel="noopener" class="wiki-link">Read more on Wikipedia →</a>
      <div class="data-source ${wiki.source !== 'live' ? 'offline' : ''}" style="margin-top:6px;">wikipedia: ${wiki.source}</div>
    </div>
    ${d.safety_note ? `<div class="safety-note" style="margin-top:12px;">⚠ ${d.safety_note}</div>` : ''}
  `;
}

function forecastSvg(days, id){
  const w=1000, h=180, pad=34;
  const maxTemp = Math.max(...days.map(d=>d.tmax));
  const minTemp = Math.min(...days.map(d=>d.tmin));
  const range = Math.max(1, maxTemp-minTemp);
  const pts = days.map((day,i)=>{
    const x = pad + (i/(days.length-1))*(w-pad*2);
    const y = h-pad - ((day.tmax-minTemp)/range)*(h-pad*1.4);
    return {x,y,day};
  });
  const line = pts.map(p=>`${p.x},${p.y}`).join(' ');
  const area = `${pad},${h-pad} ${line} ${w-pad},${h-pad}`;
  const dots = pts.map((p,i)=>{
    const dow = new Date(p.day.date).getDay();
    return `
    <circle cx="${p.x}" cy="${p.y}" r="4" fill="var(--backwater-bright)" stroke="#0e2624" stroke-width="2"/>
    <text x="${p.x}" y="${h-8}" text-anchor="middle" font-size="11" fill="var(--text-dimmer)" font-family="IBM Plex Mono">${DAY_NAMES[dow]}</text>
    <text x="${p.x}" y="${p.y-14}" text-anchor="middle" font-size="11" fill="var(--mist)" font-family="IBM Plex Mono">${Math.round(p.day.tmax)}°</text>
  `}).join('');
  return `
  <svg class="forecast" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <polygon points="${area}" fill="url(#grad-${id})" opacity="0.35"/>
    <polyline points="${line}" fill="none" stroke="var(--backwater-bright)" stroke-width="2.4"/>
    <defs>
      <linearGradient id="grad-${id}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="var(--backwater-bright)"/>
        <stop offset="100%" stop-color="var(--backwater-bright)" stop-opacity="0"/>
      </linearGradient>
    </defs>
    ${dots}
  </svg>`;
}

/* ================= COMPLETE DIRECTORY ================= */
async function loadDirectory(){
  const wrap = document.getElementById('directoryWrap');
  try{
    const res = await fetch('/api/directory');
    const data = await res.json();
    const totalPlaces = data.states.reduce((a,s)=>a+s.places.length,0);
    document.getElementById('directoryCount').textContent =
      `${data.states.length} states &amp; UTs · ${totalPlaces} places — every one linked to Wikipedia`;
    wrap.innerHTML = data.states.map(s => `
      <div class="detail directory-state">
        <div class="detail-head">
          <div><h3>${s.name}</h3><div class="sub">${s.region} · ${s.places.length} destinations</div></div>
        </div>
        <p class="mono" style="color:var(--text-dim); font-size:0.82rem; line-height:1.6;">${s.culture_note}</p>
        <div class="grid" style="margin-top:12px;">
          ${s.places.map(p => `
            <div class="dcard" onclick="jumpToPlace('${s.key}','${p.id}')">
              <div class="dcard-top">
                <div><h3 style="font-size:1.05rem;">${p.name}</h3><div class="region">${p.type}</div></div>
                <span class="tag ${p.tag}">${p.tag.replace('-', ' ')}</span>
              </div>
              <div class="cultural-bar-wrap">
                <div class="cb-label"><span>Cultural weight</span><span>${p.cultural_weight}/100</span></div>
                <div class="bar-track"><div class="bar-fill cultural" style="width:${p.cultural_weight}%"></div></div>
              </div>
              ${p.safety_note ? `<div class="safety-note">⚠ ${p.safety_note}</div>` : ''}
              <a href="${p.wiki_url}" target="_blank" rel="noopener" class="wiki-link" onclick="event.stopPropagation();">Wikipedia →</a>
            </div>
          `).join('')}
        </div>
      </div>
    `).join('');
  } catch(e){
    wrap.innerHTML = '<div class="loading">Could not load the full directory right now.</div>';
  }
}

/* ================= ASK / RECOMMEND ================= */
async function runQuery(raw){
  const askBtn = document.getElementById('askBtn');
  askBtn.disabled = true; askBtn.textContent = 'Thinking…';
  const area = document.getElementById('responseArea');
  area.innerHTML = '<div class="loading">Pulling live weather and scoring destinations…</div>';
  try{
    const res = await fetch('/api/ask', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({query: raw})
    });
    const data = await res.json();
    renderResponse(raw, data);
  } catch(e){
    area.innerHTML = `<div class="rec-card"><div class="rec-body"><div class="verdict-line avoid"><span class="icon">⚠️</span><p>Something went wrong reaching the server. Please try again.</p></div></div></div>`;
  } finally {
    askBtn.disabled = false; askBtn.textContent = 'Ask →';
  }
}

function fmtBookBy(offset){
  if(offset <= 2) return 'today';
  const today = new Date();
  const d = new Date(today); d.setDate(d.getDate() + Math.max(0, offset-2));
  return DAY_NAMES[d.getDay()];
}

function renderResponse(raw, data){
  const area = document.getElementById('responseArea');

  if(data.mode === 'clarify'){
    const chips = data.sample_states.map(s => `<span class="chip" onclick="document.getElementById('queryInput').value='${s}'; runQuery('${s}');">${s}</span>`).join('');
    area.innerHTML = `
      <div class="rec-card">
        <div class="rec-head"><div class="ai-badge">AI</div><div class="q-text">"${raw}"</div></div>
        <div class="rec-body">
          <div class="verdict-line info">
            <span class="icon">🤔</span>
            <p>I couldn't quite pin down a destination in that query. TravelWise covers all <b>${data.total_states} Indian states &amp; UTs</b>, plus any place in the world via live lookup — try naming one, e.g.:</p>
          </div>
          <div class="chips">${chips}</div>
        </div>
      </div>`;
    return;
  }

  if(data.mode === 'not_found'){
    area.innerHTML = `
      <div class="rec-card">
        <div class="rec-head"><div class="ai-badge">AI</div><div class="q-text">"${raw}"</div></div>
        <div class="rec-body">
          <div class="verdict-line avoid">
            <span class="icon">⚠️</span>
            <p>I couldn't find "<b>${data.query_location}</b>" — check the spelling, or try one of the curated states below.</p>
          </div>
        </div>
      </div>`;
    return;
  }

  if(data.mode === 'directory'){
    const stateLines = data.states.map(s => `
      <div class="directory-line" style="margin-bottom:10px; line-height:1.7;">
        <b>${s.name}</b> <span class="mono" style="color:var(--text-dimmer); font-size:0.78rem;">(${s.region})</span>:
        ${s.places.map(p => `<a href="${p.wiki_url}" target="_blank" rel="noopener">${p.name}</a>`).join(', ')}
      </div>`).join('');
    area.innerHTML = `
      <div class="rec-card">
        <div class="rec-head"><div class="ai-badge">AI</div><div class="q-text">"${raw}"</div></div>
        <div class="rec-body">
          <div class="verdict-line info">
            <span class="icon">🗺️</span>
            <p>Here's everything TravelWise currently covers — <b>${data.total_states} states &amp; UTs</b>, <b>${data.total_places} curated destinations</b>, each linked to Wikipedia. The full browsable directory is further down the page.</p>
          </div>
          ${stateLines}
        </div>
      </div>`;
    return;
  }

  if(data.mode === 'freeform'){
    const cur = data.current, day = data.day_used, climate = data.climate, wiki = data.wiki;
    const bestMonths = data.best_months_names.join(', ');
    area.innerHTML = `
      <div class="rec-card">
        <div class="rec-head"><div class="ai-badge">AI</div><div class="q-text">"${raw}"</div></div>
        <div class="rec-body">
          <div class="verdict-line info">
            <span class="icon">📍</span>
            <p><b>${data.resolved_name}${data.admin1 ? ', ' + data.admin1 : ''}, ${data.country}</b> — not in our curated cultural database yet, but here's what live data shows.</p>
          </div>
          <div class="stat-row">
            <span class="stat-pill">${weatherEmoji(cur.condition)} now: <b>${cur.temperature_c}°C, ${cur.condition}</b></span>
            <span class="stat-pill">${data.day_label}: <b>${Math.round(day.tmax)}°/${Math.round(day.tmin)}°C, ${day.condition}</b></span>
            <span class="stat-pill">best months: <b>${bestMonths}</b></span>
          </div>
          <p style="color:var(--text-dim); font-size:0.9rem; line-height:1.6; margin-top:14px;">
            Best-time estimate is computed from ~2 years of historical daily temperature and rainfall for this location, favoring mild temperatures and lower rainfall.
          </p>
          <div class="review-quote wiki">
            ${wiki.extract}
            <br><a href="${wiki.url}" target="_blank" rel="noopener" class="wiki-link">Read more on Wikipedia →</a>
          </div>
          <div class="data-source ${cur.source !== 'live' ? 'offline' : ''}">
            weather: ${cur.source} · climate model: ${climate.source} · wikipedia: ${wiki.source}
          </div>
        </div>
      </div>`;
    return;
  }

  // mode === 'state'
  const { best, avoid, day_label, culture_note, state_name, best_months_names, is_peak_season_now, is_monsoon_now } = data;
  const sameAsAvoid = avoid.id === best.id;
  const crowdDiff = Math.max(0, Math.round(((avoid.crowd - best.crowd) / Math.max(avoid.crowd,1)) * 100));
  const priceDiff = avoid.price - best.price;
  const priceLine = priceDiff > 0 ? `₹${priceDiff} cheaper avg. accommodation`
                    : priceDiff < 0 ? `₹${Math.abs(priceDiff)} more, but worth it`
                    : `about the same price`;

  let verdictHtml;
  if(sameAsAvoid){
    verdictHtml = `
      <div class="verdict-line go">
        <span class="icon">✅</span>
        <p><b>${best.name} is a solid call ${day_label}.</b> Estimated crowd ${best.crowd}%, cultural weight ${best.cultural_weight}/100, and current weather is ${best.current.condition.toLowerCase()} at ${best.current.temperature_c}°C.</p>
      </div>`;
  } else {
    verdictHtml = `
      <div class="verdict-line avoid">
        <span class="icon">⚠️</span>
        <p><b>Avoid ${avoid.name} ${day_label}</b> — estimated ${avoid.crowd}% crowd based on typical weekly/seasonal patterns.</p>
      </div>
      <div class="verdict-line go">
        <span class="icon">✅</span>
        <p>Visit <b>${best.name}</b> instead: <b>${crowdDiff}% less estimated crowd</b>, ${priceLine}. Book by <b>${fmtBookBy(0)}</b> for the best rates.</p>
      </div>`;
  }

  const seasonNote = is_monsoon_now
    ? `<div class="verdict-line avoid"><span class="icon">🌧️</span><p>Heads up — ${state_name} is currently in its <b>monsoon window</b>. Best months are typically <b>${best_months_names.join(', ')}</b>.</p></div>`
    : is_peak_season_now
    ? `<div class="verdict-line go"><span class="icon">🗓️</span><p>Good timing — you're traveling in ${state_name}'s <b>peak season</b> (best months: ${best_months_names.join(', ')}).</p></div>`
    : `<div class="verdict-line info"><span class="icon">🗓️</span><p>${state_name}'s best months are typically <b>${best_months_names.join(', ')}</b>.</p></div>`;

  const top3 = [...data.places].sort((a,b)=>b.score-a.score).slice(0,3);
  const whyRows = top3.map(d => `<tr><td>${d.name}</td><td>crowd ${d.crowd}%</td><td>cultural ${d.cultural_weight}</td><td>weather fit ${d.weather_score}</td><td>budget fit ${d.budget_fit}</td><td>score ${d.score}</td></tr>`).join('');

  const allPlacesPills = [...data.places].sort((a,b)=>a.crowd-b.crowd).map(p =>
    `<a href="${p.wiki_url}" target="_blank" rel="noopener" style="text-decoration:none;"><span class="stat-pill">${p.name} — crowd ${p.crowd}% · cultural ${p.cultural_weight}</span></a>`
  ).join('');

  area.innerHTML = `
    <div class="rec-card">
      <div class="rec-head"><div class="ai-badge">AI</div><div class="q-text">"${raw}"</div></div>
      <div class="rec-body">
        <p class="mono" style="color:var(--text-dimmer); font-size:0.8rem; margin:0 0 12px;">${culture_note}</p>
        ${verdictHtml}
        ${seasonNote}
        <div class="stat-row">
          <span class="stat-pill">state: <b>${state_name}</b></span>
          <span class="stat-pill">budget: <b>${data.parsed.budget}</b></span>
          <span class="stat-pill">window: <b>${day_label}</b></span>
          <span class="stat-pill">top pick: <b>${best.name}</b></span>
        </div>
        <span class="why-toggle" onclick="this.nextElementSibling.classList.toggle('open')">show ranking logic ▾</span>
        <div class="why-panel">
          Ranked by estimated crowd, live weather fit, cultural weight (boosted if you mention culture/heritage), and budget fit.
          <table>${whyRows}</table>
        </div>
        <p class="mono" style="color:var(--text-dimmer); font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em; margin:18px 0 8px;">All destinations in ${state_name} (click for Wikipedia)</p>
        <div class="stat-row">${allPlacesPills}</div>
        <div class="data-source ${best.current.source !== 'live' ? 'offline' : ''}">weather source: ${best.current.source}</div>
      </div>
    </div>`;

  if(currentStateKey !== data.state_key){
    document.getElementById('stateSelect').value = data.state_key;
    loadState(data.state_key).then(()=> selectDestination(best.id));
  } else {
    selectDestination(best.id);
  }
}

/* ================= WIRE UP ================= */
document.getElementById('askBtn').addEventListener('click', ()=>{
  const v = document.getElementById('queryInput').value.trim();
  if(v) runQuery(v);
});
document.getElementById('queryInput').addEventListener('keydown', e=>{
  if(e.key==='Enter'){ const v=e.target.value.trim(); if(v) runQuery(v); }
});
document.querySelectorAll('.chip').forEach(chip=>{
  chip.addEventListener('click', ()=>{
    document.getElementById('queryInput').value = chip.dataset.q;
    runQuery(chip.dataset.q);
  });
});
document.getElementById('stateSelect').addEventListener('change', e=> loadState(e.target.value));

loadState('kerala');
loadExpert();
loadDirectory();
runQuery('Suggest a budget trip to Kerala next weekend avoiding crowds');

</script>
</body>
</html>
"""


@app.route("/")
def index():
    state_list = [{"key": k, "name": v["name"], "region": v["region"]} for k, v in STATES.items()]
    return render_template_string(HTML_TEMPLATE, states=state_list)


@app.route("/api/state/<state_key>")
def api_state(state_key):
    if state_key not in STATES:
        return jsonify({"error": "unknown state"}), 404
    state = STATES[state_key]
    places = []
    for p in state["places"]:
        cur, _ = get_current_and_forecast(p["lat"], p["lon"])
        places.append({**p, "current": cur})
    return jsonify({"key": state_key, "name": state["name"], "region": state["region"],
                    "culture_note": state["culture_note"], "places": places})


@app.route("/api/place/<state_key>/<place_id>")
def api_place_detail(state_key, place_id):
    if state_key not in STATES:
        return jsonify({"error": "unknown state"}), 404
    state = STATES[state_key]
    place = next((p for p in state["places"] if p["id"] == place_id), None)
    if not place:
        return jsonify({"error": "unknown place"}), 404
    cur, fc = get_current_and_forecast(place["lat"], place["lon"])
    wiki = get_wikipedia_summary(wiki_title_guess(place["name"]))
    return jsonify({"place": place, "current": cur, "forecast": fc, "state_name": state["name"],
                    "best_months": state["best_months"], "monsoon_months": state.get("monsoon_months", []),
                    "wiki": wiki})


@app.route("/api/directory")
def api_directory():
    states_out = []
    for skey, sval in STATES.items():
        places_out = []
        for p in sval["places"]:
            places_out.append({
                "id": p["id"], "name": p["name"], "type": p["type"], "desc": p["desc"],
                "cultural_weight": p["cultural_weight"], "price": p["price"], "tag": p["tag"],
                "safety_note": p.get("safety_note"),
                "wiki_url": get_wikipedia_link(wiki_title_guess(p["name"])),
            })
        states_out.append({"key": skey, "name": sval["name"], "region": sval["region"],
                           "culture_note": sval["culture_note"],
                           "best_months_names": [MONTH_NAMES[m] for m in sval["best_months"]],
                           "places": places_out})
    return jsonify({"states": states_out})


def _current_season_fit(state, month):
    if month in state["best_months"]:
        return 1.0
    if month in state.get("shoulder_months", []):
        return 0.5
    return 0.0


@app.route("/api/expert")
def api_expert():
    month = date.today().month
    all_places = []
    for skey, sval in STATES.items():
        for p in sval["places"]:
            all_places.append({**p, "state_key": skey, "state_name": sval["name"],
                               "region": sval["region"], "season_fit": _current_season_fit(sval, month)})

    culture_pick = max(all_places, key=lambda x: x["cultural_weight"])
    hidden = [p for p in all_places if p["tag"] == "hidden-gem"]
    hidden_gem_pick = max(hidden or all_places, key=lambda x: x["cultural_weight"] - x["crowd_base"] * 0.5)
    budget_pick = min(all_places, key=lambda x: x["price"])
    luxury_pick = max(all_places, key=lambda x: x["price"])
    in_season = [p for p in all_places if p["season_fit"] == 1.0]
    season_pick = max(in_season or all_places, key=lambda x: (x["season_fit"], x["cultural_weight"] - x["crowd_base"]))
    quiet_pick = min(all_places, key=lambda x: x["crowd_base"])

    picks = {"culture": culture_pick, "hidden_gem": hidden_gem_pick, "budget": budget_pick,
             "luxury": luxury_pick, "season": season_pick, "quiet": quiet_pick}
    result = {}
    for key, p in picks.items():
        wiki = get_wikipedia_summary(wiki_title_guess(p["name"]))
        result[key] = {"id": p["id"], "name": p["name"], "state_key": p["state_key"], "state_name": p["state_name"],
                       "type": p["type"], "desc": p["desc"], "cultural_weight": p["cultural_weight"],
                       "price": p["price"], "crowd_base": p["crowd_base"], "tag": p["tag"], "wiki": wiki}
    return jsonify({"month": MONTH_NAMES[month], "picks": result})


@app.route("/api/ask", methods=["POST"])
def api_ask():
    body = request.get_json(force=True, silent=True) or {}
    query = (body.get("query") or "").strip()
    if not query:
        return jsonify({"error": "empty query"}), 400
    result = recommend(query)
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)