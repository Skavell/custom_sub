import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-for-testing-purposes-1234")
os.environ.setdefault("SETTINGS_ENCRYPTION_KEY", "test-encryption-key-32-bytes-ok!")
