# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging

from google.adk.runners import Runner
from google.genai import types

from app.state_schema import OnboardingStep

logger = logging.getLogger(__name__)


class OnboardingResumeHandler:
    def __init__(self, runner: Runner):
        """Initializes the resume handler with the active ADK Runner."""
        self.runner = runner

    def _log_structured(self, severity: str, message: str, **kwargs) -> None:
        """Helper to output formatted JSON logs that Cloud Logging can parse natively."""
        payload = {"severity": severity, "message": message, **kwargs}
        logger.info(json.dumps(payload))

    async def receive_manager_decision_callback(
        self, user_id: str, session_id: str, decision: str
    ) -> None:
        """Processes a human decision (Approve, Reject, or On Hold).

        Hydrates the existing session, transitions the checkpoint based on the decision, and resumes.
        """
        if decision not in ["APPROVE", "REJECT", "HOLD"]:
            raise ValueError(f"Invalid decision: {decision}")

        new_step = {
            "APPROVE": OnboardingStep.APPROVED,
            "REJECT": OnboardingStep.REJECTED,
            "HOLD": OnboardingStep.ON_HOLD,
        }[decision]

        self._log_structured(
            severity="INFO",
            message=f"Received manager decision '{decision}' for session {session_id}",
            event="webhook_received",
            webhook_type="manager_decision",
            session_id=session_id,
            user_id=user_id,
            decision=decision,
        )

        try:
            self._log_structured(
                severity="INFO",
                message=f"State machine transitioned to {new_step}",
                event="state_transition",
                session_id=session_id,
                user_id=user_id,
                new_step=new_step,
            )

            decision_msg = {
                "APPROVE": "Candidate has been approved by the hiring manager.",
                "REJECT": "Candidate has been rejected by the hiring manager.",
                "HOLD": "Candidate has been put on hold by the hiring manager.",
            }[decision]

            # Trigger runner wake-up and run execution ambiently
            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=f"Resume screening: {decision_msg}")],
                ),
                state_delta={
                    "current_step": new_step,
                    "pending_signals": [],
                },
            ):
                self._log_structured(
                    severity="INFO",
                    message=f"Wake-up execution event: {event}",
                    event="runner_event",
                    session_id=session_id,
                    user_id=user_id,
                )

            self._log_structured(
                severity="INFO",
                message="Ambient manager approval execution turn completed successfully",
                event="runner_turn_success",
                session_id=session_id,
                user_id=user_id,
            )
        except Exception as e:
            self._log_structured(
                severity="ERROR",
                message=f"Ambient manager approval execution failed: {e!s}",
                event="runner_turn_failure",
                session_id=session_id,
                user_id=user_id,
                error=str(e),
            )
            raise

    async def receive_hardware_delivery_callback(
        self, user_id: str, session_id: str, tracking_id: str
    ) -> None:
        """DEPRECATED: Use receive_manager_decision_callback instead.
        Kept for backward compatibility with existing tests/demo temporarily.
        """
        await self.receive_manager_decision_callback(user_id, session_id, "APPROVE")
        """Simulates a webhook confirming the candidate has booked their interview slot.

        Hydrates the session, transitions the checkpoint to COMPLETED, and resumes.
        """
        self._log_structured(
            severity="INFO",
            message=f"Received interview scheduling webhook with booking ID {tracking_id}",
            event="webhook_received",
            webhook_type="interview_booked",
            session_id=session_id,
            user_id=user_id,
            booking_id=tracking_id,
        )

        try:
            self._log_structured(
                severity="INFO",
                message=f"State machine transitioned to {OnboardingStep.COMPLETED}",
                event="state_transition",
                session_id=session_id,
                user_id=user_id,
                new_step=OnboardingStep.COMPLETED,
            )

            # Trigger runner wake-up and run execution ambiently
            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(
                            text=f"Resume screening: Candidate booked the slot with booking ID {tracking_id}."
                        )
                    ],
                ),
                state_delta={
                    "current_step": OnboardingStep.COMPLETED,
                    "pending_signals": [],
                },
            ):
                self._log_structured(
                    severity="INFO",
                    message=f"Wake-up execution event: {event}",
                    event="runner_event",
                    session_id=session_id,
                    user_id=user_id,
                )

            self._log_structured(
                severity="INFO",
                message="Ambient interview booking execution turn completed successfully",
                event="runner_turn_success",
                session_id=session_id,
                user_id=user_id,
            )
        except Exception as e:
            self._log_structured(
                severity="ERROR",
                message=f"Ambient interview booking execution failed: {e!s}",
                event="runner_turn_failure",
                session_id=session_id,
                user_id=user_id,
                error=str(e),
            )
            raise
