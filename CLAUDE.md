# Pharma Shipment Risk Analyzer

## Objective
Build a small Streamlit application that analyzes pharma supply-chain
shipments from an uploaded Excel file and identifies high-risk shipments.
Optimized for a 20-minute build — keep it small, transparent, and correct.

## Golden Rule: Inspect Before You Build
Never assume column names, data types, or thresholds. Before writing any
risk logic:
1. Load `data/pharma_shipments.xlsx` and list sheet names, columns, dtypes,
   missing-value counts, and candidate risk-signal fields.
2. Propose a risk-scoring methodology based on what actually exists in the
   data, and state assumptions explicitly.
3. Only then build the app.
If a expected signal (e.g. temperature, delay, compliance flag) is not
present in the data, say so — do not invent a column or a value.

## Required Outputs (in the UI)
1. Total shipments
2. Number of high-risk shipments
3. Temperature-excursion shipments
4. Top 5 highest-risk shipments (table)
5. Risk-distribution chart (Low / Medium / High)
6. Short, rule-based "AI-style" recommendations (3-5 bullets, deterministic
   — no external LLM calls)

## Risk Logic
- Detect temperature excursions from whichever temperature-related
  column(s) exist (e.g. min/max temp vs. an allowed range, or an explicit
  excursion flag). If no range is given in the data, use a clearly labeled
  default (e.g. 2-8°C for cold chain) and flag it as an assumption in the
  UI, not silently.
- Consider delay (e.g. actual vs. expected delivery date) and any
  quality/compliance flag columns if present.
- Build an additive, transparent risk score. Suggested starting weights
  (adapt to the real columns, state final weights in the UI):
  - Temperature excursion → +50
  - Significant delay → +25
  - Quality/compliance issue → +25
- Classify: 0-24 = Low, 25-49 = Medium, 50+ = High. Adjust thresholds only
  if the data's scale demands it, and explain why.
- The scoring formula and thresholds actually used must be visible to the
  user in the app (e.g. an expandable "How risk is calculated" section).
- Never silently drop rows. If a row can't be scored due to missing data,
  show it as "Unscored" with a reason, don't exclude it quietly.

## Data Safety
- Use only synthetic/sanitized data.
- Never process, store, or display real patient data or PII. If the sheet
  contains fields resembling patient identifiers, refuse and warn the user.
- Do not send uploaded data to any external service or API.
- Do not log raw shipment data or file contents; log only high-level
  events (e.g. "loaded 500 rows", "3 columns missing").
- All processing is local and in-memory; do not persist uploads to disk
  beyond the current session.

## Technical Stack
- Python, Streamlit, Pandas, OpenPyXL, Plotly (or native Streamlit charts)
- No external LLM/API calls — recommendations are deterministic, rule-based
- No MCP servers required for this exercise

## Architecture
- `app.py` — Streamlit UI only (upload widget, layout, charts, tables).
  No risk-scoring logic here.
- `risk_analyzer.py` — pure functions: dataset profiling, column detection,
  risk scoring, classification, recommendation generation. No Streamlit
  imports here — must be testable/callable outside the UI.
- Keep the split strict so risk logic can be unit-tested independently of
  the UI.

## Error Handling
- Validate the uploaded file is a readable .xlsx before processing.
- If expected columns are missing, degrade gracefully: show what was
  computed, clearly list what couldn't be computed and why.
- Surface pandas/openpyxl errors as a friendly message, not a raw
  traceback, in the UI.
- Never crash the app on malformed or partially-empty data.

## Quality Bar
- No hard-coded shipment counts, column names as magic strings scattered
  across files, or sample-data assumptions baked into logic.
- Modular, readable code; small functions with clear names.
- Any assumption made about the data or the scoring model must be visible
  to the end user, not just in code comments.

## Recommended Build Order (use these prompts in sequence)
1. **Inspect**: "Inspect the Excel dataset in `data/`. List sheet names,
   columns, dtypes, missing values, and candidate risk-signal fields. Do
   not write the application yet."
2. **Design**: "Based on the actual dataset, propose a transparent risk
   scoring methodology. Do not invent columns. Explain assumptions and
   thresholds."
3. **Build**: "Build the Streamlit app per CLAUDE.md and the approved
   methodology. Keep data processing separate from the UI."
4. **Test**: "Run the app against the supplied Excel file and fix any
   column, type, missing-value, or UI issues."

## Claude Code Components for This Exercise
| Component | Use here | Rationale |
|---|---|---|
| CLAUDE.md | Essential | Encodes pharma constraints, risk logic, safety rules |
| Streamlit | Essential | Interactive UI, fastest path to a working demo |
| Skills | Optional | A reusable "Excel risk-profiling" skill if repeating this across datasets |
| Subagents | Optional | Could split dataset profiling from risk-model design as parallel work |
| Hooks | Optional | Auto-run lint/tests after `risk_analyzer.py` edits |
| MCP | Not needed | No external system integration required |
| External LLM/API | Not needed | Recommendations are deterministic and rule-based |

For this 20-minute activity, keep to CLAUDE.md + Streamlit as the core.
Mention Skills/Subagents/Hooks only as the "how would this scale" answer
if asked — do not build them; scope is intentionally small.
