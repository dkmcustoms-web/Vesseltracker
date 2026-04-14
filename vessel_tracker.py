"""
DKM Vessel Tracker
- Zoek op naam, IMO (Lloyd's) of MMSI
- Toont ETA alleen als schip onderweg is naar Antwerpen of Zeebrugge
- Credits worden alleen gebruikt bij expliciet Ververs
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
    .search-result.vf { border-left-color:#f59e0b; }
    .sname { font-family:'IBM Plex Mono',monospace; font-weight:600; color:#e8eaf0; font-size:0.9rem; }
    .smeta { font-size:0.75rem; color:#6b7280; margin-top:0.15rem; font-family:'IBM Plex Mono',monospace; }

    /* Kaarten */
    .card {
        background:#1a1d27; border:1px solid #2a2d3a;
        border-left:4px solid #4b5563;
        border-radius:8px; padding:1.1rem 1.4rem; margin-bottom:0.7rem;
    }
    .card.towards { border-left-color:#10b981; }   /* onderweg naar BE */
    .card.other   { border-left-color:#f59e0b; }   /* andere bestemming */
    .card.pending { border-left-color:#3b82f6; opacity:0.7; }  /* nog niet geladen */
    .card.error   { border-left-color:#ef4444; opacity:0.6; }

    .cname { font-family:'IBM Plex Mono',monospace; font-size:1rem; font-weight:600; color:#e8eaf0; margin-bottom:0.25rem; }
    .cmeta { font-size:0.76rem; color:#6b7280; font-family:'IBM Plex Mono',monospace; margin-bottom:0.6rem; }
    .cbody { font-size:0.85rem; color:#d1d5db; }

    .eta-block {
        background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.25);
        border-radius:6px; padding:0.5rem 0.9rem; margin-top:0.5rem; display:inline-block;
    }
    .eta-label { font-size:0.68rem; color:#6b7280; text-transform:uppercase; letter-spacing:0.06em; }
    .eta-value { font-family:'IBM Plex Mono',monospace; font-size:1rem; font-weight:600; color:#34d399; }

    .not-be {
        background:rgba(245,158,11,0.08); border:1px solid rgba(245,158,11,0.2);
        border-radius:6px; padding:0.4rem 0.9rem; margin-top:0.5rem; display:inline-block;
        font-size:0.82rem; color:#fbbf24;
    }
    .pending-msg {
        font-size:0.82rem; color:#6b7280; font-style:italic; margin-top:0.3rem;
    }

    .badge { display:inline-block; padding:0.2rem 0.6rem; border-radius:4px; font-size:0.75rem;
             margin-right:0.3rem; font-family:'IBM Plex Mono',monospace; }
    .badge-stat { background:rgba(99,102,241,0.1); border:1px solid rgba(99,102,241,0.25); color:#a5b4fc; }
    .badge-speed { background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.2); color:#6ee7b7; }

    .vf-link { font-size:0.72rem; color:#4b5563; text-decoration:none; float:right; }
    .vf-link:hover { color:#D94F2B; }
    .refresh-info { font-size:0.73rem; color:#4b5563; font-family:'IBM Plex Mono',monospace; margin-bottom:0.8rem; }
    .src-dd { font-size:0.68rem; padding:0.1rem 0.45rem; border-radius:3px;
              background:rgba(59,130,246,0.1); color:#60a5fa; border:1px solid rgba(59,130,246,0.2); }
    .src-vf { font-size:0.68rem; padding:0.1rem 0.45rem; border-radius:3px;
              background:rgba(245,158,11,0.1); color:#fbbf24; border:1px solid rgba(245,158,11,0.2); }
    .tracked-lbl { font-size:0.69rem; color:#6b7280; text-transform:uppercase;
                   letter-spacing:0.08em; margin-bottom:0.35rem; }
    .credit-note { font-size:0.71rem; color:#4b5563; font-family:'IBM Plex Mono',monospace; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header-bar">
    <h1>🚢 DKM Vessel Tracker</h1>
    <span>ETA opvolging naar Antwerpen (BEANR) &amp; Zeebrugge (BEZEE)</span>
</div>
""", unsafe_allow_html=True)

# ── Constanten ────────────────────────────────────────────────────────────────
DD_BASE = "https://datadocked.com/api/vessels_operations"
ANTP_KW = ["BEANR", "ANTWERP", "ANTWERPEN", "ANR"]
ZBEE_KW = ["BEZEE", "ZEEBRUGGE", "ZEEBRUG"]

