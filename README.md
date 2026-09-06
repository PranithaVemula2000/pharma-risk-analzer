# Pharma Shipment Risk Analyzer

A small Streamlit application following the supplied `CLAUDE.md` requirements.

## Files
- `app.py` — Streamlit UI only.
- `risk_analyzer.py` — pure profiling, detection, scoring and recommendation functions.
- `requirements.txt` — dependencies.

## Run
```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Upload a synthetic/sanitized `.xlsx` workbook. The app inspects sheets, columns, dtypes and missing values before scoring.

Important: the supplied exercise specification requires inspecting the actual workbook before finalizing the risk methodology. This implementation therefore detects signals dynamically and exposes assumptions in the UI rather than hard-coding a sample dataset.
