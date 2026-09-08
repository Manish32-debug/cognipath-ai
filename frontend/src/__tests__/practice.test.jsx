import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../services/api.js', () => ({
  TOKEN_KEY: 'cognipath_token',
  endpoints: {
    recommendedPractice: vi.fn(),
    bankSummary: vi.fn(),
    startPractice: vi.fn(),
    submitPractice: vi.fn(),
    practicePerformance: vi.fn(),
    practiceHistory: vi.fn(),
    recommendedResources: vi.fn(),
    resources: vi.fn(),
    samplePapers: vi.fn(),
    samplePaperBlob: vi.fn(),
  },
  default: {},
}))

const { endpoints } = await import('../services/api.js')
const Practice = (await import('../pages/student/Practice.jsx')).default
const Resources = (await import('../pages/student/Resources.jsx')).default
const SamplePapers = (await import('../pages/student/SamplePapers.jsx')).default
const PracticeHistory = (await import('../pages/student/PracticeHistory.jsx')).default

/** Renders a student page with the outlet context the dashboard shell provides. */
function renderPage(Component, context = { studentId: 'DEMO001', reload: vi.fn() }) {
  return render(
    <MemoryRouter>
      <Routes>
        <Route path="/" element={<Component />} />
      </Routes>
    </MemoryRouter>,
  )
}

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useOutletContext: () => ({ studentId: 'DEMO001', reload: vi.fn() }) }
})

const RECOMMENDED = {
  student_id: 'DEMO001',
  items: [{
    concept: 'differentiation', label: 'Differentiation', mastery: 43.2, risk: 'Medium',
    is_root_cause: true, priority: 1, priority_score: 0.61,
    recommended_questions: 10, available_questions: 10, difficulty: 'Medium',
    questions_in_bank: 12, downstream_concepts: 5,
    reason: 'Differentiation is at 43% mastery against a 70% target. Backward propagation identifies it as a likely root cause.',
    resources: [{
      resource_id: 6, title: 'Differentiation Fundamentals', resource_type: 'Notes',
      difficulty: 'Easy', estimated_minutes: 20, url: 'https://example.org/notes',
      description: 'Definition of the derivative.',
    }],
  }],
  message: null,
}

const BANK = {
  total_questions: 42,
  concepts: [{ concept: 'differentiation', label: 'Differentiation', subject: 'Calculus', total: 12, by_difficulty: { Easy: 4 } }],
}

beforeEach(() => {
  vi.clearAllMocks()
  endpoints.bankSummary.mockResolvedValue(BANK)
})

describe('Practice page', () => {
  it('shows the recommendation with its reason and the derived question count', async () => {
    endpoints.recommendedPractice.mockResolvedValue(RECOMMENDED)
    renderPage(Practice)

    expect(await screen.findByText(/Priority 1: Differentiation/)).toBeInTheDocument()
    expect(screen.getByText('root cause')).toBeInTheDocument()
    // '43% mastery' appears both as the badge and inside the reason sentence.
    expect(screen.getAllByText(/43% mastery/).length).toBeGreaterThan(0)
    expect(screen.getByText(/likely root cause/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Practice 10 questions/ })).toBeInTheDocument()
    expect(screen.getByText(/Differentiation Fundamentals/)).toBeInTheDocument()
  })

  it('renders an empty state rather than inventing practice', async () => {
    endpoints.recommendedPractice.mockResolvedValue({
      items: [], message: 'No concept is below the 70% mastery target - practice is optional right now.',
    })
    renderPage(Practice)
    expect(await screen.findByText('Nothing flagged for practice')).toBeInTheDocument()
  })

  it('surfaces API errors instead of failing silently', async () => {
    endpoints.recommendedPractice.mockRejectedValue(new Error('Cannot reach the API.'))
    renderPage(Practice)
    expect(await screen.findByText('Something went wrong')).toBeInTheDocument()
    expect(screen.getByText('Cannot reach the API.')).toBeInTheDocument()
  })

  it('serves questions without leaking answers and submits what the student picked', async () => {
    const user = userEvent.setup()
    endpoints.recommendedPractice.mockResolvedValue(RECOMMENDED)
    endpoints.startPractice.mockResolvedValue({
      session_id: 7, concept: 'differentiation', label: 'Differentiation', difficulty: 'Medium',
      requested: 10, served: 1,
      questions: [{
        question_id: 101, subject: 'Calculus', concept: 'differentiation', difficulty: 'Easy',
        question_type: 'MCQ', question_text: 'What is d/dx of x^3?', marks: 1,
        options: [{ key: 'A', text: '3x' }, { key: 'B', text: '3x^2' }],
      }],
    })
    endpoints.submitPractice.mockResolvedValue({
      session_id: 7,
      summary: {
        total_questions: 1, correct: 1, incorrect: 0, score: 1, max_score: 1,
        accuracy: 100, time_taken_seconds: 12,
        concept_performance: [{ concept: 'differentiation', attempted: 1, correct: 1, accuracy: 100 }],
      },
      results: [{
        question_id: 101, concept: 'differentiation', label: 'Differentiation', difficulty: 'Easy',
        question_type: 'MCQ', question_text: 'What is d/dx of x^3?', your_answer: 'B',
        correct_answer: 'B', is_correct: true, graded_by: 'auto',
        explanation: 'The power rule.', score: 1, max_score: 1,
      }],
      mastery_update: {
        changes: [{ concept: 'differentiation', previous: 43.2, updated: 45.1, delta: 1.9, alpha_effective: 0.0375, graded_attempts: 1 }],
        config: { formula: 'new = (1 - alpha_eff) * old + alpha_eff * weighted_accuracy' },
        note: 'Mastery here is an application-maintained learning-state estimate.',
      },
      root_cause: { before: [], after: [], changed: false, current: [{ concept: 'limits', label: 'Limits', mastery: 40 }] },
    })

    renderPage(Practice)
    await user.click(await screen.findByRole('button', { name: /Practice 10 questions/ }))

    expect(await screen.findByText('What is d/dx of x^3?')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /3x\^2/ }))
    await user.click(screen.getByRole('button', { name: /Submit answers/ }))

    await waitFor(() => expect(endpoints.submitPractice).toHaveBeenCalled())
    const payload = endpoints.submitPractice.mock.calls[0][0]
    expect(payload.session_id).toBe(7)
    expect(payload.answers).toEqual([
      expect.objectContaining({ question_id: 101, selected_answer: 'B' }),
    ])

    expect(await screen.findByText('100')).toBeInTheDocument()
    expect(screen.getByText(/43.2% →/)).toBeInTheDocument()
    expect(screen.getByText('The power rule.')).toBeInTheDocument()
  })
})

