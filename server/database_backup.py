import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging
from sqlalchemy import text

from database import get_database_url, get_database_info, engine

logger = logging.getLogger(__name__)


class DatabaseBackupError(Exception):
    """Custom exception for database backup/restore operations"""
    pass


class DatabaseBackupManager:
    """
    Manages database backup and restore operations for both SQLite and PostgreSQL.
    """
    
    def __init__(self, backup_dir: str = "backups"):
        """
        Initialize the backup manager.
        
        Args:
            backup_dir: Directory to store backup files
        """
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        self.db_info = get_database_info()
        
    def generate_backup_filename(self, prefix: str = "backup") -> str:
        """
        Generate a timestamped backup filename.
        
        Args:
            prefix: Prefix for the backup filename
            
        Returns:
            Backup filename with timestamp
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        db_type = self.db_info["database_type"]
        
        if db_type == "sqlite":
            return f"{prefix}_{timestamp}.db"
        elif db_type == "postgresql":
            return f"{prefix}_{timestamp}.sql"
        else:
            return f"{prefix}_{timestamp}.backup"
    
    def create_backup(self, backup_name: Optional[str] = None, compress: bool = True) -> Dict[str, Any]:
        """
        Create a backup of the current database.
        
        Args:
            backup_name: Optional custom backup filename
            compress: Whether to compress the backup (PostgreSQL only)
            
        Returns:
            Dictionary with backup information
        """
        try:
            if backup_name is None:
                backup_name = self.generate_backup_filename()
            
            backup_path = self.backup_dir / backup_name
            
            if self.db_info["database_type"] == "sqlite":
                return self._backup_sqlite(backup_path)
            elif self.db_info["database_type"] == "postgresql":
                return self._backup_postgresql(backup_path, compress)
            else:
                raise DatabaseBackupError(f"Unsupported database type: {self.db_info['database_type']}")
                
        except Exception as e:
            logger.error(f"Backup failed: {str(e)}")
            raise DatabaseBackupError(f"Backup failed: {str(e)}")
    
    def _backup_sqlite(self, backup_path: Path) -> Dict[str, Any]:
        """
        Create a backup of SQLite database.
        
        Args:
            backup_path: Path where backup will be saved
            
        Returns:
            Backup information dictionary
        """
        database_url = get_database_url()
        
        # Extract database file path from URL
        if database_url.startswith("sqlite:///"):
            db_file_path = database_url.replace("sqlite:///", "")
            if db_file_path.startswith("./"):
                db_file_path = db_file_path[2:]
        else:
            raise DatabaseBackupError("Invalid SQLite database URL")
        
        source_path = Path(db_file_path)
        
        if not source_path.exists():
            raise DatabaseBackupError(f"Database file not found: {source_path}")
        
        # Use SQLite VACUUM INTO for consistent backup
        try:
            with engine.connect() as connection:
                # Use raw SQL for VACUUM INTO (not available in all SQLAlchemy versions)
                connection.execute(text(f"VACUUM INTO '{backup_path.absolute()}'"))
                connection.commit()
            
            backup_info = {
                "backup_path": str(backup_path),
                "backup_size": backup_path.stat().st_size,
                "database_type": "sqlite",
                "created_at": datetime.now().isoformat(),
                "source_database": str(source_path),
                "method": "vacuum_into"
            }
            
            logger.info(f"SQLite backup created: {backup_path}")
            return backup_info
            
        except Exception as e:
            # Fallback to file copy if VACUUM INTO fails
            logger.warning(f"VACUUM INTO failed, falling back to file copy: {e}")
            return self._backup_sqlite_copy(source_path, backup_path)
    
    def _backup_sqlite_copy(self, source_path: Path, backup_path: Path) -> Dict[str, Any]:
        """
        Fallback method to backup SQLite using file copy.
        
        Args:
            source_path: Source database file path
            backup_path: Destination backup file path
            
        Returns:
            Backup information dictionary
        """
        shutil.copy2(source_path, backup_path)
        
        backup_info = {
            "backup_path": str(backup_path),
            "backup_size": backup_path.stat().st_size,
            "database_type": "sqlite",
            "created_at": datetime.now().isoformat(),
            "source_database": str(source_path),
            "method": "file_copy"
        }
        
        logger.info(f"SQLite backup created (file copy): {backup_path}")
        return backup_info
    
    def _backup_postgresql(self, backup_path: Path, compress: bool = True) -> Dict[str, Any]:
        """
        Create a backup of PostgreSQL database using pg_dump.
        
        Args:
            backup_path: Path where backup will be saved
            compress: Whether to compress the backup
            
        Returns:
            Backup information dictionary
        """
        database_url = get_database_url()
        
        # Parse PostgreSQL URL
        if not database_url.startswith("postgresql://"):
            raise DatabaseBackupError("Invalid PostgreSQL database URL")
        
        # Build pg_dump command
        cmd = ["pg_dump", database_url]
        
        if compress:
            cmd.extend(["--compress=9"])  # Maximum compression
            if not backup_path.suffix:
                backup_path = backup_path.with_suffix(".sql.gz")
        
        cmd.extend(["--file", str(backup_path)])
        
        try:
            # Execute pg_dump
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                raise DatabaseBackupError(f"pg_dump failed: {result.stderr}")
            
            backup_info = {
                "backup_path": str(backup_path),
                "backup_size": backup_path.stat().st_size,
                "database_type": "postgresql",
                "created_at": datetime.now().isoformat(),
                "compressed": compress,
                "method": "pg_dump"
            }
            
            logger.info(f"PostgreSQL backup created: {backup_path}")
            return backup_info
            
        except subprocess.TimeoutExpired:
            raise DatabaseBackupError("Backup operation timed out")
        except FileNotFoundError:
            raise DatabaseBackupError("pg_dump command not found. Please install PostgreSQL client tools.")
    
    def restore_backup(self, backup_path: str, confirm: bool = False) -> Dict[str, Any]:
        """
        Restore database from a backup file.
        
        Args:
            backup_path: Path to the backup file
            confirm: Confirmation that user wants to proceed with restore
            
        Returns:
            Dictionary with restore information
        """
        if not confirm:
            raise DatabaseBackupError("Restore operation requires explicit confirmation")
        
        backup_file = Path(backup_path)
        
        if not backup_file.exists():
            raise DatabaseBackupError(f"Backup file not found: {backup_path}")
        
        try:
            if self.db_info["database_type"] == "sqlite":
                return self._restore_sqlite(backup_file)
            elif self.db_info["database_type"] == "postgresql":
                return self._restore_postgresql(backup_file)
            else:
                raise DatabaseBackupError(f"Unsupported database type: {self.db_info['database_type']}")
                
        except Exception as e:
            logger.error(f"Restore failed: {str(e)}")
            raise DatabaseBackupError(f"Restore failed: {str(e)}")
    
    def _restore_sqlite(self, backup_file: Path) -> Dict[str, Any]:
        """
        Restore SQLite database from backup.
        
        Args:
            backup_file: Path to backup file
            
        Returns:
            Restore information dictionary
        """
        database_url = get_database_url()
        
        # Extract current database file path
        if database_url.startswith("sqlite:///"):
            db_file_path = database_url.replace("sqlite:///", "")
            if db_file_path.startswith("./"):
                db_file_path = db_file_path[2:]
        else:
            raise DatabaseBackupError("Invalid SQLite database URL")
        
        current_db_path = Path(db_file_path)
        current_backup = None
        
        # Create backup of current database before restoring
        if current_db_path.exists():
            current_backup = current_db_path.with_suffix(f".{datetime.now().strftime('%Y%m%d_%H%M%S')}.backup")
            shutil.copy2(current_db_path, current_backup)
            logger.info(f"Current database backed up to: {current_backup}")
        
        # Restore from backup
        shutil.copy2(backup_file, current_db_path)
        
        restore_info = {
            "restored_from": str(backup_file),
            "restored_to": str(current_db_path),
            "database_type": "sqlite",
            "restored_at": datetime.now().isoformat(),
            "current_backup": str(current_backup) if current_backup else None
        }
        
        logger.info(f"SQLite database restored from: {backup_file}")
        return restore_info
    
    def _restore_postgresql(self, backup_file: Path) -> Dict[str, Any]:
        """
        Restore PostgreSQL database from backup.
        
        Args:
            backup_file: Path to backup file
            
        Returns:
            Restore information dictionary
        """
        database_url = get_database_url()
        
        if not database_url.startswith("postgresql://"):
            raise DatabaseBackupError("Invalid PostgreSQL database URL")
        
        # Build restore command
        if backup_file.suffix.endswith('.gz'):
            # Compressed backup
            cmd = ["gunzip", "-c", str(backup_file), "|", "psql", database_url]
        else:
            cmd = ["psql", database_url, "--file", str(backup_file)]
        
        try:
            if backup_file.suffix.endswith('.gz'):
                # Handle compressed file with shell pipe
                result = subprocess.run(
                    f"gunzip -c {backup_file} | psql {database_url}",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=600  # 10 minute timeout
                )
            else:
                result = subprocess.run(
                    ["psql", database_url, "--file", str(backup_file)],
                    capture_output=True,
                    text=True,
                    timeout=600
                )
            
            if result.returncode != 0:
                raise DatabaseBackupError(f"Database restore failed: {result.stderr}")
            
            restore_info = {
                "restored_from": str(backup_file),
                "database_type": "postgresql",
                "restored_at": datetime.now().isoformat(),
                "method": "psql"
            }
            
            logger.info(f"PostgreSQL database restored from: {backup_file}")
            return restore_info
            
        except subprocess.TimeoutExpired:
            raise DatabaseBackupError("Restore operation timed out")
        except FileNotFoundError:
            raise DatabaseBackupError("psql command not found. Please install PostgreSQL client tools.")
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """
        List all available backups in the backup directory.
        
        Returns:
            List of backup information dictionaries
        """
        backups = []
        
        for backup_file in self.backup_dir.iterdir():
            if backup_file.is_file():
                backup_info = {
                    "filename": backup_file.name,
                    "path": str(backup_file),
                    "size": backup_file.stat().st_size,
                    "created": datetime.fromtimestamp(backup_file.stat().st_mtime).isoformat(),
                    "type": self._guess_backup_type(backup_file)
                }
                backups.append(backup_info)
        
        # Sort by creation time (newest first)
        backups.sort(key=lambda x: x["created"], reverse=True)
        return backups
    
    def _guess_backup_type(self, backup_file: Path) -> str:
        """
        Guess backup type from file extension.
        
        Args:
            backup_file: Path to backup file
            
        Returns:
            Guessed backup type
        """
        suffix = backup_file.suffix.lower()
        
        if suffix == ".db":
            return "sqlite"
        elif suffix in [".sql", ".gz"]:
            return "postgresql"
        else:
            return "unknown"
    
    def cleanup_old_backups(self, keep_count: int = 10) -> int:
        """
        Clean up old backup files, keeping only the most recent ones.
        
        Args:
            keep_count: Number of recent backups to keep
            
        Returns:
            Number of backups deleted
        """
        backups = self.list_backups()
        
        if len(backups) <= keep_count:
            return 0
        
        backups_to_delete = backups[keep_count:]
        deleted_count = 0
        
        for backup in backups_to_delete:
            try:
                Path(backup["path"]).unlink()
                deleted_count += 1
                logger.info(f"Deleted old backup: {backup['filename']}")
            except Exception as e:
                logger.error(f"Failed to delete backup {backup['filename']}: {e}")
        
        return deleted_count


# Convenience functions for command-line usage
def create_backup(backup_name: Optional[str] = None, backup_dir: str = "backups") -> Dict[str, Any]:
    """
    Create a database backup.
    
    Args:
        backup_name: Optional custom backup name
        backup_dir: Directory to store backups
        
    Returns:
        Backup information dictionary
    """
    manager = DatabaseBackupManager(backup_dir)
    return manager.create_backup(backup_name)


def restore_backup(backup_path: str, confirm: bool = False, backup_dir: str = "backups") -> Dict[str, Any]:
    """
    Restore database from backup.
    
    Args:
        backup_path: Path to backup file
        confirm: Confirmation for destructive operation
        backup_dir: Directory containing backups
        
    Returns:
        Restore information dictionary
    """
    manager = DatabaseBackupManager(backup_dir)
    return manager.restore_backup(backup_path, confirm)


def list_backups(backup_dir: str = "backups") -> List[Dict[str, Any]]:
    """
    List available backups.
    
    Args:
        backup_dir: Directory containing backups
        
    Returns:
        List of backup information dictionaries
    """
    manager = DatabaseBackupManager(backup_dir)
    return manager.list_backups()


if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Database Backup and Restore Utility")
    parser.add_argument("action", choices=["backup", "restore", "list", "cleanup"], help="Action to perform")
    parser.add_argument("--backup-dir", default="backups", help="Backup directory")
    parser.add_argument("--name", help="Backup name (for backup action)")
    parser.add_argument("--path", help="Backup file path (for restore action)")
    parser.add_argument("--confirm", action="store_true", help="Confirm destructive operations")
    parser.add_argument("--keep", type=int, default=10, help="Number of backups to keep (for cleanup)")
    
    args = parser.parse_args()
    
    try:
        if args.action == "backup":
            result = create_backup(args.name, args.backup_dir)
            print(json.dumps(result, indent=2))
            
        elif args.action == "restore":
            if not args.path:
                parser.error("--path is required for restore action")
            result = restore_backup(args.path, args.confirm, args.backup_dir)
            print(json.dumps(result, indent=2))
            
        elif args.action == "list":
            result = list_backups(args.backup_dir)
            print(json.dumps(result, indent=2))
            
        elif args.action == "cleanup":
            manager = DatabaseBackupManager(args.backup_dir)
            deleted_count = manager.cleanup_old_backups(args.keep)
            print(f"Deleted {deleted_count} old backups")
            
    except DatabaseBackupError as e:
        print(f"Error: {e}")
        exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        exit(1) 