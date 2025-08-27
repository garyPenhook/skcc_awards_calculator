from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
from app.services.skcc import fetch_member_roster, parse_adif_files, calculate_awards, fetch_award_thresholds
from app.schemas.awards import AwardCheckResultModel, AwardProgressModel, AwardEndorsementModel, ThresholdModel

router = APIRouter(prefix="/awards", tags=["awards"])

@router.post("/check", response_model=AwardCheckResultModel, summary="Check SKCC awards from ADIF uploads")
async def check_awards(
    files: List[UploadFile] = File(...),
    enforce_key_type: bool = False,
    treat_missing_key_as_valid: bool = True,
) -> AwardCheckResultModel:
    if not files:
        raise HTTPException(status_code=400, detail="No ADIF files uploaded")
    contents: List[str] = []
    for f in files:
        raw = await f.read()
        try:
            text = raw.decode("utf-8", errors="ignore")
        except Exception as e:  # pragma: no cover (defensive)
            raise HTTPException(status_code=400, detail=f"Could not decode {f.filename}: {e}")
        contents.append(text)
    qsos = parse_adif_files(contents)
    members = await fetch_member_roster()
    thresholds = await fetch_award_thresholds()
    result = calculate_awards(
        qsos,
        members,
        thresholds,
        enable_endorsements=True,
        cw_only=True,
        enforce_key_type=enforce_key_type,
        treat_missing_key_as_valid=treat_missing_key_as_valid,
    )
    return AwardCheckResultModel(
        unique_members_worked=result.unique_members_worked,
        awards=[
            AwardProgressModel(
                name=a.name,
                required=a.required,
                current=a.current,
                achieved=a.achieved,
            )
            for a in result.awards
        ],
        endorsements=[
            AwardEndorsementModel(
                award=e.award,
                category=e.category,
                value=e.value,
                required=e.required,
                current=e.current,
                achieved=e.achieved,
            )
            for e in result.endorsements
        ],
        total_qsos=result.total_qsos,
        total_cw_qsos=result.total_cw_qsos,
        matched_qsos=result.matched_qsos,
        unmatched_calls=result.unmatched_calls,
        thresholds_used=[ThresholdModel(name=n, required=r) for n, r in result.thresholds_used],
    )
