import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import streamlit_authenticator as stauth
import requests
import base64
import json
from io import StringIO

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestor Financeiro PRO", layout="wide")

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
    
    # 1. CARREGAR DADOS DO GITHUB
    csv_data, csv_sha = get_git_file("dados.csv")
    metas_csv_data, metas_sha = get_git_file("metas.csv")

    if csv_data:
        df_ativos = pd.read_csv(StringIO(csv_data))
    else:
        df_ativos = pd.DataFrame(columns=["tipo", "nome", "valor_atual", "aporte_mensal", "juros_mensal"])

    if metas_csv_data:
        df_metas_carregado = pd.read_csv(StringIO(metas_csv_data))
        meta_inicial = df_metas_carregado["valor_meta"].iloc[0] if not df_metas_carregado.empty else 100000.0
        tempo_inicial = df_metas_carregado["tempo_anos"].iloc[0] if not df_metas_carregado.empty else 10
    else:
        meta_inicial, tempo_inicial = 100000.0, 10

    # --- CORPO PRINCIPAL ---
    st.title("📊 Painel de Investimentos Inteligente")
    
    st.subheader("📝 Gerenciar Carteira")
    # Tabela editável (sempre mostra tudo para você salvar)
    df_editado = st.data_editor(df_ativos, num_rows="dynamic", use_container_width=True)

    # --- BARRA LATERAL (SIDEBAR) COM FILTROS ---
    with st.sidebar:
        st.header(f"Olá, {st.session_state['name']}")
        
        st.subheader("🔍 Filtrar Dashboard")
        # Filtro que lê os tipos existentes na sua tabela
        tipos_disponiveis = df_editado["tipo"].unique().tolist() if not df_editado.empty else []
        filtro_tipos = st.multiselect("Selecione os Tipos:", options=tipos_disponiveis, default=tipos_disponiveis)
        
        st.markdown("---")
        st.subheader("🎯 Sua Meta")
        valor_meta = st.number_input("Objetivo Final (R$)", min_value=1.0, value=float(meta_inicial))
        tempo_anos = st.slider("Prazo (Anos)", 1, 40, value=int(tempo_inicial))
        
        st.markdown("---")
        if st.button("💾 SALVAR TUDO NO GITHUB"):
            with st.spinner("Sincronizando..."):
                csv_str = df_editado.to_csv(index=False)
                res1 = save_git_file("dados.csv", csv_str, csv_sha, "Update ativos")
                df_metas_save = pd.DataFrame([{"valor_meta": valor_meta, "tempo_anos": tempo_anos}])
                metas_csv_str = df_metas_save.to_csv(index=False)
                res2 = save_git_file("metas.csv", metas_csv_str, metas_sha, "Update metas")
                
                if res1.status_code in [200, 201] and res2.status_code in [200, 201]:
                    st.success("Salvo com sucesso!")
                    st.balloons()
                    st.rerun()

        st.markdown("---")
        authenticator.logout("Sair", "sidebar")

    # --- LÓGICA DE FILTRAGEM PARA OS GRÁFICOS ---
    # Criamos um DataFrame filtrado que será usado apenas para a visualização
    if not df_editado.empty and filtro_tipos:
        df_filtrado = df_editado[df_editado["tipo"].isin(filtro_tipos)].copy()
    else:
        df_filtrado = df_editado.copy()

    # --- CÁLCULOS E DASHBOARD ---
    if not df_filtrado.empty:
        for col in ["valor_atual", "aporte_mensal", "juros_mensal"]:
            df_filtrado[col] = pd.to_numeric(df_filtrado[col], errors='coerce').fillna(0)

        total_atual = df_filtrado["valor_atual"].sum()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Patrimônio (Filtrado)", f"R$ {total_atual:,.2f}")
        
        # Projeção (usando apenas o que está filtrado)
        meses = tempo_anos * 12
        projecao = [0.0] * (meses + 1)
        for _, row in df_filtrado.iterrows():
            v, a, j = row["valor_atual"], row["aporte_mensal"], (row["juros_mensal"] / 100)
            val = v
            for m in range(meses + 1):
                if m > 0: val = (val * (1 + j)) + a
                projecao[m] += val

        m2.metric(f"Estimado em {tempo_anos} anos", f"R$ {projecao[-1]:,.2f}")
        progresso = (total_atual / valor_meta) * 100 if valor_meta > 0 else 0
        m3.metric("Progresso da Meta", f"{progresso:.1f}%")

        # --- GRÁFICOS ---
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("### 📂 Distribuição por Tipo")
            # Agrupa os dados por tipo para o gráfico
            df_tipo = df_filtrado.groupby("tipo")["valor_atual"].sum().reset_index()
            fig_tipo = go.Figure(data=[go.Pie(labels=df_tipo["tipo"], values=df_tipo["valor_atual"], hole=.4)])
            fig_tipo.update_layout(margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig_tipo, use_container_width=True)
        
        with col2:
            st.write("### 💎 Distribuição por Nome")
            fig_nome = go.Figure(data=[go.Pie(labels=df_filtrado["nome"], values=df_filtrado["valor_atual"], hole=.4)])
            fig_nome.update_layout(margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig_nome, use_container_width=True)
        
        # Gráfico de Evolução (Linha)
        st.write("### 📈 Evolução Estimada da Seleção")
        fig_evol = go.Figure()
        fig_evol.add_trace(go.Scatter(y=projecao, mode='lines', fill='tozeroy', line=dict(color='#00FF00', width=3)))
        fig_evol.add_hline(y=valor_meta, line_dash="dash", line_color="red", annotation_text="Sua Meta")
        st.plotly_chart(fig_evol, use_container_width=True)
    else:
        st.warning("Selecione ao menos um tipo de ativo no filtro ou adicione dados à tabela.")

elif st.session_state["authentication_status"] is False:
    st.error("Usuário ou senha incorretos")
