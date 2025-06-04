import os
from typing import Optional
from sqlmodel import SQLModel, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

def get_database_url() -> str:
    """
    Get database URL from environment variables with fallback to SQLite.
    
    Environment variables:
    - DATABASE_URL: Full database URL (takes precedence)
    - DB_TYPE: 'sqlite' or 'postgresql' 
    - DB_HOST: Database host (for PostgreSQL)
    - DB_PORT: Database port (for PostgreSQL) 
    - DB_NAME: Database name
    - DB_USER: Database username (for PostgreSQL)
    - DB_PASSWORD: Database password (for PostgreSQL)
    """
    
    # Check for full DATABASE_URL first (commonly used in production/Heroku)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        # Handle postgres:// URLs (Heroku uses this, but SQLAlchemy needs postgresql://)
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        return database_url
    
    # Build URL from individual components
    db_type = os.getenv("DB_TYPE", "sqlite").lower()
    
    if db_type == "sqlite":
        db_name = os.getenv("DB_NAME", "test.db")
        return f"sqlite:///./{db_name}"
    
    elif db_type == "postgresql":
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME", "ai_ttrpg")
        db_user = os.getenv("DB_USER", "postgres")
        db_password = os.getenv("DB_PASSWORD", "")
        
        if db_password:
            return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        else:
            return f"postgresql://{db_user}@{db_host}:{db_port}/{db_name}"
    
    else:
        raise ValueError(f"Unsupported database type: {db_type}")


def create_database_engine() -> Engine:
    """
    Create database engine with appropriate configuration for the database type.
    """
    database_url = get_database_url()
    
    # Determine if we're using SQLite or PostgreSQL
    is_sqlite = database_url.startswith("sqlite:")
    is_postgresql = database_url.startswith("postgresql:")
    
    # Base engine arguments
    engine_args = {
        "echo": os.getenv("DB_ECHO", "false").lower() == "true",
    }
    
    if is_sqlite:
        # SQLite-specific configuration
        engine_args.update({
            # Use StaticPool for SQLite to handle threading
            "poolclass": StaticPool,
            "connect_args": {
                "check_same_thread": False,  # Allow SQLite to be used across threads
                "timeout": 20,  # Connection timeout in seconds
            },
        })
    
    elif is_postgresql:
        # PostgreSQL-specific configuration
        engine_args.update({
            "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
            "pool_pre_ping": True,  # Verify connections before use
            "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "3600")),  # Recycle connections after 1 hour
            "connect_args": {
                "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
                "command_timeout": int(os.getenv("DB_COMMAND_TIMEOUT", "30")),
            },
        })
    
    return create_engine(database_url, **engine_args)


def get_database_info() -> dict:
    """
    Get information about the current database configuration.
    Useful for debugging and health checks.
    """
    database_url = get_database_url()
    
    # Parse URL to extract info (without exposing passwords)
    info = {
        "database_url": database_url,
        "database_type": "sqlite" if database_url.startswith("sqlite:") else "postgresql",
        "echo_enabled": os.getenv("DB_ECHO", "false").lower() == "true",
    }
    
    if info["database_type"] == "postgresql":
        info.update({
            "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
            "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "3600")),
        })
    
    # Mask password in URL for security
    if "@" in database_url and "://" in database_url:
        scheme = database_url.split("://")[0]
        rest = database_url.split("://")[1]
        if "@" in rest:
            user_pass, host_db = rest.split("@", 1)
            if ":" in user_pass:
                user, _ = user_pass.split(":", 1)
                info["database_url"] = f"{scheme}://{user}:****@{host_db}"
    
    return info


# Create the global engine instance
DATABASE_URL = get_database_url()
engine = create_database_engine()


def create_db_and_tables():
    """
    Create database tables from SQLModel metadata.
    This is used for initial setup and development.
    In production, use Alembic migrations instead.
    """
    SQLModel.metadata.create_all(engine)


def get_engine() -> Engine:
    """
    Get the database engine instance.
    This is useful for dependency injection and testing.
    """
    return engine


def close_engine():
    """
    Close the database engine and all connections.
    Useful for cleanup in tests and application shutdown.
    """
    engine.dispose() 