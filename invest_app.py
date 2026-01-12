import streamlit as st
import pandas as pd
import requests
import base64
import json
from io import StringIO

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestor Financeiro GitHub", layout="wide")

# Pegando as chaves dos Secrets
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO_NAME = st.secrets["REPO_NAME"]
FILE_PATH = "dados.csv"
URL = f"https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}"

# Função para buscar dados do GitHub
def get_data_from_github():
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(URL, headers=headers)
    if response.status_code == 200:
        content = response.json()
        decoded_data = base64.b64decode(content['content']).decode('utf-8')
        df = pd.read_csv(StringIO(decoded_data))
        return df, content['sha']
    else:
        # Se o arquivo não existir ou der erro, cria um padrão
        df_vazio = pd.DataFrame(columns=["tipo", "nome", "valor_atual", "aporte_mensal", "juros_mensal"])
        return df_vazio, None

# Função para salvar dados no GitHub
def save_to_github(df, sha):
    csv_content = df.to_csv(index=False)
    encoded_content = base64.b64encode(csv_content.encode('utf-8')).decode('utf-8')
    
    payload = {
        "message": "Atualizando dados de investimentos via Streamlit",
        "content": encoded_content,
        "sha": sha
    }
    
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.put(URL, headers=headers, data=json.dumps(payload))
    return response.status_code

# --- INTERFACE DO APP ---
st.title("📊 Gestor Financeiro (Sincronizado com GitHub)")

# Carregamento inicial
df, current_sha = get_data_from_github()

st.subheader("📝 Seus Investimentos")
st.info("Dica: Adicione ou edite as linhas abaixo e clique em Salvar.")

# Editor de tabela
df_editado = st.data_editor(df, num_rows="dynamic", use_container_width=True)

# Botão de Salvar
if st.button("💾 Salvar e Sincronizar"):
    if current_sha is None:
        st.error("Erro: O arquivo dados.csv não foi encontrado no GitHub. Crie-o primeiro!")
    else:
        with st.spinner("Enviando dados para o repositório..."):
            status = save_to_github(df_editado, current_sha)
            if status in [200, 201]:
                st.success("Dados salvos com sucesso no seu GitHub!")
                st.balloons()
                st.rerun()
            else:
                st.error(f"Erro ao salvar. Código: {status}")

# Dashboard Simples
if not df_editado.empty:
    st.markdown("---")
    # Converte para numérico para evitar erros de soma
    df_editado["valor_atual"] = pd.to_numeric(df_editado["valor_atual"], errors='coerce').fillna(0)
    total_total = df_editado["valor_atual"].sum()
    st.metric("Patrimônio Total Armazenado", f"R$ {total_total:,.2f}")
