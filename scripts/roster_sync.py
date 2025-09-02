"""Command-line utility to sync SKCC member roster."""

import asyncio
import argparse
import sys
from pathlib import Path

# Add parent directory to path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.roster_manager import RosterManager


async def sync_roster(force=False, verbose=False):
    """Sync the SKCC member roster."""
    print("SKCC Roster Sync Utility")
    print("=" * 30)

    rm = RosterManager()

    # Get current status
    status = rm.get_status()

    if verbose:
        print(f"Current roster status:")
        print(f"  Members: {status['member_count']:,}")
        print(f"  Last update: {status['last_update'] or 'Never'}")
        print(f"  Needs update: {status['needs_update']}")
        print()

    if not force and not status["needs_update"]:
        print(f"✓ Roster is current ({status['member_count']:,} members)")
        return

    def progress_callback(message):
        if verbose:
            print(f"  {message}")

    print("Updating roster from SKCC website...")

    try:
        success, message = await rm.ensure_roster_updated(
            force=force, progress_callback=progress_callback if verbose else None
        )

        if success:
            new_status = rm.get_status()
            print(f"✓ {message}")
            print(f"✓ Database updated with {new_status['member_count']:,} members")
        else:
            print(f"✗ Update failed: {message}")
            return 1

    except Exception as e:
        print(f"✗ Error during update: {e}")
        return 1

    return 0


def lookup_call(call):
    """Look up a specific callsign."""
    rm = RosterManager()

    status = rm.get_status()
    if status["member_count"] == 0:
        print("No roster data available. Run sync first.")
        return 1

    result = rm.lookup_member(call.upper())
    if result:
        print(f"✓ {call.upper()}: SKCC #{result['number']}")
    else:
        print(f"✗ {call.upper()}: Not found in roster")

    return 0


def search_calls(prefix, limit=10):
    """Search for callsigns with a prefix."""
    rm = RosterManager()

    status = rm.get_status()
    if status["member_count"] == 0:
        print("No roster data available. Run sync first.")
        return 1

    results = rm.search_callsigns(prefix.upper(), limit=limit)

    if results:
        print(f"Found {len(results)} callsigns starting with '{prefix.upper()}':")
        for result in results:
            print(f"  {result['call']} - SKCC #{result['number']}")
    else:
        print(f"No callsigns found starting with '{prefix.upper()}'")

    return 0


def cleanup_database():
    """Clean up the roster database."""
    rm = RosterManager()

    print("SKCC Roster Database Cleanup")
    print("=" * 30)

    try:
        if rm.db.cleanup_database():
            print("✓ Database cleanup completed successfully")

            # Show updated status
            status = rm.get_status()
            print(f"✓ Members: {status['member_count']:,}")
            return 0
        else:
            print("✗ Database cleanup failed")
            return 1

    except Exception as e:
        print(f"✗ Cleanup error: {e}")
        return 1


def show_status():
    """Show roster database status."""
    rm = RosterManager()
    status = rm.get_status()

    print("SKCC Roster Database Status")
    print("=" * 30)
    print(f"Members: {status['member_count']:,}")
    print(f"Last update: {status['last_update'] or 'Never'}")
    print(f"Needs update: {'Yes' if status['needs_update'] else 'No'}")
    print(f"Update in progress: {'Yes' if status['update_in_progress'] else 'No'}")

    if status["member_count"] > 0:
        print(f"\nDatabase location: {rm.db.db_path}")

    return 0


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="SKCC Member Roster Management Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s sync              # Update roster if needed
  %(prog)s sync --force      # Force update even if current
  %(prog)s lookup W1AW       # Look up specific callsign
  %(prog)s search W1 --limit 5  # Search for callsigns starting with W1
  %(prog)s status            # Show database status
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Sync command
    sync_parser = subparsers.add_parser("sync", help="Update the roster database")
    sync_parser.add_argument(
        "--force", action="store_true", help="Force update even if roster is current"
    )
    sync_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed progress information",
    )

    # Lookup command
    lookup_parser = subparsers.add_parser("lookup", help="Look up a specific callsign")
    lookup_parser.add_argument("call", help="Callsign to look up")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search for callsigns by prefix")
    search_parser.add_argument("prefix", help="Callsign prefix to search for")
    search_parser.add_argument(
        "--limit", type=int, default=10, help="Maximum number of results (default: 10)"
    )

    # Status command
    status_parser = subparsers.add_parser("status", help="Show roster database status")

    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean up database locks and optimize")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    try:
        if args.command == "sync":
            return asyncio.run(sync_roster(force=args.force, verbose=args.verbose))
        elif args.command == "lookup":
            return lookup_call(args.call)
        elif args.command == "search":
            return search_calls(args.prefix, args.limit)
        elif args.command == "status":
            return show_status()
        elif args.command == "cleanup":
            return cleanup_database()
        else:
            parser.print_help()
            return 1

    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
