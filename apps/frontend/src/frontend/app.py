"""Streamlit GUI: thin client over the copilot API. Imports nothing from copilot
(enforced by import-linter). Walking-skeleton slice (02-phases.md Phase 2.5): chat
input, streamed answer, trace + citations rendered after the stream completes (R-08).
Phase 10 adds KPI cards, trend charts, the ranked table, exports, and the five
loading/error/empty/degraded/evidence-gap states.
"""

from __future__ import annotations

import os
import uuid

import streamlit as st

from frontend.api_client import stream_chat

COPILOT_API_URL = os.environ.get("COPILOT_API_URL", "http://localhost:8080")
COPILOT_API_KEY = os.environ.get("COPILOT_API_KEY")
GUI_TITLE = os.environ.get("GUI_TITLE", "Alarm Rationalization Copilot")

st.set_page_config(page_title=GUI_TITLE, layout="wide")
st.title(GUI_TITLE)

if "history" not in st.session_state:
    st.session_state.history = []

for turn in st.session_state.history:
    with st.chat_message("user"):
        st.write(turn["question"])
    with st.chat_message("assistant"):
        st.write(turn["answer"])
        if turn["tools"]:
            st.caption("MCP execution trace")
            st.dataframe(turn["tools"], use_container_width=True)
        if turn["citations"]:
            st.caption("Citations")
            for citation in turn["citations"]:
                st.markdown(f"- {citation['rendered']} (score: {citation['score']:.2f})")

question = st.chat_input("Ask about alarms, rationalization, or compliance...")

if question:
    with st.chat_message("user"):
        st.write(question)

    trace_id = str(uuid.uuid4())
    tool_events: list[dict] = []
    citation_events: list[dict] = []
    answer = ""

    with st.spinner("Working..."):
        try:
            for chat_event in stream_chat(
                COPILOT_API_URL, question=question, trace_id=trace_id, api_key=COPILOT_API_KEY
            ):
                if chat_event["event"] == "tool":
                    tool_events.append(chat_event["data"])
                elif chat_event["event"] == "citation":
                    citation_events.append(chat_event["data"])
                elif chat_event["event"] == "done":
                    answer = chat_event["data"]["answer"]
        except Exception as exc:
            st.error(f"Request failed (trace_id={trace_id}): {exc}")
            st.stop()

    with st.chat_message("assistant"):
        st.write(answer)
        if tool_events:
            st.caption("MCP execution trace")
            st.dataframe(tool_events, use_container_width=True)
        if citation_events:
            st.caption("Citations")
            for citation in citation_events:
                st.markdown(f"- {citation['rendered']} (score: {citation['score']:.2f})")

    st.session_state.history.append(
        {"question": question, "answer": answer, "tools": tool_events, "citations": citation_events}
    )