VF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Session state ─────────────────────────────────────────────────────────────
for k, v in [
    ("tracked",        {}),   # {ident: {name, mmsi, imo}}
    ("vessel_data",    {}),   # {ident: api dict | {"error":...} | None}
    ("search_results", []),
    ("last_search",    ""),
    ("search_source",  ""),
    ("last_fetch",     None),
]:
    if k not in st.session_state:
        st.session_state[k] = v


# ── API hulpfuncties ──────────────────────────────────────────────────────────
def dd_get(path, params, key):
    try:
        return requests.get(
            f"{DD_BASE}/{path}", params=params,
            headers={"accept": "application/json", "x-api-key": key},
            timeout=15,
        )
    except Exception:
        return None


def dd_fetch(ident, api_key):
    """Volledige scheepsdata ophalen — 5 credits."""
    r = dd_get("get-vessel-info", {"imo_or_mmsi": ident}, api_key)
    if r is None:           return {"error": "Geen verbinding"}
    if r.status_code == 401: return {"error": "API key ongeldig"}
    if r.status_code == 403: return {"error": "Geen toegang / credits op"}
    if r.status_code == 404: return {"error": "Schip niet gevonden"}
    if r.status_code != 200: return {"error": f"HTTP {r.status_code}"}
    data = r.json()
    return data.get("detail", data)


def dd_search(name, api_key):
    """Naam zoeken — 1 credit."""
    r = dd_get("vessels-by-vessel-name", {"vessel_name": name.upper()}, api_key)
    if not r or r.status_code != 200:
        return []
    data = r.json()
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        inner = data.get("detail") or data.get("vessels") or data.get("results") or []
        return inner if isinstance(inner, list) else [inner] if isinstance(inner, dict) else []
    return []


def vf_search(name):
    """VesselFinder naam-zoek als gratis fallback."""
    try:
        r = requests.get(
            f"https://www.vesselfinder.com/vessels?name={requests.utils.quote(name.upper())}",
            headers=VF_HEADERS, timeout=12,
        )
        r.raise_for_status()
    except Exception:
        return []

    soup  = BeautifulSoup(r.text, "html.parser")
    seen  = set()
    out   = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        m9   = re.search(r"/vessels/details/(\d{9})", href) or re.search(r"MMSI[_-](\d{9})", href, re.I)
        m7   = re.search(r"IMO[_-](\d{7})", href, re.I)
        mmsi = m9.group(1) if m9 else ""
        imo  = m7.group(1) if m7 else ""
        uid  = mmsi or imo
        if not uid or uid in seen:
            continue
        seen.add(uid)
        nm = a.get_text(strip=True).upper()
        if len(nm) < 3:
            continue
        out.append({"name": nm, "mmsi": mmsi, "imo": imo, "source": "VesselFinder"})

    return out[:15]


def smart_search(q, api_key):
    """Zoek via DD, fallback naar VF. Geeft (lijst, bron)."""
    res = dd_search(q, api_key)
    if res:
        for r in res:
            r["source"] = "Data Docked"
        return res, "dd"
    res = vf_search(q)
    return res, "vf"


