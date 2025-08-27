# GitHub Upload Instructions

Follow these steps to upload your SKCC Awards Calculator to GitHub.

## Prerequisites

1. **Git installed**: Download from [git-scm.com](https://git-scm.com/download/win)
2. **GitHub account**: Create at [github.com](https://github.com) if you don't have one
3. **Repository created**: You already have https://github.com/garyPenhook/skcc_awards_calculator

## Step-by-Step Upload Process

### 1. Initialize Git Repository (if not already done)
```cmd
cd C:\Users\penho\PycharmProjects\skcc_awards
git init
```

### 2. Configure Git (first time only)
```cmd
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### 3. Add Remote Repository
```cmd
git remote add origin https://github.com/garyPenhook/skcc_awards_calculator.git
```

### 4. Check What Files Will Be Uploaded
```cmd
git status
```
This shows which files will be included. The `.gitignore` file excludes:
- Personal ADIF log files (*.adi, *.adif)
- Virtual environment (.venv/)
- Cache files (__pycache__/)
- Private configuration files
- Temporary files

### 5. Add Files to Git
```cmd
git add .
```

### 6. Commit Changes
```cmd
git commit -m "Initial commit: SKCC Awards Calculator with QSO-time status validation"
```

### 7. Push to GitHub
```cmd
git push -u origin main
```

If you get an error about the branch name, try:
```cmd
git branch -M main
git push -u origin main
```

## Files That Will Be Uploaded

✅ **Source Code**:
- `backend/app/` - Core SKCC logic and FastAPI backend
- `scripts/` - GUI and debug scripts
- `.vscode/` - VS Code configuration

✅ **Documentation**:
- `README.md` - Complete user documentation
- `LICENSE` - Software license
- `requirements.txt` - Python dependencies

✅ **Setup Scripts**:
- `setup.bat` - Automated Windows setup
- `run_gui.bat` - GUI launcher
- `run_debug.bat` - Debug launcher

✅ **Configuration**:
- `.gitignore` - Excludes personal data and temporary files

## Files That Will NOT Be Uploaded

❌ **Personal Data**:
- ALL ADIF log files (*.adi, *.adif) - including sample files
- Downloaded roster cache files
- Virtual environment (.venv/)

❌ **Temporary Files**:
- Python cache (__pycache__/)
- Log files (*.log)
- Backup files (*.bak)

## Updating the Repository Later

When you make changes:
```cmd
git add .
git commit -m "Description of your changes"
git push
```

## Setting Repository to Public

1. Go to https://github.com/garyPenhook/skcc_awards_calculator
2. Click "Settings" tab
3. Scroll down to "Danger Zone"
4. Click "Change repository visibility"
5. Select "Make public"

## Adding a Description

1. Go to your repository on GitHub
2. Click the gear icon next to "About"
3. Add description: "SKCC Awards Calculator with accurate QSO-time status validation"
4. Add topics: `skcc`, `ham-radio`, `awards`, `adif`, `python`, `amateur-radio`

## Troubleshooting

**"Repository not found" error**:
- Check the repository URL is correct
- Make sure you have access to the repository

**"Authentication failed" error**:
- Use your GitHub username and personal access token (not password)
- Generate token at: GitHub Settings > Developer settings > Personal access tokens

**Large files warning**:
- The `.gitignore` should prevent this, but if you see warnings about large ADIF files, make sure they're listed in `.gitignore`

## Next Steps

After uploading:
1. Add repository description and topics on GitHub
2. Consider adding screenshots to the README
3. Set up GitHub Actions for automated testing (optional)
4. Add contribution guidelines (optional)

Your repository will be accessible at:
https://github.com/garyPenhook/skcc_awards_calculator
