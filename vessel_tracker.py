"""
DKM Vessel Tracker
Zoek schepen op naam:
  1. Data Docked naam-zoekfunctie (1 credit)
  2. Fallback: VesselFinder zoekpagina (gratis scrape) → MMSI/IMO → Data Docked details
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
    .search-result.fallback { border-left-color: #f59e0b; }
    .search-result .sname { font-family:'IBM Plex Mono',monospace; font-weight:600; color:#e8eaf0; font-size:0.9rem; }
    .search-result .smeta { font-size:0.75rem; color:#6b7280; margin-top:0.15rem; font-family:'IBM Plex Mono',monospace; }
    .search-result .ssource { font-size:0.68rem; color:#4b5563; margin-top:0.2rem; }

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
    .credit-note { font-size:0.72rem; color:#4b5563; font-family:'IBM Plex Mono',monospace; }
    .source-tag { font-size:0.68rem; padding:0.15rem 0.5rem; border-radius:3px; margin-left:0.4rem; }
    .source-dd  { background:rgba(59,130,246,0.1); color:#60a5fa; border:1px solid rgba(59,130,246,0.2); }
    .source-vf  { background:rgba(245,158,11,0.1); color:#fbbf24; border:1px solid rgba(245,158,11,0.2); }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header-bar">
    <h1>🚢 DKM Vessel Tracker</h1>
    <span>Real-time ETA opvolging naar Antwerpen &amp; Zeebrugge</span>
</div>
""", unsafe_allow_html=True)

# ── Constanten ────────────────────────────────────────────────────────────────
DD_BASE  = "https://datadocked.com/api/vessels_operations"
ANTP_KW  = ["BEANR", "ANTWERP", "ANTWERPEN", "ANR"]
ZBEE_KW  = ["BEZEE", "ZEEBRUGGE", "ZEEBRUG"]

VF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

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


# ── Data Docked hulpfuncties ──────────────────────────────────────────────────
def dd_get(path: str, params: dict, api_key: str):
    try:
        return requests.get(
            f"{DD_BASE}/{path}", params=params,
            headers={"accept": "application/json", "x-api-key": api_key},
            timeout=15,
        )
    except Exception:
        return None


def dd_search_name(name: str, api_key: str) -> list:
    """Zoek via Data Docked naam endpoint (1 credit)."""
    r = dd_get("vessels-by-vessel-name", {"vessel_name": name.upper()}, api_key)
    if not r or r.status_code != 200:
        return []
    data = r.json()
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        inner = data.get("detail") or data.get("vessels") or data.get("results") or []
        if isinstance(inner, list):
            return inner
        if isinstance(inner, dict):
            return [inner]
    return []


def dd_fetch_vessel(ident: str, api_key: str) -> dict:
    """Haal volledige scheepsdata op via Data Docked (5 credits)."""
    r = dd_get("get-vessel-info", {"imo_or_mmsi": ident}, api_key)
    if r is None:
        return {"error": "Geen verbinding met Data Docked"}
    if r.status_code == 404:
        return {"error": "Schip niet gevonden"}
    if r.status_code == 401:
        return {"error": "API key ongeldig"}
    if r.status_code == 403:
        return {"error": "Geen toegang (credits op of plan limiet)"}
    if r.status_code != 200:
        return {"error": f"HTTP {r.status_code}"}
    data = r.json()
    return data.get("detail", data)


# ── VesselFinder fallback zoekfunctie ─────────────────────────────────────────
def vf_search_name(name: str) -> list:
    """
    Zoek schepen op naam via VesselFinder zoekpagina.
    Haalt MMSI/IMO op uit de URL-structuur van de resultaten.
    Gratis, geen credits.
    """
    url = f"https://www.vesselfinder.com/vessels?name={requests.utils.quote(name.upper())}"
    try:
        r = requests.get(url, headers=VF_HEADERS, timeout=12)
        r.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]

        # Patroon 1: /vessels/details/371218000
        m1 = re.search(r"/vessels/details/(\d{7,9})", href)
        # Patroon 2: /vessels/MSC-EVA-IMO-9401130-MMSI-371218000
        m2 = re.search(r"MMSI[_-](\d{9})", href, re.I)
        # Patroon 3: ?mmsi=371218000
        m3 = re.search(r"[?&]mmsi=(\d{9})", href, re.I)

        mmsi_match = m2 or m3 or (m1 if m1 and len(m1.group(1)) == 9 else None)
        imo_match  = re.search(r"IMO[_-](\d{7})", href, re.I)

        if not mmsi_match and not imo_match:
            continue

        mmsi = mmsi_match.group(1) if mmsi_match else ""
        imo  = imo_match.group(1)  if imo_match  else ""
        uid  = mmsi or imo

        if not uid or uid in seen:
            continue
        seen.add(uid)

        vessel_name = a.get_text(strip=True).upper()
        if len(vessel_name) < 2 or vessel_name.lower() in ("details", "more", "info"):
            continue

        results.append({
            "name":   vessel_name,
            "mmsi":   mmsi,
            "imo":    imo,
            "source": "VesselFinder",
            "url":    f"https://www.vesselfinder.com/vessels/details/{mmsi or imo}",
        })

    return results[:15]


