"""
ClawFounder — Vision Agent

Takes a screenshot or image plus an instruction, calls Gemini multimodal
to generate a PM-style visual briefing, and prints a single JSON result.

Input on stdin (one JSON object):
  {
    "image": "<data URL or base64 string>",
    "prompt": "<optional user instruction>"
  }

Output on stdout (one JSON object):
  {
    "text": "<analysis text>"
  }
"""

import sys
import os
import json
import base64
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agent_shared import setup_env, get_gemini_client  # type: ignore

setup_env()


def _parse_image_field(image_field: str):
  """
  Accept either a data URL (data:image/png;base64,...) or a bare base64 string.

  Returns (mime_type, raw_bytes).
  """
  if not image_field:
    raise ValueError("image is required")

  if image_field.startswith("data:"):
    try:
      header, b64 = image_field.split(",", 1)
    except ValueError as e:
      raise ValueError("Invalid data URL") from e

    # data:image/png;base64
    mime_part = header.split(";")[0]  # data:image/png
    _, mime_type = mime_part.split(":", 1)
    return mime_type, base64.b64decode(b64)

  # Fallback: assume bare base64 PNG
  return "image/png", base64.b64decode(image_field)


def run_vision(prompt: str, image_field: str) -> str:
  """Call Gemini multimodal model with image + text and return analysis text."""
  from google.genai import types  # type: ignore

  client = get_gemini_client()

  mime_type, image_bytes = _parse_image_field(image_field)

  # Prefer a 2.5 multimodal text model for screenshots
  model = os.environ.get("GEMINI_VISION_MODEL", "gemini-2.5-flash")

  system_instruction = (
      "You are ClawFounder, a founder-facing project management copilot. "
      "You are looking at a single screenshot or image from the user's tools "
      "(dashboards, Kanban boards, PRs, docs, chats, etc.). "
      "Your job is NOT to describe pixels, but to extract what matters for execution.\n\n"
      "Output a short briefing (max ~8 bullet points) that covers:\n"
      "- What you infer is going on (status, risks, blockers, opportunities)\n"
      "- Concrete next actions the founder or team should take\n"
      "- Any anomalies or things that look off\n\n"
      "Be direct, no hedging, no markdown code fences. Assume you can also "
      "cross-check this with their other connectors later."
  )

  user_prompt = prompt or "Analyze this screenshot like an AI project manager and tell me what I should do next."

  response = client.models.generate_content(
      model=model,
      contents=[
          types.Content(
              role="user",
              parts=[
                  types.Part(text=user_prompt),
                  types.Part(
                      inline_data=types.Blob(
                          mime_type=mime_type,
                          data=image_bytes,
                      )
                  ),
              ],
          )
      ],
      config=types.GenerateContentConfig(
          system_instruction=system_instruction,
          temperature=0.4,
          max_output_tokens=1024,
      ),
  )

  text = (response.text or "").strip()
  if not text:
    raise RuntimeError("Gemini returned empty response")
  return text


def main():
  try:
    raw = sys.stdin.read()
    data = json.loads(raw or "{}")
  except Exception as e:
    print(json.dumps({"error": f"Invalid input: {e}"}))
    return

  image_field = data.get("image") or ""
  prompt = data.get("prompt") or ""

  if not image_field:
    print(json.dumps({"error": "Missing 'image'"}))
    return

  try:
    text = run_vision(prompt, image_field)
    print(json.dumps({"text": text}))
  except Exception as e:
    print(json.dumps({"error": str(e)}))


if __name__ == "__main__":
  main()

