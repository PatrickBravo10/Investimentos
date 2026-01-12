import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import streamlit_authenticator as stauth
import requests
import base64
import json
from io import StringIO
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestor Financeiro Multimoedas", layout="wide")

# --- FUNÇÃO PARA PEGAR O DÓLAR EM TEMPO REAL ---
def get_dollar_rate():
    try:
        url = "https://economia.awesomeapi.com.br/last/USD-BRL"
        res = requests.get(url).json()
        cotacao = float(res["USDBRL"]["bid"])
        data_hora = res["USDBRL"]["create_date"]
        return cotacao, data_hora
    except:
        return 5.0, "Erro ao buscar cotação"

# --- CONFIGURAÇÕES DO GITHUB (SECRETS) ---
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO_NAME = st.secrets["REPO_NAME"]
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}

# --- FUNÇÕES DE PERSISTÊNCIA ---
def get_git_file(file_path):
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{file_path}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code == 200:
        content = res.json()
        decoded = base64.b64decode(content['content']).decode('utf-8')
        return decoded, content['sha']
    return None, None

def save_git_file(file_path, content_str, sha, message):
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{file_path}"
    encoded = base64.b64encode(content_str.encode('utf-8')).decode('utf-8')
    payload = {"message": message, "content": encoded, "sha": sha}
    return requests.put(url, headers=HEADERS, data=json.dumps(payload))

# --- SISTEMA DE LOGIN ---
names = ["Patrick Bravo"]
usernames = ["admin"]
passwords = ["12345"]

authenticator = stauth.Authenticate(
    {"usernames": {usernames[0]: {"name": names[0], "password": passwords[0]}}},
    "cookie_invest", "key_invest", cookie_expiry_days=30
)

authenticator.login(location="main")

