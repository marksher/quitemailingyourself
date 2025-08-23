#!/usr/bin/env python3
"""
Migration management CLI - like alembic
"""

import sys
import os

# Add backend to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.migrations_registry import *  # Import to register migrations
from backend.migrations import migration_runner


def main():
    if len(sys.argv) < 2:
        print("Migration Management CLI")
        print()
        print("Usage: python manage_migrations.py <command> [args]")
        print()
        print("Commands:")
        print("  migrate [version]     - Run pending migrations (or up to specific version)")
        print("  rollback <version>    - Rollback to specific version")  
        print("  status               - Show migration status")
        print("  history              - Show migration history")
        print()
        print("Examples:")
        print("  python manage_migrations.py migrate")
        print("  python manage_migrations.py migrate 003") 
        print("  python manage_migrations.py rollback 002")
        print("  python manage_migrations.py status")
        sys.exit(1)

    command = sys.argv[1]

    if command == "migrate":
        target = sys.argv[2] if len(sys.argv) > 2 else None
        migration_runner.migrate(target)
        
    elif command == "rollback":
        if len(sys.argv) < 3:
            print("❌ Error: rollback command requires a target version")
            print("Usage: python manage_migrations.py rollback <target_version>")
            sys.exit(1)
        migration_runner.downgrade(sys.argv[2])
        
    elif command == "status":
        migration_runner.status()
        
    elif command == "history":
        print("📚 Available migrations:")
        for migration in migration_runner.migrations:
            applied = "✅" if migration.version in migration_runner.get_applied_migrations() else "⏳"
            rollback = "🔄" if migration.down else "❌"
            print(f"   {applied} {migration.version}: {migration.name} (rollback: {rollback})")
        
    else:
        print(f"❌ Unknown command: {command}")
        print("Run without arguments to see available commands")
        sys.exit(1)


if __name__ == "__main__":
    main()