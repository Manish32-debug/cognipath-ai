"""Tests for the multi-subject, multi-assessment upgrade.

Covers: the normalized academic schema, trend detection, subject performance and
risk, early warnings, subject-aware knowledge graphs and practice, the ML
adapter, teacher analytics, database compatibility and the new API surface.

Runs against the same throwaway database as the rest of the suite (conftest
redirects COGNIPATH_DB), seeded with subjects, assessments and results.
"""

from __future__ import annotations

import pytest

from app.database import academics_db, db
from app.database.seed_academics import (
    DEFAULT_SCHEDULE,
    base_ability,
    generate_series,
    seed_results,
)
from app.database.seed_multisubject import seed_multisubject
from app.graph.knowledge_graph import (
    CONCEPTS,
    CONCEPT_SUBJECT,
    SUBJECTS,
    concepts_for_subject,
    external_prerequisites,
    get_graph,
    subject_graph,
    subject_graph_payload,
    subject_of,
)
from app.ml import assessment_features
from app.practice import selector
from app.recommendations import context as context_rules
from app.services import academics


@pytest.fixture(scope="module", autouse=True)
def academic_data(seeded_db):
    seed_multisubject()
    seed_results()
    yield


# --------------------------------------------------------------------------- #
# schema and database compatibility
# --------------------------------------------------------------------------- #
def test_original_tables_survive_the_upgrade():
    """The pre-upgrade tables must still exist with their data intact."""
    with db.get_conn() as conn:
        names = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    for table in ("users", "students", "concept_mastery", "predictions",
                  "questions", "resources", "practice_attempts"):
        assert table in names, table
    assert db.list_students(), "existing student rows must be readable"
    assert db.get_user("teacher") is not None, "existing demo accounts must survive"


def test_new_tables_are_created():
    with db.get_conn() as conn:
        names = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    for table in ("subjects", "assessment_types", "assessments",
                  "student_assessment_results"):
        assert table in names, table


def test_init_db_is_idempotent():
    """Re-running initialisation must not disturb existing rows - this is what
    makes the Render deploy safe without a manual migration."""
    before = academics_db.result_counts()
    db.init_db()
    db.init_db()
    assert academics_db.result_counts() == before


def test_percentage_is_derived_from_max_marks():
    """A 50-mark CAT and a 100-mark final must be comparable."""
    subject = academics_db.list_assessments("mathematics")
    cat = next(a for a in subject if a["max_marks"] == 50)
    result = academics_db.record_result("DEMO001", cat["assessment_id"], 40, source="entered")
    assert result["percentage"] == pytest.approx(80.0)


def test_marks_beyond_max_are_rejected():
    cat = academics_db.list_assessments("mathematics")[0]
    with pytest.raises(ValueError):
        academics_db.record_result("DEMO001", cat["assessment_id"],
                                   cat["max_marks"] + 1, source="entered")


def test_schedule_has_at_least_five_assessments_per_subject():
    for subject_id in SUBJECTS:
        assessments = academics_db.list_assessments(subject_id)
        assert len(assessments) >= 5, subject_id
        orders = [a["assessment_order"] for a in assessments]
        assert orders == sorted(orders)


def test_final_exam_is_not_recorded():
    """The predicted outcome must not be present as an input."""
    rows = academics_db.student_results("DEMO001", "mathematics")
    assert rows, "student should have a mathematics history"
    assert all(r["assessment_type"] != "final" for r in rows)


def test_simulated_results_are_labelled():
    rows = academics_db.student_results("DEMO002")
    assert rows
    assert all(r["source"] in {"simulated", "entered"} for r in rows)
    assert any(r["source"] == "simulated" for r in rows), \
        "generated demo data must be labelled, never passed off as real"


# --------------------------------------------------------------------------- #
# seeding determinism
# --------------------------------------------------------------------------- #
def test_generation_is_deterministic_per_student_and_subject():
    features = db.get_student("DEMO003")["features"]
    a, shape_a = generate_series("DEMO003", "dsp", features)
    b, shape_b = generate_series("DEMO003", "dsp", features)
    assert a == b and shape_a == shape_b


def test_generation_is_anchored_to_the_real_record():
    """A student who was weak in the source dataset must be weak here too."""
    weak = base_ability({"G1": 5, "G2": 5, "failures": 2})
    strong = base_ability({"G1": 18, "G2": 18, "failures": 0})
    assert strong > weak + 30


