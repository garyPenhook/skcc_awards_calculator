# SKCC Awards Calculator

A Python application for calculating SKCC (Straight Key Century Club) award progress from ADIF log files. This program validates QSOs against the official SKCC member roster and accurately calculates progress toward Centurion, Tribune, and Senator awards.

## What This Program Does

### SKCC Award Overview
The Straight Key Century Club offers three main awards based on contacting SKCC members:

- **Centurion Award (100)**: Contact 100 unique SKCC members
- **Tribune Award (50)**: Contact 50 unique SKCC members who have achieved Centurion/Tribune/Senator status (both parties must be Centurions at time of QSO)
- **Senator Award**: Achieve Tribune x8 (400 qualified contacts) + contact 200 unique Tribune/Senator members

### Key Features

✅ **Accurate Award Validation**: Implements official SKCC award rules including suffix requirements  
✅ **QSO-Time Status Validation**: Uses member award status **at the time of QSO** from SKCC Logger data  
✅ **Live Roster Integration**: Fetches current SKCC member roster automatically  
✅ **ADIF Parsing**: Supports standard ADIF log files from popular logging software  
✅ **Historical Accuracy**: Correctly handles award progression based on QSO timestamps  
✅ **Multiple Interfaces**: Both GUI and command-line interfaces available  
✅ **Award Endorsements**: Calculates band and mode endorsements  
✅ **Canadian Maple Awards**: Calculates geographic-based awards for Canadian provinces/territories  
✅ **DX Awards**: Supports both DXQ (QSO-based) and DXC (country-based) international awards  
✅ **PFX Awards**: Calculates prefix-based awards (Px1-Px10) with call sign prefix scoring  
✅ **Triple Key Awards**: Tracks progress using straight key, bug, and side swiper key types  
✅ **Rag Chew Awards**: Accumulates conversational CW minutes for RC1-RC10+ levels  
✅ **WAC Awards**: Worked All Continents awards with band and QRP endorsements  

### Award Rules Implemented

The program correctly implements these SKCC award requirements:

1. **Centurion Rules**:
   - Contact 100 unique SKCC members
   - All SKCC members count regardless of award status
   - QSOs must use approved key types (straight key, bug, side swiper)

2. **Tribune Rules** (Official SKCC Requirements):
   - Contact 50 unique SKCC members who have C/T/S suffix
   - **Both parties must be Centurions (or higher) at time of QSO**
   - Only members with Centurion/Tribune/Senator status count
   - Member must have had award status **at time of QSO**
   - Valid after March 1, 2007
   - Must use straight key, bug, or side swiper
   - K9SKC (club call) and K3Y* (special event calls) excluded after October 1, 2008
   - Each member can only be used once (duplicates not allowed)
   - Endorsements available: Tx2 (100 contacts), Tx3 (150 contacts), up to Tx10 (500 contacts), then Tx15, Tx20, etc.

3. **Senator Rules**:
   - Must first achieve Tribune x8 (400 contacts with C/T/S members)
   - Then contact 200 unique Tribune/Senator members (T/S suffix only)
   - Both parties must be Centurions (or higher) at time of QSO
   - Strict QSO-time validation of member status

4. **Special Call Exclusions**:
   - K9SKC (club call) and K3Y* (special event calls) excluded after December 1, 2009
   - Both parties must be SKCC members at time of QSO

5. **Canadian Maple Awards**:
   - **Yellow Maple**: Contact 10 Canadian provinces/territories on any mix of HF bands
   - **Orange Maple**: Contact 10 provinces/territories on a single band (separate award per band)
   - **Red Maple**: Contact 10 provinces/territories on each of all 9 HF bands (90 contacts total)
   - **Gold Maple**: Same as Red Maple but QRP (5 watts or less)
   - Valid after September 1, 2009 for provinces, January 2014 for territories
   - Supports VE1-VE9, VA1-VA9, VY0-VY2, VO1-VO2 call signs

