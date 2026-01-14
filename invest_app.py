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
    # ABA 1: INVESTIMENTOS (SISTEMA COMPLETO)
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

        with st.expander("📝 Editar Carteira de Ativos", expanded=True):
            df_ed_inv = st.data_editor(df_inv, num_rows="dynamic", use_container_width=True, key="editor_inv",
                column_config={
                    "valor_atual": st.column_config.NumberColumn("Valor Unidade", format="%.2f"),
                    "aporte_mensal": st.column_config.NumberColumn("Aporte (R$)", format="%.2f"),
                    "juros_mensal": st.column_config.NumberColumn("Juros (%)", format="%.2f%%"),
                    "origem": st.column_config.SelectboxColumn("Origem", options=["B3", "Avenue", "Outros"])
                })

        # Cálculo de conversão Avenue -> Real
        df_ed_inv["valor_efetivo"] = df_ed_inv.apply(lambda r: float(r["valor_atual"]) * dolar_hoje if str(r.get("origem","")).lower().strip() == "avenue" else float(r["valor_atual"]), axis=1)

        if not df_ed_inv.empty:
            total_inv = df_ed_inv["valor_efetivo"].sum()
            with st.sidebar:
                st.markdown("---")
                v_meta = st.number_input("Meta Património (R$)", value=meta_ini, format="%.2f")
                t_anos = st.slider("Prazo Projeção (Anos)", 1, 50, value=tempo_ini)

            # Projeção Financeira
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
            k1.metric("Total Carteira", f"R$ {total_inv:,.2f}")
            k2.metric(f"Proj. {t_anos} anos", f"R$ {projs[-1]:,.2f}")
            prog = (total_inv / v_meta) * 100 if v_meta > 0 else 0
            k3.metric("Progresso Meta", f"{prog:.1f}%", delta=f"Faltam R$ {v_meta - total_inv:,.2f}", delta_color="inverse")

            with st.expander("💱 Racional da Conversão Cambial", expanded=False):
                df_rat = df_ed_inv.copy()
                df_rat["Cotação"] = df_rat["origem"].apply(lambda x: dolar_hoje if str(x).lower().strip()=="avenue" else 1.0)
                st.dataframe(df_rat[["origem", "nome", "valor_atual", "Cotação", "valor_efetivo"]], use_container_width=True)

            g1, g2 = st.columns(2)
            with g1:
                st.subheader("📂 Alocação por Tipo")
                df_t = df_ed_inv.groupby("tipo")["valor_efetivo"].sum().reset_index()
                fig_inv_pie = px.pie(df_t, names='tipo', values='valor_efetivo', hole=.4)
                fig_inv_pie.update_traces(textinfo='percent+label', texttemplate='<b>%{label}</b><br><b>%{percent:.1%}</b>', textfont_size=16, insidetextorientation='horizontal')
                st.plotly_chart(fig_inv_pie, use_container_width=True)
            with g2:
                st.subheader("📈 Curva de Crescimento")
                fig_ev = go.Figure()
                fig_ev.add_trace(go.Scatter(y=projs, fill='tozeroy', line=dict(color='#00C805', width=3)))
                fig_ev.add_hline(y=v_meta, line_dash="dash", line_color="red", annotation_text="Meta")
                st.plotly_chart(fig_ev, use_container_width=True)

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
            st.sidebar.success("Investimentos Salvos!")

    # ==========================================
    # ABA 2: FLUXO DE CAIXA (MANUAL + BOTÕES)
    # ==========================================
    elif menu == "💸 Fluxo de Caixa":
        st.title("💸 Controle de Fluxo de Caixa")
        gastos_raw, gastos_sha = get_git_file("gastos.csv")
        df_gastos = pd.read_csv(StringIO(gastos_raw), on_bad_lines='skip') if gastos_raw else pd.DataFrame(columns=["descricao","categoria","tipo_custo","fluxo","ano","mes","valor","status","recorrente"])

        c1, c2, c3 = st.columns([1, 1, 1])
        with c1: ano_sel = st.selectbox("Ano", [2024, 2025, 2026], index=2)
        with c2: mes_sel = st.selectbox("Mês", list(meses_map.keys()), index=datetime.now().month - 1)
        
        df_mes = df_gastos[(df_gastos["ano"] == ano_sel) & (df_gastos["mes"] == mes_sel)].copy()

        def salvar_g_manual(df_s):
            df_s["valor"] = df_s["valor"].abs()
            df_o = df_gastos[~((df_gastos["ano"] == ano_sel) & (df_gastos["mes"] == mes_sel))]
            df_f = pd.concat([df_o, df_s], ignore_index=True)
            save_git_file("gastos.csv", df_f.to_csv(index=False), gastos_sha, f"Save {mes_sel}")
            st.toast("✅ Dados Salvos!")

        with c3:
            st.write(" ")
            st.write(" ")
            if st.button("💾 SALVAR ALTERAÇÕES", key="btn_topo", use_container_width=True):
                salvar_g_manual(st.session_state.editor_caixa)
                st.rerun()

        df_p = df_mes[df_mes["status"] == "✅ Pago"]
        entrou, saiu = df_p[df_p["fluxo"] == "Receita"]["valor"].sum(), df_p[df_p["fluxo"] == "Despesa"]["valor"].sum()
        m1, m2, m3 = st.columns(3)
        m1.metric("Recebido", f"R$ {entrou:,.2f}")
        m2.metric("Saídas Pagas", f"R$ {saiu:,.2f}", delta_color="inverse")
        m3.metric("Saldo Real", f"R$ {entrou - saiu:,.2f}")

        df_ed_caixa = st.data_editor(df_mes, num_rows="dynamic", use_container_width=True, key="editor_caixa",
            column_config={
                "status": st.column_config.SelectboxColumn("Status", options=["✅ Pago", "⏳ Pendente"]),
                "fluxo": st.column_config.SelectboxColumn("Fluxo", options=["Receita", "Despesa"]),
                "categoria": st.column_config.SelectboxColumn("Categoria", options=sorted(["salário", "Investimento", "Contas domésticas", "Cartão de crédito", "Educação", "Obra casa", "Lazer", "Saúde", "Aluguel"])),
                "ano": st.column_config.SelectboxColumn("Ano", options=[2024, 2025, 2026]),
                "mes": st.column_config.SelectboxColumn("Mês", options=list(meses_map.keys()))
            })

        if st.button("💾 SALVAR ALTERAÇÕES", key="btn_baixo", use_container_width=True):
            salvar_g_manual(df_ed_caixa)
            st.rerun()

        st.markdown("---")
        if st.button("🔄 Replicar Recorrentes para Próximo Mês"):
            idx_m = list(meses_map.keys()).index(mes_sel)
            p_m = list(meses_map.keys())[0] if idx_m == 11 else list(meses_map.keys())[idx_m + 1]
            p_a = ano_sel + 1 if idx_m == 11 else ano_sel
            df_rec = df_mes[df_mes["recorrente"] == True].copy()
            if not df_rec.empty:
                df_rec["mes"], df_rec["ano"], df_rec["status"] = p_m, p_a, "⏳ Pendente"
                df_f = pd.concat([df_gastos, df_rec], ignore_index=True).drop_duplicates(subset=["descricao","ano","mes"], keep='last')
                save_git_file("gastos.csv", df_f.to_csv(index=False), gastos_sha, "Replicar")
                st.success(f"Recorrentes copiados para {p_m}!")
                st.rerun()

    # ==========================================
    # ABA 3: DASHBOARD & INSIGHTS (GRÁFICOS AJUSTADOS)
    # ==========================================
    elif menu == "📈 Dashboard & Insights":
        st.title("📈 Performance Financeira")
        gastos_raw, _ = get_git_file("gastos.csv")
        
        if gastos_raw:
            df = pd.read_csv(StringIO(gastos_raw), on_bad_lines='skip')
            df['mes_num'] = df['mes'].map(meses_map)
            df['periodo'] = df['mes'].str[:3] + "/" + df['ano'].astype(str).str[2:]
            df = df.sort_values(['ano', 'mes_num'])

            # --- 1. RECEITAS VS DESPESAS (BARRAS LADO A LADO) ---
            st.subheader("1. Receitas vs Despesas Mensais (Comparativo)")
            df_h = df.groupby(['periodo', 'ano', 'mes_num', 'fluxo'])['valor'].sum().reset_index().sort_values(['ano', 'mes_num'])
            fig_h = px.bar(df_h, x='periodo', y='valor', color='fluxo', barmode='group',
                          color_discrete_map={'Receita': '#00C805', 'Despesa': '#FF4B4B'}, text_auto='.2s')
            fig_h.update_traces(textfont=dict(size=14, weight='bold'), textposition='outside', cliponaxis=False)
            st.plotly_chart(fig_h, use_container_width=True)

            c_g1, c_g2 = st.columns(2)
            with c_g1:
                # --- 2. GRÁFICO DE ROSCA (DONUT) - FONTE GIGANTE SEM CORTES ---
                st.subheader("2. % de Gastos por Categoria")
                df_cat = df[df['fluxo'] == 'Despesa'].groupby('categoria')['valor'].sum().reset_index().sort_values('valor', ascending=False)
                fig_p_cat = px.pie(df_cat, names='categoria', values='valor', hole=.5)
                fig_p_cat.update_traces(
                    textinfo='percent+label', 
                    texttemplate='<b>%{label}</b><br><b>%{percent:.1%}</b>',
                    textfont_size=16, 
                    textposition='outside'
                )
                fig_p_cat.update_layout(showlegend=False, margin=dict(t=80, b=80, l=80, r=80)) 
                st.plotly_chart(fig_p_cat, use_container_width=True)
            
            with c_g2:
                # --- 3. PERFIL DE CUSTOS ---
                st.subheader("3. Fixo vs Variável")
                df_t_c = df[df['fluxo'] == 'Despesa'].groupby('tipo_custo')['valor'].sum().reset_index()
                fig_t = px.bar(df_t_c, x='tipo_custo', y='valor', color='tipo_custo', text_auto='.3s')
                fig_t.update_traces(textfont=dict(size=14, weight='bold'), textposition='outside')
                st.plotly_chart(fig_t, use_container_width=True)

            # --- 4. ACUMULADO HÍBRIDO (RECEITA BARRA / DESPESA LINHA) ---
            st.subheader("4. Fluxo Acumulado: Receita (Barra) vs Despesa (Linha)")
            df_a = df.groupby(['periodo', 'ano', 'mes_num', 'fluxo'])['valor'].sum().reset_index().sort_values(['ano', 'mes_num'])
            df_a['acumulado'] = df_a.groupby('fluxo')['valor'].cumsum()
            
            fig_a = go.Figure()
            df_rec_a = df_a[df_a['fluxo'] == 'Receita']
            fig_a.add_trace(go.Bar(x=df_rec_a['periodo'], y=df_rec_a['acumulado'], name="Acum. Receita", marker_color='rgba(0, 200, 5, 0.4)',
                                   text=[f"<b>R${v/1000:.1f}k</b>" for v in df_rec_a['acumulado']], textposition='auto'))
            
            df_des_a = df_a[df_a['fluxo'] == 'Despesa']
            fig_a.add_trace(go.Scatter(x=df_des_a['periodo'], y=df_des_a['acumulado'], name="Acum. Despesa", mode='lines+markers+text',
                                       line=dict(color='#FF4B4B', width=5), text=[f"<b>R${v/1000:.1f}k</b>" for v in df_des_a['acumulado']], 
                                       textposition="bottom center", textfont=dict(size=15, color='#B22222', weight='bold')))
            
            fig_a.update_layout(yaxis=dict(range=[0, df_a['acumulado'].max() * 1.3]), height=500)
            st.plotly_chart(fig_a, use_container_width=True)

            # --- 5. INSIGHTS DINÂMICOS ---
            st.markdown("---")
            st.subheader("🤖 Insights Gerenciais")
            if st.button("💡 GERAR NOVOS INSIGHTS"):
                tot_r, tot_d = df[df['fluxo']=='Receita']['valor'].sum(), df[df['fluxo']=='Despesa']['valor'].sum()
                taxa = ((tot_r - tot_d)/tot_r * 100) if tot_r > 0 else 0
                max_cat = df_cat.iloc[0]['categoria'] if not df_cat.empty else "N/A"
                pool = [
                    f"✅ Taxa de Poupança Histórica: **{taxa:.1f}%**.",
                    f"🚨 Maior Gasto: A categoria **'{max_cat}'** domina as tuas despesas.",
                    f"💰 Rendimento Médio: Facturas em média **R$ {(tot_r/len(df['periodo'].unique())):,.2f}** mensalmente.",
                    f"📊 Custos Fixos: Representam **{(df_t_c[df_t_c['tipo_custo']=='Fixo']['valor'].sum()/tot_d*100):.1f}%** das saídas."
                ]
                random.shuffle(pool)
                st.info(pool[0])
                st.success(pool[1])
            else:
                st.write("Clica no botão para analisar a tua saúde financeira.")
        else:
            st.warning("Sem dados suficientes.")

    st.sidebar.markdown("---")
    authenticator.logout("Sair", "sidebar")

