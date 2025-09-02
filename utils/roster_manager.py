"""SKCC Member Roster Database Manager for QSO Logger."""

import sqlite3
import asyncio
import json
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime, timedelta
import sys

# Add backend app to path for roster functions
ROOT = Path(__file__).resolve().parents[1]
BACKEND_APP = ROOT / "backend" / "app"
if str(BACKEND_APP) not in sys.path:
    sys.path.insert(0, str(BACKEND_APP))

try:
    from services.skcc import fetch_member_roster, Member
except ImportError:
    # Fallback if backend services not available
    from dataclasses import dataclass
    from typing import Optional

    @dataclass(frozen=True)
    class Member:
        call: str
        number: int
        join_date: Optional[str] = None
        suffix: Optional[str] = None
        state: Optional[str] = None

    async def fetch_member_roster():
        """Fallback roster fetcher - returns empty list."""
        return []


class RosterDatabase:
    """Manages local SKCC roster database for the QSO logger."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the roster database."""
        if db_path is None:
            # Default location: ~/.skcc_awards/roster.db
            self.db_path = Path.home() / ".skcc_awards" / "roster.db"
        else:
            self.db_path = db_path

        self.db_path.parent.mkdir(exist_ok=True)
        self._init_database()

    def _get_connection(self, timeout=30.0):
        """Get a database connection with proper timeout and settings."""
        conn = sqlite3.connect(self.db_path, timeout=timeout)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        return conn

    def _execute_with_retry(self, operation_func, max_retries=3):
        """Execute a database operation with retry logic for locked database."""
        import time

        for attempt in range(max_retries):
            try:
                return operation_func()
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 0.5  # Progressive backoff
                    print(
                        f"Database locked, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    raise

        raise sqlite3.OperationalError("Database operation failed after all retries")

    def _init_database(self) -> None:
        """Initialize the database schema."""
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                    # Enable WAL mode for better concurrent access
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.execute("PRAGMA synchronous=NORMAL")
                    conn.execute("PRAGMA temp_store=MEMORY")
                    conn.execute("PRAGMA mmap_size=268435456")  # 256MB

                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS roster_metadata (
                            key TEXT PRIMARY KEY,
                            value TEXT
                        )
                    """
                    )

                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS members (
                            number INTEGER PRIMARY KEY,
                            call TEXT NOT NULL,
                            suffix TEXT,
                            join_date TEXT,
                            state TEXT,
                            updated_at TEXT NOT NULL
                        )
                    """
                    )

                    # Add state column if it doesn't exist (migration for existing databases)
                    try:
                        conn.execute("ALTER TABLE members ADD COLUMN state TEXT")
                    except sqlite3.OperationalError:
                        # Column already exists or other error, continue
                        pass

                    # Create index for fast callsign lookups
                    conn.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_members_call 
                        ON members(call)
                    """
                    )

                    # Create index for callsign prefix searches
                    conn.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_members_call_prefix
                        ON members(call COLLATE NOCASE)
                    """
                    )

                    conn.commit()
                    break

            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and retry_count < max_retries - 1:
                    retry_count += 1
                    print(f"Database locked, retrying ({retry_count}/{max_retries})...")
                    import time

                    time.sleep(1)
                    continue
                else:
                    raise

    def get_last_update(self) -> Optional[datetime]:
        """Get the timestamp of the last roster update."""

        def operation():
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT value FROM roster_metadata WHERE key = ?", ("last_update",)
                )
                row = cursor.fetchone()
                if row:
                    try:
                        return datetime.fromisoformat(row[0])
                    except ValueError:
                        return None
                return None

        return self._execute_with_retry(operation)

    def set_last_update(self, timestamp: datetime) -> None:
        """Set the timestamp of the last roster update."""

        def operation():
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO roster_metadata (key, value) VALUES (?, ?)",
                    ("last_update", timestamp.isoformat()),
                )
                conn.commit()

        self._execute_with_retry(operation)

    def get_member_count(self) -> int:
        """Get the number of members in the database."""

        def operation():
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM members")
                return cursor.fetchone()[0]

        return self._execute_with_retry(operation)

    def update_roster(self, members: List[Member]) -> int:
        """Update the roster database with new member data."""

        def operation():
            now = datetime.now().isoformat()
            updated_count = 0

            with self._get_connection() as conn:
                # Clear existing data
                conn.execute("DELETE FROM members")

                # Insert new member data in batches
                batch_size = 1000
                for i in range(0, len(members), batch_size):
                    batch = members[i : i + batch_size]
                    member_data = [
                        (
                            member.number,
                            member.call.upper(),
                            member.suffix,
                            member.join_date,
                            member.state,
                            now,
                        )
                        for member in batch
                    ]

                    conn.executemany(
                        """
                        INSERT INTO members (number, call, suffix, join_date, state, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        member_data,
                    )

                    updated_count += len(batch)

                # Update metadata
                conn.execute(
                    "INSERT OR REPLACE INTO roster_metadata (key, value) VALUES (?, ?)",
                    ("last_update", datetime.now().isoformat()),
                )
                conn.commit()

            return updated_count

        return self._execute_with_retry(operation)

    def lookup_call(self, call: str) -> Optional[Tuple[int, str, str]]:
        """Look up a member by callsign. Returns (number, suffix, state) or None."""
        if not call:
            return None

        def operation():
            call_upper = call.upper().strip()

            with self._get_connection() as conn:
                # First try exact match
                cursor = conn.execute(
                    "SELECT number, suffix, state FROM members WHERE call = ?",
                    (call_upper,),
                )
                row = cursor.fetchone()
                if row:
                    suffix = row[1] or ""
                    state = row[2] or ""
                    return (row[0], suffix, state)

                # If no exact match, try without portable indicators
                base_call = call_upper.split("/")[0]  # Remove /P, /M, etc.
                if base_call != call_upper:
                    cursor = conn.execute(
                        "SELECT number, suffix, state FROM members WHERE call = ?",
                        (base_call,),
                    )
                    row = cursor.fetchone()
                    if row:
                        suffix = row[1] or ""
                        state = row[2] or ""
                        return (row[0], suffix, state)

            return None

        return self._execute_with_retry(operation)

    def search_calls(self, prefix: str, limit: int = 10) -> List[Tuple[str, int, str, str]]:
        """Search for callsigns starting with the given prefix."""
        if not prefix:
            return []

        def operation():
            prefix_upper = prefix.upper().strip()

            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT call, number, COALESCE(suffix, '') as suffix, COALESCE(state, '') as state 
                    FROM members 
                    WHERE call LIKE ? 
                    ORDER BY call 
                    LIMIT ?
                """,
                    (f"{prefix_upper}%", limit),
                )

                return cursor.fetchall()

        return self._execute_with_retry(operation)

    def needs_update(self, max_age_hours: int = 24) -> bool:
        """Check if the roster needs updating based on age."""
        try:
            last_update = self.get_last_update()
            if last_update is None:
                return True

            age = datetime.now() - last_update
            return age > timedelta(hours=max_age_hours)
        except Exception:
            # If we can't determine last update, assume we need to update
            return True

    def cleanup_database(self) -> bool:
        """Clean up database by removing locks and optimizing."""
        try:
            # First try to close any existing connections
            # by opening a new one and immediately closing it
            with self._get_connection(timeout=5.0) as conn:
                conn.execute("PRAGMA optimize")
                conn.commit()

            # Check if WAL files exist and clean them up
            wal_file = Path(str(self.db_path) + "-wal")
            shm_file = Path(str(self.db_path) + "-shm")

            if wal_file.exists() or shm_file.exists():
                with self._get_connection(timeout=5.0) as conn:
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    conn.commit()

            return True
        except Exception as e:
            print(f"Database cleanup failed: {e}")
            return False


