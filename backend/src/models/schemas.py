"""Schema dùng chung: trạng thái lần chạy, bản ghi lưu trữ, thống kê LLM, schema API."""

from enum import StrEnum

from pydantic import BaseModel, Field


class RunStatus(StrEnum):
    """Trạng thái một lần chạy (lưu trong store)."""

    RUNNING = "running"
    WAITING_CLARIFICATION = "waiting_clarification"
    WAITING_PLAN = "waiting_plan_review"
    WAITING_RESCUE = "waiting_rescue"
    WAITING_REVIEW = "waiting_review"
    APPROVED = "approved"
    FAILED = "failed"


class RunRecord(BaseModel):
    """Một lần chạy pipeline-agent."""

    id: str
    request_text: str
    requester: str
    status: RunStatus
    provider: str
    model: str
    created_at: str
    updated_at: str
    summary: dict = Field(default_factory=dict)


class LLMUsage(BaseModel):
    """Thống kê một lần gọi LLM (phục vụ eval chi phí)."""

    task: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    simulated: bool = False


class HealthResponse(BaseModel):
    """Phản hồi của `/health`."""

    status: str
    timestamp: str
    version: str
    env: str
    database: str
    llm_provider: str