6. **DX Awards**:
   - **DXQ Awards**: QSO-based, count unique QSOs with SKCC members from different countries
   - **DXC Awards**: Country-based, count unique DXCC countries worked (one per country)
   - Available thresholds: 10, 25, 50, 75, 100, 125, 150, 200, 250, 300, 400, 500
   - QRP endorsements available for all levels (5 watts or less)
   - DXQ valid after June 14, 2009; DXC valid after December 19, 2009
   - Both parties must be SKCC members at time of QSO

7. **PFX Awards**:
   - **Scoring**: Each unique call sign prefix scores points equal to the highest SKCC number worked for that prefix
   - **Award Levels**: Px1 (500K points), Px2 (1M), Px3 (1.5M), ..., Px10 (5M), then Px15, Px20, etc.
   - **Prefix Rules**: Standard ITU prefixes (W1, N6, VE1, JA1), portable uses base call, split calls use part after "/"
   - **Band Endorsements**: Available for each level on individual bands
   - Valid after January 1, 2013; both parties must be SKCC members at time of QSO

8. **Triple Key Award**:
   - **Requirement**: Contact 300 different SKCC members using all three key types:
     - 100 contacts using straight key (SK)
     - 100 contacts using bug
     - 100 contacts using sideswiper (cootie)
   - **Key Type Detection**: Recognizes "SK", "STRAIGHT", "BUG", "SIDESWIPER", "COOTIE"
   - **Exchange**: Must mention key type used during QSO (abbreviations like "SK", "BUG" accepted)
   - Valid after November 10, 2018; both parties must be SKCC members at time of QSO

9. **Rag Chew Award**:
   - **Requirement**: Accumulate conversational CW minutes with SKCC members
   - **Duration**: Minimum 30 minutes per QSO (40 minutes if multi-station)
   - **Award Levels**: RC1 (300 min), RC2 (600 min), RC3 (900 min), ..., RC10 (3000 min), then RC15, RC20, etc.
   - **Band Endorsements**: Available for each level on individual bands
   - **QSO Rules**: Back-to-back contacts with same station not allowed
   - Valid after July 1, 2013; both parties must be SKCC members at time of QSO

10. **SKCC Worked All Continents (WAC) Award**:
    - **Requirement**: Contact SKCC members from all 6 continents (North America, South America, Europe, Africa, Asia, Oceania)
    - **Key Types**: Must use straight key (SK), side swiper (cootie), or bug
    - **Award Types**:
      - **WAC**: Basic award for working all 6 continents
      - **WAC-QRP**: QRP endorsement (5 watts or less)
      - **WAC Band Endorsements**: Individual band achievements (160M-10M)
      - **WAC Band QRP**: Combined band and QRP endorsements
    - **Continental Areas**: 
      - **North America (NA)**: USA, Canada, Mexico, Caribbean, Central America
      - **South America (SA)**: South American countries and territories
      - **Europe (EU)**: European countries including European Russia
      - **Africa (AF)**: African countries and territories
      - **Asia (AS)**: Asian countries including Asiatic Russia  
      - **Oceania (OC)**: Australia, New Zealand, Pacific islands
    - Valid after October 9, 2011; both parties must be SKCC members at time of QSO

## Requirements

- **Windows 10/11**
- **Python 3.9 or later**
- **Internet connection** (for fetching SKCC roster)
- **ADIF log file** (preferably from SKCC Logger for best accuracy)

## Installation