class RosterManager:
    """High-level manager for roster operations in the QSO logger."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the roster manager."""
        self.db = RosterDatabase(db_path)
        self._update_in_progress = False

    async def ensure_roster_updated(
        self, force: bool = False, progress_callback=None, max_age_hours: int = 24
    ) -> Tuple[bool, str]:
        """
        Ensure the roster is up to date.

        Args:
            force: Force update even if roster is recent
            progress_callback: Optional callback for progress updates
            max_age_hours: Maximum age in hours before update is needed

        Returns:
            (success, message) tuple
        """
        if self._update_in_progress:
            return False, "Update already in progress"

        try:
            self._update_in_progress = True

            # Try to clean up database first if there are issues
            try:
                if not force and not self.db.needs_update(max_age_hours):
                    count = self.db.get_member_count()
                    return True, f"Roster is current ({count:,} members)"
            except Exception as e:
                if progress_callback:
                    progress_callback(f"Database issue detected, attempting cleanup: {e}")

                # Try cleanup
                if self.db.cleanup_database():
                    if progress_callback:
                        progress_callback("Database cleanup successful")
                else:
                    if progress_callback:
                        progress_callback("Database cleanup failed, proceeding with update")

            if progress_callback:
                progress_callback("Fetching SKCC roster...")

            # Fetch roster from SKCC website
            members = await fetch_member_roster()

            if not members:
                return False, "Failed to fetch roster from SKCC website"

            if progress_callback:
                progress_callback(f"Updating database with {len(members):,} members...")

            # Update database
            try:
                updated_count = self.db.update_roster(members)

                message = f"Roster updated: {updated_count:,} members"
                if progress_callback:
                    progress_callback(message)

                return True, message

            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower():
                    error_msg = "Database is locked by another process. Please close other SKCC applications and try again."
                else:
                    error_msg = f"Database error: {e}"

                if progress_callback:
                    progress_callback(error_msg)
                return False, error_msg

        except Exception as e:
            error_msg = f"Roster update failed: {e}"
            if progress_callback:
                progress_callback(error_msg)
            return False, error_msg

        finally:
            self._update_in_progress = False

    def lookup_member(self, call: str) -> Optional[Dict[str, str]]:
        """
        Look up member information for a callsign.

        Returns:
            Dict with 'number', 'suffix', and 'state' keys, or None if not found
        """
        result = self.db.lookup_call(call)
        if result:
            number, suffix, state = result
            return {
                "number": str(number) + suffix,
                "suffix": suffix,
                "state": state or "",
            }
        return None

    def search_callsigns(self, prefix: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Search for callsigns matching a prefix.

        Returns:
            List of dicts with 'call', 'number', 'suffix', and 'state' keys
        """
        results = self.db.search_calls(prefix, limit)
        return [
            {
                "call": call,
                "number": str(number) + suffix,
                "suffix": suffix,
                "state": state,
            }
            for call, number, suffix, state in results
        ]

    def get_status(self) -> Dict[str, Any]:
        """Get roster database status information."""
        last_update = self.db.get_last_update()
        member_count = self.db.get_member_count()
        needs_update = self.db.needs_update()

        return {
            "member_count": member_count,
            "last_update": last_update.isoformat() if last_update else None,
            "needs_update": needs_update,
            "update_in_progress": self._update_in_progress,
        }
