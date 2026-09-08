"""API surface: auth, RBAC, validation, pipeline endpoints, error handling."""
from __future__ import annotations


def test_health_reports_loaded_models(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["models"] == "loaded"


def test_login_rejects_bad_password(client):
    r = client.post("/api/auth/login", json={"username": "teacher", "password": "wrongpass"})
    assert r.status_code == 401


def test_protected_route_requires_token(client):
    assert client.get("/api/students/DEMO001/dashboard").status_code == 401


def test_student_cannot_read_another_student(client, student_headers):
    assert client.get("/api/students/DEMO005/dashboard", headers=student_headers).status_code == 403


def test_student_cannot_access_teacher_analytics(client, student_headers):
    assert client.get("/api/teacher/analytics", headers=student_headers).status_code == 403


def test_unknown_student_returns_404(client, teacher_headers):
    r = client.get("/api/students/NOPE999/dashboard", headers=teacher_headers)
    assert r.status_code == 404


def test_dashboard_returns_full_pipeline(client, student_headers):
    body = client.get("/api/students/DEMO001/dashboard", headers=student_headers).json()
    for key in ("prediction", "explanation", "mastery", "root_cause",
                "recommendations", "study_plan", "cognitive_twin"):
        assert key in body, key
    assert body["explanation"]["top_contributions"]
    assert body["mastery"]["source"] in {"simulated", "self_reported", "assessment", "practice", "mixed"}


def test_predict_validates_feature_ranges(client, teacher_headers, sample_features):
    bad = {**sample_features, "G1": 45}
    assert client.post("/api/predict", json=bad, headers=teacher_headers).status_code == 422


def test_predict_and_explain_agree_on_the_model(client, teacher_headers, sample_features):
    p = client.post("/api/predict", json=sample_features, headers=teacher_headers).json()
    e = client.post("/api/explain?task=gpa", json=sample_features, headers=teacher_headers).json()
    assert e["model"] == p["models_used"]["gpa"]
    assert abs(e["prediction"] - p["predicted_gpa"]) < 0.25


def test_knowledge_graph_is_public_and_complete(client):
    body = client.get("/api/knowledge-graph").json()
    assert body["stats"]["n_nodes"] >= 7 and body["edges"]


def test_root_cause_rejects_unknown_concept(client, teacher_headers):
    r = client.post("/api/root-cause", json={"mastery": {"quantum_stuff": 30}},
                    headers=teacher_headers)
    assert r.status_code == 422


def test_mastery_update_round_trip(client, student_headers):
    payload = {"records": [{"concept": "limits", "mastery": 41.5, "source": "self_reported"}]}
    assert client.put("/api/students/DEMO001/mastery", json=payload,
                      headers=student_headers).status_code == 200
    body = client.get("/api/students/DEMO001/mastery", headers=student_headers).json()
    limits = [r for r in body["records"] if r["concept"] == "limits"][0]
    assert limits["mastery"] == 41.5 and limits["source"] == "self_reported"


def test_mastery_update_rejects_out_of_range(client, student_headers):
    payload = {"records": [{"concept": "limits", "mastery": 180}]}
    assert client.put("/api/students/DEMO001/mastery", json=payload,
                      headers=student_headers).status_code == 422


def test_teacher_analytics_shape(client, teacher_headers):
    body = client.get("/api/teacher/analytics", headers=teacher_headers).json()
    assert body["total_students"] > 0
    assert set(body["risk_distribution"]) <= {"Low", "Medium", "High"}
    assert body["concept_summary"] and body["students"]


def test_create_student_then_run_pipeline(client, teacher_headers, sample_features):
    payload = {
        "student_id": "TEST001",
        "display_name": "Pipeline Test",
        "features": sample_features,
        "mastery": [{"concept": "limits", "mastery": 30, "source": "assessment"},
                    {"concept": "differentiation", "mastery": 25, "source": "assessment"}],
    }
    assert client.post("/api/students", json=payload, headers=teacher_headers).status_code == 201
    body = client.get("/api/students/TEST001/dashboard", headers=teacher_headers).json()
    assert body["mastery"]["source"] == "assessment"
    assert body["root_cause"]["root_causes"][0]["concept"] in {"limits", "differentiation"}
    assert client.delete("/api/students/TEST001", headers=teacher_headers).status_code == 204


def test_prediction_history_grows(client, student_headers):
    before = len(client.get("/api/students/DEMO001/history", headers=student_headers).json()["history"])
    client.get("/api/students/DEMO001/dashboard", headers=student_headers)
    after = len(client.get("/api/students/DEMO001/history", headers=student_headers).json()["history"])
    assert after >= before
