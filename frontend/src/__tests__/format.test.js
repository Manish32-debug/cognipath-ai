import { describe, expect, it } from 'vitest'
import { initials, minutes, num, pct, riskClass, riskColor } from '../utils/format.js'

describe('formatting helpers', () => {
  it('maps risk tiers to distinct badge classes and colours', () => {
    expect(riskClass('High')).toContain('badge-high')
    expect(riskClass('Low')).toContain('badge-low')
    expect(new Set(['Low', 'Medium', 'High'].map(riskColor)).size).toBe(3)
  })

  it('formats probabilities and numbers', () => {
    expect(pct(0.8342, 1)).toBe('83.4%')
    expect(num(4.2949)).toBe('4.29')
  })

  it('formats durations', () => {
    expect(minutes(45)).toBe('45m')
    expect(minutes(120)).toBe('2h')
    expect(minutes(90)).toBe('1h 30m')
  })

  it('builds avatar initials safely', () => {
    expect(initials('Aarav Sharma')).toBe('AS')
    expect(initials()).toBe('CP')
  })
})
