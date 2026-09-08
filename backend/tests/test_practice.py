"""Question bank, practice loop, learning-state update and content RBAC."""
from __future__ import annotations

import pytest

from app.practice import config, mastery_update, scoring


# --------------------------------------------------------------------------- #
# grading
# --------------------------------------------------------------------------- #
def test_mcq_accepts_key_or_option_text():
    q = {"question_type": "MCQ", "correct_answer": "B",
         "options": [{"key": "A", "text": "x"}, {"key": "B", "text": "2x"}]}
    assert scoring.grade(q, "B")[0] is True
    assert scoring.grade(q, "b")[0] is True
    assert scoring.grade(q, "2x")[0] is True
    assert scoring.grade(q, "A")[0] is False
    assert scoring.grade(q, None)[0] is False


def test_numerical_respects_tolerance_and_formats():
    q = {"question_type": "Numerical", "correct_answer": "3.162", "tolerance": 0.05}
    assert scoring.grade(q, "3.16")[0] is True
    assert scoring.grade(q, "3,16")[0] is True
    assert scoring.grade(q, "3.5")[0] is False
    frac = {"question_type": "Numerical", "correct_answer": "0.5", "tolerance": 0.01}
    assert scoring.grade(frac, "1/2")[0] is True


def test_theory_requires_self_marking_and_is_flagged():
    q = {"question_type": "Theory", "correct_answer": "model answer"}
    with pytest.raises(scoring.GradingError):
        scoring.grade(q, "my answer")
    assert scoring.grade(q, "my answer", self_marked_correct=True) == (True, "self")


# --------------------------------------------------------------------------- #
# learning-state update
# --------------------------------------------------------------------------- #
def _attempts(n, correct, difficulty="Medium"):
    return [{"concept": "differentiation", "difficulty": difficulty,
             "is_correct": i < correct, "graded_by": "auto"} for i in range(n)]


def test_update_is_damped_by_sample_size():
    """Two perfect answers must move mastery less than sixteen perfect answers."""
    small = mastery_update.project(40.0, _attempts(2, 2))
    large = mastery_update.project(40.0, _attempts(16, 16))
    assert small["delta"] < large["delta"]
    assert small["alpha_effective"] < large["alpha_effective"]


def test_alpha_saturates_at_reference_count():
    at_ref = mastery_update.project(50.0, _attempts(config.MASTERY_N_REF, 4))
    beyond = mastery_update.project(50.0, _attempts(config.MASTERY_N_REF * 3, 12))
    assert at_ref["alpha_effective"] == pytest.approx(config.MASTERY_ALPHA)
    assert beyond["alpha_effective"] == pytest.approx(config.MASTERY_ALPHA)


def test_hard_questions_carry_more_weight_than_easy():
    hard = mastery_update.project(40.0, _attempts(4, 4, "Hard"))
    easy = mastery_update.project(40.0, _attempts(4, 4, "Easy"))
    assert hard["delta"] >= easy["delta"]


def test_strong_practice_raises_and_weak_practice_lowers_mastery():
    assert mastery_update.project(43.0, _attempts(10, 9))["updated"] > 43.0
    assert mastery_update.project(70.0, _attempts(10, 1))["updated"] < 70.0


def test_update_stays_inside_bounds_and_delta_cap():
    assert mastery_update.project(0.0, _attempts(20, 0))["updated"] >= 0.0
    assert mastery_update.project(100.0, _attempts(20, 20))["updated"] <= 100.0
    swing = mastery_update.project(0.0, _attempts(40, 40))
    assert abs(swing["delta"]) <= config.MAX_DELTA_PER_SESSION


def test_self_graded_attempts_are_excluded_by_default():
    self_only = [{"concept": "limits", "difficulty": "Medium",
                  "is_correct": True, "graded_by": "self"}]
    assert mastery_update.project(50.0, self_only) is None


# --------------------------------------------------------------------------- #
# question bank API
# --------------------------------------------------------------------------- #
def test_bank_is_seeded_across_concepts(client, student_headers):
    body = client.get("/api/questions/bank-summary", headers=student_headers).json()
    assert body["total_questions"] >= 30
    populated = [c for c in body["concepts"] if c["total"] > 0]
    assert len(populated) >= 7


def test_students_never_receive_answers(client, student_headers, teacher_headers):
    student = client.get("/api/questions?limit=5", headers=student_headers).json()
    assert student["answers_included"] is False
    assert all("correct_answer" not in q for q in student["questions"])

    teacher = client.get("/api/questions?limit=5", headers=teacher_headers).json()
    assert teacher["answers_included"] is True
    assert all("correct_answer" in q for q in teacher["questions"])


