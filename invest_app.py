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

# --- FUNÇÃO PARA PEGAR O DÓLAR (DUPLA FONTE) ---
@st.cache_data(ttl=3600)
def get_dollar_rate():
    try:
        res = requests.get("https://economia.awesomeapi.com.br/json/last/USD-BRL", timeout=5).json()
        return float(res["USDBRL"]["bid"]), res["USDBRL"]["create_date"]
    except:
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
    st.info(f"💵 **Dólar Atual:** R$ {dolar_hoje:.2f} | **Data da Cotação:** {data_dolar}")

    # Tabela Principal
    st.subheader("📝 Edição da Carteira")
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
        st.header(f"Perfil: {st.session_state['name']}")
        valor_meta = st.number_input("Meta de Independência (R$)", value=meta_inicial, format="%.2f")
        tempo_anos = st.slider("Prazo Estimado (Anos)", 1, 50, value=tempo_inicial)
        
        if st.button("💾 SALVAR TUDO"):
            with st.spinner("Sincronizando..."):
                cols = ["origem", "tipo", "nome", "valor_atual", "aporte_mensal", "juros_mensal"]
                csv_str = df_editado[cols].to_csv(index=False)
                save_git_file("dados.csv", csv_str, csv_sha, "Update ativos")
                df_metas_save = pd.DataFrame([{"valor_meta": valor_meta, "tempo_anos": tempo_anos}])
                save_git_file("metas.csv", df_metas_save.to_csv(index=False), metas_sha, "Update metas")
                st.success("Dados Sincronizados!")
                st.rerun()
        
        st.markdown("---")
        authenticator.logout("Sair", "sidebar")

    # --- CÁLCULOS TÉCNICOS ---
    if not df_editado.empty:
        total_brl = df_editado["valor_efetivo"].sum()
        
        # Projeção de Crescimento Global
        meses = tempo_anos * 12
        projecao_global = [0.0] * (meses + 1)
        for _, row in df_editado.iterrows():
            v = float(row["valor_efetivo"])
            a = float(row["aporte_mensal"])
            j = (float(row["juros_mensal"])/100)
            acum = v
            for m in range(meses + 1):
                if m > 0: acum = (acum * (1 + j)) + a
                projecao_global[m] += acum

        # --- SEÇÃO 1: CARTÕES DE INDICADORES (KPIs) ---
        st.markdown("---")
        k1, k2, k3 = st.columns(3)
        k1.metric("💰 Patrimônio Atual", f"R$ {total_brl:,.2f}")
        k2.metric(f"🚀 Projetado ({tempo_anos} anos)", f"R$ {projecao_global[-1]:,.2f}")
        percent_meta = (total_brl / valor_meta) * 100 if valor_meta > 0 else 0
        k3.metric("🎯 Meta Atingida", f"{percent_meta:.1f}%", delta=f"{valor_meta - total_brl:,.2f} faltantes", delta_color="inverse")

        # --- SEÇÃO 2: RACIONAL DA CONVERSÃO ---
        with st.expander("💱 Racional da Conversão Cambial (Clique para ver detalhes)"):
            df_conv = df_editado.copy()
            df_conv["Moeda"] = df_conv["origem"].apply(lambda x: "USD (Dólar)" if str(x).lower()=="avenue" else "BRL (Real)")
            df_conv["Taxa Aplicada"] = df_conv["origem"].apply(lambda x: dolar_hoje if str(x).lower()=="avenue" else 1.0)
            st.dataframe(
                df_conv[["origem", "Moeda", "nome", "valor_atual", "Taxa Aplicada", "valor_efetivo"]].rename(
                    columns={"valor_atual": "Valor na Origem", "valor_efetivo": "Valor em Reais (R$)"}
                ), use_container_width=True
            )

        # --- SEÇÃO 3: ALGORITMO DE ALOCAÇÃO ---
        st.markdown("---")
        st.header("⚖️ Inteligência de Rebalanceamento")
        df_aloc = df_editado.groupby("tipo")["valor_efetivo"].sum().reset_index()
        cols_aloc = st.columns(len(df_aloc) if len(df_aloc) > 0 else 1)
        
        for i, row in df_aloc.iterrows():
            with cols_aloc[i % len(cols_aloc)]:
                st.write(f"**{row['tipo']}**")
                meta_tipo = st.number_input(f"Meta % ({row['tipo']})", 0.0, 100.0, 100.0/len(df_aloc), key=f"m_{row['tipo']}")
                v_ideal = (meta_tipo / 100) * total_brl
                dif = v_ideal - row['valor_efetivo']
                if dif > 0: st.success(f"Comprar: R$ {dif:,.2f}")
                else: st.warning(f"Excesso: R$ {abs(dif):,.2f}")

        # --- SEÇÃO 4: GRÁFICOS INTERATIVOS ---
        st.markdown("---")
        st.header("📊 Análise Gráfica Interativa")
        
        # Lógica de Filtro Interativo
        tipo_selecionado = None
        if st.button("🔄 Limpar Filtro Gráfico"):
            st.session_state["grafico_tipo_selecao"] = None # Reseta a seleção
            st.rerun()

        # Verifica se houve clique no gráfico de tipo
        if "grafico_tipo_selecao" in st.session_state and st.session_state["grafico_tipo_selecao"]:
             try:
                 # Tenta extrair o tipo selecionado (pode variar dependendo da versão do Streamlit/Plotly)
                 dados_selecao = st.session_state["grafico_tipo_selecao"]
                 if 'points' in dados_selecao:
                     tipo_selecionado = dados_selecao['points'][0]['label']
                 elif 'selection' in dados_selecao and 'points' in dados_selecao['selection']:
                      tipo_selecionado = dados_selecao['selection']['points'][0]['label']
             except:
                 pass # Se der erro na extração, considera sem filtro

        # Cria o DataFrame filtrado com base na seleção
        if tipo_selecionado:
            st.info(f"Filtrando por: **{tipo_selecionado}**")
            df_interativo = df_editado[df_editado["tipo"] == tipo_selecionado].copy()
        else:
            df_interativo = df_editado.copy()

        g1, g2 = st.columns(2)
        with g1:
            st.write("### 📂 Composição por Tipo (Clique para Filtrar)")
            # O gráfico principal que gera o evento de clique
            fig_p1 = go.Figure(data=[go.Pie(labels=df_aloc["tipo"], values=df_aloc["valor_efetivo"], hole=.4)])
            fig_p1.update_layout(clickmode='event+select')
            # Importante: on_select="rerun" faz a página recarregar ao clicar
            st.plotly_chart(fig_p1, use_container_width=True, on_select="rerun", key="grafico_tipo_selecao")
            
        with g2:
            titulo_grafico = f"### 💎 Composição: {tipo_selecionado if tipo_selecionado else 'Geral'}"
            st.write(titulo_grafico)
            # Este gráfico reage ao filtro do primeiro
            fig_p2 = go.Figure(data=[go.Pie(labels=df_interativo["nome"], values=df_interativo["valor_efetivo"], hole=.4)])
            st.plotly_chart(fig_p2, use_container_width=True)

        # Cálculo da Projeção Interativa (Baseada no filtro)
        projecao_interativa = [0.0] * (meses + 1)
        for _, row in df_interativo.iterrows():
            v = float(row["valor_efetivo"])
            a = float(row["aporte_mensal"])
            j = (float(row["juros_mensal"])/100)
            acum = v
            for m in range(meses + 1):
                if m > 0: acum = (acum * (1 + j)) + a
                projecao_interativa[m] += acum

        st.write(f"### 📈 Evolução Estimada: {tipo_selecionado if tipo_selecionado else 'Carteira Global'}")
        fig_evol = go.Figure()
        fig_evol.add_trace(go.Scatter(y=projecao_interativa, name="Patrimônio Filtrado", fill='tozeroy', line=dict(color='#00FF00', width=3)))
        # Mostra a meta apenas se estiver vendo a carteira global
        if not tipo_selecionado:
            fig_evol.add_hline(y=valor_meta, line_dash="dash", line_color="red", annotation_text="Meta Global")
        fig_evol.update_layout(showlegend=True, xaxis_title="Meses", yaxis_title="R$")
        st.plotly_chart(fig_evol, use_container_width=True)

elif st.session_state["authentication_status"] is False:
    st.error("Login inválido")
