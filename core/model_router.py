"""Stub for core.model_router - implements minimal functionality."""

MODELS = {}

async def route_chat(message, session_id=None, **kwargs):
    """Fallback chat router."""
    return {"response": message, "model": "stub"}

def set_active_model(model_name):
    """Set active model."""
    pass

def list_models():
    """List available models."""
    return []

def get_active_model():
    """Get active model."""
    return "stub"
