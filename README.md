# SKCC Awards Calculator

A Python application for calculating SKCC (Straight Key Century Club) award progress from ADIF log files. This program validates QSOs against the official SKCC member roster and accurately calculates progress toward Centurion, Tribune, and Senator awards.

**Note**: SKCC is exclusively for Morse code (CW) operations. All QSOs are assumed to be CW mode contacts.

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
✅ **Award Endorsements**: Calculates band endorsements (SKCC is exclusively CW/Morse code)  
✅ **Canadian Maple Awards**: Calculates geographic-based awards for Canadian provinces/territories  
✅ **DX Awards**: Supports both DXQ (QSO-based) and DXC (country-based) international awards  
✅ **PFX Awards**: Calculates prefix-based awards (Px1-Px10) with call sign prefix scoring  
✅ **Triple Key Awards**: Tracks progress using straight key, bug, and side swiper key types  
✅ **Rag Chew Awards**: Accumulates conversational CW minutes for RC1-RC10+ levels  
✅ **WAC Awards**: Worked All Continents awards with band and QRP endorsements  
✅ **Enhanced Input Validation**: Regex-based validation for URLs, file types, and data integrity  
✅ **Robust Error Handling**: Improved user feedback for invalid data and file formats  

### New Validation Features

The application now includes comprehensive input validation using regular expressions:

- **URL Validation**: Validates roster URLs before attempting to fetch data
- **File Extension Validation**: Ensures only valid ADIF files (.adi, .adif) are processed
- **Member Data Validation**: Validates member numbers and callsign formats in CSV files
- **Enhanced Error Reporting**: Provides detailed feedback about invalid data that was skipped
- **Data Integrity Checks**: Prevents processing of malformed or incomplete data

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
   - **Tribune Endorsements**: 
     - **TxN**: Requires N×50 contacts (Tx2=100, Tx3=150, ..., Tx10=500)
     - **Higher Endorsements**: Tx15=750, Tx20=1000, Tx25=1250, etc. (increments of 250)
     - All contacts must meet Tribune requirements (C/T/S members, mutual Centurion status)

3. **Senator Rules**:
   - Must first achieve Tribune x8 (400 contacts with C/T/S members)
   - Then contact 200 unique Tribune/Senator members (T/S suffix only)
   - Both parties must be Centurions (or higher) at time of QSO
   - Strict QSO-time validation of member status
   - **Senator Endorsements**:
     - **SxN**: Requires N×200 T/S contacts (Sx2=400, Sx3=600, ..., Sx10=2000)
     - **Single-band endorsements**: Senator award for individual bands (up to Sx10 per band)
     - Prerequisite: Must first achieve Tribune x8 (400 C/T/S contacts)

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
   - **Requirement**: Contact 300 different SKCC members using all three key type categories:
     - 100 contacts using SK (Straight Key)
     - 100 contacts using Bug (semi-automatic key) 
     - 100 contacts using Side Swiper (Cootie)
   - **Key Type Detection**: Recognizes "SK", "STRAIGHT", "BUG", "SEMI", "SIDESWIPER", "COOTIE", "SS"
   - **Exchange**: Must mention key type used during QSO (abbreviations like "SK", "BUG", "SS" accepted)
   - **Categories**: Shows separate progress for each key type category
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

- **Python 3.8 or higher** with tkinter support
- **Internet connection** (for fetching SKCC roster)
- **ADIF log file** (preferably from SKCC Logger for best accuracy)
- **Operating System**: Windows, Linux, or macOS

## Installation

### Prerequisites
- **Python 3.8 or higher** with tkinter support
- **Internet connection** (for fetching SKCC roster)

### Windows

**Download Python:**
1. Go to https://www.python.org/downloads/
2. During installation, check "Add Python to PATH"
3. Verify installation by opening Command Prompt and typing: `python --version`

**Install SKCC Awards Calculator:**
1. Download or clone this repository
2. Extract to a folder like `C:\skcc_awards\`
3. Choose your installation method:

**Option A: Simple Installation (Recommended)**
```cmd
# Navigate to the project folder
cd C:\skcc_awards

# Run simple installer
install_simple.bat
```

**Option B: Full Setup with Virtual Environment**
```cmd
# Navigate to the project folder
cd C:\skcc_awards

# Install required packages
pip install -r requirements.txt
```

### Linux/Mac

**Install Python:**
```bash
# Ubuntu/Debian
sudo apt install python3 python3-pip python3-tk

# macOS (with Homebrew)
brew install python-tk

# Or download from: https://www.python.org/downloads/
```

**Install SKCC Awards Calculator:**
```bash
# Clone or download the repository
git clone https://github.com/garyPenhook/skcc_awards_calculator.git
cd skcc_awards_calculator

# Run installer
./install.sh

# Or install manually
pip3 install httpx beautifulsoup4
```

### Verify Installation
Run the dependency checker to make sure everything is installed correctly:
```bash
# Windows
check_dependencies.bat

# Linux/Mac
python3 check_dependencies.py
```

**What gets installed:**
- `httpx` - For downloading SKCC roster data
- `beautifulsoup4` - For parsing SKCC roster web pages
- `pytest` - For running tests (optional)

**Note**: All other functionality uses Python's built-in modules (no additional packages needed).

## How to Run

### Quick Start (Windows)

**Option A: Simple Installation**
1. Double-click **`install_simple.bat`** to install required packages
2. Double-click **`run_gui_simple.bat`** to start the program

**Option B: Full Setup**
Double-click **`start.bat`** and select from menu:
1. **Run GUI Application** - Launch the main Tkinter interface
2. **Run Debug Mode** - Run debugging tools
3. **Setup/Install Dependencies** - First-time setup

### Quick Start (Linux/Mac)

**GUI Mode:**
```bash
# Run the graphical interface
python3 scripts/gui.py
```

**Command Line Mode:**
```bash
# Check command options
python3 scripts/awards_check.py --help

