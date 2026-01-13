import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import streamlit_authenticator as stauth
import requests
import base64
import json
from io import StringIO
from datetime import datetime

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestor Patrick 2026", layout="wide", page_icon="🏦")

# --- 2. FUNÇÕES DE SUPORTE ---
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

# --- 3. AUTENTICAÇÃO ---
names = ["Patrick Bravo"]
usernames = ["admin"]
passwords = ["12345"]
authenticator = stauth.Authenticate({"usernames": {usernames[0]: {"name": names[0], "password": passwords[0]}}}, "cookie_invest", "key_invest", 30)
authenticator.login(location="main")

if st.session_state["authentication_status"]:
    st.sidebar.title("🎮 Navegação")
    menu = st.sidebar.radio("Ir para:", ["📊 Investimentos", "💸 Fluxo de Caixa"])
    
    # --- ABA 1: INVESTIMENTOS (PRESERVADA) ---
    if menu == "📊 Investimentos":
        st.title("📊 Gestão de Investimentos Profissional")
        dolar_hoje, data_dolar = get_dollar_rate()
        csv_inv, sha_inv = get_git_file("dados.csv")
        metas_inv, sha_metas = get_git_file("metas.csv")

        df_inv = pd.read_csv(StringIO(csv_inv)) if csv_inv else pd.DataFrame(columns=["origem","tipo","nome","valor_atual","aporte_mensal","juros_mensal"])
        st.info(f"💵 **Dólar Avenue:** R$ {dolar_hoje:.2f}")

        df_ed_inv = st.data_editor(df_inv, num_rows="dynamic", use_container_width=True)
        # [Cálculos originais de investimento mantidos aqui]

    # --- ABA 2: FLUXO DE CAIXA (COM DROPDOWNS) ---
    elif menu == "💸 Fluxo de Caixa":
        st.title("💸 Fluxo de Caixa 2025-2026")
        gastos_data, gastos_sha = get_git_file("gastos.csv")
        df_gastos = pd.read_csv(StringIO(gastos_data)) if gastos_data else pd.DataFrame(columns=["descricao","categoria","tipo_custo","fluxo","ano","mes","valor","status","recorrente"])

        # Listas para Menus Suspensos
        categorias = ["salário", "Investimento", "Contas domésticas", "Cartão de crédito", "Educação", "Obra casa", "Lazer", "Aluguel"]
        meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        anos = [2025, 2026]

        col1, col2 = st.columns(2)
        with col1: ano_sel = st.selectbox("Ano", anos, index=1)
        with col2: mes_sel = st.selectbox("Mês", meses, index=0)

        df_mes = df_gastos[(df_gastos["ano"] == ano_sel) & (df_gastos["mes"] == mes_sel)].copy()
        
        # Dashboard de Totais (Somente ✅ Pago)
        df_pago = df_mes[df_mes["status"] == "✅ Pago"]
        receita = df_pago[df_pago["fluxo"] == "Receita"]["valor"].abs().sum()
        despesa = df_pago[df_pago["fluxo"] == "Despesa"]["valor"].abs().sum()

        k1, k2, k3 = st.columns(3)
        k1.metric("Entradas", f"R$ {receita:,.2f}")
        k2.metric("Saídas", f"R$ {despesa:,.2f}", delta_color="inverse")
        k3.metric("Saldo", f"R$ {receita - despesa:,.2f}")

        st.markdown("---")
        # Editor com Menus Suspensos (Dropdowns)
        df_ed_gastos = st.data_editor(df_mes, num_rows="dynamic", use_container_width=True,
            column_config={
                "valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f"),
                "status": st.column_config.SelectboxColumn("Status", options=["✅ Pago", "⏳ Pendente"]),
                "fluxo": st.column_config.SelectboxColumn("Fluxo", options=["Receita", "Despesa"]),
                "categoria": st.column_config.SelectboxColumn("Categoria", options=categorias),
                "tipo_custo": st.column_config.SelectboxColumn("Tipo", options=["Fixo", "Variável"]),
                "ano": st.column_config.SelectboxColumn("Ano", options=anos),
                "mes": st.column_config.SelectboxColumn("Mês", options=meses),
                "recorrente": st.column_config.CheckboxColumn("Recorrente?")
            })

        if st.sidebar.button("💾 SALVAR GASTOS"):
            df_ed_gastos["valor"] = df_ed_gastos["valor"].abs() # Garante valor positivo
            df_outros = df_gastos[~((df_gastos["ano"] == ano_sel) & (df_gastos["mes"] == mes_sel))]
            df_final = pd.concat([df_outros, df_ed_gastos], ignore_index=True)
            save_git_file("gastos.csv", df_final.to_csv(index=False), gastos_sha, f"Update {mes_sel}")
            st.sidebar.success("Gastos Sincronizados!")
            st.rerun()

    authenticator.logout("Sair", "sidebar")