describe('Resources page', () => {
  it('explains why each recommended resource was selected', async () => {
    endpoints.recommendedResources.mockResolvedValue({
      student_id: 'DEMO001',
      items: [{
        concept: 'differentiation', label: 'Differentiation', mastery: 43, is_root_cause: true,
        priority: 1, reason: 'Root cause affecting five downstream concepts.',
        estimated_minutes: 20,
        practice: { recommended_questions: 10, available_questions: 10, difficulty: 'Medium' },
        resources: [{
          resource_id: 6, title: 'Differentiation Fundamentals', resource_type: 'Notes',
          difficulty: 'Easy', estimated_minutes: 20, url: 'https://example.org/n', description: null,
        }],
      }],
      message: null,
    })
    endpoints.resources.mockResolvedValue({ resources: [], count: 0 })

    renderPage(Resources)
    expect(await screen.findByText('Root cause affecting five downstream concepts.')).toBeInTheDocument()
    expect(screen.getByText(/Differentiation Fundamentals/)).toBeInTheDocument()
  })
})

describe('SamplePapers page', () => {
  it('labels demo placeholders and never claims official status', async () => {
    endpoints.samplePapers.mockResolvedValue({
      count: 1,
      papers: [{ paper_id: 1, title: 'Mathematics Model Paper (Demo)', subject: 'Mathematics', is_demo: true, size_bytes: 900, difficulty: 'Medium', year: 2026 }],
      by_subject: [{
        subject: 'Mathematics',
        papers: [{ paper_id: 1, title: 'Mathematics Model Paper (Demo)', subject: 'Mathematics', is_demo: true, size_bytes: 900, difficulty: 'Medium', year: 2026, description: 'Placeholder.' }],
      }],
      note: 'Papers marked is_demo are generated placeholders. They are not official university question papers.',
    })

    renderPage(SamplePapers)
    expect(await screen.findByText(/not official university question papers/)).toBeInTheDocument()
    expect(screen.getByText('demo placeholder')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'View PDF' })).toBeInTheDocument()
  })
})

describe('PracticeHistory page', () => {
  it('reports the empty state when nothing has been attempted', async () => {
    endpoints.practicePerformance.mockResolvedValue({
      concepts: [],
      totals: { attempted: 0, correct: 0, incorrect: 0, accuracy: 0, score: 0, max_score: 0 },
      mastery_history: [],
    })
    endpoints.practiceHistory.mockResolvedValue({ sessions: [], totals: { attempted: 0 } })

    renderPage(PracticeHistory)
    expect(await screen.findByText('No practice attempts yet')).toBeInTheDocument()
  })

  it('renders concept statistics from stored attempts', async () => {
    endpoints.practicePerformance.mockResolvedValue({
      concepts: [{
        concept: 'differentiation', label: 'Differentiation', attempted: 20, correct: 13,
        incorrect: 7, accuracy: 65, current_mastery: 52, avg_time_seconds: 24,
      }],
      totals: { attempted: 20, correct: 13, incorrect: 7, accuracy: 65, score: 13, max_score: 20 },
      mastery_history: [],
    })
    endpoints.practiceHistory.mockResolvedValue({ sessions: [], totals: { attempted: 20 } })

    renderPage(PracticeHistory)
    expect(await screen.findByText('Differentiation')).toBeInTheDocument()
    expect(screen.getByText('65%')).toBeInTheDocument()
  })
})
