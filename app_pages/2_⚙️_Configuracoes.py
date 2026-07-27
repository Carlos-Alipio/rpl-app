import streamlit as st
import pandas as pd
from db_utils import (
    get_rotas, save_rotas, COLUNAS_ROTAS, adicionar_usuario, get_usuarios, remover_usuario,
    get_aeroportos, adicionar_aeroporto, remover_aeroporto,
    get_equipamentos, adicionar_equipamento, remover_equipamento,
    get_prefixos_br, adicionar_prefixo_br, remover_prefixo_br,
    get_aerodromos_excluidos, adicionar_aerodromo_excluido, remover_aerodromo_excluido,
)

# ==========================================
# 1. CONFIGURAÇÃO BASE
# ==========================================
# (Pode remover o st.set_page_config se o st.navigation já o gerir no app.py, 
# mas mantemos aqui para garantir que a página corre bem sozinha)

# --- FUNÇÕES DE LIMPEZA E FORMATAÇÃO ---
def limpar_texto(v) -> str:
    """Converte valores nulos/NaN vindos da BD em string vazia."""
    return "" if pd.isna(v) else str(v)

def formatar_hora(t):
    """Garante que a hora lida da BD fica no formato HH:MM"""
    if pd.isna(t) or str(t).strip().lower() in ['nan', 'none', '']: return ""
    t_str = str(t).replace(':', '').replace('.0', '').strip()
    if t_str.isdigit():
        t_str = t_str.zfill(4)
        if len(t_str) == 4: return f"{t_str[:2]}:{t_str[2:]}"
    return str(t)

# --- GESTÃO DE ESTADO (MEMÓRIA DO SISTEMA) ---
def carregar_dados_memoria():
    # Carregar e limpar Rotas
    df_r = get_rotas()
    
    # Prevenção: Garante que os nomes das colunas são texto
    df_r.columns = df_r.columns.astype(str)
    
    colunas_texto_r = ['DE', 'PARA', 'MACH', 'FL', 'ROTA', 'EET', 'TV']
    for col in colunas_texto_r:
        if col in df_r.columns:
            df_r[col] = df_r[col].apply(lambda x: str(x).upper().strip() if pd.notnull(x) else "")
            
    if 'HORA INICIO' in df_r.columns: df_r['HORA INICIO'] = df_r['HORA INICIO'].apply(formatar_hora)
    if 'HORA FIM' in df_r.columns: df_r['HORA FIM'] = df_r['HORA FIM'].apply(formatar_hora)
    df_r = df_r.reset_index(drop=True)
    st.session_state.df_rotas = df_r

if 'df_rotas' not in st.session_state:
    carregar_dados_memoria()

st.header(":material/settings: Painel de Configurações")
st.markdown("Gestão avançada da base de dados. Use os filtros para visualizar a malha e **clique diretamente numa linha da tabela** para a editar.")

aba1, aba2, aba3 = st.tabs([
    ":material/route: Gestão de Rotas",
    ":material/manage_accounts: Utilizadores",
    ":material/build: Sistema",
])

