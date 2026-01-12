import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import streamlit_authenticator as stauth
import requests
import base64
import json
from io import StringIO

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestor Financeiro PRO", layout="wide", page_icon="🏦")

# --- 2. FUNÇÕES DE SUPORTE ---
@st.cache_data(ttl=3600)
def get_dollar_rate():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        url = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
        res = requests.get(url, headers=headers, timeout=5).json()
        return float(res["USDBRL"]["bid"]), res["USDBRL"]["create_date"]
    except:
        return 5.80, "Cotação Fixa (Offline)"

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
        try:
            df_m = pd.read_csv(StringIO(metas_csv_data))
            meta_inicial = float(df_m["valor_meta"].iloc[0])
            tempo_inicial = int(df_m["tempo_anos"].iloc[0])
        except: pass

    # --- 4. BARRA LATERAL ---
    with st.sidebar:
        st.title("⚙️ Painel de Controle")
        v_meta = st.number_input("Meta de Patrimônio (R$)", value=meta_inicial, format="%.2f")
        t_anos = st.slider("Prazo de Simulação (Anos)", 1, 50, value=tempo_inicial)
        if st.button("💾 SALVAR TUDO NO GITHUB", use_container_width=True):
            cols = ["origem","tipo","nome","valor_atual","aporte_mensal","juros_mensal"]
            save_git_file("dados.csv", df_editado[cols].to_csv(index=False), csv_sha, "Sync")
            save_git_file("metas.csv", pd.DataFrame([{"valor_meta": v_meta, "tempo_anos": t_anos}]).to_csv(index=False), metas_sha, "Sync")
            st.success("Dados salvos com sucesso!")
            st.rerun()
        authenticator.logout("Sair", "sidebar")

    # --- 5. EDITOR E CÁLCULOS ---
    st.title("💹 Gestor de Investimentos Profissional")
    st.info(f"💵 **Dólar Avenue:** R$ {dolar_hoje:.2f} | **Atualização:** {data_dolar}")

    with st.expander("📝 Gerenciar Minha Carteira", expanded=True):
        df_editado = st.data_editor(
            df_ativos, 
            num_rows="dynamic", 
            use_container_width=True,
            column_config={
                "valor_atual": st.column_config.NumberColumn("Valor Original", format="%.2f"),
                "aporte_mensal": st.column_config.NumberColumn("Aporte (R$)", format="%.2f"),
                "juros_mensal": st.column_config.NumberColumn("Juros (%)", format="%.2f%%"),
            }
        )

    # Cálculo da conversão
    df_editado["valor_efetivo"] = df_editado.apply(lambda r: float(r["valor_atual"]) * dolar_hoje if str(r.get("origem","")).lower().strip() == "avenue" else float(r["valor_atual"]), axis=1)

    if not df_editado.empty:
        # --- 6. INDICADORES (KPIs) ---
        total_atual = df_editado["valor_efetivo"].sum()
        meses = t_anos * 12
        proj_list = [0.0] * (meses + 1)
        for _, r in df_editado.iterrows():
            v, ap, ju = float(r["valor_efetivo"]), float(r.get("aporte_mensal",0)), (float(r.get("juros_mensal",0))/100)
            acum = v
            for m in range(meses+1):
                if m > 0: acum = (acum * (1 + ju)) + ap
                proj_list[m] += acum

        st.markdown("---")
        k1, k2, k3 = st.columns(3)
        k1.metric("Patrimônio Hoje", f"R$ {total_atual:,.2f}")
        k2.metric(f"Simulação ({t_anos} anos)", f"R$ {proj_list[-1]:,.2f}")
        progresso = (total_atual / v_meta) * 100 if v_meta > 0 else 0
        k3.metric("Atingimento da Meta", f"{progresso:.1f}%", delta=f"Faltam R$ {v_meta - total_atual:,.2f}", delta_color="inverse")

        # --- 7. RACIONAL DE CONVERSÃO (RETRÁTIL) ---
        with st.expander("💱 Racional da Conversão Cambial", expanded=False):
            st.markdown("Detalhamento de como os valores da **Avenue** são convertidos:")
            df_rational = df_editado.copy()
            df_rational["Cotação"] = df_rational["origem"].apply(lambda x: dolar_hoje if str(x).lower().strip()=="avenue" else 1.0)
            df_rational["Moeda"] = df_rational["origem"].apply(lambda x: "USD" if str(x).lower().strip()=="avenue" else "BRL")
            st.dataframe(
                df_rational[["origem", "nome", "Moeda", "valor_atual", "Cotação", "valor_efetivo"]].rename(
                    columns={"valor_atual": "Valor Original", "valor_efetivo": "Valor em Reais (R$)"}
                ), use_container_width=True
            )

        # --- 8. ANÁLISE GRÁFICA ---
        st.markdown("---")
        c_g1, c_g2 = st.columns(2)
        with c_g1:
            st.subheader("📂 Alocação por Tipo")
            df_t = df_editado.groupby("tipo")["valor_efetivo"].sum().reset_index()
            st.plotly_chart(go.Figure(data=[go.Pie(labels=df_t["tipo"], values=df_t["valor_efetivo"], hole=.4)]), use_container_width=True)
        with c_g2:
            st.subheader("💎 Composição por Ativo")
            st.plotly_chart(go.Figure(data=[go.Pie(labels=df_editado["nome"], values=df_editado["valor_efetivo"], hole=.4)]), use_container_width=True)

        # Evolução
        st.subheader("📈 Projeção de Crescimento")
        fig_ev = go.Figure()
        fig_ev.add_trace(go.Scatter(y=proj_list, fill='tozeroy', line=dict(color='#00C805', width=3), name="Crescimento"))
        fig_ev.add_hline(y=v_meta, line_dash="dash", line_color="#FF4B4B", annotation_text="Meta")
        st.plotly_chart(fig_ev, use_container_width=True)

        # --- 9. INSIGHTS DE REBALANCEAMENTO ---
        st.markdown("---")
        st.subheader("⚖️ Inteligência de Rebalanceamento")
        df_bal = df_editado.groupby("tipo")["valor_efetivo"].sum().reset_index()
        cols_b = st.columns(len(df_bal) if not df_bal.empty else 1)
        for i, row in df_bal.iterrows():
            with cols_b[i % len(cols_b)]:
                st.write(f"**{row['tipo']}**")
                m_perc = st.number_input(f"Meta %", 0.0, 100.0, 100.0/len(df_bal), key=f"r_{row['tipo']}")
                v_ideal = (m_perc / 100) * total_atual
                dif = v_ideal - row['valor_efetivo']
                if dif > 0: st.success(f"Aportar: R$ {dif:,.2f}")
                else: st.warning(f"Excesso: R$ {abs(dif):,.2f}")

elif st.session_state["authentication_status"] is False:
    st.error("Login incorreto.")
