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

# --- FUNÇÃO PARA PEGAR O DÓLAR (ESTÁVEL) ---
@st.cache_data(ttl=3600)
def get_dollar_rate():
    try:
        url = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
        response = requests.get(url, timeout=5)
        data = response.json()
        cotacao = float(data["USDBRL"]["bid"])
        atualizacao = data["USDBRL"]["create_date"]
        return cotacao, atualizacao
    except:
        return 5.50, "Cotação Fixa (Erro de Conexão)"

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
    st.title("📊 Gestor Financeiro PRO")
    st.info(f"💵 **Dólar:** R$ {dolar_hoje:.2f} | **Atualizado em:** {data_dolar}")

    st.subheader("📝 Carteira de Ativos")
    
    # Editor com suporte a exclusão e decimais
    df_editado = st.data_editor(
        df_ativos,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "valor_atual": st.column_config.NumberColumn("Valor (Unidade)", format="%.2f"),
            "aporte_mensal": st.column_config.NumberColumn("Aporte (R$)", format="%.2f"),
            "juros_mensal": st.column_config.NumberColumn("Juros (%)", format="%.2f%%"),
        }
    )

    # Cálculo do Valor Efetivo
    def calcular_efetivo(row):
        try:
            val = float(row["valor_atual"])
            if str(row.get("origem", "")).strip().lower() == "avenue":
                return val * dolar_hoje
            return val
        except: return 0.0

    df_editado["valor_efetivo"] = df_editado.apply(calcular_efetivo, axis=1)

    # --- SIDEBAR ---
    with st.sidebar:
        st.header(f"Olá, {st.session_state['name']}")
        valor_meta = st.number_input("Meta (R$)", value=meta_inicial, format="%.2f")
        tempo_anos = st.slider("Anos", 1, 50, value=tempo_inicial)
        
        if st.button("💾 SALVAR NO GITHUB"):
            with st.spinner("Salvando..."):
                cols = ["origem", "tipo", "nome", "valor_atual", "aporte_mensal", "juros_mensal"]
                csv_str = df_editado[cols].to_csv(index=False)
                res1 = save_git_file("dados.csv", csv_str, csv_sha, "Update ativos")
                
                df_metas_save = pd.DataFrame([{"valor_meta": valor_meta, "tempo_anos": tempo_anos}])
                res2 = save_git_file("metas.csv", df_metas_save.to_csv(index=False), metas_sha, "Update metas")
                
                if res1.status_code in [200, 201]:
                    st.success("Salvo!")
                    st.rerun()

        authenticator.logout("Sair", "sidebar")

    # --- DASHBOARD ---
    if not df_editado.empty:
        total_brl = df_editado["valor_efetivo"].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Patrimônio Atual", f"R$ {total_brl:,.2f}")
        
        # Projeção
        meses = tempo_anos * 12
        projecao = [0.0] * (meses + 1)
        for _, row in df_editado.iterrows():
            v = float(row["valor_efetivo"])
            a = float(row["aporte_mensal"])
            j = (float(row["juros_mensal"]) / 100)
            acum = v
            for m in range(meses + 1):
                if m > 0: acum = (acum * (1 + j)) + a
                projecao[m] += acum

        c2.metric(f"Em {tempo_anos} anos", f"R$ {projecao[-1]:,.2f}")
        c3.metric("Meta", f"{(total_brl/valor_meta)*100:.1f}%")

        # Gráficos de Pizza
        st.markdown("---")
        g1, g2 = st.columns(2)
        with g1:
            st.write("### 📂 Por Categoria")
            df_tipo = df_editado.groupby("tipo")["valor_efetivo"].sum().reset_index()
            fig_tipo = go.Figure(data=[go.Pie(labels=df_tipo["tipo"], values=df_tipo["valor_efetivo"], hole=.4)])
            st.plotly_chart(fig_tipo, use_container_width=True)
        with g2:
            st.write("### 💎 Por Ativo")
            fig_nome = go.Figure(data=[go.Pie(labels=df_editado["nome"], values=df_editado["valor_efetivo"], hole=.4)])
            st.plotly_chart(fig_nome, use_container_width=True)

        # Gráfico de Evolução (Linha)
        st.write("### 📈 Simulação de Crescimento Patrimonial")
        fig_evol = go.Figure()
        fig_evol.add_trace(go.Scatter(y=projecao, mode='lines', fill='tozeroy', line=dict(color='#00FF00', width=3)))
        fig_evol.add_hline(y=valor_meta, line_dash="dash", line_color="red", annotation_text="Meta")
        st.plotly_chart(fig_evol, use_container_width=True)

        # TABELA DE CONVERSÃO (O que você pediu para ver as conversões)
        st.write("### 💱 Detalhes da Conversão (Avenue = USD -> BRL)")
        df_conv = df_editado.copy()
        df_conv["Cotação Aplicada"] = df_conv["origem"].apply(lambda x: dolar_hoje if str(x).lower()=="avenue" else 1.0)
        st.dataframe(
            df_conv[["origem", "nome", "valor_atual", "Cotação Aplicada", "valor_efetivo"]].rename(
                columns={"valor_atual": "Valor Original", "valor_efetivo": "Valor em R$"}
            ), 
            use_container_width=True
        )

elif st.session_state["authentication_status"] is False:
    st.error("Login incorreto")
