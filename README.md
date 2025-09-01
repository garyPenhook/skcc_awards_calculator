# W4GNS SKCC Logger & Awards Calculator

A comprehensive Python application for SKCC (Straight Key Century Club) QSO logging and award progress calculation. Features real-time cluster spots, automatic state lookup, and complete ADIF logging capabilities.

> **🎯 Quick Start**: Run `python w4gns_skcc_logger.py` to launch the main logger with all features!

## 🚀 Features

### W4GNS SKCC Logger (Main Application)
- **📡 Real-time Cluster Spots**: SKCC-filtered RBN spots with duplicate filtering
- **🌍 Auto Country/State Lookup**: Automatic DXCC and state resolution from callsigns
- **📊 SKCC Roster Integration**: 30,000+ member database with auto-fill
- **⏰ QSO Timing**: Automatic start/end time tracking for Rag Chew awards
- **💾 ADIF 3.1.5 Logging**: Professional QSO logging with backup management
- **🎨 Two-Column Layout**: QSO form + spots display for efficient operation
- **🔄 Smart Updates**: Hourly roster checks on startup

### Award Progress Calculator
- **🏆 All SKCC Awards**: Centurion, Tribune, Senator with endorsements
- **🍁 Canadian Maple**: Yellow, Orange, Red, Gold Maple awards
- **🌎 DX Awards**: DXQ (QSO-based) and DXC (country-based) with QRP endorsements
- **🔤 PFX Awards**: Prefix-based scoring system (Px1-Px20+)
- **🗝️ Triple Key**: Straight key, bug, side swiper tracking
- **💬 Rag Chew**: Minute accumulation awards (RC1-RC20+)
- **🌍 WAC Awards**: Worked All Continents with band endorsements

## 📥 Installation

