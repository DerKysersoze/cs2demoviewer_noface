import { create } from 'zustand'

// Holds the currently-viewed demo's parsed data.
// Populated when /viewer/:id loads from GET /api/demos/:id.
// Replaces the old sessionStorage handoff from index.html.
export const useDemoStore = create((set) => ({
  demo:    null,   // full API response for the active demo
  demoId:  null,
  setDemo: (id, data) => set({ demoId: id, demo: data }),
  clear:   ()         => set({ demoId: null, demo: null }),
}))
