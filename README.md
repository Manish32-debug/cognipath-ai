# CogniPath AI

**An Explainable AI-Driven Platform for Student Performance Prediction and Personalized Learning Recommendation**

CogniPath AI predicts academic performance from real academic and behavioural
indicators, explains every prediction with SHAP, traces weak concepts backwards
through a prerequisite knowledge graph to their *probable* origin, and converts
that diagnosis into prioritised recommendations, a weekly study plan and a
Cognitive Digital Twin.

Nothing in the application is hardcoded. Every number the dashboard shows is
produced at request time by a trained model, a SHAP explainer, a graph traversal
or a documented rule.

---

## 1. Problem statement

Conventional academic dashboards report *what* happened (marks, attendance).
They do not tell a student *why* the model expects them to struggle, and they do
not distinguish a symptom from its cause. A student weak in Differential
Equations is usually told to study more Differential Equations, when the real
blockage is often two topics upstream.

CogniPath AI addresses three gaps:

1. **Opacity** &mdash; predictions without explanations are not actionable.
2. **Symptom-level advice** &mdash; recommending the failing topic ignores prerequisites.
3. **Generic study plans** &mdash; plans that ignore the student's actual time budget and weakest links.

## 2. Features

| Module | What it does |
|---|---|
| Prediction | GPA (regression), pass probability (binary), risk tier (3-class) |
| Explainability | Real SHAP attribution per prediction, split into helping / hurting factors |
| Knowledge graph | 14-concept prerequisite DAG in NetworkX, interactive in the UI |
| Root-cause reasoning | Backward risk propagation with upstream-clearance damping |
| Recommendation engine | Transparent priority scoring over concepts + curated resources |
| Study plan | Weekly schedule derived from the student's own time budget and risk |
| Cognitive Digital Twin | Five estimated learning-profile indices, each labelled with its basis |
| Student dashboard | Ten sections: overview, performance, prediction, explainability, mastery, root cause, recommendations, plan, twin, settings |
| Teacher dashboard | Cohort risk distribution, weakest-concept ranking, search/filter, per-student drill-down |
| Auth | JWT + PBKDF2-SHA256, server-enforced role separation |

## 3. Architecture

```
React + Vite SPA                      FastAPI                     ML / reasoning
--------------------------------------------------------------------------------
pages/            ──axios──▶  api/routes/auth.py       ──▶  core/security.py
  Landing, Login                api/routes/students.py  ──▶  database/db.py (SQLite)
  StudentDashboard              api/routes/analysis.py  ──┬─▶ ml/predictor.py ──▶ joblib bundle
  TeacherDashboard                                        │      (models + preprocessor
components/  charts/  graph/                              │       + SHAP explainers)
                                                          ├─▶ graph/knowledge_graph.py (NetworkX DAG)
                                                          ├─▶ graph/root_cause.py
                                                          ├─▶ recommendations/engine.py
                                                          ├─▶ recommendations/study_plan.py
                                                          └─▶ services/cognitive_twin.py
                                        services/pipeline.py orchestrates all of the above
```

### Data flow (single student)

```
features ─▶ preprocessor.transform ─▶ 3 models ─▶ prediction
                                   └─▶ SHAP explainer ─▶ contributions
mastery  ─▶ root_cause.analyse (graph traversal) ─▶ weak concepts + likely root causes
                                   └─▶ engine.recommend ─▶ study_plan.generate
prediction + mastery + roots ─▶ cognitive_twin.build
```

### Folder structure

```
cognipath/
├── backend/
│   ├── app/
│   │   ├── main.py                     FastAPI app: wiring, CORS, error handlers, lifespan
│   │   ├── api/deps.py                 JWT dependency + RBAC helpers
│   │   ├── api/routes/auth.py          /api/auth/*
│   │   ├── api/routes/students.py      /api/students/*
│   │   ├── api/routes/analysis.py      predict, explain, graph, root-cause, recs, plan, twin, teacher
│   │   ├── schemas/models.py           Pydantic v2 request/response models
│   │   ├── core/config.py              settings from environment
│   │   ├── core/security.py            PBKDF2 hashing + JWT
│   │   ├── database/db.py              SQLite schema + repository functions
│   │   ├── database/seed.py            demo cohort seeding
│   │   ├── ml/features.py              raw vs derived feature schema, target derivation
│   │   ├── ml/dataset.py               dataset loading + profiling
│   │   ├── ml/train.py                 training pipeline (compare, select, persist)
│   │   ├── ml/predictor.py             model serving + SHAP
│   │   ├── ml/mastery_simulator.py     documented demo-only mastery generation
│   │   ├── graph/knowledge_graph.py    prerequisite DAG
│   │   ├── graph/root_cause.py         risk propagation algorithm
│   │   ├── recommendations/engine.py   priority scoring + resource catalogue
│   │   ├── recommendations/study_plan.py
│   │   └── services/pipeline.py, cognitive_twin.py
│   ├── data/student-mat.csv            UCI dataset
│   ├── models/                         joblib bundle + evaluation.json (generated)
│   ├── tests/                          47 pytest tests
│   └── requirements.txt
└── frontend/
    └── src/{components,charts,graph,pages,layouts,context,hooks,services,utils,styles}
```

