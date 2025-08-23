"""
Simple migration system for DuckDB - inspired by Alembic
"""

import os
import hashlib
from datetime import datetime
from typing import List, Callable
from sqlalchemy import text, Column, String, DateTime, Integer, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.duckdb_config import engine, SessionLocal

# Migration tracking table
MigrationBase = declarative_base()

class MigrationRecord(MigrationBase):
    __tablename__ = "schema_migrations"
    
    id = Column(Integer, primary_key=True)
    version = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    applied_at = Column(DateTime, nullable=False)
    checksum = Column(String(64), nullable=False)


class Migration:
    """Single migration with up/down operations"""
    
    def __init__(self, version: str, name: str, up: Callable, down: Callable = None):
        self.version = version
        self.name = name
        self.up = up
        self.down = down
        self.checksum = self._calculate_checksum()
    
    def _calculate_checksum(self) -> str:
        """Calculate checksum of migration content"""
        content = f"{self.version}:{self.name}:{self.up.__code__.co_code}"
        return hashlib.sha256(content.encode()).hexdigest()


class MigrationRunner:
    """Migration runner - like Alembic's migrate command"""
    
    def __init__(self):
        self.migrations: List[Migration] = []
        self._ensure_migration_table()
    
    def _ensure_migration_table(self):
        """Create migration tracking table if it doesn't exist"""
        MigrationBase.metadata.create_all(engine)
    
    def add_migration(self, version: str, name: str, up: Callable, down: Callable = None):
        """Add a migration (like creating a new revision)"""
        migration = Migration(version, name, up, down)
        self.migrations.append(migration)
        return migration
    
    def get_applied_migrations(self) -> List[str]:
        """Get list of applied migration versions"""
        with SessionLocal() as session:
            records = session.query(MigrationRecord).all()
            return [r.version for r in records]
    
    def get_pending_migrations(self) -> List[Migration]:
        """Get migrations that haven't been applied yet"""
        applied = set(self.get_applied_migrations())
        return [m for m in self.migrations if m.version not in applied]
    
    def migrate(self, target_version: str = None):
        """Run pending migrations (like alembic upgrade)"""
        pending = self.get_pending_migrations()
        
        if target_version:
            # Run up to specific version
            target_index = next((i for i, m in enumerate(pending) if m.version == target_version), None)
            if target_index is None:
                print(f"Migration version {target_version} not found")
                return
            pending = pending[:target_index + 1]
        
        if not pending:
            print("✅ No pending migrations")
            return
        
        print(f"🚀 Running {len(pending)} migration(s)...")
        
        for migration in pending:
            print(f"   Applying {migration.version}: {migration.name}")
            try:
                with SessionLocal() as session:
                    # Run the migration
                    migration.up(session)
                    
                    # Record as applied
                    record = MigrationRecord(
                        version=migration.version,
                        name=migration.name,
                        applied_at=datetime.utcnow(),
                        checksum=migration.checksum
                    )
                    session.add(record)
                    session.commit()
                    print(f"   ✅ Applied {migration.version}")
                    
            except Exception as e:
                print(f"   ❌ Failed {migration.version}: {e}")
                raise
        
        print("✅ All migrations completed successfully")
    
    def downgrade(self, target_version: str):
        """Rollback migrations (like alembic downgrade)"""
        applied = self.get_applied_migrations()
        
        # Find migrations to rollback (in reverse order)
        to_rollback = []
        for version in reversed(applied):
            if version == target_version:
                break
            migration = next((m for m in self.migrations if m.version == version), None)
            if migration and migration.down:
                to_rollback.append(migration)
        
        if not to_rollback:
            print("✅ No migrations to rollback")
            return
        
        print(f"🔄 Rolling back {len(to_rollback)} migration(s)...")
        
        for migration in to_rollback:
            print(f"   Rolling back {migration.version}: {migration.name}")
            try:
                with SessionLocal() as session:
                    # Run the down migration
                    migration.down(session)
                    
                    # Remove from tracking
                    session.query(MigrationRecord).filter_by(version=migration.version).delete()
                    session.commit()
                    print(f"   ✅ Rolled back {migration.version}")
                    
            except Exception as e:
                print(f"   ❌ Failed to rollback {migration.version}: {e}")
                raise
        
        print("✅ Rollback completed successfully")
    
    def status(self):
        """Show migration status (like alembic current)"""
        applied = self.get_applied_migrations()
        pending = self.get_pending_migrations()
        
        print("📋 Migration Status:")
        print(f"   Applied: {len(applied)}")
        print(f"   Pending: {len(pending)}")
        print()
        
        if applied:
            print("✅ Applied migrations:")
            for version in applied:
                migration = next((m for m in self.migrations if m.version == version), None)
                name = migration.name if migration else "Unknown"
                print(f"   {version}: {name}")
        
        if pending:
            print("⏳ Pending migrations:")
            for migration in pending:
                print(f"   {migration.version}: {migration.name}")


# Global migration runner instance
migration_runner = MigrationRunner()


def create_migration(version: str, name: str):
    """Decorator to create a migration (like @alembic.op)"""
    def decorator(func):
        migration_runner.add_migration(version, name, func)
        return func
    return decorator


# Example usage:
def run_migrations():
    """Run all pending migrations - call this on startup"""
    migration_runner.migrate()


def rollback_to(version: str):
    """Rollback to a specific version"""
    migration_runner.downgrade(version)


def migration_status():
    """Show current migration status"""
    migration_runner.status()


if __name__ == "__main__":
    # CLI interface for migrations
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python migrations.py [migrate|rollback|status]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "migrate":
        target = sys.argv[2] if len(sys.argv) > 2 else None
        migration_runner.migrate(target)
    elif command == "rollback":
        if len(sys.argv) < 3:
            print("Usage: python migrations.py rollback <target_version>")
            sys.exit(1)
        migration_runner.downgrade(sys.argv[2])
    elif command == "status":
        migration_runner.status()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)