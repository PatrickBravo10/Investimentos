import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import streamlit_authenticator as stauth
import requests
import base64
import json
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

# --- 3. LÓGICA DE AUTO-SAVE REFINADA (REGRAS DO PATRICK) ---
def trigger_auto_save():
    # Só executa se o editor e os dados temporários existirem na sessão
    if "editor_gastos_key" in st.session_state and "df_temp_gastos" in st.session_state:
        edits = st.session_state["editor_gastos_key"]
        df_atual = st.session_state["df_temp_gastos"]
        
        # Regra: Verificar se houve alteração especificamente na coluna "status" ou se algo foi deletado
        status_alterado = False
        # Verifica edições em linhas existentes
        for row_id, changes in edits["edited_rows"].items():
            if "status" in changes: status_alterado = True
        # Verifica se o status foi definido em novas linhas
        for row in edits["added_rows"]:
            if "status" in row: status_alterado = True
        
        deletado = len(edits["deleted_rows"]) > 0
        
        # Só dispara o upload se o Status mudou (clique em Pago/Pendente) ou se apagou linha
        if status_alterado or deletado:
            # Validação de campos obrigatórios: Descrição, Categoria e Valor
            # Filtramos apenas as linhas que estão sendo editadas/vistas
            is_complete = not df_atual[['descricao', 'categoria', 'valor']].isna().any().any()
            
            if is_complete or deletado:
                gastos_raw, gastos_sha = get_git_file("gastos.csv")
                if gastos_raw:
                    df_base = pd.read_csv(StringIO(gastos_raw), on_bad_lines='skip')
                    # Remove os dados do mês/ano que está no ecrã para evitar duplicados
                    df_outros = df_base[~((df_base["ano"] == st.session_state.ano_ativo) & 
                                         (df_base["mes"] == st.session_state.mes_ativo))]
                    
                    df_atual["valor"] = df_atual["valor"].abs() # Garante valor positivo
                    df_final = pd.concat([df_outros, df_atual], ignore_index=True)
                    
                    save_git_file("gastos.csv", df_final.to_csv(index=False), gastos_sha, "Auto-save: Status Triggered")

# --- 4. AUTENTICAÇÃO ---
names = ["Patrick Bravo"]
usernames = ["admin"]
passwords = ["12345"]
authenticator = stauth.Authenticate({"usernames": {usernames[0]: {"name": names[0], "password": passwords[0]}}}, "cookie_invest", "key_invest", 30)
authenticator.login(location="main")