def test_students_differ_from_each_other():
    f1 = db.get_student("DEMO001")["features"]
    f2 = db.get_student("DEMO002")["features"]
    s1, _ = generate_series("DEMO001", "vlsi", f1)
    s2, _ = generate_series("DEMO002", "vlsi", f2)
    assert s1 != s2


# --------------------------------------------------------------------------- #
# trend detection
# --------------------------------------------------------------------------- #
def test_declining_series_is_detected():
    result = academics.classify_trend([72, 69, 64, 61, 58])
    assert result["trend"] in ("Declining", "Strongly declining")
    assert result["slope"] < 0
    assert "declin" in result["description"].lower()


def test_improving_series_is_detected():
    result = academics.classify_trend([54, 59, 63, 69, 74])
    assert result["trend"] in ("Improving", "Strongly improving")
    assert result["slope"] > 0
    assert "improv" in result["description"].lower()


def test_stable_series_is_detected():
    result = academics.classify_trend([70, 71, 69, 70, 71])
    assert result["trend"] == "Stable"
    assert abs(result["slope"]) < academics.SLOPE_STABLE


def test_volatile_series_is_detected():
    result = academics.classify_trend([80, 45, 78, 44, 79, 46])
    assert result["trend"] == "Volatile"
    assert result["volatility"] >= academics.VOLATILITY_HIGH


def test_trend_needs_enough_points():
    assert academics.classify_trend([70, 60])["trend"] == "Insufficient data"
    assert academics.classify_trend([])["trend"] == "No data"


def test_slope_matches_a_known_least_squares_fit():
    """A perfectly linear series must return exactly its slope."""
    assert academics._slope([10, 20, 30, 40]) == pytest.approx(10.0)
    assert academics._slope([40, 30, 20, 10]) == pytest.approx(-10.0)


def test_trend_thresholds_are_reported():
    result = academics.classify_trend([60, 62, 64, 66])
    assert result["thresholds"]["stable_slope"] == academics.SLOPE_STABLE


# --------------------------------------------------------------------------- #
# subject performance and risk
# --------------------------------------------------------------------------- #
def test_subject_performance_covers_every_seeded_subject():
    performance = academics.subject_performance("DEMO001")
    assert len(performance) == len(SUBJECTS)
    for subject in performance:
        assert subject["summary"]["n_assessments"] >= 5
        assert subject["trend"]["trend"]
        assert subject["risk"]["risk"] in {"Low", "Medium", "High"}


def test_subject_risk_is_higher_for_a_failing_declining_subject():
    falling = academics.subject_risk(
        academics.summarise_series([{"percentage": p} for p in [60, 55, 48, 42, 38]]),
        academics.classify_trend([60, 55, 48, 42, 38]),
    )
    steady = academics.subject_risk(
        academics.summarise_series([{"percentage": p} for p in [78, 80, 79, 81, 80]]),
        academics.classify_trend([78, 80, 79, 81, 80]),
    )
    assert falling["risk"] == "High"
    assert steady["risk"] == "Low"
    assert falling["score"] > steady["score"]


def test_subject_risk_states_its_method_and_weights():
    risk = academics.subject_risk(
        academics.summarise_series([{"percentage": p} for p in [55, 52, 50]]),
        academics.classify_trend([55, 52, 50]),
    )
    assert "rule-based" in risk["method"]
    assert set(risk["weights"]) == {"level", "trend", "volatility"}


def test_academic_overview_shape():
    overview = academics.academic_overview("DEMO001")
    assert overview["subjects"]
    row = overview["subjects"][0]
    for key in ("subject_id", "subject_name", "current", "trend", "direction", "risk"):
        assert key in row
    assert overview["overall"]["subjects_tracked"] == len(SUBJECTS)


def test_overview_is_empty_for_a_student_without_results():
    db.upsert_student("NOASSESS", {"G1": 10, "G2": 10, "studytime": 2, "failures": 0,
                                   "absences": 4, "attendance_pct": 93},
                      display_name="No Assessments")
    overview = academics.academic_overview("NOASSESS")
    assert overview["subjects"] == []
    assert overview["message"]


# --------------------------------------------------------------------------- #
# early warning
# --------------------------------------------------------------------------- #
def test_early_warning_fires_on_a_declining_series():
    """The brief's worked example: 74 -> 69 -> 63 -> 58 must raise a warning."""
    # Overwrite the whole recorded series, not a prefix: the recent-average window
    # looks at the LAST three assessments, so leaving later simulated marks in
    # place would test a different series than the one intended.
    subject = [a for a in academics_db.list_assessments("networks")
               if a["assessment_type"] != "final"]
    for assessment, percentage in zip(subject, [74, 71, 69, 63, 58, 54]):
        academics_db.record_result("DEMO001", assessment["assessment_id"],
                                   percentage / 100 * assessment["max_marks"], source="entered")
    warnings = academics.early_warnings("DEMO001")
    networks = [w for w in warnings["warnings"] if w["subject_id"] == "networks"]
    assert networks, "a declining subject below the concern level must warn"
    triggers = {t["trigger"] for t in networks[0]["triggers"]}
    assert "declining_trend" in triggers or "low_performance" in triggers


