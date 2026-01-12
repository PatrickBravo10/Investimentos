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
passwords = ["12345"] # Você pode alterar aqui

authenticator = stauth.Authenticate(
    {"usernames": {usernames[0]: {"name": names[0], "password": passwords[0]}}},
    "cookie_invest", "key_invest", cookie_expiry_days=30
)

authenticator.login(location="main")

if st.session_state["authentication_status"]:
    
    # 1. CARREGAR DADOS DO GITHUB
    csv_data, csv_sha = get_git_file("dados.csv")
    config_data, config_sha = get_git_file("config.json")

    # Processar Investimentos
    if csv_data:
        df_ativos = pd.read_csv(StringIO(csv_data))
    else:
        df_ativos = pd.DataFrame(columns=["tipo", "nome", "valor_atual", "aporte_mensal", "juros_mensal"])

    # Processar Configurações (Meta)
    if config_data:
        conf = json.loads(config_data)
        meta_inicial = conf.get("valor_meta", 100000.0)
        tempo_inicial = conf.get("tempo_anos", 10)
    else:
        meta_inicial, tempo_inicial = 100000.0, 10

    # --- SIDEBAR ---
    with st.sidebar:
        st.header(f"Bem-vindo, {st.session_state['name']}")
        st.subheader("🎯 Sua Meta")
        valor_meta = st.number_input("Objetivo Final (R$)", min_value=1.0, value=float(meta_inicial))
        tempo_anos = st.slider("Prazo (Anos)", 1, 40, value=int(tempo_inicial))
        
        st.markdown("---")
        if st.button("💾 SALVAR TUDO NO GITHUB"):
            with st.spinner("Sincronizando..."):
                # Salvar CSV
                csv_str = df_editado.to_csv(index=False)
                res1 = save_git_file("dados.csv", csv_str, csv_sha, "Update ativos")
                
                # Salvar Config
                conf_str = json.dumps({"valor_meta": valor_meta, "tempo_anos": tempo_anos})
                res2 = save_git_file("config.json", conf_str, config_sha, "Update config")
                
                if res1.status_code in [200, 201] and res2.status_code in [200, 201]:
                    st.success("Dados protegidos no GitHub!")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("Erro na sincronização. Verifique o Token.")

        st.markdown("---")
        authenticator.logout("Sair", "sidebar")

    # --- CORPO DO APP ---
    st.title("📊 Painel de Investimentos Inteligente")

    # Editor de Ativos
    st.subheader("📝 Gerenciar Carteira")
    df_editado = st.data_editor(df_ativos, num_rows="dynamic", use_container_width=True)

    # Cálculos e Gráficos
    if not df_editado.empty:
        # Limpeza de dados
        for col in ["valor_atual", "aporte_mensal", "juros_mensal"]:
            df_editado[col] = pd.to_numeric(df_editado[col], errors='coerce').fillna(0)

        total_atual = df_editado["valor_atual"].sum()
        
        # Dashboard de Métricas
        m1, m2, m3 = st.columns(3)
        m1.metric("Patrimônio Atual", f"R$ {total_atual:,.2f}")
        
        # Cálculo de Projeção
        meses = tempo_anos * 12
        projecao = [0.0] * (meses + 1)
        for _, row in df_editado.iterrows():
            v, a, j = row["valor_atual"], row["aporte_mensal"], (row["juros_mensal"] / 100)
            val = v
            for m in range(meses + 1):
                if m > 0: val = (val * (1 + j)) + a
                projecao[m] += val

        m2.metric(f"Estimado em {tempo_anos} anos", f"R$ {projecao[-1]:,.2f}")
        progresso = (total_atual / valor_meta) * 100 if valor_meta > 0 else 0
        m3.metric("Progresso da Meta", f"{progresso:.1f}%")

        # Gráficos
        col1, col2 = st.columns(2)
        with col1:
            st.write("### Divisão por Ativo")
            fig_pie = go.Figure(data=[go.Pie(labels=df_editado["nome"], values=df_editado["valor_atual"], hole=.4)])
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            st.write("### Evolução do Patrimônio")
            fig_evol = go.Figure()
            fig_evol.add_trace(go.Scatter(y=projecao, mode='lines', line=dict(color='#00FF00', width=4), name="Crescimento"))
            fig_evol.add_hline(y=valor_meta, line_dash="dash", line_color="red", annotation_text="Sua Meta")
            st.plotly_chart(fig_evol, use_container_width=True)

elif st.session_state["authentication_status"] is False:
    st.error("Usuário ou senha incorretos")
elif st.session_state["authentication_status"] is None:
    st.warning("Por favor, faça o login para acessar seus dados.")
