"""
Data Docked API Tester — DKM
Zoek op scheepsnaam, MMSI of IMO — test je API key
"""

import streamlit as st
import requests
from datetime import datetime

st.set_page_config(page_title="Data Docked API Tester", page_icon="🔌", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;600&display=swap');
    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }

    .title { font-family: 'IBM Plex Mono', monospace; color: #D94F2B; font-size: 1.5rem; font-weight: 600; margin-bottom: 0.2rem; }
    .subtitle { color: #6b7280; font-size: 0.85rem; margin-bottom: 1.5rem; }

    .ok   { background:#0d2b1a; border:1px solid #10b981; border-radius:6px; padding:0.8rem 1rem; color:#34d399; font-family:'IBM Plex Mono',monospace; font-size:0.85rem; margin-bottom:1rem; }
    .fail { background:#2b0d0d; border:1px solid #ef4444; border-radius:6px; padding:0.8rem 1rem; color:#f87171; font-family:'IBM Plex Mono',monospace; font-size:0.85rem; margin-bottom:1rem; }

    .result-card {
        background:#1a1d27; border:1px solid #2a2d3a; border-left: 3px solid #3b82f6;
        border-radius:6px; padding:0.9rem 1.1rem; margin-bottom:0.5rem;
    }
    .result-name { font-family:'IBM Plex Mono',monospace; font-weight:600; color:#e8eaf0; font-size:0.95rem; }
    .result-meta { font-size:0.78rem; color:#6b7280; margin-top:0.2rem; font-family:'IBM Plex Mono',monospace; }

    .field-row { display:flex; flex-direction:column; padding:0.35rem 0; border-bottom:1px solid #1f2230; }
    .field-key { font-size:0.72rem; color:#6b7280; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:0.1rem; }
    .field-val { font-size:0.88rem; color:#e8eaf0; font-family:'IBM Plex Mono',monospace; }
    .field-val.eta  { color:#ff7a5c; font-weight:600; }
    .field-val.dest { color:#a78bfa; }
    .field-val.spd  { color:#34d399; }

    .credits-badge {
        display:inline-block; background:rgba(59,130,246,0.1); border:1px solid rgba(59,130,246,0.3);
        color:#60a5fa; padding:0.2rem 0.7rem; border-radius:4px;
        font-size:0.75rem; font-family:'IBM Plex Mono',monospace; margin-bottom:0.8rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">🔌 Data Docked API Tester</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Zoek op scheepsnaam, MMSI of IMO nummer — DKM intern</div>', unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "vessel_detail" not in st.session_state:
    st.session_state.vessel_detail = None

BASE = "https://datadocked.com/api/vessels_operations"

def api_get(path, params, key):
    try:
        return requests.get(
            f"{BASE}/{path}", params=params,
            headers={"accept": "application/json", "x-api-key": key},
            timeout=15,
        )
    except Exception:
        return None

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔑 API Key")
    api_key = st.text_input("Data Docked API Key", type="password", placeholder="Jouw key hier")

    st.markdown("---")
    if st.button("💳 Check resterende credits", use_container_width=True):
        if api_key:
            r = api_get("my-credits", {}, api_key)
            if r and r.status_code == 200:
                st.success(r.json().get("detail", "?"))
            elif r:
                st.error(f"Fout {r.status_code}")
            else:
                st.error("Geen verbinding")
        else:
            st.warning("Vul eerst je API key in")

    st.markdown("---")
    st.markdown("""
**Credit kosten:**
- Naam zoeken: **1 credit**
- Vessel details: **5 credits**
- Vessel locatie: **1 credit**

**Tip:** MMSI = 9 cijfers, IMO = 7 cijfers.
Bij naam zoeken krijg je een lijst waaruit je kiest — pas dan worden de 5 credits voor details aangerekend.
    """)

if not api_key:
    st.info("👈 Vul je Data Docked API key in de sidebar in.")
    st.stop()

# ── Zoekbalk ──────────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns([4, 1, 1])
with col1:
    zoek = st.text_input(
        "Zoeken",
        placeholder="Scheepsnaam  ·  MMSI (9 cijfers)  ·  IMO (7 cijfers)",
        label_visibility="collapsed",
    )
with col2:
    zoek_btn = st.button("🔍 Zoeken", type="primary", use_container_width=True)
with col3:
    if st.button("✖ Reset", use_container_width=True):
        st.session_state.search_results = []
        st.session_state.vessel_detail = None
        st.rerun()

# ── Zoeklogica ────────────────────────────────────────────────────────────────
def is_mmsi(s): return s.isdigit() and len(s) == 9
def is_imo(s):  return s.isdigit() and len(s) == 7

if zoek_btn and zoek.strip():
    q = zoek.strip()
    st.session_state.vessel_detail = None
    st.session_state.search_results = []

    if is_mmsi(q) or is_imo(q):
        # Direct detail ophalen
        with st.spinner("Schip opzoeken..."):
            r = api_get("get-vessel-info", {"imo_or_mmsi": q}, api_key)

        if r is None:
            st.error("❌ Geen verbinding")
        elif r.status_code == 401:
            st.error("❌ API key ongeldig (401)")
        elif r.status_code == 404:
            st.warning("Geen schip gevonden voor dit nummer")
        elif r.status_code == 200:
            detail = r.json().get("detail", {})
            st.session_state.vessel_detail = detail
            st.session_state.search_results = [detail]
        else:
            st.error(f"Fout {r.status_code}: {r.text[:200]}")

    else:
        # Naam zoeken — 1 credit
        with st.spinner(f"Zoeken naar '{q}'..."):
            r = api_get("vessels-by-vessel-name", {"vessel_name": q.upper()}, api_key)

        if r is None:
            st.error("❌ Geen verbinding")
        elif r.status_code == 401:
            st.error("❌ API key ongeldig (401)")
            st.stop()
        elif r.status_code == 200:
            data = r.json()
            # Resultaten kunnen in verschillende formaten zitten
            if isinstance(data, list):
                results = data
            elif isinstance(data, dict):
                results = data.get("detail") or data.get("vessels") or data.get("results") or []
                if isinstance(results, dict):
                    results = [results]
            else:
                results = []

            if not results:
                st.warning(f"Geen resultaten voor '{q}'")
            else:
                st.session_state.search_results = results
        else:
            st.error(f"Fout {r.status_code}: {r.text[:300]}")

# ── Zoekresultaten — selecteer een schip ──────────────────────────────────────
results = st.session_state.search_results

if results and not st.session_state.vessel_detail:
    st.markdown(f"**{len(results)} schip(en) gevonden** — klik op Details voor volledige info (5 credits):")
    st.markdown("")

    for i, v in enumerate(results[:20]):
        name     = v.get("name", "—")
        mmsi     = str(v.get("mmsi", ""))
        imo      = str(v.get("imo", ""))
        vtype    = v.get("shipType") or v.get("type", "")
        flag     = v.get("country") or v.get("flag", "")
        identifier = mmsi or imo

        col_card, col_btn = st.columns([5, 1])
        with col_card:
            st.markdown(f"""
<div class="result-card">
    <div class="result-name">{name}</div>
    <div class="result-meta">MMSI {mmsi or '—'} &nbsp;·&nbsp; IMO {imo or '—'} &nbsp;·&nbsp; {vtype} &nbsp;·&nbsp; {flag}</div>
</div>""", unsafe_allow_html=True)
        with col_btn:
            st.markdown("<div style='margin-top:0.45rem'></div>", unsafe_allow_html=True)
            if st.button("Details →", key=f"d_{i}_{identifier}", use_container_width=True):
                with st.spinner(f"Details laden voor {name}..."):
                    r2 = api_get("get-vessel-info", {"imo_or_mmsi": identifier}, api_key)
                if r2 and r2.status_code == 200:
                    st.session_state.vessel_detail = r2.json().get("detail", {})
                    st.rerun()
                elif r2:
                    st.error(f"Fout {r2.status_code}")

# ── Detailscherm ──────────────────────────────────────────────────────────────
d = st.session_state.vessel_detail

if d:
    st.markdown("---")
    name = d.get("name", "—")
    st.markdown(f"### 🚢 {name}")
    st.markdown('<span class="credits-badge">✅ Gegevens geladen · 5 credits gebruikt</span>', unsafe_allow_html=True)
    st.markdown("")

    col_a, col_b = st.columns(2)

    # Kolom A: identiteit & positie
    with col_a:
        st.markdown("**Identiteit & positie**")
        velden_a = [
            ("MMSI",             d.get("mmsi"),              ""),
            ("IMO",              d.get("imo"),               ""),
            ("Type",             d.get("shipType"),          ""),
            ("Vlag",             d.get("country"),           ""),
            ("Status",           d.get("navigationalStatus"),""),
            ("Snelheid (kn)",    d.get("speed"),             "spd"),
            ("Latitude",         d.get("latitude"),          ""),
            ("Longitude",        d.get("longitude"),         ""),
            ("Positie update",   d.get("positionReceived"),  ""),
            ("Laatste haven",    d.get("lastPort"),          ""),
            ("Callsign",         d.get("callsign"),          ""),
        ]
        html = ""
        for label, val, css in velden_a:
            if val and str(val) not in ("", "-", "None"):
                html += f'<div class="field-row"><div class="field-key">{label}</div><div class="field-val {css}">{val}</div></div>'
        st.markdown(html, unsafe_allow_html=True)

    # Kolom B: voyage
    with col_b:
        st.markdown("**Voyage informatie**")

        dest     = d.get("destination", "—") or "—"
        eta      = d.get("etaUtc", "—") or "—"
        unlocode = d.get("unlocodeDestination", "") or ""
        atd      = d.get("atdUtc", "—") or "—"

        velden_b = [
            ("Bestemming (AIS)",      dest,     "dest"),
            ("UNLOCODE bestemming",   unlocode, ""),
            ("ETA (UTC)",             eta,      "eta"),
            ("Vertrek vorige haven",  atd,      ""),
            ("Lengte × Breedte",      f'{d.get("length","—")} × {d.get("beam","—")}', ""),
            ("DWT",                   d.get("deadweight"), ""),
            ("Bouwjaar",              d.get("yearOfBuilt"), ""),
        ]
        html2 = ""
        for label, val, css in velden_b:
            if val and str(val) not in ("", "-", "—", "None", "— × —"):
                html2 += f'<div class="field-row"><div class="field-key">{label}</div><div class="field-val {css}">{val}</div></div>'
        st.markdown(html2, unsafe_allow_html=True)

        # Antwerpen / Zeebrugge indicator
        st.markdown("")
        dest_up  = dest.upper()
        unlo_up  = unlocode.upper()
        combined = dest_up + " " + unlo_up

        ANTP = ["BEANR","ANTWERP","ANTWERPEN"]
        ZBEE = ["BEZEE","ZEEBRUGGE","ZEEBRUG"]

        if any(k in combined for k in ANTP):
            st.success(f"✅ Onderweg naar **Antwerpen** — ETA: {eta}")
        elif any(k in combined for k in ZBEE):
            st.success(f"✅ Onderweg naar **Zeebrugge** — ETA: {eta}")
        else:
            st.info(f"ℹ️ Bestemming: **{dest}** — niet Antwerpen/Zeebrugge")

    # Havenbezoeken
    ports = d.get("ports", [])
    if ports and isinstance(ports, list) and len(ports) > 0:
        st.markdown("---")
        st.markdown("**⚓ Recente havenbezoeken**")
        import pandas as pd
        st.dataframe(pd.DataFrame(ports), use_container_width=True, hide_index=True)

    # Terug knop + raw JSON
    st.markdown("---")
    col_back, col_json = st.columns([1, 4])
    with col_back:
        if st.button("← Terug naar resultaten"):
            st.session_state.vessel_detail = None
            st.rerun()
    with col_json:
        with st.expander("🔍 Volledige JSON response"):
            st.json(d)