# ==========================================
# ABA 1: ROTAS
# ==========================================
with aba1:
    col_add, col_import = st.columns(2)
    
    # --- 1.A FORMULÁRIO DE CRIAÇÃO INDIVIDUAL ---
    with st.expander("Adicionar Rota Manualmente", icon=":material/add:", expanded=False):
        with st.form("form_add_rota", clear_on_submit=True):
            c1, c2, c3, c4, c5 = st.columns(5)
            n_de = c1.text_input("DE (Origem)*", max_chars=4, help="Ex: SBSP")
            n_para = c2.text_input("PARA (Destino)*", max_chars=4, help="Ex: SBRJ")
            n_mach = c3.text_input("MACH", value="N0450")
            n_fl = c4.text_input("FL", max_chars=3, help="Ex: 350")
            n_tv = c5.text_input("TV (HH:MM)", value="00:00", max_chars=5, help="Tempo de Voo. Ex: 01:20")
            
            n_rota = st.text_area("ROTA*", help="Insira a rota completa.", height=100)
            
            c7, c8 = st.columns(2)
            n_h_inicio = c7.text_input("HORA INÍCIO (HH:MM)", max_chars=5)
            n_h_fim = c8.text_input("HORA FIM (HH:MM)", max_chars=5)
            
            n_eet = st.text_area("OBSERVAÇÕES (PBN/EET/EQPT)", height=100)
            
            if st.form_submit_button("Guardar Nova Rota", type="primary", icon=":material/check_circle:"):
                if not n_de or not n_para or not n_rota:
                    st.error("Os campos DE, PARA e ROTA são obrigatórios.", icon=":material/warning:")
                else:
                    nova_linha = {
                        "DE": n_de.upper().strip(), "PARA": n_para.upper().strip(), "MACH": n_mach.upper().strip(),
                        "FL": n_fl.upper().strip(), "ROTA": n_rota.upper().strip(), 
                        "TV": n_tv.replace(':', '').strip(), 
                        "HORA INICIO": n_h_inicio.strip(), "HORA FIM": n_h_fim.strip(), "EET": n_eet.upper().strip()
                    }
                    novo_df = pd.DataFrame([nova_linha])
                    st.session_state.df_rotas = pd.concat([st.session_state.df_rotas, novo_df], ignore_index=True)
                    save_rotas(st.session_state.df_rotas)
                    st.success("Nova rota inserida com sucesso!", icon=":material/check_circle:")
                    st.rerun()

    # --- 1.B IMPORTAÇÃO EM LOTE ---
    with st.expander("Importar Lote via Excel/CSV", icon=":material/folder_open:", expanded=False):
        st.info("O arquivo deve conter na primeira linha (cabeçalho) as colunas: **DE, PARA, ROTA**. Pode incluir opcionalmente: MACH, FL, TV, HORA INICIO, HORA FIM, EET.")
        ficheiro_rotas = st.file_uploader("Arraste a planilha de Rotas", type=["xlsx", "xls", "csv"], key="upload_rotas")
        
        if ficheiro_rotas:
            try:
                if ficheiro_rotas.name.endswith('.csv'):
                    df_import = pd.read_csv(ficheiro_rotas, dtype=str)
                else:
                    df_import = pd.read_excel(ficheiro_rotas, dtype=str)
                
                # Forçar cabeçalhos a maiúsculas para evitar erros de case-sensitive
                df_import.columns = df_import.columns.str.upper().str.strip()
                
                if 'DE' not in df_import.columns or 'PARA' not in df_import.columns or 'ROTA' not in df_import.columns:
                    st.error("O arquivo não tem as colunas obrigatórias 'DE', 'PARA' e 'ROTA'. Verifique os cabeçalhos.", icon=":material/warning:")
                else:
                    colunas_desconhecidas = [c for c in df_import.columns if c not in COLUNAS_ROTAS]
                    if colunas_desconhecidas:
                        st.warning(
                            f"Estas colunas do arquivo não são reconhecidas e **serão ignoradas**: {', '.join(colunas_desconhecidas)}. "
                            "Verifique se não há erro de digitação ou acentuação no cabeçalho (ex: 'HORA INICIO' sem acento).",
                            icon=":material/warning:"
                        )
                    st.success(f"Arquivo lido com sucesso! ({len(df_import)} linhas encontradas).")
                    if st.button("Processar e Adicionar à Base de Dados", type="primary", icon=":material/rocket_launch:"):
                        # Descarta colunas não reconhecidas para manter a tabela consistente com o que é gravado
                        df_import = df_import[[c for c in df_import.columns if c in COLUNAS_ROTAS]]

                        # Limpeza profunda
                        for col in df_import.columns:
                            df_import[col] = df_import[col].apply(lambda x: str(x).upper().strip() if pd.notnull(x) else "")

                        st.session_state.df_rotas = pd.concat([st.session_state.df_rotas, df_import], ignore_index=True)
                        
                        # Remove duplicados exatos
                        st.session_state.df_rotas = st.session_state.df_rotas.drop_duplicates(subset=['DE', 'PARA', 'ROTA'])
                        
                        save_rotas(st.session_state.df_rotas)
                        st.success("Malha importada e consolidada com sucesso!", icon=":material/check_circle:")
                        st.rerun()
            except Exception as e:
                st.error(f"Erro ao processar arquivo: {e}")

    st.divider()

    # --- 2. FILTROS E VISUALIZAÇÃO INTERATIVA ---
    st.subheader(":material/table_view: Cadastro de Rotas")
    c_f1, c_f2, c_f3 = st.columns(3)
    
    opcoes_de = sorted(st.session_state.df_rotas['DE'].dropna().astype(str).unique())
    opcoes_para = sorted(st.session_state.df_rotas['PARA'].dropna().astype(str).unique())
    
    filtro_de = c_f1.multiselect(":material/location_on: Filtrar Origem (DE)", opcoes_de)
    filtro_para = c_f2.multiselect(":material/location_on: Filtrar Destino (PARA)", opcoes_para)
    filtro_rota = c_f3.text_input("Pesquisar trecho na ROTA", icon=":material/search:")

    df_view = st.session_state.df_rotas.copy()
    if filtro_de: df_view = df_view[df_view['DE'].isin(filtro_de)]
    if filtro_para: df_view = df_view[df_view['PARA'].isin(filtro_para)]
    if filtro_rota: df_view = df_view[df_view['ROTA'].str.contains(filtro_rota, case=False, na=False)]

    if len(df_view) == 0:
        st.warning("Nenhuma rota encontrada.")
    else:
        st.info("**Dica:** Clique na caixa de seleção à esquerda de qualquer linha na tabela para a editar ou apagar.", icon=":material/touch_app:")
        
        df_display = df_view.copy()
        if 'TV' in df_display.columns:
            df_display['TV'] = df_display['TV'].apply(formatar_hora)
            
        evento_selecao = st.dataframe(
            df_display, 
            use_container_width=True, 
            hide_index=True, 
            height=250,
            on_select="rerun",           
            selection_mode="single-row"  
        )
        
        st.divider()

        # --- 3. EDITOR DA ROTA SELECIONADA ---
        st.subheader(":material/edit_road: Gerir Rota Selecionada")
        
        linhas_clicadas = evento_selecao.get("selection", {}).get("rows", [])
        
        if not linhas_clicadas:
            st.warning("Nenhuma rota selecionada. Clique numa linha acima.")
        else:
            pos_idx = linhas_clicadas[0]
            idx_real = df_view.index[pos_idx]
            rota_atual = st.session_state.df_rotas.loc[idx_real]
            
            st.markdown(f"### A editar: `{rota_atual['DE']}` :material/arrow_forward: `{rota_atual['PARA']}`")
            
            with st.form("form_gestao_rota"):
                c1, c2, c3, c4, c5 = st.columns(5)
                e_de = c1.text_input("DE*", value=limpar_texto(rota_atual.get('DE')), max_chars=4)
                e_para = c2.text_input("PARA*", value=limpar_texto(rota_atual.get('PARA')), max_chars=4)
                e_mach = c3.text_input("MACH", value=limpar_texto(rota_atual.get('MACH')))
                e_fl = c4.text_input("FL", value=limpar_texto(rota_atual.get('FL')), max_chars=3)
                e_tv = c5.text_input("TV (HH:MM)", value=formatar_hora(rota_atual.get('TV', '')), max_chars=5)

                e_rota = st.text_area("ROTA*", value=limpar_texto(rota_atual.get('ROTA')), height=100)

                c7, c8 = st.columns(2)
                e_h_inicio = c7.text_input("HORA INÍCIO (HH:MM)", value=limpar_texto(rota_atual.get('HORA INICIO')), max_chars=5)
                e_h_fim = c8.text_input("HORA FIM (HH:MM)", value=limpar_texto(rota_atual.get('HORA FIM')), max_chars=5)

                eet_atual = limpar_texto(rota_atual.get('EET')).strip()
                e_eet = st.text_area("OBSERVAÇÕES", value=eet_atual, height=100)
                
                st.write("") 
                col_btn_upd, col_btn_del = st.columns(2)
                
                btn_atualizar = col_btn_upd.form_submit_button("Atualizar Dados", type="primary", use_container_width=True, icon=":material/save:")
                btn_apagar = col_btn_del.form_submit_button("Apagar esta Rota", use_container_width=True, icon=":material/delete:")

                if btn_atualizar:
                    if not e_de or not e_para or not e_rota:
                        st.error("Os campos DE, PARA e ROTA são obrigatórios.", icon=":material/warning:")
                    else:
                        st.session_state.df_rotas.loc[idx_real, 'DE'] = e_de.upper().strip()
                        st.session_state.df_rotas.loc[idx_real, 'PARA'] = e_para.upper().strip()
                        st.session_state.df_rotas.loc[idx_real, 'MACH'] = e_mach.upper().strip()
                        st.session_state.df_rotas.loc[idx_real, 'FL'] = e_fl.upper().strip()
                        st.session_state.df_rotas.loc[idx_real, 'ROTA'] = e_rota.upper().strip()
                        st.session_state.df_rotas.loc[idx_real, 'TV'] = e_tv.replace(':', '').strip()
                        st.session_state.df_rotas.loc[idx_real, 'HORA INICIO'] = e_h_inicio.strip()
                        st.session_state.df_rotas.loc[idx_real, 'HORA FIM'] = e_h_fim.strip()
                        st.session_state.df_rotas.loc[idx_real, 'EET'] = e_eet.upper().strip()
                        
                        save_rotas(st.session_state.df_rotas)
                        st.success("Rota atualizada com sucesso na Base de Dados!", icon=":material/check_circle:")
                        st.rerun()

                elif btn_apagar:
                    st.session_state.df_rotas = st.session_state.df_rotas.drop(idx_real).reset_index(drop=True)
                    save_rotas(st.session_state.df_rotas)
                    st.warning("Rota eliminada permanentemente da Base de Dados.", icon=":material/delete:")
                    st.rerun()

