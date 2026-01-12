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
st.set_page_config(page_title="Gestor Financeiro Global", layout="wide")

# --- FUNÇÃO PARA PEGAR O DÓLAR EM TEMPO REAL ---
def get_dollar_rate():
    try:
        url = "https://economia.awesomeapi.com.br/last/USD-BRL"
        res = requests.get(url).json()
        cotacao = float(res["USDBRL"]["bid"])
        data_hora = res["USDBRL"]["create_date"]
        return cotacao, data_hora
    except:
        return 5.50, "Cotação padrão (Erro API)"

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
        # --- CORREÇÃO DO ERRO AQUI: Garantir que a coluna 'origem' exista ---
        if "origem" not in df_ativos.columns:
            df_ativos.insert(0, "origem", "B3") # Adiciona na primeira posição
    else:
        df_ativos = pd.DataFrame(columns=["origem", "tipo", "nome", "valor_atual", "aporte_mensal", "juros_mensal"])

    if metas_csv_data:
        df_metas_carregado = pd.read_csv(StringIO(metas_csv_data))
        meta_inicial = df_metas_carregado["valor_meta"].iloc[0] if not df_metas_carregado.empty else 100000.0
        tempo_inicial = df_metas_carregado["tempo_anos"].iloc[0] if not df_metas_carregado.empty else 10
    else:
        meta_inicial, tempo_inicial = 100000.0, 10

    # --- CORPO PRINCIPAL ---
    st.title("📊 Gestor Financeiro Global")
    
    st.info(f"💵 **Cotação Dólar:** R$ {dolar_hoje:.2f} | **Atualização:** {data_dolar}")

    st.subheader("📝 Gerenciar Carteira")
    # Tabela editável
    df_editado = st.data_editor(df_ativos, num_rows="dynamic", use_container_width=True)

    # --- LÓGICA DE CÁLCULO ---
    for col in ["valor_atual", "aporte_mensal", "juros_mensal"]:
        df_editado[col] = pd.to_numeric(df_editado[col], errors='coerce').fillna(0)

    # Função de cálculo agora protegida contra erro de nome
    def calcular_efetivo(row):
        origem = str(row.get("origem", "B3")).strip().lower()
        if origem == "avenue":
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
                # Salvamos apenas as colunas que devem ir para o CSV permanente
                colunas_salvar = ["origem", "tipo", "nome", "valor_atual", "aporte_mensal", "juros_mensal"]
                csv_str = df_editado[colunas_salvar].to_csv(index=False)
                res1 = save_git_file("dados.csv", csv_str, csv_sha, "Update estrutural")
                
                df_metas_save = pd.DataFrame([{"valor_meta": valor_meta, "tempo_anos": tempo_anos}])
                metas_csv_str = df_metas_save.to_csv(index=False)
                res2 = save_git_file("metas.csv", metas_csv_str, metas_sha, "Update metas")
                
                if res1.status_code in [200, 201] and res2.status_code in [200, 201]:
                    st.success("Tabelas atualizadas no GitHub!")
                    st.balloons()
                    st.rerun()

        authenticator.logout("Sair", "sidebar")

    # --- FILTRAGEM ---
    df_filtrado = df_editado[df_editado["tipo"].isin(filtro_tipos)].copy() if filtro_tipos else df_editado.copy()

    # --- DASHBOARD ---
    if not df_filtrado.empty:
        total_brl = df_filtrado["valor_efetivo"].sum()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Patrimônio Total (R$)", f"R$ {total_brl:,.2f}")
        
        meses = tempo_anos * 12
        projecao = [0.0] * (meses + 1)
        for _, row in df_filtrado.iterrows():
            v_brl, a, j = row["valor_efetivo"], row["aporte_mensal"], (row["juros_mensal"] / 100)
            val = v_brl
            for m in range(meses + 1):
                if m > 0: val = (val * (1 + j)) + a
                projecao[m] += val

        m2.metric(f"Em {tempo_anos} anos", f"R$ {projecao[-1]:,.2f}")
        progresso = (total_brl / valor_meta) * 100 if valor_meta > 0 else 0
        m3.metric("Progresso Meta", f"{progresso:.1f}%")

        # Gráficos
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.write("### 📂 Por Tipo (R$)")
            df_tipo = df_filtrado.groupby("tipo")["valor_efetivo"].sum().reset_index()
            fig_tipo = go.Figure(data=[go.Pie(labels=df_tipo["tipo"], values=df_tipo["valor_efetivo"], hole=.4)])
            st.plotly_chart(fig_tipo, use_container_width=True)
        
        with col2:
            st.write("### 💎 Por Nome (R$)")
            fig_nome = go.Figure(data=[go.Pie(labels=df_filtrado["nome"], values=df_filtrado["valor_efetivo"], hole=.4)])
            st.plotly_chart(fig_nome, use_container_width=True)
            
    # Visualizador de detalhes
    with st.expander("🔍 Detalhes da Conversão Cambial"):
        st.dataframe(df_editado[["origem", "nome", "valor_atual", "valor_efetivo"]], use_container_width=True)

elif st.session_state["authentication_status"] is False:
    st.error("Usuário ou senha incorretos")