def test_early_warning_explains_why():
    warnings = academics.early_warnings("DEMO001")
    for warning in warnings["warnings"]:
        assert warning["why_at_risk"]
        assert warning["series"], "the evidence series must be attached"
        assert warning["severity"] in {"high", "medium", "low"}


def test_early_warning_triggers_are_documented():
    warnings = academics.early_warnings("DEMO001")
    assert set(warnings["triggers_documented"]) >= {
        "declining_trend", "low_performance", "drop_from_peak"}


def test_no_warning_for_a_strong_student():
    subject_ids = [a["assessment_id"] for a in academics_db.list_assessments("dbms")[:5]]
    db.upsert_student("STRONG1", {"G1": 18, "G2": 19, "studytime": 4, "failures": 0,
                                  "absences": 0, "attendance_pct": 100},
                      display_name="Strong Student")
    for assessment_id, percentage in zip(subject_ids, [88, 90, 89, 92, 91]):
        assessment = academics_db.get_assessment(assessment_id)
        academics_db.record_result("STRONG1", assessment_id,
                                   percentage / 100 * assessment["max_marks"], source="entered")
    warnings = academics.early_warnings("STRONG1")
    assert [w for w in warnings["warnings"] if w["subject_id"] == "dbms"] == []


# --------------------------------------------------------------------------- #
# subject-aware knowledge graph
# --------------------------------------------------------------------------- #
def test_every_concept_belongs_to_a_subject():
    for concept in CONCEPTS:
        assert subject_of(concept) in SUBJECTS, concept


def test_pre_upgrade_concepts_stayed_in_mathematics():
    """Stored mastery rows must not change meaning."""
    for concept in ("limits", "differentiation", "integration", "differential_equations"):
        assert CONCEPT_SUBJECT[concept] == "mathematics"


def test_every_subject_has_concepts_and_a_dag():
    import networkx as nx

    for subject_id in SUBJECTS:
        graph = subject_graph(subject_id)
        assert graph.number_of_nodes() >= 5, subject_id
        assert nx.is_directed_acyclic_graph(graph)


def test_subject_graph_is_an_induced_view_of_the_full_graph():
    full = get_graph()
    for subject_id in SUBJECTS:
        graph = subject_graph(subject_id)
        assert set(graph.nodes) <= set(full.nodes)
        for u, v in graph.edges:
            assert full.has_edge(u, v)


def test_cross_subject_prerequisites_are_surfaced():
    """DSP depends on Mathematics; that edge must be visible, not hidden."""
    external = external_prerequisites("dsp")
    assert external
    assert any(e["source_subject"] == "mathematics" for e in external)


def test_subject_graph_payload_shape():
    payload = subject_graph_payload("dbms")
    assert payload["subject"] == "dbms"
    assert payload["nodes"] and payload["edges"]
    assert all("unit" in n for n in payload["nodes"])


# --------------------------------------------------------------------------- #
# ML adapter
# --------------------------------------------------------------------------- #
def test_series_compresses_into_the_trained_feature_space():
    derived = assessment_features.series_to_grade_features([50, 55, 60, 65, 70, 75])
    assert 0 <= derived["G1"] <= 20 and 0 <= derived["G2"] <= 20
    assert derived["G2"] > derived["G1"], "an improving series must raise the recent feature"
    assert derived["grade_trend"] > 0


def test_declining_series_produces_a_negative_trend_feature():
    derived = assessment_features.series_to_grade_features([80, 74, 68, 60, 55, 50])
    assert derived["grade_trend"] < 0


def test_empty_series_returns_none_rather_than_inventing_numbers():
    assert assessment_features.series_to_grade_features([]) is None


def test_features_from_assessments_preserves_behavioural_columns():
    base = {"G1": 10, "G2": 10, "studytime": 3, "absences": 4, "failures": 1,
            "attendance_pct": 93, "grade_trend": 0}
    merged = assessment_features.features_from_assessments(base, [40, 45, 50])
    assert merged["studytime"] == 3 and merged["failures"] == 1
    assert merged["G2"] != base["G2"], "prior-performance slots must be re-derived"


