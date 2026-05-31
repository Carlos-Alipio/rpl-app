import streamlit as st
import time
from db_utils import verificar_login, atualizar_senha

st.set_page_config(page_title="Login - Sistema RPL", page_icon="🔒", layout="centered")

# 1. Memória do Sistema
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False
    st.session_state['precisa_trocar_senha'] = False
    st.session_state['email_usuario'] = ""

# 2. SE O UTILIZADOR FEZ LOGIN COM SUCESSO
if st.session_state['autenticado']:
    
    # 2.A: Interseção de Segurança (Forçar troca de senha provisória)
    if st.session_state['precisa_trocar_senha']:
        st.warning("⚠️ **Primeiro Acesso:** Por motivos de segurança corporativa, é obrigatório alterar a sua palavra-passe provisória.")
        
        with st.form("form_troca_senha"):
            nova_senha = st.text_input("Nova Palavra-passe", type="password")
            confirma_senha = st.text_input("Confirmar Nova Palavra-passe", type="password")
            
            if st.form_submit_button("Atualizar Palavra-passe e Entrar", type="primary"):
                if len(nova_senha) < 6:
                    st.error("A senha deve ter pelo menos 6 caracteres.")
                elif nova_senha != confirma_senha:
                    st.error("As senhas não coincidem. Tente novamente.")
                else:
                    atualizar_senha(st.session_state['email_usuario'], nova_senha)
                    st.session_state['precisa_trocar_senha'] = False
                    st.success("✅ Senha atualizada com sucesso! A redirecionar para o sistema...")
                    time.sleep(1.5)
                    st.rerun()
                    
    # 2.B: Acesso Normal Liberado
    else:
        st.title("Bem-vindo ao Sistema RPL - GLO ✈️")
        st.success(f"✅ Sessão iniciada como: **{st.session_state['email_usuario']}**")
        st.markdown("""
        **Acesso autorizado.** Utilize o menu lateral esquerdo para navegar:
        * **✈️ Gerador RPL:** Processar os planos de voo.
        * **⚙️ Configurações:** Gerir malha e códigos.
        """)
        
        st.write("")
        if st.button("🚪 Sair (Logout)"):
            st.session_state['autenticado'] = False
            st.session_state['email_usuario'] = ""
            st.rerun()

# 3. SE O UTILIZADOR AINDA NÃO FEZ LOGIN
else:
    st.title("🔒 Acesso Restrito")
    st.markdown("Insira o seu e-mail corporativo pré-autorizado para aceder.")
    
    with st.container(border=True):
        with st.form("login_form"):
            email = st.text_input("E-mail corporativo")
            senha = st.text_input("Palavra-passe", type="password")
            
            submit = st.form_submit_button("Entrar no Sistema", type="primary", use_container_width=True)
            
            if submit:
                sucesso, precisa_trocar = verificar_login(email, senha)
                if sucesso:
                    st.session_state['autenticado'] = True
                    st.session_state['precisa_trocar_senha'] = precisa_trocar
                    st.session_state['email_usuario'] = email.lower().strip()
                    st.rerun()
                else:
                    st.error("❌ E-mail ou palavra-passe incorretos.")