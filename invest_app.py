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

# --- VERIFICAÇÃO DE VERSÃO (Para debug) ---
st.sidebar.caption(f"Versão do Streamlit: {st.__version__}")

# --- FUNÇÃO DÓLAR ---
@st.cache_data(ttl=3600)
def get_dollar_rate():
    try:
        res = requests.get("https://economia.awesomeapi.com.br/json/last/USD-BRL", timeout=5).json()
        return float(res["USDBRL"]["bid"]), res["USDBRL"]["create_date"]
    except:
        return 5.50, "Cotação Manual"

# --- GITHUB CONFIG ---
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO_NAME = st.secrets["REPO_NAME"]
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}

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

# --- LOGIN ---
names = ["Patrick Bravo"]
usernames = ["admin"]
passwords = ["12345"]
authenticator = stauth.Authenticate({"usernames": {usernames[0]: {"name": names[0], "password": passwords[0]}}}, "cookie_invest", "key_invest", 30)
authenticator.login(location="main")

if st.session_state["authentication_status"]:
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
        df_m = pd.read_csv(StringIO(metas_csv_data))
        if not df_m.empty:
            meta_inicial, tempo_inicial = float(df_m["valor_meta"].iloc[0]), int(df_m["tempo_anos"].iloc[0])

    # --- UI ---
    st.title("📊 Gestor Financeiro Inteligente")
    st.info(f"💵 **Dólar:** R$ {dolar_hoje:.2f} | **Atualização:** {data_dolar}")

    # Editor de Dados
    df_editado = st.data_editor(df_ativos, num_rows="dynamic", use_container_width=True)
    
    # Conversão de Valor
    def conv(row):
        try:
            v = float(row["valor_atual"])
            return v * dolar_hoje if str(row.get("origem","")).lower() == "avenue" else v
        except: return 0.0
    df_editado["valor_efetivo"] = df_editado.apply(conv, axis=1)

    # Sidebar
    with st.sidebar:
        v_meta = st.number_input("Meta (R$)", value=meta_inicial)
        t_anos = st.slider("Anos", 1, 50, value=tempo_inicial)
        if st.button("💾 SALVAR TUDO"):
            csv_str = df_editado[["origem","tipo","nome","valor_atual","aporte_mensal","juros_mensal"]].to_csv(index=False)
            save_git_file("dados.csv", csv_str, csv_sha, "Update")
            save_git_file("metas.csv", pd.DataFrame([{"valor_meta": v_meta, "tempo_anos": t_anos}]).to_csv(index=False), metas_sha, "Update")
            st.rerun()
        authenticator.logout("Sair", "sidebar")

    # --- DASHBOARD INTERATIVO ---
    if not df_editado.empty:
        total_brl = df_editado["valor_efetivo"].sum()
        
        # KPIs
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 Total Hoje", f"R$ {total_brl:,.2f}")
        percent = (total_brl/v_meta)*100 if v_meta > 0 else 0
        c3.metric("🎯 Meta", f"{percent:.1f}%")

        # --- LÓGICA DE FILTRO POR CLIQUE ---
        st.markdown("---")
        st.header("📊 Análise por Tipo (Clique no gráfico para filtrar)")

        # Variável para armazenar o tipo selecionado
        tipo_selecionado = None

        # Verificação robusta da seleção no st.session_state
        if "donut_tipo" in st.session_state:
            selecao = st.session_state["donut_tipo"]
            # Estrutura do Plotly Selection no Streamlit 1.35+
            if selecao and "selection" in selecao and "points" in selecao["selection"]:
                points = selecao["selection"]["points"]
                if len(points) > 0:
                    tipo_selecionado = points[0]["label"]

        if tipo_selecionado:
            col_bt1, col_bt2 = st.columns([1, 5])
            with col_bt1:
                if st.button("🔄 Limpar Filtro"):
                    # Reseta manualmente a seleção
                    del st.session_state["donut_tipo"]
                    st.rerun()
            st.info(f"Mostrando detalhes de: **{tipo_selecionado}**")
            df_plot = df_editado[df_editado["tipo"] == tipo_selecionado].copy()
        else:
            df_plot = df_editado.copy()

        # Gráficos
        g1, g2 = st.columns(2)
        with g1:
            df_resumo = df_editado.groupby("tipo")["valor_efetivo"].sum().reset_index()
            fig1 = go.Figure(data=[go.Pie(labels=df_resumo["tipo"], values=df_resumo["valor_efetivo"], hole=.4)])
            # O parâmetro on_select="rerun" e a key são obrigatórios
            st.plotly_chart(fig1, use_container_width=True, on_select="rerun", key="donut_tipo")

        with g2:
            fig2 = go.Figure(data=[go.Pie(labels=df_plot["nome"], values=df_plot["valor_efetivo"], hole=.4)])
            st.plotly_chart(fig2, use_container_width=True)

        # Projeção
        st.write("### 📈 Evolução Estimada")
        meses = t_anos * 12
        proj = [0.0] * (meses + 1)
        for _, r in df_plot.iterrows():
            val, ap, ju = float(r["valor_efetivo"]), float(r["aporte_mensal"]), (float(r["juros_mensal"])/100)
            acum = val
            for m in range(meses+1):
                if m > 0: acum = (acum * (1 + ju)) + ap
                proj[m] += acum
        
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(y=proj, fill='tozeroy', line=dict(color='#00FF00'), name="Patrimônio"))
        st.plotly_chart(fig3, use_container_width=True)

        # Racional
        with st.expander("🔍 Ver Tabela de Conversão"):
            st.dataframe(df_editado[["origem","nome","valor_atual","valor_efetivo"]])

elif st.session_state["authentication_status"] is False:
    st.error("Login incorreto")
