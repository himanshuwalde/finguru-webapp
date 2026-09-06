"""
Centralized AI Client for Google Gemini API interactions.
Provides model selection, configuration, and error handling in one place.
"""
import streamlit as st
import google.generativeai as genai
from typing import Optional, List


# Cache the Gemini client configuration
@st.cache_resource
def get_gemini_client():
    """Initialize and return configured Gemini client."""
    api_key = st.secrets.get("GEMINI_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in secrets")
    genai.configure(api_key=api_key)
    return genai


@st.cache_data(ttl=3600)  # Cache model list for 1 hour
def get_available_models(_genai_client) -> List[str]:
    """Fetch all models that support generateContent."""
    try:
        models = _genai_client.list_models()
        return [m.name.replace('models/', '') for m in models if 'generateContent' in m.supported_generation_methods]
    except Exception as e:
        st.warning(f"Could not fetch models: {e}")
        return []


def get_best_model(_genai_client, prefer_flash: bool = True) -> str:
    """
    Select the best available model based on preferences.

    Args:
        _genai_client: The configured genai client
        prefer_flash: If True, prefers 'flash' models for speed/cost

    Returns:
        Model name string
    """
    valid_models = get_available_models(_genai_client)

    if not valid_models:
        return "gemini-1.5-flash"  # Safe default

    if prefer_flash:
        # Try to find a flash model
        flash_models = [m for m in valid_models if 'flash' in m.lower()]
        if flash_models:
            # Prefer 1.5-flash or 2.0-flash
            for pref in ['gemini-1.5-flash', 'gemini-2.0-flash', 'gemini-2.5-flash']:
                if pref in flash_models:
                    return pref
            return flash_models[0]

    # Fallback: prefer pro models, then first available
    pro_models = [m for m in valid_models if 'pro' in m.lower()]
    if pro_models:
        return pro_models[0]

    return valid_models[0]


def get_generative_model(_genai_client, model_name: Optional[str] = None, prefer_flash: bool = True):
    """
    Get a configured GenerativeModel instance.

    Args:
        _genai_client: The configured genai client
        model_name: Specific model to use (overrides auto-selection)
        prefer_flash: If True and no model_name given, prefers flash models

    Returns:
        Configured GenerativeModel instance
    """
    if model_name is None:
        model_name = get_best_model(_genai_client, prefer_flash)
    return _genai_client.GenerativeModel(model_name)


def generate_content_safe(model, prompt: str, max_retries: int = 2) -> Optional[str]:
    """
    Generate content with retry logic and error handling.

    Args:
        model: GenerativeModel instance
        prompt: The prompt to send
        max_retries: Number of retry attempts

    Returns:
        Generated text or None if failed
    """
    for attempt in range(max_retries + 1):
        try:
            response = model.generate_content(prompt)
            if response.text:
                return response.text
            elif attempt < max_retries:
                continue
        except Exception as e:
            if attempt == max_retries:
                st.error(f"AI generation failed after {max_retries + 1} attempts: {e}")
                return None
    return None