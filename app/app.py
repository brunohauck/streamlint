import os
import json
import requests
import streamlit as st

# ==============================
# Configurações
# ==============================
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="Agente EDA Autônomo",
    page_icon="🧠",
    layout="wide",
)

# ==============================
# Helpers
# ==============================
def _post_json(path: str, payload: dict, timeout=120):
    url = f"{API_URL}{path}"
    resp = requests.post(url, json=payload, timeout=timeout)
    return resp

def _get(path: str, timeout=120):
    url = f"{API_URL}{path}"
    resp = requests.get(url, timeout=timeout)
    return resp

def _upload_csv(file):
    files = {"file": (file.name, file, "text/csv")}
    resp = requests.post(f"{API_URL}/upload/", files=files, timeout=300)
    return resp

def _human_bytes(num):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024.0

# ==============================
# Sidebar
# ==============================
with st.sidebar:
    st.markdown("## ⚙️ Config")
    st.write("API URL:", API_URL)
    st.markdown("---")
    st.markdown("### ℹ️ Dicas")
    st.markdown(
        "- Faça upload do CSV **creditcard.csv** ou use um já existente.\n"
        "- Gere o **perfil global** antes de fazer perguntas.\n"
        "- Pergunte algo como: *'Explique o valor médio de Amount e a taxa de fraude; indique um gráfico'*. "
    )
    st.markdown("---")
    st.caption("Agente EDA • Streamlit Frontend")

st.title("🧠 Agente Autônomo de EDA")
st.caption("Upload de CSV • Perfil Global • Perguntas em linguagem natural • Gráficos automáticos")

# ==============================
# Sessão de estado
# ==============================
if "dataset_name" not in st.session_state:
    st.session_state.dataset_name = None
if "last_answer" not in st.session_state:
    st.session_state.last_answer = None
if "last_details" not in st.session_state:
    st.session_state.last_details = None
if "last_question" not in st.session_state:
    st.session_state.last_question = None

# ==============================
# Seção 1: Upload
# ==============================
st.subheader("1) Upload do CSV")

uploaded = st.file_uploader("Escolha seu arquivo CSV (ex.: creditcard.csv)", type=["csv"])
col_u1, col_u2 = st.columns([1, 3])

with col_u1:
    if uploaded is not None:
        size = _human_bytes(len(uploaded.getbuffer()))
        st.info(f"Arquivo: **{uploaded.name}** • Tamanho: {size}")
        if st.button("⬆️ Enviar para API"):
            with st.spinner("Enviando arquivo…"):
                resp = _upload_csv(uploaded)
            if resp.ok:
                data = resp.json()
                st.success(f"Upload concluído: `{data.get('filename')}`")
                st.session_state.dataset_name = data.get("filename")
            else:
                st.error(f"Falha no upload: {resp.status_code} • {resp.text}")

with col_u2:
    st.write("Ou informe manualmente o nome do arquivo já presente no servidor:")
    manual_name = st.text_input(
        "Nome do arquivo em `api/storage/datasets/`",
        value=st.session_state.dataset_name or ""
    )
    if st.button("Usar este dataset"):
        if manual_name.strip():
            st.session_state.dataset_name = manual_name.strip()
            st.success(f"Dataset definido: `{st.session_state.dataset_name}`")
        else:
            st.warning("Informe um nome de arquivo válido (ex.: creditcard.csv).")

# ==============================
# Seção 2: Perfil Global
# ==============================
st.subheader("2) Gerar / Ver Perfil Global")

if not st.session_state.dataset_name:
    st.info("Defina um dataset primeiro (upload ou manual).")
else:
    c1, c2 = st.columns([1, 1])

    with c1:
        st.markdown("**Gerar / Atualizar perfil (dataset inteiro)**")
        gerar = st.button("🧮 Gerar perfil global agora")
        if gerar:
            with st.spinner("Calculando perfil global em chunks (pode levar alguns segundos)…"):
                resp = _get(f"/profile/{st.session_state.dataset_name}")
            if resp.ok:
                out = resp.json()
                st.success("Perfil (re)gerado com sucesso.")
                st.code(json.dumps(out, indent=2, ensure_ascii=False))
            else:
                st.error(f"Erro ao gerar perfil: {resp.status_code} • {resp.text}")

    with c2:
        st.markdown("**Abrir perfil salvo (JSON)**")
        ver = st.button("📖 Ver perfil salvo")
        if ver:
            with st.spinner("Carregando perfil salvo…"):
                resp = _get(f"/profile/show/{st.session_state.dataset_name}")
            if resp.ok:
                saved = resp.json()
                st.success("Perfil carregado.")
                st.code(json.dumps(saved, indent=2, ensure_ascii=False))
            else:
                if resp.status_code == 404:
                    st.warning("Perfil ainda não foi gerado. Clique em **Gerar perfil global**.")
                else:
                    st.error(f"Erro ao abrir perfil: {resp.status_code} • {resp.text}")

