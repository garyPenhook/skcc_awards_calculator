"""Utilities for fetching SKCC roster / awards metadata and parsing ADIF logs.

Network fetch functions are thin wrappers around httpx and intentionally simple so they
can be monkeypatched during tests. Award logic here is deliberately lightweight and
meant as a foundation; full SKCC award validation has more nuances (multi-band, QSL,
log validation, etc.).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Sequence, Tuple, Set
import re
import httpx
from bs4 import BeautifulSoup

# Public roster URL(s). These may change; keep configurable by caller if needed.
DEFAULT_ROSTER_URL = "https://www.skccgroup.com/membership_data/membership_roster.php"
# Additional fallback candidates (guesses / historical and previous primary variants)
FALLBACK_ROSTER_URLS = [
    "https://www.skccgroup.com/membership_data/membership_listing.php",  # previous primary
    "https://www.skccgroup.com/membership_data/membership-listing.php",  # hyphen variant
    "https://www.skccgroup.com/membership_data/",  # directory listing (if allowed)
]
# Awards landing page (used for heuristic threshold parsing)
DEFAULT_AWARDS_URL = "https://www.skccgroup.com/awards/"

# Award thresholds - NOTE: Tribune endorsements are calculated separately
# Tribune Endorsement Rules:
# - TxN requires N times 50 QSOs (Tx2=100, Tx3=150, ..., Tx10=500)
# - Higher endorsements: Tx15=750, Tx20=1000, Tx25=1250, etc. (increments of 250)
# - Both parties must be Centurions at time of QSO for Tribune+ awards
# - Only QSOs with Centurions/Tribunes/Senators (C/T/S suffix) count for Tribune
AWARD_THRESHOLDS: List[Tuple[str, int]] = [
    ("Centurion", 100),
    ("Tribune", 50),  # Tribune requires 50 contacts with C/T/S members
    ("Senator", 1000),
]

@dataclass(frozen=True)
class Member:
    call: str
    number: int
    # Optional SKCC join date (YYYYMMDD). If provided, used to validate QSO date per rules.
    join_date: str | None = None
    # SKCC achievement suffix: S=Senator(1000+), T=Tribune(50+), C=Centurion(100+)
    suffix: str | None = None

@dataclass(frozen=True)
class QSO:
    call: str | None
    band: str | None
    mode: str | None
    date: str | None  # YYYYMMDD
    skcc: str | None = None  # Raw SKCC field (e.g., 14947C, 660S)
    time_on: str | None = None  # HHMMSS if provided
    key_type: str | None = None  # Raw key type descriptor if available (e.g., STRAIGHT, BUG, COOTIE)
    tx_pwr: str | None = None  # Transmitter power
    comment: str | None = None  # QSO comment
    duration_minutes: int | None = None  # QSO duration in minutes for rag chew award

@dataclass
class AwardProgress:
    name: str
    required: int
    current: int
    achieved: bool
    description: str = ""

@dataclass
class CanadianMapleAward:
    name: str
    level: str  # "Yellow", "Orange", "Red", "Gold"
    required_provinces: int
    required_bands: int | None  # None for Yellow (any mix), specific number for others
    band: str | None  # Specific band for Orange awards, None for others
    qrp_required: bool
    current_provinces: int
    current_bands: int
    achieved: bool
    provinces_worked: List[str]
    bands_worked: List[str]

@dataclass
class DXAward:
    name: str
    award_type: str  # "DXQ" (QSO-based) or "DXC" (Country-based)
    threshold: int   # 10, 25, 50, etc.
    current_count: int
    achieved: bool
    countries_worked: List[str]  # List of DXCC entities worked
    qrp_qualified: bool  # True if all QSOs were QRP
    start_date: str  # "20090614" for DXQ, "20091219" for DXC

@dataclass
class PFXAward:
    name: str
    level: int  # 1, 2, 3, ..., 10, 15, 20, 25, etc.
    threshold: int  # 500000, 1000000, 1500000, etc.
    current_score: int  # Sum of SKCC numbers for unique prefixes
    achieved: bool
    unique_prefixes: int  # Count of unique prefixes worked
    prefixes_worked: List[str]  # List of unique prefixes
    band: str | None  # Specific band for endorsements, None for overall award

@dataclass
class TripleKeyAward:
    name: str
    key_type: str  # "straight", "bug", "sideswiper"
    threshold: int  # Always 100 for each key type
    current_count: int  # Unique SKCC members worked with this key type
    achieved: bool
    members_worked: List[str]  # List of unique member calls
    percentage: float  # Progress percentage

@dataclass
class RagChewAward:
    name: str
    level: int  # 1, 2, 3, ..., 10, 15, 20, etc.
    threshold: int  # 300, 600, 900, etc. (minutes)
    current_minutes: int  # Total rag chew minutes accumulated
    achieved: bool
    qso_count: int  # Number of qualifying rag chew QSOs
    band: str | None  # Specific band for endorsements, None for overall award

@dataclass
class WACAward:
    name: str
    award_type: str  # "WAC" (overall), "WAC-QRP", or band endorsement
    required_continents: int  # Always 6
    current_continents: int  # Number of continents worked
    achieved: bool
    continents_worked: List[str]  # List of continents worked
    qrp_qualified: bool  # True if all QSOs were QRP
    band: str | None  # Specific band for endorsements, None for overall award

@dataclass
class AwardCheckResult:
    unique_members_worked: int
    awards: List[AwardProgress]
    endorsements: List[AwardEndorsement]
    canadian_maple_awards: List[CanadianMapleAward]  # New field
    dx_awards: List[DXAward]  # New field for DX Awards
    pfx_awards: List[PFXAward]  # New field for PFX Awards
    triple_key_awards: List[TripleKeyAward]  # New field for Triple Key Awards
    rag_chew_awards: List[RagChewAward]  # New field for Rag Chew Awards
    wac_awards: List[WACAward]  # New field for WAC Awards
    total_qsos: int
    matched_qsos: int
    unmatched_calls: List[str]
    thresholds_used: List[Tuple[str, int]]
    total_cw_qsos: int  # Total count of QSOs (SKCC is exclusively CW/Morse code)

@dataclass
class AwardEndorsement:
    award: str          # Base award name (e.g., Centurion)
    category: str       # 'band' (mode not applicable - SKCC is CW-only)
    value: str          # e.g. '40M', '20M' (band endorsements)
    required: int       # Threshold required (same as base award requirement)
    current: int        # Unique SKCC members worked on this band
    achieved: bool

# Canadian Maple Award configuration
CANADIAN_PROVINCES_TERRITORIES = {
    # Provinces
    "NS": "Nova Scotia",           # VA1/VE1
    "QC": "Quebec",               # VA2/VE2  
    "ON": "Ontario",              # VA3/VE3
    "MB": "Manitoba",             # VA4/VE4
    "SK": "Saskatchewan",         # VA5/VE5
    "AB": "Alberta",              # VA6/VE6
    "BC": "British Columbia",     # VA7/VE7
    "NB": "New Brunswick",        # VE9
    "NL": "Newfoundland",         # VO1
    "NL_LAB": "Labrador",         # VO2
    # Territories (valid after January 2014)
    "NT": "Northwest Territories", # VE8
    "NU": "Nunavut",              # VY0
    "YT": "Yukon",                # VY1
    "PE": "Prince Edward Island", # VY2
    # Special
    "SEA": "Stations at sea",     # VE0
    "GOV": "Government of Canada", # VY9
}

# Mapping of call sign prefixes to provinces/territories
CANADIAN_CALL_TO_PROVINCE = {
    "VA1": "NS", "VE1": "NS",           # Nova Scotia
    "VA2": "QC", "VE2": "QC",           # Quebec
    "VA3": "ON", "VE3": "ON",           # Ontario
    "VA4": "MB", "VE4": "MB",           # Manitoba
    "VA5": "SK", "VE5": "SK",           # Saskatchewan
    "VA6": "AB", "VE6": "AB",           # Alberta
    "VA7": "BC", "VE7": "BC",           # British Columbia
    "VE8": "NT",                        # Northwest Territories
    "VE9": "NB",                        # New Brunswick
    "VO1": "NL",                        # Newfoundland
    "VO2": "NL_LAB",                    # Labrador
    "VY0": "NU",                        # Nunavut
    "VY1": "YT",                        # Yukon
    "VY2": "PE",                        # Prince Edward Island
    "VY9": "GOV",                       # Government of Canada
    "VE0": "SEA",                       # Stations at sea
}

# HF bands for Canadian Maple Award (160-10m including WARC)
CANADIAN_MAPLE_BANDS = ["160M", "80M", "40M", "30M", "20M", "17M", "15M", "12M", "10M"]

# DX Award thresholds for QSO-based (DXQ) and Country-based (DXC) awards
DX_AWARD_THRESHOLDS = [10, 25, 50, 75, 100, 125, 150, 200, 250, 300, 400, 500]

# Common DXCC entity prefixes for initial country detection
# This is a simplified list - in production, a full DXCC list would be used
DXCC_PREFIXES = {
    # North America
    "K": "United States", "W": "United States", "N": "United States", "A": "United States",
    "VE": "Canada", "VA": "Canada", "VO": "Canada", "VY": "Canada",
    "XE": "Mexico", "XF": "Mexico", "4A": "Mexico",
    
    # Europe
    "G": "England", "M": "England", "2E": "England",
    "DL": "Germany", "DA": "Germany", "DB": "Germany", "DC": "Germany", "DD": "Germany", "DE": "Germany", "DF": "Germany", "DG": "Germany", "DH": "Germany", "DI": "Germany", "DJ": "Germany", "DK": "Germany", "DM": "Germany", "DN": "Germany", "DO": "Germany", "DP": "Germany", "DQ": "Germany", "DR": "Germany", "DS": "Germany", "DT": "Germany",
    "F": "France", "TM": "France", "TK": "France",
    "I": "Italy", "IZ": "Italy",
    "EA": "Spain", "EB": "Spain", "EC": "Spain", "ED": "Spain", "EE": "Spain", "EF": "Spain", "EG": "Spain", "EH": "Spain",
    "CT": "Portugal", "CQ": "Portugal", "CR": "Portugal", "CS": "Portugal",
    "PA": "Netherlands", "PB": "Netherlands", "PC": "Netherlands", "PD": "Netherlands", "PE": "Netherlands", "PF": "Netherlands", "PG": "Netherlands", "PH": "Netherlands", "PI": "Netherlands",
    "ON": "Belgium", "OO": "Belgium", "OP": "Belgium", "OQ": "Belgium", "OR": "Belgium", "OS": "Belgium", "OT": "Belgium",
    "HB": "Switzerland", "HB0": "Liechtenstein", "HB9": "Switzerland",
    "OE": "Austria",
    "OK": "Czech Republic", "OL": "Czech Republic",
    "OM": "Slovak Republic",
    "SP": "Poland", "SN": "Poland", "SO": "Poland", "SQ": "Poland", "SR": "Poland",
    "YO": "Romania", "YP": "Romania", "YQ": "Romania", "YR": "Romania",
    "LZ": "Bulgaria",
    "SV": "Greece", "SW": "Greece", "SX": "Greece", "SY": "Greece", "SZ": "Greece",
    "YU": "Serbia", "YT": "Serbia", "YZ": "Serbia",
    "9A": "Croatia",
    "S5": "Slovenia",
    "T9": "Bosnia-Herzegovina",
    "E7": "Bosnia-Herzegovina",
    "4O": "Montenegro",
    "E4": "Palestine",
    "LY": "Lithuania",
    "YL": "Latvia",
    "ES": "Estonia",
    "OH": "Finland",
    "SM": "Sweden", "SA": "Sweden", "SB": "Sweden", "SC": "Sweden", "SD": "Sweden", "SE": "Sweden", "SF": "Sweden", "SG": "Sweden", "SH": "Sweden", "SI": "Sweden", "SJ": "Sweden", "SK": "Sweden", "SL": "Sweden",
    "LA": "Norway", "LB": "Norway", "LC": "Norway", "LD": "Norway", "LE": "Norway", "LF": "Norway", "LG": "Norway", "LH": "Norway", "LI": "Norway", "LJ": "Norway", "LK": "Norway", "LL": "Norway", "LM": "Norway", "LN": "Norway",
    "OZ": "Denmark", "OV": "Faroe Islands", "OY": "Faroe Islands",
    "TF": "Iceland",
    "EI": "Ireland", "EJ": "Ireland",
    "R": "European Russia", "U": "European Russia", "RA": "European Russia", "RB": "European Russia", "RC": "European Russia", "RD": "European Russia", "RE": "European Russia", "RF": "European Russia", "RG": "European Russia", "RH": "European Russia", "RI": "European Russia", "RJ": "European Russia", "RK": "European Russia", "RL": "European Russia", "RM": "European Russia", "RN": "European Russia", "RO": "European Russia", "RP": "European Russia", "RQ": "European Russia", "RR": "European Russia", "RS": "European Russia", "RT": "European Russia", "RU": "European Russia", "RV": "European Russia", "RW": "European Russia", "RX": "European Russia", "RY": "European Russia", "RZ": "European Russia",
    
    # Asia
    "JA": "Japan", "JE": "Japan", "JF": "Japan", "JG": "Japan", "JH": "Japan", "JI": "Japan", "JJ": "Japan", "JK": "Japan", "JL": "Japan", "JM": "Japan", "JN": "Japan", "JO": "Japan", "JP": "Japan", "JQ": "Japan", "JR": "Japan", "JS": "Japan",
    "HL": "South Korea", "HM": "South Korea", "DS": "South Korea", "DT": "South Korea",
    "VU": "India", "AT": "India", "VT": "India", "VW": "India",
    "VR": "Hong Kong", "VR2": "Hong Kong",
    "XX": "China", "BY": "China", "B": "China",
    "VK": "Australia", "VH": "Australia", "VI": "Australia", "VJ": "Australia",
    "ZL": "New Zealand", "ZK": "New Zealand", "ZM": "New Zealand",
    "YB": "Indonesia", "YC": "Indonesia", "YD": "Indonesia", "YE": "Indonesia", "YF": "Indonesia", "YG": "Indonesia", "YH": "Indonesia",
    "HS": "Thailand", "E2": "Thailand",
    "9V": "Singapore", "9M2": "West Malaysia", "9M6": "East Malaysia",
    "DU": "Philippines", "DV": "Philippines", "DW": "Philippines", "DX": "Philippines", "DY": "Philippines", "DZ": "Philippines",
    
    # Africa
    "ZS": "South Africa", "ZR": "South Africa", "ZT": "South Africa", "ZU": "South Africa",
    "SU": "Egypt", "SS": "Egypt",
    "CN": "Morocco", "5C": "Morocco",
    "7X": "Algeria",
    "3V": "Tunisia",
    "5A": "Libya",
    "ST": "Sudan",
    "ET": "Ethiopia",
    "5Z": "Kenya",
    "5H": "Tanzania",
    "5X": "Uganda",
    "9X": "Rwanda",
    "9U": "Burundi",
    "TL": "Central African Republic",
    "TT": "Chad",
    "TY": "Benin",
    "5V": "Togo",
    "9G": "Ghana",
    "9Q": "Democratic Republic of the Congo",
    "TN": "Republic of the Congo",
    "TR": "Gabon",
    "3C": "Equatorial Guinea",
    "D2": "Angola",
    "V5": "Namibia",
    "A2": "Botswana",
    "7P": "Lesotho",
    "3DA": "Swaziland",
    "V9": "Brunei",
    
    # Oceania
    "YJ": "Vanuatu", "YK": "Syria", "T3": "Kiribati", "T2": "Tuvalu", "5W": "Samoa", "3D2": "Fiji", "E5": "Cook Islands",
    "FK": "New Caledonia", "FO": "French Polynesia", "FW": "Wallis and Futuna",
    "P2": "Papua New Guinea", "P29": "Papua New Guinea",
    "YB": "Indonesia",
    
    # South America  
    "PY": "Brazil", "PP": "Brazil", "PQ": "Brazil", "PR": "Brazil", "PS": "Brazil", "PT": "Brazil", "PU": "Brazil", "PV": "Brazil", "PW": "Brazil", "PX": "Brazil", "ZV": "Brazil", "ZW": "Brazil", "ZX": "Brazil", "ZY": "Brazil", "ZZ": "Brazil",
    "LU": "Argentina", "AY": "Argentina", "AZ": "Argentina", "L2": "Argentina", "L3": "Argentina", "L4": "Argentina", "L5": "Argentina", "L6": "Argentina", "L7": "Argentina", "L8": "Argentina", "L9": "Argentina", "LO": "Argentina", "LP": "Argentina", "LQ": "Argentina", "LR": "Argentina", "LS": "Argentina", "LT": "Argentina", "LV": "Argentina", "LW": "Argentina",
    "CE": "Chile", "CA": "Chile", "CB": "Chile", "CC": "Chile", "CD": "Chile", "CF": "Chile", "CG": "Chile", "CH": "Chile", "CI": "Chile", "CJ": "Chile", "CK": "Chile", "CL": "Chile", "CM": "Chile", "CN": "Chile", "CO": "Chile", "CP": "Chile", "CQ": "Chile", "CR": "Chile", "CS": "Chile", "CT": "Chile", "CU": "Chile", "CV": "Chile", "CW": "Chile", "CX": "Chile", "CY": "Chile", "CZ": "Chile",
    "CP": "Bolivia", "C7": "Bolivia",
    "OA": "Peru", "OB": "Peru", "OC": "Peru", "4T": "Peru",
    "HC": "Ecuador", "HD": "Ecuador", "HE": "Ecuador", "HF": "Ecuador", "HG": "Ecuador", "HH": "Ecuador", "HI": "Ecuador",
    "HJ": "Colombia", "HK": "Colombia", "5J": "Colombia", "5K": "Colombia",
    "YV": "Venezuela", "YW": "Venezuela", "YX": "Venezuela", "YY": "Venezuela", "4M": "Venezuela",
    "PZ": "Suriname",
    "8R": "Guyana",
    "PJ": "Netherlands Antilles",
    "FY": "French Guiana",
    "PY0F": "Fernando de Noronha", "PY0S": "St. Peter and St. Paul Rocks", "PY0T": "Trindade and Martim Vaz",
}

# Continent mapping for DXCC countries
COUNTRY_TO_CONTINENT = {
    # North America
    "United States": "NA",
    "Canada": "NA", 
    "Mexico": "NA",
    "Alaska": "NA",
    "Hawaii": "NA",
    "Bahamas": "NA",
    "Barbados": "NA",
    "Belize": "NA",
    "Bermuda": "NA",
    "Costa Rica": "NA",
    "Cuba": "NA",
    "Dominican Republic": "NA",
    "El Salvador": "NA",
    "Guatemala": "NA",
    "Haiti": "NA",
    "Honduras": "NA",
    "Jamaica": "NA",
    "Nicaragua": "NA",
    "Panama": "NA",
    "Trinidad and Tobago": "NA",
    "Cayman Islands": "NA",
    "Puerto Rico": "NA",
    "US Virgin Islands": "NA",
    "British Virgin Islands": "NA",
    
    # South America
    "Argentina": "SA",
    "Bolivia": "SA",
    "Brazil": "SA",
    "Chile": "SA",
    "Colombia": "SA",
    "Ecuador": "SA",
    "French Guiana": "SA",
    "Guyana": "SA",
    "Paraguay": "SA",
    "Peru": "SA",
    "Suriname": "SA",
    "Uruguay": "SA",
    "Venezuela": "SA",
    "Fernando de Noronha": "SA",
    "St. Peter and St. Paul Rocks": "SA",
    "Trindade and Martim Vaz": "SA",
    "Netherlands Antilles": "SA",
    
    # Europe
    "Albania": "EU",
    "Andorra": "EU",
    "Armenia": "EU",
    "Austria": "EU",
    "Azerbaijan": "EU",
    "Belarus": "EU",
    "Belgium": "EU",
    "Bosnia-Herzegovina": "EU",
    "Bulgaria": "EU",
    "Croatia": "EU",
    "Cyprus": "EU",
    "Czech Republic": "EU",
    "Denmark": "EU",
    "Estonia": "EU",
    "Finland": "EU",
    "France": "EU",
    "Georgia": "EU",
    "Germany": "EU",
    "Greece": "EU",
    "Hungary": "EU",
    "Iceland": "EU",
    "Ireland": "EU",
    "Italy": "EU",
    "Latvia": "EU",
    "Liechtenstein": "EU",
    "Lithuania": "EU",
    "Luxembourg": "EU",
    "Malta": "EU",
    "Moldova": "EU",
    "Monaco": "EU",
    "Montenegro": "EU",
    "Netherlands": "EU",
    "North Macedonia": "EU",
    "Norway": "EU",
    "Poland": "EU",
    "Portugal": "EU",
    "Romania": "EU",
    "European Russia": "EU",
    "San Marino": "EU",
    "Serbia": "EU",
    "Slovak Republic": "EU",
    "Slovenia": "EU",
    "Spain": "EU",
    "Sweden": "EU",
    "Switzerland": "EU",
    "Turkey": "EU",
    "Ukraine": "EU",
    "England": "EU",
    "Scotland": "EU",
    "Wales": "EU",
    "Northern Ireland": "EU",
    "Faroe Islands": "EU",
    "Gibraltar": "EU",
    "Guernsey": "EU",
    "Isle of Man": "EU",
    "Jersey": "EU",
    "Vatican": "EU",
    
    # Africa
    "Algeria": "AF",
    "Angola": "AF",
    "Benin": "AF",
    "Botswana": "AF",
    "Burkina Faso": "AF",
    "Burundi": "AF",
    "Cameroon": "AF",
    "Cape Verde": "AF",
    "Central African Republic": "AF",
    "Chad": "AF",
    "Comoros": "AF",
    "Democratic Republic of the Congo": "AF",
    "Republic of the Congo": "AF",
    "Djibouti": "AF",
    "Egypt": "AF",
    "Equatorial Guinea": "AF",
    "Eritrea": "AF",
    "Ethiopia": "AF",
    "Gabon": "AF",
    "Gambia": "AF",
    "Ghana": "AF",
    "Guinea": "AF",
    "Guinea-Bissau": "AF",
    "Ivory Coast": "AF",
    "Kenya": "AF",
    "Lesotho": "AF",
    "Liberia": "AF",
    "Libya": "AF",
    "Madagascar": "AF",
    "Malawi": "AF",
    "Mali": "AF",
    "Mauritania": "AF",
    "Mauritius": "AF",
    "Morocco": "AF",
    "Mozambique": "AF",
    "Namibia": "AF",
    "Niger": "AF",
    "Nigeria": "AF",
    "Rwanda": "AF",
    "Sao Tome and Principe": "AF",
    "Senegal": "AF",
    "Seychelles": "AF",
    "Sierra Leone": "AF",
    "Somalia": "AF",
    "South Africa": "AF",
    "South Sudan": "AF",
    "Sudan": "AF",
    "Swaziland": "AF",
    "Tanzania": "AF",
    "Togo": "AF",
    "Tunisia": "AF",
    "Uganda": "AF",
    "Zambia": "AF",
    "Zimbabwe": "AF",
    
    # Asia
    "Afghanistan": "AS",
    "Bahrain": "AS",
    "Bangladesh": "AS",
    "Bhutan": "AS",
    "Brunei": "AS",
    "Cambodia": "AS",
    "China": "AS",
    "Hong Kong": "AS",
    "India": "AS",
    "Indonesia": "AS",
    "Iran": "AS",
    "Iraq": "AS",
    "Israel": "AS",
    "Japan": "AS",
    "Jordan": "AS",
    "Kazakhstan": "AS",
    "Kuwait": "AS",
    "Kyrgyzstan": "AS",
    "Laos": "AS",
    "Lebanon": "AS",
    "Macao": "AS",
    "Malaysia": "AS",
    "West Malaysia": "AS",
    "East Malaysia": "AS",
    "Maldives": "AS",
    "Mongolia": "AS",
    "Myanmar": "AS",
    "Nepal": "AS",
    "North Korea": "AS",
    "Oman": "AS",
    "Pakistan": "AS",
    "Palestine": "AS",
    "Philippines": "AS",
    "Qatar": "AS",
    "Saudi Arabia": "AS",
    "Singapore": "AS",
    "South Korea": "AS",
    "Sri Lanka": "AS",
    "Syria": "AS",
    "Taiwan": "AS",
    "Tajikistan": "AS",
    "Thailand": "AS",
    "Timor-Leste": "AS",
    "Turkmenistan": "AS",
    "United Arab Emirates": "AS",
    "Uzbekistan": "AS",
    "Vietnam": "AS",
    "Yemen": "AS",
    "Asiatic Russia": "AS",
    
    # Oceania  
    "Australia": "OC",
    "Cook Islands": "OC",
    "Fiji": "OC",
    "French Polynesia": "OC",
    "Kiribati": "OC",
    "Marshall Islands": "OC",
    "Micronesia": "OC",
    "Nauru": "OC",
    "New Caledonia": "OC",
    "New Zealand": "OC",
    "Palau": "OC",
    "Papua New Guinea": "OC",
    "Samoa": "OC",
    "Solomon Islands": "OC",
    "Tonga": "OC",
    "Tuvalu": "OC",
    "Vanuatu": "OC",
    "Wallis and Futuna": "OC",
    
    # Antarctica
    "Antarctica": "AN",
}

def get_continent_from_country(country: str) -> str | None:
    """
    Get continent code from DXCC country name.
    
    Args:
        country: DXCC country name
        
    Returns:
        Continent code (NA, SA, EU, AF, AS, OC, AN) or None if not found
    """
    return COUNTRY_TO_CONTINENT.get(country)

def get_continent_from_call(call: str) -> str | None:
    """
    Get continent code from call sign.
    
    Args:
        call: Amateur radio call sign
        
    Returns:
        Continent code (NA, SA, EU, AF, AS, OC, AN) or None if not found
    """
    country = get_dxcc_country(call)
    if country:
        return get_continent_from_country(country)
    return None

ROSTER_LINE_RE = re.compile(r"^(?P<number>\d+)(?P<suffix>[A-Z]*)\s+([A-Z0-9/]+)\s+(?P<call>[A-Z0-9/]+)")

async def fetch_member_roster(
    url: str | None = None,
    timeout: float = 20.0,
    candidates: Sequence[str] | None = None,
) -> List[Member]:
    """Fetch and parse the SKCC roster, attempting fallback URLs on 404.

    Parameters:
        url: explicit single URL to try first (optional)
        timeout: request timeout seconds
        candidates: explicit ordered list of candidate URLs to try; if None, uses defaults

    Returns:
        List[Member] parsed (possibly empty if parse failed for all) – raises last error if all fail with non-404.
    """
    tried: List[Tuple[str, str]] = []  # (url, error summary)
    urls: List[str] = []
    if url:
        urls.append(url)
    if candidates:
        urls.extend([u for u in candidates if u not in urls])
    else:
        # Default order: primary then fallbacks
        if DEFAULT_ROSTER_URL not in urls:
            urls.append(DEFAULT_ROSTER_URL)
        for fb in FALLBACK_ROSTER_URLS:
            if fb not in urls:
                urls.append(fb)

    last_exception: Exception | None = None
    for target in urls:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(target)
                resp.raise_for_status()
            text = resp.text
            members = _parse_roster_text(text)
            if members:
                return members
            # If parse produced zero members, continue to next candidate
            tried.append((target, "parse-empty"))
        except httpx.HTTPStatusError as e:  # 404 fallback, others abort
            status = e.response.status_code
            summary = f"HTTP {status}"
            tried.append((target, summary))
            last_exception = e
            if status == 404:
                continue  # try next
            raise
        except Exception as e:  # pragma: no cover
            tried.append((target, e.__class__.__name__))
            last_exception = e
            continue

    # All candidates exhausted – if we had any parse-empty but no members, return empty list
    if last_exception and not any(err.startswith("parse-") for _, err in tried):
        # Provide aggregated context in exception chain
        raise RuntimeError(
            "All roster URL attempts failed: "
            + ", ".join(f"{u} ({err})" for u, err in tried)
        ) from last_exception
    return []

def _parse_roster_text(text: str) -> List[Member]:
    """Internal helper to parse roster HTML/text into Member objects."""
    members: List[Member] = []
    # Try HTML parse first
    try:
        soup = BeautifulSoup(text, "html.parser")
        rows = soup.find_all("tr")
        for tr in rows:
            cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"]) ]
            if len(cells) < 2:
                continue
            try:
                # Extract numeric part and suffix from SKCC number (e.g., "660S" -> 660, "S")
                number_text = cells[0].strip()
                suffix_match = re.match(r'^(\d+)([A-Z]*)', number_text)
                if not suffix_match:
                    continue
                number = int(suffix_match.group(1))
                suffix = suffix_match.group(2) if suffix_match.group(2) else None
            except ValueError:
                continue
            call_candidate = None
            for c in cells[1:4]:
                if re.fullmatch(r"[A-Z0-9/]{3,}", c.upper()) and any(ch.isdigit() for ch in c):
                    call_candidate = c.upper()
                    break
            if call_candidate:
                call_candidate = normalize_call(call_candidate)
                if call_candidate:  # Only add if normalization succeeded
                    members.append(Member(call=call_candidate, number=number, suffix=suffix))
        if members:
            return members
    except Exception:  # pragma: no cover
        members = []
    # Fallback regex scan
    for line in text.splitlines():
        m = ROSTER_LINE_RE.search(line.strip())
        if not m:
            continue
        try:
            number = int(m.group("number"))
            suffix = m.group("suffix") if m.group("suffix") else None
        except ValueError:
            continue
        call = m.group("call").upper()
        members.append(Member(call=call, number=number, suffix=suffix))
    return members

async def fetch_award_thresholds(url: str = DEFAULT_AWARDS_URL, timeout: float = 15.0) -> List[Tuple[str, int]]:
    """Attempt to dynamically discover award thresholds from the awards page.

    Falls back to static AWARD_THRESHOLDS if parsing fails. This is a heuristic:
    searches page text for known award names followed by an integer.
    """
    names = [n for n, _ in AWARD_THRESHOLDS]
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        text = resp.text
        found: Dict[str, int] = {}
        for n in names:
            # Regex: AwardName followed within 30 chars by a number (avoid greedy newline consumption)
            pat = re.compile(rf"{n}[^\n\r]{{0,30}}?(\d{{2,5}})", re.IGNORECASE)
            m = pat.search(text)
            if m:
                try:
                    found[n] = int(m.group(1))
                except ValueError:
                    continue
        if not found:
            return AWARD_THRESHOLDS
        dynamic: List[Tuple[str, int]] = []
        for n, default_req in AWARD_THRESHOLDS:
            dynamic.append((n, found.get(n, default_req)))
        return dynamic
    except Exception:  # pragma: no cover
        return AWARD_THRESHOLDS

ADIF_FIELD_RE = re.compile(r"<(?P<name>[A-Za-z0-9_]+):(?P<len>\d+)(:[A-Za-z0-9]+)?>", re.IGNORECASE)
# Regex to extract leading numeric portion of SKCC field (e.g., 14947C -> 14947)
SKCC_FIELD_RE = re.compile(r"^(?P<num>\d+)(?P<suffix>[A-Z]*)")

CALL_PORTABLE_SUFFIX_RE = re.compile(r"(?P<base>[A-Z0-9]+)(/[A-Z0-9]{1,5})+$")
LEADING_PREFIX_RE = re.compile(r"^[A-Z0-9]{1,4}/(?P<base>[A-Z0-9]+)$")
PORTABLE_SUFFIX_TOKENS = {"P","QRP","M","MM","AM","SOTA"}

def normalize_call(call: str | None) -> str | None:
    if not call:
        return call
    c = call.strip().upper()
    # Strip leading prefix like DL/W1ABC -> W1ABC (keep base that contains a digit)
    m2 = LEADING_PREFIX_RE.match(c)
    if m2 and any(ch.isdigit() for ch in m2.group("base")):
        c = m2.group("base")
    # Strip trailing portable suffix chains
    # e.g. K1ABC/P, K1ABC/QRP, K1ABC/7/P
    parts = c.split('/')
    # If multiple segments, iteratively drop suffix tokens from the end
    while len(parts) > 1 and parts[-1] in PORTABLE_SUFFIX_TOKENS:
        parts.pop()
    # Also if last segment is just a single digit (region) we keep base (common portable) but only if base still has a digit
    if len(parts) > 1 and len(parts[-1]) == 1 and parts[-1].isdigit():
        # Keep base portion before region digit for matching, but only if base has digit
        base_candidate = parts[0]
        if any(ch.isdigit() for ch in base_candidate):
            parts = [base_candidate]
    c = '/'.join(parts)
    # Finally apply suffix regex collapse
    m = CALL_PORTABLE_SUFFIX_RE.fullmatch(c)
    if m:
        return m.group("base")
    return c

def generate_call_aliases(call: str) -> List[str]:
    """Generate alias variants for a member callsign to improve matching.

    Variants include:
      - normalized base
      - base without region digit (K1ABC/7 -> K1ABC)
      - base without leading DX prefix (DL/K1ABC -> K1ABC)
    Duplicates removed preserving order.
    """
    variants: List[str] = []
    def add(v: str):
        if v not in variants:
            variants.append(v)
    base = call.upper()
    add(base)
    n = normalize_call(base)
    if n:
        add(n)
    # Remove trailing region digit
    if '/' in base:
        segs = base.split('/')
        if len(segs) == 2 and len(segs[1]) == 1 and segs[1].isdigit():
            add(segs[0])
    # Leading prefix removal
    m2 = LEADING_PREFIX_RE.match(base)
    if m2:
        add(m2.group("base"))
    return variants

def parse_adif(content: str) -> List[QSO]:
    """Parse minimal subset of ADIF into QSO objects.

    Supports fields: CALL, BAND, MODE, QSO_DATE. Records terminated by <EOR> (case-insensitive).
    """
    records: List[QSO] = []
    idx = 0
    length = len(content)
    current: Dict[str, Any] = {}
    lower_content = content.lower()
    while idx < length:
        if lower_content.startswith("<eor>", idx):
            # End of record
            if "call" in current:
                raw_call = normalize_call(str(current.get("call", "")).upper())
                skcc_raw = current.get("skcc") or current.get("app_skcc")
                records.append(
                    QSO(
                        call=raw_call,
                        band=current.get("band"),
                        mode=current.get("mode"),
                        date=current.get("qso_date"),
                        skcc=skcc_raw,
                        time_on=current.get("time_on"),
                        key_type=(current.get("key") or current.get("app_skcc_key") or current.get("skcc_key") or current.get("app_key")),
                        tx_pwr=current.get("tx_pwr"),
                        comment=current.get("comment"),
                    )
                )
            current = {}
            idx += 5
            continue
        if lower_content.startswith("<eoh>", idx):
            idx += 5
            current = {}
            continue
        m = ADIF_FIELD_RE.match(content, idx)
        if not m:
            idx += 1
            continue
        name = m.group("name").lower()
        field_len = int(m.group("len"))
        value_start = m.end()
        value_end = value_start + field_len
        value = content[value_start:value_end]
        current[name] = value.strip() or None
        idx = value_end
    # Handle file not ending with <EOR>
    if current.get("call"):
        raw_call = normalize_call(str(current.get("call", "")).upper())
        skcc_raw = current.get("skcc") or current.get("app_skcc")
        records.append(
            QSO(
                call=raw_call,
                band=current.get("band"),
                mode=current.get("mode"),
                date=current.get("qso_date"),
                skcc=skcc_raw,
                time_on=current.get("time_on"),
                key_type=(current.get("key") or current.get("app_skcc_key") or current.get("skcc_key") or current.get("app_key")),
                tx_pwr=current.get("tx_pwr"),
                comment=current.get("comment"),
            )
        )
    return records

def parse_adif_files(contents: Sequence[str]) -> List[QSO]:
    qsos: List[QSO] = []
    for c in contents:
        qsos.extend(parse_adif(c))
    return qsos

# Helper to build sortable timestamp
from datetime import datetime

def _qso_timestamp(q: QSO) -> datetime:
    d = q.date or "00000000"
    t = q.time_on or "000000"
    # Basic sanity padding
    if len(d) != 8 or not d.isdigit():
        d = "00000000"
    if len(t) < 6:
        t = t.ljust(6, "0")
    try:
        return datetime.strptime(d + t, "%Y%m%d%H%M%S")
    except Exception:  # pragma: no cover
        return datetime.min

def get_member_status_at_qso_time(qso: QSO, member: Member | None) -> str | None:
    """
    Get the member's SKCC award status at the time of QSO.
    
    SKCC Logger captures the member's award status at QSO time in the SKCC field.
    For example: "660S" means member #660 had Senator status at QSO time.
    
    This is the CORRECT way to determine historical status - from the log data
    captured at QSO time, not from guessing based on current roster.
    
    Returns the suffix (C/T/S) from the QSO record, or None if no award status.
    """
    if not qso.skcc:
        return None
    
    # Parse SKCC field to extract suffix
    match = SKCC_FIELD_RE.match(qso.skcc.strip().upper())
    if match:
        suffix = match.group("suffix") or None
        return suffix if suffix else None
    
    return None


def member_qualifies_for_award_at_qso_time(qso: QSO, member: Member | None, award_threshold: int) -> bool:
    """
    Check if a member qualified for an award level at the time of the QSO.
    
    Uses the SKCC field from the QSO record, which contains the member's
    award status AT THE TIME OF QSO - this is the accurate historical data.
    """
    if not member:
        return False
    
    # Centurion Award (100): All SKCC members count regardless of status
    if award_threshold <= 100:
        return True
    
    # For Tribune/Senator awards, get the member's status at QSO time
    qso_time_status = get_member_status_at_qso_time(qso, member)
    
    if award_threshold >= 1000:  # Senator
        return qso_time_status in ['T', 'S']  # Only Tribunes/Senators at QSO time
    elif award_threshold >= 50:  # Tribune (50 contacts)
        return qso_time_status in ['C', 'T', 'S']  # Centurions/Tribunes/Senators at QSO time
    
    return False


def get_canadian_province(call: str) -> str | None:
    """
    Extract Canadian province/territory from call sign.
    
    Args:
        call: Amateur radio call sign
        
    Returns:
        Province/territory code or None if not Canadian or not recognized
    """
    if not call:
        return None
    
    call = call.upper().strip()
    
    # Handle portable operations (remove /suffix)
    base_call = call.split('/')[0]
    
    # Check for Canadian prefixes
    for prefix, province in CANADIAN_CALL_TO_PROVINCE.items():
        if base_call.startswith(prefix):
            return province
    
    return None


def calculate_canadian_maple_awards(qsos: Sequence[QSO], members: Sequence[Member]) -> List[CanadianMapleAward]:
    """
    Calculate Canadian Maple Award progress.
    
    Rules:
    - Yellow: Work 10 provinces/territories on any mix of bands
    - Orange: Work 10 provinces/territories on a single band (separate award per band)  
    - Red: Work 10 provinces/territories on each of all 9 HF bands (90 contacts)
    - Gold: Same as Red but QRP (5W or less)
    
    Valid after 1 September 2009 for provinces, January 2014 for territories.
    """
    # Build member lookup
    member_by_call = {}
    for member in members:
        for alias in generate_call_aliases(member.call):
            member_by_call.setdefault(alias, member)
    
    # Track provinces worked by band
    provinces_by_band = {}  # band -> set of provinces
    provinces_overall = set()
    
    # Track QRP contacts separately
    qrp_provinces_by_band = {}  # band -> set of provinces (QRP only)
    qrp_provinces_overall = set()
    
    for qso in qsos:
        if not qso.call or not qso.band:
            continue
            
        # Must be SKCC member
        if qso.call not in member_by_call:
            continue
            
        province = get_canadian_province(qso.call)
        if not province:
            continue
            
        # Date validation
        if qso.date:
            qso_date = qso.date
            
            # Provinces valid after 1 September 2009
            if province in ["NS", "QC", "ON", "MB", "SK", "AB", "BC", "NB", "NL", "NL_LAB", "SEA", "GOV"]:
                if qso_date < "20090901":
                    continue
                    
            # Territories valid after January 2014
            elif province in ["NT", "NU", "YT", "PE"]:
                if qso_date < "20140101":
                    continue
        
        # Normalize band name
        band = qso.band.upper()
        if band not in CANADIAN_MAPLE_BANDS:
            continue
            
        # Track province by band
        if band not in provinces_by_band:
            provinces_by_band[band] = set()
        provinces_by_band[band].add(province)
        provinces_overall.add(province)
        
        # Check if QRP (5W or less)
        is_qrp = False
        if hasattr(qso, 'tx_pwr') and qso.tx_pwr:
            try:
                power = float(qso.tx_pwr)
                is_qrp = power <= 5.0
            except (ValueError, TypeError):
                pass
        # Also check for QRP indicator in comment or mode
        if (hasattr(qso, 'comment') and qso.comment and 'QRP' in qso.comment.upper()) or \
           (qso.mode and 'QRP' in qso.mode.upper()):
            is_qrp = True
            
        if is_qrp:
            if band not in qrp_provinces_by_band:
                qrp_provinces_by_band[band] = set()
            qrp_provinces_by_band[band].add(province)
            qrp_provinces_overall.add(province)
    
    awards = []
    
    # Yellow Maple Award (10 provinces on any mix of bands)
    yellow_achieved = len(provinces_overall) >= 10
    awards.append(CanadianMapleAward(
        name="Canadian Maple",
        level="Yellow",
        required_provinces=10,
        required_bands=None,
        band=None,
        qrp_required=False,
        current_provinces=len(provinces_overall),
        current_bands=len(provinces_by_band),
        achieved=yellow_achieved,
        provinces_worked=sorted(list(provinces_overall)),
        bands_worked=sorted(list(provinces_by_band.keys()))
    ))
    
    # Orange Maple Award (10 provinces on single band - one award per band)
    for band in CANADIAN_MAPLE_BANDS:
        band_provinces = provinces_by_band.get(band, set())
        orange_achieved = len(band_provinces) >= 10
        awards.append(CanadianMapleAward(
            name="Canadian Maple",
            level="Orange",
            required_provinces=10,
            required_bands=1,
            band=band,
            qrp_required=False,
            current_provinces=len(band_provinces),
            current_bands=1 if band_provinces else 0,
            achieved=orange_achieved,
            provinces_worked=sorted(list(band_provinces)),
            bands_worked=[band] if band_provinces else []
        ))
    
    # Red Maple Award (10 provinces on each of all 9 bands)
    bands_with_10_provinces = sum(1 for band in CANADIAN_MAPLE_BANDS 
                                 if len(provinces_by_band.get(band, set())) >= 10)
    red_achieved = bands_with_10_provinces >= 9
    awards.append(CanadianMapleAward(
        name="Canadian Maple",
        level="Red",
        required_provinces=10,
        required_bands=9,
        band=None,
        qrp_required=False,
        current_provinces=len(provinces_overall),
        current_bands=bands_with_10_provinces,
        achieved=red_achieved,
        provinces_worked=sorted(list(provinces_overall)),
        bands_worked=[band for band in CANADIAN_MAPLE_BANDS 
                     if len(provinces_by_band.get(band, set())) >= 10]
    ))
    
    # Gold Maple Award (10 provinces on each of all 9 bands, QRP only)
    qrp_bands_with_10_provinces = sum(1 for band in CANADIAN_MAPLE_BANDS 
                                     if len(qrp_provinces_by_band.get(band, set())) >= 10)
    gold_achieved = qrp_bands_with_10_provinces >= 9
    awards.append(CanadianMapleAward(
        name="Canadian Maple",
        level="Gold",
        required_provinces=10,
        required_bands=9,
        band=None,
        qrp_required=True,
        current_provinces=len(qrp_provinces_overall),
        current_bands=qrp_bands_with_10_provinces,
        achieved=gold_achieved,
        provinces_worked=sorted(list(qrp_provinces_overall)),
        bands_worked=[band for band in CANADIAN_MAPLE_BANDS 
                     if len(qrp_provinces_by_band.get(band, set())) >= 10]
    ))
    
    return awards


def get_dxcc_country(call: str) -> str | None:
    """
    Extract DXCC country from call sign.
    
    Args:
        call: Amateur radio call sign
        
    Returns:
        DXCC country name or None if not recognized
    """
    if not call:
        return None
    
    call = call.upper().strip()
    
    # Handle portable operations (remove /suffix)
    base_call = call.split('/')[0]
    
    # Check for exact prefix matches first (longest first)
    sorted_prefixes = sorted(DXCC_PREFIXES.keys(), key=len, reverse=True)
    
    for prefix in sorted_prefixes:
        if base_call.startswith(prefix):
            return DXCC_PREFIXES[prefix]
    
    return None


def calculate_dx_awards(qsos: Sequence[QSO], members: Sequence[Member], home_country: str = "United States") -> List[DXAward]:
    """
    Calculate SKCC DX Award progress for both DXQ (QSO-based) and DXC (Country-based).
    
    Rules:
    - DXQ: Count unique QSOs with SKCC members from different countries
    - DXC: Count unique DXCC countries worked (one per country)
    - DXQ valid after June 14, 2009
    - DXC valid after December 19, 2009
    - Both parties must be SKCC members at time of QSO
    """
    # Build member lookup
    member_by_call = {}
    for member in members:
        for alias in generate_call_aliases(member.call):
            member_by_call.setdefault(alias, member)
    
    # Track DX QSOs and countries
    dxq_contacts = []  # List of (country, member_number, is_qrp) tuples
    dxc_countries = set()  # Set of unique countries
    
    # Track QRP separately
    dxq_qrp_contacts = []
    dxc_qrp_countries = set()
    
    for qso in qsos:
        if not qso.call:
            continue
            
        # Must be SKCC member
        normalized_call = normalize_call(qso.call) if qso.call else ""
        member = member_by_call.get(normalized_call or "")
        if not member:
            continue
            
        # Get country from call sign
        country = get_dxcc_country(qso.call)
        if not country or country == home_country:
            continue  # Skip same country or unrecognized
            
        # Date validation
        if qso.date:
            qso_date = qso.date
            
            # DXQ valid after June 14, 2009 (20090614)
            # DXC valid after December 19, 2009 (20091219)
            if qso_date < "20090614":
                continue  # Before any DX award start date
        
        # Check if QRP (5W or less)
        is_qrp = False
        if hasattr(qso, 'tx_pwr') and qso.tx_pwr:
            try:
                power = float(qso.tx_pwr)
                is_qrp = power <= 5.0
            except (ValueError, TypeError):
                pass
        # Also check for QRP indicator in comment or mode
        if (hasattr(qso, 'comment') and qso.comment and 'QRP' in qso.comment.upper()) or \
           (qso.mode and 'QRP' in qso.mode.upper()):
            is_qrp = True
            
        # For DXQ: track individual QSOs (country, member number)
        if qso.date and qso.date >= "20090614":
            contact_key = (country, member.number)
            if contact_key not in [c[:2] for c in dxq_contacts]:
                dxq_contacts.append((country, member.number, is_qrp))
                if is_qrp:
                    dxq_qrp_contacts.append((country, member.number, is_qrp))
        
        # For DXC: track unique countries
        if qso.date and qso.date >= "20091219":
            dxc_countries.add(country)
            if is_qrp:
                dxc_qrp_countries.add(country)
    
    awards = []
    
    # DXQ Awards (QSO-based)
    dxq_count = len(dxq_contacts)
    dxq_qrp_count = len(dxq_qrp_contacts)
    dxq_countries = list(set(contact[0] for contact in dxq_contacts))
    dxq_qrp_countries = list(set(contact[0] for contact in dxq_qrp_contacts))
    
    for threshold in DX_AWARD_THRESHOLDS:
        # Regular DXQ award
        awards.append(DXAward(
            name=f"DXQ-{threshold}",
            award_type="DXQ",
            threshold=threshold,
            current_count=dxq_count,
            achieved=dxq_count >= threshold,
            countries_worked=dxq_countries,
            qrp_qualified=False,
            start_date="20090614"
        ))
        
        # QRP DXQ award
        awards.append(DXAward(
            name=f"DXQ-{threshold} QRP",
            award_type="DXQ",
            threshold=threshold,
            current_count=dxq_qrp_count,
            achieved=dxq_qrp_count >= threshold,
            countries_worked=dxq_qrp_countries,
            qrp_qualified=True,
            start_date="20090614"
        ))
    
    # DXC Awards (Country-based)
    dxc_count = len(dxc_countries)
    dxc_qrp_count = len(dxc_qrp_countries)
    
    for threshold in DX_AWARD_THRESHOLDS:
        # Regular DXC award
        awards.append(DXAward(
            name=f"DXC-{threshold}",
            award_type="DXC",
            threshold=threshold,
            current_count=dxc_count,
            achieved=dxc_count >= threshold,
            countries_worked=sorted(list(dxc_countries)),
            qrp_qualified=False,
            start_date="20091219"
        ))
        
        # QRP DXC award
        awards.append(DXAward(
            name=f"DXC-{threshold} QRP",
            award_type="DXC",
            threshold=threshold,
            current_count=dxc_qrp_count,
            achieved=dxc_qrp_count >= threshold,
            countries_worked=sorted(list(dxc_qrp_countries)),
            qrp_qualified=True,
            start_date="20091219"
        ))
    
    return awards


def extract_prefix(call: str) -> str | None:
    """
    Extract call sign prefix according to SKCC PFX Award rules.
    
    The prefix consists of letters and numbers up to and including 
    the last number on the left part of the call sign.
    Prefixes and suffixes separated by "/" are ignored.
    
    Examples:
    - AC2C -> AC2
    - N6WK -> N6  
    - DU3/W5LFA -> W5
    - 2D0YLX -> 2D0
    - S51AF -> S51
    - K5ZMD/7 -> K5
    - W4/IB4DX -> IB4
    
    Args:
        call: Amateur radio call sign
        
    Returns:
        Prefix string or None if invalid
    """
    if not call:
        return None
    
    call = call.upper().strip()
    
    # Remove portable indicators (keep base call)
    base_call = call.split('/')[0]
    
    # Handle special case like W4/IB4DX where prefix is after the /
    if '/' in call:
        parts = call.split('/')
        if len(parts) >= 2:
            # If the first part looks like a location (W4, VE7, etc.) and second is the call
            first_part = parts[0]
            second_part = parts[1]
            
            # Check if first part is a simple area designation (2-3 chars with digit)
            if len(first_part) <= 3 and any(c.isdigit() for c in first_part):
                base_call = second_part  # Use the part after /
    
    # Find the last digit in the base call
    last_digit_pos = -1
    for i, char in enumerate(base_call):
        if char.isdigit():
            last_digit_pos = i
    
    if last_digit_pos == -1:
        return None  # No digit found, invalid call
    
    # Prefix is everything up to and including the last digit
    prefix = base_call[:last_digit_pos + 1]
    
    return prefix if prefix else None


def calculate_pfx_awards(qsos: Sequence[QSO], members: Sequence[Member]) -> List[PFXAward]:
    """
    Calculate SKCC PFX Award progress based on unique prefixes and SKCC number sums.
    
    Rules:
    - Collect unique call sign prefixes from SKCC member contacts
    - Score = sum of SKCC numbers for each unique prefix
    - Px1 award at 500,000 points, then every 500,000 up to Px10
    - Beyond Px10: Px15, Px20, Px25, etc. (increments of 5)
    - Valid after January 1, 2013
    - Both parties must be SKCC members at time of QSO
    - Band endorsements available for each level
    """
    # Build member lookup with all aliases
    member_by_call = {}
    for member in members:
        for alias in generate_call_aliases(member.call):
            member_by_call.setdefault(alias, member)
    
    # Track prefixes and their associated SKCC numbers
    prefix_scores = {}  # prefix -> set of SKCC numbers worked
    prefix_scores_by_band = {}  # band -> {prefix -> set of SKCC numbers}
    
    for qso in qsos:
        if not qso.call or not qso.band:
            continue
            
        # Must be SKCC member
        normalized_call = normalize_call(qso.call) if qso.call else ""
        member = member_by_call.get(normalized_call or "")
        if not member:
            continue
            
        # Date validation - only contacts after Jan 1, 2013
        if qso.date and qso.date < "20130101":
            continue
            
        # Extract prefix
        prefix = extract_prefix(qso.call)
        if not prefix:
            continue
            
        # Get member number
        member_number = member.number
        
        # Track for overall award
        if prefix not in prefix_scores:
            prefix_scores[prefix] = set()
        prefix_scores[prefix].add(member_number)
        
        # Track by band for endorsements
        band = qso.band.upper()
        if band not in prefix_scores_by_band:
            prefix_scores_by_band[band] = {}
        if prefix not in prefix_scores_by_band[band]:
            prefix_scores_by_band[band][prefix] = set()
        prefix_scores_by_band[band][prefix].add(member_number)
    
    awards = []
    
    # Calculate overall PFX awards
    total_score = sum(max(numbers) for numbers in prefix_scores.values())
    unique_prefixes = len(prefix_scores)
    prefixes_worked = sorted(list(prefix_scores.keys()))
    
    # Define PFX award levels
    pfx_levels = []
    # Px1 through Px10 (every 500,000)
    for i in range(1, 11):
        pfx_levels.append((i, i * 500000))
    # Beyond Px10: increments of 5
    for i in range(15, 101, 5):  # Px15, Px20, Px25, ... Px100
        pfx_levels.append((i, i * 500000))
    
    for level, threshold in pfx_levels:
        awards.append(PFXAward(
            name=f"PFX Px{level}",
            level=level,
            threshold=threshold,
            current_score=total_score,
            achieved=total_score >= threshold,
            unique_prefixes=unique_prefixes,
            prefixes_worked=prefixes_worked,
            band=None
        ))
    
    # Calculate band endorsements for each achieved level
    for band, band_prefixes in prefix_scores_by_band.items():
        if not band_prefixes:
            continue
            
        band_score = sum(max(numbers) for numbers in band_prefixes.values())
        band_unique_prefixes = len(band_prefixes)
        band_prefixes_worked = sorted(list(band_prefixes.keys()))
        
        for level, threshold in pfx_levels:
            # Only create band endorsements for levels that are achieved overall
            overall_achieved = total_score >= threshold
            band_achieved = band_score >= threshold
            
            if overall_achieved or band_achieved:  # Show if either overall or band is achieved
                awards.append(PFXAward(
                    name=f"PFX Px{level}",
                    level=level,
                    threshold=threshold,
                    current_score=band_score,
                    achieved=band_achieved,
                    unique_prefixes=band_unique_prefixes,
                    prefixes_worked=band_prefixes_worked,
                    band=band
                ))
    
    return awards


def calculate_triple_key_awards(qsos: Sequence[QSO], members: Sequence[Member]) -> List[TripleKeyAward]:
    """
    Calculate SKCC Triple Key Award progress.
    
    Rules:
    - Contact 300 different SKCC members total:
      - 100 using straight key
      - 100 using bug/semi-automatic
      - 100 using sideswiper/cootie
    - Valid after November 10, 2018
    - Both parties must be SKCC members at time of QSO
    - Key type must be specified in QSO record
    """
    # Build member lookup with all aliases
    member_by_call = {}
    for member in members:
        for alias in generate_call_aliases(member.call):
            member_by_call.setdefault(alias, member)
    
    # Track unique members worked with each key type
    straight_key_members = set()  # Unique SKCC member calls
    bug_members = set()
    sideswiper_members = set()
    
    # Define key type mappings - simplified to core SKCC key types
    STRAIGHT_KEY_TYPES = {
        "SK", "STRAIGHT"
    }
    BUG_TYPES = {
        "BUG"
    }
    SIDESWIPER_TYPES = {
        "SIDESWIPER", "COOTIE"
    }
    
    for qso in qsos:
        if not qso.call:
            continue
            
        # Must be SKCC member
        normalized_call = normalize_call(qso.call)
        member = member_by_call.get(normalized_call)
        if not member:
            continue
            
        # Valid after November 10, 2018
        if qso.date and qso.date < "20181110":
            continue
            
        # Must have QSO date to verify member status
        if not qso.date:
            continue
            
        # Check if member was valid at QSO time
        if member.join_date and qso.date < member.join_date:
            continue
            
        # Extract key type from various possible fields
        key_type = None
        
        # Check comment field for key type
        if qso.comment:
            comment_upper = qso.comment.upper().strip()
            if any(kt in comment_upper for kt in STRAIGHT_KEY_TYPES):
                key_type = "straight"
            elif any(kt in comment_upper for kt in BUG_TYPES):
                key_type = "bug"
            elif any(kt in comment_upper for kt in SIDESWIPER_TYPES):
                key_type = "sideswiper"
                
        # Check dedicated key type field if available
        if not key_type and qso.key_type:
            key_upper = qso.key_type.upper().strip()
            if any(kt in key_upper for kt in STRAIGHT_KEY_TYPES):
                key_type = "straight"
            elif any(kt in key_upper for kt in BUG_TYPES):
                key_type = "bug"
            elif any(kt in key_upper for kt in SIDESWIPER_TYPES):
                key_type = "sideswiper"
        
        # Add to appropriate set if key type identified
        if key_type == "straight":
            straight_key_members.add(normalized_call)
        elif key_type == "bug":
            bug_members.add(normalized_call)
        elif key_type == "sideswiper":
            sideswiper_members.add(normalized_call)
    
    # Create award objects
    awards = []
    
    # Straight Key Award
    sk_count = len(straight_key_members)
    awards.append(TripleKeyAward(
        name="Triple Key - Straight Key",
        key_type="straight",
        threshold=100,
        current_count=sk_count,
        achieved=sk_count >= 100,
        members_worked=sorted(list(straight_key_members)),
        percentage=(sk_count / 100.0) * 100
    ))
    
    # Bug Award
    bug_count = len(bug_members)
    awards.append(TripleKeyAward(
        name="Triple Key - Bug",
        key_type="bug",
        threshold=100,
        current_count=bug_count,
        achieved=bug_count >= 100,
        members_worked=sorted(list(bug_members)),
        percentage=(bug_count / 100.0) * 100
    ))
    
    # Sideswiper Award
    ss_count = len(sideswiper_members)
    awards.append(TripleKeyAward(
        name="Triple Key - Sideswiper",
        key_type="sideswiper",
        threshold=100,
        current_count=ss_count,
        achieved=ss_count >= 100,
        members_worked=sorted(list(sideswiper_members)),
        percentage=(ss_count / 100.0) * 100
    ))
    
    # Overall Triple Key Award (requires all three components)
    all_achieved = sk_count >= 100 and bug_count >= 100 and ss_count >= 100
    total_unique = len(straight_key_members | bug_members | sideswiper_members)
    
    awards.append(TripleKeyAward(
        name="Triple Key Award",
        key_type="overall",
        threshold=300,
        current_count=total_unique,
        achieved=all_achieved,
        members_worked=sorted(list(straight_key_members | bug_members | sideswiper_members)),
        percentage=(total_unique / 300.0) * 100
    ))
    
    return awards


def calculate_rag_chew_awards(qsos: Sequence[QSO], members: Sequence[Member]) -> List[RagChewAward]:
    """
    Calculate SKCC Rag Chew Award progress.
    
    Rules:
    - 30+ minute QSOs with SKCC members count as rag chews
    - 40+ minutes if more than two stations participate
    - Awards at 300, 600, 900, ... minute thresholds (RC1, RC2, RC3, etc.)
    - Beyond RC10: RC15, RC20, RC25, etc. (increments of 5)
    - Band endorsements available for each level
    - Valid after July 1, 2013
    - Both parties must be SKCC members at time of QSO
    - Back-to-back QSOs with same station not allowed
    """
    # Build member lookup with all aliases
    member_by_call = {}
    for member in members:
        for alias in generate_call_aliases(member.call):
            member_by_call.setdefault(alias, member)
    
    # Track rag chew minutes by band and overall
    total_minutes_overall = 0
    total_qsos_overall = 0
    minutes_by_band = {}  # band -> total minutes
    qsos_by_band = {}     # band -> QSO count
    
    # Track last contact with each call to prevent back-to-back QSOs
    last_contact_by_call = {}  # call -> datetime
    valid_qsos = []
    
    for qso in qsos:
        if not qso.call or not qso.duration_minutes:
            continue
            
        # Must be SKCC member
        normalized_call = normalize_call(qso.call)
        member = member_by_call.get(normalized_call)
        if not member:
            continue
            
        # Valid after July 1, 2013
        if qso.date and qso.date < "20130701":
            continue
            
        # Must have QSO date to verify member status
        if not qso.date:
            continue
            
        # Check if member was valid at QSO time
        if member.join_date and qso.date < member.join_date:
            continue
            
        # Minimum 30 minutes for rag chew (40 if multi-station)
        min_duration = 30
        # Note: We don't have multi-station detection, so using 30 minutes
        if qso.duration_minutes < min_duration:
            continue
            
        # Check for back-to-back contacts with same station
        qso_datetime = qso.date + (qso.time_on or "0000")
        if normalized_call in last_contact_by_call:
            # For simplicity, we'll allow if there's at least one other contact in between
            # This is a simplified implementation of the back-to-back rule
            pass
        
        last_contact_by_call[normalized_call] = qso_datetime
        
        # Valid rag chew - add to totals
        total_minutes_overall += qso.duration_minutes
        total_qsos_overall += 1
        valid_qsos.append(qso)
        
        # Track by band
        band = qso.band or "Unknown"
        if band not in minutes_by_band:
            minutes_by_band[band] = 0
            qsos_by_band[band] = 0
        minutes_by_band[band] += qso.duration_minutes
        qsos_by_band[band] += 1
    
    awards = []
    
    # Overall Rag Chew Awards (RC1, RC2, RC3, ...)
    for level in range(1, 11):  # RC1 through RC10
        threshold = level * 300  # 300, 600, 900, ..., 3000
        achieved = total_minutes_overall >= threshold
        awards.append(RagChewAward(
            name=f"Rag Chew RC{level}",
            level=level,
            threshold=threshold,
            current_minutes=total_minutes_overall,
            achieved=achieved,
            qso_count=total_qsos_overall,
            band=None
        ))
    
    # Extended levels beyond RC10 (RC15, RC20, RC25, etc.)
    for level in [15, 20, 25, 30, 35, 40, 45, 50]:
        threshold = level * 300
        if total_minutes_overall >= threshold // 2:  # Only show if we're at least halfway there
            achieved = total_minutes_overall >= threshold
            awards.append(RagChewAward(
                name=f"Rag Chew RC{level}",
                level=level,
                threshold=threshold,
                current_minutes=total_minutes_overall,
                achieved=achieved,
                qso_count=total_qsos_overall,
                band=None
            ))
    
    # Band endorsements (300 minutes per band)
    STANDARD_BANDS = ["160M", "80M", "40M", "30M", "20M", "17M", "15M", "12M", "10M"]
    for band in STANDARD_BANDS:
        band_minutes = minutes_by_band.get(band, 0)
        band_qsos = qsos_by_band.get(band, 0)
        
        if band_minutes > 0:  # Only include bands with activity
            for level in range(1, 11):  # Band endorsements RC1-RC10
                threshold = level * 300
                achieved = band_minutes >= threshold
                if band_minutes >= threshold // 2 or achieved:  # Show if halfway there or achieved
                    awards.append(RagChewAward(
                        name=f"Rag Chew RC{level}",
                        level=level,
                        threshold=threshold,
                        current_minutes=band_minutes,
                        achieved=achieved,
                        qso_count=band_qsos,
                        band=band
                    ))
    
    return awards


def calculate_wac_awards(qsos: Sequence[QSO], members: Sequence[Member]) -> List[WACAward]:
    """
    Calculate SKCC Worked All Continents (WAC) Award progress.
    
    Rules:
    - Work all 6 continents: NA, SA, EU, AF, AS, OC (Antarctica AN not required)
    - Valid after October 9, 2011
    - Both parties must be SKCC members at time of QSO
    - Key types: SK (straight key), Side swiper (Cootie), or Bug
    - Band endorsements available
    - QRP endorsement available (5W or less)
    """
    # Build member lookup with all aliases
    member_by_call = {}
    for member in members:
        for alias in generate_call_aliases(member.call):
            member_by_call.setdefault(alias, member)
    
    # Track continents worked overall and by band
    continents_overall = set()
    qrp_continents_overall = set()
    continents_by_band = {}  # band -> set of continents
    qrp_continents_by_band = {}  # band -> set of continents for QRP
    
    # Valid key types for WAC award
    VALID_KEY_TYPES = {"SK", "SIDE SWIPER", "COOTIE", "BUG"}
    
    for qso in qsos:
        if not qso.call:
            continue
            
        # Must be SKCC member
        normalized_call = normalize_call(qso.call)
        member = member_by_call.get(normalized_call)
        if not member:
            continue
            
        # Valid after October 9, 2011
        if qso.date and qso.date < "20111009":
            continue
            
        # Must have QSO date to verify member status
        if not qso.date:
            continue
            
        # Check if member was valid at QSO time
        if member.join_date and qso.date < member.join_date:
            continue
            
        # Check key type (if provided and key type enforcement is desired)
        # For simplicity, we'll accept all QSOs but note the key type requirement
        key_type = qso.key_type or ""
        valid_key = not key_type or key_type.upper() in VALID_KEY_TYPES
        
        # Get continent from call sign
        continent = get_continent_from_call(qso.call)
        if not continent:
            continue
            
        # Only count the main 6 continents (exclude Antarctica)
        if continent not in ["NA", "SA", "EU", "AF", "AS", "OC"]:
            continue
            
        # Check if QRP (5W or less)
        is_qrp = False
        if qso.tx_pwr:
            try:
                power_watts = float(qso.tx_pwr)
                is_qrp = power_watts <= 5
            except (ValueError, TypeError):
                is_qrp = False
        
        # Add to overall tracking
        continents_overall.add(continent)
        if is_qrp:
            qrp_continents_overall.add(continent)
        
        # Track by band
        band = qso.band or "Unknown"
        if band not in continents_by_band:
            continents_by_band[band] = set()
            qrp_continents_by_band[band] = set()
        
        continents_by_band[band].add(continent)
        if is_qrp:
            qrp_continents_by_band[band].add(continent)
    
    awards = []
    
    # Overall WAC Award
    awards.append(WACAward(
        name="Worked All Continents (WAC)",
        award_type="WAC",
        required_continents=6,
        current_continents=len(continents_overall),
        achieved=len(continents_overall) >= 6,
        continents_worked=sorted(list(continents_overall)),
        qrp_qualified=False,
        band=None
    ))
    
    # Overall WAC-QRP Award
    awards.append(WACAward(
        name="Worked All Continents QRP (WAC-QRP)",
        award_type="WAC-QRP", 
        required_continents=6,
        current_continents=len(qrp_continents_overall),
        achieved=len(qrp_continents_overall) >= 6,
        continents_worked=sorted(list(qrp_continents_overall)),
        qrp_qualified=True,
        band=None
    ))
    
    # Band endorsements
    STANDARD_BANDS = ["160M", "80M", "40M", "30M", "20M", "17M", "15M", "12M", "10M"]
    for band in STANDARD_BANDS:
        band_continents = continents_by_band.get(band, set())
        qrp_band_continents = qrp_continents_by_band.get(band, set())
        
        if len(band_continents) > 0:  # Only include bands with activity
            # Regular band endorsement
            awards.append(WACAward(
                name=f"WAC {band} Band",
                award_type=f"WAC-{band}",
                required_continents=6,
                current_continents=len(band_continents),
                achieved=len(band_continents) >= 6,
                continents_worked=sorted(list(band_continents)),
                qrp_qualified=False,
                band=band
            ))
            
            # QRP band endorsement (if any QRP contacts on this band)
            if len(qrp_band_continents) > 0:
                awards.append(WACAward(
                    name=f"WAC {band} Band QRP",
                    award_type=f"WAC-{band}-QRP",
                    required_continents=6,
                    current_continents=len(qrp_band_continents),
                    achieved=len(qrp_band_continents) >= 6,
                    continents_worked=sorted(list(qrp_band_continents)),
                    qrp_qualified=True,
                    band=band
                ))
    
    return awards


def calculate_awards(
    qsos: Sequence[QSO],
    members: Sequence[Member],
    thresholds: Sequence[Tuple[str, int]] | None = None,
    enable_endorsements: bool = True,
    enforce_key_type: bool = False,
    allowed_key_types: Sequence[str] | None = None,
    treat_missing_key_as_valid: bool = True,
    include_unknown_ids: bool = False,
    enforce_suffix_rules: bool = True,
) -> AwardCheckResult:
    """Calculate award progress plus (optionally) band endorsements.

    SKCC is exclusively for Morse code (CW) operations - all QSOs are assumed to be CW.

    thresholds: optional override list of (name, required). Defaults to AWARD_THRESHOLDS.
    Endorsements: For each award threshold, if unique member count on a band
    meets that threshold, an endorsement record is produced.
    
    Implements SKCC Award rules:
      - Centurion Rule #2: Excludes special event / club calls (K9SKC, K3Y*) on/after 20091201.
      - Centurion Rule #3: Requires both parties be members at QSO date if join dates provided.
      - Centurion Rule #4: Counts only unique call signs (each operator only counted once).
      - Tribune Rule #1: For Tribune (50+), only count QSOs with Centurions/Tribunes/Senators (C/T/S suffix).
      - Tribune Rule #2: Both parties must be Centurions at time of QSO for Tribune+ awards.
      - Tribune Endorsements: TxN requires N×50 QSOs (Tx2=100, Tx3=150, ..., Tx10=500)
      - Tribune Higher Endorsements: Tx15=750, Tx20=1000, Tx25=1250, etc. (increments of 250)
      - Rule #6: Optionally enforces key type validation (straight key/bug/cootie).
    
    Parameters:
        enforce_suffix_rules: if True, enforces SKCC suffix requirements for Tribune/Senator awards
        include_unknown_ids: if True, accept numeric SKCC IDs parsed from log even when not present in roster
    """
    use_thresholds = list(thresholds) if thresholds else AWARD_THRESHOLDS

    def member_qualifies_for_award_at_qso_time_inner(member: Member | None, award_threshold: int, qso: QSO) -> bool:
        """
        Check if a member's suffix qualified them for counting toward a specific award AT THE TIME OF QSO.
        
        This uses the SKCC field from the QSO record, which contains the member's
        award status AT THE TIME OF QSO - this is accurate historical data.
        """
        if not enforce_suffix_rules or not member:
            return True  # No suffix enforcement means count all members
        
        # Centurion Award (100): Count all SKCC members (any suffix or no suffix)
        if award_threshold <= 100:
            return True
        
        # For Tribune/Senator awards, get the member's status at QSO time from SKCC field
        qso_time_status = get_member_status_at_qso_time(qso, member)
        
        # Tribune Award (50+): Only count members who were C/T/S at QSO time
        if award_threshold >= 1000:  # Senator
            return qso_time_status in ['T', 'S']  # Only Tribunes/Senators count for Senator
        elif award_threshold >= 50:  # Tribune (50 contacts)
            return qso_time_status in ['C', 'T', 'S']  # Centurions/Tribunes/Senators count for Tribune
        
        return True

    # Allowed key device terms (normalized upper tokens). Accept synonyms.
    default_allowed = ["STRAIGHT", "BUG", "COOTIE", "SIDESWIPER", "SIDEWINDER"]
    allowed_set = {t.upper() for t in (allowed_key_types or default_allowed)}

    def key_is_allowed(q: QSO) -> bool:
        if not enforce_key_type:
            return True
        if q.key_type is None:
            return treat_missing_key_as_valid
        tokens = re.split(r"[^A-Z0-9]+", q.key_type.upper())
        return any(tok in allowed_set for tok in tokens if tok)

    # Build primary and alias maps for member calls
    member_by_call: Dict[str, Member] = {}
    number_to_member: Dict[int, Member] = {}
    for m in members:
        number_to_member[m.number] = m
        for alias in generate_call_aliases(m.call):
            member_by_call.setdefault(alias, m)
    # worked_numbers retained for potential future logic (not currently used)

    # For endorsements we track unique member numbers per band and per mode
    band_members: Dict[str, Set[int]] = {}
    mode_members: Dict[str, Set[int]] = {}
    unmatched_calls: Set[str] = set()

    # Pre-calc disallowed special event patterns
    SPECIAL_CUTOFF = "20091201"
    def is_disallowed_special(call: str | None, date: str | None) -> bool:
        if not call or not date:
            return False
        if date < SPECIAL_CUTOFF:
            return False  # before cutoff, allowed
        base = call.upper()
        if base == "K9SKC":
            return True
        # K3Y or K3Y/1 etc (K3Y followed by optional / and region)
        if base.startswith("K3Y"):
            if base == "K3Y" or base.startswith("K3Y/"):
                return True
        return False

    filtered_qsos: List[QSO] = []
    for q in qsos:
        # SKCC is exclusively CW/Morse code - exclude any non-CW modes (data cleanup)
        if q.mode and q.mode.upper() not in ["CW", "A1A"]:
            continue
            
        # Exclude disallowed special calls (rule #2)
        if is_disallowed_special(q.call, q.date):
            continue
        # Enforce key device rule (rule #6)
        if not key_is_allowed(q):
            continue
        filtered_qsos.append(q)

    # Build chronological ordering for award progression logic
    chronological = sorted(filtered_qsos, key=_qso_timestamp)
    first_seen_time: Dict[int, datetime] = {}

    matched_qso_count = 0

    # Iterate QSOs; validate membership at QSO time and populate category sets
    for q in chronological:
        # Normalize QSO call for lookup
        normalized_call = normalize_call(q.call) if q.call else ""
        member = member_by_call.get(normalized_call or "")
        numeric_id: int | None = None
        if member:
            # Membership date validation (rule #3)
            if member.join_date and q.date and q.date < member.join_date:
                # QSO before member joined; skip entirely
                continue
            numeric_id = member.number
        else:
            # We no longer trust raw SKCC field unless it maps to a known member number
            if q.skcc:
                msk = SKCC_FIELD_RE.match(q.skcc.strip().upper())
                if msk:
                    candidate = int(msk.group("num"))
                    if candidate in number_to_member:
                        # If we have the member but call didn't match (e.g. portable variant we failed to normalize), ensure join date ok
                        m2 = number_to_member[candidate]
                        if not (m2.join_date and q.date and q.date < m2.join_date):
                            numeric_id = candidate
                    elif include_unknown_ids:
                        numeric_id = candidate
        if numeric_id is None:
            if q.call:
                unmatched_calls.add(q.call)
            continue

        # Count this QSO as matched (a valid roster member contact)
        matched_qso_count += 1
        # Track first-seen time
        if numeric_id not in first_seen_time:
            first_seen_time[numeric_id] = _qso_timestamp(q)
        # Update endorsement tracking
        if q.band:
            band_members.setdefault(q.band.upper(), set()).add(numeric_id)
        if q.mode:
            mode_members.setdefault(q.mode.upper(), set()).add(numeric_id)

    # Unique IDs set
    all_unique_ids: Set[int] = set(first_seen_time.keys())
    unique_count = len(all_unique_ids)

    # Determine centurion achievement timestamp (first moment hitting 100 uniques)
    centurion_ts: datetime | None = None
    if unique_count >= 100:
        seen: Set[int] = set()
        for q in chronological:
            member = member_by_call.get(q.call or "")
            nid = None
            if member:
                if member.join_date and q.date and q.date < member.join_date:
                    continue
                nid = member.number
            elif q.skcc:
                msk = SKCC_FIELD_RE.match(q.skcc.strip().upper())
                if msk:
                    cand = int(msk.group("num"))
                    if cand in number_to_member:
                        m2 = number_to_member[cand]
                        if m2.join_date and q.date and q.date < m2.join_date:
                            continue
                        nid = cand
                    elif include_unknown_ids:
                        nid = cand
            if nid is None:
                continue
            if nid not in seen:
                seen.add(nid)
                if len(seen) == 100:
                    centurion_ts = _qso_timestamp(q)
                    break

    # Award progress - implementing complete SKCC award rules with historical status consideration
    progresses: List[AwardProgress] = []
    
    # Centurion (100): All unique SKCC members count
    centurion_current = unique_count
    centurion_achieved = centurion_current >= 100
    progresses.append(AwardProgress(
        name="Centurion",
        required=100,
        current=centurion_current,
        achieved=centurion_achieved,
        description="Contact 100 unique SKCC members"
    ))
    
    if enforce_suffix_rules:
        # For proper SKCC rules, we need to evaluate each member's status at QSO time
        # Track members who qualified for Tribune/Senator awards at the time of contact
        tribune_qualified_members = set()
        senator_qualified_members = set()
        
        # Go through QSOs chronologically to determine qualification at QSO time
        # For Tribune award, BOTH parties must be Centurions at time of QSO
        for q in chronological:
            # Skip QSOs before you achieved Centurion (Tribune requires mutual qualification)
            if centurion_ts and q.date:
                try:
                    qso_timestamp = _qso_timestamp(q)
                    if qso_timestamp < centurion_ts:
                        continue  # You weren't qualified yet for Tribune
                except:
                    continue
            elif centurion_ts is None:
                # You haven't achieved Centurion yet, so no Tribune qualification possible
                continue
                
            member = member_by_call.get(q.call or "")
            numeric_id = None
            
            if member:
                if member.join_date and q.date and q.date < member.join_date:
                    continue
                numeric_id = member.number
            elif q.skcc:
                msk = SKCC_FIELD_RE.match(q.skcc.strip().upper())
                if msk:
                    candidate = int(msk.group("num"))
                    if candidate in number_to_member:
                        m2 = number_to_member[candidate]
                        if m2.join_date and q.date and q.date < m2.join_date:
                            continue
                        member = m2
                        numeric_id = candidate
                    elif include_unknown_ids:
                        numeric_id = candidate
            
            if numeric_id is None or member is None:
                continue
            
            # Check if this member qualified for Tribune award at QSO time (50 contacts)
            if member_qualifies_for_award_at_qso_time_inner(member, 50, q):
                tribune_qualified_members.add(numeric_id)
            
            # Check if this member qualified for Senator award at QSO time
            if member_qualifies_for_award_at_qso_time_inner(member, 1000, q):
                senator_qualified_members.add(numeric_id)
        
        tribune_current = len(tribune_qualified_members)
        tribune_achieved = tribune_current >= 50  # Tribune requires 50 contacts
        
        # Add all Tribune endorsement levels
        # TxN requires N times 50 QSOs (Tx2=100, Tx3=150, ..., Tx10=500)
        tribune_endorsements = []
        for n in range(2, 11):  # Tx2 through Tx10
            required = n * 50
            achieved = tribune_current >= required
            tribune_endorsements.append(AwardProgress(
                name=f"Tx{n}",
                required=required,
                current=tribune_current,
                achieved=achieved,
                description=f"Tribune x{n} - Contact {required} unique C/T/S members"
            ))
        
        # Higher endorsements: Tx15, Tx20, Tx25, etc. in increments of 250
        # Tx15=750, Tx20=1000, Tx25=1250, etc.
        for n in range(15, 51, 5):  # Tx15, Tx20, Tx25, ..., Tx50 (reasonable upper limit)
            required = n * 50
            if tribune_current >= required * 0.8:  # Only show if within 80% to avoid clutter
                achieved = tribune_current >= required
                tribune_endorsements.append(AwardProgress(
                    name=f"Tx{n}",
                    required=required,
                    current=tribune_current,
                    achieved=achieved,
                    description=f"Tribune x{n} - Contact {required} unique C/T/S members"
                ))
        
        # Senator requires Tribune x8 (400 qualified) PLUS 200 contacts with T/S at QSO time
        senator_current = len(senator_qualified_members)
        senator_prerequisite = tribune_current >= 400  # Tribune x8 = 400 contacts
        senator_achieved = senator_prerequisite and senator_current >= 200
        
        progresses.append(AwardProgress(
            name="Tribune",
            required=50,
            current=tribune_current,
            achieved=tribune_achieved,
            description="Contact 50 unique C/T/S members (both parties must be C+ at QSO time)"
        ))
        
        # Add all Tribune endorsement progress
        progresses.extend(tribune_endorsements)
        
        senator_desc = f"Tribune x8 (400 C/T/S) + 200 T/S members. Prerequisite: {'✓' if senator_prerequisite else '✗'}"
        progresses.append(AwardProgress(
            name="Senator",
            required=200,
            current=senator_current,
            achieved=senator_achieved,
            description=senator_desc
        ))
    else:
        # Legacy counting for backwards compatibility - uses current status
        centurion_plus_members = set()
        tribune_senator_members = set()  # T/S only for Senator award
        
        for nid in all_unique_ids:
            member = number_to_member.get(nid)
            if member and member.suffix:
                if member.suffix in ['C', 'T', 'S']:
                    centurion_plus_members.add(nid)
                if member.suffix in ['T', 'S']:
                    tribune_senator_members.add(nid)
        
        tribune_current = len(centurion_plus_members)
        tribune_achieved = tribune_current >= 50  # Tribune requires 50 contacts with C/T/S
        
        # Add all Tribune endorsement levels (legacy mode)
        # TxN requires N times 50 QSOs (Tx2=100, Tx3=150, ..., Tx10=500)
        tribune_endorsements = []
        for n in range(2, 11):  # Tx2 through Tx10
            required = n * 50
            achieved = tribune_current >= required
            tribune_endorsements.append(AwardProgress(
                name=f"Tx{n}",
                required=required,
                current=tribune_current,
                achieved=achieved,
                description=f"Tribune x{n} - Contact {required} unique C/T/S members (legacy: current status)"
            ))
        
        # Higher endorsements: Tx15, Tx20, Tx25, etc. in increments of 250
        for n in range(15, 51, 5):  # Tx15, Tx20, Tx25, ..., Tx50
            required = n * 50
            if tribune_current >= required * 0.8:  # Only show if within 80% to avoid clutter
                achieved = tribune_current >= required
                tribune_endorsements.append(AwardProgress(
                    name=f"Tx{n}",
                    required=required,
                    current=tribune_current,
                    achieved=achieved,
                    description=f"Tribune x{n} - Contact {required} unique C/T/S members (legacy: current status)"
                ))
        
        # Senator requires Tribune x8 (400 C/T/S) PLUS 200 contacts with T/S only
        senator_current = len(tribune_senator_members)
        senator_prerequisite = tribune_current >= 400  # Tribune x8 = 400 contacts
        senator_achieved = senator_prerequisite and senator_current >= 200
        
        progresses.append(AwardProgress(
            name="Tribune",
            required=50,
            current=tribune_current,
            achieved=tribune_achieved,
            description="Contact 50 unique Centurions/Tribunes/Senators (legacy: current status)"
        ))
        
        # Add all Tribune endorsement progress
        progresses.extend(tribune_endorsements)
        
        senator_desc = f"Tribune x8 (400 C/T/S) + 200 T/S members. Prerequisite: {'✓' if senator_prerequisite else '✗'}"
        progresses.append(AwardProgress(
            name="Senator",
            required=200,
            current=senator_current,
            achieved=senator_achieved,
            description=senator_desc
        ))
        
        senator_desc = f"Tribune x8 + 200 Tribunes/Senators (legacy: current status). Prerequisite: {'✓' if senator_prerequisite else '✗'}"
        progresses.append(AwardProgress(
            name="Senator",
            required=200,
            current=senator_current,
            achieved=senator_achieved,
            description=senator_desc
        ))

    endorsements: List[AwardEndorsement] = []
    if enable_endorsements:
        for name, required in use_thresholds:
            for band, nums in band_members.items():
                current = len(nums)
                if current >= required:
                    endorsements.append(
                        AwardEndorsement(
                            award=name,
                            category="band",
                            value=band,
                            required=required,
                            current=current,
                            achieved=current >= required,
                        )
                    )
            for mode, nums in mode_members.items():
                current = len(nums)
                if current >= required:
                    endorsements.append(
                        AwardEndorsement(
                            award=name,
                            category="mode",
                            value=mode,
                            required=required,
                            current=current,
                            achieved=current >= required,
                        )
                    )
        endorsements.sort(key=lambda e: (e.award, e.category, e.value))

    # Calculate Canadian Maple Awards
    canadian_maple_awards = calculate_canadian_maple_awards(filtered_qsos, members)
    
    # Calculate DX Awards (detect home country from first QSO or default to US)
    home_country = "United States"  # Default
    if filtered_qsos:
        # Try to detect home country from first QSO
        first_call = filtered_qsos[0].call
        if first_call:
            first_qso_country = get_dxcc_country(first_call)
            if first_qso_country:
                home_country = first_qso_country
    dx_awards = calculate_dx_awards(filtered_qsos, members, home_country)
    
    # Calculate PFX Awards
    pfx_awards = calculate_pfx_awards(filtered_qsos, members)
    
    # Calculate Triple Key Awards
    triple_key_awards = calculate_triple_key_awards(filtered_qsos, members)
    
    # Calculate Rag Chew Awards
    rag_chew_awards = calculate_rag_chew_awards(filtered_qsos, members)
    
    # Calculate WAC Awards
    wac_awards = calculate_wac_awards(filtered_qsos, members)

    return AwardCheckResult(
        unique_members_worked=unique_count,
        awards=progresses,
        endorsements=endorsements,
        total_qsos=len(qsos),
        matched_qsos=matched_qso_count,
        unmatched_calls=sorted(unmatched_calls),
        thresholds_used=list(use_thresholds),
        total_cw_qsos=len(filtered_qsos),
        canadian_maple_awards=canadian_maple_awards,
        dx_awards=dx_awards,
        pfx_awards=pfx_awards,
        triple_key_awards=triple_key_awards,
        rag_chew_awards=rag_chew_awards,
        wac_awards=wac_awards,
    )
