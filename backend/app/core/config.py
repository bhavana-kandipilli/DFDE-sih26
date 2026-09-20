import os


def _is_serverless_runtime() -> bool:
    return bool(
        os.getenv("VERCEL")
        or os.getenv("AWS_LAMBDA_FUNCTION_NAME")
        or os.getenv("NOW_REGION")
        or os.getenv("FUNCTIONS_WORKER_RUNTIME")
    )


def _writable_temp_dir() -> str:
    return "/tmp/digital-field-drug-evidence-storage"


class Settings:
    PROJECT_NAME: str = "Digital Field Drug Evidence System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = ""  # Top-level or v1 compatible

    # Environment & Secrets (Never hardcode secrets in production)
    SECRET_KEY: str = os.getenv("SECRET_KEY", "forensic-jwt-secret-key-change-in-production-2026")
    HMAC_SECRET: str = os.getenv("HMAC_SECRET", "forensic-evidence-hmac-secret-key-32bytes")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))  # 8 hours

    # Database: use writable serverless-safe SQLite defaults; local dev retains repo-local defaults.
    if os.getenv("DATABASE_URL"):
        DATABASE_URL: str = os.getenv("DATABASE_URL")
    elif _is_serverless_runtime():
        DATABASE_URL = "sqlite:////tmp/digital_field_drug_evidence.db"
    else:
        DATABASE_URL = "sqlite:///./storage/evidence.db"

    # Object Storage Directory: always prefer a writable path in serverless runtimes.
    STORAGE_DIR = os.getenv("STORAGE_DIR") or (
        _writable_temp_dir() if _is_serverless_runtime() else os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "storage"))
    )
    try:
        os.makedirs(STORAGE_DIR, exist_ok=True)
    except OSError:
        STORAGE_DIR = _writable_temp_dir()
        os.makedirs(STORAGE_DIR, exist_ok=True)

    # Quality & Rate Limiting Controls
    MIN_LAPLACIAN_VAR: float = float(os.getenv("MIN_LAPLACIAN_VAR", "100.0"))
    MIN_EXPOSURE_VAL: float = float(os.getenv("MIN_EXPOSURE_VAL", "30.0"))
    MAX_EXPOSURE_VAL: float = float(os.getenv("MAX_EXPOSURE_VAL", "240.0"))
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))

    # Security & Upload Hardening
    MAX_UPLOAD_SIZE_BYTES: int = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(15 * 1024 * 1024)))  # 15 MB
    MAX_IMAGE_DIMENSION: int = int(os.getenv("MAX_IMAGE_DIMENSION", "8192"))  # 8192 px
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # CORS Origins (comma-separated string or list)
    CORS_ORIGINS: list = [
        origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",")
        if origin.strip()
    ]


settings = Settings()
