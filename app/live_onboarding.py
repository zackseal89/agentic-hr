import html
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from fastapi.responses import HTMLResponse

from app.state_schema import OnboardingStep


@dataclass
class LiveOnboardingCase:
    id: str
    session_id: str
    user_id: str
    employee: dict[str, str]
    current_step: str = OnboardingStep.SCREENING_COMPLETED
    pending_signals: list[str] = field(default_factory=lambda: ["document_signed"])
    status: str = "waiting_for_manager_decision"
    document_signed: bool = False
    hardware_delivered: bool = False
    adk_status: str = "session_ready"
    events: list[dict[str, str]] = field(default_factory=list)
    artifacts: list[dict[str, str]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


CASES: dict[str, LiveOnboardingCase] = {}
SESSION_TO_CASE: dict[str, str] = {}
LATEST_CASE_ID: str | None = None


def static_root() -> Path:
    return Path(__file__).parent / "static"


def artifact_root() -> Path:
    path = Path(__file__).resolve().parents[1] / "local_artifacts" / "onboarding"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _employee() -> dict[str, str]:
    return {
        "name": "Olivia Bennett",
        "email": "olivia.bennett@example.com",
        "start_date": "2026-06-15",
        "role": "Product Manager",
        "team": "Platform Systems",
        "manager": "Avery Stone",
        "corporate_email": "olivia.bennett@example.com",
        "tracking_id": "INT-55443",
        "photo_url": "/live-onboarding/olivia-bennett.jpg",
    }


def _case_dir(case_id: str) -> Path:
    path = artifact_root() / case_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _event(case: LiveOnboardingCase, kind: str, title: str, detail: str) -> None:
    case.events.insert(
        0,
        {
            "kind": kind,
            "title": title,
            "detail": detail,
            "time": time.strftime("%H:%M:%S"),
        },
    )
    case.updated_at = time.time()


def _artifact(
    case: LiveOnboardingCase, artifact_id: str, title: str, kind: str, filename: str
) -> None:
    href = f"/api/live-onboarding/cases/{case.id}/artifacts/{artifact_id}"
    existing = next(
        (item for item in case.artifacts if item["id"] == artifact_id), None
    )
    payload = {
        "id": artifact_id,
        "title": title,
        "kind": kind,
        "filename": filename,
        "href": href,
        "created_at": time.strftime("%H:%M:%S"),
    }
    if existing:
        existing.update(payload)
    else:
        case.artifacts.insert(0, payload)


def _packet_html(case: LiveOnboardingCase, signed: bool = False) -> str:
    employee = case.employee
    status_label = (
        "APPROVED BY HIRING MANAGER" if signed else "PENDING MANAGER REVIEW"
    )
    signed_at = time.strftime("%Y-%m-%d %H:%M:%S %Z") if signed else ""
    signature_class = "signed" if signed else "pending"
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Candidate Screening Report - {html.escape(employee["name"])}</title>
    <style>
      :root {{
        color-scheme: dark;
        --canvas: #12110e;
        --panel: #1f1e19;
        --panel-soft: #181713;
        --ink: #f4f1e8;
        --muted: #c8c2b6;
        --quiet: #989184;
        --line: #343229;
        --line-strong: #514e43;
        --accent: #f54e00;
        --green: #58b991;
      }}
      body {{
        margin: 0;
        padding: clamp(14px, 4vw, 34px);
        color: var(--ink);
        font-family: Inter, system-ui, "Helvetica Neue", Arial, sans-serif;
        background: var(--canvas);
      }}
      main {{
        max-width: 820px;
        margin: 0 auto;
        padding: clamp(18px, 4vw, 30px);
        border: 1px solid var(--line);
        border-radius: 12px;
        background: var(--panel);
      }}
      header {{
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        align-items: flex-start;
        gap: 20px;
        border-bottom: 1px solid var(--line-strong);
        padding-bottom: 18px;
      }}
      h1 {{
        margin: 0;
        font-size: clamp(22px, 4vw, 28px);
        letter-spacing: 0;
        line-height: 1.18;
      }}
      h2 {{
        margin: 24px 0 8px;
        font-size: 16px;
        color: var(--accent);
      }}
      p, li {{
        font-size: 13px;
        line-height: 1.55;
      }}
      p, li, .signature {{
        color: var(--muted);
      }}
      .meta {{
        color: var(--quiet);
        font-family: ui-sans-serif, system-ui, sans-serif;
        font-size: 12px;
        line-height: 1.5;
        text-align: right;
        overflow-wrap: anywhere;
      }}
      .terms {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
        margin: 18px 0;
      }}
      .term {{
        border: 1px solid var(--line);
        padding: 12px;
        font-family: ui-sans-serif, system-ui, sans-serif;
        background: var(--panel-soft);
      }}
      .term span {{
        display: block;
        color: var(--quiet);
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
      }}
      .term strong {{
        display: block;
        margin-top: 5px;
        font-size: 14px;
        overflow-wrap: anywhere;
      }}
      .signature {{
        margin-top: 24px;
        border: 1px solid var(--line);
        padding: 14px;
        font-family: ui-sans-serif, system-ui, sans-serif;
      }}
      .signature strong {{
        display: block;
        margin-top: 8px;
        color: var(--green);
        font-size: clamp(20px, 4vw, 24px);
        font-weight: 700;
        letter-spacing: 1px;
      }}
      .signature.signed {{
        border-color: rgba(88, 185, 145, 0.45);
        background: #18251d;
      }}
      .stamp {{
        display: inline-block;
        margin-top: 10px;
        color: var(--green);
        font-size: 12px;
        font-weight: 800;
        text-transform: uppercase;
      }}
      .score-badge {{
        display: inline-block;
        padding: 4px 10px;
        background: rgba(88, 185, 145, 0.2);
        border: 1px solid var(--green);
        border-radius: 4px;
        color: var(--green);
        font-weight: bold;
        margin-bottom: 15px;
      }}
      @media (max-width: 620px) {{
        header,
        .terms {{
          grid-template-columns: 1fr;
        }}
        .meta {{
          text-align: left;
        }}
        ul {{
          padding-left: 20px;
        }}
      }}
    </style>
  </head>
  <body>
    <main>
      <header>
        <div>
          <h1>Candidate Screening Report</h1>
          <p>Resume evaluation matched against Target Job Description.</p>
        </div>
        <div class="meta">
          Candidate ID: {html.escape(case.id)}<br />
          Review Session: {html.escape(case.session_id)}<br />
          Generated by Gemini Flash
        </div>
      </header>

      <section class="terms">
        <div class="term"><span>Candidate</span><strong>{html.escape(employee["name"])}</strong></div>
        <div class="term"><span>Email</span><strong>{html.escape(employee["email"])}</strong></div>
        <div class="term"><span>Target Role</span><strong>{html.escape(employee["role"])}</strong></div>
        <div class="term"><span>Target Team</span><strong>{html.escape(employee["team"])}</strong></div>
        <div class="term"><span>Hiring Manager</span><strong>{html.escape(employee["manager"])}</strong></div>
        <div class="term"><span>Match Score</span><strong style="color: var(--green);">94% (High Fit)</strong></div>
      </section>

      <h2>Resume Summary & Evaluation</h2>
      <div class="score-badge">Match Score: 94/100</div>
      <p>
        Olivia Bennett presents a stellar background building complex API platforms and leading engineering/product teams. Her core skills directly align with the requirements for the Product Manager role in Platform Systems.
      </p>

      <h2>Key Strengths / Pros</h2>
      <ul>
        <li><strong>Technical Foundation</strong>: Holds solid experience in Docker, Kubernetes, and cloud infrastructure management.</li>
        <li><strong>API Product Design</strong>: Successfully launched developer APIs that scaled to support 10M+ active users.</li>
        <li><strong>Leadership</strong>: Over 4 years of cross-functional team coordination, collaborating with engineering and business stakeholders.</li>
      </ul>

      <h2>Potential Risks / Cons</h2>
      <ul>
        <li><strong>Frontend Experience</strong>: Focus is heavily backend/infrastructure-oriented. Minimal exposure to frontend product design, though acceptable for the Platform Systems team.</li>
      </ul>

      <section class="signature {signature_class}">
        Hiring Manager Decision
        <strong>{status_label}</strong>
        {"<span class='stamp'>Approved by " + html.escape(employee["manager"]) + " at " + html.escape(signed_at) + "</span>" if signed else ""}
      </section>
    </main>
  </body>