# ── Gecombineerde zoekfunctie ─────────────────────────────────────────────────
def smart_search(name: str, api_key: str) -> tuple[list, str]:
    """
    Zoek eerst via Data Docked. Als leeg → fallback naar VesselFinder.
    Geeft (resultaten, bron) terug.
    """
    # Stap 1: Data Docked
    dd_results = dd_search_name(name, api_key)
    if dd_results:
        for r in dd_results:
            r["source"] = "Data Docked"
        return dd_results, "datadocked"

    # Stap 2: VesselFinder fallback
    vf_results = vf_search_name(name)
    if vf_results:
        return vf_results, "vesselfinder"

    return [], "none"


def dest_info(dest: str, unlocode: str) -> tuple:
    combined = (dest + " " + unlocode).upper()
    if any(k in combined for k in ANTP_KW):
        return "Antwerpen", "towards"
    if any(k in combined for k in ZBEE_KW):
        return "Zeebrugge", "towards"
    if dest and dest not in ("—", "-", ""):
        return dest, "other"
    return "", ""


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔑 API Key")
    try:
        default_key = st.secrets["datadocked"]["api_key"]
    except Exception:
        default_key = ""

    api_key = st.text_input(
        "Data Docked API Key",
        value=default_key,
        type="password",
        placeholder="Jouw key hier",
    )

    st.markdown("---")
    st.markdown("### 🔍 Schip zoeken op naam")
    naam_input = st.text_input(
        "Scheepsnaam",
        placeholder="bv.  MSC EVA  of  ONTARIO",
        label_visibility="collapsed",
    )
    zoek_btn = st.button("🔍 Zoeken", type="primary", use_container_width=True)
    st.markdown('<div class="credit-note">↳ 1 credit · fallback via VesselFinder bij geen resultaat</div>',
                unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("##### of direct via nummer")
    nr_input   = st.text_input("MMSI of IMO", placeholder="371218000", label_visibility="collapsed")
    add_nr_btn = st.button("＋ Toevoegen", use_container_width=True)

    st.markdown("---")

    # Gevolgde schepen
    if st.session_state.tracked:
        st.markdown('<div class="tracked-label">Gevolgde schepen</div>', unsafe_allow_html=True)
        to_remove = []
        for ident, info in list(st.session_state.tracked.items()):
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(
                    f"<small style='font-family:IBM Plex Mono,monospace;color:#9ca3af'>"
                    f"{info.get('name','—')[:22]}<br>"
                    f"<span style='color:#4b5563'>{ident}</span></small>",
                    unsafe_allow_html=True,
                )
            with c2:
                if st.button("×", key=f"rm_{ident}"):
                    to_remove.append(ident)
        for m in to_remove:
            del st.session_state.tracked[m]
            st.session_state.vessel_data.pop(m, None)
            st.rerun()

        st.markdown("")
        cr, cc = st.columns(2)
        with cr:
            if st.button("🔄 Ververs", use_container_width=True):
                st.session_state.vessel_data = {}
                st.rerun()
        with cc:
            if st.button("🗑 Wis alles", use_container_width=True):
                st.session_state.tracked     = {}
                st.session_state.vessel_data = {}
                st.rerun()

    st.markdown("---")
    show_table   = st.checkbox("Toon als tabel", value=True)
    auto_refresh = st.checkbox("Auto-refresh (60s)", value=False)


# ── API key check ─────────────────────────────────────────────────────────────
if not api_key:
    st.warning("👈 Vul je Data Docked API key in de sidebar in.")
    st.stop()


# ── Direct toevoegen via nummer ───────────────────────────────────────────────
if add_nr_btn and nr_input.strip():
    nr = nr_input.strip()
    if nr.isdigit() and len(nr) in (7, 9):
        st.session_state.tracked[nr] = {"name": f"#{nr}", "mmsi": nr}
        st.session_state.search_results = []
        st.rerun()
    else:
        st.sidebar.warning("MMSI = 9 cijfers, IMO = 7 cijfers.")


# ── Zoeken op naam ────────────────────────────────────────────────────────────
if zoek_btn and naam_input.strip():
    with st.spinner(f"Zoeken naar '{naam_input}'..."):
        results, source = smart_search(naam_input.strip(), api_key)
    st.session_state.search_results = results
    st.session_state.last_search    = naam_input.strip()
    st.session_state["search_source"] = source

    if not results:
        st.warning(
            f"**'{naam_input}' niet gevonden** via Data Docked én VesselFinder. "
            f"Probeer een kortere naam (bv. `MSC EVA` → `EVA`) of zoek het MMSI/IMO op via "
            f"[VesselFinder](https://www.vesselfinder.com/vessels?name={requests.utils.quote(naam_input)}) "
            f"en voeg het direct toe via het nummerveld."
        )


# ── Zoekresultaten weergeven ──────────────────────────────────────────────────
if st.session_state.search_results:
    naam   = st.session_state.last_search
    res    = st.session_state.search_results
    source = st.session_state.get("search_source", "")

    source_label = (
        '<span class="source-tag source-dd">Data Docked</span>'
        if source == "datadocked"
        else '<span class="source-tag source-vf">VesselFinder fallback</span>'
    )

    if source == "vesselfinder":
        st.info(
            f"⚠️ **Data Docked vond niets voor '{naam}'** — "
            f"onderstaande resultaten komen van VesselFinder. "
            f"Details ophalen kost nog steeds 5 credits per schip."
        )

    st.markdown(
        f"**{len(res)} schip(en) gevonden voor '{naam}'** {source_label} "
        f"— klik **＋ Voeg toe** om te volgen:",
        unsafe_allow_html=True,
    )
    st.markdown("")

    for i, v in enumerate(res[:20]):
        name  = v.get("name", "—")
        mmsi  = str(v.get("mmsi", ""))
        imo   = str(v.get("imo", ""))
        vtype = v.get("shipType") or v.get("type", "")
        flag  = v.get("country") or v.get("flag", "")
        vsrc  = v.get("source", "")
        ident = mmsi or imo

        c_card, c_btn = st.columns([5, 1])
        with c_card:
            src_tag = (
                '<span class="source-tag source-vf">VF</span>'
                if vsrc == "VesselFinder"
                else '<span class="source-tag source-dd">DD</span>'
            )
            st.markdown(f"""
<div class="search-result {'fallback' if vsrc == 'VesselFinder' else ''}">
    <div class="sname">{name} {src_tag}</div>
    <div class="smeta">MMSI {mmsi or '—'} &nbsp;·&nbsp; IMO {imo or '—'} &nbsp;·&nbsp; {vtype} &nbsp;·&nbsp; {flag}</div>
</div>""", unsafe_allow_html=True)
        with c_btn:
            st.markdown("<div style='margin-top:0.4rem'></div>", unsafe_allow_html=True)
            already = ident in st.session_state.tracked
            if st.button(
                "✓ Toegev." if already else "＋ Voeg toe",
                key=f"add_{i}_{ident}",
                use_container_width=True,
                disabled=already,
            ):
                st.session_state.tracked[ident] = {
                    "name": name, "mmsi": mmsi, "imo": imo
                }
                st.rerun()

    if st.button("✖ Sluit zoekresultaten"):
        st.session_state.search_results = []
        st.rerun()
    st.markdown("---")


# ── Geen schepen gevolgd ──────────────────────────────────────────────────────
if not st.session_state.tracked:
    st.info("👈 Zoek een scheepsnaam links en voeg schepen toe aan je volglijst.")
    st.markdown("""
**Hoe werkt het?**
1. Typ een scheepsnaam links (bv. `MSC EVA` of `ONTARIO`)
2. Klik **🔍 Zoeken** — de app zoekt eerst via Data Docked, daarna automatisch via VesselFinder als fallback
3. Klik **＋ Voeg toe** op het juiste schip
4. Data wordt automatisch opgehaald — je ziet ETA, bestemming, status

Groene kaart = onderweg naar **Antwerpen** of **Zeebrugge** ✅
    """)
    st.stop()


# ── Data ophalen voor gevolgde schepen ────────────────────────────────────────
missing = [m for m in st.session_state.tracked if m not in st.session_state.vessel_data]

if missing:
    with st.spinner(f"Data ophalen voor {len(missing)} schip(en) ({len(missing) * 5} credits)..."):
        prog = st.progress(0)
        for i, ident in enumerate(missing):
            data = dd_fetch_vessel(ident, api_key)
            if data.get("name") and not data.get("error"):
                st.session_state.tracked[ident]["name"] = data["name"]
            st.session_state.vessel_data[ident] = data
            prog.progress((i + 1) / len(missing))
            if i < len(missing) - 1:
                time.sleep(0.3)
        prog.empty()
    st.session_state.last_fetch = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

vdata      = st.session_state.vessel_data
last_fetch = st.session_state.last_fetch or "—"


# ── KPI's ─────────────────────────────────────────────────────────────────────
total   = len(st.session_state.tracked)
met_eta = sum(1 for m in st.session_state.tracked
              if vdata.get(m, {}).get("etaUtc") not in (None, "", "-", "—"))
naar_be = sum(1 for m in st.session_state.tracked
              for v in [vdata.get(m, {})]
              if any(k in ((v.get("destination") or "") + " " + (v.get("unlocodeDestination") or "")).upper()
                     for k in ANTP_KW + ZBEE_KW))

c1, c2, c3, c4 = st.columns(4)
c1.metric("Gevolgd", total)
c2.metric("Met ETA", met_eta)
c3.metric("→ BEANR / BEZEE", naar_be)
c4.metric("Update", last_fetch.split(" ")[1] if " " in last_fetch else "—")

st.markdown(f'<div class="refresh-info">Laatste update: {last_fetch} · Data Docked AIS</div>',
            unsafe_allow_html=True)
st.markdown("---")


# ── Scheepskaarten ────────────────────────────────────────────────────────────
for ident, info in st.session_state.tracked.items():
    v = vdata.get(ident, {})

    if v.get("error"):
        st.markdown(f"""
<div class="vessel-card error">
    <div class="vessel-name">{info.get('name','—')} <span style="color:#6b7280;font-size:0.78rem">· {ident}</span></div>
    <div style="color:#ef4444;font-size:0.8rem;font-family:'IBM Plex Mono',monospace">⚠️ {v['error']}</div>
</div>""", unsafe_allow_html=True)
        continue

    name     = v.get("name")    or info.get("name", "—")
    dest     = v.get("destination") or "—"
    unlocode = v.get("unlocodeDestination") or ""
    eta      = v.get("etaUtc")  or "—"
    status   = v.get("navigationalStatus") or "—"
    speed    = v.get("speed")   or "—"
    flag     = v.get("country") or "—"
    vtype    = v.get("shipType") or "—"
    lastport = v.get("lastPort") or "—"
    mmsi     = v.get("mmsi") or ident
    imo      = v.get("imo") or ""

    port_label, card_css = dest_info(dest, unlocode)

    eta_html  = f'<span class="badge badge-eta">ETA {eta}</span>' if eta != "—" else ""
    stat_html = f'<span class="badge badge-stat">{status}</span>' if status != "—" else ""
    speed_txt = f' · {speed} kn' if speed != "—" else ""
    lp_txt    = f'Vorige haven: {lastport}' if lastport != "—" else ""

    if card_css == "towards":
        dest_html = f'<span class="badge badge-be">→ {port_label}</span>'
    elif dest != "—":
        dest_html = f'<span class="badge badge-dest">→ {dest}</span>'
    else:
        dest_html = ""

    vf_url = f"https://www.vesselfinder.com/vessels/details/{mmsi}" if mmsi else "#"

    st.markdown(f"""
<div class="vessel-card {card_css}">
    <a class="vf-link" href="{vf_url}" target="_blank">↗ VesselFinder</a>
    <div class="vessel-name">{name}</div>
    <div class="vessel-meta">MMSI {mmsi} · IMO {imo} · {vtype} · {flag}{speed_txt} · {last_fetch.split()[1] if ' ' in last_fetch else '—'}</div>
    <div>{eta_html}{dest_html}{stat_html}</div>
    <div class="detail-line">{lp_txt}</div>
</div>""", unsafe_allow_html=True)


# ── Tabel + export ────────────────────────────────────────────────────────────
if show_table:
    st.markdown("---")
    st.subheader("📋 Overzichtstabel")
    rows = []
    for ident, info in st.session_state.tracked.items():
        v    = vdata.get(ident, {})
        dest = v.get("destination") or "—"
        unlo = v.get("unlocodeDestination") or ""
        port_label, _ = dest_info(dest, unlo)
        rows.append({
            "Naam":          v.get("name") or info.get("name","—"),
            "MMSI":          v.get("mmsi") or ident,
            "IMO":           v.get("imo","—"),
            "Bestemming":    dest,
            "UNLOCODE":      unlo,
            "→ BE":          f"✅ {port_label}" if port_label in ("Antwerpen","Zeebrugge") else "—",
            "ETA (UTC)":     v.get("etaUtc","—"),
            "Status":        v.get("navigationalStatus","—"),
            "Snelheid (kn)": v.get("speed","—"),
            "Vorige haven":  v.get("lastPort","—"),
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ Download CSV",
        df.to_csv(index=False).encode("utf-8"),
        f"dkm_tracker_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv",
        "text/csv",
    )


# ── Auto-refresh ──────────────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(60)
    st.session_state.vessel_data = {}
    st.rerun()
