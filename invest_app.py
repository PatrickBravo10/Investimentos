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
st.set_page_config(page_title="Gestor Patrick AI ELITE PRO 2026", layout="wide", page_icon="🏦")

# --- 2. FUNÇÕES DE SUPORTE TÉCNICO ---
@st.cache_data(ttl=3600)
def get_dollar_rate():
    try:
        url = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
        res = requests.get(url, timeout=5).json()
        return float(res["USDBRL"]["bid"]), res["USDBRL"]["create_date"]
    except:
        return 5.85, "Cotação Fixa (Erro API)"

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

# --- 3. MOTOR DE INTELIGÊNCIA ARTIFICIAL (30+ INSIGHTS DINÂMICOS) ---
def engine_insights_300(df_gastos, df_inv, v_meta):
    if df_gastos.empty: return ["Lançamentos insuficientes para processar inteligência."]
    
    insights = []
    df_d = df_gastos[df_gastos['fluxo'] == 'Despesa'].copy()
    df_r = df_gastos[df_gastos['fluxo'] == 'Receita'].copy()
    tot_r = df_r['valor'].sum()
    tot_d = df_d['valor'].sum()
    saldo = tot_r - tot_d
    saving_rate = (saldo / tot_r * 100) if tot_r > 0 else -100

    # LÓGICA 1: ANÁLISE DE PARETO (CATEGORIA DOMINANTE)
    if not df_d.empty:
        cat_g = df_d.groupby('categoria')['valor'].sum().sort_values(ascending=False)
        top_cat = cat_g.index[0]
        insights.append(f"🎯 **Lei de Pareto:** A categoria **'{top_cat}'** domina {(cat_g[0]/tot_d*100):.1f}% dos teus gastos. Focar aqui é a estratégia mais rápida de economia.")

    # LÓGICA 2: DETECÇÃO DE ANOMALIAS (DESVIO PADRÃO)
    if len(df_d) > 4:
        avg = df_d['valor'].mean()
        std = df_d['valor'].std()
        anomalias = df_d[df_d['valor'] > (avg + 1.7 * std)]
        if not anomalias.empty:
            insights.append(f"🚨 **Anomalia Estatística:** O item **'{anomalias.iloc[0]['descricao']}'** fugiu totalmente do teu padrão. Foi um evento isolado ou novo hábito?")

    # LÓGICA 3: SAVING RATE E RUNWAY
    if saving_rate < 0:
        insights.append(f"🧨 **Risco de Caixa:** Teu Saving Rate está negativo em **{abs(saving_rate):.1f}%**. Estás a queimar patrimônio acumulado.")
    elif saving_rate > 25:
        insights.append(f"🚀 **Performance Pro:** Poupar **{saving_rate:.1f}%** coloca-te no top 5% dos investidores em termos de disciplina.")

    # LÓGICA 4: ENGESSAMENTO DE RENDA
    fixos = df_d[df_d['tipo_custo'] == 'Fixo']['valor'].sum()
    engess = (fixos / tot_r * 100) if tot_r > 0 else 0
    if engess > 50:
        insights.append(f"🔒 **Orçamento Engessado:** **{engess:.1f}%** da tua renda está presa em custos fixos. Tens pouca margem para imprevistos.")

    # LÓGICA 5-30: POOL DE DICAS DE GESTÃO PATRIMONIAL (RANDOMIZADO)
    pool_dicas = [
        "🛡️ **Proteção Cambial:** Manter 20% em Avenue protege o teu poder de compra global.",
        "📊 **Momentum:** Se os aportes mensais subirem 5% ao ano, bates a meta 3 anos mais cedo.",
        "🏦 **Eficiência Fiscal:** Verifica se teus investimentos são isentos de IR (LCI/LCA/Debêntures).",
        "⚖️ **Rebalanceamento:** Se um ativo subir demais, vende o excesso e compra o que está barato.",
        "💰 **Efeito Juros:** No longo prazo, o tempo importa mais que o valor do aporte. Mantém a constância.",
        "📉 **Inflação:** Juros reais são o que importa. Se a inflação é 6%, render 10% é ganhar apenas 4%.",
        "📈 **Diversificação:** Nunca tenhas mais de 10% do patrimônio numa única empresa (Stock).",
        "🛒 **Consumo:** Compras parceladas no cartão engessam o teu fluxo de caixa de meses futuros.",
        "🧠 **Psicologia:** O mercado cai, mas o valor das boas empresas permanece. Não vendas no pânico.",
        "🔍 **Assinaturas:** 15% dos gastos variáveis costumam ser serviços que não usamos plenamente."
    ]
    insights.extend(random.sample(pool_dicas, 3))
    random.shuffle(insights)
    return insights[:6]

