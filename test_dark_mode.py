#!/usr/bin/env python3
"""Test the dark mode theme functionality."""

import sys
from pathlib import Path
import tempfile
import json

# Add the repo root to Python path for imports
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.theme_manager import ThemeManager

def test_theme_manager():
    """Test the theme manager functionality."""
    print("Testing dark mode theme manager...")
    
    # Use a temporary config file for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a test theme manager with custom config location
        tm = ThemeManager()
        tm.config_file = Path(temp_dir) / "test_theme_config.json"
        
        # Test initial state
        assert tm.current_theme == "light", f"Expected light theme, got {tm.current_theme}"
        print("✓ Initial theme is light")
        
        # Test theme colors
        light_colors = tm.get_colors("light")
        dark_colors = tm.get_colors("dark")
        
        assert light_colors["bg"] == "#ffffff", "Light background should be white"
        assert dark_colors["bg"] == "#2d2d2d", "Dark background should be dark gray"
        print("✓ Theme colors are correct")
        
        # Test theme toggle
        new_theme = tm.toggle_theme()
        assert new_theme == "dark", f"Expected dark theme after toggle, got {new_theme}"
        assert tm.current_theme == "dark", "Current theme should be dark"
        print("✓ Theme toggle works")
        
        # Test theme persistence
        tm._save_theme_preference()
        
        # Create new instance and verify it loads the saved theme
        tm2 = ThemeManager()
        tm2.config_file = tm.config_file
        tm2._load_theme_preference()
        assert tm2.current_theme == "dark", "Theme should persist across instances"
        print("✓ Theme persistence works")
        
        # Test set_theme
        tm.set_theme("light")
        assert tm.current_theme == "light", "set_theme should work"
        print("✓ set_theme works")
        
        # Test invalid theme (should not change)
        tm.set_theme("invalid")
        assert tm.current_theme == "light", "Invalid theme should not change current theme"
        print("✓ Invalid theme handling works")
    
    print("\n🎨 All dark mode tests passed! Theme functionality is working correctly.")
    return True

if __name__ == "__main__":
    success = test_theme_manager()
    sys.exit(0 if success else 1)
