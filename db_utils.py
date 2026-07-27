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

COLUNAS_ROTAS = ['DE', 'PARA', 'MACH', 'FL', 'ROTA', 'EET', 'TV', 'HORA INICIO', 'HORA FIM']

def save_rotas(df: pd.DataFrame):
    if conn is None: return
    try:
        df = df.reindex(columns=COLUNAS_ROTAS)
        with conn.session as s:
            s.execute(text("TRUNCATE TABLE rotas"))
            # Insere na mesma transação do TRUNCATE: se a inserção falhar, o TRUNCATE
            # também é revertido e a tabela não fica vazia por engano.
            df.to_sql('rotas', con=s.connection(), if_exists='append', index=False, method='multi', chunksize=1000)
            s.commit()
        st.success("Rotas atualizadas com sucesso!")
    except Exception as e:
        st.error(f"Falha ao salvar rotas: {e}")

def adicionar_aeroporto(iata: str, icao: str) -> bool:
    """Adiciona um código IATA/ICAO; se o IATA já existir, atualiza o ICAO."""
    if conn is None: return False
    try:
        with conn.session as s:
            iata_v, icao_v = iata.upper().strip(), icao.upper().strip()
            s.execute(text('DELETE FROM aeroportos WHERE "IATA" = :iata'), {"iata": iata_v})
            s.execute(text('INSERT INTO aeroportos ("IATA", "ICAO") VALUES (:iata, :icao)'),
                       {"iata": iata_v, "icao": icao_v})
            s.commit()
        return True
    except Exception:
        return False