# ==========================================
# ABA 2: SEGURANÇA E UTILIZADORES
# ==========================================
with aba2:
    st.subheader(":material/person_add: Pré-Autorizar Novos Utilizadores")
    st.info("Insira o e-mail do operador e defina uma senha provisória. No seu primeiro acesso, ele será obrigado a criar uma senha pessoal.")
    
    with st.form("form_novo_user", clear_on_submit=True):
        c1, c2 = st.columns(2)
        novo_email = c1.text_input("E-mail do Operador")
        senha_provisoria = c2.text_input("Senha Provisória (Ex: mudar123)")
        
        if st.form_submit_button("Autorizar Acesso", type="primary", icon=":material/check_circle:"):
            if novo_email and senha_provisoria:
                if adicionar_usuario(novo_email, senha_provisoria):
                    st.success(f"O utilizador {novo_email} foi autorizado!", icon=":material/check_circle:")
                    st.rerun()
                else:
                    st.error("Este e-mail já existe na base de dados.", icon=":material/warning:")
            else:
                st.error("Preencha ambos os campos.")
                
    st.divider()
    st.subheader(":material/group: Utilizadores no Sistema")

    df_users = get_usuarios()
    df_users['Status'] = df_users['precisa_trocar_senha'].apply(lambda x: "Pendente (Troca de senha obrigatória)" if x else "Ativo")

    st.dataframe(df_users[['email', 'Status']], use_container_width=True, hide_index=True)

    st.markdown("### :material/person_remove: Remover Acesso")
    email_remover = st.selectbox("Selecione o e-mail para revogar o acesso:", ["--- Selecione ---"] + df_users['email'].tolist())
    if st.button("Revogar Acesso", type="primary", icon=":material/block:"):
        if email_remover != "--- Selecione ---":
            if email_remover == st.session_state['email_usuario']:
                st.error("Não pode remover o seu próprio acesso enquanto está logado!")
            else:
                remover_usuario(email_remover)
                st.success(f"Acesso de {email_remover} revogado.")
                st.rerun()

