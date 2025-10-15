import os
import json
import time
from urllib.parse import urljoin
import requests
import streamlit as st

# ==============================
# Config
# ==============================
API_URL = os.getenv(
    "API_URL",
    "https://backend-desafio5-agente-autonomos.onrender.com"
).rstrip("/")

st.set_page_config(page_title="Agente EDA Autônomo", page_icon="🧠", layout="wide")

# ==============================
# Helpers
# ==============================
def _abs_url(base: str, maybe_path: str | None) -> str | None:
    if not maybe_path:
        return None
    if maybe_path.startswith(("http://", "https://")):
        return maybe_path
    return urljoin(base + "/", maybe_path.lstrip("/"))

def _get(path: str, timeout=120, params: dict | None = None):
    return requests.get(f"{API_URL}{path}", params=params, timeout=timeout)

def _post_json(path: str, payload: dict, timeout=300):
    return requests.post(f"{API_URL}{path}", json=payload, timeout=timeout)

def _upload_csv(file):
    files = {"file": (file.name, file, "text/csv")}
    return requests.post(f"{API_URL}/upload/", files=files, timeout=1200)

def _human_bytes(num):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024.0

def _health():
    try:
        r = _get("/health", timeout=5)
        if r.ok and (r.json() or {}).get("status") == "ok":
            return True, "ok"
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)

def _health_badge():
    ok, msg = _health()
    if ok:
        st.success("Backend online ✅")
    else:
        st.error(f"Backend offline ❌ ({msg})")
    return ok

def _wake_server(max_wait_sec: int = 120, interval_sec: float = 2.5):
    start = time.time()
    last = ""
    while time.time() - start < max_wait_sec:
        ok, msg = _health()
        if ok:
            return True, "Servidor acordado e pronto! ✅"
        last = msg
        time.sleep(interval_sec)
    return False, f"Não foi possível acordar em {max_wait_sec}s. Último status: {last}"

# ==============================
# Header
# ==============================
st.markdown(
    f"""
<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
  <h2 style="margin:0;">🧠 Agente Autônomo de EDA</h2>
  <code style="background:#f6f6f6;padding:2px 6px;border-radius:6px;">API: {API_URL}</code>
</div>
""",
    unsafe_allow_html=True
)

left, right = st.columns([1, 6])
with left:
    if st.button("🚀 Acordar servidor"):
        with st.spinner("Acordando o backend no Render…"):
            ok, msg = _wake_server()
        st.success(msg) if ok else st.warning(msg)
with right:
    st.caption("Se o backend estiver em sleep, clique em **Acordar servidor** antes de usar.")

# ==============================
# Sidebar
# ==============================
with st.sidebar:
    st.markdown("## ⚙️ Config")
    st.write("API URL:", f"`{API_URL}`")
    backend_ok = _health_badge()
    st.markdown("---")
    st.markdown("### ℹ️ Dicas")
    st.markdown(
        "- **Passo 1**: Envie o CSV.\n"
        "- **Passo 2**: Gere o **perfil global**.\n"
        "- **Passo 3**: Faça perguntas (peça gráficos: histograma, heatmap, boxplot, série temporal, scatter…)."
    )
    st.markdown("---")
    st.caption("Agente EDA • Streamlit Frontend")

# ==============================
# Session state
# ==============================
st.session_state.setdefault("dataset_name", None)
st.session_state.setdefault("last_answer", None)
st.session_state.setdefault("last_details", None)
st.session_state.setdefault("last_question", None)

# ==============================
# 1) Upload (apenas local)
# ==============================
st.subheader("1) Upload do CSV (apenas local)")

uploaded = st.file_uploader("Escolha seu arquivo CSV (ex.: creditcard.csv)", type=["csv"])
if uploaded is not None:
    size = _human_bytes(len(uploaded.getbuffer()))
    st.info(f"Arquivo: **{uploaded.name}** • Tamanho: {size}")

    if st.button("⬆️ Enviar para API"):
        if not backend_ok:
            st.warning("O backend parece offline. Clique em 'Acordar servidor' e tente de novo.")
        else:
            with st.spinner("Enviando arquivo…"):
                resp = _upload_csv(uploaded)

            if resp.ok:
                # Tenta ler JSON
                try:
                    data = resp.json()
                except Exception:
                    data = {"_raw_text": resp.text}

                st.success("Upload concluído.")
                st.code(json.dumps(data, indent=2, ensure_ascii=False), language="json")

                # Fallbacks para descobrir nome do arquivo salvo
                fname = (
                    data.get("filename")
                    or data.get("saved_as")
                    or (os.path.basename(data.get("path")) if isinstance(data.get("path"), str) else None)
                    or uploaded.name
                )
                fname = (fname or "").strip()

                if not fname:
                    st.error("Não foi possível determinar o nome do dataset salvo.")
                else:
                    st.session_state.dataset_name = fname
                    st.info(f"Dataset definido: `{st.session_state.dataset_name}`")
            else:
                st.error(f"Falha no upload: {resp.status_code}")
                st.code(resp.text, language="text")

