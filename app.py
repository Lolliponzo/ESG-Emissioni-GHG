import streamlit as st
import pandas as pd
from io import BytesIO

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Calcolatore Emissioni GHG (Dual Reporting)", page_icon="🌍", layout="wide")

# --- INSERIMENTO LOGO AZIENDALE ---
col_logo, _ = st.columns([1, 4])
with col_logo:
    try:
        st.image("Crowe-Bompani.png", use_container_width=True)
    except FileNotFoundError:
        st.warning("Logo non trovato. Assicurati di aver caricato 'Crowe-Bompani.png' nella repository.")

# --- DATABASE FATTORI DI EMISSIONE ---
# Fonte FE Location-based: Tabella Parametri Standard Nazionali ISPRA
# Fonte Densità: CDP Technical Note
DB_FATTORI = {
    # --- SCOPE 2 ---
    "Energia Elettrica (Rete)": {"scope": "Scope 2", "unita_fe": "kWh", "fe_loc": 192.6 / 1_000_000, "unita_default": "kWh"},
    "Calore / Vapore / Raffrescamento (Telereti)": {"scope": "Scope 2", "unita_fe": "kWh", "fe_loc": 0.0, "richiede_fe_fornitore": True, "unita_default": "kWh"},
    
    # --- SCOPE 1 FOSSILE ---
    "Gas Naturale (Metano)": {"scope": "Scope 1", "unita_fe": "1000_stdm3", "fe": 2.026, "unita_default": "Stdm3"},
    "Gasolio Autotrazione": {"scope": "Scope 1", "unita_fe": "t", "fe": 3.150, "densita_kg_l": 0.84, "unita_default": "Litri"},
    "Gasolio Riscaldamento": {"scope": "Scope 1", "unita_fe": "t", "fe": 3.169, "densita_kg_l": 0.84, "unita_default": "Litri"},
    "Benzina senza piombo": {"scope": "Scope 1", "unita_fe": "t", "fe": 3.152, "densita_kg_l": 0.74, "unita_default": "Litri"},
    "GPL": {"scope": "Scope 1", "unita_fe": "t", "fe": 3.026, "densita_kg_l": 0.54, "unita_default": "Litri"},
    "Olio Combustibile Leggero": {"scope": "Scope 1", "unita_fe": "t", "fe": 3.143, "densita_kg_l": 0.94, "unita_default": "Litri"},
    "Kerosene (altro da avio)": {"scope": "Scope 1", "unita_fe": "t", "fe": 3.149, "densita_kg_l": 0.80, "unita_default": "Litri"},
    "Carbone da vapore": {"scope": "Scope 1", "unita_fe": "TJ", "fe": 92.952, "pci_gj_t": 24.854, "unita_default": "t"},
    
    # --- EMISSIONI BIOGENICHE (Out of Scopes) ---
    "Biomassa Solida (Legna/Pellet)": {"scope": "Fuori Scope (Biogenico)", "unita_fe": "TJ", "fe": 102.773, "pci_gj_t": 15.242, "unita_default": "kg"},
    "Biogas": {"scope": "Fuori Scope (Biogenico)", "unita_fe": "TJ", "fe": 53.400, "pci_gj_t": 50.358, "unita_default": "Stdm3"},
    "Bioliquidi": {"scope": "Fuori Scope (Biogenico)", "unita_fe": "TJ", "fe": 77.366, "pci_gj_t": 28.556, "unita_default": "Litri"},
    "FAME (Biodiesel)": {"scope": "Fuori Scope (Biogenico)", "unita_fe": "TJ", "fe": 75.659, "pci_gj_t": 37.405, "densita_kg_l": 0.85, "unita_default": "Litri"},
}

