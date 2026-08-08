import streamlit as st
import pandas as pd
from io import BytesIO

# ------------------------------------------------------------
# CONFIGURAZIONE PAGINA
# ------------------------------------------------------------
st.set_page_config(
    page_title="Calcolatore Emissioni GHG (Dual Reporting)",
    page_icon="🌍",
    layout="wide"
)

# ------------------------------------------------------------
# STILE BASE (CSS LEGGERO)
# ------------------------------------------------------------
CUSTOM_CSS = """
<style>
    .main {
        padding-top: 1rem;
    }
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    h1, h2, h3, h4 {
        color: #1B2A41;
    }
    .footer-text {
        text-align: center;
        color: #555555;
        font-size: 12px;
        margin-top: 20px;
    }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ------------------------------------------------------------
# LOGO E INTESTAZIONE
# ------------------------------------------------------------
header_col1, header_col2 = st.columns([1, 3])

with header_col1:
    try:
        st.image("Crowe-Bompani.png", use_container_width=True)
    except FileNotFoundError:
        st.warning(
            "Logo non trovato. Assicurati di aver caricato 'Crowe-Bompani.png' nella repository.")

with header_col2:
    st.title("Calcolatore Emissioni GHG: Dual Reporting Scope 1 e 2")
    st.caption("Versione Beta 0.2 - Strumento in fase di test e validazione")

# ------------------------------------------------------------
# GUIDA E RIFERIMENTI (SIDEBAR)
# ------------------------------------------------------------
st.sidebar.header("Guida rapida")
st.sidebar.markdown(
    """
    Questo strumento supporta la rendicontazione delle emissioni in linea con il **GHG Protocol**.

    **Scope di riferimento**
    - Scope 1: emissioni dirette da combustione di fonti di proprietà o controllate[cite: 8].
    - Scope 2: emissioni indirette da energia acquistata (elettricità e calore)[cite: 8].

    **Dual Reporting (Scope 2)**
    - *Location-based*: utilizza fattori medi nazionali (es. ISPRA)[cite: 1].
    - *Market-based*: utilizza fattori specifici del fornitore di energia[cite: 1].
    """
)

st.sidebar.markdown("---")
st.sidebar.subheader("Note metodologiche")
st.sidebar.markdown(
    """
    - Le emissioni evitate non vanno usate per compensare gli inventari Scope 1, 2 o 3, ma rendicontate separatamente[cite: 2].
    - La CO2 biogenica è riportata come informazione aggiuntiva e non sommata agli Scope principali[cite: 8].
    """
)

# ------------------------------------------------------------
# DATABASE FATTORI DI EMISSIONE
# ------------------------------------------------------------
DB_FATTORI = {
    # --- SCOPE 2 ---
    # Fattore Location-based ISPRA medio: 199.6 gCO2eq/kWh -> 0.0001996 tCO2eq/kWh
    "Energia Elettrica (Rete)": {
        "scope": "Scope 2",
        "unita_fe": "kWh",
        "fe_loc": 199.6 / 1_000_000,  # tCO2eq per kWh
        "unita_default": "kWh",
    },
    "Calore / Vapore / Raffrescamento (Telereti)": {
        "scope": "Scope 2",
        "unita_fe": "kWh",
        "fe_loc": 0.0,  # da impostare tramite fattore fornito
        "richiede_fe_fornitore": True,
        "unita_default": "kWh",
    },

    # --- SCOPE 1 FOSSILE ---
    "Gas Naturale (Metano)": {
        "scope": "Scope 1",
        "unita_fe": "1000_stdm3",
        "fe": 2.026,
        "unita_default": "Stdm3",
    },
    "Gasolio Autotrazione": {
        "scope": "Scope 1",
        "unita_fe": "t",
        "fe": 3.150,
        "densita_kg_l": 0.84,
        "unita_default": "Litri",
    },
    "Gasolio Riscaldamento": {
        "scope": "Scope 1",
        "unita_fe": "t",
        "fe": 3.169,
        "densita_kg_l": 0.84,
        "unita_default": "Litri",
    },
    "Benzina senza piombo": {
        "scope": "Scope 1",
        "unita_fe": "t",
        "fe": 3.152,
        "densita_kg_l": 0.74,
        "unita_default": "Litri",
    },
    "GPL": {
        "scope": "Scope 1",
        "unita_fe": "t",
        "fe": 3.026,
        "densita_kg_l": 0.54,
        "unita_default": "Litri",
    },
    "Olio Combustibile Leggero": {
        "scope": "Scope 1",
        "unita_fe": "t",
        "fe": 3.143,
        "densita_kg_l": 0.94,
        "unita_default": "Litri",
    },
    "Kerosene (altro da avio)": {
        "scope": "Scope 1",
        "unita_fe": "t",
        "fe": 3.149,
        "densita_kg_l": 0.80,
        "unita_default": "Litri",
    },
    "Carbone da vapore": {
        "scope": "Scope 1",
        "unita_fe": "TJ",
        "fe": 92.952,
        "pci_gj_t": 24.854,
        "unita_default": "t",
    },

    # --- EMISSIONI BIOGENICHE (Fuori Scope) ---
    "Biomassa Solida (Legna/Pellet)": {
        "scope": "Fuori Scope (Biogenico)",
        "unita_fe": "TJ",
        "fe": 102.773,
        "pci_gj_t": 15.242,
        "unita_default": "kg",
    },
    "Biogas": {
        "scope": "Fuori Scope (Biogenico)",
        "unita_fe": "TJ",
        "fe": 53.400,
        "pci_gj_t": 50.358,
        "unita_default": "Stdm3",
    },
    "Bioliquidi": {
        "scope": "Fuori Scope (Biogenico)",
        "unita_fe": "TJ",
        "fe": 77.366,
        "pci_gj_t": 28.556,
        "unita_default": "Litri",
    },
    "FAME (Biodiesel)": {
        "scope": "Fuori Scope (Biogenico)",
        "unita_fe": "TJ",
        "fe": 75.659,
        "pci_gj_t": 37.405,
        "densita_kg_l": 0.85,
        "unita_default": "Litri",
    },
}

UNITA_MAP = {
    "kWh": ["kWh", "MWh", "GJ", "TJ"],
    "1000_stdm3": ["Stdm3", "Nm3", "1000_Stdm3"],
    "t": ["t", "kg", "Litri"],
    "TJ": ["TJ", "GJ", "t", "kg", "Litri", "Stdm3", "Nm3"],
}


# ------------------------------------------------------------
# FUNZIONI DI SUPPORTO
# ------------------------------------------------------------
def converti_in_unita_base(valore: float, unita_input: str, info: dict) -> float:
    """Converte il valore inserito dall'utente nell'unità base utilizzata per il fattore di emissione."""

    unita_base = info["unita_fe"]
    valore_calcolo = valore

    if unita_base == "kWh":
        if unita_input == "MWh":
            valore_calcolo = valore * 1000
        elif unita_input == "GJ":
            valore_calcolo = valore * 277.778
        elif unita_input == "TJ":
            valore_calcolo = valore * 277_778

    elif unita_base == "1000_stdm3":
        if unita_input == "Nm3":
            valore_calcolo = (valore * 1.0549) / 1000
        elif unita_input == "Stdm3":
            valore_calcolo = valore / 1000

    elif unita_base == "t":
        if unita_input == "kg":
            valore_calcolo = valore / 1000
        elif unita_input == "Litri":
            valore_calcolo = (valore * info.get("densita_kg_l", 1.0)) / 1000

    elif unita_base == "TJ":
        if unita_input == "GJ":
            valore_calcolo = valore / 1000
        elif unita_input in ["Stdm3", "Nm3"]:
            vol_stdm3 = valore if unita_input == "Stdm3" else valore * 1.0549
            valore_calcolo = (vol_stdm3 / 1000) * (info.get("pci_gj_t", 0.0) / 1000)
        elif unita_input in ["t", "kg", "Litri"]:
            massa_ton = valore
            if unita_input == "kg":
                massa_ton = valore / 1000
            elif unita_input == "Litri":
                massa_ton = (valore * info.get("densita_kg_l", 1.0)) / 1000
            valore_calcolo = massa_ton * (info.get("pci_gj_t", 0.0) / 1000)

    return valore_calcolo


def calcola_emissioni(valore_base: float, info_vettore: dict, fe_market_input: float) -> tuple[float, float]:
    """Calcola le emissioni Location-based e Market-based in tCO2eq."""

    scope = info_vettore["scope"]
    em_loc = 0.0
    em_mkt = 0.0

    if scope == "Scope 2":
        # Location-based: utilizza il fattore predefinito se presente (es. ISPRA per elettricità)
        fe_loc = info_vettore.get("fe_loc", 0.0)
        em_loc = valore_base * fe_loc

        # Market-based: utilizza sempre il fattore fornito dall'utente (gCO2eq/kWh -> tCO2eq/kWh)
        em_mkt = valore_base * (fe_market_input / 1_000_000)

    elif scope in ["Scope 1", "Fuori Scope (Biogenico)"]:
        # Per Scope 1 e biomassa: il fattore è espresso direttamente in tCO2eq per unità base
        fe = info_vettore.get("fe", 0.0)
        em_loc = valore_base * fe
        em_mkt = em_loc

    return em_loc, em_mkt


# ------------------------------------------------------------
# STATO DI SESSIONE
# ------------------------------------------------------------
if "record" not in st.session_state:
    st.session_state.record = []


# ------------------------------------------------------------
# SEZIONE: INSERIMENTO DATI
# ------------------------------------------------------------
st.header("Inserimento dati energetici")

input_col1, input_col2, input_col3 = st.columns(3)

with input_col1:
    vettore = st.selectbox("Combustibile / Fonte energetica", list(DB_FATTORI.keys()))
    info_vettore = DB_FATTORI[vettore]

with input_col2:
    unita_ammesse = UNITA_MAP[info_vettore["unita_fe"]].copy()
    # Rimuove Litri se non è disponibile la densità
    if "Litri" in unita_ammesse and "densita_kg_l" not in info_vettore:
        unita_ammesse.remove("Litri")

    default_unit = info_vettore.get("unita_default", unita_ammesse[0])
    default_idx = unita_ammesse.index(default_unit) if default_unit in unita_ammesse else 0
    unita = st.selectbox("Unità di misura del dato", unita_ammesse, index=default_idx)

with input_col3:
    valore = st.number_input(
        f"Quantità ({unita})",
        min_value=0.0,
        value=0.0,
        step=100.0,
    )

st.markdown("---")

# ------------------------------------------------------------
# SEZIONE: PARAMETRI MARKET-BASED (SCOPE 2)
# ------------------------------------------------------------
fe_market_input = 0.0

if info_vettore["scope"] == "Scope 2":
    mb_col1, mb_col2 = st.columns([2, 1])

    with mb_col1:
        st.subheader("Parametri per il Dual Reporting (Scope 2)")
        if vettore == "Energia Elettrica (Rete)":
            st.markdown(
                """
                **Location-based:** viene applicato il fattore medio nazionale ISPRA pari a 199.6 gCO2eq/kWh (0.0001996 tCO2eq/kWh).

                **Market-based:** inserire il fattore di emissione fornito dal proprio fornitore di energia (Residual Mix AIB o valore contrattuale). 
                In caso di acquisto di energia 100% rinnovabile con Garanzie d'Origine, impostare il fattore a 0.
                """
            )
        else:
            st.markdown(
                """
                Per calore, vapore o raffrescamento da telereti, il fattore Location-based dipende dal dato fornito dal gestore della rete.

                Inserire di seguito il fattore di emissione contrattuale in gCO2eq/kWh per la rendicontazione Market-based.
                """
            )

    with mb_col2:
        default_fe = 199.6 if vettore == "Energia Elettrica (Rete)" else 0.0
        fe_market_input = st.number_input(
            "Fattore di emissione Market-based (gCO2eq/kWh)",
            min_value=0.0,
            value=default_fe,
            step=10.0,
        )

st.markdown("---")

# ------------------------------------------------------------
# AZIONE: CALCOLO E REGISTRAZIONE
# ------------------------------------------------------------
if st.button("Calcola e aggiungi al registro"):
    if valore <= 0:
        st.error("Inserire una quantità maggiore di zero.")
    else:
        try:
            valore_base = converti_in_unita_base(valore, unita, info_vettore)
            em_loc, em_mkt = calcola_emissioni(valore_base, info_vettore, fe_market_input)

            st.session_state.record.append({
                "Fonte energetica": vettore,
                "Quantità inserita": valore,
                "Unità": unita,
                "Valore convertito": round(valore_base, 4),
                "Unità ISPRA": info_vettore["unita_fe"],
                "Categoria": info_vettore["scope"],
                "Emissioni Location-based (tCO2eq)": round(em_loc, 4),
                "Emissioni Market-based (tCO2eq)": round(em_mkt, 4),
            })

            st.success("Dato acquisito correttamente nel registro.")
        except Exception as e:
            st.error(f"Errore nel calcolo: {e}")


# ------------------------------------------------------------
# SEZIONE: REPORT, RIEPILOGO E GESTIONE DATI
# ------------------------------------------------------------
if st.session_state.record:
    st.header("Registro dati e report")

    df = pd.DataFrame(st.session_state.record)
    df.index = df.index + 1

    st.subheader("Registro analitico")
    st.dataframe(df, use_container_width=True)

    # Riepilogo per categoria
    t_scope1 = df[df["Categoria"] == "Scope 1"]["Emissioni Location-based (tCO2eq)"].sum()
    t_scope2_loc = df[df["Categoria"] == "Scope 2"]["Emissioni Location-based (tCO2eq)"].sum()
    t_scope2_mkt = df[df["Categoria"] == "Scope 2"]["Emissioni Market-based (tCO2eq)"].sum()
    t_bio = df[df["Categoria"] == "Fuori Scope (Biogenico)"]["Emissioni Location-based (tCO2eq)"].sum()

    st.subheader("Riepilogo per categoria di emissione")
    sum_col1, sum_col2, sum_col3 = st.columns(3)

    sum_col1.metric("Totale Scope 1 (fossile)", f"{round(t_scope1, 3)} tCO2eq")
    sum_col2.metric("Totale Scope 2 (Location-based)", f"{round(t_scope2_loc, 3)} tCO2eq")
    sum_col3.metric("Totale Scope 2 (Market-based)", f"{round(t_scope2_mkt, 3)} tCO2eq")

    st.subheader("Inventario aziendale Scope 1 + Scope 2")
    inv_col1, inv_col2 = st.columns(2)

    inv_col1.info(
        f"Totale aziendale (Location-based): {round(t_scope1 + t_scope2_loc, 3)} tCO2eq"
    )
    inv_col2.success(
        f"Totale aziendale (Market-based): {round(t_scope1 + t_scope2_mkt, 3)} tCO2eq"
    )

    st.warning(
        f"CO2 biogenica (fuori Scope): {round(t_bio, 3)} tCO2eq. "
        "La CO2 derivante da biomasse deve essere riportata separatamente e non sommata agli Scope principali."
    )

    st.markdown("---")

    # Gestione dati (rimozione righe)
    st.subheader("Gestione del registro")
    manage_col1, manage_col2, manage_col3 = st.columns([3, 1, 1])

    with manage_col1:
        opzioni_eliminazione = [
            f"Riga {i + 1}: {r['Fonte energetica']} ({r['Quantità inserita']} {r['Unità']})"
            for i, r in enumerate(st.session_state.record)
        ]
        riga_da_eliminare = st.selectbox(
            "Seleziona la riga da cancellare", opzioni_eliminazione
        )

    with manage_col2:
        st.write("")
        st.write("")
        if st.button("Rimuovi riga selezionata", use_container_width=True):
            indice_da_eliminare = opzioni_eliminazione.index(riga_da_eliminare)
            st.session_state.record.pop(indice_da_eliminare)
            st.rerun()

    with manage_col3:
        st.write("")
        st.write("")
        if st.button("Svuota registro", use_container_width=True):
            st.session_state.record = []
            st.rerun()

    st.markdown("---")

    # Esportazione Excel
    st.subheader("Esportazione report in Excel")

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="GHG_Dual_Report")
    output.seek(0)

    st.download_button(
        label="Scarica report Excel",
        data=output,
        file_name="GHG_Dual_Report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# ------------------------------------------------------------
# FOOTER
# ------------------------------------------------------------
st.markdown("---")

st.markdown("#### Fonti e riferimenti normativi")
st.caption(
    "1. GHG Protocol Scope 2 Guidance: metodologia per il calcolo delle emissioni indirette da energia acquistata (Dual Reporting)[cite: 1]."
)
st.caption(
    "2. GHG Protocol Corporate Value Chain (Scope 3) Accounting & Reporting Standard: categorizzazione delle emissioni indirette lungo la catena del valore (es. perdite T&D)[cite: 8]."
)
st.caption(
    "3. WRI Working Paper - Estimating and Reporting the Comparative Emissions Impacts of Products: linee guida sulla rendicontazione separata degli impatti comparativi e delle emissioni evitate[cite: 2]."
)

st.markdown(
    "<p class='footer-text'>Strumento sviluppato da <strong>Alessio Morgante</strong> | Versione Beta 0.2</p>",
    unsafe_allow_html=True,
)
