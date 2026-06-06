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

from typing import List
from pydantic import BaseModel, Field

class OnboardingStep:
    START = "START"
    SCREENING_COMPLETED = "SCREENING_COMPLETED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ON_HOLD = "ON_HOLD"
    SCHEDULING_COMPLETED = "SCHEDULING_COMPLETED"
    COMPLETED = "COMPLETED"

class CandidateProfile(BaseModel):
    name: str
    email: str
    target_role: str
    years_experience: float
    skills: List[str]
    source_text: str = Field(..., description="Raw text from resume or LinkedIn profile for reasoning")

class JobDescription(BaseModel):
    req_id: str
    role_title: str
    seniority: str
    required_skills: List[str]
    nice_to_have_skills: List[str]
    team_context: str

class RequirementMatch(BaseModel):
    requirement: str
    is_met: bool
    explanation: str

class ScreeningReport(BaseModel):
    overall_match_score: int = Field(..., ge=0, le=100)
    summary: str = Field(..., description="A one-paragraph summary for the recruiter")
    strengths: List[str]
    gaps: List[str]
    requirement_breakdown: List[RequirementMatch]
    recommendation: str = Field(..., description="Shortlist / Reject / Hold")
