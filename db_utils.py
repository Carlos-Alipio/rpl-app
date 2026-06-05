import streamlit as st
import pandas as pd
import bcrypt
from sqlalchemy import text, exc
from typing import Tuple, Optional

# ==========================================
# CONEXÃO COM O SUPABASE (SEGURANÇA & CACHING)
# ==========================================
try:
    conn = st.connection("supabase", type="sql", url=st.secrets.get("SUPABASE_URL"))
except Exception as e:
    st.error(f"Erro crítico de configuração do banco de dados: {e}")
    conn = None

# ==========================================
# GESTÃO DE ROTAS E AEROPORTOS
# ==========================================

def get_rotas() -> pd.DataFrame:
    if conn is None: return pd.DataFrame()
    try:
        df = conn.query("SELECT * FROM rotas", ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=['DE', 'PARA', 'MACH', 'FL', 'ROTA', 'EET', 'TV', 'HORA INICIO', 'HORA FIM'])
        return df
    except exc.SQLAlchemyError:
        return pd.DataFrame()

def get_aeroportos() -> pd.DataFrame:
    if conn is None: return pd.DataFrame()
    try:
        df = conn.query("SELECT * FROM aeroportos", ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=['IATA', 'ICAO', 'CIDADE', 'ESTADO'])
        return df
    except exc.SQLAlchemyError:
        return pd.DataFrame()

def save_rotas(df: pd.DataFrame):
    if conn is None: return
    try:
        with conn.session as s:
            s.execute(text("TRUNCATE TABLE rotas"))
            s.commit()
        df.to_sql('rotas', con=conn.engine, if_exists='append', index=False, method='multi', chunksize=1000)
        st.success("Rotas atualizadas com sucesso!")
    except Exception as e:
        st.error(f"Falha ao salvar rotas: {e}")

def save_aeroportos(df: pd.DataFrame):
    if conn is None: return
    try:
        with conn.session as s:
            s.execute(text("TRUNCATE TABLE aeroportos"))
            s.commit()
        df.to_sql('aeroportos', con=conn.engine, if_exists='append', index=False, method='multi', chunksize=1000)
        st.success("Aeroportos atualizados com sucesso!")
    except Exception as e:
        st.error(f"Falha ao salvar aeroportos: {e}")

# ==========================================
# GESTÃO DE UTILIZADORES E SEGURANÇA
# ==========================================

def init_db():
    if conn is None: return
    try:
        with conn.session as s:
            s.execute(text('''
                CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    senha_hash TEXT NOT NULL,
                    precisa_trocar_senha BOOLEAN DEFAULT TRUE
                )
            '''))
            s.execute(text('CREATE TABLE IF NOT EXISTS aeroportos ("IATA" TEXT, "ICAO" TEXT, "CIDADE" TEXT, "ESTADO" TEXT)'))
            s.execute(text('''
                CREATE TABLE IF NOT EXISTS rotas (
                    "DE" TEXT, "PARA" TEXT, "MACH" TEXT, "FL" TEXT, 
                    "ROTA" TEXT, "EET" TEXT, "TV" TEXT, 
                    "HORA INICIO" TEXT, "HORA FIM" TEXT
                )
            '''))
            s.commit()
    except exc.SQLAlchemyError:
        pass

def verificar_login(email: str, senha: str) -> Tuple[bool, bool]:
    if conn is None: return False, False
    try:
        with conn.session as s:
            query = text("SELECT senha_hash, precisa_trocar_senha FROM usuarios WHERE email = :email")
            result = s.execute(query, {"email": email.lower().strip()}).fetchone()

        if result:
            senha_hash, precisa_trocar = result
            if bcrypt.checkpw(senha.encode('utf-8'), senha_hash.encode('utf-8')):
                return True, precisa_trocar
    except Exception:
        pass
    return False, False

def atualizar_senha(email: str, nova_senha: str) -> bool:
    novo_hash = bcrypt.hashpw(nova_senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    try:
        with conn.session as s:
            s.execute(text(
                "UPDATE usuarios SET senha_hash = :hash, precisa_trocar_senha = FALSE WHERE email = :email"
            ), {"hash": novo_hash, "email": email.lower().strip()})
            s.commit()
        return True
    except Exception:
        return False

def adicionar_usuario(email: str, senha_provisoria: str) -> bool:
    hash_senha = bcrypt.hashpw(senha_provisoria.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    try:
        with conn.session as s:
            s.execute(text(
                "INSERT INTO usuarios (email, senha_hash, precisa_trocar_senha) VALUES (:email, :hash, TRUE)"
            ), {"email": email.lower().strip(), "hash": hash_senha})
            s.commit()
        return True
    except Exception:
        return False

def get_usuarios() -> pd.DataFrame:
    if conn is None: return pd.DataFrame()
    try:
        return conn.query("SELECT email, precisa_trocar_senha FROM usuarios", ttl=0)
    except Exception:
        return pd.DataFrame(columns=['email', 'precisa_trocar_senha'])

def remover_usuario(email: str) -> bool:
    try:
        with conn.session as s:
            s.execute(text("DELETE FROM usuarios WHERE email = :email"), {"email": email.lower().strip()})
            s.commit()
        return True
    except Exception:
        return False

init_db()