### Step 1: Install Python
1. Download Python from [python.org](https://www.python.org/downloads/)
2. During installation, check "Add Python to PATH"
3. Verify installation by opening Command Prompt and typing: `python --version`

### Step 2: Download the Program
1. Download or clone this repository
2. Extract to a folder like `C:\skcc_awards\`

### Step 3: Install Dependencies
Open Command Prompt in the program folder and run:
```cmd
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

## How to Run

### Option 1: Graphical Interface (Recommended)
```cmd
cd C:\skcc_awards
.venv\Scripts\activate
python scripts\gui.py
```

**Using the GUI:**
1. Click **"Add ADIF"** to select your log file(s)
2. Click **"Load Roster (Live)"** to download current SKCC member roster
3. Configure options:
   - ✅ **Enforce SKCC suffix rules** (recommended for accurate award validation)
   - ✅ **Use historical status** (uses QSO-time member status)
   - ⚠️ **Enforce key type** (only if your log has key type data)
4. Click **"Compute"** to calculate award progress
5. View results in the **Awards**, **Endorsements**, **Canadian Maple**, **DX Awards**, **PFX Awards**, **Triple Key**, **Rag Chew**, and **WAC Awards** tabs

**Result Tabs:**
- **Awards**: Shows progress toward Centurion (100), Tribune (500), and Senator awards
- **Endorsements**: Shows band and mode endorsement progress  
- **Canadian Maple**: Shows progress toward Yellow/Orange/Red/Gold Canadian Maple Awards
- **DX Awards**: Shows progress toward DXQ/DXC international awards with QRP endorsements
- **PFX Awards**: Shows progress toward Px1-Px10 prefix awards based on call sign prefix scoring
- **Triple Key**: Shows progress toward Triple Key Award using straight key, bug, and sideswiper
- **Rag Chew**: Shows progress toward RC1-RC10+ awards based on accumulated conversation minutes
- **WAC Awards**: Shows progress toward Worked All Continents awards with band and QRP endorsements

### Option 2: Command Line Interface
```cmd
cd C:\skcc_awards
.venv\Scripts\activate
python -m backend.app.main
```

### Option 3: Debug/Testing Script
```cmd
cd C:\skcc_awards
.venv\Scripts\activate
python scripts\debug_adif.py
```

## Understanding the Results

### Award Progress Display
```
Centurion: 100/100 (ACHIEVED) - Contact 100 unique SKCC members
Tribune: 45/50 (in progress) - Contact 50 unique C/T/S members (both parties must be C+ at QSO time)
Tribune x8: 87/400 (in progress) - Contact 400 unique members who were C/T/S at QSO time
Senator: 83/200 (in progress) - Tribune x8 + 200 members who were T/S at QSO time. Prerequisite: ✗
```

### QSO-Time Status Validation
The program shows the difference between current roster status and status at QSO time:

```
KQ4LEA: QSO on 20250524
  SKCC field: 29650
  Status at QSO time: No award
  Current roster status: Tribune
  Tribune credit: ✗ (correctly excluded - no award at QSO time)
```

## ADIF File Requirements

### Best Results: SKCC Logger
For maximum accuracy, use **SKCC Logger** to record your QSOs:
- Captures member award status at QSO time
- Includes proper SKCC field formatting
- Validates member numbers in real-time
- Available from SKCC Member Services

### Other Logging Software
The program works with any ADIF-compatible logger, but requires:
- `CALL` field with station call sign
- `QSO_DATE` field in YYYYMMDD format
- `SKCC` field with member number (and suffix if known)
- Optional: `MODE`, `BAND`, key type fields

### Sample ADIF Record
```
<CALL:6>KA3LOC <QSO_DATE:8>20250520 <BAND:3>20M <MODE:2>CW <SKCC:4>660S <EOR>
```

## Configuration Options

### Suffix Rule Enforcement
- **Enabled**: Uses official SKCC award rules (recommended)
  - Centurion: All SKCC members count
  - Tribune: Only C/T/S members count
  - Senator: Only T/S members count
- **Disabled**: Legacy counting (all members count for all awards)

### Historical Status Validation
- **QSO-Time Status**: Uses member status from SKCC field at time of QSO (most accurate)
- **Current Status**: Uses current roster status (less accurate for historical QSOs)

### Key Type Enforcement
- **Enabled**: Only counts QSOs with approved key types
- **Disabled**: Counts all QSOs regardless of key type

## Troubleshooting

### Common Issues

**"No module named 'tkinter'"**
```cmd
# Install tkinter support
pip install tk
```

**"Failed to fetch roster"**
- Check internet connection
- SKCC website may be temporarily unavailable
- Try loading a saved roster CSV file instead

**"No QSOs parsed"**
- Verify ADIF file format
- Check that file contains `<EOR>` markers
- Ensure CALL and QSO_DATE fields are present

**Low matching QSO count**
- Many QSOs may be with non-SKCC members (normal)
- Check that SKCC numbers in log are correct
- Verify call sign normalization is working

### Log File Locations
- **SKCC Logger**: Usually in `Documents\skcc\`
- **Ham Radio Deluxe**: Check HRD logbook export
- **N1MM+**: Export to ADIF format
- **Contest loggers**: May need conversion to standard ADIF

## File Structure

```
skcc_awards/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── LICENSE                   # Software license
├── backend/
│   └── app/
│       ├── main.py          # FastAPI backend
│       └── services/
│           └── skcc.py      # Core SKCC logic
├── scripts/
│   ├── gui.py              # Tkinter GUI application
│   ├── debug_adif.py       # Debug/testing script
│   └── main.adi            # Sample ADIF file
└── .vscode/                # VS Code configuration
```

## Technical Details

### Roster Processing
- Fetches live data from SKCC membership roster
- Parses HTML table with member numbers, calls, and suffixes
- Handles call sign aliases and portable operations
- Supports offline roster CSV files

### Award Calculation Algorithm
1. Parse ADIF file(s) for QSO records
2. Validate each QSO against SKCC membership roster
3. Apply SKCC award rules and date restrictions
4. Track unique members per award category
5. Calculate award progress and endorsements

### QSO-Time Status Validation
The program uses the SKCC field from your log to determine the member's award status **at the time of QSO**:

```python
# Example: SKCC field "660S" means member #660 had Senator status at QSO time
if qso.skcc == "660S":
    member_status_at_qso_time = "Senator"  # Counts for Tribune and Senator awards
elif qso.skcc == "660":
    member_status_at_qso_time = "No award"  # Counts only for Centurion award
```

## Contributing

This is an open-source project. Contributions welcome for:
- Additional logging software support
- Enhanced award rule validation
- UI improvements
- Bug fixes

## Support

For issues related to:
- **SKCC award rules**: Contact SKCC Award Managers
- **SKCC Logger software**: SKCC Member Services
- **This program**: Create an issue in the repository

## License

See LICENSE file for software license terms.

---

**Important Note**: This program is an unofficial tool for SKCC award calculation. Official award applications must still be submitted through SKCC Award Managers with proper documentation. Always verify results with official SKCC resources.

---

## Original Stack Information (for developers)

This was originally a monorepo template that has been converted to a specialized SKCC awards calculator.
    schemas/          # Pydantic schemas
    tests/            # Pytest tests
frontend/             # React + TS app (Vite scaffold minimal)
infra/
  docker/             # Dockerfiles
  docker-compose.yml  # Dev orchestration
.github/workflows/    # CI pipeline definitions
scripts/              # Dev helper scripts
 docs/                # Architecture & decision records
```

## Quick Start (Backend Only)
```bash
python -m venv .venv
source .venv/Scripts/activate  # (Windows: .venv\\Scripts\\activate)
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
uvicorn app.main:app --reload --app-dir backend/app
```
Visit: http://127.0.0.1:8000/health

## Run All via Docker Compose
```bash
docker compose -f infra/docker-compose.yml up --build
```
Backend: http://localhost:8000  Frontend: http://localhost:5173

## Tests
```bash
pytest -q
```

## Environment Variables
Create a `.env` (root or backend/) with:
```
APP_ENV=dev
APP_NAME=skcc_awards
LOG_LEVEL=INFO
DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/skcc_awards
```

## Future Enhancements
- Add Alembic migrations
- Add domain-driven modules per award domain
- Implement authentication (JWT / OAuth2)
- Add caching (Redis) layer

## License
MIT

