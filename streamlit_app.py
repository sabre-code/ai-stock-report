"""Streamlit UI — AI Stock Report Generator."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime

import httpx
import streamlit as st

# In Docker / ECS the API lives on a separate container reachable via
# the service name or internal ALB.  Override with the API_BASE env var.
API_BASE = os.getenv("API_BASE", "http://localhost:8000").rstrip("/")

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Stock Report",
    page_icon="📈",
    layout="centered",
)

# ── Styles ─────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .stage-row { display:flex; align-items:flex-start; gap:10px; margin:6px 0; }
    .stage-icon { font-size:1.2rem; min-width:26px; }
    .stage-text { font-size:0.93rem; color:#e0e0e0; line-height:1.4; }
    .stage-time { font-size:0.75rem; color:#888; margin-left:4px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("📈 AI Stock Report Generator")
st.markdown(
    "Enter a natural-language query or a ticker symbol and click **Generate**. "
    "Progress will appear live — a PDF will download when ready."
)

# ── Input form ─────────────────────────────────────────────────────────────────
with st.form("report_form", clear_on_submit=False):
    query = st.text_input(
        "Query",
        placeholder="Generate a report for Nvidia stock",
        help="Plain English is fine. We'll resolve the ticker automatically.",
    )
    ticker = st.text_input(
        "Ticker (optional)",
        placeholder="NVDA",
        help="Skip ticker resolution by providing it directly.",
    )
    submitted = st.form_submit_button("Generate Report", use_container_width=True)

# ── Stage icons ────────────────────────────────────────────────────────────────
STAGE_ICONS: dict[str, str] = {
    "job_start": "🚀",
    "ticker_resolve": "🔍",
    "research": "📡",
    "report": "✍️",
    "complete": "✅",
    "error": "❌",
}

DEFAULT_ICON = "⏳"


def _icon(stage: str) -> str:
    return STAGE_ICONS.get(stage, DEFAULT_ICON)


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


# ── Main execution ─────────────────────────────────────────────────────────────
if submitted:
    if not query.strip():
        st.warning("Please enter a query.")
        st.stop()

    params: dict[str, str] = {"query": query.strip()}
    if ticker.strip():
        params["ticker"] = ticker.strip().upper()

    # Placeholder containers
    progress_box = st.container()
    progress_box.markdown("#### Live Progress")
    progress_placeholder = progress_box.empty()

    status_placeholder = st.empty()
    download_placeholder = st.empty()

    events: list[dict] = []
    job_id: str | None = None
    had_error = False

    def render_events() -> None:
        """Re-render the full event list inside the placeholder."""
        lines = []
        for ev in events:
            stage = ev.get("stage", "info")
            msg = ev.get("message", "")
            ts = ev.get("ts", "")
            icon = _icon(stage)
            lines.append(
                f'<div class="stage-row">'
                f'<span class="stage-icon">{icon}</span>'
                f'<span class="stage-text">{msg}'
                f'<span class="stage-time">{ts}</span></span></div>'
            )
        progress_placeholder.markdown("\n".join(lines), unsafe_allow_html=True)

    status_placeholder.info("Connecting to report API…")

    try:
        url = f"{API_BASE}/reports/stream"
        with httpx.Client(timeout=None) as client:
            with client.stream("GET", url, params=params) as response:
                response.raise_for_status()
                status_placeholder.info("Generating report — please wait…")

                buffer = ""
                current_event_type = "message"

                for raw_line in response.iter_lines():
                    line = raw_line.strip()

                    if line.startswith("event:"):
                        current_event_type = line[len("event:"):].strip()
                        continue

                    if line.startswith("data:"):
                        raw_data = line[len("data:"):].strip()
                        try:
                            data = json.loads(raw_data)
                        except json.JSONDecodeError:
                            continue

                        if current_event_type == "job_start":
                            job_id = data.get("job_id")
                            events.append(
                                {"stage": "job_start", "message": "Job started", "ts": _ts()}
                            )
                        else:
                            stage = data.get("stage", current_event_type)
                            message = data.get("message", "")
                            events.append({"stage": stage, "message": message, "ts": _ts()})

                            if stage == "error":
                                had_error = True
                            elif data.get("done"):
                                pass  # handled below after loop

                        render_events()
                        current_event_type = "message"

                        # Stop if last event was terminal
                        if events and events[-1]["stage"] in ("complete", "error"):
                            break

    except httpx.ConnectError:
        st.error(
            "Cannot connect to the API server. "
            "Make sure it is running: `uv run ai-stock-report-api`"
        )
        st.stop()
    except httpx.HTTPStatusError as exc:
        st.error(f"API returned an error: {exc.response.status_code} — {exc.response.text}")
        st.stop()

    # ── Post-stream results ────────────────────────────────────────────────────
    if had_error:
        error_msg = next(
            (e["message"] for e in reversed(events) if e["stage"] == "error"), "Unknown error"
        )
        status_placeholder.error(f"Report generation failed: {error_msg}")
    elif job_id:
        status_placeholder.success("Report generated successfully!")

        # Fetch the PDF bytes for the download button
        try:
            pdf_resp = httpx.get(
                f"{API_BASE}/reports/{job_id}/download", timeout=60
            )
            pdf_resp.raise_for_status()
            pdf_bytes = pdf_resp.content
            # Try to derive a nice filename from the events
            ticker_name = params.get("ticker", "stock").upper()
            download_placeholder.download_button(
                label="⬇️ Download PDF Report",
                data=pdf_bytes,
                file_name=f"{ticker_name}_stock_report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 202:
                status_placeholder.warning(
                    "PDF is still being finalised. Refresh the page in a moment."
                )
            else:
                status_placeholder.error(
                    f"Could not download the PDF: {exc.response.status_code}"
                )
        except Exception as exc:
            status_placeholder.error(f"Download failed: {exc}")
    else:
        status_placeholder.warning("No job_id received. The stream may have been empty.")

