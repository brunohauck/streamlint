import os
import json
import time
from urllib.parse import urljoin
import requests
import streamlit as st

# ==============================
# Configurações
# ==============================
# Default: URL do backend no Render; pode sobrescrever via ENV/Secrets: API_URL="https://..."
API_URL = os.getenv(
    "API_URL",
    "https://backend-desafio5-agente-autonomos.onrender.com"
).rstrip("/")

st.set_page_config(
    page_title="Agente EDA Autônomo",
    page_icon="🧠",
    layout="wide",
)

# ==============================
# Helpers
# ==============================
def _abs_url(base: str, maybe_path: str | None) -> str | None:
    """Monta URL absoluta para /static/... ou retorna se já for absoluta."""
    if not maybe_path:
        return None
    if maybe_path.startswith(("http://", "https://")):
        return maybe_path
    return urljoin(base + "/", maybe_path.lstrip("/"))

def _post_json(path: str, payload: dict, timeout=120):
    url = f"{API_URL}{path}"
    return requests.post(url, json=payload, timeout=timeout)

def _get(path: str, timeout=120, params: dict | None = None):
    url = f"{API_URL}{path}"
    return requests.get(url, timeout=timeout, params=params)

def _upload_csv(file):
    files = {"file": (file.name, file, "text/csv")}
    return requests.post(f"{API_URL}/upload/", files=files, timeout=300)

def _upload_from_url(csv_url: str, filename: str):
    # esta rota espera parâmetros na querystring
    return requests.post(
        f"{API_URL}/upload/from_url",
        params={"url": csv_url, "filename": filename},
        timeout=600
    )

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

def _wake_server(max_wait_sec: int = 90, interval_sec: float = 2.5):
    """Faz ping em /health até ficar online ou expirar o tempo."""
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
# Header com botão "Acordar"
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

col_top1, col_top2 = st.columns([1, 4])
with col_top1:
    if st.button("🚀 Acordar servidor"):
        with st.spinner("Acordando o backend no Render (pode levar alguns segundos)…"):
            ok, msg = _wake_server()
        if ok:
            st.success(msg)
        else:
            st.warning(msg)
with col_top2:
    st.caption("Se o backend estiver em sleep, clique no botão acima antes de usar o app.")

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
        "- Faça upload do CSV (ou importe por URL) e gere o **perfil global**.\n"
        "- Exemplos de pedidos de gráfico: *'histograma de Amount (log)'*, *'heatmap de correlação'*, "
        "*'série temporal'*, *'boxplot por Class'*, *'scatter V1 vs V2'*. "
    )
    st.markdown("---")
    st.caption("Agente EDA • Streamlit Frontend")

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
# Seção 1: Upload / Import
# ==============================
st.subheader("1) Upload ou Importação do CSV")

tab_up, tab_url = st.tabs(["📤 Upload local", "🌐 Importar por URL"])

with tab_up:
    uploaded = st.file_uploader("Escolha seu arquivo CSV (ex.: creditcard.csv)", type=["csv"])
    col_u1, col_u2 = st.columns([1, 3])

    with col_u1:
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

with tab_url:
    st.write("Importe direto de uma URL pública (o backend baixa no servidor; ideal para arquivos grandes).")
    col_i1, col_i2 = st.columns([3, 1])
    with col_i1:
        csv_url = st.text_input("URL direta do CSV", placeholder="https://exemplo.com/creditcard.csv")
        csv_name = st.text_input("Nome do arquivo destino no servidor", value="creditcard.csv")
    with col_i2:
        if st.button("🌐 Importar do link"):
            if not backend_ok:
                st.warning("O backend parece offline. Clique em 'Acordar servidor' e tente de novo.")
            elif not csv_url:
                st.warning("Informe a URL direta para o CSV.")
            else:
                with st.spinner("Baixando no servidor…"):
                    resp = _upload_from_url(csv_url, csv_name)
                if resp.ok:
                    data = resp.json()
                    st.success(f"Importado: `{data.get('filename')}` • {_human_bytes(data.get('size',0))}")
                    st.session_state.dataset_name = data.get("filename")
                else:
                    st.error(f"Falha na importação: {resp.status_code} • {resp.text}")

# ==============================
# Seção 2: Perfil Global
# ==============================
st.subheader("2) Gerar / Ver Perfil Global")