## 4. Technology stack

**Frontend:** React 18, Vite 5, React Router 6, Recharts, Axios, hand-written CSS design system.
**Backend:** FastAPI, Pydantic v2, Uvicorn, SQLite (stdlib `sqlite3`), PyJWT.
**ML:** scikit-learn, SHAP, pandas, NumPy, joblib.
**Graph:** NetworkX.
**Tests:** pytest (backend), Vitest + Testing Library (frontend).

## 5. Dataset

**UCI Student Performance** (Cortez & Silva, 2008), `student-mat.csv`: **395 records, 33 raw
columns, 0 missing values**. Pass rate 67.1%. Risk distribution: 165 Medium / 130 High / 100 Low.

### Raw vs derived

`app/ml/features.py` keeps these strictly separate:

* **Raw numeric (15):** `age, Medu, Fedu, traveltime, studytime, failures, famrel, freetime, goout, Dalc, Walc, health, absences, G1, G2`
* **Raw categorical (11):** `sex, address, famsize, Pstatus, schoolsup, famsup, paid, activities, higher, internet, romantic`
* **Derived (2):**
  * `attendance_pct = 100 × (1 − min(absences, 60)/60)` &mdash; the dataset records absences, not
    attendance; 60 nominal sessions per term is a **documented modelling assumption** and a
    monotone rescaling, so it adds interpretability, not information.
  * `grade_trend = G2 − G1`.

After one-hot encoding: **28 model features**.

### Targets (all documented transforms of `G3`)

| Target | Rule |
|---|---|
| `gpa` | `G3 / 2` &mdash; exact rescale from the 0–20 Portuguese scale to 0–10 |
| `passed` | `G3 ≥ 10` &mdash; the pass mark used in the original paper |
| `risk_tier` | High `G3 < 10`, Medium `10 ≤ G3 < 14`, Low `G3 ≥ 14` |

### What the dataset does **not** contain

There are **no per-concept assessment scores**. Concept mastery therefore cannot be derived from
it, and this project does not pretend otherwise:

* Demo-cohort mastery is generated by `app/ml/mastery_simulator.py`, stored with
  `source='simulated'`, and the UI prints a warning banner wherever it is shown.
* Real students enter their own scores (`self_reported`) or import them (`assessment`).

The simulator is anchored to each student's real record (G1, G2, study time, failures,
attendance), propagates values down the prerequisite chain, and applies a per-student
"topic shock" so different students have different weak chains. It is documented in full in the
module docstring.

## 6. ML methodology

* Stratified 80/20 split on `risk_tier` (316 train / 79 test).
* The `ColumnTransformer` (StandardScaler + OneHotEncoder) is **fitted on the training split only**.
* Candidates compared by 5-fold cross-validation **on the training split**; the test split is
  scored exactly once.
* Missing optional inputs at serving time fall back to **training** medians/modes, so imputation
  cannot leak test statistics.

### Model comparison (cross-validated, training split)

| Task | Metric | Candidates |
|---|---|---|
| GPA regression | R² | Linear 0.802, Ridge 0.804, Lasso 0.814, **RF 0.875**, GBR 0.854, HistGB 0.852 |
| Pass classification | ROC-AUC | **LogReg 0.972**, RF 0.971, GB 0.958, HistGB 0.967 |
| Risk classification | macro F1 | LogReg 0.873, **RF 0.879**, GB 0.859, HistGB 0.861 |

### Held-out test metrics

| Task | Selected model | Metrics |
|---|---|---|
| GPA | RandomForestRegressor | MAE **0.455**, RMSE **0.700**, R² **0.897** |
| Pass | LogisticRegression | Acc **0.937**, P 0.980, R 0.925, F1 **0.951**, ROC-AUC **0.993** |
| Risk | RandomForestClassifier | Acc **0.835**, macro-P 0.880, macro-R 0.811, macro-F1 **0.826** |

Confusion matrices for both classifiers are in `models/evaluation.json` and are served at
`GET /api/evaluation`.

