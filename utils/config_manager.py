"""Configuration management for SKCC Awards and QSO Logger."""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict, field


@dataclass
class UserSettings:
    """User configuration settings."""

    # Station information
    station_callsign: str = ""
    operator: str = ""
    my_skcc_number: str = ""
    default_power: int = 5
    default_key_type: str = "straight"

    # File locations
    default_adif_file: str = "qso_log.adi"
    log_directory: str = ""

    # Roster settings
    auto_update_roster: bool = True
    roster_update_hours: int = 24

    # UI preferences
    theme: str = "light"
    window_geometry: Dict[str, str] = field(default_factory=dict)


class ConfigManager:
    """Manages application configuration and user settings."""

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize configuration manager."""
        if config_dir is None:
            self.config_dir = Path.home() / ".skcc_awards"
        else:
            self.config_dir = config_dir

        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / "config.json"
        self.settings = self._load_settings()

    def _load_settings(self) -> UserSettings:
        """Load settings from configuration file."""
        if not self.config_file.exists():
            return UserSettings()

        try:
            with open(self.config_file, "r") as f:
                data = json.load(f)

            # Convert dict to UserSettings, handling missing fields gracefully
            settings_dict = {}
            for field_name in UserSettings.__dataclass_fields__:
                if field_name in data:
                    settings_dict[field_name] = data[field_name]

            return UserSettings(**settings_dict)

        except (json.JSONDecodeError, TypeError, ValueError) as e:
            print(f"Warning: Failed to load config: {e}")
            return UserSettings()

    def save_settings(self) -> None:
        """Save current settings to configuration file."""
        try:
            with open(self.config_file, "w") as f:
                json.dump(asdict(self.settings), f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save config: {e}")

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a specific setting value."""
        return getattr(self.settings, key, default)

    def set_setting(self, key: str, value: Any) -> None:
        """Set a specific setting value."""
        if hasattr(self.settings, key):
            setattr(self.settings, key, value)
            self.save_settings()

    def update_settings(self, **kwargs) -> None:
        """Update multiple settings at once."""
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        self.save_settings()

    def get_data_dir(self) -> Path:
        """Get the data directory path."""
        return self.config_dir

    def get_default_adif_path(self) -> Path:
        """Get the default ADIF file path."""
        if self.settings.log_directory:
            log_dir = Path(self.settings.log_directory)
        else:
            log_dir = self.config_dir / "logs"

        log_dir.mkdir(exist_ok=True)
        return log_dir / self.settings.default_adif_file

    def reset_to_defaults(self) -> None:
        """Reset all settings to defaults."""
        self.settings = UserSettings()
        self.save_settings()


# Global config instance
_config_manager = None


def get_config() -> ConfigManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
