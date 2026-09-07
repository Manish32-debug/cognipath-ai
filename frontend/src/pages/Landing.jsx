import { Link } from 'react-router-dom'
import { useApi } from '../hooks/useApi.js'
import { endpoints } from '../services/api.js'
import { Card } from '../components/Card.jsx'
import { num } from '../utils/format.js'

const PIPELINE = [
  ['1. Predict', 'Trained regression + classification models estimate GPA, pass probability and academic risk.'],
  ['2. Explain', 'SHAP decomposes each prediction into per-feature contributions.'],
  ['3. Diagnose', 'A prerequisite knowledge graph traces weak concepts back to likely upstream gaps.'],
  ['4. Recommend', 'Concepts are prioritised by root-cause evidence, mastery gap and downstream impact.'],
  ['5. Personalise', 'A weekly plan and a Cognitive Digital Twin adapt to the student\u2019s own data.'],
]

const FEATURES = [
  ['Explainable by construction', 'No prediction is shown without its SHAP decomposition. Positive and negative contributors are separated so a student can see what is helping and what is hurting.'],
  ['Root cause, not symptom', 'Backward traversal over a prerequisite DAG. A weak concept whose own prerequisites are strong is flagged as the start of the weak chain; a mid-chain concept is not.'],
  ['Honest about its data', 'The dataset has no per-concept assessments, so demo mastery scores are clearly labelled as simulated. Real scores can be entered or imported.'],
  ['Teacher-side triage', 'Cohort risk distribution, concept weakness ranking, and drill-down into any student\u2019s full explanation and plan.'],
]

export default function Landing() {
  const { data: health } = useApi(() => endpoints.health(), [])
  const { data: evaluation } = useApi(() => endpoints.evaluation(), [])
  const gpa = evaluation?.tasks?.gpa_regression
  const pass = evaluation?.tasks?.pass_classification

  return (
    <div>
      <div className="container">
        <header className="between" style={{ padding: '1.4rem 0' }}>
          <div className="brand">
            <span className="brand-mark">CP</span>
            CogniPath<span style={{ color: 'var(--brand-2)' }}> AI</span>
          </div>
          <div className="row">
            <a className="btn btn-sm btn-ghost" href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">API docs</a>
            <Link className="btn btn-sm btn-primary" to="/login">Get started</Link>
          </div>
        </header>

        <section className="hero">
          <div className="eyebrow">
            <span className="spinner" style={{ width: 8, height: 8, borderWidth: 1, animation: 'none', background: health ? 'var(--good)' : 'var(--warn)', borderColor: 'transparent' }} />
            {health ? `API online \u00B7 models ${health.models}` : 'Connecting to API...'}
          </div>
          <h1>
            Understand performance.<br />
            <span className="gradient-text">Discover root causes. Learn smarter.</span>
          </h1>
          <p className="lead">
            CogniPath AI predicts academic performance from real academic and behavioural
            indicators, explains every prediction with SHAP, traces weak concepts back through a
            prerequisite knowledge graph to their probable origin, and turns that diagnosis into a
            prioritised weekly study plan.
          </p>
          <div className="row wrap">
            <Link className="btn btn-primary" to="/login">Open the dashboard</Link>
            <a className="btn" href="#pipeline">See how it works</a>
          </div>
        </section>

        <section className="section" id="pipeline">
          <h2>Student &rarr; Prediction &rarr; Explanation &rarr; Root cause &rarr; Recommendation</h2>
          <p>Each stage is a real component, not a mock-up. The demo cohort runs the same pipeline as any new student.</p>
          <div className="pipeline">
            {PIPELINE.map(([title, body]) => (
              <div key={title} className="pipeline-step">
                <strong className="small">{title}</strong>
                <p className="tiny" style={{ marginTop: '.4rem', marginBottom: 0 }}>{body}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="section">
          <h2>What makes it different</h2>
          <div className="grid grid-2" style={{ marginTop: '1.2rem' }}>
            {FEATURES.map(([title, body]) => (
              <Card key={title} title={title}><p className="small" style={{ margin: 0 }}>{body}</p></Card>
            ))}
          </div>
        </section>

        <section className="section">
          <h2>Measured performance</h2>
          <p>Held-out test metrics written by the training pipeline, loaded live from the API.</p>
          <div className="grid grid-3">
            <Card title="GPA regression" subtitle={gpa?.selected_model || 'loading...'}>
              <div className="small mono">
                MAE {gpa ? num(gpa.test_metrics.mae, 3) : '-'}<br />
                RMSE {gpa ? num(gpa.test_metrics.rmse, 3) : '-'}<br />
                R&sup2; {gpa ? num(gpa.test_metrics.r2, 3) : '-'}
              </div>
            </Card>
            <Card title="Pass classification" subtitle={pass?.selected_model || 'loading...'}>
              <div className="small mono">
                Accuracy {pass ? num(pass.test_metrics.accuracy, 3) : '-'}<br />
                F1 {pass ? num(pass.test_metrics.f1, 3) : '-'}<br />
                ROC-AUC {pass ? num(pass.test_metrics.roc_auc, 3) : '-'}
              </div>
            </Card>
            <Card title="Dataset" subtitle="UCI Student Performance (Cortez &amp; Silva, 2008)">
              <div className="small mono">
                {evaluation ? `${evaluation.data_profile.n_rows} records` : '-'}<br />
                {evaluation ? `${evaluation.n_train} train / ${evaluation.n_test} test` : '-'}<br />
                {evaluation ? `${evaluation.data_profile.missing_values} missing values` : '-'}
              </div>
            </Card>
          </div>
        </section>

        <section className="section">
          <h2>Technology</h2>
          <div className="row wrap">
            {['React', 'Vite', 'React Router', 'Recharts', 'Axios', 'FastAPI', 'Pydantic v2',
              'scikit-learn', 'SHAP', 'NetworkX', 'pandas', 'NumPy', 'SQLite', 'JWT + PBKDF2', 'pytest']
              .map((t) => <span key={t} className="chip">{t}</span>)}
          </div>
          <div className="notice" style={{ marginTop: '1.4rem' }}>
            <b>Responsible use.</b> CogniPath AI produces statistical estimates to prompt human
            review. It does not decide outcomes, and its root-cause output is diagnostic inference
            over a curriculum model &mdash; not proven causality.
          </div>
        </section>

        <footer className="section center tiny muted">
          CogniPath AI &middot; academic project prototype &middot; explainable learning analytics
        </footer>
      </div>
    </div>
  )
}