**Honest caveat:** G1 and G2 are extremely strong predictors of G3 — this is well known for this
dataset, and it is why R² is high. The model is a *within-term early-warning* tool, not a
cold-start predictor for a student with no prior grades.

## 7. SHAP explainability

`TreeExplainer` for tree ensembles, `LinearExplainer` for linear models — both exact, so no kernel
approximation is needed at request time. Explainers are built once and cached per process.

* For the risk model, the **predicted class** is explained ("why did it say High?").
* Units are reported per task: GPA points, log-odds of passing, or class probability.
* Additivity (`base + Σφ = model output`) is asserted in the test suite to within 0.05.

The UI separates positive contributors ("what is helping") from negative ones ("what is hurting")
and shows each feature's actual value on hover.

## 8. Knowledge graph

A NetworkX `DiGraph` of 14 concepts and 20 weighted prerequisite edges, validated as acyclic at
build time and cached with `lru_cache`. Edges carry a `strength` in (0, 1] expressing how strongly
a topic depends on its prerequisite.

Required chain, preserved: `Functions → Limits → Differentiation → Integration → Differential
Equations → (Laplace / Signals) → Control Systems → Robotics`, plus Algebra, Trigonometry, Linear
Algebra, Probability and Numerical Methods.

Adding a concept means adding one entry to `CONCEPTS` and its edges to `PREREQUISITES` — the graph
is data, not code.

## 9. Root-cause reasoning

For a concept *c* with mastery *m*:

1. `gap(c) = max(0, 70 − m) / 70` — a concept at target has zero gap and can never be blamed.
2. `downstream(a) = Σ over weak descendants d of gap(d) × path_strength(a→d) × 0.6^(hops−1)`
3. `clearance(a) = 1 − max gap among a's own prerequisites`, floored at 0.15 — **this is the key
   term**: if *a*'s prerequisites are themselves weak, *a* is not the start of the chain.
4. `root_score(a) = gap(a) × (1 + 1.2 × downstream(a)) × clearance(a)`

