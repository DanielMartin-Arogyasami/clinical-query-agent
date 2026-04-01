"""
CDISC standard lookup tools. Uses only publicly available specs.
[FIX M5] Renamed validate_sdtm_variable_name → is_required_sdtm_variable.
"""
from __future__ import annotations
from src.models.clinical import SDTM_DOMAINS, VITAL_SIGN_RANGES, VitalSignRange


def lookup_sdtm_domain(domain_code: str) -> dict | None:
    return SDTM_DOMAINS.get(domain_code.upper())


def get_required_variables(domain_code: str) -> list[str]:
    domain = SDTM_DOMAINS.get(domain_code.upper())
    return domain["required_variables"] if domain else []


def lookup_vital_sign_range(test_code: str) -> VitalSignRange | None:
    return VITAL_SIGN_RANGES.get(test_code.upper())


def is_required_sdtm_variable(domain: str, variable: str) -> bool:
    """Check if a variable is in the required list for the given domain. [FIX M5]"""
    domain_info = SDTM_DOMAINS.get(domain.upper())
    if not domain_info:
        return False
    return variable.upper() in domain_info["required_variables"]


def get_controlled_terminology(codelist: str) -> list[str]:
    from src.models.clinical import SEX_TERMS, RACE_TERMS, ETHNIC_TERMS, SEVERITY_TERMS
    mapping = {
        "SEX": list(SEX_TERMS.values()),
        "RACE": RACE_TERMS,
        "ETHNIC": ETHNIC_TERMS,
        "SEVERITY": SEVERITY_TERMS,
    }
    return mapping.get(codelist.upper(), [])
