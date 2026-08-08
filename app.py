import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Calcolatore Emissioni GHG (Dual Reporting)", page_icon="🌍", layout="wide")

# --- DATABASE FATTORI DI EMISSIONE ---
# Fonte FE Location-based: Tabella Parametri Standard Nazionali ISPRA (2022-2024 per il 2025)
# Fonte Densità: CDP Technical Note
DB_FATTORI = {
    # --- SCOPE 2 ---
    "Energia Elettrica (Rete)": {"scope": "Scope 2", "unita_fe": "kWh", "fe_loc": 192.6 / 1_000_000},
    "Calore / Vapore / Raffrescamento (Telereti)": {"scope": "Scope 2", "unita_fe": "kWh", "fe_loc": 0.0, "richiede_fe_fornitore": True},

    # --- SCOPE 1 FOSSILE ---
    "Gas Naturale (Metano)": {"scope": "Scope 1", "unita_fe": "1000_stdm3", "fe": 2.026},
    "Gasolio Autotrazione": {"scope": "Scope 1", "unita_fe": "t", "fe": 3.150, "densita_kg_l": 0.84},
    "Gasolio Riscaldamento": {"scope": "Scope 1", "unita_fe": "t", "fe": 3.169, "densita_kg_l": 0.84},
    "Benzina senza piombo": {"scope": "Scope 1", "unita_fe": "t", "fe": 3.152, "densita_kg_l": 0.74},
    "GPL": {"scope": "Scope 1", "unita_fe": "t", "fe": 3.026, "densita_kg_l": 0.54},
    "Olio Combustibile Leggero": {"scope": "Scope 1", "unita_fe": "t", "fe": 3.143, "densita_kg_l": 0.94},
    "Kerosene (altro da avio)": {"scope": "Scope 1", "unita_fe": "t", "fe": 3.149, "densita_kg_l": 0.80},
    "Carbone da vapore": {"scope": "Scope 1", "unita_fe": "TJ", "fe": 92.952, "pci_gj_t": 24.854},

    # --- EMISSIONI BIOGENICHE (Out of Scopes) ---
    "Biomassa Solida (Legna/Pellet)": {"scope": "Fuori Scope (Biogenico)", "unita_fe": "TJ", "fe": 102.773, "pci_gj_t": 15.242},
    "Biogas": {"scope": "Fuori Scope (Biogenico)", "unita_fe": "TJ", "fe": 53.400, "pci_gj_t": 50.358},
    "Bioliquidi": {"scope": "Fuori Scope (Biogenico)", "unita_fe": "TJ", "fe": 77.366, "pci_gj_t": 28.556},
    "FAME (Biodiesel)": {"scope": "Fuori Scope (Biogenico)", "unita_fe": "TJ", "fe": 75.659, "pci_gj_t": 37.405, "densita_kg_l": 0.85},
}

UNITA_MAP = {
    "kWh": ["kWh", "MWh", "GJ", "TJ"],
    "1000_stdm3": ["Stdm3", "Nm3", "1000_Stdm3"],
    "t": ["t", "kg", "Litri"],
    "TJ": ["TJ", "GJ", "t", "kg", "Litri"]
}

def converti_in_unita_base(valore, unita_input, info):
    unita_base = info["unita_fe"]
    valore_calcolo = valore

    if unita_base == "kWh":
        if unita_input == "MWh": valore_calcolo = valore * 1000
        elif unita_input == "GJ": valore_calcolo = valore * 277.778
        elif unita_input == "TJ": valore_calcolo = valore * 277778

    elif unita_base == "1000_stdm3":
        if unita_input == "Nm3": valore_calcolo = (valore * 1.0549) / 1000
        elif unita_input == "Stdm3": valore_calcolo = valore / 1000

    elif unita_base == "t":
        if unita_input == "kg": valore_calcolo = valore / 1000
        elif unita_input == "Litri":
            valore_calcolo = (valore * info["densita_kg_l"]) / 1000

    elif unita_base == "TJ":
        if unita_input == "GJ": valore_calcolo = valore / 1000
        elif unita_input in ["t", "kg", "Litri"]:
            massa_ton = valore
            if unita_input == "kg": massa_ton = valore / 1000
            elif unita_input == "Litri": massa_ton = (valore * info["densita_kg_l"]) / 1000
            valore_calcolo = massa_ton * (info["pci_gj_t"] / 1000)

    return valore_calcolo

# --- INTERFACCIA GRAFICA ---
st.title("🌍 Calcolatore GHG: Dual Reporting Scope 1 & 2")
st.markdown("Strumento di rendicontazione conforme al **GHG Protocol Scope 2 Guidance**. Gestisce la separazione tra metodo Location-based e Market-based, e isola le emissioni biogeniche.")

if 'record' not in st.session_state:
    st.session_state.record = []

col1, col2, col3 = st.columns(3)

with col1:
    vettore = st.selectbox("Combustibile / Fonte", list(DB_FATTORI.keys()))
    info_vettore = DB_FATTORI[vettore]

with col3:
    unita_ammesse = UNITA_MAP[info_vettore["unita_fe"]].copy()
    if "Litri" in unita_ammesse and "densita_kg_l" not in info_vettore:
        unita_ammesse.remove("Litri")
    unita = st.selectbox("Unità di misura", unita_ammesse)

