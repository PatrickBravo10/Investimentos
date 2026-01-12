import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import streamlit_authenticator as stauth
import requests
import base64
import json
from io import StringIO

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestor Financeiro PRO", layout="wide", page_icon="📈")

# Estilo CSS para melhorar a estética dos cartões
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 28px; }
    .main { background-color: #f8f9fa; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNÇÕES DE SUPORTE (DÓLAR E GITHUB) ---
@st.cache_data(ttl=3600)
def get_dollar_rate():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        url = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
        res = requests.get(url, headers=headers, timeout=5).json()
        return float(res["USDBRL"]["bid"]), res["USDBRL"]["create_date"]
    except:
        return 5.80, "Cotação Fixa (Offline)"

GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO_NAME = st.secrets["REPO_NAME"]
HEADERS_GIT = {"Authorization": f"token {GITHUB_TOKEN}"}

def get_git_file(file_path):
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{file_path}"
    res = requests.get(url, headers=HEADERS_GIT)
    if res.status_code == 200:
        content = res.json()
        decoded = base64.decodebytes(content['content'].encode()).decode()
        return decoded, content['sha']
    return None, None

def save_git_file(file_path, content_str, sha, message):
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{file_path}"
    encoded = base64.b64encode(content_str.encode()).decode()
    payload = {"message": message, "content": encoded, "sha": sha}
    return requests.put(url, headers=HEADERS_GIT, data=json.dumps(payload))

# --- 3. AUTENTICAÇÃO ---
names = ["Patrick Bravo"]
usernames = ["admin"]
passwords = ["12345"]
authenticator = stauth.Authenticate({"usernames": {usernames[0]: {"name": names[0], "password": passwords[0]}}}, "cookie_invest", "key_invest", 30)
authenticator.login(location="main")

if st.session_state["authentication_status"]:
    # Carregamento de dados
    dolar_hoje, data_dolar = get_dollar_rate()
    csv_data, csv_sha = get_git_file("dados.csv")
    metas_csv_data, metas_sha = get_git_file("metas.csv")

    if csv_data:
        df_ativos = pd.read_csv(StringIO(csv_data))
        if "origem" not in df_ativos.columns: df_ativos.insert(0, "origem", "B3")
    else:
        df_ativos = pd.DataFrame(columns=["origem", "tipo", "nome", "valor_atual", "aporte_mensal", "juros_mensal"])

    meta_inicial, tempo_inicial = 100000.0, 10
    if metas_csv_data:
        try:
            df_m = pd.read_csv(StringIO(metas_csv_data))
            meta_inicial = float(df_m["valor_meta"].iloc[0])
            tempo_inicial = int(df_m["tempo_anos"].iloc[0])
        except: pass

    # --- 4. BARRA LATERAL (CONFIGURAÇÕES) ---
    with st.sidebar:
        st.title("⚙️ Configurações")
        st.header(f"Olá, {st.session_state['name']}")
        v_meta = st.number_input("Meta de Patrimônio (R$)", value=meta_inicial, format="%.2f")
        t_anos = st.slider("Prazo de Simulação (Anos)", 1, 50, value=tempo_inicial)
        
        st.markdown("---")
        if st.button("💾 SALVAR ALTERAÇÕES", use_container_width=True):
            cols = ["origem","tipo","nome","valor_atual","aporte_mensal","juros_mensal"]
            save_git_file("dados.csv", df_editado[cols].to_csv(index=False), csv_sha, "Sync")
            save_git_file("metas.csv", pd.DataFrame([{"valor_meta": v_meta, "tempo_anos": t_anos}]).to_csv(index=False), metas_sha, "Sync")
            st.success("GitHub Sincronizado!")
            st.rerun()
        
        authenticator.logout("Sair", "sidebar")

    # --- 5. CABEÇALHO E EDITOR ---
    st.title("💹 Dashboard de Investimentos Estratégico")
    
    col_info1, col_info2 = st.columns([2, 1])
    with col_info1:
        st.info(f"💵 **Câmbio Avenue:** R$ {dolar_hoje:.2f} | **Atualização:** {data_dolar}")
    
    with st.expander("📝 Editar Minha Carteira", expanded=True):
        df_editado = st.data_editor(
            df_ativos, 
            num_rows="dynamic", 
            use_container_width=True,
            column_config={
                "valor_atual": st.column_config.NumberColumn("Valor Unidade", format="%.2f"),
                "aporte_mensal": st.column_config.NumberColumn("Aporte (R$)", format="%.2f"),
                "juros_mensal": st.column_config.NumberColumn("Juros (%)", format="%.2f%%"),
            }
        )

    # Cálculo dos valores efetivos
    df_editado["valor_efetivo"] = df_editado.apply(lambda r: float(r["valor_atual"]) * dolar_hoje if str(r.get("origem","")).lower().strip() == "avenue" else float(r["valor_atual"]), axis=1)

    if not df_editado.empty:
        # --- 6. INDICADORES (KPIs) ---
        total_atual = df_editado["valor_efetivo"].sum()
        meses = t_anos * 12
        proj_list = [0.0] * (meses + 1)
        for _, r in df_editado.iterrows():
            v, ap, ju = float(r["valor_efetivo"]), float(r.get("aporte_mensal",0)), (float(r.get("juros_mensal",0))/100)
            acum = v
            for m in range(meses+1):
                if m > 0: acum = (acum * (1 + ju)) + ap
                proj_list[m] += acum
        
        st.markdown("---")
        k1, k2, k3 = st.columns(3)
        k1.metric("Patrimônio Total", f"R$ {total_atual:,.2f}")
        k2.metric(f"Projeção ({t_anos} anos)", f"R$ {proj_list[-1]:,.2f}")
        percent_meta = (total_atual / v_meta) * 100 if v_meta > 0 else 0
        k3.metric("Progresso da Meta", f"{percent_meta:.1f}%", delta=f"R$ {v_meta - total_atual:,.2f} restantes", delta_color="inverse")

        # --- 7. RACIONAL DE CONVERSÃO ---
        with st.container():
            st.subheader("💱 Racional da Conversão Cambial")
            df_conv = df_editado.copy()
            df_conv["Cotação"] = df_conv["origem"].apply(lambda x: dolar_hoje if str(x).lower().strip()=="avenue" else 1.0)
            df_conv["Moeda"] = df_conv["origem"].apply(lambda x: "USD" if str(x).lower().strip()=="avenue" else "BRL")
            
            # Formatação profissional da tabela de racional
            st.dataframe(
                df_conv[["origem", "nome", "Moeda", "valor_atual", "Cotação", "valor_efetivo"]].rename(
                    columns={"valor_atual": "Valor Original", "valor_efetivo": "Valor em Reais"}
                ), use_container_width=True
            )

        # --- 8. ANÁLISE GRÁFICA ---
        st.markdown("---")
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.subheader("📂 Alocação por Tipo")
            df_tipo = df_editado.groupby("tipo")["valor_efetivo"].sum().reset_index()
            fig1 = go.Figure(data=[go.Pie(labels=df_tipo["tipo"], values=df_tipo["valor_efetivo"], hole=.4)])
            fig1.update_layout(margin=dict(t=30, b=0, l=0, r=0))
            st.plotly_chart(fig1, use_container_width=True)

        with col_g2:
            st.subheader("💎 Composição dos Ativos")
            fig2 = go.Figure(data=[go.Pie(labels=df_editado["nome"], values=df_editado["valor_efetivo"], hole=.4)])
            fig2.update_layout(margin=dict(t=30, b=0, l=0, r=0))
            st.plotly_chart(fig2, use_container_width=True)

        # --- 9. EVOLUÇÃO E REBALANCEAMENTO ---
        st.markdown("---")
        st.subheader("📈 Crescimento Patrimonial Estimado")
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(y=proj_list, fill='tozeroy', line=dict(color='#28a745', width=3), name="Patrimônio Estimado"))
        fig3.add_hline(y=v_meta, line_dash="dash", line_color="#dc3545", annotation_text="Meta Definida")
        fig3.update_layout(xaxis_title="Meses", yaxis_title="Reais (R$)", height=400)
        st.plotly_chart(fig3, use_container_width=True)

        st.markdown("---")
        st.subheader("⚖️ Insights para Rebalanceamento")
        df_bal = df_editado.groupby("tipo")["valor_efetivo"].sum().reset_index()
        cols_bal = st.columns(len(df_bal) if not df_bal.empty else 1)
        
        for i, row in df_bal.iterrows():
            with cols_bal[i % len(cols_bal)]:
                st.write(f"**{row['tipo']}**")
                m_t = st.number_input(f"Meta % ({row['tipo']})", 0.0, 100.0, 100.0/len(df_bal), key=f"rebal_{row['tipo']}")
                dif = ((m_t/100) * total_atual) - row['valor_efetivo']
                if dif > 0:
                    st.success(f"Aportar: R$ {dif:,.2f}")
                else:
                    st.warning(f"Excesso: R$ {abs(dif):,.2f}")

elif st.session_state["authentication_status"] is False:
    st.error("Usuário ou senha inválidos.")
