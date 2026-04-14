"""
DKM Vessel Tracker
Volg specifieke schepen op via VesselFinder (ETA, bestemming, status)
"""

import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import re

# ── Paginaconfiguratie ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="DKM Vessel Tracker",
    page_icon="🚢",
    layout="wide",
)

# ── Stijl ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }
    .main { background-color: #0f1117; }

    .header-bar {
        background: linear-gradient(135deg, #D94F2B 0%, #b03a1e 100%);
        padding: 1.2rem 2rem;
        border-radius: 8px;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    .header-bar h1 {
        color: white;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1.6rem;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .header-bar span {
        color: rgba(255,255,255,0.7);
        font-size: 0.85rem;
    }

    .vessel-card {
        background: #1a1d27;
        border: 1px solid #2a2d3a;
        border-left: 4px solid #D94F2B;
        border-radius: 8px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 0.8rem;
        transition: border-color 0.2s;
    }
    .vessel-card:hover { border-left-color: #ff6b47; }
    .vessel-card.error { border-left-color: #555; opacity: 0.6; }

    .vessel-name {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1.1rem;
        font-weight: 600;
        color: #e8eaf0;
        margin-bottom: 0.4rem;
    }
    .vessel-meta {
        font-size: 0.8rem;
        color: #6b7280;
        font-family: 'IBM Plex Mono', monospace;
        margin-bottom: 0.8rem;
    }
    .eta-badge {
        display: inline-block;
        background: rgba(217, 79, 43, 0.15);
        border: 1px solid rgba(217, 79, 43, 0.4);
        color: #ff7a5c;
        padding: 0.3rem 0.8rem;
        border-radius: 4px;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.85rem;
        font-weight: 600;
        margin-right: 0.6rem;
    }
    .dest-badge {
        display: inline-block;
        background: rgba(59, 130, 246, 0.1);
        border: 1px solid rgba(59, 130, 246, 0.3);
        color: #60a5fa;
        padding: 0.3rem 0.8rem;
        border-radius: 4px;
        font-size: 0.8rem;
        margin-right: 0.6rem;
    }
    .status-badge {
        display: inline-block;
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.3);
        color: #34d399;
        padding: 0.3rem 0.8rem;
        border-radius: 4px;
        font-size: 0.8rem;
    }
    .status-badge.anchored {
        background: rgba(245, 158, 11, 0.1);
        border-color: rgba(245, 158, 11, 0.3);
        color: #fbbf24;
    }
    .lastport {
        font-size: 0.78rem;
        color: #6b7280;
        margin-top: 0.5rem;
    }
    .vf-link {
        font-size: 0.75rem;
        color: #4b5563;
        text-decoration: none;
        float: right;
        margin-top: -0.2rem;
    }
    .vf-link:hover { color: #D94F2B; }

    .refresh-info {
        font-size: 0.75rem;
        color: #4b5563;
        font-family: 'IBM Plex Mono', monospace;
        margin-bottom: 1rem;
    }
    .error-msg {
        color: #ef4444;
        font-size: 0.8rem;
        font-family: 'IBM Plex Mono', monospace;
    }

    /* Streamlit overrides */
    .stTextArea textarea {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.85rem !important;
        background-color: #1a1d27 !important;
        border-color: #2a2d3a !important;
        color: #e8eaf0 !important;
    }
    div[data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Header ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="header-bar">
    <div>
        <h1>🚢 DKM Vessel Tracker</h1>
        <span>Real-time ETA opvolging via VesselFinder AIS data</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Scraper functie ─────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def scrape_vessel(mmsi: str) -> dict:
    """Haal schepsinfo op van VesselFinder voor een MMSI nummer."""
    mmsi = mmsi.strip()
    url = f"https://www.vesselfinder.com/vessels/details/{mmsi}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        return {"mmsi": mmsi, "error": str(e), "url": url}

    soup = BeautifulSoup(resp.text, "html.parser")

    result = {
        "mmsi": mmsi,
        "name": "—",
        "type": "—",
        "flag": "—",
        "destination": "—",
        "eta": "—",
        "status": "—",
        "speed": "—",
        "last_port": "—",
        "scraped_at": datetime.utcnow().strftime("%H:%M UTC"),
        "url": url,
        "error": None,
    }

    # Scheepsnaam — zit in <h1> of title
    title = soup.find("title")
    if title:
        t = title.text.strip()
        # bv. "MSC ANTWERP - IMO 9839662 - MMSI 255806420 - VesselFinder"
        name_match = re.match(r"^(.+?)\s*[-–]", t)
        if name_match:
            result["name"] = name_match.group(1).strip()

    # Tabellen uitlezen — VesselFinder gebruikt <table> voor voyage details
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            key = cells[0].get_text(strip=True).lower()
            val = cells[1].get_text(strip=True)

            if "destination" in key:
                result["destination"] = val or "—"
            elif "eta" in key and "ais" not in key:
                result["eta"] = val or "—"
            elif "status" in key or "nav status" in key:
                result["status"] = val or "—"
            elif "speed" in key:
                result["speed"] = val or "—"
            elif "last port" in key or "previous port" in key:
                result["last_port"] = val or "—"
            elif "flag" in key:
                result["flag"] = val or "—"
            elif "type" in key and result["type"] == "—":
                result["type"] = val or "—"

    # Fallback: zoek in dl/dt/dd structuur
    for dt in soup.find_all("dt"):
        key = dt.get_text(strip=True).lower()
        dd = dt.find_next_sibling("dd")
        if not dd:
            continue
        val = dd.get_text(strip=True)
        if "destination" in key and result["destination"] == "—":
            result["destination"] = val
        elif "eta" in key and result["eta"] == "—":
            result["eta"] = val
        elif "status" in key and result["status"] == "—":
            result["status"] = val
        elif "speed" in key and result["speed"] == "—":
            result["speed"] = val
        elif "last port" in key and result["last_port"] == "—":
            result["last_port"] = val

    # Zoek ook in tekstblokken naar ETA patronen als fallback
    if result["eta"] == "—":
        text = soup.get_text()
        eta_match = re.search(r"ETA[:\s]+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}|\d{2}/\d{2}\s+\d{2}:\d{2})", text)
        if eta_match:
            result["eta"] = eta_match.group(1)

    return result


def status_badge(status: str) -> str:
    s = status.lower()
    if "anchor" in s:
        css_class = "status-badge anchored"
    else:
        css_class = "status-badge"
    return f'<span class="{css_class}">{status}</span>'


# ── Sidebar: configuratie ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Instellingen")

    mmsi_input = st.text_area(
        "MMSI nummers (één per lijn)",
        placeholder="244650589\n244650123\n...",
        height=200,
        help="Voer één MMSI per lijn in. MMSI = 9-cijferig nummer."
    )

    auto_refresh = st.checkbox("Auto-refresh (60s)", value=False)
    show_table = st.checkbox("Toon ook als tabel", value=True)

    fetch_btn = st.button("🔄 Ophalen", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("""
**ℹ️ Toelichting**

Data wordt opgehaald van [VesselFinder](https://www.vesselfinder.com) 
via publieke scheepspagina's.

- MMSI = 9-cijferig nummer  
- Bv. *Antwerp Gateway*: `244650589`
- Refresh elke 60s voor live tracking

*Data is afhankelijk van AIS transmissies.*
    """)

# ── Hoofdgedeelte ────────────────────────────────────────────────────────────
if not mmsi_input.strip():
    st.info("👈 Voer MMSI nummers in de sidebar in en klik op **Ophalen**.")
    st.markdown("""
#### Hoe vind je een MMSI?
1. Ga naar [VesselFinder](https://www.vesselfinder.com) of [MarineTraffic](https://www.marinetraffic.com)
2. Zoek op scheepsnaam
3. Kopieer het 9-cijferig MMSI nummer

**Voorbeeldnummers om te testen:**
```
244650589
566554000
```
    """)
    st.stop()

mmsi_list = [m.strip() for m in mmsi_input.strip().split("\n") if m.strip()]

if not mmsi_list:
    st.warning("Geen geldige MMSI nummers gevonden.")
    st.stop()

# ── Data ophalen ─────────────────────────────────────────────────────────────
should_fetch = fetch_btn or (auto_refresh and "vessels" not in st.session_state)

if fetch_btn or "vessels" not in st.session_state or \
   st.session_state.get("last_mmsi_list") != mmsi_list:

    with st.spinner(f"Ophalen van {len(mmsi_list)} schip(en)..."):
        vessels = []
        progress = st.progress(0)
        for i, mmsi in enumerate(mmsi_list):
            vessels.append(scrape_vessel(mmsi))
            progress.progress((i + 1) / len(mmsi_list))
            if i < len(mmsi_list) - 1:
                time.sleep(0.5)  # beleefd scrapen
        progress.empty()

    st.session_state["vessels"] = vessels
    st.session_state["last_fetch"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    st.session_state["last_mmsi_list"] = mmsi_list

vessels = st.session_state.get("vessels", [])
last_fetch = st.session_state.get("last_fetch", "—")

if vessels:
    st.markdown(f'<div class="refresh-info">Laatste update: {last_fetch} · {len(vessels)} schip(en) · Data: VesselFinder AIS</div>', unsafe_allow_html=True)

# ── Kaartweergave ─────────────────────────────────────────────────────────────
ok_vessels = [v for v in vessels if not v.get("error")]
err_vessels = [v for v in vessels if v.get("error")]

if ok_vessels:
    cols = st.columns(min(3, len(ok_vessels)))
    # Kleine KPI badges bovenaan
    etas = [v["eta"] for v in ok_vessels if v["eta"] != "—"]
    col1, col2, col3 = st.columns(3)
    col1.metric("Schepen getrackt", len(ok_vessels))
    col2.metric("Met ETA", len(etas))
    col3.metric("Zonder data", len(err_vessels))

    st.markdown("---")

for v in vessels:
    if v.get("error"):
        st.markdown(f"""
<div class="vessel-card error">
    <div class="vessel-name">MMSI: {v['mmsi']}</div>
    <div class="error-msg">⚠️ Fout bij ophalen: {v['error']}</div>
    <div class="lastport"><a href="{v['url']}" target="_blank" style="color:#4b5563">→ Bekijk op VesselFinder</a></div>
</div>
""", unsafe_allow_html=True)
        continue

    eta_html = f'<span class="eta-badge">ETA {v["eta"]}</span>' if v["eta"] != "—" else ""
    dest_html = f'<span class="dest-badge">→ {v["destination"]}</span>' if v["destination"] != "—" else ""
    status_html = status_badge(v["status"]) if v["status"] != "—" else ""
    speed_txt = f' · {v["speed"]} kn' if v["speed"] != "—" else ""
    lastport_txt = f'Vorige haven: {v["last_port"]}' if v["last_port"] != "—" else ""
    type_flag = f'{v["flag"]} · {v["type"]}' if v["type"] != "—" else v["flag"]

    st.markdown(f"""
<div class="vessel-card">
    <a class="vf-link" href="{v['url']}" target="_blank">↗ VesselFinder</a>
    <div class="vessel-name">{v['name']}</div>
    <div class="vessel-meta">MMSI {v['mmsi']} · {type_flag}{speed_txt} · {v['scraped_at']}</div>
    <div>
        {eta_html}
        {dest_html}
        {status_html}
    </div>
    <div class="lastport">{lastport_txt}</div>
</div>
""", unsafe_allow_html=True)


# ── Tabelweergave ─────────────────────────────────────────────────────────────
if show_table and vessels:
    st.markdown("---")
    st.subheader("📋 Overzichtstabel")

    df_data = []
    for v in vessels:
        df_data.append({
            "MMSI": v["mmsi"],
            "Naam": v["name"] if not v.get("error") else "ERROR",
            "Bestemming": v.get("destination", "—"),
            "ETA": v.get("eta", "—"),
            "Status": v.get("status", "—"),
            "Snelheid": v.get("speed", "—"),
            "Vorige haven": v.get("last_port", "—"),
            "Update": v.get("scraped_at", "—"),
        })

    df = pd.DataFrame(df_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # CSV download
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download CSV",
        csv,
        f"vessel_tracker_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv",
        "text/csv",
        use_container_width=False,
    )

# ── Auto-refresh ──────────────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(60)
    st.rerun()