Worked example (the specification's own case):

| Concept | Mastery | root_score |
|---|---|---|
| Limits | 45% | **0.886** |
| Differentiation | 30% | **0.854** |
| Differential Equations | 35% | 0.417 |
| Integration | 48% | 0.306 |

Differential Equations is the *symptom*; the algorithm ranks Limits and Differentiation above it.

Every result includes the reasoning path (a real `nx.shortest_path`), the three score components,
and the wording *"likely root cause" / "probable prerequisite gap"*. The API returns an explicit
disclaimer that this is **diagnostic inference, not proven causality**.

## 10. Recommendation engine

Rule-based, deliberately. A learned recommender needs interaction data (resource opened, dwell
time, subsequent score) which this project does not have; a model fitted to nothing would be a
black box pretending to be intelligence. `score_concept` is the single extension point where a
learned ranker would later plug in.

```
priority = 0.45 × normalised root-cause score
         + 0.30 × mastery gap
         + 0.15 × normalised downstream fan-out
         + 0.10 × predicted risk boost
```

Root causes therefore outrank equally weak downstream concepts. Each item carries a reason, an
action matched to severity, curated free resources (Khan Academy, MIT OCW, 3Blue1Brown, Paul's
Notes) and an effort estimate. All 14 concepts have catalogue coverage (asserted in tests).

## 11. Weekly study plan

```
weekly_minutes = STUDYTIME_MINUTES[studytime] + 30 × (freetime − 3), × risk multiplier,
                 clamped to [120, 900]
```

Minutes are split across concepts in proportion to priority score, chopped into 30–60 minute
sessions, and dealt round-robin across the week — with **root-cause sessions scheduled first**,
because later topics depend on them.

## 12. Cognitive Digital Twin

Five indices, each returned with `status: "Estimated"`, the `basis` (which inputs produced it) and
an `evidence_strength`:

| Trait | Derived from |
|---|---|
| Learning speed | `G2 − G1` relative to reported study time |
| Memory retention | Mastery held in foundational vs recently taught concepts |
| Study consistency | Attendance, study time, past failures |
| Confidence (proxy) | Past failures and grade trend |
| Academic engagement | Attendance, study time, free time |

**Learning style is not inferred.** No data here could support it, and the learning-styles
hypothesis has weak empirical backing (Pashler et al., 2008). It is displayed only if the student
states it, otherwise "Not assessed".

## 13. Installation

Requires Python 3.10+ and Node 18+.

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m app.ml.train          # trains, compares, selects, saves models/ + evaluation.json
python -m app.database.seed     # creates cognipath.db and the 60-student demo cohort
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173 (proxies /api to port 8000)
```

Or use the bundled scripts: `./run_backend.sh` then `./run_frontend.sh`.

### Demo credentials

| Role | Username | Password |
|---|---|---|
| Teacher | `teacher` | `teach1234` |
| Student | `demo001` … `demo060` | `demo1234` |

These are seeded development accounts, documented as such.

## 14. API

Interactive docs at **`http://127.0.0.1:8000/docs`** (23 documented paths).

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/register`, `/api/auth/login` | issue JWT |
| GET | `/api/auth/me` | current identity |
| GET/POST | `/api/students` | list (teacher) / create or update |
| GET | `/api/students/{id}` | stored record |
| GET/PUT | `/api/students/{id}/mastery` | read / update concept mastery |
| GET | `/api/students/{id}/history` | logged prediction history |
| GET | `/api/students/{id}/dashboard` | **whole pipeline in one call** |
| POST | `/api/predict`, `/api/explain?task=gpa\|pass\|risk` | stateless prediction / SHAP |
| GET | `/api/knowledge-graph`, `/api/concepts` | curriculum graph (public) |
| POST/GET | `/api/root-cause`, `/api/root-cause/{id}` | propagation analysis |
| GET | `/api/recommendations/{id}`, `/api/study-plan/{id}`, `/api/cognitive-twin/{id}` | |
| GET | `/api/teacher/analytics`, `/api/teacher/student/{id}` | teacher only |
| GET | `/api/model-info`, `/api/evaluation`, `/api/health` | system |

## 15. Testing

```bash
cd backend  && pytest -q      # 47 passed
cd frontend && npm test       # 12 passed
```

Backend coverage includes: derived-column correctness, target-rule correctness, model monotonicity
(better grades ⇒ higher predicted GPA), **SHAP additivity**, DAG invariants, root-cause ordering
("upstream beats downstream", "a strong concept is never a root cause", "reasoning paths are real
graph paths"), recommendation prioritisation, study-plan budget bounds, RBAC 401/403, validation
422s, and a full create-student → dashboard → delete round trip.

Frontend tests render the prediction, root-cause, recommendation, study-plan, mastery and error
components against representative API payloads.

## 16. Error handling and loading states

The axios layer normalises every failure into one readable message (unreachable API, timeout,
untrained models, validation detail). Every async panel uses the shared `<Async>` wrapper, which
shows a labelled skeleton ("Calculating explanation…", "Tracing prerequisite dependencies…") and
an error card with a retry button. The backend returns 404 for unknown students, 422 for invalid
input or unknown concepts, 401/403 for auth failures and 503 when the model bundle is missing —
with a message telling you to run the training command.

## 17. Limitations

1. **Correlation, not causation.** Both the SHAP output and the graph traversal are inferential.
   Neither establishes cause.
2. **G1/G2 dominance.** The models lean heavily on prior grades; they cannot predict for a student
   with no assessment history.
3. **Dataset origin.** Two Portuguese secondary schools, 2005–2006, 395 students. Coefficients do
   not transfer unchanged to another institution — retrain on local data.
4. **Simulated mastery in the demo cohort.** Clearly labelled; the pipeline is real but the
   mastery inputs for demo students are generated.
5. **Cognitive Twin traits are proxies**, not psychometric measurements.
6. **Small test set** (79 records) — metrics carry meaningful variance.
7. **Prototype auth.** Correct primitives, but no lockout, rate limiting or refresh-token rotation.

## 18. Responsible AI

The system never states that a student *will* fail. It reports *predicted risk*, always alongside
its explanation, and is designed to trigger teacher review rather than automate decisions. Only a
student ID, display name and academic indicators are stored — no contact or demographic
identifiers beyond what the model consumes. Simulated data is labelled as simulated everywhere it
appears.

## 19. Future enhancements

* Replace simulated mastery with real per-concept assessment ingestion (LMS/quiz integration).
* Learned recommender once resource-interaction data exists (`score_concept` is the seam).
* Temporal modelling across multiple terms instead of a single-term snapshot.
* Fairness auditing of predictions across `sex`, `address` and parental-education subgroups.
* Per-edge prerequisite strengths estimated from data instead of set by curriculum judgement.

## 20. Reference

Cortez, P. and Silva, A. (2008). *Using Data Mining to Predict Secondary School Student
Performance.* Proceedings of 5th FUture BUsiness TEChnology Conference.
Lundberg, S. and Lee, S.-I. (2017). *A Unified Approach to Interpreting Model Predictions.* NeurIPS.
