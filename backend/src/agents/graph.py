"""Graph LangGraph của luồng P-113 (khớp sơ đồ kiến trúc):

NL → E1 planner ⇄ J1 clarify → V0 spec_check → J1b plan_review (DE duyệt kế hoạch) → E0 ingest → P profiler → E2 mock_data → E3 codegen → E3b testgen
→ V1 safety → V2 sandbox_run (≤3 lần sửa, lỗi lặp → cứu hộ) → E4 optimizer ⇄ V3 compare → package → J2 review.
"""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer

from src.agents import routing
from src.agents.nodes.clarify import clarify_node
from src.agents.nodes.codegen import codegen_node
from src.agents.nodes.compare import compare_node
from src.agents.nodes.ingest import ingest_node
from src.agents.nodes.mock_data import mock_data_node
from src.agents.nodes.optimizer import optimizer_node
from src.agents.nodes.package import package_node
from src.agents.nodes.plan_review import plan_review_node
from src.agents.nodes.planner import planner_node
from src.agents.nodes.profiler import profiler_node
from src.agents.nodes.rescue import rescue_node
from src.agents.nodes.review import fail_node, finalize_node, review_node
from src.agents.nodes.safety import safety_node
from src.agents.nodes.sandbox_run import sandbox_run_node
from src.agents.nodes.spec_check import spec_check_node
from src.agents.nodes.testgen import testgen_node
from src.agents.state import PipelineState

NODES = {
    "planner": planner_node,
    "clarify": clarify_node,
    "spec_check": spec_check_node,
    "plan_review": plan_review_node,
    "ingest": ingest_node,
    "profiler": profiler_node,
    "mock_data": mock_data_node,
    "codegen": codegen_node,
    "testgen": testgen_node,
    "safety": safety_node,
    "sandbox_run": sandbox_run_node,
    "rescue": rescue_node,
    "optimizer": optimizer_node,
    "compare": compare_node,
    "package": package_node,
    "review": review_node,
    "finalize": finalize_node,
    "fail": fail_node,
}
CONDITIONAL = {
    "planner": routing.after_planner,
    "spec_check": routing.after_spec_check,
    "plan_review": routing.after_plan_review,
    "ingest": routing.after_ingest,
    "safety": routing.after_safety,
    "sandbox_run": routing.after_sandbox,
    "rescue": routing.after_rescue,
    "optimizer": routing.after_optimizer,
    "compare": routing.after_compare,
    "review": routing.after_review,
}
EDGES = [
    (START, "planner"),
    ("clarify", "planner"),
    ("profiler", "mock_data"),
    ("mock_data", "codegen"),
    ("codegen", "testgen"),
    ("testgen", "safety"),
    ("package", "review"),
    ("finalize", END),
    ("fail", END),
]


def build_graph(checkpointer: Checkpointer = None) -> CompiledStateGraph:
    """Dựng và biên dịch graph; cần checkpointer để tạm dừng ở J1/J1b/J2/cứu hộ rồi chạy tiếp."""
    graph = StateGraph(PipelineState)
    for name, node in NODES.items():
        graph.add_node(name, node)
    for source, target in EDGES:
        graph.add_edge(source, target)
    for source, router in CONDITIONAL.items():
        graph.add_conditional_edges(source, router)
    return graph.compile(checkpointer=checkpointer)
