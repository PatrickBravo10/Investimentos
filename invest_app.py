import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import streamlit_authenticator as stauth
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestor com Google Sheets", layout="wide")

# Login (Mantém o teu padrão)
names = ["Usuario Teste"]
usernames = ["admin"]
passwords = ["12345"]
authenticator = stauth.Authenticate(
    {"usernames": {usernames[0]: {"name": names[0], "password": passwords[0]}}},
    "cookie_invest", "key_invest", cookie_expiry_days=30
)
authenticator.login(location="main")

if st.session_state["authentication_status"]:
    # 1. LIGAÇÃO AO GOOGLE SHEETS
    # Substitui pelo URL da tua planilha no passo seguinte (Secrets)
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Carregar dados existentes
    df_atual = conn.read(ttl=0) # ttl=0 garante que lê sempre o dado mais fresco

    with st.sidebar:
        st.header("🎯 Meta Principal")
        valor_meta = st.number_input("Objetivo Final (R$)", min_value=0.0, value=100000.0)
        tempo_anos = st.slider("Prazo (Anos)", 1, 40, 10)
        authenticator.logout("Sair", "sidebar")

    st.title("📊 Minha Carteira (Google Sheets)")

    # 2. EDITOR DE TABELA
    df_editado = st.data_editor(df_atual, num_rows="dynamic", use_container_width=True)

    if st.button("💾 Guardar na Planilha"):
        conn.update(data=df_editado)
        st.success("Dados guardados diretamente no seu Google Sheets!")

    # --- CÁLCULOS (Mesma lógica anterior) ---
    total_atual = df_editado["valor_atual"].sum()
    meses = tempo_anos * 12
    evolucao_total = [0.0] * (meses + 1)
    
    for _, row in df_editado.iterrows():
        v, a, j = row["valor_atual"], row["aporte_mensal"], row["juros_mensal"] / 100
        val_anterior = v
        for m in range(meses + 1):
            if m == 0: val_m = v
            else: val_m = (val_anterior * (1 + j)) + a
            evolucao_total[m] += val_m
            val_anterior = val_m

    # --- DASHBOARD ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Património Hoje", f"R$ {total_atual:,.2f}")
    m2.metric("Projeção Final", f"R$ {evolucao_total[-1]:,.2f}")
    m3.metric("Meta Alcançada", f"{(total_atual/valor_meta)*100:.1f}%")

    # Gráfico de Pizza
    fig_pizza = go.Figure(data=[go.Pie(labels=df_editado["nome"], values=df_editado["valor_atual"], hole=.4)])
    st.plotly_chart(fig_pizza, use_container_width=True)
