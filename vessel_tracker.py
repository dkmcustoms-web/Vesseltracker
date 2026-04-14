"""
DKM Vessel Tracker
Zoek schepen op naam via VesselFinder — volg ETA, bestemming en status op
"""

import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import re

st.set_page_config(page_title="DKM Vessel Tracker", page_icon="🚢", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }

    .header-bar {
        background: linear-gradient(135deg, #D94F2B 0%, #b03a1e 100%);
        padding: 1.1rem 2rem; border-radius: 8px; margin-bottom: 1.5rem;
    }
    .header-bar h1 { color:white; font-family:'IBM Plex Mono',monospace; font-size:1.5rem; margin:0; }
    .header-bar span { color:rgba(255,255,255,0.7); font-size:0.82rem; }

    .search-result {
        background:#1a1d27; border:1px solid #2a2d3a; border-left:3px solid #3b82f6;
        border-radius:6px; padding:0.7rem 1rem; margin-bottom:0.4rem;
    }
    .search-result .sname { font-family:'IBM Plex Mono',monospace; font-weight:600; color:#e8eaf0; font-size:0.9rem; }
    .search-result .smeta { font-size:0.75rem; color:#6b7280; margin-top:0.15rem; font-family:'IBM Plex Mono',monospace; }

    .vessel-card {
        background:#1a1d27; border:1px solid #2a2d3a; border-left:4px solid #D94F2B;
        border-radius:8px; padding:1.1rem 1.4rem; margin-bottom:0.7rem;
    }
    .vessel-card.towards { border-left-color:#10b981; }
    .vessel-card.other   { border-left-color:#f59e0b; }
    .vessel-card.error   { border-left-color:#374151; opacity:0.6; }

    .vessel-name { font-family:'IBM Plex Mono',monospace; font-size:1rem; font-weight:600; color:#e8eaf0; margin-bottom:0.3rem; }
    .vessel-meta { font-size:0.76rem; color:#6b7280; font-family:'IBM Plex Mono',monospace; margin-bottom:0.6rem; }

    .badge { display:inline-block; padding:0.25rem 0.7rem; border-radius:4px; font-size:0.8rem; margin-right:0.4rem; font-family:'IBM Plex Mono',monospace; font-weight:600; }
    .badge-eta  { background:rgba(217,79,43,0.15); border:1px solid rgba(217,79,43,0.4); color:#ff7a5c; }
    .badge-dest { background:rgba(139,92,246,0.1); border:1px solid rgba(139,92,246,0.3); color:#a78bfa; font-weight:400; }
    .badge-stat { background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.25); color:#6ee7b7; font-weight:400; }
    .badge-be   { background:rgba(16,185,129,0.15); border:1px solid rgba(16,185,129,0.4); color:#34d399; }

    .detail-line { font-size:0.76rem; color:#6b7280; margin-top:0.4rem; }
    .vf-link { font-size:0.72rem; color:#4b5563; text-decoration:none; float:right; }
    .vf-link:hover { color:#D94F2B; }
    .refresh-info { font-size:0.74rem; color:#4b5563; font-family:'IBM Plex Mono',monospace; margin-bottom:0.8rem; }
    .tracked-label { font-size:0.7rem; color:#6b7280; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:0.4rem; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header-bar">
    <h1>🚢 DKM Vessel Tracker</h1>
    <span>Real-time ETA opvolging via VesselFinder AIS data</span>
</div>
""", unsafe_allow_html=True)

# ── Constanten ────────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "en-US,en;q=0.9",
}
ANTP_KW = ["BEANR", "ANTWERP", "ANTWERPEN", "ANR"]
ZBEE_KW = ["BEZEE", "ZEEBRUGGE", "ZEEBRUG"]

# ── Session state ─────────────────────────────────────────────────────────────
for key, default in [
    ("tracked", {}),
    ("search_results", []),
    ("vessel_data", {}),
    ("last_fetch", None),
    ("last_search", ""),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── Functies ──────────────────────────────────────────────────────────────────
def search_by_name(name: str) -> list:
    """Zoek schepen op naam via VesselFinder."""
    url = f"https://www.vesselfinder.com/vessels?name={requests.utils.quote(name.upper())}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Formaat 1: /vessels/details/MMSI
        m1 = re.search(r"/vessels/details/(\d{9})", href)
        # Formaat 2: /vessels/NAME-IMO-XXXXXXX-MMSI-XXXXXXXXX
        m2 = re.search(r"MMSI-(\d{9})", href, re.I)
        mmsi_m = m1 or m2
        if not mmsi_m:
            continue
        mmsi = mmsi_m.group(1)
        if mmsi in seen:
            continue
        seen.add(mmsi)

        imo_m = re.search(r"IMO-(\d{7})", href, re.I)
        imo = imo_m.group(1) if imo_m else ""

        vessel_name = a.get_text(strip=True).upper() or f"MMSI {mmsi}"
        if len(vessel_name) < 2:
            continue

        results.append({
            "name": vessel_name,
            "mmsi": mmsi,
            "imo":  imo,
            "url":  f"https://www.vesselfinder.com/vessels/details/{mmsi}",
        })

    return results[:15]


def scrape_vessel(mmsi: str) -> dict:
    """Scrape scheepsdetails van VesselFinder."""
    url = f"https://www.vesselfinder.com/vessels/details/{mmsi}"
    result = {
        "mmsi": mmsi, "name": "—", "type": "—", "flag": "—",
        "destination": "—", "eta": "—", "status": "—",
        "speed": "—", "last_port": "—",
        "scraped_at": datetime.utcnow().strftime("%H:%M UTC"),
        "url": url, "error": None,
    }
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
    except Exception as e:
        result["error"] = str(e)
        return result

    soup = BeautifulSoup(r.text, "html.parser")

    title = soup.find("title")
    if title:
        m = re.match(r"^(.+?)\s*[-–]", title.text.strip())
        if m:
            result["name"] = m.group(1).strip()

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            key = cells[0].get_text(strip=True).lower()
            val = cells[1].get_text(strip=True)
            if not val:
                continue
            if "destination" in key:                       result["destination"] = val
            elif "eta" in key and "ais" not in key:        result["eta"] = val
            elif "status" in key:                          result["status"] = val
            elif "speed" in key:                           result["speed"] = val
            elif "last port" in key or "previous" in key:  result["last_port"] = val
            elif "flag" in key:                            result["flag"] = val
            elif "type" in key and result["type"] == "—":  result["type"] = val

    for dt in soup.find_all("dt"):
        key = dt.get_text(strip=True).lower()
        dd  = dt.find_next_sibling("dd")
        if not dd:
            continue
        val = dd.get_text(strip=True)
        if "destination" in key and result["destination"] == "—": result["destination"] = val
        elif "eta"       in key and result["eta"] == "—":          result["eta"] = val
        elif "status"    in key and result["status"] == "—":       result["status"] = val
        elif "speed"     in key and result["speed"] == "—":        result["speed"] = val
        elif "last port" in key and result["last_port"] == "—":    result["last_port"] = val

    return result


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔍 Schip zoeken op naam")
    naam_input = st.text_input(
        "Scheepsnaam",
        placeholder="bv.  MSC ANTWERP",
        label_visibility="collapsed",
    )
    zoek_btn = st.button("🔍 Zoeken op naam", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("##### of direct via nummer")
    nr_input = st.text_input("MMSI of IMO", placeholder="244650589", label_visibility="collapsed")
    add_nr_btn = st.button("＋ Toevoegen", use_container_width=True)

    st.markdown("---")

    if st.session_state.tracked:
        st.markdown('<div class="tracked-label">Gevolgde schepen</div>', unsafe_allow_html=True)
        to_remove = []
        for mmsi, info in list(st.session_state.tracked.items()):
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(
                    f"<small style='font-family:IBM Plex Mono,monospace;color:#9ca3af'>"
                    f"{info.get('name','—')[:22]}<br>"
                    f"<span style='color:#4b5563'>{mmsi}</span></small>",
                    unsafe_allow_html=True
                )
            with c2:
                if st.button("×", key=f"rm_{mmsi}"):
                    to_remove.append(mmsi)
        for m in to_remove:
            del st.session_state.tracked[m]
            st.session_state.vessel_data.pop(m, None)
            st.rerun()

        st.markdown("")
        c_r, c_c = st.columns(2)
        with c_r:
            if st.button("🔄 Ververs", use_container_width=True):
                st.session_state.vessel_data = {}
                st.rerun()
        with c_c:
            if st.button("🗑 Wis alles", use_container_width=True):
                st.session_state.tracked = {}
                st.session_state.vessel_data = {}
                st.rerun()

    st.markdown("---")
    show_table   = st.checkbox("Toon als tabel", value=True)
    auto_refresh = st.checkbox("Auto-refresh (60s)", value=False)


# ── Directe toevoeging via nummer ─────────────────────────────────────────────
if add_nr_btn and nr_input.strip():
    nr = nr_input.strip()
    if nr.isdigit() and len(nr) in (7, 9):
        st.session_state.tracked[nr] = {"name": f"#{nr}", "mmsi": nr}
        st.rerun()
    else:
        st.warning("Voer een geldig MMSI (9 cijfers) of IMO (7 cijfers) in.")


# ── Naam zoeken ───────────────────────────────────────────────────────────────
if zoek_btn and naam_input.strip():
    with st.spinner(f"Zoeken naar '{naam_input}'..."):
        res = search_by_name(naam_input.strip())
    st.session_state.search_results = res
    st.session_state.last_search = naam_input.strip()

if st.session_state.search_results:
    naam = st.session_state.last_search
    res  = st.session_state.search_results
    st.markdown(f"**{len(res)} schip(en) gevonden voor '{naam}'** — klik **＋ Voeg toe** om te volgen:")
    st.markdown("")

    for i, v in enumerate(res):
        c_card, c_btn = st.columns([5, 1])
        with c_card:
            st.markdown(f"""
<div class="search-result">
    <div class="sname">{v['name']}</div>
    <div class="smeta">MMSI {v['mmsi']} &nbsp;·&nbsp; IMO {v.get('imo','—')}</div>
</div>""", unsafe_allow_html=True)
        with c_btn:
            st.markdown("<div style='margin-top:0.4rem'></div>", unsafe_allow_html=True)
            already = v["mmsi"] in st.session_state.tracked
            if st.button(
                "✓ Toegev." if already else "＋ Voeg toe",
                key=f"add_{i}_{v['mmsi']}",
                use_container_width=True,
                disabled=already,
            ):
                st.session_state.tracked[v["mmsi"]] = v
                st.rerun()

    if st.button("✖ Sluit zoekresultaten"):
        st.session_state.search_results = []
        st.rerun()
    st.markdown("---")


# ── Geen schepen gevolgd ──────────────────────────────────────────────────────
if not st.session_state.tracked:
    st.info("👈 Zoek een scheepsnaam links en voeg schepen toe aan je volglijst.")
    st.stop()


# ── Data ophalen ──────────────────────────────────────────────────────────────
missing = [m for m in st.session_state.tracked if m not in st.session_state.vessel_data]
if missing:
    with st.spinner(f"AIS data ophalen voor {len(missing)} schip(en)..."):
        prog = st.progress(0)
        for i, mmsi in enumerate(missing):
            data = scrape_vessel(mmsi)
            if data.get("name") and data["name"] != "—":
                st.session_state.tracked[mmsi]["name"] = data["name"]
            st.session_state.vessel_data[mmsi] = data
            prog.progress((i + 1) / len(missing))
            if i < len(missing) - 1:
                time.sleep(0.5)
        prog.empty()
    st.session_state.last_fetch = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

vdata      = st.session_state.vessel_data
last_fetch = st.session_state.last_fetch or "—"

# ── KPI's ─────────────────────────────────────────────────────────────────────
total   = len(st.session_state.tracked)
met_eta = sum(1 for m in st.session_state.tracked if vdata.get(m, {}).get("eta", "—") != "—")
naar_be = sum(1 for m in st.session_state.tracked
              if any(k in (vdata.get(m, {}).get("destination") or "").upper()
                     for k in ANTP_KW + ZBEE_KW))

c1, c2, c3, c4 = st.columns(4)
c1.metric("Gevolgd", total)
c2.metric("Met ETA", met_eta)
c3.metric("→ BEANR / BEZEE", naar_be)
c4.metric("Update", last_fetch.split(" ")[1] if " " in last_fetch else "—")

st.markdown(f'<div class="refresh-info">Laatste update: {last_fetch} · VesselFinder AIS</div>',
            unsafe_allow_html=True)
st.markdown("---")


# ── Scheepskaarten ────────────────────────────────────────────────────────────
for mmsi, info in st.session_state.tracked.items():
    v = vdata.get(mmsi, {})
    if v.get("error"):
        st.markdown(f"""
<div class="vessel-card error">
    <div class="vessel-name">{info.get('name','—')} <span style="color:#6b7280;font-size:0.78rem">· {mmsi}</span></div>
    <div style="color:#ef4444;font-size:0.8rem;font-family:'IBM Plex Mono',monospace">⚠️ {v['error']}</div>
    <a class="vf-link" href="https://www.vesselfinder.com/vessels/details/{mmsi}" target="_blank">↗ VesselFinder</a>
</div>""", unsafe_allow_html=True)
        continue

    dest    = v.get("destination") or "—"
    eta     = v.get("eta") or "—"
    dest_up = dest.upper()
    is_be   = any(k in dest_up for k in ANTP_KW + ZBEE_KW)

    # Port label
    if any(k in dest_up for k in ANTP_KW):
        port_badge = '<span class="badge badge-be">→ Antwerpen</span>'
    elif any(k in dest_up for k in ZBEE_KW):
        port_badge = '<span class="badge badge-be">→ Zeebrugge</span>'
    elif dest != "—":
        port_badge = f'<span class="badge badge-dest">→ {dest}</span>'
    else:
        port_badge = ""

    eta_html  = f'<span class="badge badge-eta">ETA {eta}</span>' if eta != "—" else ""
    stat_html = f'<span class="badge badge-stat">{v.get("status","")}</span>' if v.get("status","—") != "—" else ""
    speed_txt = f' · {v["speed"]} kn' if v.get("speed","—") != "—" else ""
    lp_txt    = f'Vorige haven: {v["last_port"]}' if v.get("last_port","—") != "—" else ""
    card_css  = "towards" if is_be else ("other" if dest != "—" else "")

    st.markdown(f"""
<div class="vessel-card {card_css}">
    <a class="vf-link" href="{v.get('url','#')}" target="_blank">↗ VesselFinder</a>
    <div class="vessel-name">{v.get('name') or info.get('name','—')}</div>
    <div class="vessel-meta">MMSI {mmsi} · {v.get('type','—')} · {v.get('flag','—')}{speed_txt} · {v.get('scraped_at','—')}</div>
    <div>{eta_html}{port_badge}{stat_html}</div>
    <div class="detail-line">{lp_txt}</div>
</div>""", unsafe_allow_html=True)


# ── Tabel + export ────────────────────────────────────────────────────────────
if show_table:
    st.markdown("---")
    st.subheader("📋 Overzichtstabel")
    rows = []
    for mmsi, info in st.session_state.tracked.items():
        v    = vdata.get(mmsi, {})
        dest = v.get("destination") or "—"
        rows.append({
            "Naam":         v.get("name") or info.get("name","—"),
            "MMSI":         mmsi,
            "Bestemming":   dest,
            "→ BE":         "✅" if any(k in dest.upper() for k in ANTP_KW + ZBEE_KW) else "—",
            "ETA":          v.get("eta","—"),
            "Status":       v.get("status","—"),
            "Snelheid":     v.get("speed","—"),
            "Vorige haven": v.get("last_port","—"),
            "Update":       v.get("scraped_at","—"),
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ Download CSV",
        df.to_csv(index=False).encode("utf-8"),
        f"dkm_tracker_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv",
        "text/csv",
    )

if auto_refresh:
    time.sleep(60)
    st.session_state.vessel_data = {}
    st.rerun()