# ==============================
# 2) Perfil Global
# ==============================
st.subheader("2) Gerar / Ver Perfil Global")
st.caption(f"Dataset atual: {st.session_state.get('dataset_name') or '—'}")

if not st.session_state.dataset_name:
    st.info("Envie seu CSV primeiro.")
else:
    c1, c2 = st.columns([1, 1])

    with c1:
        st.markdown("**Gerar / Atualizar perfil (dataset inteiro)**")
        if st.button("🧮 Gerar perfil global agora"):
            if not backend_ok:
                st.warning("O backend parece offline. Clique em 'Acordar servidor' e tente de novo.")
            else:
                with st.spinner("Calculando perfil global em chunks…"):
                    resp = _get(f"/profile/{st.session_state.dataset_name}", timeout=900)
                if resp.ok:
                    out = resp.json()
                    st.success("Perfil (re)gerado com sucesso.")
                    st.code(json.dumps(out, indent=2, ensure_ascii=False))
                else:
                    st.error(f"Erro ao gerar perfil: {resp.status_code} • {resp.text}")

    with c2:
        st.markdown("**Abrir perfil salvo (JSON)**")
        if st.button("📖 Ver perfil salvo"):
            if not backend_ok:
                st.warning("O backend parece offline. Clique em 'Acordar servidor' e tente de novo.")
            else:
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
# 3) Pergunte ao agente
# ==============================
st.subheader("3) Pergunte ao agente")
if not st.session_state.dataset_name:
    st.info("Envie o CSV e gere o perfil antes de perguntar.")
else:
    default_q = "Explique o valor médio de Amount e a taxa de fraude; indique que gráfico eu deveria ver."
    question = st.text_area("Sua pergunta:", value=default_q, height=120)

    ask_col, tip_col = st.columns([1, 3])
    with ask_col:
        if st.button("💬 Perguntar"):
            if not backend_ok:
                st.warning("O backend parece offline. Clique em 'Acordar servidor' e tente novamente.")
            else:
                st.session_state.last_question = question
                payload = {"dataset": st.session_state.dataset_name, "question": question}
                with st.spinner("Consultando o agente…"):
                    resp = _post_json("/agent/ask", payload, timeout=300)
                if resp.ok:
                    ans = resp.json()
                    st.session_state.last_answer = ans.get("answer")
                    st.session_state.last_details = ans.get("details")
                    st.success("Resposta recebida.")
                else:
                    st.error(f"Erro: {resp.status_code} • {resp.text}")

    with tip_col:
        st.caption("Peça: 'histograma de Amount (log)', 'heatmap de correlação', 'boxplot Amount por Class', 'série temporal', 'scatter V1 vs V2'…")

    if st.session_state.last_answer:
        st.markdown("#### Resposta")
        st.write(st.session_state.last_answer)

    if st.session_state.last_details and isinstance(st.session_state.last_details, dict):
        url_rel = st.session_state.last_details.get("plot_url")
        url_abs = _abs_url(API_URL, url_rel) if url_rel else None
        if url_abs:
            st.image(url_abs, caption="Gráfico gerado pelo agente")
        else:
            direct_path = st.session_state.last_details.get("plot_path")
            if direct_path:
                try:
                    st.image(direct_path, caption="Gráfico gerado pelo agente")
                except Exception:
                    pass

    if st.session_state.last_details and isinstance(st.session_state.last_details, dict):
        many = st.session_state.last_details.get("plot_paths")
        if many and isinstance(many, list) and len(many) > 0:
            st.markdown("#### Gráficos gerados")
            cols = st.columns(2)
            for i, p in enumerate(many):
                absu = _abs_url(API_URL, p) if isinstance(p, str) and p.startswith("/static/") else None
                with cols[i % 2]:
                    if absu:
                        st.image(absu, caption=os.path.basename(p))
                    else:
                        try:
                            st.image(p, caption=os.path.basename(p))
                        except Exception:
                            st.caption(p)

# ==============================
# 4) Histórico
# ==============================
st.subheader("4) Histórico desta sessão")
if st.session_state.get("last_answer"):
    st.markdown("**Última pergunta e resposta**")
    st.code(st.session_state.get("last_question", ""), language="markdown")
    st.write(st.session_state["last_answer"])
else:
    st.caption("Na primeira pergunta respondida, o histórico aparece aqui.")