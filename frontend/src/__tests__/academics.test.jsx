import { render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import {
  percent, severityClass, trendArrow, trendColor,
} from '../utils/format.js'

// Fixtures copied from real API responses so the pages are tested against the
// shapes the backend actually returns.
const ACADEMICS = {
  student_id: 'DEMO004',
  subjects: [
    {
      subject_id: 'aiml', subject_name: 'Artificial Intelligence / Machine Learning',
      current: 45.4, latest: 43.1, average: 52.2, n_assessments: 6,
      trend: 'Volatile', direction: 'down', slope: -3.1, risk: 'High',
      risk_reason: 'Risk driven by recent average 45%, inconsistent scores.',
    },
    {
      subject_id: 'networks', subject_name: 'Computer Networks',
      current: 74.7, latest: 75.0, average: 73.9, n_assessments: 6,
      trend: 'Stable', direction: 'flat', slope: 0.2, risk: 'Low',
      risk_reason: 'Risk driven by recent average 75%.',
    },
  ],
  overall: {
    average_percentage: 65.0, subjects_tracked: 6,
    risk_distribution: { High: 1, Medium: 1, Low: 4 },
    strong_subjects: ['Computer Networks'], weak_subjects: ['Artificial Intelligence / Machine Learning'],
  },
  ml_prediction: {
    prediction: { predicted_gpa: 6.39, pass_probability: 0.82, risk_tier: 'Medium' },
    source: 'multi_subject_assessments',
    derived_inputs: { n_assessments: 6, earlier_average_pct: 62.7, recent_average_pct: 64.8 },
    note: 'Assessment percentages are pooled and compressed into the trained features.',
  },
  provenance: { ml: ['SHAP attributions'] },
  message: null,
}

const WARNINGS = {
  student_id: 'DEMO004', n_warnings: 1, highest_severity: 'high',
  warnings: [{
    subject_id: 'aiml', subject_name: 'Artificial Intelligence / Machine Learning',
    severity: 'high', recent_average: 45.4, trend: 'Volatile',
    series: [66, 52, 61, 44, 49, 43],
    assessment_names: ['CAT 1', 'Assignment 1', 'CAT 2', 'Midterm', 'Assignment 2', 'CAT 3'],
    triggers: [{ trigger: 'low_performance', severity: 'high', detail: 'Below the critical level.' }],
    why_at_risk: 'Recent average of 45% is below the 50% critical level.',
    likely_root_cause: {
      concept: 'linear_algebra', label: 'Linear Algebra', mastery: 53.9,
      reasoning: 'Linear Algebra mastery is 54%.', method: 'graph-based prerequisite propagation',
    },
    what_to_do_next: ['Revise Linear Algebra before moving on', 'Practise 10 questions'],
  }],
  message: null,
}

const SUBJECT_DETAIL = {
  student_id: 'DEMO004', subject_id: 'dsp',
  performance: {
    subject_id: 'dsp', subject_name: 'Digital Signal Processing',
    summary: {
      n_assessments: 6, current: 58.2, average: 55.1, recent_average: 56.7,
      best: 63.0, worst: 47.0, consistency: 78.4, delta_from_average: 3.1,
    },
    trend: {
      trend: 'Improving', direction: 'up', slope: 2.4, volatility: 4.1,
      confidence: 'high', n_points: 6,
      description: 'Gradual improvement of about +2.4 points per assessment.',
    },
    risk: {
      risk: 'Low', score: 0.28, reason: 'Risk driven by recent average 57%.',
      method: 'rule-based over the assessment series (not the ML risk classifier)',
      weights: { level: 0.55, trend: 0.3, volatility: 0.15 },
    },
    assessments: [
      { assessment_id: 1, name: 'CAT 1', type: 'cat', order: 1, marks: 23.5, max_marks: 50, percentage: 47.0, source: 'simulated' },
      { assessment_id: 2, name: 'Assignment 1', type: 'assignment', order: 2, marks: 11.0, max_marks: 20, percentage: 55.0, source: 'simulated' },
      { assessment_id: 3, name: 'CAT 3', type: 'cat', order: 6, marks: 29.1, max_marks: 50, percentage: 58.2, source: 'entered' },
    ],
  },
  ml_prediction: {
    subject_id: 'dsp',
    prediction: { predicted_gpa: 5.07, pass_probability: 0.61, risk_tier: 'Medium' },
    basis: 'The trained models applied to this subject\u2019s assessment history.',
  },
  mastery: {
    source: 'simulated', average: 55.4,
    concepts: [
      { concept: 'digital_filtering', label: 'Digital Filtering', unit: 'Filter Design', mastery: 51.7, risk: 'Medium' },
      { concept: 'fourier_transform', label: 'Fourier Transform', unit: 'Transforms', mastery: 55.1, risk: 'Medium' },
    ],
  },
  root_causes: [{
    concept: 'fourier_transform', label: 'Fourier Transform', mastery: 55.1, risk: 'Medium',
    reasoning: 'Fourier Transform mastery is 55%.',
    affected_concepts: [{ path_labels: ['Fourier Transform', 'DFT and FFT'], concept: 'dft_fft' }],
  }],
  practice_plan: {
    items: [{
      concept: 'digital_filtering', label: 'Digital Filtering', subject: 'dsp', unit: 'Filter Design',
      mastery: 51.7, risk: 'Medium', is_root_cause: false, difficulty: 'Medium',
      recommended_questions: 8, available_questions: 2, priority: 1, priority_score: 0.6,
      reason: 'Digital Filtering is below the mastery target.',
      resources: [{ resource_id: 1, title: 'FIR and IIR Filter Design' }],
    }],
    message: null,
  },
  practice_performance: { attempted: 6, correct: 4, accuracy: 0.6667 },
  context_advice: [{
    strategy: 'Conceptual revision, not more attendance',
    advice: 'Focus on conceptual revision and worked examples.',
    why: 'Attendance is 93% but recent scores average 57%.',
    actions: ['Re-derive each formula from first principles'],
    rule: 'attendance >= 85% and recent average < 60%',
  }],
  advice_rules: [{ rule: 'default', strategy: 'Maintain' }],
}

const SUBJECT_GRAPH = {
  subject: 'dsp', subject_name: 'Digital Signal Processing',
  nodes: [
    { id: 'sampling', label: 'Sampling', area: 'DSP', unit: 'Sampling Theory', subject: 'dsp', description: 'x', level: 0, prerequisites: [], dependents: ['nyquist_theorem'] },
    { id: 'nyquist_theorem', label: 'Nyquist Theorem', area: 'DSP', unit: 'Sampling Theory', subject: 'dsp', description: 'y', level: 1, prerequisites: ['sampling'], dependents: [] },
  ],
  edges: [{ source: 'sampling', target: 'nyquist_theorem', strength: 1.0 }],
  external_prerequisites: [{
    source: 'integration', source_label: 'Integration', source_subject: 'mathematics',
    target: 'fourier_transform', target_label: 'Fourier Transform', strength: 0.8,
  }],
  stats: { n_nodes: 2, n_edges: 1, max_level: 1 },
}

const ANALYTICS = {
  students_tracked: 60,
  subjects: [
    {
      subject_id: 'dsp', subject_name: 'Digital Signal Processing', students: 60,
      class_average: 53.2, lowest: 22.1, highest: 88.4,
      risk_distribution: { High: 18, Medium: 21, Low: 21 },
      trend_distribution: { Declining: 20, Improving: 25, Stable: 15 },
    },
  ],
  assessment_trends: [
    { subject_id: 'dsp', assessment: 'CAT 1', order: 1, n_results: 60, average: 55.2, min: 20, max: 90 },
    { subject_id: 'dsp', assessment: 'CAT 2', order: 3, n_results: 60, average: 52.9, min: 18, max: 92 },
  ],
  declining_students: [{
    student_id: 'DEMO004', display_name: 'Meera Iyer', subject_id: 'dsp',
    subject_name: 'Digital Signal Processing', recent_average: 41.2,
    trend: 'Strongly declining', slope: -6.2, risk: 'High',
  }],
  improving_students: [{
    student_id: 'DEMO028', display_name: 'Dev Reddy', subject_id: 'dsp',
    subject_name: 'Digital Signal Processing', recent_average: 78.4,
    trend: 'Improving', slope: 4.8, risk: 'Low',
  }],
  high_risk_students: [{
    student_id: 'DEMO017', display_name: 'Isha Nair', subject_id: 'dsp',
    subject_name: 'Digital Signal Processing', recent_average: 38.0,
    trend: 'Declining', slope: -3.0, risk: 'High',
  }],
}

vi.mock('../services/api.js', () => ({
  endpoints: {
    academics: vi.fn().mockResolvedValue(ACADEMICS),
    earlyWarnings: vi.fn().mockResolvedValue(WARNINGS),
    subjectDetail: vi.fn().mockResolvedValue(SUBJECT_DETAIL),
    subjectGraph: vi.fn().mockResolvedValue(SUBJECT_GRAPH),
    subjectAnalytics: vi.fn().mockResolvedValue(ANALYTICS),
    subjects: vi.fn().mockResolvedValue({ count: 1, subjects: [] }),
    assessments: vi.fn().mockResolvedValue({ assessments: [], assessment_types: [] }),
    recordResult: vi.fn(),
  },
}))

vi.mock('react-router-dom', async (orig) => {
  const actual = await orig()
  return { ...actual, useOutletContext: () => ({ studentId: 'DEMO004' }) }
})

const { default: Academics } = await import('../pages/student/Academics.jsx')
const { default: SubjectDetail } = await import('../pages/student/SubjectDetail.jsx')
const { SubjectAnalytics } = await import('../pages/teacher/Academics.jsx')

const renderAt = (ui, path = '/', pattern = '/') => render(
  <MemoryRouter initialEntries={[path]}>
    <Routes><Route path={pattern} element={ui} /></Routes>
  </MemoryRouter>,
)

describe('multi-subject formatting helpers', () => {
  it('maps trend direction to an arrow and a colour', () => {
    expect(trendArrow('up')).toBe('\u2191')
    expect(trendArrow('down')).toBe('\u2193')
    expect(trendArrow('flat')).toBe('\u2192')
    expect(trendColor('up')).not.toBe(trendColor('down'))
  })

  it('maps warning severity to distinct badge classes', () => {
    expect(severityClass('high')).toContain('badge-high')
    expect(severityClass('low')).toContain('badge-low')
  })

  it('formats percentages and handles missing values', () => {
    expect(percent(74.66)).toBe('75%')
    expect(percent(null)).toBe('-')
  })
})

describe('student academic overview', () => {
  it('lists every subject with its current level, trend and risk', async () => {
    renderAt(<Academics />)
    expect(await screen.findByText('Academic overview')).toBeInTheDocument()
    expect(screen.getByText('Computer Networks')).toBeInTheDocument()
    expect(screen.getAllByText('Volatile').length).toBeGreaterThan(0)
    expect(screen.getByText('Stable')).toBeInTheDocument()
    expect(screen.getAllByText('High').length).toBeGreaterThan(0)
  })

  it('shows the assessment-driven ML prediction and says where it came from', async () => {
    renderAt(<Academics />)
    expect((await screen.findAllByText('6.39')).length).toBeGreaterThan(0)
    expect(screen.getByText(/multi subject assessments/i)).toBeInTheDocument()
    expect(screen.getByText(/pooled and compressed/i)).toBeInTheDocument()
  })

  it('renders early warnings with evidence, root cause and next steps', async () => {
    renderAt(<Academics />)
    expect(await screen.findByText('Early warning')).toBeInTheDocument()
    expect(screen.getByText(/Recent average of 45%/)).toBeInTheDocument()
    expect(screen.getAllByText(/Linear Algebra/).length).toBeGreaterThan(0)
    expect(screen.getByText('Revise Linear Algebra before moving on')).toBeInTheDocument()
    expect(screen.getByText(/CAT 1: 66%/)).toBeInTheDocument()
  })
})

describe('student subject detail', () => {
  it('renders the assessment timeline and trend description', async () => {
    renderAt(<SubjectDetail />, '/app/academics/dsp', '/app/academics/:subjectId')
    expect(await screen.findByText(/assessment timeline/)).toBeInTheDocument()
    expect(screen.getByText(/Gradual improvement of about \+2.4/)).toBeInTheDocument()
    expect(screen.getByText('Assignment 1')).toBeInTheDocument()
  })

  it('labels a mark entered by a teacher separately from simulated data', async () => {
    renderAt(<SubjectDetail />, '/app/academics/dsp', '/app/academics/:subjectId')
    expect(await screen.findByText('entered')).toBeInTheDocument()
    expect(screen.getAllByText('simulated').length).toBeGreaterThan(0)
  })

  it('shows subject concept mastery, root causes and context advice', async () => {
    renderAt(<SubjectDetail />, '/app/academics/dsp', '/app/academics/:subjectId')
    expect((await screen.findAllByText('Digital Filtering')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Fourier Transform').length).toBeGreaterThan(0)
    expect(screen.getByText('Conceptual revision, not more attendance')).toBeInTheDocument()
    expect(screen.getByText(/attendance >= 85%/)).toBeInTheDocument()
  })

  it('states that subject risk is rule-based, not the ML classifier', async () => {
    renderAt(<SubjectDetail />, '/app/academics/dsp', '/app/academics/:subjectId')
    expect(await screen.findByText(/not the ML risk classifier/)).toBeInTheDocument()
  })

  it('surfaces cross-subject prerequisites from the subject graph', async () => {
    renderAt(<SubjectDetail />, '/app/academics/dsp', '/app/academics/:subjectId')
    expect(await screen.findByText(/Prerequisites from other subjects/)).toBeInTheDocument()
    expect(screen.getByText(/Integration/)).toBeInTheDocument()
  })
})

describe('teacher subject analytics', () => {
  it('renders subject averages and the mover tables', async () => {
    renderAt(<SubjectAnalytics />)
    expect(await screen.findByText('Subject performance')).toBeInTheDocument()
    expect(screen.getByText('Early warning: declining students')).toBeInTheDocument()
    expect(screen.getByText('Improving students')).toBeInTheDocument()
  })

  it('shows declining students with their slope', async () => {
    renderAt(<SubjectAnalytics />)
    const declining = await screen.findByText('Early warning: declining students')
    const card = declining.closest('section')
    expect(within(card).getByText('Meera Iyer')).toBeInTheDocument()
    expect(within(card).getByText(/-6.2 \/ assessment/)).toBeInTheDocument()
  })
})