def test_student_cannot_create_a_question(client, student_headers):
    payload = {"subject": "Mathematics", "concept": "limits", "difficulty": "Easy",
               "question_type": "MCQ", "question_text": "Student written question?",
               "options": [{"key": "A", "text": "yes"}, {"key": "B", "text": "no"}],
               "correct_answer": "A"}
    assert client.post("/api/questions", json=payload, headers=student_headers).status_code == 403


def test_question_crud_round_trip(client, teacher_headers):
    payload = {"subject": "Calculus", "concept": "integration", "difficulty": "Medium",
               "question_type": "MCQ", "question_text": "CRUD probe: integral of 1 dx?",
               "options": [{"key": "A", "text": "x + C"}, {"key": "B", "text": "1 + C"}],
               "correct_answer": "A", "explanation": "Antiderivative of a constant.",
               "marks": 2}
    created = client.post("/api/questions", json=payload, headers=teacher_headers)
    assert created.status_code == 201
    qid = created.json()["question_id"]

    upd = client.put(f"/api/questions/{qid}", json={"difficulty": "Hard"},
                     headers=teacher_headers)
    assert upd.status_code == 200
    assert client.get(f"/api/questions/{qid}", headers=teacher_headers).json()["difficulty"] == "Hard"

    assert client.delete(f"/api/questions/{qid}", headers=teacher_headers).status_code == 200
    # Soft deleted: still readable by id, but gone from the active listing.
    listed = client.get("/api/questions?limit=500", headers=teacher_headers).json()["questions"]
    assert all(q["question_id"] != qid or not q["is_active"] for q in listed)


def test_question_rejects_unknown_concept(client, teacher_headers):
    payload = {"subject": "Mathematics", "concept": "quantum_stuff", "difficulty": "Easy",
               "question_type": "Numerical", "question_text": "What is 2 + 2?",
               "correct_answer": "4"}
    r = client.post("/api/questions", json=payload, headers=teacher_headers)
    assert r.status_code == 422


def test_mcq_answer_must_match_an_option_key(client, teacher_headers):
    payload = {"subject": "Mathematics", "concept": "algebra", "difficulty": "Easy",
               "question_type": "MCQ", "question_text": "Inconsistent MCQ probe?",
               "options": [{"key": "A", "text": "one"}, {"key": "B", "text": "two"}],
               "correct_answer": "D"}
    assert client.post("/api/questions", json=payload, headers=teacher_headers).status_code == 422


# --------------------------------------------------------------------------- #
# recommended practice
# --------------------------------------------------------------------------- #
def test_recommended_practice_is_derived_not_hardcoded(client, student_headers):
    body = client.get("/api/practice/recommended/DEMO001", headers=student_headers).json()
    assert body["items"], "expected at least one weak concept for the demo student"
    for item in body["items"]:
        assert config.MIN_QUESTIONS <= item["recommended_questions"] <= config.MAX_QUESTIONS
        assert item["difficulty"] in config.DIFFICULTIES
        assert item["reason"]
        # Difficulty must follow the configured mastery bands.
        if item["mastery"] < config.EASY_BELOW:
            assert item["difficulty"] == "Easy"
        elif item["mastery"] > config.HARD_ABOVE:
            assert item["difficulty"] == "Hard"


def test_recommendations_differ_between_students(client, teacher_headers):
    a = client.get("/api/practice/recommended/DEMO001", headers=teacher_headers).json()
    b = client.get("/api/practice/recommended/DEMO007", headers=teacher_headers).json()
    signature = lambda body: [(i["concept"], i["recommended_questions"], i["difficulty"])
                              for i in body["items"]]
    assert signature(a) != signature(b), "recommendations look hardcoded"


def test_student_cannot_read_another_students_recommendations(client, student_headers):
    assert client.get("/api/practice/recommended/DEMO005",
                      headers=student_headers).status_code == 403


# --------------------------------------------------------------------------- #
# the full loop
# --------------------------------------------------------------------------- #
def _run_session(client, headers, student_id, concept, answer_all_correctly):
    start = client.post(f"/api/practice/start?student_id={student_id}",
                        json={"concept": concept, "count": 4}, headers=headers)
    assert start.status_code == 201, start.text
    session = start.json()

    answers = []
    for q in session["questions"]:
        full = None
        if q["question_type"] == "Theory":
            answers.append({"question_id": q["question_id"], "selected_answer": "attempt",
                            "self_marked_correct": answer_all_correctly, "time_taken": 30})
            continue
        # The served payload deliberately omits the answer, so read it back as
        # the seeder wrote it.
        from app.database import practice_db
        full = practice_db.get_question(q["question_id"])
        given = full["correct_answer"] if answer_all_correctly else "___wrong___"
        answers.append({"question_id": q["question_id"], "selected_answer": given,
                        "time_taken": 25})

    submit = client.post("/api/practice/submit",
                         json={"session_id": session["session_id"], "answers": answers,
                               "elapsed_seconds": 120},
                         headers=headers)
    assert submit.status_code == 200, submit.text
    return session, submit.json()


