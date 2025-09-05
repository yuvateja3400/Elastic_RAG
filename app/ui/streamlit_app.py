# ui/streamlit_app.py
import os
import requests
import textwrap
import streamlit as st

st.set_page_config(page_title="Elastic RAG", page_icon="📚", layout="wide")

# ---- Config ----
DEFAULT_API_BASE = os.getenv("RAG_API_BASE", "http://localhost:8000")

# ---- Helpers ----
def api_base() -> str:
    return st.session_state.get("api_base", DEFAULT_API_BASE).rstrip("/")

def healthcheck():
    try:
        r = requests.get(f"{api_base()}/healthz", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def call_query(q: str, mode: str, k: int):
    payload = {"q": q, "k": int(k), "mode": mode}
    r = requests.post(f"{api_base()}/query", json=payload, timeout=120)
    r.raise_for_status()
    return r.json()

def call_ingest(limit: int = 20, reindex: bool = True):
    payload = {"limit": int(limit), "reindex": bool(reindex)}
    r = requests.post(f"{api_base()}/ingest", json=payload, timeout=3600)
    r.raise_for_status()
    return r.json()

def short_snippet(cite: dict, max_len: int = 240) -> str:
    s = cite.get("snippet") or cite.get("text") or ""
    s = " ".join(s.split())
    return (s[:max_len] + "…") if len(s) > max_len else s

# ---- Sidebar ----
with st.sidebar:
    st.markdown("## ⚙️ Settings")
    st.text_input("API Base URL", value=DEFAULT_API_BASE, key="api_base")
    mode_label = st.radio("Retrieval mode", ["Hybrid", "ELSER-only"], index=0, horizontal=True)
    mode = "hybrid" if mode_label == "Hybrid" else "elser"
    k = st.slider("K (top documents)", min_value=1, max_value=20, value=5, step=1)

    st.markdown("---")
    st.markdown("### 🩺 Health")
    hc = healthcheck()
    if "error" in hc:
        st.error(f"API unreachable: {hc['error']}")
    else:
        es_ok = hc.get("elasticsearch")
        ol_ok = hc.get("ollama")
        st.write(f"Elasticsearch: {'✅' if es_ok else '❌'}  |  Ollama: {'✅' if ol_ok else '❌'}")

    with st.expander("Re-ingest (optional)"):
        limit = st.number_input("Limit", min_value=1, max_value=1000, value=20, step=1)
        do_reindex = st.checkbox("Reindex (apply pipelines)", value=True)
        if st.button("Run ingest"):
            with st.spinner("Ingesting…"):
                try:
                    resp = call_ingest(limit=limit, reindex=do_reindex)
                    st.success("Ingest kicked off / completed")
                    st.json(resp)
                except requests.HTTPError as e:
                    st.error(f"Ingest failed: {e.response.text}")
                except Exception as e:
                    st.error(f"Ingest failed: {e}")

# ---- Main ----
st.title("📚 Elastic RAG — QA")
st.caption("Ask a question about your indexed documents. Answers are generated via your local Ollama model and citations are pulled from Elasticsearch.")

with st.form("ask"):
    q = st.text_area("Your question", height=100, placeholder="e.g. Who are the main characters in Two Little Soldiers?")
    submitted = st.form_submit_button("Ask")
    if submitted:
        if not q.strip():
            st.warning("Please enter a question.")
        else:
            with st.spinner("Thinking…"):
                try:
                    out = call_query(q=q.strip(), mode=mode, k=k)
                except requests.HTTPError as e:
                    st.error(f"API error: {e.response.text}")
                    st.stop()
                except Exception as e:
                    st.error(f"Request failed: {e}")
                    st.stop()

            # Render answer
            answer = out.get("answer", "")
            citations = out.get("citations", [])

            st.markdown("### ✅ Answer")
            if answer:
                st.markdown(answer)
            else:
                st.info("No answer returned.")

            # Render citations
            st.markdown("### 🔗 Citations")
            if not citations:
                st.caption("No citations returned.")
            else:
                for i, c in enumerate(citations, start=1):
                    title = c.get("filename") or c.get("title") or f"Citation {i}"
                    url = c.get("drive_url") or c.get("url") or c.get("link") or "#"
                    page_range = None
                    ps, pe = c.get("page_start"), c.get("page_end")
                    if ps and pe:
                        page_range = f"(pp. {ps}–{pe})" if ps != pe else f"(p. {ps})"

                    meta_bits = []
                    if page_range: meta_bits.append(page_range)
                    chunk_id = c.get("chunk_id")
                    if chunk_id: meta_bits.append(f"chunk {chunk_id}")

                    meta = "  •  ".join(meta_bits) if meta_bits else ""
                    left, right = st.columns([0.75, 0.25])

                    with left:
                        st.markdown(f"**[{title}]({url})**  {meta}")
                        snip = short_snippet(c)
                        if snip:
                            st.markdown("> " + textwrap.fill(snip, 100))

                    with right:
                        if url and url != "#":
                            st.link_button("Open", url)

                with st.expander("Raw response"):
                    st.json(out)
