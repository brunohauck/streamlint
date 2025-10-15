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
        if r.ok:
            try:
                j = r.json() or {}
            except Exception:
                j = {}
            if j.get("status") == "ok":
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

def _candidates_from_upload(data: dict, uploaded_name: str) -> list[str]:
    """
    Gera possíveis identificadores de dataset aceitos pelo backend:
      - filename / saved_as / path (basename)
      - file_path (basename)
      - relative_path (com e sem '/')
      - uploaded_name (basename do cliente) — fica por último
    """
    import os as _os

    cands: list[str] = []

    # 1) chaves padrão
    for key in ("filename", "saved_as"):
        v = (data.get(key) or "").strip()
        if v:
            cands.append(v)

    # 2) path absolutos → basename
    for key in ("path", "file_path"):
        v = (data.get(key) or "").strip()
        if v:
            cands.append(_os.path.basename(v))

    # 3) relative_path → com e sem barra inicial
    rel = (data.get("relative_path") or "").strip()
    if rel:
        cands.append(rel.lstrip("/"))
        if not rel.startswith("/"):
            cands.append("/" + rel)

    # 4) por último, o nome local do arquivo enviado
    if uploaded_name:
        cands.append(_os.path.basename(uploaded_name))

    # remove duplicados mantendo ordem
    seen = set()
    uniq = []
    for c in cands:
        if c and c not in seen:
            uniq.append(c)
            seen.add(c)
    return uniq

def _try_profile(candidates: list[str], show_json=False) -> tuple[bool, str | None, dict | None, str | None]:
    """
    Tenta gerar o perfil usando cada candidato em ordem.
    Retorna: (ok, name_que_funcionou, json_resposta, erro_texto)
    """
    last_err = None
    for name in candidates:
        try:
            resp = _get(f"/profile/{name}", timeout=900)
            if resp.ok:
                j = resp.json()
                return True, name, j, None
            else:
                last_err = f"{resp.status_code} • {resp.text[:200]}"
        except Exception as e:
            last_err = str(e)
    return False, None, None, last_err

def _try_profile_show(candidates: list[str]) -> tuple[bool, str | None, dict | None, str | None]:
    last_err = None
    for name in candidates:
        try:
            resp = _get(f"/profile/show/{name}", timeout=120)
            if resp.ok:
                j = resp.json()
                return True, name, j, None
            else:
                last_err = f"{resp.status_code} • {resp.text[:200]}"
        except Exception as e:
            last_err = str(e)
    return False, None, None, last_err

def _try_agent_ask(candidates: list[str], question: str) -> tuple[bool, str | None, dict | None, str | None]:
    last_err = None
    for name in candidates:
        try:
            payload = {"dataset": name, "question": question}
            resp = _post_json("/agent/ask", payload, timeout=300)
            if resp.ok:
                j = resp.json()
                return True, name, j, None
            else:
                last_err = f"{resp.status_code} • {resp.text[:200]}"
        except Exception as e:
            last_err = str(e)
    return False, None, None, last_err

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
st.session_state.setdefault("dataset_name", None)          # nome que funcionou por último
st.session_state.setdefault("dataset_candidates", [])      # candidatos vindos do upload
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
                try:
                    data = resp.json()
                except Exception:
                    data = {"_raw_text": resp.text}

                st.success("Upload concluído.")
                st.code(json.dumps(data, indent=2, ensure_ascii=False), language="json")

                # 🔧 gera candidatos a nome reconhecido pelo backend
                cands = _candidates_from_upload(data, uploaded.name)
                if not cands:
                    st.error("O backend não retornou informações suficientes (filename/relative_path/file_path).")
                    st.stop()

                st.session_state.dataset_candidates = cands
                # não assumimos ainda qual funciona; apenas mostramos o primeiro como sugestão
                st.session_state.dataset_name = cands[0]
                st.info(f"Possíveis nomes do dataset: {cands}")
                st.success(f"Dataset sugerido: `{st.session_state.dataset_name}`")
            else:
                st.error(f"Falha no upload: {resp.status_code}")
                st.code(resp.text, language="text")

# ==============================
# 2) Perfil Global
# ==============================
st.subheader("2) Gerar / Ver Perfil Global")
st.caption(f"Dataset atual/sugerido: {st.session_state.get('dataset_name') or '—'}")

if not (st.session_state.dataset_name or st.session_state.dataset_candidates):
    st.info("Envie seu CSV primeiro.")
else:
    c1, c2 = st.columns([1, 1])

    with c1:
        st.markdown("**Gerar / Atualizar perfil (dataset inteiro)**")
        if st.button("🧮 Gerar perfil global agora"):
            if not backend_ok:
                st.warning("O backend parece offline. Clique em 'Acordar servidor' e tente de novo.")
            else:
                with st.spinner("Tentando gerar perfil (testando nomes possíveis)…"):
                    ok, used, out, err = _try_profile(st.session_state.dataset_candidates or [st.session_state.dataset_name])
                if ok:
                    st.session_state.dataset_name = used  # fixa o que funcionou
                    st.success(f"Perfil (re)gerado com sucesso usando `{used}`.")
                    st.code(json.dumps(out, indent=2, ensure_ascii=False))
                else:
                    st.error("Não consegui gerar o perfil com os nomes candidatos.")
                    if err:
                        st.code(str(err), language="text")
                    st.info(f"Candidatos testados: {st.session_state.dataset_candidates}")

    with c2:
        st.markdown("**Abrir perfil salvo (JSON)**")
        if st.button("📖 Ver perfil salvo"):
            if not backend_ok:
                st.warning("O backend parece offline. Clique em 'Acordar servidor' e tente de novo.")
            else:
                with st.spinner("Tentando abrir perfil salvo…"):
                    ok, used, saved, err = _try_profile_show(st.session_state.dataset_candidates or [st.session_state.dataset_name])
                if ok:
                    st.session_state.dataset_name = used
                    st.success(f"Perfil carregado usando `{used}`.")
                    st.code(json.dumps(saved, indent=2, ensure_ascii=False))
                else:
                    st.error("Não consegui abrir o perfil salvo com os nomes candidatos.")
                    if err:
                        st.code(str(err), language="text")
                    st.info(f"Candidatos testados: {st.session_state.dataset_candidates}")

# ==============================
# 3) Pergunte ao agente
# ==============================
st.subheader("3) Pergunte ao agente")
if not (st.session_state.dataset_name or st.session_state.dataset_candidates):
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
                with st.spinner("Consultando o agente (testando nomes possíveis)…"):
                    ok, used, ans, err = _try_agent_ask(st.session_state.dataset_candidates or [st.session_state.dataset_name], question)
                if ok and isinstance(ans, dict):
                    st.session_state.dataset_name = used
                    st.session_state.last_question = question
                    st.session_state.last_answer = ans.get("answer")
                    st.session_state.last_details = ans.get("details")
                    st.success(f"Resposta recebida usando `{used}`.")
                else:
                    st.error("Não consegui consultar o agente com os nomes candidatos.")
                    if err:
                        st.code(str(err), language="text")
                    st.info(f"Candidatos testados: {st.session_state.dataset_candidates}")

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