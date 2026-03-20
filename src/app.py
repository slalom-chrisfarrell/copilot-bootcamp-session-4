"""
Slalom Capabilities Management System API

A FastAPI application that enables Slalom consultants to register their
capabilities and manage consulting expertise across the organization.
"""

from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import os
from pathlib import Path
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

app = FastAPI(title="Slalom Capabilities Management API",
              description="API for managing consulting capabilities and consultant expertise")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

PRACTICE_LEADS_FILE = current_dir / "practice_leads.json"
AUDIT_LOG_FILE = current_dir / "audit.log"
SESSION_TTL_HOURS = 8


class LoginRequest(BaseModel):
    username: str
    password: str


practice_leads = {}
sessions = {}


def log_audit_event(
    action: str,
    status: str,
    actor: str,
    capability_name: str = "",
    target_email: str = "",
    detail: str = "",
) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    entry = (
        f"{timestamp} action={action} status={status} actor={actor} "
        f"capability={capability_name} target={target_email} detail={detail}\n"
    )
    with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as audit_file:
        audit_file.write(entry)


def hash_password(password: str, salt: str, iterations: int = 390000) -> str:
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return f"pbkdf2_sha256${iterations}${salt}${password_hash}"


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iteration_str, salt, expected_hash = encoded_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False

        calculated = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iteration_str),
        ).hex()
        return hmac.compare_digest(calculated, expected_hash)
    except ValueError:
        return False


def load_practice_leads() -> dict:
    if PRACTICE_LEADS_FILE.exists():
        with open(PRACTICE_LEADS_FILE, "r", encoding="utf-8") as leads_file:
            return json.load(leads_file)

    bootstrap_password = os.getenv("PRACTICE_LEAD_BOOTSTRAP_PASSWORD", "ChangeMe123!")
    salt = secrets.token_hex(16)
    default_data = {
        "practice_leads": [
            {
                "username": "practice.lead",
                "password_hash": hash_password(bootstrap_password, salt),
                "role": "practice_lead",
                "practice_areas": ["Technology", "Strategy", "Operations"],
            }
        ]
    }

    with open(PRACTICE_LEADS_FILE, "w", encoding="utf-8") as leads_file:
        json.dump(default_data, leads_file, indent=2)

    log_audit_event(
        action="bootstrap_practice_lead",
        status="success",
        actor="system",
        detail="Created default practice lead credentials",
    )
    return default_data


def get_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return parts[1].strip()


def get_session(authorization: Optional[str]) -> Optional[dict]:
    token = get_bearer_token(authorization)
    if not token:
        return None

    session = sessions.get(token)
    if not session:
        return None

    if session["expires_at"] < datetime.now(timezone.utc):
        sessions.pop(token, None)
        return None

    return session


def require_practice_lead(authorization: Optional[str]) -> dict:
    session = get_session(authorization)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required")

    if session["role"] != "practice_lead":
        raise HTTPException(status_code=403, detail="Practice lead access required")

    return session

# In-memory capabilities database
capabilities = {
    "Cloud Architecture": {
        "description": "Design and implement scalable cloud solutions using AWS, Azure, and GCP",
        "practice_area": "Technology",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["AWS Solutions Architect", "Azure Architect Expert"],
        "industry_verticals": ["Healthcare", "Financial Services", "Retail"],
        "capacity": 40,  # hours per week available across team
        "consultants": ["alice.smith@slalom.com", "bob.johnson@slalom.com"]
    },
    "Data Analytics": {
        "description": "Advanced data analysis, visualization, and machine learning solutions",
        "practice_area": "Technology", 
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Tableau Desktop Specialist", "Power BI Expert", "Google Analytics"],
        "industry_verticals": ["Retail", "Healthcare", "Manufacturing"],
        "capacity": 35,
        "consultants": ["emma.davis@slalom.com", "sophia.wilson@slalom.com"]
    },
    "DevOps Engineering": {
        "description": "CI/CD pipeline design, infrastructure automation, and containerization",
        "practice_area": "Technology",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"], 
        "certifications": ["Docker Certified Associate", "Kubernetes Admin", "Jenkins Certified"],
        "industry_verticals": ["Technology", "Financial Services"],
        "capacity": 30,
        "consultants": ["john.brown@slalom.com", "olivia.taylor@slalom.com"]
    },
    "Digital Strategy": {
        "description": "Digital transformation planning and strategic technology roadmaps",
        "practice_area": "Strategy",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Digital Transformation Certificate", "Agile Certified Practitioner"],
        "industry_verticals": ["Healthcare", "Financial Services", "Government"],
        "capacity": 25,
        "consultants": ["liam.anderson@slalom.com", "noah.martinez@slalom.com"]
    },
    "Change Management": {
        "description": "Organizational change leadership and adoption strategies",
        "practice_area": "Operations",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Prosci Certified", "Lean Six Sigma Black Belt"],
        "industry_verticals": ["Healthcare", "Manufacturing", "Government"],
        "capacity": 20,
        "consultants": ["ava.garcia@slalom.com", "mia.rodriguez@slalom.com"]
    },
    "UX/UI Design": {
        "description": "User experience design and digital product innovation",
        "practice_area": "Technology",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Adobe Certified Expert", "Google UX Design Certificate"],
        "industry_verticals": ["Retail", "Healthcare", "Technology"],
        "capacity": 30,
        "consultants": ["amelia.lee@slalom.com", "harper.white@slalom.com"]
    },
    "Cybersecurity": {
        "description": "Information security strategy, risk assessment, and compliance",
        "practice_area": "Technology",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["CISSP", "CISM", "CompTIA Security+"],
        "industry_verticals": ["Financial Services", "Healthcare", "Government"],
        "capacity": 25,
        "consultants": ["ella.clark@slalom.com", "scarlett.lewis@slalom.com"]
    },
    "Business Intelligence": {
        "description": "Enterprise reporting, data warehousing, and business analytics",
        "practice_area": "Technology",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Microsoft BI Certification", "Qlik Sense Certified"],
        "industry_verticals": ["Retail", "Manufacturing", "Financial Services"],
        "capacity": 35,
        "consultants": ["james.walker@slalom.com", "benjamin.hall@slalom.com"]
    },
    "Agile Coaching": {
        "description": "Agile transformation and team coaching for scaled delivery",
        "practice_area": "Operations",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Certified Scrum Master", "SAFe Agilist", "ICAgile Certified"],
        "industry_verticals": ["Technology", "Financial Services", "Healthcare"],
        "capacity": 20,
        "consultants": ["charlotte.young@slalom.com", "henry.king@slalom.com"]
    }
}

