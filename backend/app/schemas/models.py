"""Pydantic v2 request/response schemas.

Validation ranges mirror the UCI dataset codebook exactly, so an out-of-range
value is rejected at the API boundary instead of silently producing a
meaningless prediction.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

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
    source: Literal["simulated", "self_reported", "assessment", "practice"] = "self_reported"


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


# --------------------------------------------------------------------------- #
# Question bank, resources, sample papers and practice
# --------------------------------------------------------------------------- #

Difficulty = Literal["Easy", "Medium", "Hard"]
QuestionType = Literal["MCQ", "Numerical", "Theory"]
ResourceType = Literal["Video", "Article", "Notes", "PDF", "Exercise"]


class QuestionOption(BaseModel):
    key: str = Field(..., min_length=1, max_length=4)
    text: str = Field(..., min_length=1, max_length=500)


class QuestionCreate(BaseModel):
    """A bank question. `concept` must be a knowledge-graph concept id
    (`differential_equations`), not a display label - the route validates it
    against CONCEPTS the same way the mastery endpoint does."""

    subject: str = Field(..., min_length=2, max_length=60)
    concept: str = Field(..., min_length=2, max_length=60)
    difficulty: Difficulty
    question_type: QuestionType
    question_text: str = Field(..., min_length=5, max_length=2000)
    options: list[QuestionOption] | None = None
    correct_answer: str = Field(..., min_length=1, max_length=500)
    explanation: str | None = Field(None, max_length=2000)
    marks: float = Field(1.0, gt=0, le=100)
    tolerance: float | None = Field(None, ge=0, description="Numerical answers only")
    source: str | None = Field(None, max_length=120)

    @field_validator("options")
    @classmethod
    def unique_keys(cls, v):
        if v and len({o.key.upper() for o in v}) != len(v):
            raise ValueError("option keys must be unique")
        return v

    @model_validator(mode="after")
    def check_type_consistency(self):
        if self.question_type == "MCQ":
            if not self.options or len(self.options) < 2:
                raise ValueError("MCQ questions need at least two options")
            keys = {o.key.strip().upper() for o in self.options}
            if self.correct_answer.strip().upper() not in keys:
                raise ValueError("correct_answer must match one of the option keys")
        else:
            if self.options:
                raise ValueError(f"{self.question_type} questions must not carry options")
        if self.question_type == "Numerical":
            try:
                float(self.correct_answer.replace(",", "."))
            except ValueError:
                raise ValueError("Numerical questions need a numeric correct_answer")
        return self


class QuestionUpdate(BaseModel):
    subject: str | None = Field(None, min_length=2, max_length=60)
    concept: str | None = Field(None, min_length=2, max_length=60)
    difficulty: Difficulty | None = None
    question_type: QuestionType | None = None
    question_text: str | None = Field(None, min_length=5, max_length=2000)
    options: list[QuestionOption] | None = None
    correct_answer: str | None = Field(None, min_length=1, max_length=500)
    explanation: str | None = Field(None, max_length=2000)
    marks: float | None = Field(None, gt=0, le=100)
    tolerance: float | None = Field(None, ge=0)
    source: str | None = Field(None, max_length=120)
    is_active: bool | None = None


class ResourceCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=160)
    subject: str = Field(..., min_length=2, max_length=60)
    concept: str = Field(..., min_length=2, max_length=60)
    resource_type: ResourceType
    difficulty: Difficulty = "Medium"
    description: str | None = Field(None, max_length=1000)
    url: str | None = Field(None, max_length=500)
    estimated_minutes: int = Field(20, gt=0, le=600)

    @field_validator("url")
    @classmethod
    def http_url(cls, v):
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        return v


class ResourceUpdate(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=160)
    subject: str | None = Field(None, min_length=2, max_length=60)
    concept: str | None = Field(None, min_length=2, max_length=60)
    resource_type: ResourceType | None = None
    difficulty: Difficulty | None = None
    description: str | None = Field(None, max_length=1000)
    url: str | None = Field(None, max_length=500)
    estimated_minutes: int | None = Field(None, gt=0, le=600)
    is_active: bool | None = None


class PracticeStartRequest(BaseModel):
    concept: str = Field(..., min_length=2, max_length=60)
    difficulty: Difficulty | None = None
    count: int = Field(5, ge=1, le=25)
    origin: Literal["manual", "recommended", "root_cause"] = "manual"


class SubmittedAnswer(BaseModel):
    question_id: int
    selected_answer: str | None = Field(None, max_length=1000)
    time_taken: float | None = Field(None, ge=0, le=7200)
    self_marked_correct: bool | None = Field(
        None, description="Theory questions only - the student marks their own answer"
    )


class PracticeSubmitRequest(BaseModel):
    session_id: int
    answers: list[SubmittedAnswer] = Field(..., min_length=1, max_length=50)
    elapsed_seconds: float | None = Field(None, ge=0)


# --------------------------------------------------------------------------- #
# Multi-subject academic records (multi-subject upgrade)
# --------------------------------------------------------------------------- #
class SubjectCreate(BaseModel):
    """Subjects are configuration, so a teacher can add one without a schema change."""

    subject_id: str = Field(..., min_length=2, max_length=32, pattern=r"^[a-z0-9_]+$")
    name: str = Field(..., min_length=2, max_length=80)
    code: str | None = Field(None, max_length=12)
    description: str | None = Field(None, max_length=400)
    semester: str | None = Field(None, max_length=40)
    credits: float | None = Field(None, ge=0, le=20)


class AssessmentCreate(BaseModel):
    subject_id: str = Field(..., min_length=2, max_length=32)
    assessment_type: str = Field(..., min_length=2, max_length=32)
    name: str = Field(..., min_length=1, max_length=60)
    assessment_order: int = Field(..., ge=1, le=50)
    max_marks: float = Field(100, gt=0, le=1000)
    weight: float = Field(1.0, ge=0, le=10)
    scheduled_on: str | None = Field(None, max_length=32)


class AssessmentResultEntry(BaseModel):
    student_id: str = Field(..., min_length=2, max_length=32)
    marks: float = Field(..., ge=0, le=1000)


class BulkResultRow(AssessmentResultEntry):
    assessment_id: int = Field(..., ge=1)


class BulkAssessmentResults(BaseModel):
    results: list[BulkResultRow] = Field(..., min_length=1, max_length=500)
