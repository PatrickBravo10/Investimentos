import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit_authenticator as stauth
import requests
import base64
import json
import random
import numpy as np
from io import StringIO
from datetime import datetime

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestor Patrick PRO 2026", layout="wide", page_icon="🏦")

# --- 2. FUNÇÕES DE SUPORTE (DÓLAR E GITHUB) ---
@st.cache_data(ttl=3600)
def get_dollar_rate():
    try:
        url = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
        res = requests.get(url, timeout=5).json()
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

# --- 3. MOTOR DE INSIGHTS ESTATÍSTICOS ---
def motor_insights_ai(df):
    if df.empty: return ["Sem dados para analisar."]
    insights = []
    df_d = df[df['fluxo'] == 'Despesa'].copy()
    df_r = df[df['fluxo'] == 'Receita'].copy()
    
    if not df_d.empty:
        cat_g = df_d.groupby('categoria')['valor'].sum().sort_values(ascending=False)
        perc = (cat_g.iloc[0] / cat_g.sum()) * 100
        if perc > 40: insights.append(f"🎯 **Pareto:** '{cat_g.index[0]}' consome {perc:.1f}% dos teus gastos.")
    
    if len(df_d) > 5:
        avg, std = df_d['valor'].mean(), df_d['valor'].std()
        anom = df_d[df_d['valor'] > (avg + 1.8 * std)]
        if not anom.empty: insights.append(f"🚨 **Anomalia:** '{anom.iloc[0]['descricao']}' está muito acima da tua média.")
    
    tr, td = df_r['valor'].sum(), df_d['valor'].sum()
    rate = ((tr - td) / tr * 100) if tr > 0 else 0
    insights.append(f"💰 **Taxa de Poupança:** {rate:.1f}% acumulado.")
    
    return insights

# --- 4. AUTENTICAÇÃO ---
names = ["Patrick Bravo"]
usernames = ["admin"]
passwords = ["12345"] 
authenticator = stauth.Authenticate({"usernames": {usernames[0]: {"name": names[0], "password": passwords[0]}}}, "cookie_invest", "key_invest", 30)
authenticator.login(location="main")

