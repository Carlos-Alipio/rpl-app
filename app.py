import streamlit as st
import time
import base64
from db_utils import verificar_login, atualizar_senha, init_db

# Garante que a base de dados acorda e se auto-repara mal a nuvem liga!
init_db()

# ==========================================
# 1. CONFIGURAÇÃO BASE E LOGÓTIPO
# ==========================================
st.set_page_config(
    page_title="Sistema RPL - GLO",
    page_icon="assets/logo-voegol-new.svg", # Muda o ícone na aba do navegador!
    layout="wide",
    initial_sidebar_state="expanded"
)

with open("assets/logo-voegol-new.svg", "rb") as _f:
    _logo_b64 = base64.b64encode(_f.read()).decode()

# Estilização CSS injetada diretamente (Layout Premium)
st.markdown("""
    <style>
    /* Oculta o cabeçalho padrão do Streamlit (substituído pela faixa laranja) */
    header[data-testid="stHeader"] {display: none;}

    /* Faixa laranja fixa no topo, acima do menu lateral e do conteúdo */
    .topbar-gol {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 3.5rem;
        background-color: #FF7020;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 1.5rem;
        z-index: 999999;
    }
    .topbar-gol .topbar-brand {
        display: flex;
        align-items: center;
        gap: 1.25rem;
    }
    .topbar-gol .topbar-brand img {
        height: 20px;
        /* Converte a marca para branco sobre o fundo laranja */
        filter: brightness(0) invert(1);
    }
    .topbar-gol .topbar-brand span {
        color: #fff;
        font-weight: 700;
        font-size: 1rem;
        letter-spacing: 0.02em;
    }
    .topbar-gol .topbar-user {
        color: #fff;
        font-size: 0.875rem;
    }

    /* Empurra o menu lateral e o conteúdo principal para baixo da faixa */
    div[data-testid="stAppViewContainer"] {
        padding-top: 3.5rem;
    }

    /* Menu lateral sempre visível: esconde os controlos de recolher/expandir */
    [data-testid="stSidebarCollapseButton"] {display: none;}
    [data-testid="stExpandSidebarButton"] {display: none;}

    /* Letra um pouco maior no menu lateral */
    [data-testid="stSidebarNavLink"] span[label] {
        font-size: 1rem;
    }
    [data-testid="stNavSectionHeader"] {
        font-size: 0.9rem;
    }

    /* Botões mais elegantes, na mesma cor laranja da faixa superior */
    button[data-baseweb="button"] {
        border-radius: 8px;
    }
    button[data-testid^="stBaseButton-primary"] {
        background-color: #FF7020;
        border-color: #FF7020;
        color: #fff;
    }
    button[data-testid^="stBaseButton-primary"]:hover,
    button[data-testid^="stBaseButton-primary"]:active,
    button[data-testid^="stBaseButton-primary"]:focus:not(:active) {
        background-color: #e0611c;
        border-color: #e0611c;
        color: #fff;
    }
    button[data-testid^="stBaseButton-secondary"] {
        border-color: #FF7020;
        color: #FF7020;
    }
    button[data-testid^="stBaseButton-secondary"]:hover,
    button[data-testid^="stBaseButton-secondary"]:active,
    button[data-testid^="stBaseButton-secondary"]:focus:not(:active) {
        border-color: #FF7020;
        color: #FF7020;
        background-color: rgba(255, 112, 32, 0.08);
    }
    </style>
""", unsafe_allow_html=True)

# 2. Memória do Sistema de Segurança
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False
    st.session_state['precisa_trocar_senha'] = False
    st.session_state['email_usuario'] = ""

# ==========================================
# FAIXA LARANJA (TOPO, SEMPRE VISÍVEL)
# ==========================================
_email_logado = st.session_state['email_usuario'] if st.session_state['autenticado'] else ""
st.markdown(f"""
    <div class="topbar-gol">
        <div class="topbar-brand">
            <img src="data:image/svg+xml;base64,{_logo_b64}" alt="GOL">
            <span>Sistema RPL</span>
        </div>
        <div class="topbar-user">{_email_logado}</div>
    </div>
""", unsafe_allow_html=True)

