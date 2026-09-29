import streamlit as st
import pandas as pd
from io import BytesIO

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Calcolatore Emissioni GHG (Dual Reporting & Scope 3)", page_icon="🌍", layout="wide")

# --- INSERIMENTO LOGO AZIENDALE ---
col_logo, _ = st.columns([1, 4])
with col_logo:
    try:
        st.image("Crowe-Bompani.png", use_container_width=True)
    except FileNotFoundError:
        st.warning("Logo non trovato. Assicurati di aver caricato 'Crowe-Bompani.png' nella repository.")

# --- TITOLO E GUIDA INTRODUTTIVA ---
st.title("🌍 Calcolatore GHG: Inventario Completo (Scope 1, 2, 3)")
st.caption("🚀 **Versione Beta 1.0** - *Strumento in fase di test e validazione (Non definitivo)*")

with st.expander("📖 Guida ai concetti: Scope, Dual Reporting e Inserimento Dati"):
    st.markdown("""
    Questo strumento guida l'utente partendo dall'**attività aziendale concreta**, senza richiedere conoscenze tecniche pregresse. L'algoritmo assegnerà automaticamente l'impatto allo Scope normativo corretto secondo il **GHG Protocol**.
    
    * **Scope 1 (Emissioni Dirette):** Consumi degli immobili (es. caldaie a metano) e della flotta di proprietà.
    * **Scope 2 (Emissioni Indirette da Energia):** Elettricità e teleriscaldamento. Viene applicato il **Dual Reporting**:
      * *Location-based:* Impatto reale della rete fisica nazionale (Fattore ISPRA).
      * *Market-based:* Scelte contrattuali (es. inserendo **0** se si ha energia 100% verde con Garanzie d'Origine).
    * **Scope 3 (Catena del Valore):** Emissioni indirette a monte e a valle[span_1](start_span)[span_1](end_span). Lo strumento include le categorie più comuni: *Cat. 6 Business Travel* (voli e treni) e *Cat. 5 Waste* (smaltimento rifiuti)[span_2](start_span)[span_2](end_span).
    * **CO2 Biogenica:** Quantificata separatamente e non sommata ai totali, come da normativa.
    """)

# --- DATABASE ATTIVITÀ E FATTORI DI EMISSIONE ---
# Struttura organizzata per aree aziendali (User-friendly)
DB_ATTIVITA = {
    "🏢 Immobili e Sedi (Riscaldamento ed Elettricità)": {
        "Energia Elettrica (Rete)": {"scope": "Scope 2", "dettaglio": "Consumi Elettrici", "unita_fe": "kWh", "fe_loc": 199.6 / 1_000_000, "unita_default": "kWh"},
        "Gas Naturale (Metano)": {"scope": "Scope 1", "dettaglio": "Combustione Stazionaria", "unita_fe": "1000_stdm3", "fe": 2.026, "unita_default": "Stdm3"},
        "Gasolio Riscaldamento": {"scope": "Scope 1", "dettaglio": "Combustione Stazionaria", "unita_fe": "t", "fe": 3.169, "densita_kg_l": 0.84, "unita_default": "Litri"},
        "Calore / Teleriscaldamento": {"scope": "Scope 2", "dettaglio": "Energia Termica Acquistata", "unita_fe": "kWh", "fe_loc": 0.0, "richiede_fe_fornitore": True, "unita_default": "kWh"},
    },
    "🚗 Flotta Aziendale (Veicoli di Proprietà o Leasing lungo termine)": {
        "Gasolio Autotrazione": {"scope": "Scope 1", "dettaglio": "Combustione Mobile", "unita_fe": "t", "fe": 3.150, "densita_kg_l": 0.84, "unita_default": "Litri"},
        "Benzina senza piombo": {"scope": "Scope 1", "dettaglio": "Combustione Mobile", "unita_fe": "t", "fe": 3.152, "densita_kg_l": 0.74, "unita_default": "Litri"},
        "GPL": {"scope": "Scope 1", "dettaglio": "Combustione Mobile", "unita_fe": "t", "fe": 3.026, "densita_kg_l": 0.54, "unita_default": "Litri"},
    },
    "✈️ Viaggi di Lavoro e Trasferte (Dipendenti)": {
        "Volo Aereo Corto Raggio (<3h)": {"scope": "Scope 3", "dettaglio": "Cat. 6 - Business Travel", "unita_fe": "pax_km", "fe": 0.00015, "unita_default": "Passeggeri-km"},
        "Volo Aereo Lungo Raggio (>6h)": {"scope": "Scope 3", "dettaglio": "Cat. 6 - Business Travel", "unita_fe": "pax_km", "fe": 0.00011, "unita_default": "Passeggeri-km"},
        "Treno (Media/Alta Velocità)": {"scope": "Scope 3", "dettaglio": "Cat. 6 - Business Travel", "unita_fe": "pax_km", "fe": 0.00003, "unita_default": "Passeggeri-km"}
    },
    "🗑️ Gestione Rifiuti (Smaltiti da Terzi)": {
        "Rifiuti Urbani Misti (Discarica)": {"scope": "Scope 3", "dettaglio": "Cat. 5 - Waste Generated in Operations", "unita_fe": "t_rifiuti", "fe": 0.35, "unita_default": "t"},
        "Carta/Cartone (Riciclo)": {"scope": "Scope 3", "dettaglio": "Cat. 5 - Waste Generated in Operations", "unita_fe": "t_rifiuti", "fe": 0.021, "unita_default": "t"},
        "Plastica (Riciclo)": {"scope": "Scope 3", "dettaglio": "Cat. 5 - Waste Generated in Operations", "unita_fe": "t_rifiuti", "fe": 0.021, "unita_default": "t"}
    },
    "🌱 Biomasse (Out of Scope / Biogeniche)": {
        "Biomassa Solida (Legna/Pellet)": {"scope": "Fuori Scope", "dettaglio": "Biogenico", "unita_fe": "TJ", "fe": 102.773, "pci_gj_t": 15.242, "unita_default": "kg"},
        "Biogas": {"scope": "Fuori Scope", "dettaglio": "Biogenico", "unita_fe": "TJ", "fe": 53.400, "pci_gj_t": 50.358, "unita_default": "Stdm3"}
    }
}

