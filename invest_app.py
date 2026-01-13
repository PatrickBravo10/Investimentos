import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit_authenticator as stauth
import requests
import base64
import json
import random
from io import StringIO
from datetime import datetime

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestor Patrick PRO 2026", layout="wide", page_icon="🏦")

# --- 2. FUNÇÕES DE SUPORTE (DÓLAR E GITHUB) ---
@st.cache_data(ttl=3600)
def get_dollar_rate():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        url = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
        res = requests.get(url, headers=headers, timeout=5).json()
        return float(res["USDBRL"]["bid"]), res["USDBRL"]["create_date"]
    except:
        return 5.85, "Cotação Fixa"

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
    st.sidebar.title(f"👋 Olá, {st.session_state['name']}")
    menu = st.sidebar.radio("Navegação Principal", ["📊 Investimentos", "💸 Fluxo de Caixa", "📈 Dashboard & Insights"])
    
    meses_map = {"Janeiro":1, "Fevereiro":2, "Março":3, "Abril":4, "Maio":5, "Junho":6, "Julho":7, "Agosto":8, "Setembro":9, "Outubro":10, "Novembro":11, "Dezembro":12}

    # ==========================================
    # ABA 1: INVESTIMENTOS
    # ==========================================
    if menu == "📊 Investimentos":
        st.title("📊 Gestão de Patrimônio & Ativos")
        dolar_hoje, data_dolar = get_dollar_rate()
        csv_inv, sha_inv = get_git_file("dados.csv")
        metas_inv, sha_metas = get_git_file("metas.csv")
        df_inv = pd.read_csv(StringIO(csv_inv)) if csv_inv else pd.DataFrame(columns=["origem","tipo","nome","valor_atual","aporte_mensal","juros_mensal"])
        
        if metas_inv:
            try:
                df_m = pd.read_csv(StringIO(metas_inv))
                meta_ini, tempo_ini = float(df_m["valor_meta"].iloc[0]), int(df_m["tempo_anos"].iloc[0])
            except: meta_ini, tempo_ini = 100000.0, 10
        else: meta_ini, tempo_ini = 100000.0, 10

        st.info(f"💵 **Câmbio Avenue:** R$ {dolar_hoje:.2f} | **Ref:** {data_dolar}")

        with st.expander("📝 Editar Carteira", expanded=True):
            df_ed_inv = st.data_editor(df_inv, num_rows="dynamic", use_container_width=True, key="editor_inv")

        df_ed_inv["valor_efetivo"] = df_ed_inv.apply(lambda r: float(r["valor_atual"]) * dolar_hoje if str(r.get("origem","")).lower().strip() == "avenue" else float(r["valor_atual"]), axis=1)

        if not df_ed_inv.empty:
            total_inv = df_ed_inv["valor_efetivo"].sum()
            with st.sidebar:
                v_meta = st.number_input("Meta Patrimônio (R$)", value=meta_ini, format="%.2f")
                t_anos = st.slider("Prazo Projeção (Anos)", 1, 50, value=tempo_ini)

            st.markdown("---")
            k1, k2, k3 = st.columns(3)
            k1.metric("Total Carteira", f"R$ {total_inv:,.2f}")
            prog = (total_inv / v_meta) * 100 if v_meta > 0 else 0
            k3.metric("Progresso Meta", f"{prog:.1f}%", delta=f"Faltam R$ {v_meta - total_inv:,.2f}", delta_color="inverse")

            g1, g2 = st.columns(2)
            with g1:
                st.subheader("📂 Alocação")
                df_t = df_ed_inv.groupby("tipo")["valor_efetivo"].sum().reset_index()
                fig_inv_pie = px.pie(df_t, names='tipo', values='valor_efetivo', hole=.4)
                # AJUSTE: Apenas % em negrito e maior
                fig_inv_pie.update_traces(textinfo='percent+label', texttemplate='<b>%{label}</b><br><b>%{percent:.1%}</b>', textfont_size=16)
                st.plotly_chart(fig_inv_pie, use_container_width=True)
            with g2:
                st.subheader("⚖️ Rebalanceamento")
                df_bal = df_ed_inv.groupby("tipo")["valor_efetivo"].sum().reset_index()
                for i, row in df_bal.iterrows():
                    m_p = 100/len(df_bal)
                    dif = ((m_p / 100) * total_inv) - row['valor_efetivo']
                    if dif > 0: st.success(f"Aportar em {row['tipo']}: R$ {dif:,.2f}")
                    else: st.warning(f"Excesso em {row['tipo']}: R$ {abs(dif):,.2f}")

        if st.sidebar.button("💾 SALVAR INVESTIMENTOS", use_container_width=True):
            save_git_file("dados.csv", df_ed_inv[["origem","tipo","nome","valor_atual","aporte_mensal","juros_mensal"]].to_csv(index=False), sha_inv, "Sync")
            save_git_file("metas.csv", pd.DataFrame([{"valor_meta": v_meta, "tempo_anos": t_anos}]).to_csv(index=False), sha_metas, "Sync")
            st.sidebar.success("Investimentos Salvos!")

    # ==========================================
    # ABA 2: FLUXO DE CAIXA
    # ==========================================
    elif menu == "💸 Fluxo de Caixa":
        st.title("💸 Fluxo de Caixa")
        gastos_raw, gastos_sha = get_git_file("gastos.csv")
        if gastos_raw:
            try: df_gastos = pd.read_csv(StringIO(gastos_raw), on_bad_lines='skip')
            except: df_gastos = pd.DataFrame(columns=["descricao","categoria","tipo_custo","fluxo","ano","mes","valor","status","recorrente"])
        else: df_gastos = pd.DataFrame(columns=["descricao","categoria","tipo_custo","fluxo","ano","mes","valor","status","recorrente"])

        c1, c2, c3 = st.columns([1, 1, 1])
        with c1: ano_sel = st.selectbox("Ano", [2024, 2025, 2026], index=2)
        with c2: mes_sel = st.selectbox("Mês", list(meses_map.keys()), index=datetime.now().month - 1)
        
        df_mes = df_gastos[(df_gastos["ano"] == ano_sel) & (df_gastos["mes"] == mes_sel)].copy()

        def salvar_g(df_s):
            df_s["valor"] = df_s["valor"].abs()
            df_o = df_gastos[~((df_gastos["ano"] == ano_sel) & (df_gastos["mes"] == mes_sel))]
            df_f = pd.concat([df_o, df_s], ignore_index=True)
            save_git_file("gastos.csv", df_f.to_csv(index=False), gastos_sha, f"Save {mes_sel}")
            st.toast("✅ Salvo!")

        with c3:
            st.write(" ")
            st.write(" ")
            if st.button("💾 SALVAR GASTOS", key="btn_t", use_container_width=True):
                salvar_g(st.session_state.editor_caixa)
                st.rerun()

        df_p = df_mes[df_mes["status"] == "✅ Pago"]
        entrou = df_p[df_p["fluxo"] == "Receita"]["valor"].sum()
        saiu = df_p[df_p["fluxo"] == "Despesa"]["valor"].sum()
        m1, m2, m3 = st.columns(3)
        m1.metric("Recebido", f"R$ {entrou:,.2f}")
        m2.metric("Saídas Pagas", f"R$ {saiu:,.2f}", delta_color="inverse")
        m3.metric("Saldo Real", f"R$ {entrou - saiu:,.2f}")

        df_ed_caixa = st.data_editor(df_mes, num_rows="dynamic", use_container_width=True, key="editor_caixa")

        if st.button("💾 SALVAR GASTOS", key="btn_b", use_container_width=True):
            salvar_g(df_ed_caixa)
            st.rerun()

    # ==========================================
    # ABA 3: DASHBOARD & INSIGHTS (GRÁFICOS AJUSTADOS)
    # ==========================================
    elif menu == "📈 Dashboard & Insights":
        st.title("📈 Dashboard Inteligente")
        gastos_raw, _ = get_git_file("gastos.csv")
        
        if gastos_raw:
            df = pd.read_csv(StringIO(gastos_raw), on_bad_lines='skip')
            df['mes_num'] = df['mes'].map(meses_map)
            df['periodo'] = df['mes'].str[:3] + "/" + df['ano'].astype(str).str[2:]
            df = df.sort_values(['ano', 'mes_num'])

            # 1. BARRAS: RECEITA E DESPESA (COM NÚMEROS)
            st.subheader("1. Receitas vs Despesas Mensais")
            df_h = df.groupby(['periodo', 'ano', 'mes_num', 'fluxo'])['valor'].sum().reset_index().sort_values(['ano', 'mes_num'])
            fig_h = px.bar(df_h, x='periodo', y='valor', color='fluxo', barmode='group',
                          color_discrete_map={'Receita': '#00C805', 'Despesa': '#FF4B4B'},
                          text_auto='.2s')
            fig_h.update_traces(textfont_size=12, textposition='outside', cliponaxis=False)
            st.plotly_chart(fig_h, use_container_width=True)

            c_g1, c_g2 = st.columns(2)
            with c_g1:
                # 2. PIZZA: CATEGORIA (APENAS % EM NEGRITO E MAIOR)
                st.subheader("2. % de Gastos por Categoria")
                df_cat = df[df['fluxo'] == 'Despesa'].groupby('categoria')['valor'].sum().reset_index().sort_values('valor', ascending=False)
                fig_p_cat = px.pie(df_cat, names='categoria', values='valor', hole=.4)
                fig_p_cat.update_traces(
                    textinfo='percent+label', 
                    texttemplate='<b>%{label}</b><br><b>%{percent:.1%}</b>',
                    textfont_size=16
                )
                st.plotly_chart(fig_p_cat, use_container_width=True)
            with c_g2:
                # 3. BARRAS: FIXO VS VARIÁVEL (COM NÚMEROS)
                st.subheader("3. Perfil de Custos")
                df_t_c = df[df['fluxo'] == 'Despesa'].groupby('tipo_custo')['valor'].sum().reset_index()
                fig_t = px.bar(df_t_c, x='tipo_custo', y='valor', color='tipo_custo', text_auto='.3s')
                fig_t.update_traces(textfont_size=14, textposition='outside')
                st.plotly_chart(fig_t, use_container_width=True)

            # 4. LINHA: ACUMULADO (COM NÚMEROS)
            st.subheader("4. Fluxo de Caixa Acumulado")
            df_a = df.groupby(['periodo', 'ano', 'mes_num', 'fluxo'])['valor'].sum().reset_index().sort_values(['ano', 'mes_num'])
            df_a['acumulado'] = df_a.groupby('fluxo')['valor'].cumsum()
            fig_a = go.Figure()
            for f in ['Receita', 'Despesa']:
                df_f = df_a[df_a['fluxo'] == f]
                fig_a.add_trace(go.Scatter(
                    x=df_f['periodo'], y=df_f['acumulado'], name=f"Total {f}",
                    mode='lines+markers+text',
                    text=[f"R${v/1000:.1f}k" for v in df_f['acumulado']],
                    textposition="top center",
                    textfont=dict(size=12, color='black'),
                    line=dict(width=4, color='#00C805' if f=='Receita' else '#FF4B4B')
                ))
            st.plotly_chart(fig_a, use_container_width=True)

            st.markdown("---")
            st.subheader("🤖 Insights Gerenciais")
            if st.button("💡 GERAR NOVOS INSIGHTS"):
                tot_r = df[df['fluxo']=='Receita']['valor'].sum()
                tot_d = df[df['fluxo']=='Despesa']['valor'].sum()
                taxa = ((tot_r - tot_d)/tot_r * 100) if tot_r > 0 else 0
                st.info(f"✅ Sua Taxa de Poupança Histórica: **{taxa:.1f}%**")
        else:
            st.warning("Sem dados.")

    st.sidebar.markdown("---")
    authenticator.logout("Sair", "sidebar")
