# CogniPath AI

**An Explainable AI-Powered Multi-Subject Student Intelligence and Personalized Learning Platform**

CogniPath AI tracks a student's academic progress over time across six subjects
and six assessments per subject, predicts performance from that longitudinal
record, explains every prediction with SHAP, traces weak concepts backwards
through subject-aware prerequisite knowledge graphs to their *probable* origin,
raises early warnings before a subject becomes a fail, and converts the whole
diagnosis into prioritised recommendations, adaptive practice, a weekly study
plan and a Cognitive Digital Twin.

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
| Multi-subject records | 6 subjects, 6+ assessments each, in a normalized subjects -> assessments -> results schema |
| Trend detection | Least-squares slope + volatility over the assessment series: Improving / Declining / Stable / Volatile |
| Early warning | Rule-based triggers that fire before a fail, each with its evidence, root cause and next steps |
| Knowledge graph | 47-concept prerequisite DAG in NetworkX, per-subject views, cross-subject prerequisite edges |
| Root-cause reasoning | Backward risk propagation with upstream-clearance damping |
| Recommendation engine | Transparent priority scoring over concepts + curated resources |
| Study plan | Weekly schedule derived from the student's own time budget and risk |
| Cognitive Digital Twin | Five estimated learning-profile indices, each labelled with its basis |
| Question bank | MCQ / Numerical / Theory items mapped to knowledge-graph concepts, teacher-managed |
| Practice | Recommended and free practice sessions, graded server side with per-question explanations |
| Learning-state update | Practice performance moves concept mastery through a damped, transparent, configurable rule |
| Resource library | Study materials per concept, recommended by the same priority ranking as everything else |
| Sample papers | PDF storage, upload validation and authenticated download |
| Context-aware advice | Rule table mapping attendance / trend / mastery / practice accuracy to a study strategy |
| Student dashboard | Sixteen sections, including Academic overview and per-subject detail: overview, academic overview, subject detail, performance, prediction, explainability, mastery, root cause, recommendations, plan, practice, practice history, study materials, sample papers, twin, settings |
| Teacher dashboard | Subject analytics, assessment trends, declining/improving/high-risk lists, mark entry, cohort risk distribution, weakest-concept ranking, search/filter, per-student drill-down, question bank, resource and paper management, practice analytics |
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
python -m app.database.seed     # cognipath.db, 60-student demo cohort, question bank,
                                # resource library and demo sample papers
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173 (proxies /api to port 8000)
```

Or use the bundled scripts: `./run_backend.sh` then `./run_frontend.sh`.

`app.database.seed` calls `app.database.seed_content` for you. To reseed only the question
bank, resources and demo papers against an existing database — which is what you want on a
deployed instance whose student data already exists — run it directly:

```bash
cd backend && python -m app.database.seed_content
```

Both seeders are idempotent: they insert only rows that are absent and never overwrite
existing student, mastery or attempt data.

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
| GET | `/api/practice/config` | the exact constants used for selection and the mastery update |
| GET | `/api/practice/recommended/{id}` | what to practise, how much, at what difficulty, and why |
| POST | `/api/practice/start?student_id={id}` | open a session; questions are served **without** answers |
| POST | `/api/practice/submit` | grade, update learning state, re-run root cause, return the delta |
| GET | `/api/practice/history/{id}`, `/api/practice/performance/{id}` | session log / concept statistics |
| GET/POST | `/api/questions` | list (answers withheld from students) / create (teacher) |
| GET | `/api/questions/bank-summary` | per-concept coverage by difficulty |
| GET/PUT/DELETE | `/api/questions/{id}` | read / edit / retire (teacher writes) |
| GET/POST | `/api/resources` | library listing / create (teacher) |
| GET | `/api/resources/recommended/{id}` | concept-prioritised materials with reasons |
| PUT/DELETE | `/api/resources/{id}` | edit / retire (teacher) |
| GET/POST | `/api/sample-papers` | listing / multipart PDF upload (teacher) |
| GET | `/api/sample-papers/{id}/file?download=true` | authenticated inline view or download |
| DELETE | `/api/sample-papers/{id}` | remove (teacher) |
| GET | `/api/teacher/practice-analytics` | cohort practice aggregates (teacher) |

## 15. Testing

```bash
cd backend  && pytest -q      # 85 passed
cd frontend && npm test       # 20 passed
```

Backend coverage includes: derived-column correctness, target-rule correctness, model monotonicity
(better grades ⇒ higher predicted GPA), **SHAP additivity**, DAG invariants, root-cause ordering
("upstream beats downstream", "a strong concept is never a root cause", "reasoning paths are real
graph paths"), recommendation prioritisation, study-plan budget bounds, RBAC 401/403, validation
422s, and a full create-student → dashboard → delete round trip.

`tests/test_practice.py` adds grading correctness for all three question types, damping and
bounds on the learning-state update, answer non-disclosure to students, question-bank CRUD and
concept validation, the full root-cause → practice → mastery → root-cause loop, proof that
practice does **not** change the prediction or its SHAP values, session replay rejection,
upload content sniffing, and RBAC on every new write path.

Frontend tests render the prediction, root-cause, recommendation, study-plan, mastery and error
components against representative API payloads, plus the practice runner (selection → submit
payload → results), the resource and sample-paper pages, and practice-history empty states.

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
2. **Prior-grade dominance, and a compression step.** The models lean heavily on prior
   performance and cannot predict for a student with no assessment history. Since the
   multi-subject upgrade they read a *compressed* view of the assessment series (see 23.7):
   real longitudinal input, but the models themselves were never retrained on
   multi-assessment data, because no labelled multi-assessment dataset exists here. Volatility,
   subject identity and per-subject trend are computed by rules and shown separately.
3. **Dataset origin.** Two Portuguese secondary schools, 2005–2006, 395 students. Coefficients do
   not transfer unchanged to another institution — retrain on local data.
4. **Simulated mastery in the demo cohort.** Clearly labelled; the pipeline is real but the
   mastery inputs for demo students are generated.
5. **Cognitive Twin traits are proxies**, not psychometric measurements.
6. **Small test set** (79 records) — metrics carry meaningful variance.
7. **Prototype auth.** Correct primitives, but no lockout, rate limiting or refresh-token rotation.
8. **Mastery is a learning-state estimate, not a measurement.** The update rule in
   `app/practice/mastery_update.py` is transparent bookkeeping, not item-response theory. It is
   reproducible by hand from the stored attempts and the config, and that is the whole of its
   claim.
9. **Theory questions are self-marked.** There is no defensible way to grade free text here, so
   the student marks their own answer against the model answer. Self-marked attempts are stored
   with `graded_by='self'` and excluded from the learning-state update by default.
10. **Thin question bank.** 87 seeded questions across 47 concepts — roughly two per concept for
    the newer subjects. The recommender can ask for up to 15 questions on a concept where only
    two exist; the UI reports what is actually available (`available_questions`), and the teacher
    analytics page shows which concepts are starved. This is the most visible gap in the demo:
    a subject page can recommend "practice 8 questions" and deliver two.
11. **Sample papers are generated placeholders.** They carry no institutional status and are not
    official or previous-year university papers.
12. **Uploads are not durable on ephemeral hosting.** See section 21.
13. **Assessment series are simulated for demo students.** Deterministic, anchored to each
    student's real record, labelled `source='simulated'` in the database and in the UI. A real
    deployment records genuine marks through the teacher's Assessments page, and every analytic
    then runs on real data with no code change.
14. **Per-subject prediction reuses a single-subject model.** The same trained model is applied
    to each subject's marks; it has no notion of which subject it is reading.
15. **Subject risk and the ML risk tier can disagree.** They measure different things — one is a
    rule over the assessment series, the other a trained classifier over student features. Both
    are shown, each labelled with its method.

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

---

## 21. Question bank, practice and the learning-state loop

This section documents the extension added on top of the original prediction → explanation →
graph → recommendation pipeline.

### 21.1 The loop

```
weak concept
   -> root-cause propagation over the prerequisite DAG
   -> recommended study material  (app/practice/selector.py + resources table)
   -> recommended questions       (count and difficulty derived, not fixed)
   -> student practice            (POST /api/practice/start)
   -> grading                     (app/practice/scoring.py)
   -> learning-state update       (app/practice/mastery_update.py -> concept_mastery)
   -> root-cause recalculation    (re-run inside the same request)