### Windows (Recommended)
1. **Download Python 3.8+** from [python.org](https://python.org/downloads)
   - ✅ Check "Add Python to PATH" during installation
2. **Download this repository** and extract to a folder
3. **Run the installer**:
   ```cmd
   install_simple.bat
   ```

### Linux/Mac
```bash
# Install dependencies
sudo apt install python3 python3-pip python3-tk  # Ubuntu/Debian
brew install python-tk                            # macOS

# Clone and install
git clone https://github.com/garyPenhook/skcc_awards_calculator.git
cd skcc_awards_calculator
pip3 install -r requirements.txt
```

### Verify Installation
```bash
python check_dependencies.py
```

## 🖥️ Usage

### Main Logger (Recommended)
```bash
# Windows
python w4gns_skcc_logger.py
# OR double-click: run_qso_logger.bat

# Linux/Mac  
python3 w4gns_skcc_logger.py
```

**Features Available:**
- QSO logging with real-time cluster spots
- Automatic state/country lookup
- SKCC member auto-fill from 30,000+ database
- Duplicate spot filtering
- Backup management

### Awards Calculator GUI
```bash
# Windows
run_gui.bat

# Linux/Mac
python3 scripts/gui.py
```

### Command Line Awards Check
```bash
python3 scripts/awards_check.py mylog.adi
```

## 🎯 Quick Start Guide

### 1. First Time Setup
1. Run `python w4gns_skcc_logger.py`
2. Wait for roster download (30,000+ members, ~30 seconds)
3. Configure your station info in the QSO form

### 2. Enable Cluster Spots (Optional)
1. Visit [rbn.telegraphy.de/web](http://rbn.telegraphy.de/web)
2. Enter your callsign, enable "Club members" → "SKCC"
3. In the logger, click "Connect to Cluster"
4. Enter your callsign (e.g., "W4GNS-SKCC")

### 3. Start Logging
- **Auto-fill**: Double-click cluster spots to populate QSO form
- **State lookup**: Callsign automatically fills country/state
- **SKCC numbers**: Auto-populated from member database
- **Timing**: Start time begins when callsign entered

## 📋 System Requirements

- **Python**: 3.8 or higher with tkinter
- **Internet**: Required for roster downloads and cluster spots
- **Storage**: ~10 MB for SKCC roster database
- **OS**: Windows, macOS, Linux

**Dependencies** (auto-installed):
- `httpx` - HTTP requests for roster
- `beautifulsoup4` - HTML parsing

## 🏆 SKCC Awards Supported

### Core Awards
| Award | Requirement | Notes |
|-------|-------------|-------|
| **Centurion** | Contact 100 unique SKCC members | All members count |
| **Tribune** | Contact 50 unique C/T/S members | Both must be C+ at QSO time |
| **Senator** | Tribune x8 + 200 T/S contacts | Requires 400 C/T/S + 200 T/S |

### Specialty Awards
| Award | Description |
|-------|-------------|
| **Canadian Maple** | Contact Canadian provinces/territories |
| **DX Awards** | International contacts (QSO or country-based) |
| **PFX Awards** | Prefix-based point accumulation |
| **Triple Key** | 300 contacts using all 3 key types |
| **Rag Chew** | Accumulate conversational minutes |
| **WAC** | Work all 6 continents |

### Award Endorsements
- **Band endorsements**: Individual band achievements
- **QRP endorsements**: 5 watts or less
- **Multiple levels**: Tx2, Tx3... Sx2, Sx3... etc.

## 📁 File Structure

```
skcc_awards_calculator/
├── w4gns_skcc_logger.py         # 🎯 MAIN LOGGER (start here)
├── run_qso_logger.bat           # Windows launcher
├── install_simple.bat           # Easy installer
├── gui/
│   └── tk_qso_form_clean.py     # Main GUI implementation
├── utils/
│   ├── cluster_client.py        # Real-time spots
│   ├── roster_manager.py        # SKCC member database
│   └── backup_manager.py        # ADIF backups
├── scripts/
│   ├── gui.py                   # Awards calculator GUI
│   └── awards_check.py          # Command-line calculator
└── backend/
    └── app/
        └── services/
            └── skcc.py          # Award calculation engine
```

## ⚙️ Configuration

### Roster Updates
- **Automatic**: Checks every startup (1-hour minimum interval)
- **Manual**: Use `python scripts/roster_sync.py sync`
- **Database**: Stored at `~/.skcc_awards/roster.db`

### Backup Settings
- **Location**: Configure in QSO logger settings
- **Automatic**: Backup before each session
- **Format**: Standard ADIF files

### Cluster Spots
- **Server**: rbn.telegraphy.de (CW-Club gateway)
- **Filters**: SKCC members only
- **Duplicates**: Automatically filtered

## 🔧 Troubleshooting

### Common Issues
| Problem | Solution |
|---------|----------|
| **Import errors** | Run `pip install -r requirements.txt` |
| **No tkinter** | Install Python with tkinter support |
| **Roster fails** | Check internet connection, try `roster_sync.py cleanup` |
| **Database locked** | Run `python scripts/roster_sync.py cleanup` |

### Log Locations
- **QSO logs**: Created in current directory as `.adi` files
- **Roster database**: `~/.skcc_awards/roster.db`
- **Config files**: `~/.skcc_awards/` directory

## 🤝 Contributing

Contributions welcome! Areas of focus:
- Additional logging software integration
- UI/UX improvements  
- Award rule enhancements
- Bug fixes and testing

## 📞 Support

- **Program Issues**: Create a GitHub issue
- **SKCC Award Rules**: Contact SKCC Award Managers
- **SKCC Logger**: SKCC Member Services

## 📜 License

MIT License - See LICENSE file for details.

---

## 🎯 For New Users

**Just want to start logging QSOs?**
1. Run `python w4gns_skcc_logger.py`
2. Wait for roster download
3. Start logging!

**Want to check award progress?**
1. Export your log to ADIF format
2. Run `run_gui.bat` (Windows) or `python3 scripts/gui.py`
3. Load your ADIF file and current roster
4. Click "Compute" to see your progress

---

> **⚠️ Important**: This is an unofficial tool. Official award applications must be submitted through SKCC Award Managers with proper documentation.

