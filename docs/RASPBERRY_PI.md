# Running SKCC Logger & Awards Calculator on Raspberry Pi

This guide shows how to install and run the W4GNS SKCC Logger and Awards Calculator on a Raspberry Pi (Pi 3, 4, 5 or newer). The application is lightweight and works well on Raspberry Pi OS (Bullseye or Bookworm), both 32‑bit and 64‑bit.

## ✅ Features That Work on Pi
- Full tkinter GUI (main logger & awards interface)
- RBN / SKCC cluster connection (network permitting)
- Roster download + caching
- ADIF logging + automatic backups
- Spot duplicate filtering
- Country/state lookup (backend optional)

## 📋 Requirements
| Component | Notes |
|-----------|-------|
| OS | Raspberry Pi OS (Desktop edition recommended) |
| Python | 3.10+ (system Python OK) |
| GUI | Desktop session (X11/Wayland). Headless needs X forwarding or `xvfb-run` |
| Storage | ~20 MB total (roster DB + code + backups) |
| Network | Needed for roster + cluster spots |

## 🛠️ Install Steps
```bash
# 1. Update system packages
sudo apt update && sudo apt upgrade -y

# 2. Install Python + tkinter (GUI toolkit)
sudo apt install -y python3 python3-pip python3-venv python3-tk

# 3. (Optional) Install Pillow system packages for JPG scaling
yes | sudo apt install -y python3-pil python3-pil.imagetk

# 4. Clone the repository
git clone https://github.com/garyPenhook/skcc_awards_calculator.git
cd skcc_awards_calculator

# 5. Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# 6. Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 7. (Optional) Install Pillow from pip if you skipped apt
pip install Pillow

# 8. Launch the logger GUI
python w4gns_skcc_logger.py
```

If you want the FastAPI backend services (country/state helpers) running:
```bash
pip install fastapi uvicorn
cd backend/app
PYTHONPATH=../.. uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## ▶️ Autostart at Login (Optional)
Create a desktop entry so the logger starts automatically when the Pi boots into the desktop:
```bash
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/skcc_logger.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=SKCC Logger
Exec=/home/pi/skcc_awards_calculator/.venv/bin/python /home/pi/skcc_awards_calculator/w4gns_skcc_logger.py
X-GNOME-Autostart-enabled=true
EOF
```
Adjust paths if you used a different user or location.

## 🧪 Quick Sanity Check
```bash
python - <<'PY'
import tkinter, httpx, bs4
print('Tk version:', tkinter.TkVersion)
print('httpx version:', httpx.__version__)
print('BeautifulSoup4 OK')
PY
```

## 🧵 Performance & Tips
- Pi 3 works; Pi 4/5 feels smoother.
- Use 64‑bit Raspberry Pi OS on Pi 4/5 for slightly faster Python.
- First roster sync may take 15–45 seconds (network dependent).
- Keep the ADIF log on SD card or external SSD; backups go to `~/.skcc_awards/backups`.

## 🛰️ Cluster / RBN Connectivity
If clicking “Connect to RBN” does nothing:
1. Confirm system clock: `timedatectl`
2. Test DNS: `ping -c1 rbn.telegraphy.de`
3. Ensure outbound port not blocked (some clusters use 7300; check code / config)
4. Re-run logger from terminal to view trace output.

## 🐞 Troubleshooting
| Issue | Cause | Fix |
|-------|-------|-----|
| `ModuleNotFoundError: tkinter` | `python3-tk` missing | `sudo apt install python3-tk` |
| GUI won’t open over SSH | No X forwarding | Use `ssh -X` or run locally |
| Roster never updates | Network / site unreachable | Retry; run later or check connectivity |
| Slow UI | Underpowered Pi or heavy background | Close other apps; disable backend server |
| JPG image not showing | Pillow not installed | `pip install Pillow` or use PNG |

## 🧹 Uninstall
```bash
rm -rf ~/.skcc_awards  # Removes roster DB & backups
rm -rf skcc_awards_calculator
```
(You may also remove the virtual environment directory.)

## 🔮 Future Pi Enhancements (Ideas)
- Minimal CLI mode for headless logging
- Systemd service for backend API
- Optional systray icon (needs extra libs)
- Touchscreen layout profile

## ✅ Summary
Everything is pure Python + tkinter + small libs. No platform lock‑ins. The app is Raspberry Pi friendly and ideal for portable / field ops with a small display.

---
Questions or want a headless/CLI workflow documented? Open an issue or ask! :)