practice_leads = load_practice_leads()


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/capabilities")
def get_capabilities():
    return capabilities


@app.post("/auth/login")
def login(payload: LoginRequest):
    lead_records = practice_leads.get("practice_leads", [])

    for lead in lead_records:
        if lead.get("username") == payload.username and verify_password(
            payload.password,
            lead.get("password_hash", ""),
        ):
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)
            sessions[token] = {
                "username": payload.username,
                "role": lead.get("role", "practice_lead"),
                "practice_areas": lead.get("practice_areas", []),
                "expires_at": expires_at,
            }

            log_audit_event(
                action="login",
                status="success",
                actor=payload.username,
            )

            return {
                "token": token,
                "role": sessions[token]["role"],
                "username": payload.username,
                "expires_at": expires_at.isoformat(),
            }

    log_audit_event(
        action="login",
        status="failure",
        actor=payload.username,
        detail="Invalid credentials",
    )
    raise HTTPException(status_code=401, detail="Invalid username or password")


@app.post("/auth/logout")
def logout(authorization: Optional[str] = Header(default=None)):
    token = get_bearer_token(authorization)
    session = get_session(authorization)

    if token:
        sessions.pop(token, None)

    if session:
        log_audit_event(
            action="logout",
            status="success",
            actor=session["username"],
        )

    return {"message": "Logged out"}


@app.get("/auth/me")
def get_current_user(authorization: Optional[str] = Header(default=None)):
    session = get_session(authorization)
    if not session:
        return {"authenticated": False}

    return {
        "authenticated": True,
        "username": session["username"],
        "role": session["role"],
        "practice_areas": session["practice_areas"],
        "expires_at": session["expires_at"].isoformat(),
    }


@app.post("/capabilities/{capability_name}/register")
def register_for_capability(
    capability_name: str,
    email: str,
    authorization: Optional[str] = Header(default=None),
):
    """Register a consultant for a capability"""
    # Validate capability exists
    if capability_name not in capabilities:
        raise HTTPException(status_code=404, detail="Capability not found")

    # Get the specific capability
    capability = capabilities[capability_name]

    # Validate consultant is not already registered
    if email in capability["consultants"]:
        actor = get_session(authorization)
        actor_name = actor["username"] if actor else email
        log_audit_event(
            action="register",
            status="failure",
            actor=actor_name,
            capability_name=capability_name,
            target_email=email,
            detail="Consultant already registered",
        )
        raise HTTPException(
            status_code=400,
            detail="Consultant is already registered for this capability"
        )

    # Add consultant
    capability["consultants"].append(email)

    actor = get_session(authorization)
    actor_name = actor["username"] if actor else email
    log_audit_event(
        action="register",
        status="success",
        actor=actor_name,
        capability_name=capability_name,
        target_email=email,
    )

    return {"message": f"Registered {email} for {capability_name}"}


@app.delete("/capabilities/{capability_name}/unregister")
def unregister_from_capability(
    capability_name: str,
    email: str,
    authorization: Optional[str] = Header(default=None),
):
    """Unregister a consultant from a capability"""
    session = require_practice_lead(authorization)

    # Validate capability exists
    if capability_name not in capabilities:
        log_audit_event(
            action="unregister",
            status="failure",
            actor=session["username"],
            capability_name=capability_name,
            target_email=email,
            detail="Capability not found",
        )
        raise HTTPException(status_code=404, detail="Capability not found")

    # Get the specific capability
    capability = capabilities[capability_name]

    # Validate consultant is registered
    if email not in capability["consultants"]:
        log_audit_event(
            action="unregister",
            status="failure",
            actor=session["username"],
            capability_name=capability_name,
            target_email=email,
            detail="Consultant was not registered",
        )
        raise HTTPException(
            status_code=400,
            detail="Consultant is not registered for this capability"
        )

    # Remove consultant
    capability["consultants"].remove(email)
    log_audit_event(
        action="unregister",
        status="success",
        actor=session["username"],
        capability_name=capability_name,
        target_email=email,
    )

    return {"message": f"Unregistered {email} from {capability_name}"}