```

`POST /api/practice/submit` performs the last four steps and returns the mastery delta and the
recomputed diagnosis. The frontend renders that payload and derives nothing.

### 21.2 Database changes

Six additive tables, every statement `CREATE TABLE IF NOT EXISTS`, applied by `db.init_db()` via
`practice_db.init_content_schema()`. No existing table is altered and no existing row is touched.

| Table | Purpose |
|---|---|
| `questions` | bank items; `concept` holds a knowledge-graph id, `options` is JSON, `is_active` supports soft delete |
| `resources` | study material per concept, with type, difficulty and estimated minutes |
| `sample_papers` | paper metadata, including `is_demo` |
| `sample_paper_files` | PDF bytes, separated so listing papers never drags blobs through the row factory |
| `practice_sessions` | one row per started session; `served_questions` pins which items were issued |
| `practice_attempts` | one row per graded answer; `concept` and `difficulty` are denormalised so teacher edits cannot rewrite history |
| `mastery_history` | audit trail of every learning-state change with the inputs that produced it |

`init_db()` also sets `PRAGMA journal_mode = WAL`. Submitting a session writes attempts, mastery
rows and history in one request; WAL lets readers continue during those writes.

Two behavioural notes on existing structures: `MasteryRecord.source` gained a fourth value,
`practice`, and `concept_mastery` is written through the existing `db.set_mastery` so the provenance
label the UI already renders stays truthful (a student with both simulated and practice-derived
concepts reports `mixed`).

### 21.3 Recommendation logic

No new ranking was introduced. `app.recommendations.engine.score_concepts` already orders concepts by

```
0.45 * root-cause evidence + 0.30 * mastery gap
+ 0.15 * downstream impact + 0.10 * predicted risk
```

`app/practice/selector.py` consumes that ordering and decides only *how much and how hard*:

* **question count** scales linearly between `MIN_QUESTIONS` (5) and `MAX_QUESTIONS` (15) by the
  concept's priority relative to the top-ranked concept;
* **difficulty** comes from current mastery — Easy below 40%, Hard above 65%, Medium between;
* **reason** (the explainable-AI requirement) is generated from graph facts: the mastery figure, the
  target, whether backward propagation flagged the concept as a root cause, and how many descendants
  depend on it.

Nothing is per-student hardcoded. `test_recommendations_differ_between_students` asserts that two
demo students receive different concept/count/difficulty signatures.

### 21.4 Practice scoring

| Type | Grading |
|---|---|
| MCQ | exact match on the option key, or on the option text if the client posts that instead |
| Numerical | float comparison within a per-question `tolerance`, defaulting to relative 1%; accepts `3,14`, `3.14e0` and simple fractions |
| Theory | **not auto-graded** — the student self-marks against the model answer; stored as `graded_by='self'` |

No partial credit: a wrong answer scores zero out of the question's `marks`.

### 21.5 Learning-state update

```
weighted_accuracy = sum(w_d * correct) / sum(w_d)          w = {Easy 0.7, Medium 1.0, Hard 1.4}
alpha_eff         = ALPHA * min(1, n_graded / N_REF)       ALPHA = 0.30, N_REF = 8
new               = (1 - alpha_eff) * old + alpha_eff * weighted_accuracy * 100
```

Clamped to `[0, 100]` and to ±`MAX_DELTA_PER_SESSION` (15 points). Every change is written to
`mastery_history` with `previous`, `updated`, `practice_score`, `alpha_effective`, `n_attempts` and
the session id, so any mastery figure in the system can be recomputed by hand.

The damping term is the point. A plain `0.7*old + 0.3*accuracy` blend lets three lucky MCQs move
mastery by twenty points, which would let a student swing their own root-cause diagnosis by
answering a handful of easy items. Difficulty weighting exists for the same reason: a correct Hard
answer is stronger evidence than a correct Easy one.

**Mastery is not an ML input.** `StudentFeatures` contains no mastery fields, so this update cannot
change predicted GPA, pass probability, risk tier or any SHAP value. It feeds the prerequisite
graph, root-cause analysis, recommendations, the weekly plan and the cognitive twin. This is
asserted by `test_practice_does_not_change_the_prediction_or_shap`. It is also why the submit
response says so explicitly to the student: practising raises the learning-state estimate, not the
prediction.

Every constant above is overridable from the environment and is returned verbatim by
`GET /api/practice/config`.

### 21.6 New frontend routes

| Route | Page |
|---|---|
| `/app/practice` | recommended practice, free practice, question runner, results |
| `/app/practice-history` | concept statistics, mastery trajectory, session log |
| `/app/resources` | AI-recommended materials with reasons, plus the full library |
| `/app/sample-papers` | papers grouped by subject, authenticated view/download |
| `/teacher` | cohort overview (unchanged, now the index route) |
| `/teacher/questions` | question bank CRUD |
| `/teacher/resources` | study material CRUD |
| `/teacher/sample-papers` | PDF upload and management |
| `/teacher/practice-analytics` | cohort practice aggregates |

`TeacherDashboard.jsx` became a nested-route layout to host the new teacher pages; the cohort view
moved verbatim to `pages/teacher/Cohort.jsx`.

**Router ordering matters in `main.py`.** The SPA fallback registers `GET /{full_path:path}`.
FastAPI matches in registration order, so a router included below it would be shadowed and every new
GET would silently return `index.html` instead of JSON. New routers go in the `include_router` block
above it.

### 21.7 Seed data

`python -m app.database.seed_content` inserts 42 questions across 14 concepts (MCQ, Numerical and
Theory, at all three difficulties), 23 resources linking to freely available material (MIT
OpenCourseWare, Khan Academy, 3Blue1Brown, Paul's Online Notes), and 4 demo sample papers.

The demo PDFs are **generated at seed time** by a small hand-rolled writer in `seed_content.py`
rather than committed as binaries or produced with reportlab, which would add a build dependency for
four placeholder files. Every one of them is stored with `is_demo=1`, contains a disclaimer in its
body text, and is labelled as a placeholder in both the API response and the UI. They are not
official or previous-year university papers.

## 22. Deployment

`render.yaml` now captures the build and start commands in version control; previously they existed
only in the Render dashboard. Reconcile it against your dashboard before switching the service to
blueprint mode.

```yaml
buildCommand: |
  cd frontend && npm ci && npm run build
  cd ../backend && pip install -r requirements.txt
  python -m app.ml.train
  python -m app.database.seed
  python -m app.database.seed_content
