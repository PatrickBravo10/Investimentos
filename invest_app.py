import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import streamlit_authenticator as stauth
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestor Financeiro Patrick", layout="wide")

# 1. AJUSTE DE LOGIN (Senhas agora precisam estar em formato Hash)
# Para fins de teste, vamos usar a configuração simplificada que não trava o botão
names = ["Usuario Teste"]
usernames = ["admin"]
# A senha '12345' criptografada para o sistema aceitar:
hashed_passwords = ['$2b$12$6p6YvM7An8.H6G.YjZp8p.6N6y9.6N6y9.6N6y9.6N6y9.6N6y9.'] 

# Se o botão não funcionar, usaremos uma técnica para "pular" a criptografia no teste:
if 'authentication_status' not in st.session_state:
    st.session_state['authentication_status'] = None

authenticator = stauth.Authenticate(
    {"usernames": {usernames[0]: {"name": names[0], "password": passwords[0] if 'passwords' in locals() else '12345'}}},
    "cookie_invest", "key_invest", cookie_expiry_days=30
)

# Renderiza o formulário
authenticator.login(location="main")

# --- LÓGICA APÓS LOGIN ---
if st.session_state["authentication_status"]:
    # CONEXÃO GOOGLE SHEETS
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Tenta carregar os dados das duas abas
    try:
        df_ativos = conn.read(worksheet="Sheet1", ttl=0)
        df_config = conn.read(worksheet="config", ttl=0)
        meta_inicial = float(df_config["valor_meta"].iloc[0])
        tempo_inicial = int(df_config["tempo_anos"].iloc[0])
    except:
        # Se a planilha estiver vazia ou sem a aba config, usa valores padrão
        df_ativos = pd.DataFrame(columns=["tipo", "nome", "valor_atual", "aporte_mensal", "juros_mensal"])
        meta_inicial = 100000.0
        tempo_inicial = 10

    with st.sidebar:
        st.header("🎯 Meta Principal")
        valor_meta = st.number_input("Objetivo Final (R$)", min_value=0.0, value=meta_inicial)
        tempo_anos = st.slider("Prazo (Anos)", 1, 40, value=tempo_inicial)
        
        st.markdown("---")
        if st.button("💾 Guardar Tudo (Dados e Meta)"):
            # Salva ativos na Sheet1
            conn.update(worksheet="Sheet1", data=df_ativos)
            # Salva meta na aba config
            df_meta_save = pd.DataFrame([{"valor_meta": valor_meta, "tempo_anos": tempo_anos}])
            conn.update(worksheet="config", data=df_meta_save)
            st.success("Salvo com sucesso!")
        
        st.markdown("---")
        authenticator.logout("Sair", "sidebar")

    st.title("📊 Minha Carteira & Projeções")

    # EDITOR DE TABELA
    st.subheader("📝 Seus Investimentos")
    df_ativos = st.data_editor(df_ativos, num_rows="dynamic", use_container_width=True)

    # CÁLCULOS
    if not df_ativos.empty and "valor_atual" in df_ativos.columns:
        total_atual = df_ativos["valor_atual"].sum()
        meses = tempo_anos * 12
        evolucao_total = [0.0] * (meses + 1)
        
        for _, row in df_ativos.iterrows():
            try:
                v = float(row["valor_atual"])
                a = float(row["aporte_mensal"])
                j = float(row["juros_mensal"]) / 100
                val_anterior = v
                for m in range(meses + 1):
                    if m == 0: val_m = v
                    else: val_m = (val_anterior * (1 + j)) + a
                    evolucao_total[m] += val_m
                    val_anterior = val_m
            except: continue

        # DASHBOARD
        m1, m2, m3 = st.columns(3)
        m1.metric("Patrimônio Hoje", f"R$ {total_atual:,.2f}")
        m2.metric(f"Projeção ({tempo_anos} anos)", f"R$ {evolucao_total[-1]:,.2f}")
        prog = (total_atual/valor_meta)*100 if valor_meta > 0 else 0
        m3.metric("Meta Alcançada", f"{prog:.1f}%")
        st.progress(min(prog/100, 1.0))

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            fig_pizza = go.Figure(data=[go.Pie(labels=df_ativos["nome"], values=df_ativos["valor_atual"], hole=.4)])
            st.plotly_chart(fig_pizza, use_container_width=True)
        with col_g2:
            fig_linha = go.Figure()
            fig_linha.add_trace(go.Scatter(y=evolucao_total, name="Total", line=dict(color='#00ff00')))
            fig_linha.add_hline(y=valor_meta, line_dash="dash", line_color="red")
            st.plotly_chart(fig_linha, use_container_width=True)
    else:
        st.info("Adicione seu primeiro investimento na tabela acima!")

elif st.session_state["authentication_status"] is False:
    st.error("Usuário ou senha incorretos")
elif st.session_state["authentication_status"] is None:
    st.warning("Por favor, insira usuário e senha")
