import pandas as pd
import streamlit as st
import textwrap
from datetime import datetime
import os
import re

# ==========================================
# CONSTANTES E CONFIGURAÇÕES
# ==========================================
DEFAULT_RMK_1 = "EQPT/SDFGIKRWY/LB1 STS/ATFMX"
DEFAULT_RMK_2 = "PBN/B1C1D1O1S2T1 EET/SBCW0003"
DEFAULT_ROUTE = "N0000 000 ROUTE UNKNOWN"
PREFIXOS_BR = ('SB', 'SD', 'SI', 'SJ', 'SN', 'SS', 'SW')

# ==========================================
# FUNÇÕES AUXILIARES
# ==========================================
def parse_time_to_int(t_str):
    if pd.isna(t_str): return None
    s = str(t_str).replace(':', '').strip()
    return int(s) if s.isdigit() and s != '' else None

def parse_rmk(rmk_raw):
    if pd.isna(rmk_raw) or str(rmk_raw).strip().lower() in ['nan', 'none', '', '<na>']:
        return DEFAULT_RMK_1, DEFAULT_RMK_2
    rmk_str = str(rmk_raw).strip()
    for tag in ['PBN/', 'EET/']:
        if tag in rmk_str:
            idx = rmk_str.find(tag)
            return rmk_str[:idx].strip(), rmk_str[idx:].strip()
    return rmk_str, ""

def map_equipment(eq):
    mapping = {
        "73G": "B737/M", "73M": "B738/M", "73X": "B738/M", "738": "B738/M", 
        "73A": "B738/M", "7M8": "B38M/M", "7ME": "B38M/M"
    }
    return mapping.get(str(eq).strip().upper(), "B738/M") 

def gerar_cabecalho(data_ref, pagina_atual):
    meses = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
    data_formatada = f"{data_ref.day:02d}{meses[data_ref.month-1]}.{data_ref.year}"
    linhas = ["", ""] if pagina_atual > 1 else ["", "", "                                               Planos de Voo Repetitivos", "                                               Classificação: Ident Anv", ""]
    linhas.extend([
        f"CIA: GLO                                    INÍCIO DE VALIDADE: {data_formatada}                                       PAG.: {pagina_atual}",
        "-" * 105,
        "   VALIDO VALIDO DIAS OP  IDENT  TIPO   ADEP     VEL   FL  ROTA                                DEST         OBSERVACOES",
        "   DESDE   ATE   STQQSSD   ANV     TURB     EOBT                                                   EET",
        "-" * 105,
        "", ""  
    ])
    return linhas

def get_group_mask(weekdays_series):
    days_map = {'Monday': 1, 'Tuesday': 2, 'Wednesday': 3, 'Thursday': 4, 'Friday': 5, 'Saturday': 6, 'Sunday': 7}
    mask = ['0'] * 7
    for day in weekdays_series.unique():
        if day in days_map: mask[days_map[day]-1] = str(days_map[day])
    return ''.join(mask)

def safe_float_to_int_str(val, zfill_len=0):
    """Conversão robusta de valores numéricos em string, tratando vazios e NaNs."""
    if pd.isna(val) or str(val).strip() == '': return "0" * zfill_len
    try:
        return str(int(float(str(val).strip()))).zfill(zfill_len)
    except (ValueError, TypeError):
        return "0" * zfill_len