def test_served_questions_never_include_the_answer(client, student_headers):
    start = client.post("/api/practice/start?student_id=DEMO001",
                        json={"concept": "differentiation", "count": 3},
                        headers=student_headers)
    assert start.status_code == 201
    for q in start.json()["questions"]:
        assert "correct_answer" not in q and "explanation" not in q


def test_practice_submit_grades_and_explains(client, student_headers):
    _, result = _run_session(client, student_headers, "DEMO001", "differentiation", True)
    summary = result["summary"]
    assert summary["total_questions"] >= 1
    assert summary["correct"] == summary["total_questions"]
    assert summary["accuracy"] == 100.0
    assert summary["concept_performance"]
    assert all(r["explanation"] is not None for r in result["results"])


def test_correct_practice_raises_mastery_and_reruns_root_cause(client, teacher_headers):
    before = client.get("/api/students/DEMO002/mastery", headers=teacher_headers).json()
    before_map = {r["concept"]: r["mastery"] for r in before["records"]}

    _, result = _run_session(client, teacher_headers, "DEMO002", "differentiation", True)

    changes = result["mastery_update"]["changes"]
    assert changes, "practice produced no learning-state change"
    change = changes[0]
    assert change["updated"] > change["previous"]
    assert change["previous"] == pytest.approx(before_map["differentiation"], abs=0.1)

    after = client.get("/api/students/DEMO002/mastery", headers=teacher_headers).json()
    after_map = {r["concept"]: r["mastery"] for r in after["records"]}
    assert after_map["differentiation"] > before_map["differentiation"]
    assert [r for r in after["records"] if r["concept"] == "differentiation"][0]["source"] == "practice"
    assert "current" in result["root_cause"]


def test_practice_does_not_change_the_prediction_or_shap(client, teacher_headers):
    """Mastery is not a model input; the loop must not move the prediction."""
    before = client.get("/api/students/DEMO003/dashboard", headers=teacher_headers).json()
    _run_session(client, teacher_headers, "DEMO003", "integration", True)
    after = client.get("/api/students/DEMO003/dashboard", headers=teacher_headers).json()

    assert after["prediction"]["predicted_gpa"] == before["prediction"]["predicted_gpa"]
    assert after["prediction"]["risk_tier"] == before["prediction"]["risk_tier"]
    assert (after["explanation"]["top_contributions"][0]["shap_value"]
            == before["explanation"]["top_contributions"][0]["shap_value"])


def test_session_cannot_be_submitted_twice(client, teacher_headers):
    session, _ = _run_session(client, teacher_headers, "DEMO004", "limits", False)
    replay = client.post("/api/practice/submit",
                         json={"session_id": session["session_id"],
                               "answers": [{"question_id": session["questions"][0]["question_id"],
                                            "selected_answer": "A"}]},
                         headers=teacher_headers)
    assert replay.status_code == 409


def test_answers_from_outside_the_session_are_rejected(client, teacher_headers):
    start = client.post("/api/practice/start?student_id=DEMO005",
                        json={"concept": "limits", "count": 2}, headers=teacher_headers)
    session_id = start.json()["session_id"]
    r = client.post("/api/practice/submit",
                    json={"session_id": session_id,
                          "answers": [{"question_id": 999999, "selected_answer": "A"}]},
                    headers=teacher_headers)
    assert r.status_code == 422


def test_performance_and_history_reflect_stored_attempts(client, teacher_headers):
    _run_session(client, teacher_headers, "DEMO006", "integration", True)

    perf = client.get("/api/practice/performance/DEMO006", headers=teacher_headers).json()
    integration = [c for c in perf["concepts"] if c["concept"] == "integration"][0]
    assert integration["attempted"] >= 1
    assert integration["accuracy"] == 100.0
    assert perf["mastery_history"]

    hist = client.get("/api/practice/history/DEMO006", headers=teacher_headers).json()
    assert hist["sessions"] and hist["totals"]["attempted"] >= 1


def test_dashboard_exposes_practice_without_breaking_the_pipeline(client, student_headers):
    body = client.get("/api/students/DEMO001/dashboard", headers=student_headers).json()
    for key in ("prediction", "explanation", "mastery", "root_cause",
                "recommendations", "study_plan", "cognitive_twin", "practice"):
        assert key in body, key
    assert "recommended" in body["practice"]


def test_start_rejects_unknown_concept(client, student_headers):
    r = client.post("/api/practice/start?student_id=DEMO001",
                    json={"concept": "quantum_stuff", "count": 3}, headers=student_headers)
    assert r.status_code == 422


