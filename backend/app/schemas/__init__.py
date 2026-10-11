from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class In(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("*", mode="before")
    @classmethod
    def empty_to_none(cls, v):
        return None if v == "" else v


# ---------- auth / users ----------

class LoginIn(In):
    username: str
    password: str


class RefreshIn(In):
    refresh_token: str


class ChangePasswordIn(In):
    old_password: str
    new_password: str = Field(min_length=8)


class UserIn(In):
    username: str = Field(min_length=3, max_length=100)
    full_name: str
    phone: str | None = None
    role_id: int
    unit_scope_id: int | None = None
    active: bool = True
    password: str | None = Field(default=None, min_length=8)


class RoleIn(In):
    name: str
    description: str | None = None


class RolePermissionsIn(In):
    permissions: list[str]  # ["soldiers.view", ...]


# ---------- geography ----------

class ProvinceIn(In):
    id: int
    name_kh: str
    name_en: str | None = None
    type: Literal["រាជធានី", "ខេត្ត"] = "ខេត្ត"
    active: bool = True


class DistrictIn(In):
    id: int
    province_id: int
    name_kh: str
    name_en: str | None = None
    type: Literal["ស្រុក", "ក្រុង", "ខណ្ឌ"] = "ស្រុក"
    active: bool = True


class CommuneIn(In):
    id: int
    district_id: int
    name_kh: str
    name_en: str | None = None
    type: Literal["ឃុំ", "សង្កាត់"] = "ឃុំ"
    active: bool = True


class VillageIn(In):
    id: int
    commune_id: int
    name_kh: str
    name_en: str | None = None
    active: bool = True


class CountryIn(In):
    name_kh: str
    name_en: str | None = None
    active: bool = True


# ---------- organisation / master ----------

class UnitIn(In):
    parent_id: int | None = None
    level: int = Field(ge=1, le=4)
    code: str | None = None
    name_kh: str
    name_en: str | None = None
    sort_order: int = 0
    active: bool = True


class RankClassIn(In):
    name_kh: str
    name_en: str | None = None
    sort_order: int = 0


class RankIn(In):
    rank_class_id: int
    name_kh: str
    name_en: str | None = None
    short_kh: str | None = None
    sort_order: int = 0
    min_years_to_next: int | None = Field(default=None, ge=0, le=50)
    active: bool = True


class NamedIn(In):
    name_kh: str
    name_en: str | None = None
    active: bool = True


class PositionIn(NamedIn):
    grade: int | None = None
    sort_order: int = 0


class DocumentTypeIn(NamedIn):
    direction: Literal["in", "out", "both"] = "both"


class LookupIn(NamedIn):
    category: str
    code: str | None = None
    sort_order: int = 0


# ---------- soldiers ----------

class EducationIn(In):
    kind: Literal["general", "specialty", "other"] = "general"
    education_level_id: int | None = None
    specialty_text: str | None = None
    institution: str | None = None
    country_id: int | None = None
    is_abroad: bool = False
    start_date: date | None = None
    end_date: date | None = None
    duration_text: str | None = None


class LanguageIn(In):
    language_id: int
    level: str | None = None


class ChildIn(In):
    name: str
    gender: Literal["M", "F"] | None = None
    date_of_birth: date | None = None


class SoldierIn(In):
    military_id: str = Field(min_length=1, max_length=50)
    name_kh: str = Field(min_length=1)
    name_latin: str | None = None
    gender: Literal["M", "F"]
    date_of_birth: date | None = None
    national_id: str | None = None
    phone: str | None = None
    blood_type_id: int | None = None
    birth_village_id: int | None = None
    birth_place_text: str | None = None
    current_village_id: int | None = None
    current_address_text: str | None = None
    current_rank_id: int | None = None
    rank_date: date | None = None
    current_position_id: int | None = None
    position_date: date | None = None
    current_unit_id: int | None = None
    unit_transfer_date: date | None = None
    from_unit_text: str | None = None
    enlistment_date: date | None = None
    status_id: int | None = None
    education_level_id: int | None = None
    specialty_id: int | None = None
    combat_veteran: bool = False
    combat_note: str | None = None
    marital_status_id: int | None = None
    spouse_name: str | None = None
    spouse_job_id: int | None = None
    children_count: int = Field(default=0, ge=0, le=50)
    father_name: str | None = None
    mother_name: str | None = None
    notes: str | None = None
    educations: list[EducationIn] = []
    languages: list[LanguageIn] = []
    children: list[ChildIn] = []


# ---------- documents ----------

class DocumentInIn(In):
    incoming_no: str
    subject: str
    doc_date: date
    received_date: date | None = None
    document_type_id: int | None = None
    from_unit: str | None = None
    status: str = "received"
    remarks: str | None = None


class DocumentOutIn(In):
    outgoing_no: str | None = None  # auto-generated when empty
    subject: str
    doc_date: date
    document_type_id: int | None = None
    unit_id: int | None = None
    recipient_name: str | None = None
    recipient_phone: str | None = None
    status: str = "sent"
    remarks: str | None = None


# ---------- decisions ----------

class DecisionItemIn(In):
    soldier_id: int
    new_rank_id: int | None = None
    new_position_id: int | None = None
    new_unit_id: int | None = None
    note: str | None = None


class DecisionIn(In):
    kind: Literal["appoint", "transfer", "promote"]
    decision_no: str
    decision_date: date
    effective_date: date
    issued_by: str | None = None
    outgoing_document_id: int | None = None
    notes: str | None = None
    items: list[DecisionItemIn] = Field(min_length=1)


# ---------- training & records ----------

class ParticipantIn(In):
    soldier_id: int
    result: str | None = None
    certificate_no: str | None = None


class TrainingCourseIn(In):
    name: str
    course_type: Literal["long", "short"]
    specialty_id: int | None = None
    institution: str | None = None
    country_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    notes: str | None = None
    participants: list[ParticipantIn] = []


class DisciplineIn(In):
    soldier_id: int
    discipline_type_id: int | None = None
    reason: str | None = None
    decision_no: str | None = None
    decision_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None


class AwardIn(In):
    soldier_id: int
    award_type_id: int | None = None
    reason: str | None = None
    decision_no: str | None = None
    decision_date: date | None = None


class RetirementIn(In):
    soldier_id: int
    type: Literal["pension", "category2"]
    decision_no: str | None = None
    decision_date: date | None = None
    effective_date: date
    pension_amount: float | None = None
    notes: str | None = None


class SeparationIn(In):
    soldier_id: int
    reason_id: int | None = None
    decision_no: str | None = None
    decision_date: date | None = None
    effective_date: date
    notes: str | None = None


class StrengthIn(In):
    soldier_id: int
    unit_id: int | None = None
    direction: Literal["in", "out"]
    reason: str
    movement_date: date
    note: str | None = None


class SettingsIn(BaseModel):
    values: dict[str, str | None]