if st.session_state["authentication_status"]:
    
    # 1. BUSCAR COTAÇÃO DO DÓLAR
    dolar_hoje, data_dolar = get_dollar_rate()

    # 2. CARREGAR DADOS DO GITHUB
    csv_data, csv_sha = get_git_file("dados.csv")
    metas_csv_data, metas_sha = get_git_file("metas.csv")

    if csv_data:
        df_ativos = pd.read_csv(StringIO(csv_data))
    else:
        # Adicionado coluna 'origem'
        df_ativos = pd.DataFrame(columns=["origem", "tipo", "nome", "valor_atual", "aporte_mensal", "juros_mensal"])

    if metas_csv_data:
        df_metas_carregado = pd.read_csv(StringIO(metas_csv_data))
        meta_inicial = df_metas_carregado["valor_meta"].iloc[0] if not df_metas_carregado.empty else 100000.0
        tempo_inicial = df_metas_carregado["tempo_anos"].iloc[0] if not df_metas_carregado.empty else 10
    else:
        meta_inicial, tempo_inicial = 100000.0, 10

    # --- CORPO PRINCIPAL ---
    st.title("📊 Gestor Financeiro Global")
    
    # Exibir cotação do dólar no topo
    st.info(f"💵 **Cotação Dólar:** R$ {dolar_hoje:.2f} | **Última atualização:** {data_dolar}")

    st.subheader("📝 Gerenciar Carteira")
    # Tabela editável
    df_editado = st.data_editor(df_ativos, num_rows="dynamic", use_container_width=True)

    # --- LÓGICA DE CÁLCULO DO VALOR EFETIVO ---
    # Convertemos colunas para números para evitar erros
    for col in ["valor_atual", "aporte_mensal", "juros_mensal"]:
        df_editado[col] = pd.to_numeric(df_editado[col], errors='coerce').fillna(0)

    # Criamos a coluna de Valor Efetivo baseada na Origem
    def calcular_efetivo(row):
        if str(row["origem"]).strip().lower() == "avenue":
            return row["valor_atual"] * dolar_hoje
        return row["valor_atual"]

    df_editado["valor_efetivo"] = df_editado.apply(calcular_efetivo, axis=1)

    # --- BARRA LATERAL (SIDEBAR) ---
    with st.sidebar:
        st.header(f"Olá, {st.session_state['name']}")
        
        st.subheader("🔍 Filtrar Dashboard")
        tipos_disponiveis = df_editado["tipo"].unique().tolist() if not df_editado.empty else []
        filtro_tipos = st.multiselect("Selecione os Tipos:", options=tipos_disponiveis, default=tipos_disponiveis)
        
        st.markdown("---")
        st.subheader("🎯 Sua Meta")
        valor_meta = st.number_input("Objetivo Final (R$)", min_value=1.0, value=float(meta_inicial))
        tempo_anos = st.slider("Prazo (Anos)", 1, 40, value=int(tempo_inicial))
        
        st.markdown("---")
        if st.button("💾 SALVAR TUDO NO GITHUB"):
            with st.spinner("Sincronizando..."):
                # Salvamos apenas as colunas originais (sem a calculada valor_efetivo)
                colunas_salvar = ["origem", "tipo", "nome", "valor_atual", "aporte_mensal", "juros_mensal"]
                csv_str = df_editado[colunas_salvar].to_csv(index=False)
                res1 = save_git_file("dados.csv", csv_str, csv_sha, "Update ativos e origem")
                
                df_metas_save = pd.DataFrame([{"valor_meta": valor_meta, "tempo_anos": tempo_anos}])
                metas_csv_str = df_metas_save.to_csv(index=False)
                res2 = save_git_file("metas.csv", metas_csv_str, metas_sha, "Update metas")
                
                if res1.status_code in [200, 201] and res2.status_code in [200, 201]:
                    st.success("Salvo com sucesso!")
                    st.balloons()
                    st.rerun()

        authenticator.logout("Sair", "sidebar")

    # --- FILTRAGEM PARA GRÁFICOS ---
    df_filtrado = df_editado[df_editado["tipo"].isin(filtro_tipos)].copy() if filtro_tipos else df_editado.copy()

    # --- DASHBOARD COM VALOR EFETIVO ---
    if not df_filtrado.empty:
        # ATENÇÃO: Agora usamos 'valor_efetivo' em vez de 'valor_atual'
        total_atual_brl = df_filtrado["valor_efetivo"].sum()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Patrimônio Total (R$)", f"R$ {total_atual_brl:,.2f}")
        
        # Projeção
        meses = tempo_anos * 12
        projecao = [0.0] * (meses + 1)
        for _, row in df_filtrado.iterrows():
            v_brl, a, j = row["valor_efetivo"], row["aporte_mensal"], (row["juros_mensal"] / 100)
            val = v_brl
            for m in range(meses + 1):
                if m > 0: val = (val * (1 + j)) + a
                projecao[m] += val

        m2.metric(f"Estimado em {tempo_anos} anos", f"R$ {projecao[-1]:,.2f}")
        progresso = (total_atual_brl / valor_meta) * 100 if valor_meta > 0 else 0
        m3.metric("Progresso da Meta", f"{progresso:.1f}%")

        # Gráficos
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.write("### 📂 Distribuição por Tipo (R$)")
            df_tipo = df_filtrado.groupby("tipo")["valor_efetivo"].sum().reset_index()
            fig_tipo = go.Figure(data=[go.Pie(labels=df_tipo["tipo"], values=df_tipo["valor_efetivo"], hole=.4)])
            st.plotly_chart(fig_tipo, use_container_width=True)
        
        with col2:
            st.write("### 💎 Distribuição por Nome (R$)")
            fig_nome = go.Figure(data=[go.Pie(labels=df_filtrado["nome"], values=df_filtrado["valor_efetivo"], hole=.4)])
            st.plotly_chart(fig_nome, use_container_width=True)
        
        st.write("### 📈 Evolução Estimada (Em Reais)")
        fig_evol = go.Figure()
        fig_evol.add_trace(go.Scatter(y=projecao, mode='lines', fill='tozeroy', line=dict(color='#00FF00', width=3)))
        fig_evol.add_hline(y=valor_meta, line_dash="dash", line_color="red", annotation_text="Meta")
        st.plotly_chart(fig_evol, use_container_width=True)

    # Mostrar a tabela com o cálculo pra conferência
    with st.expander("🔍 Visualizar Tabela de Conversão (Valores em R$)"):
        st.dataframe(df_editado[["origem", "nome", "valor_atual", "valor_efetivo"]], use_container_width=True)

elif st.session_state["authentication_status"] is False:
    st.error("Usuário ou senha incorretos")