if st.session_state["authentication_status"]:
    st.sidebar.title(f"Olá, {st.session_state['name']}")
    menu = st.sidebar.radio("Navegação", ["📊 Investimentos", "💸 Fluxo de Caixa"])
    
    # --- ABA 1: INVESTIMENTOS (VERSÃO COMPLETA RESTAURADA) ---
    if menu == "📊 Investimentos":
        st.title("📊 Gestão de Investimentos & Património")
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

        st.info(f"💵 **Dólar Avenue:** R$ {dolar_hoje:.2f} | **Atualização:** {data_dolar}")

        with st.expander("📝 Editar Carteira de Ativos", expanded=True):
            df_ed_inv = st.data_editor(df_inv, num_rows="dynamic", use_container_width=True,
                column_config={
                    "valor_atual": st.column_config.NumberColumn("Valor Unidade", format="%.2f"),
                    "aporte_mensal": st.column_config.NumberColumn("Aporte (R$)", format="%.2f"),
                    "juros_mensal": st.column_config.NumberColumn("Juros (%)", format="%.2f%%"),
                })

        # Conversão de Moeda
        df_ed_inv["valor_efetivo"] = df_ed_inv.apply(lambda r: float(r["valor_atual"]) * dolar_hoje if str(r.get("origem","")).lower().strip() == "avenue" else float(r["valor_atual"]), axis=1)

        if not df_ed_inv.empty:
            total_inv = df_ed_inv["valor_efetivo"].sum()
            
            with st.sidebar:
                st.markdown("---")
                v_meta = st.number_input("Sua Meta (R$)", value=meta_ini, format="%.2f")
                t_anos = st.slider("Anos de Projeção", 1, 50, value=tempo_ini)

            # Cálculo de Projeção Futurista
            meses = t_anos * 12
            projs = [0.0] * (meses + 1)
            for _, r in df_ed_inv.iterrows():
                v, ap, ju = float(r["valor_efetivo"]), float(r.get("aporte_mensal",0)), (float(r.get("juros_mensal",0))/100)
                acum = v
                for m in range(meses+1):
                    if m > 0: acum = (acum * (1 + ju)) + ap
                    projs[m] += acum

            # KPIs de Topo
            st.markdown("---")
            k1, k2, k3 = st.columns(3)
            k1.metric("Património Hoje", f"R$ {total_inv:,.2f}")
            k2.metric(f"Proj. ({t_anos} anos)", f"R$ {projs[-1]:,.2f}")
            prog = (total_inv / v_meta) * 100 if v_meta > 0 else 0
            k3.metric("Meta", f"{prog:.1f}%", delta=f"Faltam R$ {v_meta - total_inv:,.2f}", delta_color="inverse")

            # RACIONAL CAMBIAL RETRÁTIL
            with st.expander("💱 Racional da Conversão Cambial (Avenue vs B3)", expanded=False):
                df_rat = df_ed_inv.copy()
                df_rat["Cotação"] = df_rat["origem"].apply(lambda x: dolar_hoje if str(x).lower().strip()=="avenue" else 1.0)
                st.dataframe(df_rat[["origem", "nome", "valor_atual", "Cotação", "valor_efetivo"]].rename(columns={"valor_atual": "Valor Original", "valor_efetivo": "Total em R$"}), use_container_width=True)

            # GRÁFICOS
            g1, g2 = st.columns(2)
            with g1:
                st.subheader("📂 Alocação por Tipo")
                df_t = df_ed_inv.groupby("tipo")["valor_efetivo"].sum().reset_index()
                st.plotly_chart(go.Figure(data=[go.Pie(labels=df_t["tipo"], values=df_t["valor_efetivo"], hole=.4)]), use_container_width=True)
            with g2:
                st.subheader("📈 Curva de Crescimento")
                fig_ev = go.Figure()
                fig_ev.add_trace(go.Scatter(y=projs, fill='tozeroy', line=dict(color='#00C805', width=3), name="Património"))
                fig_ev.add_hline(y=v_meta, line_dash="dash", line_color="red", annotation_text="Meta")
                st.plotly_chart(fig_ev, use_container_width=True)

            # REBALANCEAMENTO ESTRATÉGICO
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

        if st.sidebar.button("💾 SALVAR INVESTIMENTOS"):
            save_git_file("dados.csv", df_ed_inv[["origem","tipo","nome","valor_atual","aporte_mensal","juros_mensal"]].to_csv(index=False), sha_inv, "Update Invest")
            save_git_file("metas.csv", pd.DataFrame([{"valor_meta": v_meta, "tempo_anos": t_anos}]).to_csv(index=False), sha_metas, "Update Metas")
            st.sidebar.success("Investimentos Sincronizados!")

    # --- ABA 2: FLUXO DE CAIXA (REGRAS DE SALVAMENTO AUTOMÁTICO) ---
    elif menu == "💸 Fluxo de Caixa":
        st.title("💸 Controle de Fluxo de Caixa")
        gastos_raw, gastos_sha = get_git_file("gastos.csv")
        if gastos_raw:
            try: df_gastos = pd.read_csv(StringIO(gastos_raw), on_bad_lines='skip')
            except: df_gastos = pd.DataFrame(columns=["descricao","categoria","tipo_custo","fluxo","ano","mes","valor","status","recorrente"])
        else: df_gastos = pd.DataFrame(columns=["descricao","categoria","tipo_custo","fluxo","ano","mes","valor","status","recorrente"])

        meses_list = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        c1, c2 = st.columns(2)
        with c1: st.session_state.ano_ativo = st.selectbox("Ano", [2024, 2025, 2026], index=2)
        with c2: st.session_state.mes_ativo = st.selectbox("Mês", meses_list, index=datetime.now().month - 1)

        df_mes = df_gastos[(df_gastos["ano"] == st.session_state.ano_ativo) & 
                          (df_gastos["mes"] == st.session_state.mes_ativo)].copy()
        
        # Dash de Totais (Só ✅ Pago)
        df_p = df_mes[df_mes["status"] == "✅ Pago"]
        entrou = df_p[df_p["fluxo"] == "Receita"]["valor"].sum()
        saiu = df_p[df_p["fluxo"] == "Despesa"]["valor"].sum()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Recebido", f"R$ {entrou:,.2f}")
        m2.metric("Despesas Pagas", f"R$ {saiu:,.2f}", delta_color="inverse")
        m3.metric("Saldo Real", f"R$ {entrou - saiu:,.2f}")

        st.markdown("---")
        st.caption("🔒 **Auto-Save Inteligente**: Salva automaticamente ao clicar em **✅ Pago** ou **⏳ Pendente** (se a linha estiver preenchida).")
        
        # EDITOR COM DROPDOWNS E AUTO-SAVE CONDICIONAL
        df_ed_gastos = st.data_editor(
            df_mes, 
            num_rows="dynamic", 
            use_container_width=True,
            on_change=trigger_auto_save,
            key="editor_gastos_key",
            column_config={
                "valor": st.column_config.NumberColumn("Valor", format="%.2f"),
                "status": st.column_config.SelectboxColumn("Status", options=["✅ Pago", "⏳ Pendente"]),
                "fluxo": st.column_config.SelectboxColumn("Fluxo", options=["Receita", "Despesa"]),
                "categoria": st.column_config.SelectboxColumn("Categoria", options=sorted(["salário", "Investimento", "Contas domésticas", "Cartão de crédito", "Educação", "Obra casa", "Lazer", "Saúde", "Aluguel"])),
                "tipo_custo": st.column_config.SelectboxColumn("Tipo", options=["Fixo", "Variável"]),
                "ano": st.column_config.SelectboxColumn("Ano", options=[2024, 2025, 2026]),
                "mes": st.column_config.SelectboxColumn("Mês", options=meses_list),
                "recorrente": st.column_config.CheckboxColumn("Recorrente?")
            }
        )
        st.session_state["df_temp_gastos"] = df_ed_gastos

        # Replicação de Recorrentes
        if st.button("🔄 Replicar Recorrentes para o Mês Seguinte"):
            idx = meses_list.index(st.session_state.mes_ativo)
            p_m = meses_list[0] if idx == 11 else meses_list[idx + 1]
            p_a = st.session_state.ano_ativo + 1 if idx == 11 else st.session_state.ano_ativo
            df_rec = df_mes[df_mes["recorrente"] == True].copy()
            if not df_rec.empty:
                df_rec["mes"], df_rec["ano"], df_rec["status"] = p_m, p_a, "⏳ Pendente"
                df_f_g = pd.concat([df_gastos, df_rec], ignore_index=True).drop_duplicates(subset=["descricao","ano","mes"], keep='last')
                save_git_file("gastos.csv", df_f_g.to_csv(index=False), gastos_sha, f"Replicate to {p_m}")
                st.success(f"Copiado para {p_m}!")
                st.rerun()

    authenticator.logout("Sair", "sidebar")

elif st.session_state["authentication_status"] is False:
    st.error("Login incorreto.")
