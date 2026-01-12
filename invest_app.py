import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import streamlit_authenticator as stauth
from sqlalchemy import text

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestor Financeiro Neon", layout="wide")

# Conexão com o Neon SQL
conn = st.connection("postgresql", type="sql")

# LOGIN CONFIG
names = ["Usuario Teste"]
usernames = ["admin"]
passwords = ["12345"]

authenticator = stauth.Authenticate(
    {"usernames": {usernames[0]: {"name": names[0], "password": passwords[0]}}},
    "cookie_invest", "key_invest", cookie_expiry_days=30
)

authenticator.login(location="main")

if st.session_state["authentication_status"]:
    
    # 1. CARREGAR DADOS
    try:
        # Tenta ler as tabelas. Se não existirem, o except cuida.
        df_ativos = conn.query("SELECT tipo, nome, valor_atual, aporte_mensal, juros_mensal FROM ativos", ttl=0)
        df_config = conn.query("SELECT valor_meta, tempo_anos FROM config WHERE id = 1", ttl=0)
        
        meta_inicial = float(df_config["valor_meta"].iloc[0]) if not df_config.empty else 100000.0
        tempo_inicial = int(df_config["tempo_anos"].iloc[0]) if not df_config.empty else 10
    except Exception:
        df_ativos = pd.DataFrame(columns=["tipo", "nome", "valor_atual", "aporte_mensal", "juros_mensal"])
        meta_inicial, tempo_inicial = 100000.0, 10

    with st.sidebar:
        st.header("🎯 Metas")
        valor_meta = st.number_input("Objetivo (R$)", min_value=1.0, value=meta_inicial)
        tempo_anos = st.slider("Anos", 1, 40, value=tempo_inicial)
        
        if st.button("💾 Salvar no Neon SQL"):
            try:
                with conn.session as s:
                    # Garantir que as tabelas existam
                    s.execute(text("CREATE TABLE IF NOT EXISTS ativos (tipo TEXT, nome TEXT, valor_atual FLOAT, aporte_mensal FLOAT, juros_mensal FLOAT)"))
                    s.execute(text("CREATE TABLE IF NOT EXISTS config (id INT PRIMARY KEY, valor_meta FLOAT, tempo_anos INT)"))
                    
                    # Limpar ativos antigos e inserir novos
                    s.execute(text("DELETE FROM ativos"))
                    for _, row in df_ativos.iterrows():
                        s.execute(
                            text("INSERT INTO ativos (tipo, nome, valor_atual, aporte_mensal, juros_mensal) VALUES (:t, :n, :v, :a, :j)"),
                            {"t": row.tipo, "n": row.nome, "v": row.valor_atual, "a": row.aporte_mensal, "j": row.juros_mensal}
                        )
                    
                    # Upsert da configuração da meta
                    s.execute(
                        text("INSERT INTO config (id, valor_meta, tempo_anos) VALUES (1, :m, :t) ON CONFLICT (id) DO UPDATE SET valor_meta = EXCLUDED.valor_meta, tempo_anos = EXCLUDED.tempo_anos"),
                        {"m": valor_meta, "t": tempo_anos}
                    )
                    s.commit()
                st.success("Conexão OK! Dados salvos no Neon.")
                st.balloons()
            except Exception as e:
                st.error(f"Erro de Conexão: {e}")
        
        st.markdown("---")
        authenticator.logout("Sair", "sidebar")

    st.title("📊 Gestor Financeiro (Neon SQL)")

    # 2. EDITOR DE DADOS
    st.subheader("📝 Seus Investimentos")
    df_ativos = st.data_editor(df_ativos, num_rows="dynamic", use_container_width=True)

    # 3. DASHBOARD
    if not df_ativos.empty:
        for col in ["valor_atual", "aporte_mensal", "juros_mensal"]:
            df_ativos[col] = pd.to_numeric(df_ativos[col], errors='coerce').fillna(0)
            
        total = df_ativos["valor_atual"].sum()
        st.metric("Patrimônio Acumulado", f"R$ {total:,.2f}")
        
        fig = go.Figure(data=[go.Pie(labels=df_ativos["nome"], values=df_ativos["valor_atual"], hole=.4)])
        st.plotly_chart(fig, use_container_width=True)

elif st.session_state["authentication_status"] is False:
    st.error("Login ou senha inválidos")