def test_prediction_moves_when_a_new_result_is_recorded():
    """Longitudinal by construction: the prediction must respond to new marks."""
    student = db.get_student("DEMO010")
    before = assessment_features.overall_prediction("DEMO010", student["features"])

    for assessment in academics_db.list_assessments("mathematics")[:5]:
        academics_db.record_result("DEMO010", assessment["assessment_id"],
                                   0.15 * assessment["max_marks"], source="entered")

    after = assessment_features.overall_prediction("DEMO010", student["features"])
    assert after["prediction"]["predicted_gpa"] < before["prediction"]["predicted_gpa"]
    assert after["source"] == "multi_subject_assessments"


def test_provenance_separates_ml_from_rules():
    provenance = assessment_features.feature_provenance()
    assert any("SHAP" in item for item in provenance["ml"])
    assert any("Trend" in item for item in provenance["rule_based"])
    assert any("prerequisite" in item.lower() for item in provenance["graph_based"])


# --------------------------------------------------------------------------- #
# subject-aware practice and context advice
# --------------------------------------------------------------------------- #
def test_practice_can_be_filtered_to_one_subject():
    mastery = {c: 40.0 for c in CONCEPTS}
    from app.graph import root_cause

    roots = root_cause.analyse(mastery)
    plan = selector.recommended_practice(mastery, roots, "High", subject="vlsi")
    assert plan["items"]
    assert all(item["subject"] == "vlsi" for item in plan["items"])


def test_practice_items_carry_subject_and_unit():
    mastery = {c: 45.0 for c in CONCEPTS}
    from app.graph import root_cause

    plan = selector.recommended_practice(mastery, root_cause.analyse(mastery), "Medium")
    assert all("subject" in item and "unit" in item for item in plan["items"])


def test_question_bank_covers_every_subject():
    from app.database import practice_db

    counts = practice_db.question_counts_by_concept()
    covered_subjects = {subject_of(c) for c in counts}
    assert covered_subjects == set(SUBJECTS), \
        "every subject needs questions or its practice loop is dead"


def test_context_advice_differs_by_situation():
    attentive = context_rules.advise({"attendance_pct": 95, "recent_average": 52})
    absent = context_rules.advise({"attendance_pct": 55, "trend": "Declining",
                                   "recent_average": 52})
    exam_weak = context_rules.advise({"average_mastery": 78, "recent_average": 55})

    assert "revision" in attentive[0]["strategy"].lower()
    assert "recovery" in absent[0]["strategy"].lower()
    assert "mock" in exam_weak[0]["strategy"].lower()


def test_every_advice_item_states_its_rule_and_reason():
    for advice in context_rules.advise({"attendance_pct": 90, "recent_average": 50}):
        assert advice["rule"] and advice["why"] and advice["actions"]


def test_advice_falls_back_rather_than_returning_nothing():
    advice = context_rules.advise({})
    assert advice and advice[0]["strategy"] == "Maintain"


# --------------------------------------------------------------------------- #
# teacher analytics
# --------------------------------------------------------------------------- #
def test_cohort_analytics_reports_subjects_and_movers():
    data = academics.cohort_subject_analytics()
    assert data["students_tracked"] > 0
    assert len(data["subjects"]) == len(SUBJECTS)
    for subject in data["subjects"]:
        assert subject["class_average"] is not None
        assert sum(subject["risk_distribution"].values()) > 0
    assert data["assessment_trends"]


def test_declining_and_improving_lists_are_sorted_by_slope():
    data = academics.cohort_subject_analytics()
    declining = [row["slope"] for row in data["declining_students"]]
    improving = [row["slope"] for row in data["improving_students"]]
    assert declining == sorted(declining)
    assert improving == sorted(improving, reverse=True)
    assert all(s < 0 for s in declining)


# --------------------------------------------------------------------------- #
# API surface
# --------------------------------------------------------------------------- #
def test_subjects_endpoint_returns_the_unit_tree(client):
    body = client.get("/api/subjects").json()
    assert body["count"] == len(SUBJECTS)
    subject = body["subjects"][0]
    assert subject["units"] and subject["units"][0]["concepts"]


def test_subject_knowledge_graph_endpoint(client):
    body = client.get("/api/subjects/dsp/knowledge-graph").json()
    assert body["stats"]["n_nodes"] == len(concepts_for_subject("dsp"))
    assert body["external_prerequisites"]


def test_unknown_subject_returns_404(client):
    assert client.get("/api/subjects/astrology/knowledge-graph").status_code == 404


