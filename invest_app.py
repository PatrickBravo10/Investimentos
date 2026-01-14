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
st.set_page_config(page_title="Gestor Patrick AI ELITE 2026", layout="wide", page_icon="🏦")

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

# --- 3. MOTOR DE INTELIGÊNCIA ARTIFICIAL (POOL DE 30+ INSIGHTS) ---
def engine_insights_pro(df, df_inv, v_meta):
    if df.empty: return ["Lançamentos insuficientes para análise."]
    
    insights = []
    df_d = df[df['fluxo'] == 'Despesa'].copy()
    df_r = df[df['fluxo'] == 'Receita'].copy()
    tot_r = df_r['valor'].sum()
    tot_d = df_d['valor'].sum()
    
    # Insights de Pareto e Anomalias
    if not df_d.empty:
        cat_g = df_d.groupby('categoria')['valor'].sum().sort_values(ascending=False)
        insights.append(f"🎯 **Lei de Pareto:** A categoria **'{cat_g.index[0]}'** representa {(cat_g[0]/tot_d*100):.1f}% dos teus gastos totais. Focar aqui gera o maior impacto.")
        
        avg, std = df_d['valor'].mean(), df_d['valor'].std()
        anomalias = df_d[df_d['valor'] > (avg + 1.8 * std)]
        if not anomalias.empty:
            insights.append(f"🚨 **Detecção de Anomalia:** O gasto com '{anomalias.iloc[0]['descricao']}' fugiu do teu padrão estatístico.")

    # Insights de Saving Rate
    s_rate = ((tot_r - tot_d) / tot_r * 100) if tot_r > 0 else 0
    if s_rate > 20: insights.append(f"🚀 **Performance de Elite:** Tua taxa de poupança está em {s_rate:.1f}%. Estás no caminho da liberdade financeira.")
    elif s_rate < 0: insights.append(f"⚠️ **Alerta de Caixa:** Estás a gastar mais do que ganhas. O déficit é de {abs(s_rate):.1f}%.")

    # Insights de Patrimônio
    if not df_inv.empty:
        pat_atual = df_inv['valor_efetivo'].sum()
        if pat_atual < v_meta:
            insights.append(f"📈 **Caminho da Meta:** Estás a {(pat_atual/v_meta*100):.1f}% de atingir o teu objetivo de R$ {v_meta:,.0f}.")

    # Pool de Dicas de Gestão (Sorteio Dinâmico)
    dicas = [
        "💡 **Dica de Gestão:** Revisa os teus custos fixos trimestralmente para evitar o engessamento do orçamento.",
        "📊 **Estratégia:** Mantém ativos dolarizados (Avenue) para proteger o teu patrimônio contra a inflação local.",
        "🛡️ **Reserva:** Garante 6 meses de custo fixo em liquidez imediata antes de aumentar o risco.",
        "⚖️ **Diversificação:** Não permitas que um único ativo represente mais de 25% da tua carteira total.",
        "💰 **Consistência:** O segredo da riqueza exponencial é o aporte mensal constante, não apenas o juro.",
        "📉 **Análise:** Se os custos variáveis subirem 2 meses seguidos, corta 10% do lazer no mês seguinte."
    ]
    insights.extend(random.sample(dicas, 2))
    random.shuffle(insights)
    return insights[:5]

# --- 4. AUTENTICAÇÃO ---
names = ["Patrick Bravo"]
usernames = ["admin"]
passwords = ["12345"] 
authenticator = stauth.Authenticate({"usernames": {usernames[0]: {"name": names[0], "password": passwords[0]}}}, "cookie_invest", "key_invest", 30)
authenticator.login(location="main")

