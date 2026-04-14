"""
Data Docked API Tester — DKM
Snel testen of je API key werkt + ruwe response bekijken
"""

import streamlit as st
import requests
import json
from datetime import datetime

st.set_page_config(page_title="Data Docked API Tester", page_icon="🔌", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;600&display=swap');
    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
    .title { font-family: 'IBM Plex Mono', monospace; color: #D94F2B; font-size: 1.5rem; font-weight: 600; }
    .ok   { background:#0d2b1a; border:1px solid #10b981; border-radius:6px; padding:1rem; color:#34d399; font-family:'IBM Plex Mono',monospace; }
    .fail { background:#2b0d0d; border:1px solid #ef4444; border-radius:6px; padding:1rem; color:#f87171; font-family:'IBM Plex Mono',monospace; }
    .field-row { display:flex; gap:1rem; margin-bottom:0.3rem; font-size:0.85rem; }
    .field-key { color:#6b7280; width:180px; flex-shrink:0; font-family:'IBM Plex Mono',monospace; }
    .field-val { color:#e8eaf0; }
    .field-val.highlight { color:#ff7a5c; font-weight:600; font-family:'IBM Plex Mono',monospace; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">🔌 Data Docked API Tester</div>', unsafe_allow_html=True)
st.markdown("Test je API key en bekijk de ruwe response van de Data Docked AIS API.")
st.markdown("---")

# ── Invoer ────────────────────────────────────────────────────────────────────
col1, col2 = st.columns([1, 1])

with col1:
    api_key = st.text_input(
        "🔑 API Key",
        type="password",
        placeholder="Jouw Data Docked API key",
    )

with col2:
    imo_mmsi = st.text_input(
        "🚢 IMO of MMSI nummer",
        placeholder="bv. 9247431  of  244650589",
        value="9247431",
        help="IMO = 7 cijfers, MMSI = 9 cijfers"
    )

show_raw = st.checkbox("Toon volledige JSON response", value=True)

test_btn = st.button("▶ Test API", type="primary")

# ── API call ──────────────────────────────────────────────────────────────────
BASE_URL = "https://datadocked.com/api/vessels_operations/get-vessel-info"

# Interessante velden om te highlighten
KEY_FIELDS = {
    "name":               "Naam",
    "mmsi":               "MMSI",
    "imo":                "IMO",
    "shipType":           "Type",
    "destination":        "Bestemming (AIS)",
    "unlocodeDestination":"UNLOCODE bestemming",
    "etaUtc":             "ETA (UTC)",
    "speed":              "Snelheid (kn)",
    "navigationalStatus": "Status",
    "latitude":           "Latitude",
    "longitude":          "Longitude",
    "positionReceived":   "Positie ontvangen",
    "lastPort":           "Laatste haven",
    "unlocodeLastport":   "UNLOCODE laatste haven",
    "country":            "Vlag",
    "length":             "Lengte",
    "deadweight":         "DWT",
}

ETA_HIGHLIGHT = {"etaUtc", "destination", "unlocodeDestination", "navigationalStatus"}

if test_btn:
    if not api_key.strip():
        st.error("Vul je API key in.")
        st.stop()
    if not imo_mmsi.strip():
        st.error("Vul een IMO of MMSI in.")
        st.stop()

    with st.spinner("API aanroepen..."):
        try:
            resp = requests.get(
                BASE_URL,
                params={"imo_or_mmsi": imo_mmsi.strip()},
                headers={"accept": "application/json", "x-api-key": api_key.strip()},
                timeout=15,
            )
        except requests.exceptions.ConnectionError:
            st.error("❌ Geen verbinding met datadocked.com — controleer je internetverbinding.")
            st.stop()
        except requests.exceptions.Timeout:
            st.error("❌ Timeout — de API reageert niet binnen 15 seconden.")
            st.stop()

    ts = datetime.utcnow().strftime("%H:%M:%S UTC")

    # ── Status check ──────────────────────────────────────────────────────────
    st.markdown(f"**HTTP status:** `{resp.status_code}` — gevraagd om `{ts}`")

    if resp.status_code == 200:
        st.markdown('<div class="ok">✅ API key werkt — verbinding geslaagd</div>', unsafe_allow_html=True)
    elif resp.status_code == 401:
        st.markdown('<div class="fail">❌ 401 Unauthorized — API key ongeldig of verlopen</div>', unsafe_allow_html=True)
        st.stop()
    elif resp.status_code == 403:
        st.markdown('<div class="fail">❌ 403 Forbidden — geen toegang tot dit endpoint met jouw plan</div>', unsafe_allow_html=True)
        st.stop()
    elif resp.status_code == 404:
        st.markdown('<div class="fail">❌ 404 — schip niet gevonden voor dit IMO/MMSI</div>', unsafe_allow_html=True)
    elif resp.status_code == 429:
        st.markdown('<div class="fail">❌ 429 Too Many Requests — rate limit bereikt</div>', unsafe_allow_html=True)
        st.stop()
    else:
        st.markdown(f'<div class="fail">⚠️ Onverwachte status {resp.status_code}</div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── Response parsen ───────────────────────────────────────────────────────
    try:
        data = resp.json()
    except Exception:
        st.error("Response is geen geldige JSON.")
        st.code(resp.text[:2000])
        st.stop()

    # Data zit in data["detail"] of direct in data
    detail = data.get("detail", data)

    # ── Overzicht van ETA-gerelateerde velden ──────────────────────────────────
    if isinstance(detail, dict):
        st.subheader("📋 Scheepsgegevens")

        rows_html = ""
        for api_key_field, label in KEY_FIELDS.items():
            val = detail.get(api_key_field, "—")
            if val in (None, "", "-"):
                val = "—"
            highlight = "highlight" if api_key_field in ETA_HIGHLIGHT and val != "—" else ""
            rows_html += f"""
            <div class="field-row">
                <div class="field-key">{label}</div>
                <div class="field-val {highlight}">{val}</div>
            </div>"""

        st.markdown(rows_html, unsafe_allow_html=True)

        # Port call history indien aanwezig
        ports = detail.get("ports", [])
        if ports:
            st.markdown("---")
            st.subheader("⚓ Recente havenbezoeken")
            import pandas as pd
            df_ports = pd.DataFrame(ports)
            st.dataframe(df_ports, use_container_width=True, hide_index=True)

    elif isinstance(detail, str):
        st.warning(f"API antwoord: {detail}")

    # ── Volledige JSON ─────────────────────────────────────────────────────────
    if show_raw:
        st.markdown("---")
        st.subheader("🔍 Volledige JSON response")
        st.json(data)

    # ── Credits check tip ──────────────────────────────────────────────────────
    remaining = resp.headers.get("X-RateLimit-Remaining") or resp.headers.get("x-credits-remaining")
    if remaining:
        st.info(f"💳 Resterende credits/calls: **{remaining}**")

st.markdown("---")
st.markdown("""
**Andere endpoints om te testen:**

| Endpoint | URL |
|---|---|
| Vessel info (IMO/MMSI) | `/api/vessels_operations/get-vessel-info?imo_or_mmsi=...` |
| Vessels in gebied | `/api/vessels_operations/get-vessels-in-area?lat=...&lon=...&radius=...` |

📖 Volledige docs: [datadocked.com/api-reference](https://datadocked.com/api-reference)
""")
