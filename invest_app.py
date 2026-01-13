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
st.set_page_config(page_title="Gestor Patrick 2026", layout="wide", page_icon="🏦")

# --- FUNÇÕES DE SUPORTE ---
@st.cache_data(ttl=3600)
def get_dollar_rate():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        url = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
        res = requests.get(url, headers=headers, timeout=5).json()
        return float(res["USDBRL"]["bid"]), res["USDBRL"]["create_date"]
    except:
        return 5.85, "Cotação Fixa (Offline)"

GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO_NAME = st.secrets["REPO_NAME"]
HEADERS_GIT = {"Authorization": f"token {GITHUB_TOKEN}"}

def get_git_file(file_path):
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{file_path}"
    res = requests.get(url, headers=HEADERS_GIT)
    if res.status_code == 200:
        content = res.json()
        decoded = base64.b64decode(content['content']).decode('utf-8')
        return decoded, content['sha']
    return None, None

def save_git_file(file_path, content_str, sha, message):
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{file_path}"
    encoded = base64.b64encode(content_str.encode('utf-8')).decode('utf-8')
    payload = {"message": message, "content": encoded, "sha": sha}
    return requests.put(url, headers=HEADERS_GIT, data=json.dumps(payload))

# --- AUTENTICAÇÃO ---
names = ["Patrick Bravo"]
usernames = ["admin"]
passwords = ["12345"]
authenticator = stauth.Authenticate({"usernames": {usernames[0]: {"name": names[0], "password": passwords[0]}}}, "cookie_invest", "key_invest", 30)
authenticator.login(location="main")

if st.session_state["authentication_status"]:
    st.sidebar.title("🎮 Navegação")
    menu = st.sidebar.radio("Ir para:", ["📊 Investimentos", "💸 Fluxo de Caixa"])
    
    if menu == "📊 Investimentos":
        st.title("📊 Gestão de Investimentos")
        dolar_hoje, data_dolar = get_dollar_rate()
        csv_data, csv_sha = get_git_file("dados.csv")
        metas_csv_data, metas_sha = get_git_file("metas.csv")
        df_ativos = pd.read_csv(StringIO(csv_data)) if csv_data else pd.DataFrame(columns=["origem","tipo","nome","valor_atual","aporte_mensal","juros_mensal"])
        st.info(f"💵 **Dólar:** R$ {dolar_hoje:.2f}")
        df_ed = st.data_editor(df_ativos, use_container_width=True)
        # ... logic de investimento ...

    elif menu == "💸 Fluxo de Caixa":
        st.title("💸 Fluxo de Caixa Profissional")
        gastos_data, gastos_sha = get_git_file("gastos.csv")
        
        # CORREÇÃO DO ERRO DE LEITURA
        if gastos_data:
            try:
                df_gastos = pd.read_csv(StringIO(gastos_data), on_bad_lines='skip')
            except:
                df_gastos = pd.DataFrame(columns=["descricao","categoria","tipo_custo","fluxo","ano","mes","valor","status","recorrente"])
        else:
            df_gastos = pd.DataFrame(columns=["descricao","categoria","tipo_custo","fluxo","ano","mes","valor","status","recorrente"])

        # OPÇÕES DOS DROPDOWNS
        cats = sorted(list(set(["salário", "Investimento", "Contas domésticas", "Cartão de crédito", "Educação", "Obra casa", "Lazer", "Decoração", "Aluguel", "Saúde"] + df_gastos["categoria"].tolist())))
        meses_list = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        anos_list = [2024, 2025, 2026]

        col1, col2 = st.columns(2)
        with col1: ano_sel = st.selectbox("Ano", anos_list, index=1)
        with col2: mes_sel = st.selectbox("Mês", meses_list, index=datetime.now().month - 1)

        df_mes = df_gastos[(df_gastos["ano"] == ano_sel) & (df_gastos["mes"] == mes_sel)].copy()
        
        # Dash de Totais (Somente ✅ Pago)
        df_pago = df_mes[df_mes["status"] == "✅ Pago"]
        entrou = df_pago[df_pago["fluxo"] == "Receita"]["valor"].abs().sum()
        saiu = df_pago[df_pago["fluxo"] == "Despesa"]["valor"].abs().sum()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Recebido", f"R$ {entrou:,.2f}")
        m2.metric("Saídas", f"R$ {saiu:,.2f}", delta_color="inverse")
        m3.metric("Saldo", f"R$ {entrou - saiu:,.2f}")

        # EDITOR COM DROPDOWNS
        df_ed_gastos = st.data_editor(df_mes, num_rows="dynamic", use_container_width=True,
            column_config={
                "valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f"),
                "status": st.column_config.SelectboxColumn("Status", options=["✅ Pago", "⏳ Pendente"]),
                "fluxo": st.column_config.SelectboxColumn("Fluxo", options=["Receita", "Despesa"]),
                "categoria": st.column_config.SelectboxColumn("Categoria", options=cats),
                "tipo_custo": st.column_config.SelectboxColumn("Tipo", options=["Fixo", "Variável"]),
                "ano": st.column_config.SelectboxColumn("Ano", options=anos_list),
                "mes": st.column_config.SelectboxColumn("Mês", options=meses_list),
                "recorrente": st.column_config.CheckboxColumn("Recorrente?")
            })

        if st.sidebar.button("💾 SALVAR GASTOS"):
            df_ed_gastos["valor"] = df_ed_gastos["valor"].abs() # Garante positivo
            df_outros = df_gastos[~((df_gastos["ano"] == ano_sel) & (df_gastos["mes"] == mes_sel))]
            df_f = pd.concat([df_outros, df_ed_gastos], ignore_index=True)
            save_git_file("gastos.csv", df_f.to_csv(index=False), gastos_sha, f"Update {mes_sel}")
            st.sidebar.success("Sincronizado!")
            st.rerun()

    authenticator.logout("Sair", "sidebar")
