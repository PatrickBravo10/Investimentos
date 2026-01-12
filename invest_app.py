import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import streamlit_authenticator as stauth
from sqlalchemy import text

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestor Financeiro PRO", layout="wide")

# Conexão com Supabase SQL
conn = st.connection("postgresql", type="sql")

# LOGIN CONFIG
names = ["Usuario Teste"]
usernames = ["admin"]
passwords = ["12345"]

authenticator = stauth.Authenticate(
    {"usernames": {usernames[0]: {"name": names[0], "password": passwords[0]}}},
    "cookie_invest", "key_invest", cookie_expiry_days=30
)

authenticator.login(location="main")

if st.session_state["authentication_status"]:
    
    # 1. CARREGAR DADOS
    try:
        df_ativos = conn.query("SELECT tipo, nome, valor_atual, aporte_mensal, juros_mensal FROM ativos", ttl=0)
        df_config = conn.query("SELECT valor_meta, tempo_anos FROM config WHERE id = 1", ttl=0)
        
        if not df_config.empty:
            meta_inicial = float(df_config["valor_meta"].iloc[0])
            tempo_inicial = int(df_config["tempo_anos"].iloc[0])
        else:
            meta_inicial, tempo_inicial = 100000.0, 10
    except Exception:
        df_ativos = pd.DataFrame(columns=["tipo", "nome", "valor_atual", "aporte_mensal", "juros_mensal"])
        meta_inicial, tempo_inicial = 100000.0, 10

    with st.sidebar:
        st.header("🎯 Meta Principal")
        valor_meta = st.number_input("Objetivo Final (R$)", min_value=1.0, value=meta_inicial)
        tempo_anos = st.slider("Prazo (Anos)", 1, 40, value=tempo_inicial)
        
        st.markdown("---")
        if st.button("💾 Salvar no Banco SQL"):
            try:
                with conn.session as s:
                    # Limpa e atualiza ativos
                    s.execute(text("DELETE FROM ativos"))
                    for _, row in df_ativos.iterrows():
                        s.execute(
                            text("INSERT INTO ativos (tipo, nome, valor_atual, aporte_mensal, juros_mensal) VALUES (:t, :n, :v, :a, :j)"),
                            params=dict(t=row.tipo, n=row.nome, v=row.valor_atual, a=row.aporte_mensal, j=row.juros_mensal)
                        )
                    # Atualiza meta (id=1 sempre)
                    s.execute(
                        text("INSERT INTO config (id, valor_meta, tempo_anos) VALUES (1, :m, :t) ON CONFLICT (id) DO UPDATE SET valor_meta = EXCLUDED.valor_meta, tempo_anos = EXCLUDED.tempo_anos"),
                        params=dict(m=valor_meta, t=tempo_anos)
                    )
                    s.commit()
                st.success("Dados salvos com sucesso!")
                st.balloons()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")
        
        st.markdown("---")
        authenticator.logout("Sair", "sidebar")

    st.title("📊 Gestor Financeiro (PostgreSQL)")

    # 2. EDITOR DE TABELA
    st.subheader("📝 Seus Investimentos")
    df_ativos = st.data_editor(df_ativos, num_rows="dynamic", use_container_width=True)

    # --- 3. CÁLCULOS ---
    if not df_ativos.empty:
        # Garantir que são números e limpar nulos
        for col in ["valor_atual", "aporte_mensal", "juros_mensal"]:
            df_ativos[col] = pd.to_numeric(df_ativos[col], errors='coerce').fillna(0)

        total_atual = df_ativos["valor_atual"].sum()
        meses = tempo_anos * 12
        evolucao_total = [0.0] * (meses + 1)
        
        for _, row in df_ativos.iterrows():
            v, a, j = row["valor_atual"], row["aporte_mensal"], (row["juros_mensal"] / 100)
            val_ant = v
            for m in range(meses + 1):
                if m == 0: val_m = v
                else: val_m = (val_ant * (1 + j)) + a
                evolucao_total[m] += val_m
                val_ant = val_m

        # --- 4. DASHBOARD ---
        st.markdown("---")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Hoje", f"R$ {total_atual:,.2f}")
        m2.metric(f"Em {tempo_anos} anos", f"R$ {evolucao_total[-1]:,.2f}")
        prog = (total_atual/valor_meta)*100 if valor_meta > 0 else 0
        m3.metric("Progresso", f"{prog:.1f}%")
        
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(go.Figure(data=[go.Pie(labels=df_ativos["nome"], values=df_ativos["valor_atual"], hole=.4)]), use_container_width=True)
        with col2:
            fig_evol = go.Figure()
            fig_evol.add_trace(go.Scatter(y=evolucao_total, line=dict(color='#00ff00', width=3), name="Evolução"))
            fig_evol.add_hline(y=valor_meta, line_dash="dash", line_color="red", annotation_text="Sua Meta")
            fig_evol.update_layout(xaxis_title="Meses", yaxis_title="R$")
            st.plotly_chart(fig_evol, use_container_width=True)

elif st.session_state["authentication_status"] is False:
    st.error("Erro de login")
elif st.session_state["authentication_status"] is None:
    st.warning("Insira usuário e senha")
