import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import streamlit_authenticator as stauth
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestor Financeiro Patrick", layout="wide")

# LOGIN CONFIG
names = ["Usuario Teste"]
usernames = ["admin"]
passwords = ["12345"] # Corrigido: Removido o 'A' que estava sobrando aqui

authenticator = stauth.Authenticate(
    {"usernames": {usernames[0]: {"name": names[0], "password": passwords[0]}}},
    "cookie_invest", "key_invest", cookie_expiry_days=30
)

authenticator.login(location="main")

# --- APP PRINCIPAL ---
if st.session_state["authentication_status"]:
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # 1. CARREGAR DADOS COM TRATAMENTO DE ERRO
    try:
        df_ativos = conn.read(worksheet="Sheet1", ttl=0)
        df_config = conn.read(worksheet="config", ttl=0)
        
        if not df_config.empty:
            meta_inicial = float(df_config["valor_meta"].iloc[0])
            tempo_inicial = int(df_config["tempo_anos"].iloc[0])
        else:
            meta_inicial, tempo_inicial = 100000.0, 10
    except Exception:
        df_ativos = pd.DataFrame(columns=["tipo", "nome", "valor_atual", "aporte_mensal", "juros_mensal"])
        meta_inicial, tempo_inicial = 100000.0, 10

    with st.sidebar:
        st.header("🎯 Meta Principal")
        valor_meta = st.number_input("Objetivo Final (R$)", min_value=1.0, value=meta_inicial)
        tempo_anos = st.slider("Prazo (Anos)", 1, 40, value=tempo_inicial)
        
        st.markdown("---")
        if st.button("💾 Guardar Tudo (Dados e Meta)"):
            # Remove linhas vazias e garante que as colunas estão certas
            df_para_salvar = df_ativos.dropna(how='all')
            
            # Atualiza abas
            conn.update(worksheet="Sheet1", data=df_para_salvar)
            df_meta_save = pd.DataFrame([{"valor_meta": valor_meta, "tempo_anos": tempo_anos}])
            conn.update(worksheet="config", data=df_meta_save)
            
            st.success("Dados salvos no Google Sheets!")
            st.balloons()
        
        st.markdown("---")
        authenticator.logout("Sair", "sidebar")

    st.title("📊 Minha Carteira & Projeções")

    # 2. EDITOR DE TABELA
    st.subheader("📝 Seus Investimentos")
    
    colunas_obrigatorias = ["tipo", "nome", "valor_atual", "aporte_mensal", "juros_mensal"]
    for col in colunas_obrigatorias:
        if col not in df_ativos.columns:
            df_ativos[col] = 0.0 if any(x in col for x in ["valor", "juros", "aporte"]) else ""

    df_ativos = st.data_editor(df_ativos, num_rows="dynamic", use_container_width=True)

    # --- 3. CÁLCULOS DE PROJEÇÃO ---
    total_atual = 0.0
    meses = tempo_anos * 12
    evolucao_total = [0.0] * (meses + 1)

    if not df_ativos.empty:
        for col in ["valor_atual", "aporte_mensal", "juros_mensal"]:
            df_ativos[col] = pd.to_numeric(df_ativos[col], errors='coerce').fillna(0)

        total_atual = df_ativos["valor_atual"].sum()
        
        for _, row in df_ativos.iterrows():
            v, a, j = row["valor_atual"], row["aporte_mensal"], row["juros_mensal"] / 100
            val_anterior = v
            for m in range(meses + 1):
                if m == 0: val_m = v
                else: val_m = (val_anterior * (1 + j)) + a
                evolucao_total[m] += val_m
                val_anterior = val_m

    # --- 4. DASHBOARD VISUAL ---
    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    
    proj_final = evolucao_total[-1]
    progresso_pct = (total_atual / valor_meta) * 100 if valor_meta > 0 else 0

    m1.metric("Patrimônio Hoje", f"R$ {total_atual:,.2f}")
    m2.metric(f"Projeção ({tempo_anos} anos)", f"R$ {proj_final:,.2f}")
    m3.metric("Meta Alcançada", f"{progresso_pct:.1f}%")
    
    st.progress(min(progresso_pct/100, 1.0))

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.subheader("🍕 Distribuição")
        if total_atual > 0:
            fig_pizza = go.Figure(data=[go.Pie(labels=df_ativos["nome"], values=df_ativos["valor_atual"], hole=.4)])
            st.plotly_chart(fig_pizza, use_container_width=True)
    with col_g2:
        st.subheader("📈 Evolução")
        fig_linha = go.Figure()
        fig_linha.add_trace(go.Scatter(y=evolucao_total, name="Evolução", line=dict(color='#00ff00', width=3)))
        fig_linha.add_hline(y=valor_meta, line_dash="dash", line_color="red")
        st.plotly_chart(fig_linha, use_container_width=True)

elif st.session_state["authentication_status"] is False:
    st.error("Usuário ou senha incorretos")
elif st.session_state["authentication_status"] is None:
    st.warning("Por favor, insira usuário e senha")