startCommand: cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
healthCheckPath: /api/health
```

`python -m app.database.seed_content` must run **unconditionally**. A build step that guards seeding
with `[ -f cognipath.db ] || seed` will skip the question bank entirely on an instance whose
database already exists. The content seeder is independently idempotent, so running it every deploy
is safe.

No new backend dependencies were added — `python-multipart` was already present for form parsing.
One frontend devDependency was added: `@testing-library/user-event`.

### Environment variables

| Variable | Default | Notes |
|---|---|---|
| `COGNIPATH_SECRET` | dev placeholder | **Required in any deployment.** The app logs a warning when the fallback is used |
| `COGNIPATH_DB` | `backend/cognipath.db` | point at a persistent mount if you attach a disk |
| `COGNIPATH_MODELS` | `backend/models/cognipath_models.joblib` | |
| `COGNIPATH_TOKEN_MINUTES` | `480` | JWT lifetime |
| `COGNIPATH_DEMO_SIZE` | `60` | demo cohort size |
| `COGNIPATH_CORS` | localhost origins | comma-separated |
| `COGNIPATH_MASTERY_ALPHA` | `0.30` | learning-state blend weight |
| `COGNIPATH_MASTERY_N_REF` | `8` | attempts before alpha saturates |
| `COGNIPATH_MAX_MASTERY_DELTA` | `15` | per-session mastery cap, in points |
| `COGNIPATH_INCLUDE_SELF_GRADED` | `0` | count self-marked Theory answers toward mastery |
| `COGNIPATH_W_EASY` / `_MEDIUM` / `_HARD` | `0.7` / `1.0` / `1.4` | difficulty weights |
| `COGNIPATH_MIN_QUESTIONS` / `_MAX_QUESTIONS` | `5` / `15` | recommended session size bounds |
| `COGNIPATH_EASY_BELOW` / `_HARD_ABOVE` | `40` / `65` | difficulty band thresholds |
| `COGNIPATH_MAX_PDF_BYTES` | `10485760` | sample-paper upload cap |

### Persistence warning

Render's filesystem is ephemeral. `.gitignore` excludes `*.db` and `models/*.joblib`, so both are
rebuilt at build time. Consequences without a persistent disk:

* demo students, questions, resources and demo papers are recreated by the build step, so the
  application still works after a redeploy;
* **teacher-uploaded PDFs, student practice attempts and mastery history are lost.**

To keep them, attach a Render disk and point `COGNIPATH_DB` at the mount. Note that a disk forces a
single instance, disables zero-downtime deploys, and is unavailable on the free plan. The teacher
sample-papers page states this limitation in the UI rather than letting staff discover it after a
deploy.
