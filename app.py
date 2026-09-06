import io
import streamlit as st
import pandas as pd
from risk_analyzer import (
    profile_workbook, analyze_dataframe, recommendations,
    TEMP_WEIGHT, DELAY_WEIGHT, QUALITY_WEIGHT
)

st.set_page_config(page_title="Pharma Shipment Risk Analyzer", page_icon="💊", layout="wide")
st.title("💊 Pharma Shipment Risk Analyzer")
st.caption("Local, transparent, rule-based shipment risk analysis")

uploaded = st.file_uploader("Upload a synthetic/sanitized Excel workbook (.xlsx)", type=["xlsx"])

if not uploaded:
    st.info("Upload an .xlsx file to begin. No data is sent to an external service.")
    st.stop()

try:
    raw = uploaded.getvalue()
    profile = profile_workbook(io.BytesIO(raw))
except Exception:
    st.error("The workbook could not be read. Please upload a valid, readable .xlsx file.")
    st.stop()

# Basic PII guard: refuse fields that strongly resemble patient identifiers.
all_columns = [c for p in profile.sheet_profiles.values() for c in p["columns"]]
pii_patterns = ("patient name", "patient id", "patient identifier", "mrn", "medical record")
pii_hits = [c for c in all_columns if any(p in str(c).strip().lower() for p in pii_patterns)]
if pii_hits:
    st.error("Potential patient-identifying fields were detected. This app will not process the workbook.")
    st.write("Detected fields:", pii_hits)
    st.stop()

st.subheader("Dataset inspection")
st.write("Sheets:", ", ".join(profile.sheets))
for sheet, p in profile.sheet_profiles.items():
    with st.expander(f"{sheet} — {p['rows']} rows × {len(p['columns'])} columns"):
        st.write("Columns:", p["columns"])
        st.dataframe(pd.DataFrame({
            "Column": p["columns"],
            "dtype": [p["dtypes"][c] for c in p["columns"]],
            "Missing": [p["missing"][c] for c in p["columns"]],
        }), use_container_width=True)

sheet = st.selectbox("Sheet to analyze", profile.sheets)

try:
    df = pd.read_excel(io.BytesIO(raw), sheet_name=sheet, engine="openpyxl")
    result, assumptions, detected = analyze_dataframe(df)
except Exception:
    st.error("The selected sheet could not be processed. Please check that it contains valid tabular data.")
    st.stop()

st.subheader("Risk dashboard")
total = len(result)
high = int((result["Risk Level"] == "High").sum())
temp = int(result.get("Temperature Excursion", pd.Series(False, index=result.index)).fillna(False).sum())

c1, c2, c3 = st.columns(3)
c1.metric("Total shipments", total)
c2.metric("High-risk shipments", high)
c3.metric("Temperature-excursion shipments", temp)

st.subheader("Risk distribution")
counts = result["Risk Level"].value_counts().reindex(["Low", "Medium", "High"], fill_value=0)
st.bar_chart(counts)

st.subheader("Top 5 highest-risk shipments")
top = result.sort_values(["Risk Score"], ascending=False).head(5).copy()
st.dataframe(top.drop(columns=["_unscored_reason"], errors="ignore"), use_container_width=True)

st.subheader("Recommendations")
for item in recommendations(result):
    st.markdown(f"- {item}")

with st.expander("How risk is calculated"):
    st.markdown(f"""
**Additive score**
- Temperature excursion: **+{TEMP_WEIGHT}**
- Significant delay: **+{DELAY_WEIGHT}**
- Quality/compliance issue: **+{QUALITY_WEIGHT}**

**Classification**
- 0–24 → Low
- 25–49 → Medium
- 50+ → High

The application detects fields from the uploaded dataset rather than assuming fixed column names.
""")
    if detected:
        st.write("Detected scoring signals:")
        for d in detected:
            st.write(f"- {d}")
    if assumptions:
        st.warning("Assumptions / limitations:")
        for a in assumptions:
            st.write(f"- {a}")

unscored = result[result["Risk Level"] == "Unscored"]
if not unscored.empty:
    st.warning(f"{len(unscored)} row(s) could not be scored because required detected signal data was missing.")
    st.dataframe(
        unscored.drop(columns=["_unscored_reason"], errors="ignore"),
        use_container_width=True
    )
