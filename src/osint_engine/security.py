from __future__ import annotations


def mask_email(value: str) -> str:
    if "@" not in value:
        return "***"
    local, domain = value.split("@", 1)
    local_masked = (local[:1] + "***") if local else "***"
    return f"{local_masked}@{domain}"


def mask_phone(value: str) -> str:
    if len(value) <= 4:
        return "***"
    return f"***{value[-4:]}"


def safe_seed_summary(person_name: str, username: str, email: str, phone: str) -> str:
    parts = []
    if person_name:
        parts.append("nombre capturado")
    if username:
        parts.append(f"usuario @{username}")
    if email:
        parts.append(f"correo {mask_email(email)}")
    if phone:
        parts.append(f"teléfono {mask_phone(phone)}")
    return ", ".join(parts) or "sin identificadores"
