"""Walking-skeleton graph (02-phases.md Phase 2.5): plan (hardcoded AnalysisPlan) ->
execute_mcp -> retrieve_rag -> synthesize (stub LLM). Phase 8 replaces the hardcoded
plan with LlmPlanner/RuleBasedPlanner, adds the evaluate + interrupt/approval nodes, and
wires a PostgresSaver checkpointer -- all on top of this same four-node thread.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from copilot.graph.state import CopilotState
from copilot.llm.port import LLMPort
from copilot.mcp.registry import McpToolRegistry
from copilot.planning.models import AnalysisPlan, PlanStep
from copilot.rag.service import RagService


def build_graph(
    registry: McpToolRegistry, rag_service: RagService, llm: LLMPort
) -> CompiledStateGraph:
    graph: StateGraph[CopilotState] = StateGraph(CopilotState)

    async def plan_node(state: CopilotState) -> dict:
        plan = AnalysisPlan(
            steps=[PlanStep(tool_name="search_assets", arguments={"query": state["question"]})]
        )
        return {"plan": plan}

    async def execute_mcp_node(state: CopilotState) -> dict:
        plan = state["plan"]
        assert plan is not None
        invocations = [
            await registry.call_tool(step.tool_name, step.arguments, trace_id=state["trace_id"])
            for step in plan.steps
        ]
        return {"invocations": invocations}

    async def retrieve_rag_node(state: CopilotState) -> dict:
        citations = rag_service.retrieve(state["question"])
        return {"citations": citations}

    async def synthesize_node(state: CopilotState) -> dict:
        tool_summary = "; ".join(
            f"{inv.tool_name} -> {'ok' if inv.ok else 'failed'}" for inv in state["invocations"]
        )
        citation_summary = "; ".join(c.rendered() for c in state["citations"])
        prompt = (
            f"Question: {state['question']}\n"
            f"Tool results: {tool_summary}\n"
            f"Citations: {citation_summary}"
        )
        answer = await llm.generate(prompt)
        return {"answer": answer}

    graph.add_node("plan", plan_node)
    graph.add_node("execute_mcp", execute_mcp_node)
    graph.add_node("retrieve_rag", retrieve_rag_node)
    graph.add_node("synthesize", synthesize_node)

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "execute_mcp")
    graph.add_edge("execute_mcp", "retrieve_rag")
    graph.add_edge("retrieve_rag", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()
