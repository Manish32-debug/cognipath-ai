"""Pydantic v2 request/response schemas.

Validation ranges mirror the UCI dataset codebook exactly, so an out-of-range
value is rejected at the API boundary instead of silently producing a
meaningless prediction.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Yes = Literal["yes", "no"]


class StudentFeatures(BaseModel):
    """Model input. G1, G2, studytime, failures and absences are the strong signals;
    the rest are optional and fall back to training medians/modes."""

    G1: float = Field(..., ge=0, le=20, description="First period grade (0-20)")
    G2: float = Field(..., ge=0, le=20, description="Second period grade (0-20)")
    studytime: int = Field(2, ge=1, le=4, description="1:<2h 2:2-5h 3:5-10h 4:>10h weekly")
    failures: int = Field(0, ge=0, le=4, description="Past class failures")
    absences: float = Field(0, ge=0, le=93)
    attendance_pct: float | None = Field(None, ge=0, le=100,
                                         description="Overrides the value derived from absences")
    health: int = Field(3, ge=1, le=5)
    freetime: int = Field(3, ge=1, le=5)
    goout: int = Field(3, ge=1, le=5)
    age: int = Field(17, ge=15, le=25)
    Medu: int = Field(2, ge=0, le=4)
    Fedu: int = Field(2, ge=0, le=4)
    traveltime: int = Field(1, ge=1, le=4)
    famrel: int = Field(4, ge=1, le=5)
    Dalc: int = Field(1, ge=1, le=5)
    Walc: int = Field(1, ge=1, le=5)
    sex: Literal["F", "M"] = "M"
    address: Literal["U", "R"] = "U"
    famsize: Literal["LE3", "GT3"] = "GT3"
    Pstatus: Literal["T", "A"] = "T"
    schoolsup: Yes = "no"
    famsup: Yes = "yes"
    paid: Yes = "no"
    activities: Yes = "yes"
    higher: Yes = "yes"
    internet: Yes = "yes"
    romantic: Yes = "no"


class PredictionResponse(BaseModel):
    predicted_gpa: float
    predicted_g3_equivalent: float
    pass_probability: float
    risk_tier: str
    risk_probabilities: dict[str, float]
    models_used: dict[str, str]
    interpretation: str


class Contribution(BaseModel):
    feature: str
    label: str
    shap_value: float
    direction: str
    student_value: float | str | None = None


class ExplanationResponse(BaseModel):
    task: str
    explained_class: str | None = None
    units: str
    base_value: float
    prediction: float
    explainer: str
    model: str
    top_contributions: list[Contribution]
    helping: list[Contribution]
    hurting: list[Contribution]
    explanation_note: str


class MasteryRecord(BaseModel):
    concept: str
    mastery: float = Field(..., ge=0, le=100)
    source: Literal["simulated", "self_reported", "assessment"] = "self_reported"


class MasteryUpdate(BaseModel):
    records: list[MasteryRecord] = Field(..., min_length=1)


class RootCauseRequest(BaseModel):
    mastery: dict[str, float]

    @field_validator("mastery")
    @classmethod
    def in_range(cls, v: dict[str, float]) -> dict[str, float]:
        for concept, score in v.items():
            if not 0 <= score <= 100:
                raise ValueError(f"mastery for '{concept}' must be between 0 and 100")
        return v


class StudentCreate(BaseModel):
    student_id: str = Field(..., min_length=2, max_length=32,
                            pattern=r"^[A-Za-z0-9_-]+$")
    display_name: str | None = Field(None, max_length=80)
    learning_style: str | None = Field(None, max_length=40)
    features: StudentFeatures
    mastery: list[MasteryRecord] | None = None


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=40)
    password: str = Field(..., min_length=6, max_length=128)


class RegisterRequest(LoginRequest):
    role: Literal["student", "teacher"] = "student"
    student_id: str | None = None
    full_name: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
    student_id: str | None = None


class ErrorResponse(BaseModel):
    detail: str