</html>"""


def _schedule_html(case: LiveOnboardingCase) -> str:
    employee = case.employee
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Interview Schedule Itinerary</title>
    <style>
      :root {{
        color-scheme: dark;
        --canvas: #12110e;
        --panel: #1f1e19;
        --panel-soft: #181713;
        --ink: #f4f1e8;
        --muted: #c8c2b6;
        --quiet: #989184;
        --line: #343229;
        --accent: #f54e00;
      }}
      body {{
        margin: 0;
        padding: clamp(14px, 4vw, 34px);
        color: var(--ink);
        font-family: Inter, system-ui, "Helvetica Neue", Arial, sans-serif;
        background: var(--canvas);
      }}
      main {{
        max-width: 760px;
        margin: 0 auto;
        padding: clamp(20px, 5vw, 34px);
        border: 1px solid var(--line);
        border-radius: 12px;
        background: var(--panel);
      }}
      h1 {{
        margin: 0 0 10px;
        font-size: clamp(24px, 5vw, 34px);
        font-weight: 400;
        letter-spacing: -0.68px;
        line-height: 1.2;
      }}
      p {{
        margin: 0 0 28px;
        color: var(--muted);
        line-height: 1.55;
      }}
      ol {{
        display: grid;
        gap: 12px;
        margin: 0;
        padding: 0;
        list-style: none;
      }}
      li {{
        display: grid;
        grid-template-columns: minmax(58px, 72px) minmax(0, 1fr);
        gap: 16px;
        padding: 14px 16px;
        border: 1px solid var(--line);
        border-radius: 8px;
        color: var(--muted);
        background: var(--panel-soft);
      }}
      strong {{
        color: var(--accent);
        font-family: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 13px;
        font-weight: 500;
      }}
      .meta {{
        color: var(--quiet);
        font-size: 13px;
      }}
    </style>
  </head>
  <body>
    <main>
      <h1>Interview Schedule for {html.escape(employee["name"])}</h1>
      <p>Sent to {html.escape(employee["email"])} after the booking slot was confirmed.</p>
      <ol>
        <li><strong>09:30 AM</strong><span>Platform Systems Architecture Deep-Dive (60 mins)</span></li>
        <li><strong>11:00 AM</strong><span>Product Case Study & Roadmap Planning (45 mins)</span></li>
        <li><strong>01:30 PM</strong><span>Cross-functional Leadership & Team Introductions (30 mins)</span></li>
        <li><strong>03:00 PM</strong><span>HR & Culture Alignment Review (30 mins)</span></li>
      </ol>
    </main>
  </body>
</html>"""