UNITA_MAP = {
    "kWh": ["kWh", "MWh", "GJ", "TJ"],
    "1000_stdm3": ["Stdm3", "Nm3", "1000_Stdm3"],
    "t": ["t", "kg", "Litri"],
    "TJ": ["TJ", "GJ", "t", "kg", "Litri", "Stdm3", "Nm3"]
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
            valore_calcolo = (valore * info.get("densita_kg_l", 1)) / 1000
            
    elif unita_base == "TJ":
        if unita_input == "GJ": valore_calcolo = valore / 1000
        elif unita_input in ["Stdm3", "Nm3"]:
            # Gestione specifica per gas in TJ (come il Biogas)
            vol_stdm3 = valore if unita_input == "Stdm3" else valore * 1.0549
            valore_calcolo = (vol_stdm3 / 1000) * (info.get("pci_gj_t", 0) / 1000) # Assumendo pci riferito a 1000_stdm3 per gas
        elif unita_input in ["t", "kg", "Litri"]:
            massa_ton = valore
            if unita_input == "kg": massa_ton = valore / 1000
            elif unita_input == "Litri": massa_ton = (valore * info.get("densita_kg_l", 1)) / 1000
            valore_calcolo = massa_ton * (info.get("pci_gj_t", 0) / 1000)

    return valore_calcolo

# --- INTERFACCIA GRAFICA ---
st.title("🌍 Calcolatore GHG: Dual Reporting Scope 1 & 2")
st.markdown("Strumento di rendicontazione conforme al **GHG Protocol Scope 2 Guidance**. Inserisci i consumi così come li leggi in bolletta o in fattura: il sistema farà le conversioni in automatico.")

if 'record' not in st.session_state:
    st.session_state.record = []

col1, col2, col3 = st.columns(3)

# 1. Scelta della Fonte
with col1:
    vettore = st.selectbox("Combustibile / Fonte", list(DB_FATTORI.keys()))
    info_vettore = DB_FATTORI[vettore]

# 2. Scelta dell'Unità di Misura (Con default intelligente)
with col2:
    unita_ammesse = UNITA_MAP[info_vettore["unita_fe"]].copy()
    if "Litri" in unita_ammesse and "densita_kg_l" not in info_vettore:
        unita_ammesse.remove("Litri")
        
    default_unit = info_vettore.get("unita_default", unita_ammesse[0])
    default_idx = unita_ammesse.index(default_unit) if default_unit in unita_ammesse else 0
    unita = st.selectbox("In che unità hai il dato?", unita_ammesse, index=default_idx)

# 3. Inserimento Quantità
with col3:
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
                em_loc = valore_base * info_vettore["fe"]
                em_mkt = em_loc

            st.session_state.record.append({
                "Fonte Energetica": vettore,
                "Quantità Inserita": valore,
                "Unità": unita,
                "Valore Convertito": round(valore_base, 4),
                "Unità ISPRA": info_vettore["unita_fe"],
                "Categoria": info_vettore["scope"],
                "Emissioni Location-based (tCO2eq)": round(em_loc, 4),
                "Emissioni Market-based (tCO2eq)": round(em_mkt, 4)
            })
            st.success("Dato acquisito correttamente nel registro.")
        except Exception as e:
            st.error(str(e))

st.divider()

# --- VISUALIZZAZIONE REPORT E GESTIONE RIGHE ---
if st.session_state.record:
    st.subheader("📊 Data Log e Report Esportabile")
    
    df = pd.DataFrame(st.session_state.record)
    df.index = df.index + 1 
    st.dataframe(df, use_container_width=True)
    
    t_scope1 = df[df['Categoria'] == 'Scope 1']['Emissioni Location-based (tCO2eq)'].sum()
    t_scope2_loc = df[df['Categoria'] == 'Scope 2']['Emissioni Location-based (tCO2eq)'].sum()
    t_scope2_mkt = df[df['Categoria'] == 'Scope 2']['Emissioni Market-based (tCO2eq)'].sum()
    t_bio = df[df['Categoria'] == 'Fuori Scope (Biogenico)']['Emissioni Location-based (tCO2eq)'].sum()
    
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Totale Scope 1 (Fossile)", f"{round(t_scope1, 3)} tCO2eq")
    col_b.metric("Totale Scope 2 (Location-based)", f"{round(t_scope2_loc, 3)} tCO2eq")
    col_c.metric("Totale Scope 2 (Market-based)", f"{round(t_scope2_mkt, 3)} tCO2eq")
    
    st.warning(f"🌱 **CO2 Biogenica (Fuori Scope):** {round(t_bio, 3)} tCO2eq. _Nota: La CO2 derivante da biomasse deve essere riportata separatamente e non sommata agli Scope principali._")

    st.divider()
    
    # --- GESTIONE E RIMOZIONE SINGOLE VOCI ---
    st.subheader("🛠️ Gestione Dati")
    
    opzioni_eliminazione = [f"Riga {i+1}: {r['Fonte Energetica']} ({r['Quantità Inserita']} {r['Unità']})" for i, r in enumerate(st.session_state.record)]
    
    col_mod1, col_mod2, col_mod3 = st.columns([3, 1, 1])
    
    with col_mod1:
        riga_da_eliminare = st.selectbox("Seleziona la riga specifica da cancellare:", opzioni_eliminazione)
        
    with col_mod2:
        st.write("") 
        st.write("")
        if st.button("❌ Rimuovi Riga", use_container_width=True):
            indice_da_eliminare = opzioni_eliminazione.index(riga_da_eliminare)
            st.session_state.record.pop(indice_da_eliminare)
            st.rerun() 
            
    with col_mod3:
        st.write("")
        st.write("")
        if st.button("🗑️ Svuota Tutto", use_container_width=True):
            st.session_state.record = []
            st.rerun()

    st.divider()

    # --- DOWNLOAD EXCEL ---
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='GHG_Dual_Report')
    output.seek(0)
    
    st.download_button(
        label="📥 Scarica Report Excel Completo", 
        data=output, 
        file_name="GHG_Dual_Report.xlsx", 
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

# --- FOOTER METODOLOGICO E CREDITS ---
st.markdown("---")
st.caption("ℹ️ **Note Metodologiche (GHG Protocol Scope 2 Guidance):**")
st.caption("- **Dual Reporting**: Le emissioni derivanti dall'acquisto di energia elettrica sono riportate sia in base alle medie geografiche di rete (Location-based), sia in base alle scelte contrattuali del consumatore (Market-based).")
st.caption("- **Perdite di Trasmissione e Distribuzione (T&D)**: I fattori di emissione applicati misurano le emissioni al punto di generazione. Le perdite di rete e le emissioni del ciclo di vita a monte NON sono incluse nello Scope 2, ma devono essere valutate e riportate separatamente nello **Scope 3 (Categoria 3)**.")
st.caption("- **Emissioni Biogeniche**: La combustione di bioenergie produce emissioni la cui quota di CO2 deve essere documentata esternamente ai totali Scope 1 e 2 per prevenire distorsioni nella contabilizzazione climatica complessiva.")

st.markdown("---")
st.markdown("<p style='text-align: center; color: #888888; font-size: 14px;'>Strumento sviluppato da <strong>Alessio Morgante</strong></p> | Versione Beta 1.0", unsafe_allow_html=True)