def be_destination(dest, unlocode):
    """Geeft ('Antwerpen'|'Zeebrugge'|'') terug."""
    c = (dest + " " + unlocode).upper()
    if any(k in c for k in ANTP_KW): return "Antwerpen"
    if any(k in c for k in ZBEE_KW): return "Zeebrugge"
    return ""


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔑 API Key")
    try:
        default_key = st.secrets["datadocked"]["api_key"]
    except Exception:
        default_key = ""

    api_key = st.text_input(
        "Data Docked API Key", value=default_key,
        type="password", placeholder="Jouw key hier",
    )

    st.markdown("---")
    st.markdown("### 🔍 Zoeken")
    zoek_input = st.text_input(
        "Scheepsnaam, IMO of MMSI",
        placeholder="MSC EVA  ·  9401130  ·  371218000",
        label_visibility="collapsed",
    )
    zoek_btn = st.button("🔍 Zoeken", type="primary", use_container_width=True)
    st.markdown(
        '<div class="credit-note">'
        'Naam → 1 credit &nbsp;·&nbsp; IMO/MMSI → 0 credits<br>'
        'Data ophalen → 5 credits per schip (bij Ververs)'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # Gevolgde schepen lijst
    if st.session_state.tracked:
        st.markdown('<div class="tracked-lbl">Gevolgde schepen</div>', unsafe_allow_html=True)
        to_remove = []
        for ident, info in list(st.session_state.tracked.items()):
            c1, c2 = st.columns([5, 1])
            with c1:
                loaded = ident in st.session_state.vessel_data
                dot    = "🟢" if loaded else "⚪"
                st.markdown(
                    f"<small style='font-family:IBM Plex Mono,monospace;color:#9ca3af'>"
                    f"{dot} {info.get('name','—')[:20]}<br>"
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
            ververs_btn = st.button("🔄 Ververs", use_container_width=True, type="primary")
        with cc:
            if st.button("🗑 Wis alles", use_container_width=True):
                st.session_state.tracked     = {}
                st.session_state.vessel_data = {}
                st.rerun()

        if ververs_btn:
            st.session_state.vessel_data = {}
            st.rerun()
    else:
        ververs_btn = False

    st.markdown("---")
    show_table   = st.checkbox("Toon als tabel", value=True)
    auto_refresh = st.checkbox("Auto-refresh (60s)", value=False)


# ── API key check ─────────────────────────────────────────────────────────────
if not api_key:
    st.warning("👈 Vul je Data Docked API key in de sidebar in.")
    st.stop()


# ── Zoeklogica ────────────────────────────────────────────────────────────────
if zoek_btn and zoek_input.strip():
    q = zoek_input.strip()

    if q.isdigit() and len(q) in (7, 9):
        # IMO of MMSI — direct toevoegen, nog geen credits gebruiken
        label = "IMO" if len(q) == 7 else "MMSI"
        if q not in st.session_state.tracked:
            st.session_state.tracked[q] = {"name": f"{label} {q}", "mmsi": q if len(q)==9 else "", "imo": q if len(q)==7 else ""}
        st.session_state.search_results = []
        st.success(f"✅ {label} `{q}` toegevoegd — klik **🔄 Ververs** om data op te halen.")

    else:
        with st.spinner(f"Zoeken naar '{q}'..."):
            results, source = smart_search(q, api_key)
        st.session_state.search_results  = results
        st.session_state.last_search     = q
        st.session_state.search_source   = source

        if not results:
            vf_url = f"https://www.vesselfinder.com/vessels?name={requests.utils.quote(q)}"
            st.warning(
                f"**'{q}' niet gevonden.** "
                f"Probeer kortere naam of zoek het IMO/MMSI op via "
                f"[VesselFinder]({vf_url}) en plak het 7- of 9-cijferig nummer in de zoekbalk."
            )


# ── Zoekresultaten ────────────────────────────────────────────────────────────
if st.session_state.search_results:
    res    = st.session_state.search_results
    naam   = st.session_state.last_search
    source = st.session_state.search_source

    if source == "vf":
        st.info(f"⚠️ Data Docked vond niets voor **'{naam}'** — resultaten komen van VesselFinder.")

    src_tag = '<span class="src-dd">DD</span>' if source == "dd" else '<span class="src-vf">VF</span>'
    st.markdown(
        f"**{len(res)} schip(en) gevonden voor '{naam}'** {src_tag} "
        f"— klik **＋** om toe te voegen (data wordt pas geladen bij Ververs):",
        unsafe_allow_html=True,
    )
    st.markdown("")

    for i, v in enumerate(res[:20]):
        name  = v.get("name", "—")
        mmsi  = str(v.get("mmsi") or "")
        imo   = str(v.get("imo")  or "")
        vtype = v.get("shipType") or v.get("type", "")
        flag  = v.get("country")  or v.get("flag", "")
        ident = mmsi or imo
        vsrc  = v.get("source", "")

        c_card, c_btn = st.columns([5, 1])
        with c_card:
            tag = '<span class="src-vf">VF</span>' if vsrc == "VesselFinder" else '<span class="src-dd">DD</span>'
            st.markdown(f"""
<div class="search-result {'vf' if vsrc == 'VesselFinder' else ''}">
    <div class="sname">{name} {tag}</div>
    <div class="smeta">MMSI {mmsi or '—'} &nbsp;·&nbsp; IMO {imo or '—'} &nbsp;·&nbsp; {vtype} &nbsp;·&nbsp; {flag}</div>
</div>""", unsafe_allow_html=True)
        with c_btn:
            st.markdown("<div style='margin-top:0.4rem'></div>", unsafe_allow_html=True)
            already = ident in st.session_state.tracked
            if st.button(
                "✓" if already else "＋",
                key=f"add_{i}_{ident}",
                use_container_width=True,
                disabled=already,
            ):
                st.session_state.tracked[ident] = {"name": name, "mmsi": mmsi, "imo": imo}
                st.rerun()

    if st.button("✖ Sluit resultaten"):
        st.session_state.search_results = []
        st.rerun()
    st.markdown("---")


# ── Geen schepen gevolgd ──────────────────────────────────────────────────────
if not st.session_state.tracked:
    st.info("👈 Zoek een scheepsnaam of IMO/MMSI en voeg schepen toe.")
    st.markdown("""
**Hoe werkt het?**
1. Typ een **scheepsnaam** (bv. `MSC EVA`), **IMO/Lloyd's** (bv. `9401130`) of **MMSI** (bv. `371218000`)
2. Klik **🔍 Zoeken** en voeg het juiste schip toe
3. Klik **🔄 Ververs** om data op te halen (5 credits per schip)
4. Je ziet alleen een ETA als het schip **onderweg is naar Antwerpen of Zeebrugge**
    """)
    st.stop()


# ── Data ophalen — alleen bij expliciete Ververs of ontbrekende data ──────────
# Laad alleen als: er missing data is EN ververs is geklikt
# Bij eerste toevoeging: kaart tonen als "pending" zonder credits te gebruiken
missing_and_refresh = [
    m for m in st.session_state.tracked
    if m not in st.session_state.vessel_data
    and ververs_btn  # alleen bij expliciete klik
]

# Eerste keer ophalen na toevoegen: check of er al data is, zo niet toon pending
missing_nodata = [
    m for m in st.session_state.tracked
    if m not in st.session_state.vessel_data
]

# Auto-haal op als ververs geklikt
if ververs_btn or (missing_nodata and not ververs_btn and not st.session_state.vessel_data):
    te_laden = [m for m in st.session_state.tracked if m not in st.session_state.vessel_data]
    if te_laden:
        with st.spinner(f"Data ophalen voor {len(te_laden)} schip(en) ({len(te_laden) * 5} credits)..."):
            prog = st.progress(0)
            for i, ident in enumerate(te_laden):
                st.session_state.vessel_data[ident] = dd_fetch(ident, api_key)
                name = st.session_state.vessel_data[ident].get("name")
                if name and not st.session_state.vessel_data[ident].get("error"):
                    st.session_state.tracked[ident]["name"] = name
                prog.progress((i + 1) / len(te_laden))
                if i < len(te_laden) - 1:
                    time.sleep(0.3)
            prog.empty()
        st.session_state.last_fetch = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

vdata      = st.session_state.vessel_data
last_fetch = st.session_state.last_fetch or "—"


# ── KPI's ─────────────────────────────────────────────────────────────────────
total   = len(st.session_state.tracked)
geladen = sum(1 for m in st.session_state.tracked if m in vdata and not vdata[m].get("error"))
naar_be = sum(
    1 for m in st.session_state.tracked
    if m in vdata and be_destination(
        vdata[m].get("destination",""), vdata[m].get("unlocodeDestination","")
    )
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Gevolgd", total)
c2.metric("Geladen", geladen)
c3.metric("→ BEANR / BEZEE", naar_be)
c4.metric("Update", last_fetch.split(" ")[1] if " " in last_fetch else "—")

st.markdown(
    f'<div class="refresh-info">Laatste update: {last_fetch} · Data Docked AIS · '
    f'Klik 🔄 Ververs voor actuele data</div>',
    unsafe_allow_html=True,
)
st.markdown("---")


# ── Scheepskaarten ────────────────────────────────────────────────────────────
for ident, info in st.session_state.tracked.items():

    mmsi = info.get("mmsi") or ident
    vf_url = f"https://www.vesselfinder.com/vessels/details/{mmsi}" if mmsi else "#"

    # Nog niet geladen
    if ident not in vdata:
        st.markdown(f"""
<div class="card pending">
    <a class="vf-link" href="{vf_url}" target="_blank">↗ VesselFinder</a>
    <div class="cname">{info.get('name','—')}</div>
    <div class="cmeta">MMSI/IMO {ident}</div>
    <div class="pending-msg">⚪ Nog niet geladen — klik <strong>🔄 Ververs</strong> om data op te halen (5 credits)</div>
</div>""", unsafe_allow_html=True)
        continue

    v = vdata[ident]

    # Fout
    if v.get("error"):
        st.markdown(f"""
<div class="card error">
    <div class="cname">{info.get('name','—')} <span style="color:#6b7280;font-size:0.78rem">· {ident}</span></div>
    <div style="color:#ef4444;font-size:0.82rem;font-family:'IBM Plex Mono',monospace">⚠️ {v['error']}</div>
</div>""", unsafe_allow_html=True)
        continue

    # Gegevens
    name     = v.get("name")    or info.get("name", "—")
    dest     = v.get("destination")          or "—"
    unlocode = v.get("unlocodeDestination")  or ""
    eta      = v.get("etaUtc")               or ""
    status   = v.get("navigationalStatus")   or "—"
    speed    = v.get("speed")                or "—"
    flag     = v.get("country")              or "—"
    vtype    = v.get("shipType")             or "—"
    lastport = v.get("lastPort")             or "—"
    v_mmsi   = v.get("mmsi") or mmsi
    v_imo    = v.get("imo")  or info.get("imo","")

    port = be_destination(dest, unlocode)

    # Kaartkleur
    card_css = "towards" if port else ("other" if dest != "—" else "")

    # ETA blok: alleen tonen als bestemming Antwerpen of Zeebrugge is
    if port and eta:
        eta_html = f"""
<div class="eta-block">
    <div class="eta-label">ETA {port}</div>
    <div class="eta-value">{eta}</div>
</div>"""
    elif port and not eta:
        eta_html = f'<div class="eta-block"><div class="eta-label">ETA {port}</div><div class="eta-value" style="color:#9ca3af">Geen ETA in AIS</div></div>'
    else:
        # Andere bestemming — toon bestemming maar geen ETA
        eta_html = f'<div class="not-be">Huidige bestemming: <strong>{dest}</strong> — nog niet naar Antwerpen/Zeebrugge</div>'

    # Badges
    stat_badge  = f'<span class="badge badge-stat">{status}</span>'  if status != "—" else ""
    speed_badge = f'<span class="badge badge-speed">{speed} kn</span>' if speed  != "—" else ""
    lp_txt      = f'Vorige haven: {lastport}' if lastport != "—" else ""

    st.markdown(f"""
<div class="card {card_css}">
    <a class="vf-link" href="{vf_url}" target="_blank">↗ VesselFinder</a>
    <div class="cname">{name}</div>
    <div class="cmeta">MMSI {v_mmsi} &nbsp;·&nbsp; IMO {v_imo} &nbsp;·&nbsp; {vtype} &nbsp;·&nbsp; {flag}</div>
    <div>{stat_badge}{speed_badge}</div>
    {eta_html}
    <div class="detail-line" style="margin-top:0.5rem">{lp_txt}</div>
</div>""", unsafe_allow_html=True)


# ── Tabel ─────────────────────────────────────────────────────────────────────
if show_table and any(m in vdata for m in st.session_state.tracked):
    st.markdown("---")
    st.subheader("📋 Overzicht")
    rows = []
    for ident, info in st.session_state.tracked.items():
        v    = vdata.get(ident, {})
        dest = v.get("destination") or "—"
        unlo = v.get("unlocodeDestination") or ""
        port = be_destination(dest, unlo)
        eta  = v.get("etaUtc") or "—"
        rows.append({
            "Naam":         v.get("name") or info.get("name","—"),
            "MMSI":         v.get("mmsi") or ident,
            "IMO":          v.get("imo","—"),
            "→ BE":         f"✅ {port}" if port else "—",
            "Bestemming":   dest if not port else f"{port} ({unlo})",
            "ETA (UTC)":    eta if port else "—",
            "Status":       v.get("navigationalStatus","—"),
            "Snelheid (kn)":v.get("speed","—"),
            "Vorige haven": v.get("lastPort","—"),
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
if auto_refresh and st.session_state.vessel_data:
    time.sleep(60)
    st.session_state.vessel_data = {}
    st.rerun()
