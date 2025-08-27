import streamlit as st
import requests
import re
from pathlib import Path

# =========================
# Configuração da Aplicação
# =========================
URL_BRASILAPI_CNPJ = "https://brasilapi.com.br/api/cnpj/v1/"
URL_OPEN_CNPJA = "https://open.cnpja.com/office/"

st.set_page_config(
    page_title="Consulta CNPJ - Arlequim",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# =========================
# CSS Customizado
# =========================
st.markdown("""
<style>
    .stApp { background-color: #1A1A1A; color: #EEEEEE; }
    h1 { color: #FFC300; text-align: center; }
    h2, h3 { color: #FFC300; }
    .stAlert { border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# =========================
# Caminho para Imagens
# =========================
IMAGE_DIR = Path(__file__).resolve().parent / "images"

# Logo topo
st.image(str(IMAGE_DIR / "logo_main.png"), width=150)
st.markdown("<h1>Consulta de CNPJ</h1>", unsafe_allow_html=True)

# =========================
# Funções Auxiliares
# =========================
def limpar_cnpj(cnpj: str) -> str:
    return re.sub(r'[^0-9]', '', cnpj or "")

def consultar_brasilapi(cnpj: str):
    try:
        r = requests.get(f"{URL_BRASILAPI_CNPJ}{cnpj}", timeout=15)
        r.raise_for_status()
        return r.json()
    except:
        return None

def consultar_open_cnpja(cnpj: str):
    try:
        r = requests.get(f"{URL_OPEN_CNPJA}{cnpj}", timeout=15)
        if r.status_code == 200:
            return r.json()
    except:
        return None
    return None

def get_regime_tributario(api_data):
    regimes = api_data.get("regime_tributario", [])
    if not regimes:
        return "N/A"
    # pega o último ano disponível
    ultimo = max(regimes, key=lambda x: x.get("ano", 0))
    return ultimo.get("forma_de_tributacao", "N/A")

def get_ie_from_open(cnpj):
    data = consultar_open_cnpja(cnpj)
    if not data or "registrations" not in data:
        return "N/A"
    regs = data.get("registrations", [])
    if not regs:
        return "N/A"
    formatted = []
    for reg in regs:
        uf = reg.get("state", "N/A")
        ie = reg.get("number", "N/A")
        status = reg.get("status", {}).get("text", "N/A")
        tipo = reg.get("type", {}).get("text", "N/A")
        formatted.append(f"UF: {uf} | IE: {ie} | Status: {status} | Tipo: {tipo}")
    return "\n".join(formatted)

def badge_regime(texto):
    if "LUCRO REAL" in texto.upper():
        color = "#3498db"  # azul
    elif "LUCRO PRESUMIDO" in texto.upper():
        color = "#2ecc71"  # verde
    elif "SIMPLES" in texto.upper():
        color = "#f1c40f"  # amarelo
    elif "MEI" in texto.upper():
        color = "#e67e22"  # laranja
    else:
        color = "#e74c3c"  # vermelho
    return f"<div style='background-color:{color};padding:8px;border-radius:5px;text-align:center;font-weight:bold;'>{texto}</div>"

def badge_situacao(texto):
    if not texto: return "N/A"
    t = texto.upper()
    if "ATIVA" in t:
        return "🟢 Ativa"
    elif "INAPTA" in t:
        return "🟡 Inapta"
    elif "SUSPENSA" in t or "SUSPENSO" in t:
        return "🟠 Suspensa"
    elif "BAIXADA" in t:
        return "🔴 Baixada"
    return texto

# =========================
# Interface
# =========================
cnpj_input = st.text_input("Digite o CNPJ:", placeholder="00.000.000/0001-00")

if st.button("Consultar CNPJ"):
    cnpj_limpo = limpar_cnpj(cnpj_input)
    if len(cnpj_limpo) != 14:
        st.error("CNPJ inválido, digite 14 números.")
    else:
        with st.spinner("Consultando CNPJ..."):
            dados = consultar_brasilapi(cnpj_limpo)
            if not dados:
                st.error("CNPJ não encontrado ou erro na consulta. Verifique o número e tente novamente.")
            else:
                # Razão Social em destaque
                razao = dados.get("razao_social", "N/A")
                situacao = dados.get("descricao_situacao_cadastral", "")
                if situacao and "BAIXADA" in situacao.upper():
                    razao = f"{razao} - (BAIXADO)"
                st.markdown(f"<h2 style='color:#FFC300;text-align:center;'>{razao}</h2>", unsafe_allow_html=True)

                # Regime Tributário
                regime = get_regime_tributario(dados)
                st.markdown(badge_regime(f"Regime Tributário: {regime}"), unsafe_allow_html=True)

                # Campos simulados da reforma
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown(badge_regime("Situação do Fornecedor para crédito de CBS e IBS: Em construção"), unsafe_allow_html=True)
                if "SIMPLES" in regime.upper():
                    st.markdown(badge_regime("Regime do Simples (Regular ou Normal): Em construção"), unsafe_allow_html=True)

                st.markdown("---")
                st.subheader("Dados da Empresa")
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Nome Fantasia:** {dados.get('nome_fantasia','N/A')}")
                    st.write(f"**CNPJ:** {dados.get('cnpj','N/A')}")
                    st.write(f"**Situação Cadastral:** {badge_situacao(dados.get('descricao_situacao_cadastral','N/A'))}")
                    st.write(f"**Data Início Atividade:** {dados.get('data_inicio_atividade','N/A')}")
                    st.write(f"**CNAE Fiscal:** {dados.get('cnae_fiscal_descricao','N/A')} ({dados.get('cnae_fiscal','N/A')})")
                with col2:
                    st.write(f"**Natureza Jurídica:** {dados.get('natureza_juridica','N/A')}")
                    st.write(f"**Capital Social:** R$ {dados.get('capital_social','N/A')}")
                    st.write(f"**Email:** {dados.get('email','N/A')}")
                    st.write(f"**Opção Simples:** {'Sim' if dados.get('opcao_pelo_simples') else 'Não'}")
                    st.write(f"**Opção MEI:** {'Sim' if dados.get('opcao_pelo_mei') else 'Não'}")

                st.markdown("---")
                st.subheader("Endereço")
                st.write(f"{dados.get('descricao_tipo_de_logradouro','')} {dados.get('logradouro','N/A')}, {dados.get('numero','N/A')}")
                st.write(f"{dados.get('bairro','N/A')} - {dados.get('municipio','N/A')}/{dados.get('uf','N/A')}")
                st.write(f"CEP: {dados.get('cep','N/A')}")

                # CNAEs secundários
                st.markdown("---")
                st.subheader("CNAEs Secundários")
                cnaes = dados.get("cnaes_secundarios", [])
                if cnaes:
                    for cnae in cnaes:
                        st.write(f"- {cnae.get('codigo','N/A')} - {cnae.get('descricao','N/A')}")
                else:
                    st.info("Nenhum CNAE secundário encontrado para este CNPJ.")

                # Inscrições Estaduais (via open.cnpja)
                st.markdown("---")
                st.subheader("Inscrições Estaduais")
                ies = get_ie_from_open(cnpj_limpo)
                st.text(ies)

                # Logo resultado
                st.image(str(IMAGE_DIR / "logo_resultado.png"), width=100)
