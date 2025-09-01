"""Backup management for ADIF files."""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

class BackupManager:
    """Manages automatic backups of ADIF files."""
    
    def __init__(self):
        self.config_file = Path.home() / ".skcc_awards" / "backup_config.json"
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load backup configuration from file."""
        default_config = {
            "backup_enabled": True,
            "backup_folder": str(Path.home() / ".skcc_awards" / "backups"),
            "max_backups": 10
        }
        
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults to handle missing keys
                    return {**default_config, **config}
        except Exception:
            pass
        
        return default_config
    
    def save_config(self) -> None:
        """Save backup configuration to file."""
        try:
            self.config_file.parent.mkdir(exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception:
            pass  # Fail silently if we can't save
    
    def create_backup(self, source_file: str) -> bool:
        """Create backup of ADIF file. Returns True if successful."""
        if not self.config.get("backup_enabled", True):
            return True  # Backup disabled, consider it successful
            
        try:
            source_path = Path(source_file)
            if not source_path.exists():
                return False
            
            # Create timestamp for backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{source_path.stem}_backup_{timestamp}{source_path.suffix}"
            
            # Primary backup location
            backup_folder_str = self.config.get("backup_folder", "")
            if backup_folder_str:
                backup_folder = Path(backup_folder_str)
            else:
                backup_folder = Path.home() / ".skcc_awards" / "backups"
                
            backup_folder.mkdir(parents=True, exist_ok=True)
            primary_backup = backup_folder / backup_name
            shutil.copy2(source_file, primary_backup)
                    
            # Clean up old backups
            self._cleanup_old_backups(backup_folder, source_path.stem)
            return True
            
        except Exception as e:
            print(f"Backup failed: {e}")
            return False
    
    def _cleanup_old_backups(self, backup_folder: Path, file_stem: str) -> None:
        """Keep only the most recent backups for each file."""
        try:
            max_backups = self.config.get("max_backups", 10)
            pattern = f"{file_stem}_backup_*"
            backups = sorted(backup_folder.glob(pattern), 
                           key=lambda p: p.stat().st_mtime, reverse=True)
            
            # Remove backups beyond the maximum
            for old_backup in backups[max_backups:]:
                old_backup.unlink()
        except Exception:
            pass
    
    def get_backup_folder(self) -> Path:
        """Get the primary backup folder path."""
        backup_folder_str = self.config.get("backup_folder", "")
        if backup_folder_str:
            return Path(backup_folder_str)
        else:
            return Path.home() / ".skcc_awards" / "backups"

# Global backup manager instance
backup_manager = BackupManager()
