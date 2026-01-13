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
    
    # Navegação entre Abas
    aba = st.sidebar.radio("Navegação Principal", ["📊 Meus Investimentos", "💸 Fluxo de Caixa"])
    
    # --- ABA 1: INVESTIMENTOS ---
    if aba == "📊 Meus Investimentos":
        st.title("📊 Gestão de Investimentos & Independência")
        dolar_hoje, data_dolar = get_dollar_rate()
        csv_data, csv_sha = get_git_file("dados.csv")
        metas_data, metas_sha = get_git_file("metas.csv")

        if csv_data:
            df_invest = pd.read_csv(StringIO(csv_data))
        else:
            df_invest = pd.DataFrame(columns=["origem","tipo","nome","valor_atual","aporte_mensal","juros_mensal"])

        # Interface de Investimentos (Resumo do que construímos)
        st.info(f"💵 **Câmbio Avenue:** R$ {dolar_hoje:.2f} | **Atualização:** {data_dolar}")
        
        with st.expander("📝 Editar Carteira", expanded=True):
            df_ed_invest = st.data_editor(df_invest, num_rows="dynamic", use_container_width=True)
        
        df_ed_invest["valor_efetivo"] = df_ed_invest.apply(lambda r: float(r["valor_atual"]) * dolar_hoje if str(r.get("origem","")).lower() == "avenue" else float(r["valor_atual"]), axis=1)
        
        # KPIs de Investimentos
        total_inv = df_ed_invest["valor_efetivo"].sum()
        k1, k2 = st.columns(2)
        k1.metric("Patrimônio Total", f"R$ {total_inv:,.2f}")
        
        # Gráficos
        st.markdown("---")
        g1, g2 = st.columns(2)
        with g1:
            df_t = df_ed_invest.groupby("tipo")["valor_efetivo"].sum().reset_index()
            st.plotly_chart(go.Figure(data=[go.Pie(labels=df_t["tipo"], values=df_t["valor_efetivo"], hole=.4)]), use_container_width=True)
        with g2:
            st.write("### ⚖️ Rebalanceamento")
            # (Lógica de rebalanceamento aqui conforme códigos anteriores)
            st.caption("Ajuste as metas de alocação para ver os insights de compra.")

        if st.sidebar.button("💾 SALVAR INVESTIMENTOS"):
            save_git_file("dados.csv", df_ed_invest[["origem","tipo","nome","valor_atual","aporte_mensal","juros_mensal"]].to_csv(index=False), csv_sha, "Update Invest")
            st.rerun()

    # --- ABA 2: CONTROLE DE GASTOS ---
    elif aba == "💸 Fluxo de Caixa":
        st.title("💸 Controle de Gastos & Receitas")
        
        gastos_data, gastos_sha = get_git_file("gastos.csv")
        df_gastos = pd.read_csv(StringIO(gastos_data)) if gastos_data else pd.DataFrame(columns=["descricao","categoria","tipo_custo","fluxo","ano","mes","valor","status","recorrente","fim_recorrencia"])

        # Seletores de Tempo
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            ano_sel = st.selectbox("Selecione o Ano", [2025, 2026], index=1)
        with col_t2:
            meses_list = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
            mes_sel = st.selectbox("Selecione o Mês", meses_list, index=datetime.now().month - 1)

        # Filtro do Mês
        df_mes = df_gastos[(df_gastos["ano"] == ano_sel) & (df_gastos["mes"] == mes_sel)].copy()
        
        # Resumo Financeiro
        # Ajuste: Tratamos despesas como positivo para soma, mas diferenciamos pelo fluxo
        entrou = df_mes[df_mes["fluxo"] == "Receita"]["valor"].sum()
        saiu = abs(df_mes[df_mes["fluxo"] == "Despesa"]["valor"].sum())
        investido = abs(df_mes[df_mes["categoria"] == "Investimento"]["valor"].sum())
        sobra = entrou - saiu

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Faturamento", f"R$ {entrou:,.2f}")
        m2.metric("Despesas Totais", f"R$ {saiu:,.2f}", delta_color="inverse")
        m3.metric("Saldo do Mês", f"R$ {sobra:,.2f}")
        m4.metric("Aporte Investido", f"R$ {investido:,.2f}")

        st.markdown("---")
        
        # Editor Profissional de Gastos
        st.subheader(f"📑 Lançamentos: {mes_sel} / {ano_sel}")
        df_editor_gastos = st.data_editor(
            df_mes,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f"),
                "status": st.column_config.SelectboxColumn("Status", options=["Pago", "Pendente"]),
                "fluxo": st.column_config.SelectboxColumn("Fluxo", options=["Receita", "Despesa"]),
                "recorrente": st.column_config.CheckboxColumn("Recorrente?"),
                "ano": st.column_config.NumberColumn(disabled=True),
                "mes": st.column_config.TextColumn(disabled=True),
                "tipo_custo": st.column_config.SelectboxColumn("Tipo", options=["Fixo", "Variável"])
            }
        )

        if st.sidebar.button("💾 SALVAR GASTOS"):
            with st.spinner("Sincronizando..."):
                # Mescla as edições com o restante do banco de dados
                df_outros = df_gastos[~((df_gastos["ano"] == ano_sel) & (df_gastos["mes"] == mes_sel))]
                df_editor_gastos["ano"] = ano_sel
                df_editor_gastos["mes"] = mes_sel
                df_final = pd.concat([df_outros, df_editor_gastos], ignore_index=True)
                
                save_git_file("gastos.csv", df_final.to_csv(index=False), gastos_sha, f"Update Gastos {mes_sel}")
                st.success("Fluxo de Caixa atualizado!")
                st.rerun()

        # Alerta de Pendências
        pendentes = df_editor_gastos[df_editor_gastos["status"] == "Pendente"]
        if not pendentes.empty:
            st.warning(f"⚠️ Atenção: Existem {len(pendentes)} lançamentos pendentes de pagamento!")

        # Análise de Gastos por Categoria
        if not df_editor_gastos.empty:
            st.markdown("---")
            st.subheader("📊 Distribuição de Custos")
            df_despesas = df_editor_gastos[df_editor_gastos["fluxo"] == "Despesa"]
            fig_gastos = go.Figure(data=[go.Pie(labels=df_despesas["categoria"], values=abs(df_despesas["valor"]), hole=.4)])
            st.plotly_chart(fig_gastos, use_container_width=True)

    # Logout no rodapé da sidebar
    st.sidebar.markdown("---")
    authenticator.logout("Sair do Sistema", "sidebar")

elif st.session_state["authentication_status"] is False:
    st.error("Login incorreto.")
