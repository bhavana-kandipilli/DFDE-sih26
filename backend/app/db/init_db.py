import logging
from backend.app.db.session import engine, Base, SessionLocal
from backend.app.db.models import User, ModelVersion
from backend.app.core.security import hash_password

logger = logging.getLogger("forensic_db")

def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Seed Default Users for all 5 Roles
    seed_users = [
        {
            "username": "officer1",
            "email": "officer1@taskforce.gov",
            "password": "fieldpass123",
            "role": "FIELD_OFFICER",
            "badge_number": "BADGE-4092",
            "department": "Narcotics Interdiction Taskforce"
        },
        {
            "username": "analyst1",
            "email": "analyst1@crimelab.gov",
            "password": "analystpass123",
            "role": "FORENSIC_ANALYST",
            "badge_number": "ANALYST-108",
            "department": "State Forensic Crime Laboratory"
        },
        {
            "username": "admin1",
            "email": "admin1@forensics.gov",
            "password": "adminpass123",
            "role": "ADMIN",
            "badge_number": "ADMIN-001",
            "department": "Forensic Systems Administration"
        },
        {
            "username": "auditor1",
            "email": "auditor1@justice.gov",
            "password": "auditorpass123",
            "role": "AUDITOR",
            "badge_number": "AUDIT-77",
            "department": "Office of the Inspector General"
        },
        {
            "username": "readonly1",
            "email": "readonly1@justice.gov",
            "password": "readonlypass123",
            "role": "READ_ONLY",
            "badge_number": "RO-99",
            "department": "Judicial Records Review"
        }
    ]

    for u_info in seed_users:
        existing = db.query(User).filter(User.username == u_info["username"]).first()
        if not existing:
            new_user = User(
                username=u_info["username"],
                email=u_info["email"],
                hashed_password=hash_password(u_info["password"]),
                role=u_info["role"],
                badge_number=u_info["badge_number"],
                department=u_info["department"],
                is_active=True
            )
            db.add(new_user)
            logger.info(f"Seeded user '{u_info['username']}' with role '{u_info['role']}'.")

    # Seed Active Model Version
    active_model = db.query(ModelVersion).filter(ModelVersion.version_tag == "v1.0.0-presumptive-idpad").first()
    if not active_model:
        model_ver = ModelVersion(
            version_tag="v1.0.0-presumptive-idpad",
            model_type="Logistic_Regression_Platt_Calibrated",
            file_path="ml/models/best_model_calibrated.joblib",
            accuracy=0.8596,
            f1_score=0.8974,
            is_active=True
        )
        db.add(model_ver)

    db.commit()
    db.close()
