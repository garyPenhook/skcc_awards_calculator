from pydantic import BaseModel, Field
from typing import List


class AwardProgressModel(BaseModel):
    name: str = Field(..., description="Award name")
    required: int = Field(..., description="Contacts required to achieve")
    current: int = Field(..., description="Current unique SKCC member contacts")
    achieved: bool = Field(..., description="Whether requirement met")


class AwardEndorsementModel(BaseModel):
    award: str = Field(..., description="Base award name")
    category: str = Field(..., description="'band' or 'mode'")
    value: str = Field(..., description="Band (e.g. 40M) or Mode (e.g. CW)")
    required: int
    current: int
    achieved: bool


class ThresholdModel(BaseModel):
    name: str
    required: int


class AwardCheckResultModel(BaseModel):
    unique_members_worked: int
    awards: List[AwardProgressModel]
    endorsements: List[AwardEndorsementModel] = Field(default_factory=list)
    total_qsos: int
    matched_qsos: int
    unmatched_calls: List[str] = Field(default_factory=list)
    thresholds_used: List[ThresholdModel]
    total_cw_qsos: int