def _hardware_receipt_html(case: LiveOnboardingCase) -> str:
    employee = case.employee
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Interview Booking Confirmation</title>
    <style>
      :root {{
        color-scheme: dark;
        --canvas: #12110e;
        --panel: #1f1e19;
        --panel-soft: #181713;
        --ink: #f4f1e8;
        --muted: #c8c2b6;
        --quiet: #989184;
        --line: #343229;
        --success: #58b991;
      }}
      body {{
        margin: 0;
        padding: clamp(14px, 4vw, 34px);
        color: var(--ink);
        font-family: Inter, system-ui, "Helvetica Neue", Arial, sans-serif;
        background: var(--canvas);
      }}
      main {{
        max-width: 680px;
        margin: 0 auto;
        padding: clamp(20px, 5vw, 34px);
        border: 1px solid var(--line);
        border-radius: 12px;
        background: var(--panel);
      }}
      h1 {{
        margin: 0 0 12px;
        font-size: clamp(24px, 5vw, 34px);
        font-weight: 400;
        letter-spacing: -0.68px;
        line-height: 1.2;
      }}
      p {{
        margin: 0;
        color: var(--muted);
        line-height: 1.55;
      }}
      .receipt {{
        margin-top: 24px;
        padding: 18px;
        border: 1px solid rgba(88, 185, 145, 0.42);
        border-radius: 8px;
        background: #18251d;
      }}
      .receipt span {{
        display: block;
        margin-bottom: 6px;
        color: var(--quiet);
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.88px;
        text-transform: uppercase;
      }}
      strong {{
        color: var(--success);
        font-family: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 14px;
        font-weight: 500;
      }}
    </style>
  </head>
  <body>
    <main>
      <h1>Interview Booking Confirmation</h1>
      <p>Candidate booking receipt generated by the Screening Demo.</p>
      <section class="receipt">
        <span>Booking Verified</span>
        <p><strong>{html.escape(employee["tracking_id"])}</strong> slot confirmed for {html.escape(employee["name"])}.</p>
      </section>
    </main>
  </body>
