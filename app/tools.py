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

from google.adk.tools import ToolContext

from app.state_schema import OnboardingStep


def screen_candidate_resume(
    name: str, email: str, role: str, tool_context: ToolContext
) -> dict:
    """Evaluates the candidate's resume against the Job Description and draft screening report.

    Args:
        name: Full name of the candidate.
        email: Email address of the candidate.
        role: The target job role (e.g. Product Manager).

    Returns:
        A dictionary containing screening status.
    """
    state = tool_context.state
    state["new_hire_details"] = {
        "name": name,
        "email": email,
        "role": role,
    }
    state["current_step"] = OnboardingStep.SCREENING_COMPLETED
    state["pending_signals"] = ["document_signed"]

    return {
        "status": "success",
        "message": f"Resume screening completed for {name} ({email}). Matching report generated.",
        "screening_report_id": f"REP-{name.replace(' ', '').upper()}",
    }


def generate_interview_scheduling_link(username: str, tool_context: ToolContext) -> dict:
    """Generates an interview scheduling invite link for the approved candidate.

    Args:
        username: Corporate scheduling ID prefix.

    Returns:
        A dictionary containing the generated schedule status.
    """
    state = tool_context.state
    email = f"{username}@example.com"

    state["current_step"] = OnboardingStep.SCHEDULING_COMPLETED
    state["new_hire_details"]["corporate_email"] = email

    if "document_signed" in state.get("pending_signals", []):
        state["pending_signals"].remove("document_signed")

    state["pending_signals"].append("hardware_delivered")

    return {
        "status": "success",
        "scheduling_link": f"https://calendly.com/{username}/interview",
        "candidate_email": email,
    }


def check_hardware_delivery(tracking_id: str, tool_context: ToolContext) -> dict:
    """Queries the calendar scheduling API to confirm if the candidate has booked a slot.

    Args:
        tracking_id: The interview booking ID (e.g., INT-12345).

    Returns:
        A dictionary containing scheduling confirmation.
    """
    state = tool_context.state

    if tracking_id.startswith("HW-") or tracking_id.startswith("INT-"):
        state["current_step"] = OnboardingStep.COMPLETED

        if "hardware_delivered" in state.get("pending_signals", []):
            state["pending_signals"].remove("hardware_delivered")

        return {
            "status": "scheduled",
            "booking_id": tracking_id,
            "interview_type": "Technical Panel",
            "candidate": state.get("new_hire_details", {}).get("name", "Candidate"),
        }

    return {
        "status": "pending_booking",
        "booking_id": tracking_id,
        "message": "Waiting for candidate to pick a slot on Calendly.",
    }


def generate_rejection_email(email: str, tool_context: ToolContext) -> dict:
    """Generates and sends a polite rejection letter to a candidate who was not selected.

    Args:
        email: The candidate's email address.

    Returns:
        A dictionary confirming completion status.
    """
    state = tool_context.state
    state["current_step"] = OnboardingStep.REJECTED
    state["pending_signals"] = []

    name = state.get("new_hire_details", {}).get("name", "Candidate")

    return {
        "status": "rejected",
        "message": f"Polite rejection email successfully sent to {name} at {email}.",
    }