# ==========================================
# TELA DE LOGIN (SEM MENU LATERAL)
# ==========================================
if not st.session_state['autenticado']:
    # Esconde o menu lateral obrigatoriamente
    st.markdown("<style>[data-testid='stSidebar'] {display: none;}</style>", unsafe_allow_html=True)
    
    st.title(":material/lock: Login Sistema RPL")
    st.markdown("Insira o seu e-mail corporativo pré-autorizado para aceder à plataforma.")
    
    # Caixa centralizada para o formulário de login
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.container(border=True):
            with st.form("login_form"):
                email = st.text_input("E-mail corporativo", placeholder="exemplo@glo.com.br")
                senha = st.text_input("Palavra-passe", type="password")
                
                st.write("") # Espaço em branco
                submit = st.form_submit_button("Entrar no Sistema", type="primary", use_container_width=True)
                
                if submit:
                    sucesso, precisa_trocar = verificar_login(email, senha)
                    if sucesso:
                        st.session_state['autenticado'] = True
                        st.session_state['precisa_trocar_senha'] = precisa_trocar
                        st.session_state['email_usuario'] = email.lower().strip()
                        st.rerun()
                    else:
                        st.error("E-mail ou palavra-passe incorretos.", icon=":material/error:")

# ==========================================
# USUÁRIO LOGADO
# ==========================================
else:
    # --- FASE A: TROCA DE SENHA OBRIGATÓRIA ---
    if st.session_state['precisa_trocar_senha']:
        # Mantém o menu escondido
        st.markdown("<style>[data-testid='stSidebar'] {display: none;}</style>", unsafe_allow_html=True)
        
        st.warning("**Primeiro Acesso:** Por motivos de segurança corporativa, é obrigatório alterar a sua palavra-passe provisória.", icon=":material/warning:")
        
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            with st.form("form_troca_senha", border=True):
                nova_senha = st.text_input("Nova Palavra-passe", type="password", help="Mínimo de 6 caracteres")
                confirma_senha = st.text_input("Confirmar Nova Palavra-passe", type="password")
                
                st.write("")
                if st.form_submit_button("Atualizar e Entrar", type="primary", use_container_width=True):
                    if len(nova_senha) < 6:
                        st.error("A senha deve ter pelo menos 6 caracteres.")
                    elif nova_senha != confirma_senha:
                        st.error("As senhas não coincidem. Tente novamente.")
                    else:
                        atualizar_senha(st.session_state['email_usuario'], nova_senha)
                        st.session_state['precisa_trocar_senha'] = False
                        st.success("Senha atualizada com sucesso! A redirecionar...", icon=":material/check_circle:")
                        time.sleep(1.5)
                        st.rerun()
                    
    # --- FASE B: SISTEMA PRINCIPAL COM MENU LATERAL ---
    else:
        # 1. Definição das Páginas (Mapeia para os ficheiros da pasta pages/)
        pg_rpl = st.Page("app_pages/1_✈️_Gerador_RPL.py", title="Gerador RPL", icon=":material/flight_takeoff:", default=True)
        pg_config = st.Page("app_pages/2_⚙️_Configuracoes.py", title="Configurações", icon=":material/settings:")

        # 2. Construção da Navegação Sectorizada (Operacional / Ajustes)
        pg = st.navigation({
            "Operacional": [pg_rpl],
            "Ajustes": [pg_config],
        })

        # 3. Roda a página selecionada
        pg.run()

        # 4. Botão de Logout no fundo do Sidebar
        if st.sidebar.button("Sair do Sistema", icon=":material/logout:", use_container_width=True):
            st.session_state['autenticado'] = False
            st.session_state['email_usuario'] = ""
            st.rerun()