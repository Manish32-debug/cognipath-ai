import '@testing-library/jest-dom/vitest'

// Recharts' ResponsiveContainer measures the DOM, which jsdom does not do.
// Stubbing the observer keeps chart components renderable in tests.
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
}