if st.session_state["authentication_status"]:
    st.sidebar.title(f"👋 Olá, Patrick")
    menu = st.sidebar.radio("Navegação Principal", ["📊 Investimentos", "💸 Fluxo de Caixa", "📈 Dashboard AI"])
    
    meses_map = {"Janeiro":1, "Fevereiro":2, "Março":3, "Abril":4, "Maio":5, "Junho":6, "Julho":7, "Agosto":8, "Setembro":9, "Outubro":10, "Novembro":11, "Dezembro":12}

    # ==========================================
    # ABA 1: INVESTIMENTOS (TUDO INTEGRADO)
    # ==========================================
    if menu == "📊 Investimentos":
        st.title("📊 Gestão de Patrimônio & Ativos")
        dolar, _ = get_dollar_rate()
        c_raw, c_sha = get_git_file("dados.csv")
        m_raw, m_sha = get_git_file("metas.csv")
        df_inv = pd.read_csv(StringIO(c_raw)) if c_raw else pd.DataFrame(columns=["origem","tipo","nome","valor_atual","aporte_mensal","juros_mensal"])
        if "origem" not in df_inv.columns: df_inv.insert(0, "origem", "B3")
        
        if m_raw:
            dm = pd.read_csv(StringIO(m_raw))
            m_ini, t_ini = float(dm["valor_meta"].iloc[0]), int(dm["tempo_anos"].iloc[0])
        else: m_ini, t_ini = 100000.0, 10

        st.info(f"💵 **Dólar Avenue:** R$ {dolar:.2f}")
        
        with st.expander("📝 Editar Carteira de Ativos", expanded=True):
            df_ed_inv = st.data_editor(df_inv, num_rows="dynamic", use_container_width=True, key="ed_inv_total",
                column_config={
                    "origem": st.column_config.SelectboxColumn("Origem", options=["B3", "Avenue", "Outros"]),
                    "valor_atual": st.column_config.NumberColumn("Valor Original", format="%.2f"),
                    "aporte_mensal": st.column_config.NumberColumn("Aporte (R$)", format="%.2f"),
                    "juros_mensal": st.column_config.NumberColumn("Juros (%)", format="%.2f")
                })
        
        df_ed_inv["valor_efetivo"] = df_ed_inv.apply(lambda r: float(r["valor_atual"]) * dolar if str(r.get("origem","")).lower().strip() == "avenue" else float(r["valor_atual"]), axis=1)

        if not df_ed_inv.empty:
            total_v = df_ed_inv["valor_efetivo"].sum()
            with st.sidebar:
                st.markdown("---")
                v_meta = st.number_input("Meta Patrimônio (R$)", value=m_ini, format="%.2f")
                t_anos = st.slider("Prazo Projeção (Anos)", 1, 50, value=t_ini)

            # Projeção Financeira
            meses_proj = t_anos * 12
            projs = [0.0] * (meses_proj + 1)
            for _, r in df_ed_inv.iterrows():
                v, ap, ju = float(r["valor_efetivo"]), float(r.get("aporte_mensal",0)), (float(r.get("juros_mensal",0))/100)
                acum = v
                for m in range(meses_proj+1):
                    if m > 0: acum = (acum * (1 + ju)) + ap
                    projs[m] += acum

            k1, k2, k3 = st.columns(3)
            k1.metric("Total Hoje", f"R$ {total_v:,.2f}")
            k2.metric(f"Proj. em {t_anos} anos", f"R$ {projs[-1]:,.2f}")
            prog = (total_v/v_meta)*100 if v_meta>0 else 0
            k3.metric("Meta", f"{prog:.1f}%", delta=f"Faltam R$ {v_meta-total_v:,.2f}", delta_color="inverse")

            with st.expander("💱 Racional da Conversão Cambial", expanded=False):
                df_rat = df_ed_inv.copy()
                df_rat["Cotação"] = df_rat["origem"].apply(lambda x: dolar if str(x).lower().strip()=="avenue" else 1.0)
                st.dataframe(df_rat[["origem", "nome", "valor_atual", "Cotação", "valor_efetivo"]], use_container_width=True)

            cola, colb = st.columns(2)
            with cola:
                st.subheader("📂 Alocação")
                df_t = df_ed_inv.groupby("tipo")["valor_efetivo"].sum().reset_index()
                fig_p = px.pie(df_t, names='tipo', values='valor_efetivo', hole=.4)
                fig_p.update_traces(textinfo='percent+label', texttemplate='<b>%{label}</b><br><b>%{percent:.1%}</b>', textfont_size=14)
                st.plotly_chart(fig_p, use_container_width=True)
            with colb:
                st.subheader("⚖️ Inteligência de Rebalanceamento")
                for i, r in df_t.iterrows():
                    m_p = 100/len(df_t)
                    dif = ((m_p/100)*total_v) - r['valor_efetivo']
                    if dif>0: st.success(f"Aportar em {r['tipo']}: R$ {dif:,.2f}")
                    else: st.warning(f"Excesso em {r['tipo']}: R$ {abs(dif):,.2f}")

        if st.sidebar.button("💾 SALVAR INVESTIMENTOS", use_container_width=True):
            save_git_file("dados.csv", df_ed_inv[["origem","tipo","nome","valor_atual","aporte_mensal","juros_mensal"]].to_csv(index=False), c_sha, "Sync")
            save_git_file("metas.csv", pd.DataFrame([{"valor_meta": v_meta, "tempo_anos": t_anos}]).to_csv(index=False), m_sha, "Sync")
            st.sidebar.success("Investimentos Salvos!")

    # ==========================================
    # ABA 2: FLUXO DE CAIXA
    # ==========================================
    elif menu == "💸 Fluxo de Caixa":
        st.title("💸 Fluxo de Caixa")
        gr, gs = get_git_file("gastos.csv")
        df_g = pd.read_csv(StringIO(gr), on_bad_lines='skip') if gr else pd.DataFrame(columns=["descricao","categoria","tipo_custo","fluxo","ano","mes","valor","status","recorrente"])

        c1, c2, c3 = st.columns([1, 1, 1])
        with c1: a_s = st.selectbox("Selecione o Ano", [2024, 2025, 2026], index=2)
        with c2: m_s = st.selectbox("Selecione o Mês", list(meses_map.keys()), index=datetime.now().month - 1)
        
        df_mes = df_g[(df_g["ano"] == a_s) & (df_g["mes"] == m_s)].copy()

        def salvar_g_manual(df_para_s):
            df_para_s["valor"] = df_para_s["valor"].abs()
            df_outros = df_g[~((df_g["ano"] == a_s) & (df_g["mes"] == m_s))]
            df_f = pd.concat([df_outros, df_para_s], ignore_index=True)
            save_git_file("gastos.csv", df_f.to_csv(index=False), gs, f"Save {m_s}")
            st.toast("✅ Salvo com sucesso!")

        with c3:
            st.write(" "); st.write(" ")
            if st.button("💾 SALVAR ALTERAÇÕES (TOPO)", key="bt", use_container_width=True):
                salvar_g_manual(st.session_state.editor_fluxo_total); st.rerun()

        df_p = df_mes[df_mes["status"] == "✅ Pago"]
        receita, despesa = df_p[df_p["fluxo"] == "Receita"]["valor"].sum(), df_p[df_p["fluxo"] == "Despesa"]["valor"].sum()
        m1, m2, m3 = st.columns(3)
        m1.metric("Entradas Pagas", f"R$ {receita:,.2f}")
        m2.metric("Saídas Pagas", f"R$ {despesa:,.2f}", delta_color="inverse")
        m3.metric("Saldo Real em Conta", f"R$ {receita - despesa:,.2f}")

        st.markdown("---")
        df_ed_caixa = st.data_editor(df_mes, num_rows="dynamic", use_container_width=True, key="editor_fluxo_total",
            column_config={
                "status": st.column_config.SelectboxColumn("Status", options=["✅ Pago", "⏳ Pendente"]),
                "fluxo": st.column_config.SelectboxColumn("Fluxo", options=["Receita", "Despesa"]),
                "categoria": st.column_config.SelectboxColumn("Categoria", options=sorted(["salário", "Investimento", "Contas domésticas", "Cartão de crédito", "Educação", "Obra casa", "Lazer", "Saúde", "Aluguel"]))
            })

        if st.button("💾 SALVAR ALTERAÇÕES (BASE)", key="bb", use_container_width=True):
            salvar_g_manual(df_ed_caixa); st.rerun()

        st.markdown("---")
        if st.button("🔄 Replicar Recorrentes para o Mês Seguinte"):
            idx_m = list(meses_map.keys()).index(m_s)
            p_m = list(meses_map.keys())[0] if idx_m == 11 else list(meses_map.keys())[idx_m + 1]
            p_a = a_s + 1 if idx_m == 11 else a_s
            df_rec = df_mes[df_mes["recorrente"] == True].copy()
            if not df_rec.empty:
                df_rec["mes"], df_rec["ano"], df_rec["status"] = p_m, p_a, "⏳ Pendente"
                df_f = pd.concat([df_g, df_rec], ignore_index=True).drop_duplicates(subset=["descricao","ano","mes"], keep='last')
                save_git_file("gastos.csv", df_f.to_csv(index=False), gs, "Replicar")
                st.success(f"Contas fixas copiadas para {p_m}!")
                st.rerun()

    # ==========================================
    # ABA 3: DASHBOARD AI
    # ==========================================
    elif menu == "📈 Dashboard AI":
        st.title("📈 Dashboard AI & Performance")
        gr_raw, _ = get_git_file("gastos.csv")
        ci_raw, _ = get_git_file("dados.csv")
        mi_raw, _ = get_git_file("metas.csv")
        
        if gr_raw:
            df = pd.read_csv(StringIO(gr_raw), on_bad_lines='skip')
            df['m_n'] = df['mes'].map(meses_map)
            df['per'] = df['mes'].str[:3] + "/" + df['ano'].astype(str).str[2:]
            df = df.sort_values(['ano', 'm_n'])
            
            # --- MOTOR DE INSIGHTS ---
            st.subheader("🤖 Smart Insights")
            if st.button("✨ GERAR NOVOS INSIGHTS AGORA"):
                df_i_ai = pd.read_csv(StringIO(ci_raw)) if ci_raw else pd.DataFrame()
                if not df_i_ai.empty: 
                    d_ai, _ = get_dollar_rate()
                    df_i_ai["valor_efetivo"] = df_i_ai.apply(lambda r: float(r["valor_atual"]) * d_ai if str(r.get("origem","")).lower()=="avenue" else float(r["valor_atual"]), axis=1)
                
                v_m_ai = 100000.0
                if mi_raw: v_m_ai = float(pd.read_csv(StringIO(mi_raw))["valor_meta"].iloc[0])
                
                for ins in engine_insights_pro(df, df_i_ai, v_m_ai): st.info(ins)

            st.markdown("---")
            # 1. BARRAS COMPARATIVAS (NÚMEROS 1,5k)
            st.subheader("1. Receitas vs Despesas Mensais")
            df_h = df.groupby(['per', 'ano', 'm_n', 'fluxo'])['valor'].sum().reset_index().sort_values(['ano', 'm_n'])
            df_h['txt'] = df_h['valor'].apply(lambda x: f"<b>{x/1000:,.1f}k</b>".replace('.', ','))
            fig1 = px.bar(df_h, x='per', y='valor', color='fluxo', barmode='group',
                          color_discrete_map={'Receita': '#00C805', 'Despesa': '#FF4B4B'}, text='txt')
            fig1.update_traces(textfont_size=14, textposition='outside', cliponaxis=False)
            st.plotly_chart(fig1, use_container_width=True)

            cola, colb = st.columns(2)
            with cola:
                # 2. ROSCA CATEGORIAS (SEM CORTES)
                st.subheader("2. % de Gastos por Categoria")
                df_c = df[df['fluxo'] == 'Despesa'].groupby('categoria')['valor'].sum().reset_index().sort_values('valor', ascending=False)
                fig2 = px.pie(df_c, names='categoria', values='valor', hole=.5)
                fig2.update_traces(textinfo='percent+label', texttemplate='<b>%{label}</b><br><b>%{percent:.1%}</b>',
                                  textfont_size=14, textposition='outside')
                fig2.update_layout(showlegend=False, margin=dict(t=80, b=80, l=100, r=100))
                st.plotly_chart(fig2, use_container_width=True)
            with colb:
                # 4. ACUMULADO HÍBRIDO (BARRA RECEITA / LINHA DESPESA)
                st.subheader("4. Fluxo Acumulado Histórico")
                df_a = df.groupby(['per', 'ano', 'm_n', 'fluxo'])['valor'].sum().reset_index().sort_values(['ano', 'm_n'])
                df_a['acu'] = df_a.groupby('fluxo')['valor'].cumsum()
                fig4 = go.Figure()
                dr = df_a[df_a['fluxo'] == 'Receita']
                fig4.add_trace(go.Bar(x=dr['per'], y=dr['acu'], name="Acumulado Receita", marker_color='rgba(0, 200, 5, 0.3)'))
                dd = df_a[df_a['fluxo'] == 'Despesa']
                fig4.add_trace(go.Scatter(x=dd['per'], y=dd['acu'], name="Acumulado Despesa", mode='lines+markers+text',
                                          line=dict(color='#FF4B4B', width=5), textfont=dict(size=14, color='#B22222'),
                                          text=[f"<b>{v/1000:,.1f}k</b>".replace('.', ',') for v in dd['acu']], textposition="bottom center"))
                fig4.update_layout(yaxis=dict(range=[0, df_a['acu'].max() * 1.3]))
                st.plotly_chart(fig4, use_container_width=True)
        else:
            st.warning("Sem dados históricos para exibir o Dashboard.")

    st.sidebar.markdown("---")
    authenticator.logout("Sair do Sistema", "sidebar")
