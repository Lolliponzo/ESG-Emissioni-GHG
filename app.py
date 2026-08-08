import pandas as pd

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
# FUNZIONI DI UTILITÀ PER REPORT
# ------------------------------------------------------------

def riepilogo_emissioni(df: pd.DataFrame) -> dict:
    """Calcola i totali per Scope 1, Scope 2 (loc/mkt) e biomassa."""
    t_scope1 = df[df["Categoria"] == "Scope 1"]["Emissioni Location-based (tCO2eq)"].sum()
    t_scope2_loc = df[df["Categoria"] == "Scope 2"]["Emissioni Location-based (tCO2eq)"].sum()
    t_scope2_mkt = df[df["Categoria"] == "Scope 2"]["Emissioni Market-based (tCO2eq)"].sum()
    t_bio = df[df["Categoria"] == "Fuori Scope (Biogenico)"]["Emissioni Location-based (tCO2eq)"].sum()

    return {
        "t_scope1": t_scope1,
        "t_scope2_loc": t_scope2_loc,
        "t_scope2_mkt": t_scope2_mkt,
        "t_bio": t_bio,
    }