# Example: Process ADIF file
python3 scripts/awards_check.py mylog.adi
```

### Option 1: Graphical Interface (Recommended)
```cmd
# Quick start
start.bat

# Or manually:
setup.bat          # First time only
run_gui.bat        # Start the GUI
```

**Using the GUI:**
1. Click **"Add ADIF"** to select your log file(s)
   - ⚠️ The program now validates file extensions and warns about non-ADIF files
2. Click **"Load Roster (Live)"** to download current SKCC member roster
   - ⚠️ Custom roster URLs are now validated before attempting to fetch
3. Configure options:
   - ✅ **Enforce SKCC suffix rules** (recommended for accurate award validation)
   - ✅ **Use historical status** (uses QSO-time member status)
   - ⚠️ **Enforce key type** (only if your log has key type data)
4. Click **"Compute"** to calculate award progress
5. View results in the **Awards**, **Endorsements**, **Canadian Maple**, **DX Awards**, **PFX Awards**, **Triple Key**, **Rag Chew**, and **WAC Awards** tabs

**Enhanced Data Validation:**
- **Invalid files**: Non-ADIF files are automatically filtered out with warnings
- **URL validation**: Invalid roster URLs are rejected before network requests
- **CSV validation**: Member data is validated with detailed error reporting
- **Improved feedback**: Clear messages about what data was accepted or rejected

### Option 2: Command Line Interface
```cmd
setup.bat                    # First time only
.venv\Scripts\activate
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Option 3: Debug/Testing Scripts
```cmd
run_debug.bat               # Run ADIF debugging tools
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

**"Invalid URL" error**
- Ensure roster URL starts with http:// or https://
- Check for typos in the URL
- Leave URL field blank to use default SKCC roster URL

**"Non-ADIF files ignored" warning**
- Only .adi and .adif files are processed
- Convert other log formats to ADIF before importing
- Check file extensions are correct

**CSV import warnings**
- Invalid member numbers (non-numeric) are skipped
- Empty rows and malformed data are automatically filtered
- Warning messages show how many rows were skipped

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
├── README.md                 # This documentation
├── LICENSE                   # Software license
├── requirements.txt          # Python dependencies
├── main.adi                  # Sample ADIF file for testing
├── start.bat                 # Windows launcher menu
├── setup.bat                 # Windows setup script
├── run_gui.bat              # Windows GUI launcher
├── run_debug.bat            # Windows debug launcher
├── backend/
│   ├── requirements.txt     # Backend-specific dependencies
│   └── app/
│       ├── main.py          # FastAPI backend server
│       ├── services/
│       │   └── skcc.py      # Core SKCC awards logic
│       ├── api/             # REST API endpoints
│       ├── schemas/         # Pydantic data models
│       └── tests/           # Unit tests
└── scripts/
    ├── gui.py              # Main Tkinter GUI application
    ├── debug_*.py          # Debug and analysis tools
    └── awards_check.py     # Command-line awards checker
```

## Technical Details

### Enhanced Input Validation

The application now uses regular expressions for robust input validation:

```python
# URL validation pattern
URL_PATTERN = re.compile(r'^https?://[^\s/$.?#].[^\s]*$', re.IGNORECASE)

# ADIF file extension validation
ADIF_EXTENSION_PATTERN = re.compile(r'\.(adi|adif)$', re.IGNORECASE)

# Callsign format validation (basic amateur radio format)
CALLSIGN_PATTERN = re.compile(r'^[A-Z0-9]{1,3}[0-9][A-Z0-9]{0,3}[A-Z]$')

# Member number validation (digits only)
MEMBER_NUMBER_PATTERN = re.compile(r'^\d+$')
```

### Validation Features

- **Pre-processing validation**: Files and URLs are validated before processing
- **Data sanitization**: Invalid data is filtered out with user notification
- **Error recovery**: Application continues processing valid data when encountering invalid entries
- **User feedback**: Clear messages about what was accepted, rejected, or requires attention

### Roster Processing
- Fetches live data from SKCC membership roster
- Parses HTML table with member numbers, calls, and suffixes
- Handles call sign aliases and portable operations
- Supports offline roster CSV files
- **Enhanced**: URL validation before network requests

### Award Calculation Algorithm
1. Parse ADIF file(s) for QSO records
2. **Enhanced**: Validate file extensions and warn about non-ADIF files
3. Validate each QSO against SKCC membership roster
4. Apply SKCC award rules and date restrictions
5. Track unique members per award category
6. Calculate award progress and endorsements

### Data Processing Improvements
- **Robust CSV parsing**: Invalid rows are skipped with detailed reporting
- **File type checking**: Only valid ADIF files are processed
- **Input sanitization**: Member numbers and callsigns are validated
- **Error aggregation**: Multiple validation errors are collected and reported together

## Recent Updates

### Version 2.1.0 - Enhanced Input Validation
- Added comprehensive regex-based input validation
- Improved file type checking for ADIF files
- Enhanced URL validation for roster sources
- Better error handling and user feedback
- Robust CSV parsing with data validation
- Callsign format validation with warnings
- Member number validation in CSV imports

## Contributing

This is an open-source project. Contributions welcome for:
- Additional logging software support
- Enhanced award rule validation
- UI improvements
- Bug fixes
- Input validation improvements
- Error handling enhancements

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

