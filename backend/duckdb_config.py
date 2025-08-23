import os
import boto3
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from typing import Generator

# S3 Configuration
S3_BUCKET = "quitemailingmyself"
S3_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# DuckDB Configuration
DUCKDB_S3_PATH = f"s3://{S3_BUCKET}/data/app.duckdb"

def get_duckdb_engine():
    """Create DuckDB engine with S3 configuration using IAM role."""
    
    # Create S3-backed DuckDB (uses EC2 IAM role automatically)
    engine = create_engine(
        "duckdb:///",  # In-memory DuckDB that can access S3
        echo=False,
        future=True
    )
    
    # Configure S3 settings - no credentials needed with IAM role
    with engine.connect() as conn:
        conn.execute(text(f"SET s3_region='{S3_REGION}';"))
        # DuckDB will automatically use EC2 instance's IAM role
        conn.execute(text("SET s3_use_ssl=true;"))
        
        # Install and load required extensions
        conn.execute(text("INSTALL httpfs;"))
        conn.execute(text("LOAD httpfs;"))
        
        # Create or attach S3 database
        conn.execute(text(f"ATTACH '{DUCKDB_S3_PATH}' AS main_db;"))
        
    print(f"✅ DuckDB connected to S3: {DUCKDB_S3_PATH} (using IAM role)")
    return engine

def init_s3_bucket():
    """Initialize S3 bucket if it doesn't exist (uses IAM role)"""
    try:
        # Uses EC2 instance's IAM role automatically
        s3_client = boto3.client('s3', region_name=S3_REGION)
        
        # Check if bucket exists
        try:
            s3_client.head_bucket(Bucket=S3_BUCKET)
            print(f"✅ S3 bucket exists: {S3_BUCKET}")
        except:
            # Create bucket
            if S3_REGION == 'us-east-1':
                s3_client.create_bucket(Bucket=S3_BUCKET)
            else:
                s3_client.create_bucket(
                    Bucket=S3_BUCKET,
                    CreateBucketConfiguration={'LocationConstraint': S3_REGION}
                )
            print(f"✅ Created S3 bucket: {S3_BUCKET}")
            
    except Exception as e:
        error_msg = f"S3 connection failed: {str(e)}"
        print(f"❌ {error_msg}")
        print("   Make sure your EC2 instance has an IAM role with S3 permissions")
        print("   Check that AWS services are accessible")
        raise RuntimeError(f"Database unavailable - {error_msg}") from e

# Create engine and session factory
engine = get_duckdb_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def get_session() -> Generator:
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()