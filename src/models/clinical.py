"""
Clinical domain models, CDISC constants, and reference ranges.
Uses ONLY publicly available CDISC standards and common clinical references.
"""
from __future__ import annotations
from dataclasses import dataclass

SDTM_DOMAINS: dict[str, dict] = {
    "DM": {
        "label": "Demographics",
        "class": "Special Purpose",
        "key_variables": ["STUDYID", "USUBJID"],
        "required_variables": [
            "STUDYID", "DOMAIN", "USUBJID", "SUBJID", "RFSTDTC", "RFENDTC",
            "SITEID", "BRTHDTC", "AGE", "AGEU", "SEX", "RACE", "ETHNIC",
            "ARMCD", "ARM", "COUNTRY",
        ],
    },
    "VS": {
        "label": "Vital Signs",
        "class": "Findings",
        "key_variables": ["STUDYID", "USUBJID", "VSTESTCD", "VISITNUM"],
        "required_variables": [
            "STUDYID", "DOMAIN", "USUBJID", "VSSEQ", "VSTESTCD", "VSTEST",
            "VSORRES", "VSORRESU", "VSSTRESC", "VSSTRESN", "VSSTRESU",
            "VISITNUM", "VISIT", "VSDTC",
        ],
        # [FIX L1] True input-required fields (not result fields like VSSTRESN)
        "input_required_variables": [
            "STUDYID", "DOMAIN", "USUBJID", "VSTESTCD", "VSTEST",
            "VISITNUM", "VISIT", "VSDTC",
        ],
    },
    "AE": {
        "label": "Adverse Events",
        "class": "Events",
        "key_variables": ["STUDYID", "USUBJID", "AESEQ"],
        "required_variables": [
            "STUDYID", "DOMAIN", "USUBJID", "AESEQ", "AETERM", "AEDECOD",
            "AESTDTC", "AEENDTC", "AESEV", "AESER", "AEREL",
        ],
    },
    "LB": {
        "label": "Laboratory Test Results",
        "class": "Findings",
        "key_variables": ["STUDYID", "USUBJID", "LBTESTCD", "VISITNUM"],
        "required_variables": [
            "STUDYID", "DOMAIN", "USUBJID", "LBSEQ", "LBTESTCD", "LBTEST",
            "LBORRES", "LBORRESU", "LBSTRESC", "LBSTRESN", "LBSTRESU",
            "LBNRIND", "VISITNUM", "VISIT", "LBDTC",
        ],
    },
    "CM": {
        "label": "Concomitant Medications",
        "class": "Interventions",
        "key_variables": ["STUDYID", "USUBJID", "CMSEQ"],
        "required_variables": [
            "STUDYID", "DOMAIN", "USUBJID", "CMSEQ", "CMTRT", "CMDECOD",
            "CMSTDTC", "CMENDTC", "CMDOSE", "CMDOSU", "CMROUTE",
        ],
    },
    "MH": {
        "label": "Medical History",
        "class": "Events",
        "key_variables": ["STUDYID", "USUBJID", "MHSEQ"],
        "required_variables": [
            "STUDYID", "DOMAIN", "USUBJID", "MHSEQ", "MHTERM", "MHDECOD",
            "MHSTDTC", "MHENDTC", "MHCAT",
        ],
    },
}


@dataclass
class VitalSignRange:
    test_code: str
    test_name: str
    unit: str
    normal_low: float
    normal_high: float
    critical_low: float
    critical_high: float


VITAL_SIGN_RANGES: dict[str, VitalSignRange] = {
    "SYSBP": VitalSignRange("SYSBP", "Systolic Blood Pressure", "mmHg", 90, 140, 60, 200),
    "DIABP": VitalSignRange("DIABP", "Diastolic Blood Pressure", "mmHg", 60, 90, 40, 130),
    "PULSE": VitalSignRange("PULSE", "Pulse Rate", "beats/min", 60, 100, 40, 150),
    "TEMP": VitalSignRange("TEMP", "Temperature", "C", 36.1, 37.2, 35.0, 39.5),
    "RESP": VitalSignRange("RESP", "Respiratory Rate", "breaths/min", 12, 20, 8, 30),
    "WEIGHT": VitalSignRange("WEIGHT", "Weight", "kg", 40, 150, 25, 250),
    "HEIGHT": VitalSignRange("HEIGHT", "Height", "cm", 140, 200, 100, 230),
    "BMI": VitalSignRange("BMI", "BMI", "kg/m2", 18.5, 30.0, 12.0, 60.0),
}

SEX_TERMS = {"M": "MALE", "F": "FEMALE", "U": "UNKNOWN"}
RACE_TERMS = [
    "WHITE", "BLACK OR AFRICAN AMERICAN", "ASIAN",
    "AMERICAN INDIAN OR ALASKA NATIVE",
    "NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER",
    "MULTIPLE", "NOT REPORTED", "UNKNOWN",
]
ETHNIC_TERMS = ["HISPANIC OR LATINO", "NOT HISPANIC OR LATINO", "NOT REPORTED", "UNKNOWN"]
SEVERITY_TERMS = ["MILD", "MODERATE", "SEVERE"]


@dataclass
class EditCheckTemplate:
    check_type: str
    description: str
    condition_template: str
    query_template: str


STANDARD_EDIT_CHECKS: list[EditCheckTemplate] = [
    EditCheckTemplate(
        "range", "Value outside expected range",
        "not ({low} <= value <= {high})",
        "The value of {field} ({value} {unit}) for Subject {subject} at Visit {visit} "
        "is outside the expected range of {low}-{high} {unit}. Please verify.",
    ),
    EditCheckTemplate(
        "presence", "Required field is missing",
        "value is None or value == ''",
        "The required field {field} is missing for Subject {subject} at Visit {visit}. "
        "Please provide the value.",
    ),
    EditCheckTemplate(
        "temporal", "Date before informed consent",
        "date < informed_consent_date",
        "The date for {field} ({value}) for Subject {subject} is before the informed "
        "consent date ({consent_date}). Please verify.",
    ),
    EditCheckTemplate(
        "cross_field", "Diastolic >= Systolic BP",
        "diabp >= sysbp",
        "Diastolic BP ({diabp} mmHg) >= Systolic BP ({sysbp} mmHg) for Subject "
        "{subject} at Visit {visit}. Please verify.",
    ),
    EditCheckTemplate(
        "consistency", "AE end date before start date",
        "end_date < start_date",
        "End date ({end_date}) for AE '{ae_term}' is before start date ({start_date}) "
        "for Subject {subject}. Please verify.",
    ),
]