if not st.session_state.dataset_name:
    st.info("Defina um dataset primeiro (upload, importação por URL ou manual).")
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
# Seção 3: Perguntas ao Agente (LLM)
# ==============================
st.subheader("3) Pergunte ao agente")

if st.session_state.dataset_name:
    default_q = "Explique o valor médio de Amount e a taxa de fraude; indique que gráfico eu deveria ver."
    question = st.text_area("Sua pergunta:", value=default_q, height=120)

    c_ask1, c_ask2 = st.columns([1, 3])
    with c_ask1:
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

    with c_ask2:
        st.caption("Dica: peça gráficos (ex.: 'histograma de Amount (log)'), correlações, outliers, tendência temporal etc.")

    # Exibir resposta
    if st.session_state.last_answer:
        st.markdown("#### Resposta")
        st.write(st.session_state.last_answer)

    # Mostrar gráfico principal (plot_url)
    if st.session_state.last_details and isinstance(st.session_state.last_details, dict):
        url_rel = st.session_state.last_details.get("plot_url")
        url_abs = _abs_url(API_URL, url_rel) if url_rel else None
        if url_abs:
            st.image(url_abs, caption="Gráfico gerado pelo agente")
        else:
            direct_path = st.session_state.last_details.get("plot_path")
            if direct_path:
                # Em Cloud, path local do servidor não é acessível; mostramos só em ambiente local
                try:
                    st.image(direct_path, caption="Gráfico gerado pelo agente")
                except Exception:
                    pass

    # Mostrar vários gráficos, se vierem (plot_paths)
    if st.session_state.last_details and isinstance(st.session_state.last_details, dict):
        many = st.session_state.last_details.get("plot_paths")
        if many and isinstance(many, list) and len(many) > 0:
            st.markdown("#### Gráficos gerados")
            cols = st.columns(2)
            for i, p in enumerate(many):
                url_abs = _abs_url(API_URL, p) if isinstance(p, str) and p.startswith("/static/") else None
                with cols[i % 2]:
                    if url_abs:
                        st.image(url_abs, caption=os.path.basename(p))
                    else:
                        try:
                            st.image(p, caption=os.path.basename(p))
                        except Exception:
                            st.caption(p)

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
                        f"/plot/amount_hist/{st.session_state.dataset_name}",
                        params={"bins": plot.get("bins", 50), "log": plot.get("log", True)}
                    )
                    if r.ok:
                        j = r.json()
                        url = _abs_url(API_URL, j.get("plot_url"))
                        st.image(url or j.get("plot_path"), caption="Histograma de Amount (gerado pelo backend)")
                elif plot.get("type") == "timeseries":
                    r = _get(
                        f"/plot/time_series/{st.session_state.dataset_name}",
                        params={"bins": plot.get("bins", 120)}
                    )
                    if r.ok:
                        j = r.json()
                        url = _abs_url(API_URL, j.get("plot_url"))
                        st.image(url or j.get("plot_path"), caption="Série temporal (gerada pelo backend)")
                elif plot.get("type") == "corr_heatmap":
                    r = _get(
                        f"/plot/corr_heatmap/{st.session_state.dataset_name}",
                        params={"sample_rows": plot.get("sample_rows", 50000)}
                    )
                    if r.ok:
                        j = r.json()
                        url = _abs_url(API_URL, j.get("plot_url"))
                        st.image(url or j.get("plot_path"), caption="Heatmap de correlação (gerado pelo backend)")
                elif plot.get("type") == "box_amount_by_class":
                    r = _get(
                        f"/plot/box_amount_by_class/{st.session_state.dataset_name}",
                        params={"max_per_class": plot.get("max_per_class", 20000)}
                    )
                    if r.ok:
                        j = r.json()
                        url = _abs_url(API_URL, j.get("plot_url"))
                        st.image(url or j.get("plot_path"), caption="Boxplot Amount por Classe (gerado pelo backend)")
                elif plot.get("type") == "scatter":
                    r = _get(
                        f"/plot/scatter_pca/{st.session_state.dataset_name}",
                        params={
                            "x": plot.get("x", "V1"),
                            "y": plot.get("y", "V2"),
                            "sample_rows": plot.get("sample_rows", 50000),
                        }
                    )
                    if r.ok:
                        j = r.json()
                        url = _abs_url(API_URL, j.get("plot_url"))
                        st.image(url or j.get("plot_path"),
                                 caption=f"Scatter {plot.get('x','V1')} vs {plot.get('y','V2')} (gerado pelo backend)")
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