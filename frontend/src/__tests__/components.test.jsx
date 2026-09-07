import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import PredictionCard from '../components/PredictionCard.jsx'
import RootCausePanel from '../components/RootCausePanel.jsx'
import RecommendationCard from '../components/RecommendationCard.jsx'
import StudyPlan from '../components/StudyPlan.jsx'
import ConceptMastery from '../components/ConceptMastery.jsx'
import { ErrorState } from '../components/Loader.jsx'

const prediction = {
  predicted_gpa: 4.29, predicted_g3_equivalent: 8.59, pass_probability: 0.125,
  risk_tier: 'High', risk_probabilities: { High: 0.77, Medium: 0.22, Low: 0.01 },
  models_used: { gpa: 'RandomForestRegressor', pass: 'LogisticRegression', risk: 'RandomForestClassifier' },
  interpretation: 'Model estimates a GPA of 4.29/10.',
}

describe('PredictionCard', () => {
  it('renders model output and names the models used', () => {
    render(<PredictionCard prediction={prediction} />)
    expect(screen.getByText('4.29')).toBeInTheDocument()
    expect(screen.getByText('12.5%')).toBeInTheDocument()
    expect(screen.getByText('High risk')).toBeInTheDocument()
    expect(screen.getByText(/RandomForestRegressor/)).toBeInTheDocument()
  })
})

describe('RootCausePanel', () => {
  const analysis = {
    weak_concepts: [{ concept: 'differentiation', label: 'Differentiation', mastery: 30, risk: 'High' }],
    root_causes: [{
      concept: 'limits', label: 'Limits', mastery: 45, risk: 'Medium', root_score: 0.88,
      own_gap: 0.36, downstream_pressure: 1.2, upstream_clearance: 1,
      blocking_prerequisites: [],
      affected_concepts: [{ concept: 'differentiation', label: 'Differentiation', mastery: 30, distance: 1, contribution: 0.5, path: ['limits', 'differentiation'], path_labels: ['Limits', 'Differentiation'] }],
      reasoning: 'Limits mastery is 45%.',
    }],
    disclaimer: 'Diagnostic inference, not proven causality.',
  }

  it('labels the top result as a likely root cause and shows the reasoning path', () => {
    render(<RootCausePanel analysis={analysis} />)
    expect(screen.getByText(/#1 likely root cause/)).toBeInTheDocument()
    expect(screen.getByText(/Limits\s+→\s+Differentiation/)).toBeInTheDocument()
    expect(screen.getByText(/not proven causality/)).toBeInTheDocument()
  })

  it('handles a student with no weak concepts', () => {
    render(<RootCausePanel analysis={{ weak_concepts: [], root_causes: [] }} />)
    expect(screen.getByText(/No concept is below/)).toBeInTheDocument()
  })
})

describe('RecommendationCard', () => {
  it('shows priority order and flags root-cause items', () => {
    render(<RecommendationCard recommendations={{
      items: [{
        concept: 'limits', label: 'Limits', mastery: 45, risk: 'Medium', priority: 1,
        priority_score: 0.7, is_root_cause: true, reason: 'Likely root-cause prerequisite gap',
        action: 'Concept revision', estimated_minutes: 80,
        resources: [{ type: 'video', title: 'Limits video', url: 'https://example.org/x', minutes: 20 }],
      }],
      scoring: { root_cause_weight: 0.45, gap_weight: 0.3, downstream_weight: 0.15, risk_weight: 0.1 },
    }} />)
    expect(screen.getByText('Priority 1: Limits')).toBeInTheDocument()
    expect(screen.getByText('root cause')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Limits video/ })).toHaveAttribute('href', 'https://example.org/x')
  })

  it('shows the empty message when nothing needs work', () => {
    render(<RecommendationCard recommendations={{ items: [], message: 'All concepts above target.' }} />)
    expect(screen.getByText('All concepts above target.')).toBeInTheDocument()
  })
})

describe('StudyPlan', () => {
  it('renders all seven days', () => {
    render(<StudyPlan plan={{
      weekly_minutes: 240,
      budget_inputs: { studytime: 2, freetime: 3, risk_tier: 'High' },
      days: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        .map((day, i) => ({ day, sessions: i === 0 ? [{ concept: 'limits', label: 'Limits', minutes: 45, focus: 'Limits - concept revision', is_root_cause: true, resource: null }] : [] })),
    }} />)
    expect(screen.getByText('Monday')).toBeInTheDocument()
    expect(screen.getByText('Sunday')).toBeInTheDocument()
    expect(screen.getByText('Limits - concept revision')).toBeInTheDocument()
  })
})

describe('ConceptMastery', () => {
  it('warns clearly when the mastery data is simulated', () => {
    render(<ConceptMastery source="simulated" concepts={[
      { concept: 'limits', label: 'Limits', mastery: 45, risk: 'Medium' },
    ]} />)
    expect(screen.getByText(/simulated demo data/)).toBeInTheDocument()
    expect(screen.getByText('45%')).toBeInTheDocument()
  })
})

describe('ErrorState', () => {
  it('shows the API error message instead of crashing', () => {
    render(<ErrorState message="Cannot reach the API." />)
    expect(screen.getByText('Cannot reach the API.')).toBeInTheDocument()
  })
})
