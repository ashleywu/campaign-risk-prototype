# Campaign Delivery Risk Prototype

This is a lightweight internal prototype for HTS Media to identify which campaigns are at risk of under-delivery, understand why, and see a suggested next action.

**Live app:** [https://campaign-risk-prototype-v1.streamlit.app/](https://campaign-risk-prototype-v1.streamlit.app/)

The core logic lives in `app.py` (Streamlit UI) and `AdsRanking.ipynb` (notebook exploration), with a small synthetic dataset in `hts_media_campaigns.csv`.

---

## What the app does

- Shows all campaigns with:
  - Budget, spend, pacing, and remaining time.
  - A risk score (0–100) and a tier (High / Medium / Low).
  - A plain-language explanation of *why* the campaign is at that risk.
  - One concrete suggested next action per campaign.
- Highlights, at the top, which advertisers need attention (High/Medium risk).
- Lets users tune:
  - The relative weights of risk factors (delivery gap, recovery pressure, time urgency, performance trend, blockers).
  - The thresholds that define High and Medium risk tiers.

---

## Running locally

### 1. Install dependencies

From the project root:

```bash
pip install -r requirements.txt
```

### 2. Start the Streamlit app

From the same directory:

```bash
python -m streamlit run app.py
```

Then open the URL printed in the terminal (typically `http://localhost:8501`).

### 3. Load the sample data

- Ensure `hts_media_campaigns.csv` is in the same directory as `app.py`.
- In the UI, set the **Campaign CSV path** to:

```text
hts_media_campaigns.csv
```

The table and details panel will populate with the sample campaigns.

---

## Deploying on Streamlit Community Cloud

High-level steps:

1. Push this project (including `app.py`, `requirements.txt`, and `hts_media_campaigns.csv`) to GitHub.
2. In Streamlit Community Cloud:
   - Create a new app from that repository.
   - Choose `app.py` as the main file.
3. Once deployed, open the app and set **Campaign CSV path** to:

```text
hts_media_campaigns.csv
```

You can then share the Streamlit URL as part of your prototype submission.

---

## Notes and limitations

- The risk model is heuristic (hand-tuned weights) rather than trained on historical outcomes.
- Pacing assumes roughly linear delivery against budget and does not model seasonal curves explicitly.
- Some signals are derived from free-text notes (e.g., premium partner, learning phase, low bids), which is convenient but fragile if note conventions change.