# ==========================================
# ABA 3: SISTEMA (PARÂMETROS DO GERADOR DE RPL)
# ==========================================
with aba3:
    # --- 4.A CÓDIGOS DE AEROPORTOS ---
    st.subheader(":material/local_airport: Conversor IATA/ICAO")
    st.caption("Converte o código IATA do arquivo de voos (ex: CGH) no código ICAO usado no RPL (ex: SBSP).")

    df_aero = get_aeroportos()
    ALTURA_AERO = 280
    c_ae1, c_ae2, c_ae3 = st.columns([2, 1, 1])
    with c_ae1:
        st.dataframe(df_aero, use_container_width=True, hide_index=True, height=ALTURA_AERO, column_order=['IATA', 'ICAO'])
    with c_ae2:
        with st.form("form_add_aero", clear_on_submit=True, height=ALTURA_AERO):
            st.markdown(":material/add: **Adicionar**")
            n_iata = st.text_input("IATA (ex: CGH)", max_chars=3)
            n_icao = st.text_input("ICAO (ex: SBSP)", max_chars=4)
            if st.form_submit_button("Guardar", type="primary", icon=":material/check_circle:"):
                if n_iata and n_icao:
                    adicionar_aeroporto(n_iata, n_icao)
                    st.success(f"{n_iata.upper()} → {n_icao.upper()} guardado!", icon=":material/check_circle:")
                    st.rerun()
                else:
                    st.error("Preencha ambos os campos.", icon=":material/warning:")
    with c_ae3:
        with st.container(border=True, height=ALTURA_AERO):
            st.markdown(":material/delete: **Remover**")
            aero_remover = st.selectbox("IATA a remover", ["--- Selecione ---"] + df_aero['IATA'].tolist(), key="sel_remover_aero")
            if st.button("Remover Aeroporto", type="secondary", icon=":material/delete:"):
                if aero_remover != "--- Selecione ---":
                    remover_aeroporto(aero_remover)
                    st.success(f"Aeroporto {aero_remover} removido.")
                    st.rerun()

    st.divider()

    # --- 4.B MAPEAMENTO DE EQUIPAMENTOS ---
    st.subheader(":material/flight: Mapeamento de Equipamentos")
    st.caption("Converte o código de equipamento do arquivo de voos (ex: 73G) no tipo usado no RPL (ex: B737/M).")

    df_equip = get_equipamentos()
    ALTURA_EQUIP = 280
    c_eq1, c_eq2, c_eq3 = st.columns([2, 1, 1])
    with c_eq1:
        st.dataframe(df_equip, use_container_width=True, hide_index=True, height=ALTURA_EQUIP)
    with c_eq2:
        with st.form("form_add_equip", clear_on_submit=True, height=ALTURA_EQUIP):
            st.markdown(":material/add: **Adicionar**")
            eq_codigo = st.text_input("Código (ex: 73G)", max_chars=10)
            eq_tipo = st.text_input("Tipo RPL (ex: B737/M)", max_chars=15)
            if st.form_submit_button("Guardar", type="primary", icon=":material/check_circle:"):
                if eq_codigo and eq_tipo:
                    adicionar_equipamento(eq_codigo, eq_tipo)
                    st.success(f"{eq_codigo.upper()} → {eq_tipo.upper()} guardado!", icon=":material/check_circle:")
                    st.rerun()
                else:
                    st.error("Preencha ambos os campos.", icon=":material/warning:")
    with c_eq3:
        with st.container(border=True, height=ALTURA_EQUIP):
            st.markdown(":material/delete: **Remover**")
            eq_remover = st.selectbox("Código a remover", ["--- Selecione ---"] + df_equip['CODIGO'].tolist(), key="sel_remover_equip")
            if st.button("Remover Equipamento", type="secondary", icon=":material/delete:"):
                if eq_remover != "--- Selecione ---":
                    remover_equipamento(eq_remover)
                    st.success(f"Equipamento {eq_remover} removido.")
                    st.rerun()

    st.divider()

    # --- 4.C PREFIXOS BRASIL ---
    st.subheader(":material/flag: Prefixos ICAO Considerados")
    st.caption("Só são gerados voos cujo aeródromo de origem e destino comecem com um destes prefixos.")

    df_prefixos = get_prefixos_br()
    ALTURA_PREFIXO = 220
    c_pf1, c_pf2, c_pf3 = st.columns([2, 1, 1])
    with c_pf1:
        st.dataframe(df_prefixos, use_container_width=True, hide_index=True, height=ALTURA_PREFIXO)
    with c_pf2:
        with st.form("form_add_prefixo", clear_on_submit=True, height=ALTURA_PREFIXO):
            st.markdown(":material/add: **Adicionar**")
            novo_prefixo = st.text_input("Prefixo (2 letras, ex: SB)", max_chars=2)
            if st.form_submit_button("Guardar", type="primary", icon=":material/check_circle:"):
                if novo_prefixo:
                    adicionar_prefixo_br(novo_prefixo)
                    st.success(f"Prefixo {novo_prefixo.upper()} adicionado!", icon=":material/check_circle:")
                    st.rerun()
                else:
                    st.error("Preencha o prefixo.", icon=":material/warning:")
    with c_pf3:
        with st.container(border=True, height=ALTURA_PREFIXO):
            st.markdown(":material/delete: **Remover**")
            prefixo_remover = st.selectbox("Prefixo a remover", ["--- Selecione ---"] + df_prefixos['PREFIXO'].tolist(), key="sel_remover_prefixo")
            if st.button("Remover Prefixo", type="secondary", icon=":material/delete:"):
                if prefixo_remover != "--- Selecione ---":
                    remover_prefixo_br(prefixo_remover)
                    st.success(f"Prefixo {prefixo_remover} removido.")
                    st.rerun()

    st.divider()

    # --- 4.D AERÓDROMOS EXCLUÍDOS ---
    st.subheader(":material/block: Aeródromos Excluídos")
    st.caption("Voos com origem ou destino nestes aeródromos nunca são incluídos no RPL, mesmo que atendam aos prefixos acima.")

    df_excluidos = get_aerodromos_excluidos()
    ALTURA_EXCLUIDO = 220
    c_ex1, c_ex2, c_ex3 = st.columns([2, 1, 1])
    with c_ex1:
        st.dataframe(df_excluidos, use_container_width=True, hide_index=True, height=ALTURA_EXCLUIDO)
    with c_ex2:
        with st.form("form_add_excluido", clear_on_submit=True, height=ALTURA_EXCLUIDO):
            st.markdown(":material/add: **Adicionar**")
            novo_excluido = st.text_input("Código ICAO (ex: SBJP)", max_chars=4)
            if st.form_submit_button("Guardar", type="primary", icon=":material/check_circle:"):
                if novo_excluido:
                    adicionar_aerodromo_excluido(novo_excluido)
                    st.success(f"Aeródromo {novo_excluido.upper()} excluído do RPL!", icon=":material/check_circle:")
                    st.rerun()
                else:
                    st.error("Preencha o código ICAO.", icon=":material/warning:")
    with c_ex3:
        with st.container(border=True, height=ALTURA_EXCLUIDO):
            st.markdown(":material/delete: **Remover da exclusão**")
            excluido_remover = st.selectbox("Código a remover", ["--- Selecione ---"] + df_excluidos['ICAO'].tolist(), key="sel_remover_excluido")
            if st.button("Remover da Lista", type="secondary", icon=":material/delete:"):
                if excluido_remover != "--- Selecione ---":
                    remover_aerodromo_excluido(excluido_remover)
                    st.success(f"Aeródromo {excluido_remover} voltará a ser incluído no RPL.")
                    st.rerun()