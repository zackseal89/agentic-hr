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

import os
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

import google.auth
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from app.state_schema import OnboardingStep
from app.tools import (
    check_hardware_delivery,
    generate_interview_scheduling_link,
    generate_rejection_email,
    screen_candidate_resume,
)

# Shared model for tools that need to call LLM directly
model_instance = Gemini(
    model="gemini-3.1-flash-lite",
    retry_options=types.HttpRetryOptions(attempts=3),
)

if os.environ.get("GEMINI_API_KEY"):
    os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "False"
else:
    try:
        _, project_id = google.auth.default()
        os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
        os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
        os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "True"
    except Exception:
        os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "False"


async def initialize_onboarding_state(callback_context: CallbackContext) -> None:
    """Ensures all onboarding state machine keys are initialized to prevent errors."""
    state = callback_context.state
    if "current_step" not in state:
        state["current_step"] = OnboardingStep.START
    if "new_hire_details" not in state:
        state["new_hire_details"] = {}
    if "pending_signals" not in state:
        state["pending_signals"] = []


instruction = """You are a Candidate Screening and Shortlisting Agent. Your goal is to screen applicants against Job Descriptions and guide them through hiring checkpoints.

Current Step: {current_step}
Candidate/Job Details: {new_hire_details}
Pending Signals: {pending_signals}

Follow this state machine flow exactly:
1. If current_step is 'START': The session should already contain a 'candidate_profile' and a 'job_description' in the state. Invoke the 'screen_candidate_resume' tool to evaluate the candidate.
2. If current_step is 'SCREENING_COMPLETED': Inform the user that the screening report is ready with a recommendation. You are now waiting for a human hiring manager to 'Approve', 'Reject', or put the candidate 'On Hold'. Do not call other tools.
3. If current_step is 'ON_HOLD': Inform the user that the candidate is currently on hold. You are waiting for a human decision to either 'Approve' or 'Reject' them to proceed.
4. If current_step is 'APPROVED': Delegate the scheduling link generation to the 'scheduling_agent' subagent. Do not call tools directly for scheduling; transfer execution to 'scheduling_agent'.
5. If current_step is 'SCHEDULING_COMPLETED': Advise that the interview link has been generated. Wait for the candidate to select a slot. Once they book a slot, invoke 'check_hardware_delivery' (which verifies calendar bookings).
6. If current_step is 'REJECTED': Invoke the 'generate_rejection_email' tool.
7. If current_step is 'COMPLETED': State that the screening and scheduling process is complete, congratulate the team, and list the interview confirmation.

Always stay grounded in your tools and current state. Do not skip steps or invent details. The AI recommendation is for human review only and does not automatically advance the state.
"""

scheduling_agent = Agent(
    name="scheduling_agent",
    model=Gemini(
        model="gemini-3.1-flash-lite",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are an Interview Scheduling Agent. Your goal is to generate interview invites and scheduling links for the candidate.

Current Step: {current_step}
Candidate Details: {new_hire_details}

Follow these instructions:
1. Prompt the user/coordinator for the desired corporate calendar prefix if they haven't provided one.
2. Once provided, invoke the 'generate_interview_scheduling_link' tool.
3. Inform the coordinator that the scheduling link is generated and return execution back to the parent agent.
""",
    tools=[generate_interview_scheduling_link],
)

root_agent = Agent(
    name="candidate_screening_coordinator",
    model=Gemini(
        model="gemini-3.1-flash-lite",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    tools=[screen_candidate_resume, check_hardware_delivery, generate_rejection_email],
    sub_agents=[scheduling_agent],
    before_agent_callback=initialize_onboarding_state,
)

app = App(
    root_agent=root_agent,
    name="app",
)
