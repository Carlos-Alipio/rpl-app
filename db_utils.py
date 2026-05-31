import sqlite3
import pandas as pd

DB_PATH = 'database.sqlite'

def get_rotas():
    """Lê a tabela de rotas da base de dados e devolve um DataFrame."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM rotas", conn)
    conn.close()
    return df

def get_aeroportos():
    """Lê a tabela de aeroportos da base de dados e devolve um DataFrame."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM aeroportos", conn)
    conn.close()
    return df

def save_rotas(df):
    """Guarda as alterações feitas na tabela de rotas."""
    conn = sqlite3.connect(DB_PATH)
    df.to_sql('rotas', conn, if_exists='replace', index=False)
    conn.close()

def save_aeroportos(df):
    """Guarda as alterações feitas na tabela de aeroportos."""
    conn = sqlite3.connect(DB_PATH)
    df.to_sql('aeroportos', conn, if_exists='replace', index=False)
    conn.close()

import bcrypt

# ==========================================
# GESTÃO DE UTILIZADORES E SEGURANÇA
# ==========================================
def init_db():
    """Cria a tabela de utilizadores e um admin padrão, corrigindo problemas de colunas se necessário."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. Verifica se a tabela existe E se tem a coluna nova 'precisa_trocar_senha'
    try:
        c.execute("SELECT precisa_trocar_senha FROM usuarios LIMIT 1")
    except sqlite3.OperationalError:
        # Se deu erro, a tabela não existe ou é a versão antiga do seu outro app. Vamos recriar do zero!
        c.execute("DROP TABLE IF EXISTS usuarios")
        c.execute('''
            CREATE TABLE usuarios (
                email TEXT PRIMARY KEY,
                senha_hash TEXT NOT NULL,
                precisa_trocar_senha BOOLEAN NOT NULL CHECK (precisa_trocar_senha IN (0, 1))
            )
        ''')
        conn.commit()
    
    # 2. Se a tabela estiver vazia, cria o primeiro Administrador de emergência
    c.execute("SELECT COUNT(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        senha_padrao = bcrypt.hashpw("glo2026".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        c.execute("INSERT INTO usuarios (email, senha_hash, precisa_trocar_senha) VALUES (?, ?, 1)",
                  ("admin@glo.com.br", senha_padrao))
        conn.commit()
        
    conn.close()

def verificar_login(email, senha):
    """Verifica se o email existe e se a senha criptografada bate certo."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT senha_hash, precisa_trocar_senha FROM usuarios WHERE email = ?", (email.lower().strip(),))
    user = c.fetchone()
    conn.close()

    if user:
        senha_hash = user[0]
        precisa_trocar = bool(user[1])
        # Compara a senha digitada com o Hash na base de dados
        if bcrypt.checkpw(senha.encode('utf-8'), senha_hash.encode('utf-8')):
            return True, precisa_trocar
    return False, False

def atualizar_senha(email, nova_senha):
    """Guarda a nova senha do utilizador e tira a obrigatoriedade de troca."""
    novo_hash = bcrypt.hashpw(nova_senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE usuarios SET senha_hash = ?, precisa_trocar_senha = 0 WHERE email = ?", 
              (novo_hash, email.lower().strip()))
    conn.commit()
    conn.close()

def adicionar_usuario(email, senha_provisoria):
    """Usado pelo Admin para pré-autorizar um novo operador."""
    hash_senha = bcrypt.hashpw(senha_provisoria.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        # Coloca 1 (True) para forçar o operador a mudar a senha no primeiro acesso
        c.execute("INSERT INTO usuarios (email, senha_hash, precisa_trocar_senha) VALUES (?, ?, 1)", 
                  (email.lower().strip(), hash_senha))
        conn.commit()
        sucesso = True
    except sqlite3.IntegrityError:
        sucesso = False # O e-mail já existe
    conn.close()
    return sucesso

def get_usuarios():
    """Lê a lista de acessos para o painel de configurações."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT email, precisa_trocar_senha FROM usuarios", conn)
    conn.close()
    return df

def remover_usuario(email):
    """Remove o acesso de um utilizador."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM usuarios WHERE email = ?", (email.lower().strip(),))
    conn.commit()
    conn.close()

# Executa a inicialização sempre que o sistema arranca
init_db()