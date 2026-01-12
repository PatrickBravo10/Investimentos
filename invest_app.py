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

# --- FUNÇÃO PARA PEGAR O DÓLAR (ROBUSTA) ---
@st.cache_data(ttl=3600)
def get_dollar_rate():
    headers = {'User-Agent': 'Mozilla/5.0'}
    # Fonte 1
    try:
        url = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
        res = requests.get(url, headers=headers, timeout=5).json()
        return float(res["USDBRL"]["bid"]), res["USDBRL"]["create_date"]
    except:
        # Fonte 2
        try:
            url = "https://api.exchangerate-api.com/v4/latest/USD"
            res = requests.get(url, headers=headers, timeout=5).json()
            return float(res["rates"]["BRL"]), "Cotação via API Secundária"
        except:
            return 5.80, "Cotação Manual (Serviços Offline)"

# --- CONFIGURAÇÕES GITHUB ---
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

# --- LOGIN ---
names = ["Patrick Bravo"]
usernames = ["admin"]
passwords = ["12345"]
authenticator = stauth.Authenticate({"usernames": {usernames[0]: {"name": names[0], "password": passwords[0]}}}, "cookie_invest", "key_invest", 30)
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

    meta_inicial, tempo_inicial = 100000.0, 10
    if metas_csv_data:
        try:
            df_m = pd.read_csv(StringIO(metas_csv_data))
            meta_inicial = float(df_m["valor_meta"].iloc[0])
            tempo_inicial = int(df_m["tempo_anos"].iloc[0])
        except: pass

    # --- UI ---
    st.title("📊 Gestor Financeiro Inteligente")
    st.info(f"💵 **Dólar Atual:** R$ {dolar_hoje:.2f} | **Atualização:** {data_dolar}")

    # Tabela com Centavos e Exclusão
    st.subheader("📝 Carteira de Ativos")
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
    def calcular_v_efetivo(row):
        try:
            v = float(row["valor_atual"])
            return v * dolar_hoje if str(row.get("origem","")).lower().strip() == "avenue" else v
        except: return 0.0
    df_editado["valor_efetivo"] = df_editado.apply(calcular_v_efetivo, axis=1)

    # Sidebar
    with st.sidebar:
        v_meta = st.number_input("Sua Meta (R$)", value=meta_inicial, format="%.2f")
        t_anos = st.slider("Anos", 1, 50, value=tempo_inicial)
        if st.button("💾 SALVAR TUDO"):
            cols = ["origem","tipo","nome","valor_atual","aporte_mensal","juros_mensal"]
            save_git_file("dados.csv", df_editado[cols].to_csv(index=False), csv_sha, "Update")
            save_git_file("metas.csv", pd.DataFrame([{"valor_meta": v_meta, "tempo_anos": t_anos}]).to_csv(index=False), metas_sha, "Update")
            st.success("Sincronizado!")
            st.rerun()
        authenticator.logout("Sair", "sidebar")

    if not df_editado.empty:
        total_brl = df_editado["valor_efetivo"].sum()
        
        # KPIs
        st.markdown("---")
        k1, k2, k3 = st.columns(3)
        k1.metric("💰 Patrimônio Atual", f"R$ {total_brl:,.2f}")
        
        # Cálculo de Projeção Global
        meses = t_anos * 12
        proj_global = [0.0] * (meses + 1)
        for _, r in df_editado.iterrows():
            v, ap, ju = float(r["valor_efetivo"]), float(r.get("aporte_mensal",0)), (float(r.get("juros_mensal",0))/100)
            acum = v
            for m in range(meses+1):
                if m > 0: acum = (acum * (1 + ju)) + ap
                proj_global[m] += acum
        
        k2.metric(f"🚀 Projetado ({t_anos} anos)", f"R$ {proj_global[-1]:,.2f}")
        k3.metric("🎯 Meta", f"{(total_brl/v_meta)*100:.1f}%" if v_meta > 0 else "0%")

        # Racional da Conversão
        with st.expander("💱 Detalhes da Conversão (Avenue = USD)"):
            st.dataframe(df_editado[["origem", "nome", "valor_atual", "valor_efetivo"]].rename(columns={"valor_atual": "Valor Original", "valor_efetivo": "Valor R$"}), use_container_width=True)

        # Inteligência de Alocação
        st.header("⚖️ Insight de Rebalanceamento")
        df_aloc = df_editado.groupby("tipo")["valor_efetivo"].sum().reset_index()
        cols_aloc = st.columns(len(df_aloc) if not df_aloc.empty else 1)
        for i, row in df_aloc.iterrows():
            with cols_aloc[i % len(cols_aloc)]:
                st.write(f"**{row['tipo']}**")
                m_t = st.number_input(f"Meta %", 0.0, 100.0, 100.0/len(df_aloc), key=f"m_{row['tipo']}")
                dif = ((m_t/100) * total_brl) - row['valor_efetivo']
                st.success(f"Comprar: R$ {dif:,.2f}") if dif > 0 else st.warning(f"Excesso: R$ {abs(dif):,.2f}")

        # --- SEÇÃO INTERATIVA ---
        st.markdown("---")
        st.header("📊 Filtro por Clique")
        
        if st.button("🔄 Limpar Filtro"):
            if "selecao" in st.session_state: del st.session_state["selecao"]
            st.rerun()

        # Captura de Seleção (Novo padrão Streamlit 1.35+)
        tipo_sel = None
        # O objeto de seleção agora é retornado pela função st.plotly_chart
        g1, g2 = st.columns(2)
        
        with g1:
            st.write("### 📂 Composição por Tipo (Clique para Filtrar)")
            fig1 = go.Figure(data=[go.Pie(labels=df_aloc["tipo"], values=df_aloc["valor_efetivo"], hole=.4)])
            # Atribuímos a uma variável para capturar o evento de clique
            evento = st.plotly_chart(fig1, use_container_width=True, on_select="rerun", key="selecao")
            
            # Extração segura do rótulo clicado
            if evento and "selection" in evento and "points" in evento["selection"]:
                if len(evento["selection"]["points"]) > 0:
                    tipo_sel = evento["selection"]["points"][0]["label"]

        df_final = df_editado[df_editado["tipo"] == tipo_sel].copy() if tipo_sel else df_editado.copy()

        with g2:
            st.write(f"### 💎 Detalhes: {tipo_sel if tipo_sel else 'Carteira Total'}")
            fig2 = go.Figure(data=[go.Pie(labels=df_final["nome"], values=df_final["valor_efetivo"], hole=.4)])
            st.plotly_chart(fig2, use_container_width=True)

        # Evolução Projetada
        st.write(f"### 📈 Evolução Projetada: {tipo_sel if tipo_sel else 'Total'}")
        proj_f = [0.0] * (meses + 1)
        for _, r in df_final.iterrows():
            v_f, a_f, j_f = float(r["valor_efetivo"]), float(r.get("aporte_mensal",0)), (float(r.get("juros_mensal",0))/100)
            ac_f = v_f
            for m in range(meses+1):
                if m > 0: ac_f = (ac_f * (1 + j_f)) + a_f
                proj_f[m] += ac_f

        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(y=proj_f, fill='tozeroy', name="Evolução Patrimonial", line=dict(color='#00FF00', width=3)))
        if not tipo_sel: fig3.add_hline(y=v_meta, line_dash="dash", line_color="red", annotation_text="Meta Global")
        fig3.update_layout(showlegend=True, xaxis_title="Meses", yaxis_title="R$")
        st.plotly_chart(fig3, use_container_width=True)

elif st.session_state["authentication_status"] is False:
    st.error("Login inválido")
