import pytest

from app.live_onboarding import (
    CASES,
    SESSION_TO_CASE,
    artifact_response,
    create_live_case,
    mark_document_signed,
    mark_hardware_delivered,
)


class FakeSessionService:
    def __init__(self) -> None:
        self.created_sessions: dict[tuple[str, str], dict] = {}

    async def create_session(self, **kwargs) -> None:
        key = (kwargs["user_id"], kwargs["session_id"])
        self.created_sessions[key] = kwargs

    async def get_session(self, user_id: str, session_id: str) -> any:
        from dataclasses import dataclass
        @dataclass
        class FakeSession:
            state: dict

        session_data = self.created_sessions.get((user_id, session_id))
        return FakeSession(state=session_data["state"])


class FakeRunner:
    def __init__(self, session_service) -> None:
        self.session_service = session_service

    def run_async(self, user_id: str, session_id: str, **kwargs) -> any:
        # Simulate screening tool execution
        session_data = self.session_service.created_sessions[(user_id, session_id)]
        state = session_data["state"]

        if state["current_step"] == "START":
            state["current_step"] = "SCREENING_COMPLETED"
            state["screening_report"] = {
                "overall_match_score": 85,
                "summary": "Mock summary",
                "strengths": ["Mock strength"],
                "gaps": ["Mock gap"],
                "recommendation": "Shortlist"
            }

        # We need to return an async iterator
        class AsyncIter:
            def __aiter__(self): return self
            async def __anext__(self): raise StopAsyncIteration

        return AsyncIter()


class FakeResumeHandler:
    def __init__(self, runner) -> None:
        self.runner = runner
        self.signed_calls: list[tuple[str, str]] = []
        self.hardware_calls: list[tuple[str, str, str]] = []

    async def receive_manager_decision_callback(
        self, user_id: str, session_id: str, decision: str
    ) -> None:
        self.signed_calls.append((user_id, session_id))
        session_data = self.runner.session_service.created_sessions[(user_id, session_id)]
        state = session_data["state"]
        if decision == "APPROVE":
            state["current_step"] = "APPROVED" # This will then transition to SCHEDULING_COMPLETED by agent instruction, but for mock we'll just set it
            state["current_step"] = "SCHEDULING_COMPLETED"

    async def receive_signed_documents_callback(
        self, user_id: str, session_id: str
    ) -> None:
        await self.receive_manager_decision_callback(user_id, session_id, "APPROVE")

    async def receive_hardware_delivery_callback(
        self, user_id: str, session_id: str, tracking_id: str
    ) -> None:
        self.hardware_calls.append((user_id, session_id, tracking_id))
        session_data = self.runner.session_service.created_sessions[(user_id, session_id)]
        state = session_data["state"]
        state["current_step"] = "COMPLETED"


@pytest.fixture(autouse=True)
def clear_live_state() -> None:
    CASES.clear()
    SESSION_TO_CASE.clear()


@pytest.mark.asyncio
async def test_create_live_case_generates_unsigned_packet() -> None:
    session_service = FakeSessionService()
    runner = FakeRunner(session_service)

    case = await create_live_case(session_service, runner)

    assert case.status == "waiting_for_manager_decision"
    assert case.current_step == "SCREENING_COMPLETED"
    assert case.pending_signals == ["manager_decision"]
    assert [artifact["id"] for artifact in case.artifacts] == ["screening-report"]
    assert session_service.created_sessions[(case.user_id, case.session_id)]["session_id"] == case.session_id
    assert (
        "Candidate Screening Report"
        in artifact_response(case.id, "screening-report").body.decode()
    )


@pytest.mark.asyncio
async def test_signature_resume_stores_signed_packet_and_waits_for_hardware() -> None:
    session_service = FakeSessionService()
    runner = FakeRunner(session_service)
    case = await create_live_case(session_service, runner)
    resume_handler = FakeResumeHandler(runner)

    await mark_document_signed(case, resume_handler)

    assert case.document_signed is True
    assert case.status == "waiting_for_interview_booking"
    assert case.current_step == "SCHEDULING_COMPLETED"
    assert case.pending_signals == ["hardware_delivered"]
    assert resume_handler.signed_calls == [(case.user_id, case.session_id)]
    assert [artifact["id"] for artifact in case.artifacts] == [
        "approved-report",
        "screening-report",
    ]
    assert "APPROVED BY HIRING MANAGER" in artifact_response(case.id, "approved-report").body.decode()


@pytest.mark.asyncio
async def test_hardware_resume_creates_receipt_then_day_one_schedule() -> None:
    session_service = FakeSessionService()
    runner = FakeRunner(session_service)
    case = await create_live_case(session_service, runner)
    resume_handler = FakeResumeHandler(runner)
    await mark_document_signed(case, resume_handler)

    await mark_hardware_delivered(case, resume_handler)

    assert case.hardware_delivered is True
    assert case.status == "completed"
    assert case.current_step == "COMPLETED"
    assert case.pending_signals == []
    assert resume_handler.hardware_calls == [
        (case.user_id, case.session_id, case.employee["tracking_id"])
    ]
    assert [artifact["id"] for artifact in case.artifacts] == [
        "day-one-schedule",
        "hardware-receipt",
        "approved-report",
        "screening-report",
    ]
    assert (
        "Interview Booking Confirmation"
        in artifact_response(case.id, "hardware-receipt").body.decode()
    )
    assert (
        "Interview Schedule"
        in artifact_response(case.id, "day-one-schedule").body.decode()
    )
