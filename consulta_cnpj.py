import streamlit as st
import requests
import re
from pathlib import Path
import time
import datetime
import io
import csv

URL_BRASILAPI_CNPJ = "https://brasilapi.com.br/api/cnpj/v1/"
URL_OPEN_CNPJA = "https://open.cnpja.com/office/"

st.set_page_config(page_title="Consulta CNPJ - Adapta", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .stApp { background-color: #1A1A1A; color: #EEEEEE; }
    h1, h2, h3, h4, h5, h6 { color: #FFC300; }
    .stTextInput label { color: #FFC300; }
    .stTextInput div[data-baseweb="input"] > div { background-color: #333333; color: #EEEEEE; border: 1px solid #FFC300; }
    .stTextInput div[data-baseweb="input"] > div:focus-within { border-color: #FFD700; box-shadow: 0 0 0 0.1rem rgba(255,195,0,.25); }
    .stButton > button { background-color: #FFC300; color: #1A1A1A; border:none; padding:10px 20px; border-radius:5px; font-weight:700; }
    .stButton > button:hover { background-color:#FFD700; color:#000000; }
    .stExpander { background-color:#333333; border:1px solid #FFC300; border-radius:5px; padding:10px; margin-bottom:10px; }
    hr { border-top:1px solid #444444; }

    .ghost-buttons { display:flex; gap:10px; flex-wrap:wrap; margin-top:8px; }
    .ghost-btn {
        background: #2a2a2a; border: 1px dashed #6b7280; color:#9ca3af;
        padding:10px 14px; border-radius:10px; font-weight:700; cursor:not-allowed; position:relative;
    }
    .ghost-btn .tag {
        position:absolute; top:-10px; right:-10px; background:#374151; color:#f3f4f6;
        font-size:10px; padding:3px 6px; border-radius:999px; border:1px solid #6b7280;
    }
    .ghost-caption { color:#9ca3af; font-size:12px; margin-top:6px; }
</style>
""", unsafe_allow_html=True)

IMAGE_DIR = Path(__file__).resolve().parent / "images"

def only_digits(s: str) -> str:
    return re.sub(r'[^0-9]', '', s or "")

def format_currency_brl(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "N/A"

def format_phone(ddd, num):
    return f"({ddd}) {num}" if ddd and num else "N/A"

def format_cnpj_mask(cnpj: str) -> str:
    c = only_digits(cnpj)
    return f"{c[0:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:14]}" if len(c) == 14 else cnpj

# ---------- matriz utils ----------
def calcular_digitos_verificadores_cnpj(cnpj_base_12_digitos: str) -> str:
    pesos_12 = [5,4,3,2,9,8,7,6,5,4,3,2]
    pesos_13 = [6,5,4,3,2,9,8,7,6,5,4,3,2]
    def dv(base, pesos):
        s = sum(int(base[i]) * pesos[i] for i in range(len(base)))
        r = s % 11
        return '0' if r < 2 else str(11 - r)
    d13 = dv(cnpj_base_12_digitos[:12], pesos_12)
    d14 = dv(cnpj_base_12_digitos[:12] + d13, pesos_13)
    return d13 + d14

def to_matriz_if_filial(cnpj_clean: str) -> str:
    if len(cnpj_clean) != 14:
        return cnpj_clean
    if cnpj_clean[8:12] != "0001":
        raiz = cnpj_clean[:8]
        base12 = raiz + "0001"
        dvs = calcular_digitos_verificadores_cnpj(base12)
        return base12 + dvs
    return cnpj_clean

# ---------- consultas ----------
@st.cache_data(ttl=3600, show_spinner=False)
def consulta_brasilapi_cnpj(cnpj_limpo: str):
    try:
        r = requests.get(f"{URL_BRASILAPI_CNPJ}{cnpj_limpo}", timeout=15)
        if r.status_code in (400, 404):
            return {"__error": "not_found"}
        if r.status_code in (429, 500, 502, 503, 504):
            return {"__error": "unavailable"}
        r.raise_for_status()
        return r.json()
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        return {"__error": "unavailable"}
    except requests.exceptions.HTTPError:
        return {"__error": "unavailable"}
    except Exception:
        return {"__error": "unavailable"}

# ---------- regime unificado ----------
def determinar_regime_unificado(dados_cnpj: dict) -> str:
    is_mei = dados_cnpj.get("opcao_pelo_mei")
    if is_mei: return "MEI"
    is_simples = dados_cnpj.get("opcao_pelo_simples")
    if is_simples: return "SIMPLES NACIONAL"
    regimes = dados_cnpj.get("regime_tributario") or []
    if regimes:
        current_year = datetime.date.today().year
        anos = [r.get("ano") for r in regimes if isinstance(r.get("ano"), int)]
        if anos:
            candidatos = [a for a in anos if a <= current_year]
            alvo = max(candidatos) if candidatos else max(anos)
            regime_alvo = next((r for r in reversed(regimes) if r.get("ano") == alvo), regimes[-1])
            forma = (regime_alvo or {}).get("forma_de_tributacao", "N/A")
            return str(forma).upper()
        forma = (regimes[-1] or {}).get("forma_de_tributacao", "N/A")
        return str(forma).upper()
    return "N/A"

def badge_cor_regime(regime: str):
    r = (regime or "").upper()
    if "MEI" in r: return "#FB923C", "#111111"
    if "SIMPLES" in r: return "#FACC15", "#111111"
    if "LUCRO REAL" in r: return "#3B82F6", "#FFFFFF"
    if "LUCRO PRESUMIDO" in r: return "#22C55E", "#111111"
    return "#EF4444", "#FFFFFF"

def render_badge(texto: str, bg: str, fg: str):
    st.markdown(
        f"""<div style="display:inline-block;padding:8px 12px;border-radius:999px;font-weight:800;letter-spacing:.3px;background:{bg};color:{fg};">
            {texto}
        </div>""",
        unsafe_allow_html=True
    )

def render_regime_badge(regime: str):
    bg, fg = badge_cor_regime(regime)
    render_badge(regime, bg, fg)

# ---------- situação cadastral ----------
def normalizar_situacao_cadastral(txt: str) -> str:
    s = (txt or "").strip().upper()
    if not s: return "N/A"
    if "ATIV" in s: return "ATIVO"
    if "INAPT" in s: return "INAPTO"
    if "SUSP" in s: return "SUSPENSO"
    if "BAIX" in s: return "BAIXADO"
    return s

def render_situacao_badge(label: str, valor: str):
    s = (valor or "N/A").upper()
    if s == "ATIVO": icon, txt = "🟢", "Ativo"
    elif s == "INAPTO": icon, txt = "🟡", "Inapto"
    elif s == "SUSPENSO": icon, txt = "🟠", "Suspenso"
    elif s == "BAIXADO": icon, txt = "🔴", "Baixado"
    else: icon, txt = "⚪", (valor.title() if valor else "N/A")
    st.write(f"**{label}:** {icon} {txt}")

# ---------- UI ----------
st.image(str(IMAGE_DIR / "logo_main.png"), width=150)
st.markdown("<h1 style='text-align: center;'>Consulta de CNPJ</h1>", unsafe_allow_html=True)

cnpj_input = st.text_input("Digite o CNPJ (apenas números, ou com pontos, barras e traços):")

if st.button("Consultar CNPJ"):
    cnpj_limpo = only_digits(cnpj_input)
    if len(cnpj_limpo) != 14:
        st.error("CNPJ inválido")
    else:
        with st.spinner(f"Consultando CNPJ {format_cnpj_mask(cnpj_limpo)}..."):
            dados_cnpj = consulta_brasilapi_cnpj(cnpj_limpo)
            if dados_cnpj.get("__error") == "not_found":
                st.error("CNPJ não encontrado."); st.stop()
            if dados_cnpj.get("__error") == "unavailable":
                st.error("Serviço indisponível."); st.stop()

            st.success(f"Dados encontrados para o CNPJ: {format_cnpj_mask(dados_cnpj.get('cnpj','N/A'))}")

            # Situação e Razão Social
            sit_norm = normalizar_situacao_cadastral(dados_cnpj.get('descricao_situacao_cadastral'))
            razao = dados_cnpj.get('razao_social', 'N/A')
            if sit_norm == "BAIXADO":
                razao = f"{razao} - (BAIXADO)"
            st.markdown(f"<div style='text-align:center; font-size: 1.6rem; font-weight: 800; color: #FFC300;'>{razao}</div>", unsafe_allow_html=True)

            # Regime via matriz
            cnpj_matriz = to_matriz_if_filial(cnpj_limpo)
            regime_source = dados_cnpj
            if cnpj_matriz != cnpj_limpo:
                dados_matriz = consulta_brasilapi_cnpj(cnpj_matriz)
                if isinstance(dados_matriz, dict) and "cnpj" in dados_matriz:
                    regime_source = dados_matriz
            regime_final = determinar_regime_unificado(regime_source)

            st.markdown("---")
            st.markdown("## Regime Tributário")
            render_regime_badge(regime_final)

            # Situação Cadastral logo abaixo do regime
            render_situacao_badge("Situação Cadastral", sit_norm)

            # ... (demais seções: Dados da Empresa, Endereço, QSA, CNAEs, IE, Exportação)

            # Integração ERP (somente botões que pediu)
            st.markdown("---")
            st.subheader("Integração ERP (SAP Business One)")
            st.markdown("""
                <div class="ghost-buttons">
                    <div class="ghost-btn">⬆️ Exportar PN para SAP B1 <span class="tag">Em breve</span></div>
                    <div class="ghost-btn">🔄 Atualizar Cadastro no SAP B1 <span class="tag">Em breve</span></div>
                </div>
                <div class="ghost-caption">Conectores prontos para ativação com credenciais do SAP Business One (Service Layer).</div>
            """, unsafe_allow_html=True)