</html>"""


def _write_artifact(case: LiveOnboardingCase, filename: str, body: str) -> None:
    (_case_dir(case.id) / filename).write_text(body, encoding="utf-8")


def case_payload(case: LiveOnboardingCase) -> dict[str, Any]:
    return {
        "id": case.id,
        "session_id": case.session_id,
        "user_id": case.user_id,
        "employee": case.employee,
        "current_step": case.current_step,
        "pending_signals": case.pending_signals,
        "status": case.status,
        "document_signed": case.document_signed,
        "hardware_delivered": case.hardware_delivered,
        "adk_status": case.adk_status,
        "events": case.events,
        "artifacts": case.artifacts,
        "updated_at": case.updated_at,
    }


async def create_live_case(session_service) -> LiveOnboardingCase:
    global LATEST_CASE_ID

    employee = _employee()
    case_id = str(uuid.uuid4())
    case = LiveOnboardingCase(
        id=case_id,
        session_id=case_id,
        user_id="employee",
        employee=employee,
    )
    await session_service.create_session(
        app_name="app",
        user_id=case.user_id,
        session_id=case.session_id,
        state={
            "current_step": OnboardingStep.SCREENING_COMPLETED,
            "new_hire_details": {
                "name": employee["name"],
                "email": employee["email"],
                "start_date": employee["start_date"],
            },
            "pending_signals": ["document_signed"],
        },
    )
    _write_artifact(case, "welcome_packet.html", _packet_html(case))
    _artifact(
        case,
        "welcome-packet",
        "Resume Screening Report",
        "html",
        "welcome_packet.html",
    )
    _event(
        case,
        "agent",
        "Screening analysis report generated",
        "A local HTML screening analysis report comparing Olivia's resume against the JD was created.",
    )
    _event(
        case,
        "state",
        "Agent is waiting",
        "ADK session is parked at SCREENING_COMPLETED waiting for manager approval.",
    )
    CASES[case.id] = case
    SESSION_TO_CASE[case.session_id] = case.id
    LATEST_CASE_ID = case.id
    return case


async def mark_document_signed(case: LiveOnboardingCase, resume_handler) -> None:
    case.document_signed = True
    case.status = "waking_after_approval"
    case.current_step = OnboardingStep.APPROVED
    case.pending_signals = []
    _write_artifact(
        case, "signed_onboarding_packet.html", _packet_html(case, signed=True)
    )
    _artifact(
        case,
        "signed-packet",
        "Approved Candidate Report",
        "html",
        "signed_onboarding_packet.html",
    )
    _event(
        case,
        "manager",
        f"Hiring Manager approved {case.employee['name']}",
        "Manager clicked Approve Candidate. Generating invite link.",
    )
    _event(
        case,
        "webhook",
        "manager_approved webhook fired",
        "The app invoked the ADK resume loop to wake up the coordinator.",
    )
    try:
        await resume_handler.receive_signed_documents_callback(
            user_id=case.user_id, session_id=case.session_id
        )
        case.adk_status = "manager_approval_completed"
        case.current_step = OnboardingStep.SCHEDULING_COMPLETED
        case.pending_signals = ["hardware_delivered"]
        case.status = "waiting_for_interview_booking"
        _event(
            case,
            "agent",
            "ADK resume completed",
            "Interview scheduling link generated. Waiting for candidate to select a slot.",
        )
    except Exception as exc:
        case.adk_status = "manager_approval_failed"
        case.status = "approval_adk_resume_failed"
        _event(case, "error", "ADK resume failed", str(exc))
    finally:
        case.updated_at = time.time()


async def mark_hardware_delivered(case: LiveOnboardingCase, resume_handler) -> None:
    case.hardware_delivered = True
    case.status = "waking_after_booking"
    case.current_step = OnboardingStep.COMPLETED
    case.pending_signals = []
    _write_artifact(
        case,
        "hardware_delivery_receipt.html",
        _hardware_receipt_html(case),
    )
    _artifact(
        case,
        "hardware-receipt",
        "Interview Booking Receipt",
        "html",
        "hardware_delivery_receipt.html",
    )
    _event(
        case,
        "candidate",
        f"{case.employee['name']} scheduled their interview",
        f"Candidate booked the slot. Confirmation ID {case.employee['tracking_id']} issued.",
    )
    _event(
        case,
        "webhook",
        "interview_booked webhook fired",
        "The app invoked the ADK resume loop to process the booking.",
    )
    try:
        await resume_handler.receive_hardware_delivery_callback(
            user_id=case.user_id,
            session_id=case.session_id,
            tracking_id=case.employee["tracking_id"],
        )
        case.adk_status = "interview_booking_completed"
        case.current_step = OnboardingStep.COMPLETED
        case.status = "completed"
        _write_artifact(case, "day_one_schedule.html", _schedule_html(case))
        _artifact(
            case,
            "day-one-schedule",
            "Interview Itinerary Schedule",
            "html",
            "day_one_schedule.html",
        )
        _event(
            case,
            "agent",
            "Screening & scheduling completed",
            "The candidate confirmed their slot and the panel schedule was finalized.",
        )
    except Exception as exc:
        case.adk_status = "interview_booking_failed"
        case.status = "booking_adk_resume_failed"
        _event(case, "error", "ADK resume failed", str(exc))
    finally:
        case.updated_at = time.time()


def case_for_session(session_id: str) -> LiveOnboardingCase | None:
    case_id = SESSION_TO_CASE.get(session_id)
    if not case_id:
        return None
    return CASES.get(case_id)


def get_case(case_id: str) -> LiveOnboardingCase:
    case = CASES.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Candidate case not found")
    return case


def artifact_response(case_id: str, artifact_id: str) -> HTMLResponse:
    case = get_case(case_id)
    artifact = next(
        (item for item in case.artifacts if item["id"] == artifact_id), None
    )
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    path = _case_dir(case.id) / artifact["filename"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Artifact file not found")
    return HTMLResponse(path.read_text(encoding="utf-8"))


def empty_case_payload() -> dict[str, Any]:
    return {"active": False, "message": "No live candidate case has been started."}


def latest_case_payload() -> dict[str, Any]:
    if not LATEST_CASE_ID or LATEST_CASE_ID not in CASES:
        return empty_case_payload()
    return {"active": True, "case": case_payload(CASES[LATEST_CASE_ID])}