# --- 4. SISTEMA DE AUTENTICAÇÃO ---
names = ["Patrick Bravo"]
usernames = ["admin"]
passwords = ["12345"] 
authenticator = stauth.Authenticate({"usernames": {usernames[0]: {"name": names[0], "password": passwords[0]}}}, "cookie_invest", "key_invest", 30)
authenticator.login(location="main")

if st.session_state["authentication_status"]:
    st.sidebar.title(f"👋 Olá, {st.session_state['name']}")
    menu = st.sidebar.radio("Navegação Principal", ["📊 Investimentos", "💸 Fluxo de Caixa", "📈 Dashboard AI & Performance"])
    
    meses_map = {"Janeiro":1, "Fevereiro":2, "Março":3, "Abril":4, "Maio":5, "Junho":6, "Julho":7, "Agosto":8, "Setembro":9, "Outubro":10, "Novembro":11, "Dezembro":12}

    # =========================================================================
    # ABA 1: INVESTIMENTOS (LÓGICA ORIGINAL COMPLETA USD/BRL)
    # =========================================================================
    if menu == "📊 Investimentos":
        st.title("📊 Gestão de Patrimônio & Ativos Globais")
        dolar, ref_dolar = get_dollar_rate()
        
        # Carregamento de Persistência
        c_raw, c_sha = get_git_file("dados.csv")
        m_raw, m_sha = get_git_file("metas.csv")
        df_inv = pd.read_csv(StringIO(c_raw)) if c_raw else pd.DataFrame(columns=["origem","tipo","nome","valor_atual","aporte_mensal","juros_mensal"])
        if "origem" not in df_inv.columns: df_inv.insert(0, "origem", "B3")
        
        if m_raw:
            dm = pd.read_csv(StringIO(m_raw)); m_ini = float(dm["valor_meta"].iloc[0]); t_ini = int(dm["tempo_anos"].iloc[0])
        else: m_ini, t_ini = 100000.0, 10

        st.info(f"💵 **Dólar Avenue (Hoje):** R$ {dolar:.2f} | **Ref:** {ref_dolar}")
        
        # EDITOR DE DADOS ROBUSTO
        with st.expander("📝 Editar Carteira de Ativos", expanded=True):
            df_ed_inv = st.data_editor(df_inv, num_rows="dynamic", use_container_width=True, key="mega_editor_inv",
                column_config={
                    "origem": st.column_config.SelectboxColumn("Origem", options=["B3", "Avenue", "Outros"]),
                    "valor_atual": st.column_config.NumberColumn("Valor Original", format="%.2f"),
                    "aporte_mensal": st.column_config.NumberColumn("Aporte (R$)", format="%.2f"),
                    "juros_mensal": st.column_config.NumberColumn("Juros Mensal (%)", format="%.2f")
                })
        
        # CÁLCULO DE CONVERSÃO REAL-TIME
        df_ed_inv["valor_efetivo"] = df_ed_inv.apply(lambda r: float(r["valor_atual"]) * dolar if str(r.get("origem","")).lower().strip() == "avenue" else float(r["valor_atual"]), axis=1)

        if not df_ed_inv.empty:
            total_patrimonio = df_ed_inv["valor_efetivo"].sum()
            
            with st.sidebar:
                st.markdown("---")
                v_meta = st.number_input("Meta Patrimonial (R$)", value=m_ini, format="%.2f")
                t_anos = st.slider("Horizonte de Tempo (Anos)", 1, 50, value=t_ini)

            # LÓGICA DE PROJEÇÃO DE JUROS COMPOSTOS ATIVO POR ATIVO
            meses_proj = t_anos * 12
            timeline_projs = [0.0] * (meses_proj + 1)
            for _, r in df_ed_inv.iterrows():
                val_i = float(r["valor_efetivo"])
                aport = float(r.get("aporte_mensal", 0))
                taxa_m = float(r.get("juros_mensal", 0)) / 100
                acumulado_ativo = val_i
                for m in range(meses_proj + 1):
                    if m > 0: acumulado_ativo = (acumulado_ativo * (1 + taxa_m)) + aport
                    timeline_projs[m] += acumulado_ativo

            # KPIs FINANCEIROS
            st.markdown("---")
            k1, k2, k3 = st.columns(3)
            k1.metric("Patrimônio Hoje", f"R$ {total_patrimonio:,.2f}")
            k2.metric(f"Proj. {t_anos} Anos", f"R$ {timeline_projs[-1]:,.2f}")
            progresso = (total_patrimonio / v_meta) * 100 if v_meta > 0 else 0
            k3.metric("Atingimento Meta", f"{progresso:.1f}%", delta=f"Faltam R$ {v_meta - total_patrimonio:,.2f}", delta_color="inverse")

            # RACIONAL DA CONVERSÃO (DETALHADO)
            with st.expander("💱 Racional da Conversão Cambial", expanded=False):
                df_rat = df_ed_inv.copy()
                df_rat["Cotação Aplicada"] = df_rat["origem"].apply(lambda x: dolar if str(x).lower().strip()=="avenue" else 1.0)
                st.dataframe(df_rat[["origem", "nome", "valor_atual", "Cotação Aplicada", "valor_efetivo"]], use_container_width=True)

            # GRÁFICOS DE ALOCAÇÃO E CURVA
            g1, g2 = st.columns(2)
            with g1:
                st.subheader("📂 Alocação por Classe")
                df_pie = df_ed_inv.groupby("tipo")["valor_efetivo"].sum().reset_index()
                fig_pie = px.pie(df_pie, names='tipo', values='valor_efetivo', hole=.4)
                fig_pie.update_traces(textinfo='percent+label', texttemplate='<b>%{label}</b><br><b>%{percent:.1%}</b>', textfont_size=14)
                st.plotly_chart(fig_pie, use_container_width=True)
            with g2:
                st.subheader("📈 Curva de Crescimento Estimada")
                fig_line = go.Figure()
                fig_line.add_trace(go.Scatter(y=timeline_projs, fill='tozeroy', line=dict(color='#00C805', width=4)))
                fig_line.add_hline(y=v_meta, line_dash="dash", line_color="red", annotation_text="Meta")
                st.plotly_chart(fig_line, use_container_width=True)

            # INTELIGÊNCIA DE REBALANCEAMENTO
            st.markdown("---")
            st.subheader("⚖️ Inteligência de Rebalanceamento")
            df_rebal = df_ed_inv.groupby("tipo")["valor_efetivo"].sum().reset_index()
            cols_rebal = st.columns(len(df_rebal) if not df_rebal.empty else 1)
            for i, row in df_rebal.iterrows():
                with cols_rebal[i % len(cols_rebal)]:
                    st.write(f"**{row['tipo']}**")
                    meta_p = st.number_input(f"Meta %", 0.0, 100.0, 100.0/len(df_rebal), key=f"rebal_input_{row['tipo']}")
                    diferenca = ((meta_p / 100) * total_patrimonio) - row['valor_efetivo']
                    if diferenca > 0: st.success(f"Aportar: R$ {diferenca:,.2f}")
                    else: st.warning(f"Excesso: R$ {abs(diferenca):,.2f}")

        if st.sidebar.button("💾 SALVAR INVESTIMENTOS", use_container_width=True):
            save_git_file("dados.csv", df_ed_inv[["origem","tipo","nome","valor_atual","aporte_mensal","juros_mensal"]].to_csv(index=False), c_sha, "Sync")
            save_git_file("metas.csv", pd.DataFrame([{"valor_meta": v_meta, "tempo_anos": t_anos}]).to_csv(index=False), m_sha, "Sync")
            st.sidebar.success("Dados Sincronizados no GitHub!")

    # =========================================================================
    # ABA 2: FLUXO DE CAIXA (MANUAL TOTAL COM DROPDOWNS)
    # =========================================================================
    elif menu == "💸 Fluxo de Caixa":
        st.title("💸 Controle de Caixa e Lançamentos")
        gr_raw, gs_sha = get_git_file("gastos.csv")
        df_gastos = pd.read_csv(StringIO(gr_raw), on_bad_lines='skip') if gr_raw else pd.DataFrame(columns=["descricao","categoria","tipo_custo","fluxo","ano","mes","valor","status","recorrente"])

        col_f1, col_f2, col_btn = st.columns([1, 1, 1])
        with col_f1: ano_sel = st.selectbox("Filtrar Ano", [2024, 2025, 2026], index=2)
        with col_f2: mes_sel = st.selectbox("Filtrar Mês", list(meses_map.keys()), index=datetime.now().month - 1)
        
        df_mes_caixa = df_gastos[(df_gastos["ano"] == ano_sel) & (df_gastos["mes"] == mes_sel)].copy()

        def salvar_caixa_total(df_para_salvar):
            df_para_salvar["valor"] = df_para_salvar["valor"].abs()
            df_outros = df_gastos[~((df_gastos["ano"] == ano_sel) & (df_gastos["mes"] == mes_sel))]
            df_final_caixa = pd.concat([df_outros, df_para_salvar], ignore_index=True)
            save_git_file("gastos.csv", df_final_caixa.to_csv(index=False), gs_sha, f"Save {mes_sel}")
            st.toast("✅ Dados Guardados com Sucesso!")

        with col_btn:
            st.write(" "); st.write(" ")
            if st.button("💾 SALVAR ALTERAÇÕES (TOPO)", key="btn_topo_caixa", use_container_width=True):
                salvar_caixa_total(st.session_state.mega_editor_fluxo); st.rerun()

        # KPIs do Mês
        df_pago = df_mes_caixa[df_mes_caixa["status"] == "✅ Pago"]
        entrou, saiu = df_pago[df_pago["fluxo"] == "Receita"]["valor"].sum(), df_pago[df_pago["fluxo"] == "Despesa"]["valor"].sum()
        m1, m2, m3 = st.columns(3)
        m1.metric("Recebido (Pago)", f"R$ {entrou:,.2f}")
        m2.metric("Saído (Pago)", f"R$ {saiu:,.2f}", delta_color="inverse")
        m3.metric("Saldo Real em Conta", f"R$ {entrou - saiu:,.2f}")

        st.markdown("---")
        df_ed_fluxo = st.data_editor(df_mes_caixa, num_rows="dynamic", use_container_width=True, key="mega_editor_fluxo",
            column_config={
                "status": st.column_config.SelectboxColumn("Status", options=["✅ Pago", "⏳ Pendente"]),
                "fluxo": st.column_config.SelectboxColumn("Fluxo", options=["Receita", "Despesa"]),
                "categoria": st.column_config.SelectboxColumn("Categoria", options=sorted(["salário", "Investimento", "Contas domésticas", "Cartão de crédito", "Educação", "Obra casa", "Lazer", "Saúde", "Aluguel"])),
                "tipo_custo": st.column_config.SelectboxColumn("Tipo", options=["Fixo", "Variável"]),
                "valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f")
            })

        if st.button("💾 SALVAR ALTERAÇÕES (BASE)", key="btn_base_caixa", use_container_width=True):
            salvar_caixa_total(df_ed_fluxo); st.rerun()

        st.markdown("---")
        if st.button("🔄 Replicar Recorrentes para o Mês Seguinte"):
            idx_m = list(meses_map.keys()).index(mes_sel)
            p_m = list(meses_map.keys())[0] if idx_m == 11 else list(meses_map.keys())[idx_m + 1]
            p_a = ano_sel + 1 if idx_m == 11 else ano_sel
            df_recorrentes = df_mes_caixa[df_mes_caixa["recorrente"] == True].copy()
            if not df_recorrentes.empty:
                df_recorrentes["mes"], df_recorrentes["ano"], df_recorrentes["status"] = p_m, p_a, "⏳ Pendente"
                df_replicado = pd.concat([df_gastos, df_recorrentes], ignore_index=True).drop_duplicates(subset=["descricao","ano","mes"], keep='last')
                save_git_file("gastos.csv", df_replicado.to_csv(index=False), gs_sha, "Replicar")
                st.success(f"Itens recorrentes copiados para {p_m}!"); st.rerun()

    # =========================================================================
    # ABA 3: DASHBOARD AI & PERFORMANCE (VISUAL DE ALTA DEFINIÇÃO)
    # =========================================================================
    elif menu == "📈 Dashboard AI & Performance":
        st.title("📈 Inteligência Analítica e Dashboards")
        gr_raw, _ = get_git_file("gastos.csv")
        ci_raw, _ = get_git_file("dados.csv")
        mi_raw, _ = get_git_file("metas.csv")
        
        if gr_raw:
            df = pd.read_csv(StringIO(gr_raw), on_bad_lines='skip')
            df['m_n'] = df['mes'].map(meses_map)
            df['per'] = df['mes'].str[:3] + "/" + df['ano'].astype(str).str[2:]
            df = df.sort_values(['ano', 'm_n'])
            
            # MOTOR DE INSIGHTS PRO
            st.subheader("🤖 Smart Insights Patrick AI")
            if st.button("✨ GERAR NOVOS INSIGHTS AGORA"):
                df_i_ai = pd.read_csv(StringIO(ci_raw)) if ci_raw else pd.DataFrame()
                if not df_i_ai.empty: 
                    d_val, _ = get_dollar_rate()
                    df_i_ai["valor_efetivo"] = df_i_ai.apply(lambda r: float(r["valor_atual"]) * d_val if str(r.get("origem","")).lower().strip()=="avenue" else float(r["valor_atual"]), axis=1)
                
                v_m_ai = 100000.0
                if mi_raw: v_m_ai = float(pd.read_csv(StringIO(mi_raw))["valor_meta"].iloc[0])
                
                res_ins = engine_insights_300(df, df_i_ai, v_m_ai)
                for ins in res_ins: st.info(ins)

            st.markdown("---")
            # 1. BARRAS LADO A LADO (FORMATO 1,5k)
            st.subheader("1. Evolução Mensal: Faturamento vs Despesas")
            df_hist = df.groupby(['per', 'ano', 'm_n', 'fluxo'])['valor'].sum().reset_index().sort_values(['ano', 'm_n'])
            df_hist['txt'] = df_hist['valor'].apply(lambda x: f"<b>{x/1000:,.1f}k</b>".replace('.', ','))
            
            fig_hist = px.bar(df_hist, x='per', y='valor', color='fluxo', barmode='group',
                          color_discrete_map={'Receita': '#00C805', 'Despesa': '#FF4B4B'}, text='txt')
            fig_hist.update_traces(textfont=dict(size=14), textposition='outside', cliponaxis=False)
            st.plotly_chart(fig_hist, use_container_width=True)

            cola, colb = st.columns(2)
            with cola:
                # 2. ROSCA CATEGORIAS (SEM CORTES)
                st.subheader("2. % de Gastos por Categoria")
                df_cat = df[df['fluxo'] == 'Despesa'].groupby('categoria')['valor'].sum().reset_index().sort_values('valor', ascending=False)
                fig_pie_cat = px.pie(df_cat, names='categoria', values='valor', hole=.5)
                fig_pie_cat.update_traces(textinfo='percent+label', texttemplate='<b>%{label}</b><br><b>%{percent:.1%}</b>',
                                        textfont_size=14, textposition='outside')
                fig_pie_cat.update_layout(showlegend=False, margin=dict(t=80, b=80, l=100, r=100))
                st.plotly_chart(fig_pie_cat, use_container_width=True)
            
            with colb:
                # 3. TIPO DE CUSTO
                st.subheader("3. Perfil de Saídas (Fixo vs Variável)")
                df_tipo = df[df['fluxo'] == 'Despesa'].groupby('tipo_custo')['valor'].sum().reset_index()
                df_tipo['txt'] = df_tipo['valor'].apply(lambda x: f"<b>{x/1000:,.1f}k</b>".replace('.', ','))
                fig_tipo = px.bar(df_tipo, x='tipo_custo', y='valor', color='tipo_custo', text='txt')
                fig_tipo.update_traces(textfont=dict(size=14), textposition='outside')
                st.plotly_chart(fig_tipo, use_container_width=True)

            # 4. ACUMULADO HÍBRIDO (BARRA RECEITA / LINHA DESPESA)
            st.subheader("4. Fluxo Acumulado Histórico")
            df_acu = df.groupby(['per', 'ano', 'm_n', 'fluxo'])['valor'].sum().reset_index().sort_values(['ano', 'm_n'])
            df_acu['acu'] = df_acu.groupby('fluxo')['valor'].cumsum()
            
            fig_acu = go.Figure()
            dr = df_acu[df_acu['fluxo'] == 'Receita']
            fig_acu.add_trace(go.Bar(x=dr['per'], y=dr['acu'], name="Acumulado Receita", marker_color='rgba(0, 200, 5, 0.3)',
                                   text=[f"<b>{v/1000:,.1f}k</b>".replace('.', ',') for v in dr['acu']], textposition='auto', textfont_size=14))
            
            dd = df_acu[df_acu['fluxo'] == 'Despesa']
            fig_acu.add_trace(go.Scatter(x=dd['per'], y=dd['acu'], name="Acumulado Despesa", mode='lines+markers+text',
                                       line=dict(color='#FF4B4B', width=5), textfont=dict(size=14, color='#B22222'),
                                       text=[f"<b>{v/1000:,.1f}k</b>".replace('.', ',') for v in dd['acu']], textposition="bottom center"))
            
            fig_acu.update_layout(yaxis=dict(range=[0, df_acu['acu'].max() * 1.3]), height=500)
            st.plotly_chart(fig_acu, use_container_width=True)
        else:
            st.warning("Sem dados históricos no arquivo de gastos.")

    authenticator.logout("Sair do Sistema", "sidebar")

elif st.session_state["authentication_status"] is False:
    st.error("Login ou senha incorretos.")
