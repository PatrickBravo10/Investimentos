import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import streamlit_authenticator as stauth

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Meu Gestor de Investimentos", layout="wide")

# Login (Mantenha o padrão que funcionou)
names = ["Usuario Teste"]
usernames = ["bravo"]
passwords = ["12345"]

authenticator = stauth.Authenticate(
    {"usernames": {usernames[0]: {"name": names[0], "password": passwords[0]}}},
    "cookie_invest", "key_invest", cookie_expiry_days=30
)

authenticator.login(location="main")

if st.session_state["authentication_status"] is False:
    st.error("Usuário ou senha incorretos")
elif st.session_state["authentication_status"] is None:
    st.warning("Por favor, insira usuário e senha")
else:
    # --- APP PRINCIPAL ---
    with st.sidebar:
        st.header("🎯 Meta Principal")
        valor_meta = st.number_input("Objetivo Final (R$)", min_value=0.0, value=100000.0)
        tempo_anos = st.slider("Prazo para a Meta (Anos)", 1, 40, 10)
        st.markdown("---")
        authenticator.logout("Sair", "sidebar")

    st.title("🏦 Minha Carteira & Metas")

    # --- SEÇÃO: CADASTRO DE INVESTIMENTOS ---
    st.subheader("📝 Meus Investimentos Atuais")
    st.info("Adicione abaixo seus ativos, o valor que tem hoje e a taxa de juros mensal esperada.")

    # Criando uma tabela editável para os ativos
    if 'ativos_df' not in st.session_state:
        # Dados iniciais de exemplo
        data = {
            "Tipo": ["Fundo Imobiliário", "Ações Brasil", "Internacional"],
            "Nome do Ativo": ["HGLG11", "PETR4", "Apple"],
            "Valor Atual (R$)": [5000.0, 3000.0, 2000.0],
            "Juros Mensal (%)": [0.8, 1.0, 0.7]
        }
        st.session_state.ativos_df = pd.DataFrame(data)

    # Editor de tabela (permite adicionar e excluir linhas)
    df_editado = st.data_editor(
        st.session_state.ativos_df, 
        num_rows="dynamic", 
        use_container_width=True,
        column_config={
            "Valor Atual (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Juros Mensal (%)": st.column_config.NumberColumn(format="%.2f%%"),
        }
    )
    st.session_state.ativos_df = df_editado

    # --- CÁLCULOS ---
    total_atual = df_editado["Valor Atual (R$)"].sum()
    
    # Cálculo da projeção baseada na média ponderada das taxas
    # (Ou poderíamos calcular cada um individualmente, aqui faremos a média para o gráfico)
    taxa_media_mensal = (df_editado["Valor Atual (R$)"] * (df_editado["Juros Mensal (%)"] / 100)).sum() / total_atual if total_atual > 0 else 0
    
    meses = tempo_anos * 12
    projecao_final = total_atual * ((1 + taxa_media_mensal) ** meses)

    # --- DASHBOARD ---
    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    
    m1.metric("Patrimônio Total Hoje", f"R$ {total_atual:,.2f}")
    m2.metric("Projeção em {0} anos".format(tempo_anos), f"R$ {projecao_final:,.2f}")
    
    progresso_meta = min(total_atual / valor_meta, 1.0)
    m3.metric("Progresso da Meta", f"{progresso_meta*100:.1f}%")
    st.progress(progresso_meta)

    # --- GRÁFICOS ---
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.subheader("🍕 Distribuição da Carteira")
        fig_pizza = go.Figure(data=[go.Pie(
            labels=df_editado["Nome do Ativo"], 
            values=df_editado["Valor Atual (R$)"],
            hole=.4,
            textinfo='label+percent'
        )])
        fig_pizza.update_layout(margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig_pizza, use_container_width=True)

    with col_g2:
        st.subheader("📈 Projeção de Crescimento")
        # Simulação mês a mês para o gráfico
        meses_lista = list(range(meses + 1))
        valores_lista = [total_atual * ((1 + taxa_media_mensal) ** m) for m in meses_lista]
        
        fig_linha = go.Figure()
        fig_linha.add_trace(go.Scatter(x=meses_lista, y=valores_lista, name="Evolução", line=dict(color='#00ff00', width=4)))
        fig_linha.add_hline(y=valor_meta, line_dash="dash", line_color="red", annotation_text="Meta")
        fig_linha.update_layout(xaxis_title="Meses", yaxis_title="R$")
        st.plotly_chart(fig_linha, use_container_width=True)

    # Insights
    if total_atual > 0:
        st.markdown("---")
        st.subheader("💡 Insights")
        if projecao_final >= valor_meta:
            st.success(f"Excelente! Com o rendimento atual de **{taxa_media_mensal*100:.2f}% a.m.**, você atingirá sua meta sem novos aportes.")
        else:
            falta = valor_meta - projecao_final
            st.warning(f"Atenção: No ritmo atual, você chegará a R$ {projecao_final:,.2f}. Faltarão R$ {falta:,.2f} para sua meta.")