def test_student_academics_endpoint(client, student_headers):
    body = client.get("/api/students/DEMO001/academics", headers=student_headers).json()
    assert body["subjects"]
    assert body["ml_prediction"]["prediction"]["predicted_gpa"] is not None
    assert body["provenance"]["ml"]


def test_subject_detail_endpoint(client, student_headers):
    body = client.get("/api/students/DEMO001/academics/mathematics",
                      headers=student_headers).json()
    assert body["performance"]["trend"]["trend"]
    assert body["mastery"]["concepts"]
    assert all(m["label"] for m in body["mastery"]["concepts"])
    assert body["context_advice"] and body["advice_rules"]


def test_early_warning_endpoint_names_a_root_cause(client, student_headers):
    body = client.get("/api/students/DEMO001/early-warnings", headers=student_headers).json()
    for warning in body["warnings"]:
        assert warning["what_to_do_next"]
        if warning["likely_root_cause"]:
            assert warning["likely_root_cause"]["method"] == "graph-based prerequisite propagation"


def test_students_cannot_read_another_students_academics(client, student_headers):
    assert client.get("/api/students/DEMO005/academics",
                      headers=student_headers).status_code == 403


def test_students_cannot_record_marks(client, student_headers):
    assessment = academics_db.list_assessments("mathematics")[0]
    response = client.post(
        f"/api/assessments/{assessment['assessment_id']}/results",
        json={"student_id": "DEMO001", "marks": 40}, headers=student_headers)
    assert response.status_code == 403


def test_teacher_can_record_a_mark_and_it_reaches_the_analytics(client, teacher_headers):
    assessment = academics_db.list_assessments("aiml")[0]
    created = client.post(
        f"/api/assessments/{assessment['assessment_id']}/results",
        json={"student_id": "DEMO002", "marks": assessment["max_marks"] * 0.9},
        headers=teacher_headers)
    assert created.status_code == 201
    assert created.json()["percentage"] == pytest.approx(90.0, abs=0.5)

    body = client.get("/api/students/DEMO002/academics/aiml", headers=teacher_headers).json()
    entered = [a for a in body["performance"]["assessments"] if a["source"] == "entered"]
    assert entered


def test_marks_above_the_maximum_are_rejected_by_the_api(client, teacher_headers):
    assessment = academics_db.list_assessments("aiml")[0]
    response = client.post(
        f"/api/assessments/{assessment['assessment_id']}/results",
        json={"student_id": "DEMO002", "marks": assessment["max_marks"] + 10},
        headers=teacher_headers)
    assert response.status_code == 422


def test_teacher_can_create_a_subject(client, teacher_headers):
    payload = {"subject_id": "thermo", "name": "Thermodynamics", "code": "THM",
               "semester": "Semester 3", "credits": 3}
    created = client.post("/api/subjects", json=payload, headers=teacher_headers)
    assert created.status_code == 201
    # A subject with no graph concepts must say so rather than silently misbehave.
    assert created.json()["note"] is not None


def test_teacher_subject_analytics_endpoint(client, teacher_headers):
    body = client.get("/api/teacher/subject-analytics", headers=teacher_headers).json()
    assert body["subjects"]
    assert "declining_students" in body and "high_risk_students" in body


def test_practice_recommendation_accepts_a_subject_filter(client, student_headers):
    body = client.get("/api/practice/recommended/DEMO001?subject=networks",
                      headers=student_headers).json()
    assert body["subject"] == "networks"
    assert all(item["subject"] == "networks" for item in body["items"])


def test_practice_recommendation_rejects_an_unknown_subject(client, student_headers):
    assert client.get("/api/practice/recommended/DEMO001?subject=astrology",
                      headers=student_headers).status_code == 422


# --------------------------------------------------------------------------- #
# regression: the original pipeline is untouched
# --------------------------------------------------------------------------- #
def test_original_dashboard_pipeline_still_works(client, student_headers):
    body = client.get("/api/students/DEMO001/dashboard", headers=student_headers).json()
    for key in ("prediction", "explanation", "mastery", "root_cause",
                "recommendations", "study_plan", "cognitive_twin"):
        assert key in body, key
    assert body["explanation"]["top_contributions"]


def test_cognitive_twin_gained_subject_dimensions(client, student_headers):
    body = client.get("/api/cognitive-twin/DEMO001", headers=student_headers).json()
    assert body["traits"], "original traits must survive"
    assert "strong_subjects" in body and "weak_subjects" in body
    assert body["subject_profile"]