# --------------------------------------------------------------------------- #
# resources and sample papers
# --------------------------------------------------------------------------- #
def test_resources_are_seeded_and_recommended_dynamically(client, student_headers):
    listing = client.get("/api/resources", headers=student_headers).json()
    assert listing["count"] >= 10

    rec = client.get("/api/resources/recommended/DEMO001", headers=student_headers).json()
    assert rec["items"]
    assert all(item["reason"] for item in rec["items"])


def test_resource_write_requires_teacher(client, student_headers, teacher_headers):
    payload = {"title": "Probe resource", "subject": "Calculus", "concept": "limits",
               "resource_type": "Notes", "difficulty": "Easy", "estimated_minutes": 10,
               "url": "https://example.org/notes"}
    assert client.post("/api/resources", json=payload, headers=student_headers).status_code == 403
    created = client.post("/api/resources", json=payload, headers=teacher_headers)
    assert created.status_code == 201
    rid = created.json()["resource_id"]
    assert client.delete(f"/api/resources/{rid}", headers=teacher_headers).status_code == 200


def test_resource_rejects_non_http_url(client, teacher_headers):
    payload = {"title": "Bad url", "subject": "Calculus", "concept": "limits",
               "resource_type": "Notes", "difficulty": "Easy", "url": "javascript:alert(1)"}
    assert client.post("/api/resources", json=payload, headers=teacher_headers).status_code == 422


def test_sample_papers_are_labelled_as_demo(client, student_headers):
    body = client.get("/api/sample-papers", headers=student_headers).json()
    assert body["count"] >= 1
    assert all(p["is_demo"] for p in body["papers"])
    assert "not official" in body["note"].lower()


def test_sample_paper_downloads_as_a_real_pdf(client, student_headers):
    papers = client.get("/api/sample-papers", headers=student_headers).json()["papers"]
    paper_id = papers[0]["paper_id"]
    r = client.get(f"/api/sample-papers/{paper_id}/file", headers=student_headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-")
    assert r.content.rstrip().endswith(b"%%EOF")


def test_paper_upload_rejects_non_pdf_content(client, teacher_headers):
    r = client.post(
        "/api/sample-papers",
        files={"file": ("evil.pdf", b"<?php system($_GET[0]); ?>", "application/pdf")},
        data={"title": "Not a PDF", "subject": "Mathematics", "difficulty": "Easy"},
        headers=teacher_headers,
    )
    assert r.status_code == 422


def test_paper_upload_rejects_wrong_mime_type(client, teacher_headers):
    r = client.post(
        "/api/sample-papers",
        files={"file": ("notes.txt", b"%PDF-1.4 fake", "text/plain")},
        data={"title": "Text file", "subject": "Mathematics", "difficulty": "Easy"},
        headers=teacher_headers,
    )
    assert r.status_code == 415


def test_paper_upload_and_delete_round_trip(client, teacher_headers):
    from app.database.seed_content import _demo_pdf

    pdf = _demo_pdf("Upload probe", ["line one"])
    created = client.post(
        "/api/sample-papers",
        files={"file": ("probe.pdf", pdf, "application/pdf")},
        data={"title": "Upload probe", "subject": "Mathematics",
              "difficulty": "Medium", "year": "2026"},
        headers=teacher_headers,
    )
    assert created.status_code == 201
    paper_id = created.json()["paper_id"]
    assert client.get(f"/api/sample-papers/{paper_id}/file",
                      headers=teacher_headers).content.startswith(b"%PDF-")
    assert client.delete(f"/api/sample-papers/{paper_id}", headers=teacher_headers).status_code == 200


def test_student_cannot_upload_or_delete_papers(client, student_headers):
    from app.database.seed_content import _demo_pdf

    r = client.post(
        "/api/sample-papers",
        files={"file": ("probe.pdf", _demo_pdf("x", ["y"]), "application/pdf")},
        data={"title": "Student upload", "subject": "Mathematics", "difficulty": "Easy"},
        headers=student_headers,
    )
    assert r.status_code == 403


# --------------------------------------------------------------------------- #
# teacher analytics
# --------------------------------------------------------------------------- #
def test_practice_analytics_aggregates_real_attempts(client, teacher_headers):
    _run_session(client, teacher_headers, "DEMO008", "control_systems", False)
    body = client.get("/api/teacher/practice-analytics", headers=teacher_headers).json()

    assert body["totals"]["total_questions"] >= 30
    assert body["totals"]["total_attempts"] >= 1
    assert body["concept_performance"]
    for row in body["concept_performance"]:
        assert 0.0 <= row["average_accuracy"] <= 100.0
        assert row["correct"] <= row["attempted"]


def test_students_cannot_read_practice_analytics(client, student_headers):
    assert client.get("/api/teacher/practice-analytics",
                      headers=student_headers).status_code == 403
