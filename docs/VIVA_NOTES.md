# Viva notes — CogniPath AI

Short, defensible answers to the questions an examiner actually asks.

---

## Design justifications

**Why Random Forest for GPA?**
It won on cross-validated R² (0.875 vs 0.814 for the best linear model) on the training split, and
it gets *exact* TreeSHAP — so choosing it costs nothing in explainability. Linear models were
included precisely so the comparison is honest; with 316 training rows a large ensemble is not a
foregone conclusion.

**Why Logistic Regression for pass probability?**
It had the best CV ROC-AUC (0.972) and gives calibrated-by-construction probabilities plus exact
LinearSHAP in log-odds. When the simplest model wins, you take it.

**Why three separate models instead of one?**
They answer different questions and get different loss functions. GPA is a magnitude (regression,
MAE/RMSE), pass is a decision boundary at 10/20 (needs a probability, ROC-AUC), risk is an
ordered band (macro-F1 so the minority tier is not ignored). Thresholding one regressor would
throw away the probability calibration the pass model provides.

**Why SHAP rather than feature_importances_?**
`feature_importances_` is global and model-wide — it tells you what matters across the dataset, not
why *this* student got *this* prediction. SHAP is local, additive (base + Σφ = output, which the
test suite asserts), and works uniformly across the tree and linear models used here.

**Why NetworkX?**
The prerequisite structure is a DAG, and the algorithm needs ancestors, descendants, shortest paths
and an acyclicity check. NetworkX gives all four; a graph database would add infrastructure for a
14-node graph that fits in memory. The graph is cached with `lru_cache`.

**Why FastAPI?**
Pydantic v2 validation at the boundary (an out-of-range grade is rejected before it reaches a
model), automatic OpenAPI docs at `/docs` for the demo, and native async. Type hints double as the
schema.

**Why React + Vite?**
Component reuse across the two dashboards (the teacher drill-down reuses the student panels
verbatim), and Vite gives instant HMR plus a dev proxy that removes CORS friction.

**Why SQLite?**
Four tables, single-writer academic prototype, zero-configuration file database that ships with
Python. Postgres would add a service with no benefit at this scale. The repository layer in
`database/db.py` is the only place SQL lives, so swapping it is contained.

**Why a hand-written SVG graph instead of a graph library?**
The meaning of this graph *is* its layering — prerequisites left, dependents right. A
force-directed layout would randomise exactly the property the user needs to read. Node x-position
comes from the backend's topological level.

**Why a rule-based recommender?**
A learned recommender needs interaction data (opens, dwell time, subsequent scores). We have none.
A model fitted to nothing is a black box pretending to be intelligence. The rules are transparent
and `score_concepts()` is the single seam where a learned ranker plugs in later.

---

## Mechanism questions

**How is risk calculated?**
Two layers. Training labels come from documented `G3` bands (High < 10, Medium 10–13, Low ≥ 14).
At inference a RandomForestClassifier predicts the tier and returns per-class probabilities. It is
*not* thresholded from the GPA regressor.

**How does root-cause propagation work?**
Four steps: (1) mastery gap relative to the 70% target; (2) downstream pressure — sum over weak
descendants of their gap × path strength × 0.6^(hops−1); (3) upstream clearance — 1 minus the
worst gap among the concept's own prerequisites, so a mid-chain concept gets damped when its own
foundations are weak; (4) score = gap × (1 + 1.2 × downstream) × clearance. Rank descending.
The clearance term is the part that makes it point *upstream* rather than at the loudest symptom.

**Prove it doesn't just pick the lowest mastery.**
Functions 90, Limits 45, Differentiation 30, Integration 48, DE 35 → ranking is Limits 0.886,
Differentiation 0.854, DE 0.417. Limits (45%) outranks DE (35%) because Limits has more weak
concepts beneath it and nothing weak above it. A test asserts this ordering.

**How are recommendations prioritised?**
`0.45 × root-cause score + 0.30 × mastery gap + 0.15 × downstream fan-out + 0.10 × risk boost`.
The first two are normalised to [0,1] so the weights mean what they say. Root-cause evidence
carries the largest weight by design — that is the project's thesis.

**How do you avoid data leakage?**
The `ColumnTransformer` is fitted on the training split only; the test split is transformed with
the already-fitted object. Model selection uses cross-validation *inside* the training split; the
test split is scored exactly once, at the end. At serving time, missing optional inputs fall back
to **training** medians and modes stored in the joblib bundle.

**Why is R² 0.897 — is that too good?**
G1 and G2 are the same subject's earlier grades, so they are near-deterministic predictors of G3.
This is a documented property of the dataset, not a bug and not leakage — those columns are
genuinely available before the final exam. It does mean the system is an *early-warning tool for
students who already have assessment history*, not a cold-start predictor. Say this before the
examiner does.

**Where does concept mastery come from?**
It is not in the dataset — the dataset has period grades, not per-concept scores. Real students
enter it or it is imported from assessments. For the demo cohort it is simulated by a documented
process anchored to each student's real record, stored with `source='simulated'`, and the UI shows
a warning banner. This is the single most important honesty point in the project.

**Is the Cognitive Twin psychology?**
No. Five indices computed from behavioural columns, each returned with `status: "Estimated"` and
the exact inputs it came from. Learning style is deliberately *not* inferred — nothing here could
support it, and the learning-styles hypothesis is weakly supported in the literature anyway.

**What stops a student from reading another student's data?**
The JWT carries `role` and `student_id`; `authorise_student()` runs on every student-scoped route
and teacher-only routes depend on `require_teacher`. The React guard is convenience only — remove
it and the API still returns 403. Two tests assert this.

---

## Two-minute demo script

1. Landing page — live test metrics fetched from `/api/evaluation`.
2. Sign in as `demo001`. Overview: predicted GPA, pass probability, risk tier, overall mastery.
3. **Explainability** — switch task to "Why this risk tier?", show helping vs hurting factors.
4. **Concept mastery** — click a node in the prerequisite graph; note the simulated-data banner.
5. **Root cause** — show that the top result is upstream of the weakest concept, with its path.
6. **Recommendations → Study plan** — root-cause concept scheduled on Monday.
7. **Settings** — drop G2, save; the whole pipeline re-runs and the risk tier changes.
8. Sign in as `teacher` — risk distribution, weakest concepts, filter to High risk, drill into a
   student and show the same explanation from the teacher's side.

## Numbers worth memorising

395 records, 0 missing, 316/79 split, 28 encoded features, 14 concepts, 20 edges.
GPA: MAE 0.455, R² 0.897. Pass: F1 0.951, ROC-AUC 0.993. Risk: acc 0.835, macro-F1 0.826.
47 backend tests, 12 frontend tests.