# ==========================================
# FUNÇÃO PRINCIPAL
# ==========================================
def gerar_ficheiros_rpl(caminho_csv_voos, data_inicio_str, data_fim_str):
    try:
        from db_utils import get_aeroportos, get_rotas
        df_iata_icao, df_rotas = get_aeroportos(), get_rotas()
        if df_iata_icao.empty or df_rotas.empty: raise ValueError("Base de dados vazia.")
        iata_icao = dict(zip(df_iata_icao['IATA'], df_iata_icao['ICAO']))
    except Exception as e:
        st.error(f"Erro BD: {e}")
        return None, None

    routes_map = {}
    df_rotas['DE'] = df_rotas['DE'].fillna('').str.strip()
    df_rotas['PARA'] = df_rotas['PARA'].fillna('').str.strip()
    
    for _, row in df_rotas.iterrows():
        origem, destino = row['DE'], row['PARA']
        if not origem or not destino: continue
        
        mach = str(row.get('MACH', 'N0000')).strip()[:5].ljust(5)
        fl_val = str(row.get('FL', '000')).strip().replace('F', '').zfill(3)[:3]
        
        # Robustez: Tratamento de string vazia em campos numéricos da rota
        tv_str = safe_float_to_int_str(row.get('TV'), 4)
        
        route_data = {
            'route': f"{mach} {fl_val} {str(row.get('ROTA', 'ROUTE UNKNOWN')).strip()}",
            'tv': tv_str,
            'obs1': parse_rmk(row.get('EET'))[0], 'obs2': parse_rmk(row.get('EET'))[1],
            'start': parse_time_to_int(row.get('HORA INICIO')), 'end': parse_time_to_int(row.get('HORA FIM'))
        }
        key = (origem, destino)
        if key not in routes_map: routes_map[key] = {'default': None, 'timed': []}
        if route_data['start'] is not None and route_data['end'] is not None:
            routes_map[key]['timed'].append(route_data)
        else: routes_map[key]['default'] = route_data

    try:
        df_voos = pd.read_csv(caminho_csv_voos, sep=None, engine='python')
        df_voos['Data_Voo'] = pd.to_datetime(df_voos['Day'], format='%d%b%Y', errors='coerce')
        df_voos = df_voos.dropna(subset=['Data_Voo'])
    except Exception as e:
        st.error(f"Erro CSV: {e}")
        return None, None

    d_ini, d_fim = pd.to_datetime(data_inicio_str), pd.to_datetime(data_fim_str)
    df = df_voos[(df_voos['Data_Voo'] >= d_ini) & (df_voos['Data_Voo'] <= d_fim)].copy()
    if df.empty: return None, None

    df['ADEP'] = df['Dept Sta'].map(iata_icao).fillna(df['Dept Sta'])
    df['ADES'] = df['Arvl Sta'].map(iata_icao).fillna(df['Arvl Sta'])
    df = df[df['ADEP'].str.startswith(PREFIXOS_BR, na=False) & df['ADES'].str.startswith(PREFIXOS_BR, na=False) & (~df['ADEP'].isin(['SBJP'])) & (~df['ADES'].isin(['SBJP']))].copy()
    
    if df.empty: return None, None

    df['Equip_Map'] = df['Equip'].apply(map_equipment)
    df['EOBT'] = df['Dept Time'].astype(str).str.replace(':', '').str.zfill(4)
    
    # Robustez: Conversão de Flt Num tratando strings vazias ou nulas
    df['Flt_Num_Clean'] = df['Flt Num'].apply(lambda x: safe_float_to_int_str(x))
    df['Flt_Id'] = df['Aln'].replace('G3', 'GLO') + df['Flt_Num_Clean']

    df = df.sort_values(by=['Flt_Id', 'Data_Voo'])
    df['Block_ID'] = (df[['Flt_Id', 'Equip_Map', 'ADEP', 'ADES', 'EOBT']] != df[['Flt_Id', 'Equip_Map', 'ADEP', 'ADES', 'EOBT']].shift(1)).any(axis=1).cumsum()

    rpl_lines, csv_records, cur_page, flt_page, LIMIT = [], [], 1, 0, 60
    rpl_lines.extend(gerar_cabecalho(d_ini, cur_page))

    def resolve(dep, arr, eobt):
        res = routes_map.get((dep, arr))
        if not res: return {'route': DEFAULT_ROUTE, 'tv': "0000", 'obs1': DEFAULT_RMK_1, 'obs2': DEFAULT_RMK_2}
        t_val = parse_time_to_int(eobt)
        for tr in res['timed']:
            s, e = tr['start'], tr['end']
            if (s <= e and s <= t_val <= e) or (s > e and (t_val >= s or t_val <= e)): return tr
        return res['default'] or {'route': DEFAULT_ROUTE, 'tv': "0000", 'obs1': DEFAULT_RMK_1, 'obs2': DEFAULT_RMK_2}

    for _, group in df.groupby('Block_ID'):
        if flt_page >= LIMIT:
            cur_page += 1
            rpl_lines.extend(gerar_cabecalho(d_ini, cur_page))
            flt_page = 0
        base = group.iloc[0]
        v_from, v_to = group['Data_Voo'].min().strftime('%d%m%y'), group['Data_Voo'].max().strftime('%d%m%y')
        rt = resolve(base['ADEP'], base['ADES'], base['EOBT'])
        
        r_body = rt['route'][11:]
        r_chunks = textwrap.wrap(r_body, width=34) or [""]
        o_chunks = textwrap.wrap(rt['obs2'], width=30) if rt['obs2'] else []
        
        line1 = (f"   {v_from} {v_to} {get_group_mask(group['Weekday'])} {base['Flt_Id']:7} "
                 f"{base['Equip_Map']:6} {base['ADEP']}{base['EOBT']} "
                 f"{rt['route'][:10]}{r_chunks[0]:<34} {base['ADES']}{rt['tv']} {rt['obs1']}")
        rpl_lines.append(line1)
        
        for i in range(1, max(len(r_chunks), len(o_chunks) + 1)):
            rc, oc = r_chunks[i] if i < len(r_chunks) else "", o_chunks[i-1] if (i-1) < len(o_chunks) else ""
            if rc or oc: rpl_lines.append(f"{' ' * 59}{rc:<45}{oc}")
        flt_page += 1
        csv_records.append({**base.to_dict(), **rt, 'VALID_FROM': v_from, 'VALID_TO': v_to})

    txt_out, csv_out = "RPL_Final.txt", "RPL_Dados_Consolidados.csv"
    with open(txt_out, 'w', encoding='utf-8') as f: f.write('\n'.join(rpl_lines) + '\n')
    pd.DataFrame(csv_records).to_csv(csv_out, index=False, sep=';')
    return txt_out, csv_out
