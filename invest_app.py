import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import streamlit_authenticator as stauth
from sqlalchemy import create_engine

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestor Financeiro Local", layout="wide")

# Conexão SQLite (Cria um arquivo chamado invest.db no seu GitHub/Streamlit)
engine = create_engine("sqlite:///invest.db")

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
    
    # 1. CARREGAR DADOS DO SQLITE
    try:
        df_ativos = pd.read_sql("SELECT * FROM ativos", engine)
        df_config = pd.read_sql("SELECT * FROM config", engine)
        meta_inicial = float(df_config["valor_meta"].iloc[0])
        tempo_inicial = int(df_config["tempo_anos"].iloc[0])
    except:
        # Se o banco estiver vazio, cria estrutura padrão
        df_ativos = pd.DataFrame(columns=["tipo", "nome", "valor_atual", "aporte_mensal", "juros_mensal"])
        meta_inicial, tempo_inicial = 100000.0, 10

    with st.sidebar:
        st.header("🎯 Meta Principal")
        valor_meta = st.number_input("Objetivo Final (R$)", min_value=1.0, value=meta_inicial)
        tempo_anos = st.slider("Prazo (Anos)", 1, 40, value=tempo_inicial)
        
        st.markdown("---")
        if st.button("💾 Salvar Dados"):
            # Salva no SQLite (sobrescreve o anterior)
            df_ativos.to_sql("ativos", engine, if_exists="replace", index=False)
            df_meta_save = pd.DataFrame([{"valor_meta": valor_meta, "tempo_anos": tempo_anos}])
            df_meta_save.to_sql("config", engine, if_exists="replace", index=False)
            st.success("Dados salvos com sucesso no banco local!")
            st.balloons()
        
        st.markdown("---")
        authenticator.logout("Sair", "sidebar")

    st.title("📊 Minha Carteira (SQLite)")

    # 2. EDITOR DE TABELA
    st.subheader("📝 Seus Investimentos")
    df_ativos = st.data_editor(df_ativos, num_rows="dynamic", use_container_width=True)

    # --- 3. CÁLCULOS ---
    if not df_ativos.empty:
        # Garantir que são números
        for col in ["valor_atual", "aporte_mensal", "juros_mensal"]:
            df_ativos[col] = pd.to_numeric(df_ativos[col], errors='coerce').fillna(0)

        total_atual = df_ativos["valor_atual"].sum()
        meses = tempo_anos * 12
        evolucao_total = [0.0] * (meses + 1)
        
        for _, row in df_ativos.iterrows():
            v, a, j = row["valor_atual"], row["aporte_mensal"], row["juros_mensal"] / 100
            val_anterior = v
            for m in range(meses + 1):
                if m == 0: val_m = v
                else: val_m = (val_anterior * (1 + j)) + a
                evolucao_total[m] += val_m
                val_anterior = val_m

        # --- 4. DASHBOARD ---
        st.markdown("---")
        m1, m2, m3 = st.columns(3)
        m1.metric("Patrimônio Hoje", f"R$ {total_atual:,.2f}")
        m2.metric(f"Projeção ({tempo_anos} anos)", f"R$ {evolucao_total[-1]:,.2f}")
        prog = (total_atual/valor_meta)*100 if valor_meta > 0 else 0
        m3.metric("Meta Alcançada", f"{prog:.1f}%")

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            fig_pizza = go.Figure(data=[go.Pie(labels=df_ativos["nome"], values=df_ativos["valor_atual"], hole=.4)])
            st.plotly_chart(fig_pizza, use_container_width=True)
        with col_g2:
            fig_linha = go.Figure()
            fig_linha.add_trace(go.Scatter(y=evolucao_total, name="Evolução", line=dict(color='#00ff00')))
            fig_linha.add_hline(y=valor_meta, line_dash="dash", line_color="red")
            st.plotly_chart(fig_linha, use_container_width=True)

elif st.session_state["authentication_status"] is False:
    st.error("Usuário ou senha incorretos")
elif st.session_state["authentication_status"] is None:
    st.warning("Por favor, insira usuário e senha")
