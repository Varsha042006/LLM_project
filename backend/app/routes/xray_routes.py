from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from ..xray_service import run_xray_inspection, get_cached_xray_model

router = APIRouter(prefix="/api/xray", tags=["Neural LLM X-Ray"])


class XRayInspectRequest(BaseModel):
    text: str
    layer_idx: Optional[int] = 0
    head_idx: Optional[int] = 0
    token_idx: Optional[int] = 0
    max_new_tokens: Optional[int] = 120


@router.post("/inspect")
def inspect_xray_endpoint(req: XRayInspectRequest):
    """
    Executes a real forward pass on the local LLM with eager attention & hidden state capture.
    Returns tensor analytics across all 6 inspection tabs.
    """
    try:
        return run_xray_inspection(
            text=req.text,
            layer_idx=req.layer_idx or 0,
            head_idx=req.head_idx or 0,
            token_idx=req.token_idx or 0,
            max_new_tokens=req.max_new_tokens or 120
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"X-Ray inspection error: {str(e)}")


@router.get("/metadata")
def xray_metadata_endpoint():
    """Returns architecture specs for the neural X-Ray engine."""
    try:
        model, _, _ = get_cached_xray_model()
        config = model.config
        return {
            "status": "ready",
            "model_name": "Qwen 2.5 0.5B Instruct",
            "num_layers": getattr(config, "num_hidden_layers", 24),
            "num_heads": getattr(config, "num_attention_heads", 14),
            "hidden_dim": getattr(config, "hidden_size", 896),
            "vocab_size": getattr(config, "vocab_size", 151643),
            "parameters": "0.49B",
            "device": "CPU"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