if st.session_state["authentication_status"]:
    st.sidebar.title(f"👋 Gestor Patrick")
    menu = st.sidebar.radio("Ir para:", ["📊 Investimentos", "💸 Fluxo de Caixa", "📈 Dashboard AI"])
    
    meses_map = {"Janeiro":1, "Fevereiro":2, "Março":3, "Abril":4, "Maio":5, "Junho":6, "Julho":7, "Agosto":8, "Setembro":9, "Outubro":10, "Novembro":11, "Dezembro":12}

    # ==========================================
    # ABA 1: INVESTIMENTOS (TUDO RESTAURADO)
    # ==========================================
    if menu == "📊 Investimentos":
        st.title("📊 Gestão de Património & Ativos")
        dolar_hoje, data_dolar = get_dollar_rate()
        
        csv_inv, sha_inv = get_git_file("dados.csv")
        metas_inv, sha_metas = get_git_file("metas.csv")
        
        df_inv = pd.read_csv(StringIO(csv_inv)) if csv_inv else pd.DataFrame(columns=["origem","tipo","nome","valor_atual","aporte_mensal","juros_mensal"])
        if "origem" not in df_inv.columns: df_inv.insert(0, "origem", "B3")

        if metas_inv:
            try:
                df_m = pd.read_csv(StringIO(metas_inv))
                meta_ini, tempo_ini = float(df_m["valor_meta"].iloc[0]), int(df_m["tempo_anos"].iloc[0])
            except: meta_ini, tempo_ini = 100000.0, 10
        else: meta_ini, tempo_ini = 100000.0, 10

        st.info(f"💵 **Dólar Avenue:** R$ {dolar_hoje:.2f} | **Ref:** {data_dolar}")
        
        with st.expander("📝 Editar Minha Carteira de Ativos", expanded=True):
            df_ed_inv = st.data_editor(df_inv, num_rows="dynamic", use_container_width=True, key="editor_inv_abs",
                column_config={
                    "origem": st.column_config.SelectboxColumn("Origem", options=["B3", "Avenue", "Outros"]),
                    "valor_atual": st.column_config.NumberColumn("Valor Original", format="%.2f"),
                    "aporte_mensal": st.column_config.NumberColumn("Aporte (R$)", format="%.2f"),
                    "juros_mensal": st.column_config.NumberColumn("Juros (%)", format="%.2f")
                })
        
        # Lógica de Câmbio
        df_ed_inv["valor_efetivo"] = df_ed_inv.apply(lambda r: float(r["valor_atual"]) * dolar_hoje if str(r.get("origem","")).lower().strip() == "avenue" else float(r["valor_atual"]), axis=1)

        if not df_ed_inv.empty:
            total_inv = df_ed_inv["valor_efetivo"].sum()
            with st.sidebar:
                st.markdown("---")
                v_meta = st.number_input("Sua Meta Final (R$)", value=meta_ini, format="%.2f")
                t_anos = st.slider("Prazo (Anos)", 1, 50, value=tempo_ini)

            # Cálculo de Projeção de Juros Compostos
            meses_proj = t_anos * 12
            projs = [0.0] * (meses_proj + 1)
            for _, r in df_ed_inv.iterrows():
                v, ap, ju = float(r["valor_efetivo"]), float(r.get("aporte_mensal",0)), (float(r.get("juros_mensal",0))/100)
                acum = v
                for m in range(meses_proj+1):
                    if m > 0: acum = (acum * (1 + ju)) + ap
                    projs[m] += acum

            st.markdown("---")
            k1, k2, k3 = st.columns(3)
            k1.metric("Património Hoje", f"R$ {total_inv:,.2f}")
            k2.metric(f"Proj. em {t_anos} anos", f"R$ {projs[-1]:,.2f}")
            prog = (total_inv / v_meta) * 100 if v_meta > 0 else 0
            k3.metric("Atingimento Meta", f"{prog:.1f}%", delta=f"Faltam R$ {v_meta - total_inv:,.2f}", delta_color="inverse")

            with st.expander("💱 Racional da Conversão Cambial", expanded=False):
                df_rat = df_ed_inv.copy()
                df_rat["Cotação"] = df_rat["origem"].apply(lambda x: dolar_hoje if str(x).lower().strip()=="avenue" else 1.0)
                st.dataframe(df_rat[["origem", "nome", "valor_atual", "Cotação", "valor_efetivo"]], use_container_width=True)

            g1, g2 = st.columns(2)
            with g1:
                st.subheader("📂 Alocação por Tipo")
                df_t = df_ed_inv.groupby("tipo")["valor_efetivo"].sum().reset_index()
                fig_inv_pie = px.pie(df_t, names='tipo', values='valor_efetivo', hole=.4)
                fig_inv_pie.update_traces(textinfo='percent+label', texttemplate='<b>%{label}</b><br><b>%{percent:.1%}</b>', textfont_size=16)
                st.plotly_chart(fig_inv_pie, use_container_width=True)
            with g2:
                st.subheader("📈 Curva de Crescimento")
                fig_ev = go.Figure()
                fig_ev.add_trace(go.Scatter(y=projs, fill='tozeroy', line=dict(color='#00C805', width=3)))
                fig_ev.add_hline(y=v_meta, line_dash="dash", line_color="red", annotation_text="Meta")
                st.plotly_chart(fig_ev, use_container_width=True)

            # Inteligência de Rebalanceamento
            st.markdown("---")
            st.subheader("⚖️ Inteligência de Rebalanceamento")
            df_bal = df_ed_inv.groupby("tipo")["valor_efetivo"].sum().reset_index()
            cols_b = st.columns(len(df_bal) if not df_bal.empty else 1)
            for i, row in df_bal.iterrows():
                with cols_b[i % len(cols_b)]:
                    st.write(f"**{row['tipo']}**")
                    m_perc = st.number_input(f"Meta %", 0.0, 100.0, 100.0/len(df_bal), key=f"rebal_{row['tipo']}")
                    dif = ((m_perc / 100) * total_inv) - row['valor_efetivo']
                    if dif > 0: st.success(f"Aportar: R$ {dif:,.2f}")
                    else: st.warning(f"Excesso: R$ {abs(dif):,.2f}")

        if st.sidebar.button("💾 SALVAR INVESTIMENTOS", use_container_width=True):
            save_git_file("dados.csv", df_ed_inv[["origem","tipo","nome","valor_atual","aporte_mensal","juros_mensal"]].to_csv(index=False), sha_inv, "Sync")
            save_git_file("metas.csv", pd.DataFrame([{"valor_meta": v_meta, "tempo_anos": t_anos}]).to_csv(index=False), sha_metas, "Sync")
            st.sidebar.success("Investimentos Sincronizados!")

    # ==========================================
    # ABA 2: FLUXO DE CAIXA (MANUAL TOTAL)
    # ==========================================
    elif menu == "💸 Fluxo de Caixa":
        st.title("💸 Fluxo de Caixa")
        gr, gs = get_git_file("gastos.csv")
        df_g = pd.read_csv(StringIO(gr), on_bad_lines='skip') if gr else pd.DataFrame(columns=["descricao","categoria","tipo_custo","fluxo","ano","mes","valor","status","recorrente"])

        c1, c2, c3 = st.columns([1, 1, 1])
        with c1: a_s = st.selectbox("Ano", [2024, 2025, 2026], index=2)
        with c2: m_s = st.selectbox("Mês", list(meses_map.keys()), index=datetime.now().month - 1)
        
        df_mes = df_g[(df_g["ano"] == a_s) & (df_g["mes"] == m_s)].copy()

        def salvar_fluxo_total(df_para_salvar):
            df_para_salvar["valor"] = df_para_salvar["valor"].abs()
            df_outros = df_g[~((df_g["ano"] == a_s) & (df_g["mes"] == m_s))]
            df_final = pd.concat([df_outros, df_para_salvar], ignore_index=True)
            save_git_file("gastos.csv", df_final.to_csv(index=False), gs, f"Save {m_s}")
            st.toast("✅ Dados Salvos!")

        with c3:
            st.write(" "); st.write(" ")
            if st.button("💾 SALVAR ALTERAÇÕES", key="btn_topo", use_container_width=True):
                salvar_fluxo_total(st.session_state.editor_fluxo_abs); st.rerun()

        df_p = df_mes[df_mes["status"] == "✅ Pago"]
        receita, despesa = df_p[df_p["fluxo"] == "Receita"]["valor"].sum(), df_p[df_p["fluxo"] == "Despesa"]["valor"].sum()
        m1, m2, m3 = st.columns(3)
        m1.metric("Recebido", f"R$ {receita:,.2f}")
        m2.metric("Saídas Pagas", f"R$ {despesa:,.2f}", delta_color="inverse")
        m3.metric("Saldo Real", f"R$ {receita - despesa:,.2f}")

        df_ed_caixa = st.data_editor(df_mes, num_rows="dynamic", use_container_width=True, key="editor_fluxo_abs",
            column_config={
                "status": st.column_config.SelectboxColumn("Status", options=["✅ Pago", "⏳ Pendente"]),
                "fluxo": st.column_config.SelectboxColumn("Fluxo", options=["Receita", "Despesa"]),
                "categoria": st.column_config.SelectboxColumn("Categoria", options=sorted(["salário", "Investimento", "Contas domésticas", "Cartão de crédito", "Educação", "Obra casa", "Lazer", "Saúde", "Aluguel"]))
            })
        if st.button("💾 SALVAR ALTERAÇÕES", key="btn_baixo", use_container_width=True):
            salvar_fluxo_total(df_ed_caixa); st.rerun()

        st.markdown("---")
        if st.button("🔄 Replicar Recorrentes para Próximo Mês"):
            idx_m = list(meses_map.keys()).index(m_s)
            p_m = list(meses_map.keys())[0] if idx_m == 11 else list(meses_map.keys())[idx_m + 1]
            p_a = a_s + 1 if idx_m == 11 else a_s
            df_rec = df_mes[df_mes["recorrente"] == True].copy()
            if not df_rec.empty:
                df_rec["mes"], df_rec["ano"], df_rec["status"] = p_m, p_a, "⏳ Pendente"
                df_f = pd.concat([df_g, df_rec], ignore_index=True).drop_duplicates(subset=["descricao","ano","mes"], keep='last')
                save_git_file("gastos.csv", df_f.to_csv(index=False), gs, "Replicar")
                st.success(f"Copiados para {p_m}!")
                st.rerun()

    # ==========================================
    # ABA 3: DASHBOARD AI (VISUAL BRAVO)
    # ==========================================
    elif menu == "📈 Dashboard AI":
        st.title("📈 Performance e Insights AI")
        gr, _ = get_git_file("gastos.csv")
        if gr:
            df = pd.read_csv(StringIO(gr), on_bad_lines='skip')
            df['m_n'] = df['mes'].map(meses_map)
            df['per'] = df['mes'].str[:3] + "/" + df['ano'].astype(str).str[2:]
            df = df.sort_values(['ano', 'm_n'])

            if st.button("🤖 GERAR NOVOS INSIGHTS"):
                for ins in motor_insights_ai(df): st.info(ins)

            # 1. BARRAS LADO A LADO
            st.subheader("1. Receitas vs Despesas Mensais")
            df_h = df.groupby(['per', 'ano', 'm_n', 'fluxo'])['valor'].sum().reset_index().sort_values(['ano', 'm_n'])
            df_h['txt'] = df_h['valor'].apply(lambda x: f"<b>{x/1000:,.1f}k</b>".replace('.', ','))
            fig1 = px.bar(df_h, x='per', y='valor', color='fluxo', barmode='group',
                          color_discrete_map={'Receita': '#00C805', 'Despesa': '#FF4B4B'}, text='txt')
            fig1.update_traces(textfont_size=14, textposition='outside', cliponaxis=False)
            st.plotly_chart(fig1, use_container_width=True)

            col_a, col_b = st.columns(2)
            with col_a:
                # 2. ROSCA CATEGORIA
                st.subheader("2. % por Categoria")
                df_c = df[df['fluxo'] == 'Despesa'].groupby('categoria')['valor'].sum().reset_index().sort_values('valor', ascending=False)
                fig2 = px.pie(df_c, names='categoria', values='valor', hole=.5)
                fig2.update_traces(textinfo='percent+label', texttemplate='<b>%{label}</b><br><b>%{percent:.1%}</b>',
                                  textfont_size=14, textposition='outside')
                fig2.update_layout(showlegend=False, margin=dict(t=80, b=80, l=100, r=100))
                st.plotly_chart(fig2, use_container_width=True)
            with col_b:
                # 3. TIPO CUSTO
                st.subheader("3. Perfil de Saídas")
                df_tc = df[df['fluxo'] == 'Despesa'].groupby('tipo_custo')['valor'].sum().reset_index()
                df_tc['txt'] = df_tc['valor'].apply(lambda x: f"<b>{x/1000:,.1f}k</b>".replace('.', ','))
                fig3 = px.bar(df_tc, x='tipo_custo', y='valor', color='tipo_custo', text='txt')
                fig3.update_traces(textfont_size=14, textposition='outside')
                st.plotly_chart(fig3, use_container_width=True)

            # 4. ACUMULADO HÍBRIDO
            st.subheader("4. Fluxo Acumulado: Receita (Barra) vs Despesa (Linha)")
            df_a = df.groupby(['per', 'ano', 'm_n', 'fluxo'])['valor'].sum().reset_index().sort_values(['ano', 'm_n'])
            df_a['acu'] = df_a.groupby('fluxo')['valor'].cumsum()
            fig4 = go.Figure()
            dr = df_a[df_a['fluxo'] == 'Receita']
            fig4.add_trace(go.Bar(x=dr['per'], y=dr['acu'], name="Acum. Rec.", marker_color='rgba(0, 200, 5, 0.3)',
                                  text=[f"<b>{v/1000:,.1f}k</b>".replace('.', ',') for v in dr['acu']], textposition='auto', textfont_size=14))
            dd = df_a[df_a['fluxo'] == 'Despesa']
            fig4.add_trace(go.Scatter(x=dd['per'], y=dd['acu'], name="Acum. Desp.", mode='lines+markers+text',
                                      line=dict(color='#FF4B4B', width=5), textfont=dict(size=14, color='#B22222'),
                                      text=[f"<b>{v/1000:,.1f}k</b>".replace('.', ',') for v in dd['acu']], textposition="bottom center"))
            fig4.update_layout(yaxis=dict(range=[0, df_a['acu'].max() * 1.3]), height=500)
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.warning("Sem dados históricos.")

    authenticator.logout("Sair", "sidebar")