# ==============================
# Seção 3: Perguntas ao Agente (LLM)
# ==============================
st.subheader("3) Pergunte ao agente")

if st.session_state.dataset_name:
    default_q = "Explique o valor médio de Amount e a taxa de fraude; indique que gráfico eu deveria ver."
    question = st.text_area("Sua pergunta:", value=default_q, height=120)

    c_ask1, c_ask2 = st.columns([1, 3])
    with c_ask1:
        if st.button("💬 Perguntar"):
            st.session_state.last_question = question
            payload = {"dataset": st.session_state.dataset_name, "question": question}
            with st.spinner("Consultando o agente…"):
                resp = _post_json("/agent/ask", payload)
            if resp.ok:
                ans = resp.json()
                st.session_state.last_answer = ans.get("answer")
                st.session_state.last_details = ans.get("details")
                st.success("Resposta recebida.")
            else:
                st.error(f"Erro: {resp.status_code} • {resp.text}")

    with c_ask2:
        st.caption("Dica: peça gráficos (ex.: 'histograma de Amount, com escala log'), correlações, outliers, tendência temporal etc.")

    # Exibir resposta
    if st.session_state.last_answer:
        st.markdown("#### Resposta")
        st.write(st.session_state.last_answer)

    # Mostrar imagem/URL retornada diretamente pelo backend (1 gráfico)
    if st.session_state.last_details and isinstance(st.session_state.last_details, dict):
        url = st.session_state.last_details.get("plot_url")
        if url:
            st.image(API_URL + url, caption="Gráfico gerado pelo agente")
        else:
            direct_path = st.session_state.last_details.get("plot_path")
            if direct_path:
                st.image(direct_path, caption="Gráfico gerado pelo agente")

    # Mostrar vários gráficos, se vierem (plot_paths)
    if st.session_state.last_details and isinstance(st.session_state.last_details, dict):
        many = st.session_state.last_details.get("plot_paths")
        if many and isinstance(many, list) and len(many) > 0:
            st.markdown("#### Histogramas gerados")
            for p in many:
                # se vier apenas path, tenta exibir; se vier nome no /static, prefixa URL
                if p.startswith("/static/"):
                    st.image(API_URL + p, caption=p.split("/")[-1])
                else:
                    st.image(p, caption=os.path.basename(p))

    # Se vier meta com instrução de plot, tenta puxar o gráfico sob demanda (fallback)
    if st.session_state.last_details and isinstance(st.session_state.last_details, dict):
        meta = st.session_state.last_details.get("meta")
        if meta and isinstance(meta, dict) and "plot" in meta:
            plot = meta["plot"]
            with st.expander("Instrução de gráfico sugerida pelo agente"):
                st.json(plot)

            try:
                if plot.get("type") == "hist_amount":
                    r = _get(
                        f"/plot/amount_hist/{st.session_state.dataset_name}?bins={plot.get('bins',50)}&log={str(plot.get('log', True)).lower()}"
                    )
                    if r.ok:
                        j = r.json()
                        url = j.get("plot_url")
                        path = j.get("plot_path")
                        st.image(API_URL + url if url else path, caption="Histograma de Amount (gerado pelo backend)")
                elif plot.get("type") == "timeseries":
                    r = _get(
                        f"/plot/time_series/{st.session_state.dataset_name}?bins={plot.get('bins',120)}"
                    )
                    if r.ok:
                        j = r.json()
                        url = j.get("plot_url")
                        path = j.get("plot_path")
                        st.image(API_URL + url if url else path, caption="Série temporal (gerada pelo backend)")
                # (Outros tipos podem ser adicionados aqui quando os endpoints existirem)
            except Exception as e:
                st.warning(f"Não foi possível renderizar o gráfico automaticamente: {e}")

else:
    st.info("Defina um dataset e gere o perfil antes de fazer perguntas.")

# ==============================
# Seção 4: Histórico rápido (memória)
# ==============================
st.subheader("4) Histórico desta sessão")
if st.session_state.last_answer:
    st.markdown("**Última pergunta e resposta**")
    st.code(st.session_state.get("last_question", ""), language="markdown")
    st.write(st.session_state.last_answer)
else:
    st.caption("Na primeira pergunta respondida, o histórico aparece aqui.")