def remover_aeroporto(iata: str) -> bool:
    if conn is None: return False
    try:
        with conn.session as s:
            s.execute(text('DELETE FROM aeroportos WHERE "IATA" = :iata'), {"iata": iata})
            s.commit()
        return True
    except Exception:
        return False

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
            s.execute(text('CREATE TABLE IF NOT EXISTS config_textos ("chave" TEXT PRIMARY KEY, "valor" TEXT NOT NULL)'))
            s.execute(text('CREATE TABLE IF NOT EXISTS equipamentos ("CODIGO" TEXT PRIMARY KEY, "TIPO" TEXT NOT NULL)'))
            s.execute(text('CREATE TABLE IF NOT EXISTS prefixos_br ("PREFIXO" TEXT PRIMARY KEY)'))
            s.execute(text('CREATE TABLE IF NOT EXISTS aerodromos_excluidos ("ICAO" TEXT PRIMARY KEY)'))

            # Seeds: só insere os valores padrão de fábrica se a tabela estiver
            # completamente vazia, para não "ressuscitar" itens que o utilizador apagou.
            s.execute(text('''
                INSERT INTO config_textos ("chave", "valor")
                SELECT * FROM (VALUES
                    ('DEFAULT_RMK_1', 'EQPT/SDFGIKRWY/LB1 STS/ATFMX'),
                    ('DEFAULT_RMK_2', 'PBN/B1C1D1O1S2T1 EET/SBCW0003'),
                    ('DEFAULT_ROUTE', 'N0000 000 ROUTE UNKNOWN')
                ) AS v("chave", "valor")
                WHERE NOT EXISTS (SELECT 1 FROM config_textos)
            '''))
            s.execute(text('''
                INSERT INTO equipamentos ("CODIGO", "TIPO")
                SELECT * FROM (VALUES
                    ('73G','B737/M'), ('73M','B738/M'), ('73X','B738/M'), ('738','B738/M'),
                    ('73A','B738/M'), ('7M8','B38M/M'), ('7ME','B38M/M')
                ) AS v("CODIGO", "TIPO")
                WHERE NOT EXISTS (SELECT 1 FROM equipamentos)
            '''))
            s.execute(text('''
                INSERT INTO prefixos_br ("PREFIXO")
                SELECT * FROM (VALUES ('SB'),('SD'),('SI'),('SJ'),('SN'),('SS'),('SW')) AS v("PREFIXO")
                WHERE NOT EXISTS (SELECT 1 FROM prefixos_br)
            '''))
            s.execute(text('''
                INSERT INTO aerodromos_excluidos ("ICAO")
                SELECT * FROM (VALUES ('SBJP')) AS v("ICAO")
                WHERE NOT EXISTS (SELECT 1 FROM aerodromos_excluidos)
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
    if conn is None: return False
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
    if conn is None: return False
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
    if conn is None: return False
    try:
        with conn.session as s:
            s.execute(text("DELETE FROM usuarios WHERE email = :email"), {"email": email.lower().strip()})
            s.commit()
        return True
    except Exception:
        return False

# ==========================================
# GESTÃO DE CONFIGURAÇÕES INTERNAS DO SISTEMA (RPL)
# ==========================================

def get_config_textos() -> dict:
    """Retorna {chave: valor} para os textos padrão (RMK1, RMK2, ROTA padrão)."""
    if conn is None: return {}
    try:
        df = conn.query('SELECT "chave", "valor" FROM config_textos', ttl=0)
        return dict(zip(df['chave'], df['valor'])) if df is not None and not df.empty else {}
    except exc.SQLAlchemyError:
        return {}

def salvar_config_texto(chave: str, valor: str) -> bool:
    if conn is None: return False
    try:
        with conn.session as s:
            s.execute(text('UPDATE config_textos SET "valor" = :valor WHERE "chave" = :chave'),
                       {"valor": valor, "chave": chave})
            s.commit()
        return True
    except Exception:
        return False

def get_equipamentos() -> pd.DataFrame:
    if conn is None: return pd.DataFrame(columns=['CODIGO', 'TIPO'])
    try:
        df = conn.query('SELECT * FROM equipamentos ORDER BY "CODIGO"', ttl=0)
        return df if df is not None and not df.empty else pd.DataFrame(columns=['CODIGO', 'TIPO'])
    except exc.SQLAlchemyError:
        return pd.DataFrame(columns=['CODIGO', 'TIPO'])

def adicionar_equipamento(codigo: str, tipo: str) -> bool:
    if conn is None: return False
    try:
        with conn.session as s:
            s.execute(text(
                'INSERT INTO equipamentos ("CODIGO", "TIPO") VALUES (:codigo, :tipo) '
                'ON CONFLICT ("CODIGO") DO UPDATE SET "TIPO" = EXCLUDED."TIPO"'
            ), {"codigo": codigo.upper().strip(), "tipo": tipo.upper().strip()})
            s.commit()
        return True
    except Exception:
        return False

def remover_equipamento(codigo: str) -> bool:
    if conn is None: return False
    try:
        with conn.session as s:
            s.execute(text('DELETE FROM equipamentos WHERE "CODIGO" = :codigo'), {"codigo": codigo})
            s.commit()
        return True
    except Exception:
        return False

def get_prefixos_br() -> pd.DataFrame:
    if conn is None: return pd.DataFrame(columns=['PREFIXO'])
    try:
        df = conn.query('SELECT * FROM prefixos_br ORDER BY "PREFIXO"', ttl=0)
        return df if df is not None and not df.empty else pd.DataFrame(columns=['PREFIXO'])
    except exc.SQLAlchemyError:
        return pd.DataFrame(columns=['PREFIXO'])

def adicionar_prefixo_br(prefixo: str) -> bool:
    if conn is None: return False
    try:
        with conn.session as s:
            s.execute(text(
                'INSERT INTO prefixos_br ("PREFIXO") VALUES (:p) ON CONFLICT ("PREFIXO") DO NOTHING'
            ), {"p": prefixo.upper().strip()})
            s.commit()
        return True
    except Exception:
        return False

def remover_prefixo_br(prefixo: str) -> bool:
    if conn is None: return False
    try:
        with conn.session as s:
            s.execute(text('DELETE FROM prefixos_br WHERE "PREFIXO" = :p'), {"p": prefixo})
            s.commit()
        return True
    except Exception:
        return False

def get_aerodromos_excluidos() -> pd.DataFrame:
    if conn is None: return pd.DataFrame(columns=['ICAO'])
    try:
        df = conn.query('SELECT * FROM aerodromos_excluidos ORDER BY "ICAO"', ttl=0)
        return df if df is not None and not df.empty else pd.DataFrame(columns=['ICAO'])
    except exc.SQLAlchemyError:
        return pd.DataFrame(columns=['ICAO'])

def adicionar_aerodromo_excluido(icao: str) -> bool:
    if conn is None: return False
    try:
        with conn.session as s:
            s.execute(text(
                'INSERT INTO aerodromos_excluidos ("ICAO") VALUES (:icao) ON CONFLICT ("ICAO") DO NOTHING'
            ), {"icao": icao.upper().strip()})
            s.commit()
        return True
    except Exception:
        return False

def remover_aerodromo_excluido(icao: str) -> bool:
    if conn is None: return False
    try:
        with conn.session as s:
            s.execute(text('DELETE FROM aerodromos_excluidos WHERE "ICAO" = :icao'), {"icao": icao})
            s.commit()
        return True
    except Exception:
        return False

init_db()