with col2:
    valore = st.number_input(f"Quantità ({unita})", min_value=0.0, value=0.0, step=100.0)

# --- DUAL REPORTING INPUTS ---
fe_market_input = 0.0

if info_vettore["scope"] == "Scope 2":
    st.divider()
    st.subheader("Dati specifici del fornitore (Market-based)")

    if vettore == "Energia Elettrica (Rete)":
        st.info("💡 **Dual Reporting:** Il metodo Location-based (media di rete) viene calcolato automaticamente (Fattore ISPRA). Inserisci qui il fattore di emissione del tuo contratto per il metodo Market-based. Se hai acquistato il 100% di energia rinnovabile tramite Garanzie d'Origine (GO), inserisci **0**.")
        fe_market_input = st.number_input("Fattore di Emissione Market-based (gCO2/kWh)", min_value=0.0, value=0.0, step=10.0)
    else:
        st.info("💡 **Reti Termiche:** Inserisci il fattore di emissione fornito dal gestore della rete di teleriscaldamento / teleraffrescamento. Sarà applicato sia al calcolo Location che Market-based.")
        fe_market_input = st.number_input("Fattore di Emissione Fornitore (gCO2/kWh)", min_value=0.0, value=0.0, step=10.0)

if st.button("➕ Calcola e Aggiungi", type="primary"):
    if valore > 0:
        try:
            valore_base = converti_in_unita_base(valore, unita, info_vettore)
            em_loc = 0.0
            em_mkt = 0.0

            # Logica di calcolo Dual Reporting
            if info_vettore["scope"] == "Scope 2":
                if vettore == "Energia Elettrica (Rete)":
                    em_loc = valore_base * info_vettore["fe_loc"]
                    em_mkt = valore_base * (fe_market_input / 1_000_000)
                else:
                    em_loc = valore_base * (fe_market_input / 1_000_000)
                    em_mkt = em_loc
            else:
                # Per Scope 1 e Biogenico, il valore Location e Market coincidono nell'inventario aggregato
                em_loc = valore_base * info_vettore["fe"]
                em_mkt = em_loc

            st.session_state.record.append({
                "Fonte Energetica": vettore,
                "Quantità Inserita": valore,
                "Unità": unita,
                "Categoria": info_vettore["scope"],
                "Emissioni Location-based (tCO2eq)": round(em_loc, 4),
                "Emissioni Market-based (tCO2eq)": round(em_mkt, 4)
            })
            st.success("Dato acquisito correttamente nel registro.")
        except Exception as e:
            st.error(str(e))

st.divider()

# --- VISUALIZZAZIONE REPORT ---
if st.session_state.record:
    st.subheader("📊 Data Log e Report Esportabile")
    df = pd.DataFrame(st.session_state.record)
    st.dataframe(df, use_container_width=True)

    # Riassunto per Scope secondo regole GHG Protocol
    t_scope1 = df[df['Categoria'] == 'Scope 1']['Emissioni Location-based (tCO2eq)'].sum()
    t_scope2_loc = df[df['Categoria'] == 'Scope 2']['Emissioni Location-based (tCO2eq)'].sum()
    t_scope2_mkt = df[df['Categoria'] == 'Scope 2']['Emissioni Market-based (tCO2eq)'].sum()
    t_bio = df[df['Categoria'] == 'Fuori Scope (Biogenico)']['Emissioni Location-based (tCO2eq)'].sum()

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Totale Scope 1 (Fossile)", f"{round(t_scope1, 3)} tCO2eq")
    col_b.metric("Totale Scope 2 (Location-based)", f"{round(t_scope2_loc, 3)} tCO2eq")
    col_c.metric("Totale Scope 2 (Market-based)", f"{round(t_scope2_mkt, 3)} tCO2eq")

    st.warning(f"🌱 **CO2 Biogenica (Fuori Scope):** {round(t_bio, 3)} tCO2eq. _Nota: La CO2 derivante da biomasse deve essere riportata separatamente e non sommata agli Scope principali._")

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='GHG_Dual_Report')
    output.seek(0)

    st.download_button(label="📥 Scarica Report Excel", data=output, file_name="GHG_Dual_Report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    if st.button("🗑️ Reset Dati"):
        st.session_state.record = []
        st.rerun()

# --- FOOTER METODOLOGICO ---
st.markdown("---")
st.caption("ℹ️ **Note Metodologiche (GHG Protocol Scope 2 Guidance):**")
st.caption("- **Dual Reporting**: Le emissioni derivanti dall'acquisto di energia elettrica sono riportate sia in base alle medie geografiche di rete (Location-based), sia in base alle scelte contrattuali del consumatore (Market-based).")
st.caption("- **Perdite di Trasmissione e Distribuzione (T&D)**: I fattori di emissione applicati misurano le emissioni al punto di generazione. Le perdite di rete e le emissioni del ciclo di vita a monte NON sono incluse nello Scope 2, ma devono essere valutate e riportate separatamente nello **Scope 3 (Categoria 3)**.")
st.caption("- **Emissioni Biogeniche**: La combustione di bioenergie produce emissioni la cui quota di CO2 deve essere documentata esternamente ai totali Scope 1 e 2 per prevenire distorsioni nella contabilizzazione climatica complessiva.")
