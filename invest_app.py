import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import streamlit_authenticator as stauth
import requests
import base64
import json
from io import StringIO

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestor Financeiro Inteligente", layout="wide")

# --- FUNÇÃO PARA PEGAR O DÓLAR (DUPLA FONTE) ---
@st.cache_data(ttl=3600)
def get_dollar_rate():
    # Fonte 1: AwesomeAPI
    try:
        res = requests.get("https://economia.awesomeapi.com.br/json/last/USD-BRL", timeout=5).json()
        return float(res["USDBRL"]["bid"]), res["USDBRL"]["create_date"]
    except:
        # Fonte 2: Alternativa (exchangerate-api)
        try:
            res = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5).json()
            return float(res["rates"]["BRL"]), "Cotação via API Secundária"
        except:
            return 5.50, "Cotação Manual (Serviço Indisponível)"

# --- CONFIGURAÇÕES GITHUB ---
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

authenticator = stauth.Authenticate(
    {"usernames": {usernames[0]: {"name": names[0], "password": passwords[0]}}},
    "cookie_invest", "key_invest", cookie_expiry_days=30
)

authenticator.login(location="main")

if st.session_state["authentication_status"]:
    dolar_hoje, data_dolar = get_dollar_rate()

    # Carregar Dados
    csv_data, csv_sha = get_git_file("dados.csv")
    metas_csv_data, metas_sha = get_git_file("metas.csv")

    if csv_data:
        df_ativos = pd.read_csv(StringIO(csv_data))
        if "origem" not in df_ativos.columns: df_ativos.insert(0, "origem", "B3")
    else:
        df_ativos = pd.DataFrame(columns=["origem", "tipo", "nome", "valor_atual", "aporte_mensal", "juros_mensal"])

    if metas_csv_data:
        df_metas_carregado = pd.read_csv(StringIO(metas_csv_data))
        meta_inicial = float(df_metas_carregado["valor_meta"].iloc[0]) if not df_metas_carregado.empty else 100000.0
        tempo_inicial = int(df_metas_carregado["tempo_anos"].iloc[0]) if not df_metas_carregado.empty else 10
    else:
        meta_inicial, tempo_inicial = 100000.0, 10

    # --- UI PRINCIPAL ---
    st.title("📊 Gestor Financeiro Inteligente")
    st.info(f"💵 **Dólar:** R$ {dolar_hoje:.2f} | **Atualizado em:** {data_dolar}")

    # Tabela Editável
    st.subheader("📝 Carteira de Ativos")
    df_editado = st.data_editor(df_ativos, num_rows="dynamic", use_container_width=True)

    # Cálculo do Valor Efetivo (Conversão)
    def calcular_efetivo(row):
        try:
            val = float(row["valor_atual"])
            return val * dolar_hoje if str(row.get("origem", "")).strip().lower() == "avenue" else val
        except: return 0.0

    df_editado["valor_efetivo"] = df_editado.apply(calcular_efetivo, axis=1)

    # --- SIDEBAR ---
    with st.sidebar:
        st.header(f"Olá, {st.session_state['name']}")
        valor_meta = st.number_input("Sua Meta (R$)", value=meta_inicial, format="%.2f")
        tempo_anos = st.slider("Anos", 1, 50, value=tempo_inicial)
        
        if st.button("💾 SALVAR TUDO"):
            with st.spinner("Sincronizando..."):
                cols = ["origem", "tipo", "nome", "valor_atual", "aporte_mensal", "juros_mensal"]
                csv_str = df_editado[cols].to_csv(index=False)
                save_git_file("dados.csv", csv_str, csv_sha, "Update ativos")
                df_metas_save = pd.DataFrame([{"valor_meta": valor_meta, "tempo_anos": tempo_anos}])
                save_git_file("metas.csv", df_metas_save.to_csv(index=False), metas_sha, "Update metas")
                st.success("Salvo com sucesso!")
                st.rerun()

    # --- DASHBOARD & INSIGHTS ---
    if not df_editado.empty:
        total_brl = df_editado["valor_efetivo"].sum()
        
        # --- SEÇÃO 1: INSIGHTS DE ALOCAÇÃO (ALGORITMO) ---
        st.markdown("---")
        st.header("⚖️ Inteligência de Alocação & Balanço")
        
        # Agrupar por tipo
        df_aloc = df_editado.groupby("tipo")["valor_efetivo"].sum().reset_index()
        df_aloc["% Atual"] = (df_aloc["valor_efetivo"] / total_brl) * 100
        
        cols_aloc = st.columns(len(df_aloc) if len(df_aloc) > 0 else 1)
        
        metas_alocacao = {}
        for i, row in df_aloc.iterrows():
            with cols_aloc[i % len(cols_aloc)]:
                st.write(f"**{row['tipo']}**")
                # O usuário define a meta ideal para cada tipo
                meta_tipo = st.number_input(f"Meta % ({row['tipo']})", min_value=0.0, max_value=100.0, value=100.0/len(df_aloc), key=f"meta_{row['tipo']}")
                metas_alocacao[row['tipo']] = meta_tipo
                
                # Cálculo do desvio
                valor_ideal = (meta_tipo / 100) * total_brl
                diferenca = valor_ideal - row['valor_efetivo']
                
                if diferenca > 0:
                    st.success(f"Comprar: R$ {diferenca:,.2f}")
                else:
                    st.warning(f"Excesso: R$ {abs(diferenca):,.2f}")

        # --- SEÇÃO 2: GRÁFICOS ---
        st.markdown("---")
        g1, g2 = st.columns(2)
        with g1:
            st.write("### 📂 Distribuição por Categoria")
            fig_pie = go.Figure(data=[go.Pie(labels=df_aloc["tipo"], values=df_aloc["valor_efetivo"], hole=.4)])
            st.plotly_chart(fig_pie, use_container_width=True)
        with g2:
            st.write("### 💎 Composição da Carteira")
            fig_nome = go.Figure(data=[go.Pie(labels=df_editado["nome"], values=df_editado["valor_efetivo"], hole=.4)])
            st.plotly_chart(fig_nome, use_container_width=True)

        # --- SEÇÃO 3: EVOLUÇÃO (COM LEGENDA) ---
        st.write("### 📈 Simulação de Crescimento Patrimonial")
        meses = tempo_anos * 12
        projecao = [0.0] * (meses + 1)
        for _, row in df_editado.iterrows():
            v, a, j = float(row["valor_efetivo"]), float(row["aporte_mensal"]), (float(row["juros_mensal"])/100)
            acum = v
            for m in range(meses + 1):
                if m > 0: acum = (acum * (1 + j)) + a
                projecao[m] += acum

        fig_evol = go.Figure()
        fig_evol.add_trace(go.Scatter(
            x=list(range(meses + 1)), 
            y=projecao, 
            name="Patrimônio Projetado",
            fill='tozeroy', 
            line=dict(color='#00FF00', width=3)
        ))
        fig_evol.add_hline(
            y=valor_meta, 
            line_dash="dash", 
            line_color="red", 
            annotation_text="Sua Meta de Independência",
            name="Meta"
        )
        fig_evol.update_layout(
            showlegend=True, 
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis_title="Meses",
            yaxis_title="Reais (R$)"
        )
        st.plotly_chart(fig_evol, use_container_width=True)

elif st.session_state["authentication_status"] is False:
    st.error("Login incorreto")
