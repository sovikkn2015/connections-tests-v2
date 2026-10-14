# V5 Design Brief — "Make it feel like a real product"

**Date:** 2026-05-02
**Problem statement:** V2/V3/V4 all feel amateurish despite having the
right content, the right wiring, and the right labels. The user's
feedback: "not getting the touch and feel", "still cluttered", "not
organized, systematic, free flowing", "still looking like an amateurish
portal."

**Root cause (diagnosed from industry research):** five specific visual
failures, not content failures.

---

## The five fixes

### Fix 1 — Surface hierarchy (the biggest single change)

**Problem:** everything is the same shade of dark. Panels don't separate
from the background. The eye sees one dark mass.

**Fix:** three distinct surface levels with visible contrast steps.

```
Surface 0 (workspace bg):  oklch(0.13 0.01 240)  ≈ #0A0F1A  (near-black navy)
Surface 1 (panel bg):      oklch(0.18 0.01 240)  ≈ #111827  (dark slate)
Surface 2 (elevated):      oklch(0.22 0.01 240)  ≈ #1A2332  (lighter slate)
```

Each step is ~5% lightness apart in OKLCH — enough to see the
separation without being distracting. The workspace background is
visibly darker than the panels sitting on it. Panels are visibly darker
than their headers. This is the Bloomberg/FactSet pattern (content
rephrased from https://www.hedgeui.com/blog/designing-dark-mode-for-trading-interfaces
and https://natural20.com/coverage/architecture-of-cognitive-efficiency-designing-ai-news-aggregators).

### Fix 2 — Spacing rhythm (4px base unit)

**Problem:** 8px everywhere = no hierarchy of spacing.

**Fix:** 4px base unit, applied as:

| Relationship | Spacing | Example |
|---|---|---|
| Within a panel (label → content) | 8px | Pane header → pane body |
| Between sibling panels in a column | 12px | Market pane → Filings pane |
| Between major sections | 20-24px | Body → trust spine |
| Page edge padding | 16px | Left/right/top of the viewport |

The body grid gap goes from 8px → 12px. The trust spine margin goes
from 8px → 20px top. The audit strip gets 0 margin (pinned). This
creates a visual rhythm where the eye can tell "these two things are
in the same group" vs "this is a new section."

### Fix 3 — Remove most borders, use surface colour instead

**Problem:** 6+ bordered rectangles = wireframe look.

**Fix:** panels separate from the workspace by surface colour difference
(Fix 1 handles this). Borders are removed from:
- Pane containers (`.pane` loses its `border`)
- Map container (`.traversal-map` loses its `border`)
- Timeline container (`.timeline` loses its `border`)

Borders are KEPT on:
- Input fields (query input, composer textarea) — interactive affordance
- The audit strip top edge — it's a pinned footer, needs a separator
- Pane headers — a subtle 1px bottom border inside the panel to
  separate the label from the content

This cuts the visible rectangle count from 6+ to 2-3. The panels
"float" on the darker workspace background instead of being boxed.

### Fix 4 — Clear visual anchor (brief pane dominance)

**Problem:** all panels compete at the same visual weight.

**Fix:** the brief pane gets:
- A slightly lighter surface than the side rails (Surface 1.5 — between
  Surface 1 and Surface 2)
- A subtle left accent border (2px brand-500) to draw the eye
- The heading inside the brief (`h2`) goes from 17px → 20px with
  font-weight 700 and -0.02em letter-spacing

The side rails (Market, Filings, Sentiment, Demand) get:
- Surface 1 background (same as the panel default)
- Slightly smaller pane headers (10px instead of 11px)
- No accent border

This creates a 60/40 visual weight split where the brief is clearly
the primary zone and the rails are supporting context.

### Fix 5 — Typography breathing room

**Problem:** heading-to-body ratio too flat (1.3x). Pane headers too
small to read as labels.

**Fix:**
- Brief h2: 20px / 700 / -0.02em (was 17px / 600 / -0.01em)
- Brief body: 13.5px / 1.6 line-height (was 13px / 1.55)
- Pane header labels: 11px / 600 / 0.08em tracking (was 0.06em) —
  slightly wider tracking makes the uppercase labels read as labels
  rather than noise
- Audit strip: 11px mono stays (it's correct for that density)
- Map node labels: 12px sans-serif at Simple level (was 12px but
  sometimes clipped)

---

## What does NOT change

- V4's content (panes, wiring, stores, hooks) — all correct
- V4's three-level map zoom (Simple / Detailed / Developer)
- V4's plain-English labels
- V4's collapsible trust spine
- V4's light/dark toggle
- V4's queue wiring fix
- V4's persona identity fix
- V4's FSI Workforce 360 brand

V5 is a **CSS-only pass** on the research terminal. If it reads right,
I'll propagate to advisor + client. If it doesn't, I've only changed
one file (the design system CSS) and can revert cleanly.

---

## Implementation plan

1. Create `frontend/src/v5/` as a thin wrapper that imports V4's
   components but overrides the CSS with a `v5-design-system.css` that
   applies the five fixes above. This way V4 stays intact as a
   fallback.
2. Route via `?v5=1`.
3. Build, test, deploy.
4. If the research terminal reads right, propagate the CSS to advisor
   + client in the same commit.

**Estimated scope:** ~200 LOC of CSS changes + a thin V5App wrapper.
No component rewrites. No new atoms. No new stores.

---

## Success criteria

Open `?persona=research&v5=1` and:
1. The brief pane is clearly the dominant element — your eye lands there
   first.
2. Panels float on a darker workspace — no wireframe rectangles.
3. The trust spine section feels like a separate zone, not crammed
   against the body.
4. The audit strip is a quiet footer, not a competing element.
5. Typography has a clear hierarchy: brief heading → brief body → pane
   labels → mono numbers.
6. The overall impression is "this looks like a real product" not "this
   looks like a developer built it."

---

*Written 2026-05-02 before any V5 code. The brief is the contract;
the code follows.*
