import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import streamlit_authenticator as stauth
import sqlite3

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
def conectar_db():
    conn = sqlite3.connect('investimentos.db', check_same_thread=False)
    return conn

def criar_tabela():
    conn = conectar_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS ativos 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     tipo TEXT, nome TEXT, valor_atual REAL, 
                     aporte_mensal REAL, juros_mensal REAL)''')
    conn.commit()

def salvar_dados(df):
    conn = conectar_db()
    conn.execute("DELETE FROM ativos") # Limpa para sobrescrever
    df.to_sql('ativos', conn, if_exists='append', index=False)
    conn.commit()

def carregar_dados():
    conn = conectar_db()
    return pd.read_sql('SELECT tipo, nome, valor_atual, aporte_mensal, juros_mensal FROM ativos', conn)

# --- INICIALIZAÇÃO ---
st.set_page_config(page_title="Gestor de Investimentos", layout="wide")
criar_tabela()

# Login (Mantenha o padrão)
names = ["Usuario Teste"]
usernames = ["admin"]
passwords = ["12345"]
authenticator = stauth.Authenticate(
    {"usernames": {usernames[0]: {"name": names[0], "password": passwords[0]}}},
    "cookie_invest", "key_invest", cookie_expiry_days=30
)
authenticator.login(location="main")

if st.session_state["authentication_status"]:
    with st.sidebar:
        st.header("🎯 Meta Principal")
        valor_meta = st.number_input("Objetivo Final (R$)", min_value=0.0, value=100000.0)
        tempo_anos = st.slider("Prazo (Anos)", 1, 40, 10)
        st.markdown("---")
        authenticator.logout("Sair", "sidebar")

    st.title("🏦 Minha Carteira Inteligente")

    # Carregar dados do banco ou criar iniciais
    if 'df_temp' not in st.session_state:
        df_db = carregar_dados()
        if df_db.empty:
            st.session_state.df_temp = pd.DataFrame([{
                "tipo": "Ações", "nome": "Exemplo", "valor_atual": 1000.0, 
                "aporte_mensal": 100.0, "juros_mensal": 1.0
            }])
        else:
            st.session_state.df_temp = df_db

    st.subheader("📝 Gerenciar Ativos")
    st.caption("Dica: Para EXCLUIR, selecione a linha no canto esquerdo e aperte 'Delete' no teclado.")
    
    # Editor de tabela
    df_editado = st.data_editor(
        st.session_state.df_temp,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "valor_atual": st.column_config.NumberColumn("Valor Atual (R$)", format="R$ %.2f"),
            "aporte_mensal": st.column_config.NumberColumn("Aporte Mensal (R$)", format="R$ %.2f"),
            "juros_mensal": st.column_config.NumberColumn("Juros Mensal (%)", format="%.2f%%"),
        }
    )

    if st.button("💾 Salvar Alterações"):
        salvar_dados(df_editado)
        st.session_state.df_temp = df_editado
        st.success("Dados salvos com sucesso!")

    # --- CÁLCULOS DE PROJEÇÃO INDIVIDUAL ---
    total_atual = df_editado["valor_atual"].sum()
    meses = tempo_anos * 12
    
    # Lista para o gráfico de evolução
    evolucao_total = [0.0] * (meses + 1)
    
    for _, row in df_editado.iterrows():
        v = row["valor_atual"]
        a = row["aporte_mensal"]
        j = row["juros_mensal"] / 100
        
        for m in range(meses + 1):
            if m == 0:
                valor_m = v
            else:
                # Fórmula: Capital anterior * juros + novo aporte
                valor_m = (evolucao_individual_anterior * (1 + j)) + a
            
            evolucao_total[m] += valor_m
            evolucao_individual_anterior = valor_m

    projecao_final = evolucao_total[-1]

    # --- DASHBOARD ---
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("Patrimônio Hoje", f"R$ {total_atual:,.2f}")
    c2.metric(f"Projeção ({tempo_anos} anos)", f"R$ {projecao_final:,.2f}")
    c3.metric("Meta Alcançada", f"{(total_atual/valor_meta)*100:.1f}%")
    st.progress(min(total_atual / valor_meta, 1.0))

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.subheader("🍕 Distribuição Atual")
        fig_pizza = go.Figure(data=[go.Pie(labels=df_editado["nome"], values=df_editado["valor_atual"], hole=.4)])
        st.plotly_chart(fig_pizza, use_container_width=True)

    with col_g2:
        st.subheader("📈 Crescimento com Aportes")
        fig_linha = go.Figure()
        fig_linha.add_trace(go.Scatter(y=evolucao_total, name="Evolução Total", line=dict(color='#00ff00')))
        fig_linha.add_hline(y=valor_meta, line_dash="dash", line_color="red")
        st.plotly_chart(fig_linha, use_container_width=True)

elif st.session_state["authentication_status"] is False:
    st.error("Usuário/Senha incorretos")
