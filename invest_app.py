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
passwords = ["12345"] # Altere conforme sua necessidade
authenticator = stauth.Authenticate({"usernames": {usernames[0]: {"name": names[0], "password": passwords[0]}}}, "cookie_invest", "key_invest", 30)
authenticator.login(location="main")

if st.session_state["authentication_status"]:
    st.sidebar.title(f"👋 Olá, {st.session_state['name']}")
    menu = st.sidebar.radio("Navegação Principal", ["📊 Investimentos", "💸 Fluxo de Caixa", "📈 Dashboard & Insights"])
    
    # Ordem dos meses para gráficos e filtros
    meses_map = {"Janeiro":1, "Fevereiro":2, "Março":3, "Abril":4, "Maio":5, "Junho":6, "Julho":7, "Agosto":8, "Setembro":9, "Outubro":10, "Novembro":11, "Dezembro":12}

    # ==========================================
    # ABA 1: INVESTIMENTOS (SISTEMA COMPLETO)
    # ==========================================
    if menu == "📊 Investimentos":
        st.title("📊 Gestão de Patrimônio & Ativos")
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

        st.info(f"💵 **Câmbio Avenue:** R$ {dolar_hoje:.2f} | **Ref:** {data_dolar}")

        with st.expander("📝 Editar Carteira de Ativos", expanded=True):
            df_ed_inv = st.data_editor(df_inv, num_rows="dynamic", use_container_width=True,
                column_config={
                    "valor_atual": st.column_config.NumberColumn("Valor Original", format="%.2f"),
                    "aporte_mensal": st.column_config.NumberColumn("Aporte (R$)", format="%.2f"),
                    "juros_mensal": st.column_config.NumberColumn("Juros (%)", format="%.2f%%"),
                    "origem": st.column_config.SelectboxColumn("Origem", options=["B3", "Avenue", "Outros"])
                })

        # Conversão Automática
        df_ed_inv["valor_efetivo"] = df_ed_inv.apply(lambda r: float(r["valor_atual"]) * dolar_hoje if str(r.get("origem","")).lower().strip() == "avenue" else float(r["valor_atual"]), axis=1)

        if not df_ed_inv.empty:
            total_inv = df_ed_inv["valor_efetivo"].sum()
            
            with st.sidebar:
                st.markdown("---")
                v_meta = st.number_input("Meta de Patrimônio (R$)", value=meta_ini, format="%.2f")
                t_anos = st.slider("Prazo de Projeção (Anos)", 1, 50, value=tempo_ini)

            # Projeção Composta
            meses_proj = t_anos * 12
            projs = [0.0] * (meses_proj + 1)
            for _, r in df_ed_inv.iterrows():
                v, ap, ju = float(r["valor_efetivo"]), float(r.get("aporte_mensal",0)), (float(r.get("juros_mensal",0))/100)
                acum = v
                for m in range(meses_proj+1):
                    if m > 0: acum = (acum * (1 + ju)) + ap
                    projs[m] += acum

            # KPIs de Investimento
            st.markdown("---")
            k1, k2, k3 = st.columns(3)
            k1.metric("Total em Carteira", f"R$ {total_inv:,.2f}")
            k2.metric(f"Proj. em {t_anos} anos", f"R$ {projs[-1]:,.2f}")
            prog = (total_inv / v_meta) * 100 if v_meta > 0 else 0
            k3.metric("Progresso Meta", f"{prog:.1f}%", delta=f"Faltam R$ {v_meta - total_inv:,.2f}", delta_color="inverse")

            # Racional Retrátil
            with st.expander("💱 Racional da Conversão (Avenue → BRL)", expanded=False):
                df_rat = df_ed_inv.copy()
                df_rat["Cotação"] = df_rat["origem"].apply(lambda x: dolar_hoje if str(x).lower().strip()=="avenue" else 1.0)
                st.dataframe(df_rat[["origem", "nome", "valor_atual", "Cotação", "valor_efetivo"]], use_container_width=True)

            # Gráficos
            g1, g2 = st.columns(2)
            with g1:
                st.subheader("📂 Alocação por Tipo")
                df_t = df_ed_inv.groupby("tipo")["valor_efetivo"].sum().reset_index()
                st.plotly_chart(go.Figure(data=[go.Pie(labels=df_t["tipo"], values=df_t["valor_efetivo"], hole=.4)]), use_container_width=True)
            with g2:
                st.subheader("📈 Curva de Crescimento")
                fig_ev = go.Figure()
                fig_ev.add_trace(go.Scatter(y=projs, fill='tozeroy', line=dict(color='#00C805', width=3)))
                fig_ev.add_hline(y=v_meta, line_dash="dash", line_color="red", annotation_text="Meta")
                st.plotly_chart(fig_ev, use_container_width=True)

            # Inteligência de Rebalanceamento
            st.markdown("---")
            st.subheader("⚖️ Sugestão de Rebalanceamento")
            df_bal = df_ed_inv.groupby("tipo")["valor_efetivo"].sum().reset_index()
            cols_b = st.columns(len(df_bal) if not df_bal.empty else 1)
            for i, row in df_bal.iterrows():
                with cols_b[i % len(cols_b)]:
                    st.write(f"**{row['tipo']}**")
                    meta_p = st.number_input(f"Meta %", 0.0, 100.0, 100.0/len(df_bal), key=f"rebal_{row['tipo']}")
                    dif = ((meta_p / 100) * total_inv) - row['valor_efetivo']
                    if dif > 0: st.success(f"Aportar: R$ {dif:,.2f}")
                    else: st.warning(f"Excesso: R$ {abs(dif):,.2f}")

        if st.sidebar.button("💾 SALVAR INVESTIMENTOS", use_container_width=True):
            save_git_file("dados.csv", df_ed_inv[["origem","tipo","nome","valor_atual","aporte_mensal","juros_mensal"]].to_csv(index=False), sha_inv, "Sync")
            save_git_file("metas.csv", pd.DataFrame([{"valor_meta": v_meta, "tempo_anos": t_anos}]).to_csv(index=False), sha_metas, "Sync")
            st.sidebar.success("Investimentos Salvos!")

    # ==========================================
    # ABA 2: FLUXO DE CAIXA (BOTÕES MANUAIS)
    # ==========================================
    elif menu == "💸 Fluxo de Caixa":
        st.title("💸 Fluxo de Caixa e Lançamentos")
        gastos_raw, gastos_sha = get_git_file("gastos.csv")
        
        if gastos_raw:
            try: df_gastos = pd.read_csv(StringIO(gastos_raw), on_bad_lines='skip')
            except: df_gastos = pd.DataFrame(columns=["descricao","categoria","tipo_custo","fluxo","ano","mes","valor","status","recorrente"])
        else: df_gastos = pd.DataFrame(columns=["descricao","categoria","tipo_custo","fluxo","ano","mes","valor","status","recorrente"])

        # Filtros e Botão Superior
        col_f1, col_f2, col_s1 = st.columns([1, 1, 1])
        with col_f1: ano_sel = st.selectbox("Selecione o Ano", [2024, 2025, 2026], index=2)
        with col_f2: mes_sel = st.selectbox("Selecione o Mês", list(meses_map.keys()), index=datetime.now().month - 1)
        
        df_mes = df_gastos[(df_gastos["ano"] == ano_sel) & (df_gastos["mes"] == mes_sel)].copy()

        # Função de salvamento manual
        def salvar_gastos_final(dataframe_ed):
            dataframe_ed["valor"] = dataframe_ed["valor"].abs()
            df_outros = df_gastos[~((df_gastos["ano"] == ano_sel) & (df_gastos["mes"] == mes_sel))]
            df_final = pd.concat([df_outros, dataframe_ed], ignore_index=True)
            res = save_git_file("gastos.csv", df_final.to_csv(index=False), gastos_sha, f"Save {mes_sel}")
            if res.status_code in [200, 201]: st.toast("✅ Salvo com sucesso!")
            else: st.error("Erro ao salvar no GitHub.")

        with col_s1:
            st.write(" ") # Espaçamento para alinhar
            st.write(" ")
            if st.button("💾 SALVAR ALTERAÇÕES", key="btn_topo", use_container_width=True):
                salvar_gastos_final(st.session_state.editor_caixa)
                st.rerun()

        # Resumo do Mês Selecionado (Só o que está pago)
        df_p = df_mes[df_mes["status"] == "✅ Pago"]
        receita = df_p[df_p["fluxo"] == "Receita"]["valor"].sum()
        despesa = df_p[df_p["fluxo"] == "Despesa"]["valor"].sum()
        m1, m2, m3 = st.columns(3)
        m1.metric("Entradas (Pagas)", f"R$ {receita:,.2f}")
        m2.metric("Saídas (Pagas)", f"R$ {despesa:,.2f}", delta_color="inverse")
        m3.metric("Saldo Real em Conta", f"R$ {receita - despesa:,.2f}")

        st.markdown("---")
        
        # Tabela com Dropdowns
        df_ed_caixa = st.data_editor(df_mes, num_rows="dynamic", use_container_width=True,
            column_config={
                "valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f"),
                "status": st.column_config.SelectboxColumn("Status", options=["✅ Pago", "⏳ Pendente"]),
                "fluxo": st.column_config.SelectboxColumn("Fluxo", options=["Receita", "Despesa"]),
                "categoria": st.column_config.SelectboxColumn("Categoria", options=sorted(["salário", "Investimento", "Contas domésticas", "Cartão de crédito", "Educação", "Obra casa", "Lazer", "Saúde", "Aluguel"])),
                "tipo_custo": st.column_config.SelectboxColumn("Tipo de Custo", options=["Fixo", "Variável"]),
                "ano": st.column_config.SelectboxColumn("Ano", options=[2024, 2025, 2026]),
                "mes": st.column_config.SelectboxColumn("Mês", options=list(meses_map.keys()))
            }, key="editor_caixa")

        # Botão Inferior de Salvamento
        if st.button("💾 SALVAR ALTERAÇÕES", key="btn_baixo", use_container_width=True):
            salvar_gastos_final(df_ed_caixa)
            st.rerun()

        st.markdown("---")
        if st.button("🔄 Replicar Recorrentes para o Mês Seguinte"):
            idx_mes = list(meses_map.keys()).index(mes_sel)
            prox_m = list(meses_map.keys())[0] if idx_mes == 11 else list(meses_map.keys())[idx_mes + 1]
            prox_a = ano_sel + 1 if idx_mes == 11 else ano_sel
            df_recorrentes = df_mes[df_mes["recorrente"] == True].copy()
            if not df_recorrentes.empty:
                df_recorrentes["mes"], df_recorrentes["ano"], df_recorrentes["status"] = prox_m, prox_a, "⏳ Pendente"
                df_novo_total = pd.concat([df_gastos, df_recorrentes], ignore_index=True).drop_duplicates(subset=["descricao","ano","mes"], keep='last')
                save_git_file("gastos.csv", df_novo_total.to_csv(index=False), gastos_sha, f"Replicate to {prox_m}")
                st.success(f"Contas fixas copiadas para {prox_m}!")
                st.rerun()

    # ==========================================
    # ABA 3: DASHBOARD & INSIGHTS (GRÁFICOS)
    # ==========================================
    elif menu == "📈 Dashboard & Insights":
        st.title("📈 Inteligência Financeira e Histórico")
        gastos_raw, _ = get_git_file("gastos.csv")
        
        if gastos_raw:
            df = pd.read_csv(StringIO(gastos_raw), on_bad_lines='skip')
            df['mes_num'] = df['mes'].map(meses_map)
            df['periodo'] = df['mes'].str[:3] + "/" + df['ano'].astype(str).str[2:]
            df = df.sort_values(['ano', 'mes_num'])

            # 1. RECEITA E DESPESA AO LONGO DO TEMPO
            st.subheader("1. Linha do Tempo: Faturamento vs Gastos")
            df_hist = df.groupby(['periodo', 'ano', 'mes_num', 'fluxo'])['valor'].sum().reset_index().sort_values(['ano', 'mes_num'])
            fig_hist = px.bar(df_hist, x='periodo', y='valor', color='fluxo', barmode='group',
                             color_discrete_map={'Receita': '#00C805', 'Despesa': '#FF4B4B'})
            st.plotly_chart(fig_hist, use_container_width=True)

            c_g1, c_g2 = st.columns(2)
            with c_g1:
                # 2. TOTAL DESPESA POR CATEGORIA
                st.subheader("2. Gastos por Categoria")
                df_cat = df[df['fluxo'] == 'Despesa'].groupby('categoria')['valor'].sum().reset_index().sort_values('valor', ascending=False)
                st.plotly_chart(px.pie(df_cat, names='categoria', values='valor', hole=.4), use_container_width=True)
            with c_g2:
                # 3. TOTAL POR TIPO DE CUSTO
                st.subheader("3. Perfil de Saídas (Fixo vs Variável)")
                df_tipo_c = df[df['fluxo'] == 'Despesa'].groupby('tipo_custo')['valor'].sum().reset_index()
                st.plotly_chart(px.bar(df_tipo_c, x='tipo_custo', y='valor', color='tipo_custo'), use_container_width=True)

            # 4. ACUMULADO
            st.subheader("4. Evolução do Patrimônio Acumulado (Fluxo)")
            df_acu = df.groupby(['periodo', 'ano', 'mes_num', 'fluxo'])['valor'].sum().reset_index().sort_values(['ano', 'mes_num'])
            df_acu['acumulado'] = df_acu.groupby('fluxo')['valor'].cumsum()
            fig_acu = go.Figure()
            for f in ['Receita', 'Despesa']:
                df_f = df_acu[df_acu['fluxo'] == f]
                fig_acu.add_trace(go.Scatter(x=df_f['periodo'], y=df_f['acumulado'], name=f"Total {f}", line=dict(width=4, color='#00C805' if f=='Receita' else '#FF4B4B')))
            st.plotly_chart(fig_acu, use_container_width=True)

            # 5. INSIGHTS AUTOMÁTICOS
            st.markdown("---")
            st.subheader("🤖 Insights Gerenciais")
            if st.button("💡 GERAR NOVOS INSIGHTS"):
                tot_r = df[df['fluxo']=='Receita']['valor'].sum()
                tot_d = df[df['fluxo']=='Despesa']['valor'].sum()
                taxa = ((tot_r - tot_d)/tot_r * 100) if tot_r > 0 else 0
                max_cat = df_cat.iloc[0]['categoria'] if not df_cat.empty else "N/A"
                
                frases = [
                    f"✅ Sua Taxa de Poupança acumulada é de **{taxa:.1f}%**. O mercado recomenda 20%.",
                    f"🚨 Olho aberto: A categoria **'{max_cat}'** é sua maior despesa histórica.",
                    f"💰 Seu faturamento médio mensal é de **R$ {(tot_r/len(df['periodo'].unique())):,.2f}**.",
                    f"📉 Seus custos fixos representam **{(df_tipo_c[df_tipo_c['tipo_custo']=='Fixo']['valor'].sum()/tot_d*100):.1f}%** das saídas totais."
                ]
                st.info(random.choice(frases))
                st.success(random.choice(frases))
        else:
            st.warning("Sem dados suficientes para gerar o Dashboard.")

    st.sidebar.markdown("---")
    authenticator.logout("Sair do Sistema", "sidebar")

elif st.session_state["authentication_status"] is False:
    st.error("Login ou senha incorretos.")
