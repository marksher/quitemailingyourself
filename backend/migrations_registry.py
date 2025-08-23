"""
Migration registry - define your migrations here
"""

from sqlalchemy import text
from backend.migrations import create_migration


@create_migration("001", "initial_schema")
def migration_001_initial_schema(session):
    """Initial schema creation - this will be automatically handled by SQLAlchemy"""
    # Since we use Base.metadata.create_all(), this migration is mostly a placeholder
    # for tracking that the initial schema has been "migrated"
    pass


@create_migration("002", "add_reading_time_feature") 
def migration_002_add_reading_time_feature(session):
    """Migration for reading time feature - already implemented in code"""
    # This is a placeholder migration to track the reading time feature
    # The actual changes are already in the AI enrichment code
    pass


# Example of a real migration you might add in the future:
@create_migration("003", "add_user_preferences_table")
def migration_003_add_user_preferences(session):
    """Add user preferences table"""
    # Example of how you'd add a new table
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            theme VARCHAR(32) DEFAULT 'light',
            items_per_page INTEGER DEFAULT 20,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """))


# Example of a reversible migration:
@create_migration("004", "add_link_favorite_flag")
def migration_004_add_favorite_flag(session):
    """Add favorite flag to links table"""
    session.execute(text("""
        ALTER TABLE links ADD COLUMN is_favorite BOOLEAN DEFAULT FALSE
    """))


# You can also add a down migration for rollbacks:
def migration_004_down(session):
    """Rollback favorite flag addition"""
    session.execute(text("""
        ALTER TABLE links DROP COLUMN is_favorite
    """))

# Register the down migration
from backend.migrations import migration_runner
migration_runner.migrations[-1].down = migration_004_down