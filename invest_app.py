import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import streamlit_authenticator as stauth
from sqlalchemy import text

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestor Financeiro PRO", layout="wide")

# Conexão robusta com o banco (Neon SQL)
conn = st.connection("postgresql", type="sql")

# --- SISTEMA DE LOGIN ---
names = ["Usuario Teste"]
usernames = ["admin"]
passwords = ["12345"]

authenticator = stauth.Authenticate(
    {"usernames": {usernames[0]: {"name": names[0], "password": passwords[0]}}},
    "cookie_invest", "key_invest", cookie_expiry_days=30
)

authenticator.login(location="main")

# --- APP PRINCIPAL ---
if st.session_state["authentication_status"]:
    
    # 1. CARREGAR DADOS DO BANCO
    try:
        # ttl=0 garante que ele busque dados novos toda vez
        df_ativos = conn.query("SELECT tipo, nome, valor_atual, aporte_mensal, juros_mensal FROM ativos", ttl=0)
        df_config = conn.query("SELECT valor_meta, tempo_anos FROM config WHERE id = 1", ttl=0)
        
        if not df_config.empty:
            meta_inicial = float(df_config["valor_meta"].iloc[0])
            tempo_inicial = int(df_config["tempo_anos"].iloc[0])
        else:
            meta_inicial, tempo_inicial = 100000.0, 10
    except Exception:
        # Fallback se as tabelas ainda não existirem
        df_ativos = pd.DataFrame(columns=["tipo", "nome", "valor_atual", "aporte_mensal", "juros_mensal"])
        meta_inicial, tempo_inicial = 100000.0, 10

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("🎯 Metas")
        valor_meta = st.number_input("Objetivo Final (R$)", min_value=1.0, value=meta_inicial)
        tempo_anos = st.slider("Prazo (Anos)", 1, 40, value=tempo_inicial)
        
        st.markdown("---")
        if st.button("💾 Salvar no Neon SQL"):
            try:
                with conn.session as s:
                    # Criação automática das tabelas
                    s.execute(text("""
                        CREATE TABLE IF NOT EXISTS ativos (
                            tipo TEXT, nome TEXT, valor_atual FLOAT, 
                            aporte_mensal FLOAT, juros_mensal FLOAT
                        )
                    """))
                    s.execute(text("""
                        CREATE TABLE IF NOT EXISTS config (
                            id INT PRIMARY KEY, valor_meta FLOAT, tempo_anos INT
                        )
                    """))
                    
                    # Limpa e reinsere os ativos
                    s.execute(text("DELETE FROM ativos"))
                    for _, row in df_ativos.iterrows():
                        s.execute(
                            text("INSERT INTO ativos (tipo, nome, valor_atual, aporte_mensal, juros_mensal) VALUES (:t, :n, :v, :a, :j)"),
                            {"t": row.tipo, "n": row.nome, "v": row.valor_atual, "a": row.aporte_mensal, "j": row.juros_mensal}
                        )
                    
                    # Atualiza a meta (Upsert)
                    s.execute(
                        text("""
                            INSERT INTO config (id, valor_meta, tempo_anos) VALUES (1, :m, :t) 
                            ON CONFLICT (id) DO UPDATE SET valor_meta = EXCLUDED.valor_meta, tempo_anos = EXCLUDED.tempo_anos
                        """),
                        {"m": valor_meta, "t": tempo_anos}
                    )
                    s.commit()
                st.success("Dados salvos com sucesso!")
                st.balloons()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")
        
        st.markdown("---")
        authenticator.logout("Sair", "sidebar")

    # --- INTERFACE PRINCIPAL ---
    st.title("📊 Gestor Financeiro")

    # Tabela editável
    st.subheader("📝 Meus Ativos")
    df_ativos = st.data_editor(df_ativos, num_rows="dynamic", use_container_width=True)

    # Cálculos rápidos
    if not df_ativos.empty:
        # Garante que os valores são numéricos
        for col in ["valor_atual", "aporte_mensal", "juros_mensal"]:
            df_ativos[col] = pd.to_numeric(df_ativos[col], errors='coerce').fillna(0)

        total_atual = df_ativos["valor_atual"].sum()
        
        st.markdown("---")
        c1, c2 = st.columns(2)
        c1.metric("Patrimônio Atual", f"R$ {total_atual:,.2f}")
        c2.metric("Meta Objetivo", f"R$ {valor_meta:,.2f}")
        
        # Gráfico Simples
        fig = go.Figure(data=[go.Pie(labels=df_ativos["nome"], values=df_ativos["valor_atual"], hole=.3)])
        st.plotly_chart(fig, use_container_width=True)

elif st.session_state["authentication_status"] is False:
    st.error("Login inválido.")
