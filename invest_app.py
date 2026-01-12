import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import streamlit_authenticator as stauth

# --- CONFIGURAÇÃO E LOGIN ---
st.set_page_config(page_title="Gestor de Investimentos", layout="wide")

# Sistema simples de usuários (Em produção, use banco de dados)
names = ["Usuario Teste"]
usernames = ["admin"]
passwords = ["12345"] # Em app real, as senhas devem ser criptografadas

authenticator = stauth.Authenticate(
    {"usernames": {usernames[0]: {"name": names[0], "password": passwords[0]}}},
    "cookie_invest", "key_invest", cookie_expiry_days=30
)


# Primeiro, chamamos o login sem atribuir a variáveis
authenticator.login(location='main')

# Depois, pegamos os valores que precisamos do estado da sessão
name = st.session_state["name"]
authentication_status = st.session_state["authentication_status"]
username = st.session_state["username"]




if authentication_status is False:
    st.error("Usuário ou senha incorretos")
elif authentication_status is None:
    st.warning("Por favor, insira usuário e senha")
else:
    # --- APP PRINCIPAL ---
    with st.sidebar:
        st.write(f"Bem-vindo, **{name}**")
        authenticator.logout("Sair", "sidebar")
        st.markdown("---")
        
        st.header("🎯 Minha Meta")
        valor_meta = st.number_input("Objetivo Final (R$)", min_value=0.0, value=100000.0)
        
        st.header("📈 Configurações de Mercado")
        taxa_anual = st.number_input("Taxa de Juros Esperada (% ao ano)", value=10.0)
        tempo_anos = st.slider("Tempo do Plano (Anos)", 1, 40, 10)

    st.title("🚀 Simulador de Carteira e Metas")

    # --- LANÇAMENTO POR CLASSE DE ATIVOS ---
    st.subheader("🏦 Lançamento Mensal por Ativo")
    col_a, col_b, col_c = st.columns(3)
    
    with col_a:
        fii = st.number_input("FIIs (R$)", min_value=0.0, value=500.0)
    with col_b:
        acoes_br = st.number_input("Ações Brasil (R$)", min_value=0.0, value=300.0)
    with col_c:
        acoes_int = st.number_input("Ações Internacionais (R$)", min_value=0.0, value=200.0)

    aporte_total = fii + acoes_br + acoes_int
    taxa_mensal = (1 + taxa_anual/100)**(1/12) - 1
    total_meses = tempo_anos * 12

    # --- CÁLCULOS ---
    dados = []
    saldo = 0
    investido_acumulado = 0

    for mes in range(1, total_meses + 1):
        juros = saldo * taxa_mensal
        saldo += juros + aporte_total
        investido_acumulado += aporte_total
        
        dados.append({
            "Mês": mes,
            "Investido": investido_acumulado,
            "Juros": saldo - investido_acumulado,
            "Total": saldo
        })

    df = pd.DataFrame(dados)
    montante_final = df["Total"].iloc[-1]

    # --- DASHBOARD ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Montante em {} Anos".format(tempo_anos), f"R$ {montante_final:,.2f}")
    c2.metric("Aporte Mensal Total", f"R$ {aporte_total:,.2f}")
    
    progresso = min(montante_final / valor_meta, 1.0)
    c3.metric("Atingimento da Meta", f"{progresso*100:.1f}%")
    st.progress(progresso)

    # --- GRÁFICOS ---
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["Mês"], y=df["Investido"], name="Capital Investido", marker_color='#1f77b4'))
    fig.add_trace(go.Bar(x=df["Mês"], y=df["Juros"], name="Juros Acumulados", marker_color='#2ca02c'))
    
    # Linha da Meta
    fig.add_hline(y=valor_meta, line_dash="dash", line_color="red", annotation_text="Sua Meta")

    fig.update_layout(barmode='stack', title="Crescimento Patrimonial vs Meta", xaxis_title="Meses", yaxis_title="R$")
    st.plotly_chart(fig, use_container_width=True)

    # --- INSIGHTS ---
    st.subheader("💡 Insights do Planejamento")
    col_i1, col_i2 = st.columns(2)

    with col_i1:
        if montante_final >= valor_meta:
            st.success(f"✅ Com esse plano, você baterá sua meta de R$ {valor_meta:,.2f}!")
        else:
            falta = valor_meta - montante_final
            st.error(f"❌ Para atingir a meta neste prazo, você precisa de mais R$ {falta:,.2f} ou aumentar o aporte.")

    with col_i2:
        distribuicao = pd.DataFrame({
            "Ativo": ["FIIs", "Ações BR", "Ações Int"],
            "Valor": [fii, acoes_br, acoes_int]
        })
        fig_pizza = go.Figure(data=[go.Pie(labels=distribuicao["Ativo"], values=distribuicao["Valor"], hole=.3)])
        fig_pizza.update_layout(title="Distribuição do Aporte Mensal", height=300)
        st.plotly_chart(fig_pizza, use_container_width=True)

    st.subheader("📋 Tabela de Evolução")

    st.dataframe(df.tail(12), use_container_width=True) # Mostra os últimos 12 meses