UNITA_MAP = {
    "kWh": ["kWh", "MWh", "GJ", "TJ"],
    "1000_stdm3": ["Stdm3", "Nm3", "1000_Stdm3"],
    "t": ["t", "kg", "Litri"],
    "TJ": ["TJ", "GJ", "t", "kg", "Litri", "Stdm3", "Nm3"],
    "pax_km": ["Passeggeri-km"],
    "t_rifiuti": ["t", "kg"]
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
            vol_stdm3 = valore if unita_input == "Stdm3" else valore * 1.0549
            valore_calcolo = (vol_stdm3 / 1000) * (info.get("pci_gj_t", 0) / 1000) 
        elif unita_input in ["t", "kg", "Litri"]:
            massa_ton = valore
            if unita_input == "kg": massa_ton = valore / 1000
            elif unita_input == "Litri": massa_ton = (valore * info.get("densita_kg_l", 1)) / 1000
            valore_calcolo = massa_ton * (info.get("pci_gj_t", 0) / 1000)
            
    elif unita_base == "pax_km":
        valore_calcolo = valore # Nessuna conversione necessaria
        
    elif unita_base == "t_rifiuti":
        if unita_input == "kg": valore_calcolo = valore / 1000
        else: valore_calcolo = valore

    return valore_calcolo

# --- INSERIMENTO DATI ---
st.divider()

if 'record' not in st.session_state:
    st.session_state.record = []

col1, col2 = st.columns(2)

with col1:
    macro_area = st.selectbox("1. Seleziona l'Area Aziendale", list(DB_ATTIVITA.keys()))

with col2:
    vettore = st.selectbox("2. Seleziona la Fonte / Attività", list(DB_ATTIVITA[macro_area].keys()))
    info_vettore = DB_ATTIVITA[macro_area][vettore]

col_unit, col_val = st.columns(2)

with col_unit:
    unita_ammesse = UNITA_MAP[info_vettore["unita_fe"]].copy()
    if "Litri" in unita_ammesse and "densita_kg_l" not in info_vettore:
        unita_ammesse.remove("Litri")
        
    default_unit = info_vettore.get("unita_default", unita_ammesse[0])
    default_idx = unita_ammesse.index(default_unit) if default_unit in unita_ammesse else 0
    unita = st.selectbox("3. Unità di Misura", unita_ammesse, index=default_idx)

with col_val:
    valore = st.number_input(f"4. Quantità ({unita})", min_value=0.0, value=0.0, step=100.0)

# Input condizionale visibile SOLO per lo Scope 2
fe_market_input = 0.0

if info_vettore["scope"] == "Scope 2":
    st.markdown("---")
    if vettore == "Energia Elettrica (Rete)":
        st.info("💡 **Dati per il Market-based method:** Se l'azienda ha acquistato energia 100% rinnovabile con Garanzie d'Origine (GO), inserisci **0**. Se ha un contratto standard senza GO, lascia il valore preimpostato (Consumi Elettrici ISPRA Tab. 1.7) o inserisci il dato del fornitore.")
        fe_market_input = st.number_input("Fattore di Emissione Market-based (gCO2eq/kWh)", min_value=0.0, value=199.6, step=10.0)
    else:
        st.info("💡 **Reti Termiche:** Inserisci il fattore di emissione fornito dal gestore della rete di teleriscaldamento / teleraffrescamento.")
        fe_market_input = st.number_input("Fattore di Emissione Fornitore (gCO2eq/kWh)", min_value=0.0, value=0.0, step=10.0)

if st.button("➕ Calcola e Aggiungi all'Inventario", type="primary"):
    if valore > 0:
        try:
            valore_base = converti_in_unita_base(valore, unita, info_vettore)
            em_loc = 0.0
            em_mkt = 0.0
            nota_modifica = "-"
            fe_loc_str = "-"
            
            # Calcolo Emissioni e Generazione Tracciato Audit
            if info_vettore["scope"] == "Scope 2":
                fe_loc_str = f"{round(info_vettore['fe_loc'] * 1_000_000, 2)} gCO2eq/kWh"
                
                if vettore == "Energia Elettrica (Rete)":
                    em_loc = valore_base * info_vettore["fe_loc"]
                    em_mkt = valore_base * (fe_market_input / 1_000_000)
                    
                    if fe_market_input == 0.0:
                        nota_modifica = "Modificato: 0 (Dichiarata fornitura 100% GO/Rinnovabile)"
                    elif fe_market_input != 199.6:
                        nota_modifica = f"Modificato: inserito {fe_market_input} gCO2eq/kWh (Fattore specifico fornitore)"
                    else:
                        nota_modifica = "Standard di default (199.6 gCO2eq/kWh - ISPRA 430/2026 Tabella 1.7)"
                else:
                    em_loc = valore_base * (fe_market_input / 1_000_000)
                    em_mkt = em_loc
                    nota_modifica = f"Fattore inserito per rete termica: {fe_market_input} gCO2eq/kWh"
                    
            elif info_vettore["scope"] == "Scope 1" or info_vettore["scope"] == "Scope 3":
                em_loc = valore_base * info_vettore["fe"]
                em_mkt = em_loc # Per Scope 1 e 3, Location e Market coincidono di default in questo tool
                fe_loc_str = f"{info_vettore['fe']} tCO2e/unità base"
                nota_modifica = f"N/A (Metodo Market-based non applicabile allo {info_vettore['scope']})"
                
            else: # Fuori Scope (Biogenico)
                em_loc = valore_base * info_vettore["fe"]
                em_mkt = em_loc
                fe_loc_str = f"{info_vettore['fe']} tCO2e/unità base"
                nota_modifica = "Emissioni biogeniche rendicontate separatamente"

            # Aggiunta al log di sessione
            st.session_state.record.append({
                "Area Aziendale": macro_area,
                "Attività / Fonte": vettore,
                "Quantità Inserita": valore,
                "Unità": unita,
                "Scope": info_vettore["scope"],
                "Categoria Normativa": info_vettore["dettaglio"],
                "FE Location-based": fe_loc_str,
                "FE Market-based applicato": f"{fe_market_input} gCO2eq/kWh" if info_vettore["scope"] == "Scope 2" else "-",
                "Verifica Override Utente": nota_modifica,
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
    
    # Vista compatta a schermo: nascondiamo le colonne di Audit per chiarezza visiva
    colonne_nascoste = ["FE Location-based", "FE Market-based applicato", "Verifica Override Utente", "Area Aziendale"]
    st.dataframe(df.drop(columns=colonne_nascoste), use_container_width=True)
    
    t_scope1 = df[df['Scope'] == 'Scope 1']['Emissioni Location-based (tCO2eq)'].sum()
    t_scope2_loc = df[df['Scope'] == 'Scope 2']['Emissioni Location-based (tCO2eq)'].sum()
    t_scope2_mkt = df[df['Scope'] == 'Scope 2']['Emissioni Market-based (tCO2eq)'].sum()
    t_scope3 = df[df['Scope'] == 'Scope 3']['Emissioni Location-based (tCO2eq)'].sum()
    t_bio = df[df['Scope'] == 'Fuori Scope']['Emissioni Location-based (tCO2eq)'].sum()
    
    # Metriche dettagliate per Scope
    st.markdown("### Riepilogo Analitico")
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Totale Scope 1", f"{round(t_scope1, 3)} tCO2eq")
    col_b.metric("Totale Scope 2 (Loc)", f"{round(t_scope2_loc, 3)} tCO2eq")
    col_c.metric("Totale Scope 2 (Mkt)", f"{round(t_scope2_mkt, 3)} tCO2eq")
    col_d.metric("Totale Scope 3", f"{round(t_scope3, 3)} tCO2eq")
    
    # Metriche di Inventario Totale
    st.markdown("### Inventario Complessivo Aziendale")
    col_tot1, col_tot2 = st.columns(2)
    col_tot1.info(f"**Totale Aziendale (Location-based):** {round(t_scope1 + t_scope2_loc + t_scope3, 3)} tCO2eq")
    col_tot2.success(f"**Totale Aziendale (Market-based):** {round(t_scope1 + t_scope2_mkt + t_scope3, 3)} tCO2eq")
    
    st.warning(f"🌱 **CO2 Biogenica (Fuori Scope):** {round(t_bio, 3)} tCO2eq. _La CO2 derivante da biomasse deve essere riportata separatamente e non sommata agli Scope principali._")

    st.divider()
    
    # --- GESTIONE E RIMOZIONE SINGOLE VOCI ---
    st.subheader("🛠️ Gestione Dati")
    opzioni_eliminazione = [f"Riga {i+1}: {r['Attività / Fonte']} ({r['Quantità Inserita']} {r['Unità']})" for i, r in enumerate(st.session_state.record)]
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
    # Il file scaricato conterrà TUTTE le colonne, compreso il tracciato per Audit
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventario_GHG')
    output.seek(0)
    
    st.download_button(
        label="📥 Scarica Report Excel Completo (Incluso Tracciato Audit)", 
        data=output, 
        file_name="Inventario_GHG_Completo.xlsx", 
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

# --- FOOTER CREDITS E FONTI ---
st.markdown("---")
st.markdown("#### Fonti e Riferimenti Normativi")
st.caption("1. **Rapporto ISPRA 430/2026 (Tabella 1.7)**: Fattori di emissione nel settore elettrico - Consumi elettrici e produzione lorda.")
st.caption("2. **GHG Protocol Scope 2 Guidance**: Metodologia per il calcolo delle emissioni indirette da energia acquistata (Dual Reporting).")
st.caption("3. **GHG Protocol Corporate Value Chain (Scope 3) Standard**: Standard ufficiale per le 15 categorie della catena del valore (es. Cat 5 Rifiuti, Cat 6 Business Travel)[span_3](start_span)[span_3](end_span).")

st.markdown("<p style='text-align: center; color: #1B2A41; font-size: 14px; margin-top: 20px;'>Strumento sviluppato da <strong>[Nome e Cognome]</strong> | Versione Beta 1.0</p>", unsafe_allow_html=True)
tegoria"] == "Scope 2"]["Emissioni Location-based (tCO2eq)"].sum()
    t_scope2_mkt = df[df["Categoria"] == "Scope 2"]["Emissioni Market-based (tCO2eq)"].sum()
    t_bio = df[df["Categoria"] == "Fuori Scope (Biogenico)"]["Emissioni Location-based (tCO2eq)"].sum()

    return {
        "t_scope1": t_scope1,
        "t_scope2_loc": t_scope2_loc,
        "t_scope2_mkt": t_scope2_mkt,
        "t_bio": t_bio,
    }

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

# Pulsante di calcolo evidenziato subito sotto gli input, centrato
action_col1, action_col2, action_col3 = st.columns([3, 2, 3])
with action_col2:
    calcola_button = st.button("Calcola e aggiungi al registro", type="primary")

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
if calcola_button:
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

    totali = riepilogo_emissioni(df)

    st.subheader("Riepilogo per categoria di emissione")
    sum_col1, sum_col2, sum_col3 = st.columns(3)

    sum_col1.metric("Totale Scope 1 (fossile)", f"{round(totali['t_scope1'], 3)} tCO2eq")
    sum_col2.metric("Totale Scope 2 (Location-based)", f"{round(totali['t_scope2_loc'], 3)} tCO2eq")
    sum_col3.metric("Totale Scope 2 (Market-based)", f"{round(totali['t_scope2_mkt'], 3)} tCO2eq")

    st.subheader("Inventario aziendale Scope 1 + Scope 2")
    inv_col1, inv_col2 = st.columns(2)

    inv_col1.info(
        f"Totale aziendale (Location-based): {round(totali['t_scope1'] + totali['t_scope2_loc'], 3)} tCO2eq"
    )
    inv_col2.success(
        f"Totale aziendale (Market-based): {round(totali['t_scope1'] + totali['t_scope2_mkt'], 3)} tCO2eq"
    )

    st.warning(
        f"CO2 biogenica (fuori Scope): {round(totali['t_bio'], 3)} tCO2eq. "
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
