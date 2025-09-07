#!/usr/bin/env python3
"""
Check if Python and required modules are properly installed
"""

import sys


def check_python_version():
    """Check if Python version is sufficient"""
    print(f"Python version: {sys.version}")
    # Require Python 3.9+ (align with project runtime); noqa: UP036
    if sys.version_info < (3, 9):
        print("❌ Python 3.9 or higher is required")
        return False
    print("✅ Python version is sufficient")
    return True


def check_module(module_name, package_name=None):
    """Check if a module can be imported"""
    if package_name is None:
        package_name = module_name

    try:
        __import__(module_name)
        print(f"✅ {module_name} is installed")
        return True
    except ImportError:
        print(f"❌ {module_name} is not installed")
        print(f"   Install with: pip install {package_name}")
        return False


def main():
    print("SKCC Awards Calculator - Dependency Check")
    print("=" * 45)
    print()

    all_good = True

    # Check Python version
    if not check_python_version():
        all_good = False
    print()

    # Check required modules
    print("Checking required modules:")
    required_modules = [
        ("httpx", "httpx"),
        ("bs4", "beautifulsoup4"),
    ]

    for module, package in required_modules:
        if not check_module(module, package):
            all_good = False

    print()

    # Check built-in modules that should always be available
    print("Checking built-in modules:")
    builtin_modules = ["tkinter", "threading", "asyncio", "csv", "json", "re"]
    for module in builtin_modules:
        check_module(module)

    print()

    if all_good:
        print("🎉 All dependencies are installed! You can run the program.")
        print("   Start with: python w4gns_skcc_logger.py")
    else:
        print("⚠️  Some dependencies are missing. Install them with:")
        print("   pip install httpx beautifulsoup4")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
