# DKM Vessel Tracker

Streamlit apps voor vessel tracking en ETA opvolging via de Data Docked AIS API.

---

## Apps in deze repo

| Bestand | Wat |
|---|---|
| `datadocked_tester.py` | Test je Data Docked API key + bekijk ruwe response |
| `vessel_tracker.py` | Volg specifieke schepen op via MMSI (VesselFinder scraping) |

---

## Vereisten

- Python 3.9 of hoger
- Git

---

## Installatie & lokaal draaien

### 1. Repo clonen

```bash
git clone https://github.com/JOUW-GEBRUIKERSNAAM/dkm-vessel-tracker.git
cd dkm-vessel-tracker
```

### 2. Virtuele omgeving aanmaken (aanbevolen)

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Mac/Linux:**
```bash
python -m venv venv
source venv/bin/activate
```

### 3. Packages installeren

```bash
pip install -r requirements.txt
```

### 4. API key instellen

Maak de map `.streamlit` aan en maak daarin een bestand `secrets.toml`:

```bash
# Windows
mkdir .streamlit
copy .streamlit\secrets.toml.example .streamlit\secrets.toml

# Mac/Linux
mkdir -p .streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Open `.streamlit/secrets.toml` en vul je Data Docked API key in:

```toml
[datadocked]
api_key = "jouw_echte_api_key_hier"
```

> ⚠️ `secrets.toml` staat in `.gitignore` en wordt **nooit** naar GitHub gepusht.

### 5. App starten

**API tester:**
```bash
streamlit run datadocked_tester.py
```

**Vessel tracker:**
```bash
streamlit run vessel_tracker.py
```

De app opent automatisch in je browser op `http://localhost:8501`

---

## Deployen op Streamlit Cloud (optioneel)

1. Push deze repo naar GitHub
2. Ga naar [share.streamlit.io](https://share.streamlit.io)
3. Klik **New app** → kies je repo → kies het gewenste `.py` bestand
4. Ga naar **Settings → Secrets** en voeg toe:
   ```toml
   [datadocked]
   api_key = "jouw_api_key"
   ```
5. Klik **Deploy**

> ⚠️ De `vessel_tracker.py` (VesselFinder scraping) werkt op Streamlit Cloud.  
> De `datadocked_tester.py` werkt ook op Streamlit Cloud mits de API key via Secrets is ingesteld.

---

## Deployen op Azure App Service (voor Oracle-verbinding later)

Zie de bestaande DKM Azure pipeline. Nieuwe Streamlit apps met Oracle-toegang draaien op Azure App Service, niet op Streamlit Cloud.

---

## Structuur

```
dkm-vessel-tracker/
├── datadocked_tester.py        # API key tester
├── vessel_tracker.py           # Vessel tracker (VesselFinder)
├── requirements.txt            # Python dependencies
├── .gitignore                  # Bestanden die niet naar GitHub gaan
└── .streamlit/
    └── secrets.toml.example    # Voorbeeld secrets (vul in en hernoem)
```

---

## Data bronnen

- **Data Docked** — [datadocked.com](https://datadocked.com) — AIS API (betaald, testaccount)
- **VesselFinder** — [vesselfinder.com](https://www.vesselfinder.com) — publieke website scraping

---

*DKM-Customs — intern tooling project*
