"""
Agent 3: Syntax Validator + Self-Corrector
For each translated Python file:
  1. Run ast.parse() to catch syntax errors
  2. If error → send back to Claude with error context (max 2 retries)
  3. Update translation status: valid / corrected / failed
"""

import ast
import os
import time
from typing import TypedDict, Dict, Any, List
import anthropic


def validate_python_syntax(python_code: str) -> tuple[bool, str]:
    """
    Parse Python code with ast.parse.
    Returns (is_valid, error_message).
    """
    try:
        ast.parse(python_code)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, str(e)


def self_correct(python_code: str, error_msg: str, filename: str, attempt: int) -> str:
    """
    Ask Claude to fix the syntax error in the generated code.
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = f"""The following Python code translated from SAS file '{filename}' has a syntax error.

ERROR: {error_msg}

ATTEMPT: {attempt} of 2

Fix ONLY the syntax error. Do not change the logic or add new features.
Return the complete corrected Python code only — no explanation.

--- Code with error ---
{python_code}"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]
    return raw.strip()


class ValidatorState(TypedDict):
    translations: Dict[str, Dict[str, Any]]
    validator_notes: List[str]


def run_syntax_validator(state: ValidatorState) -> ValidatorState:
    """
    LangGraph node: Validates syntax and self-corrects up to 2 times.
    """
    notes = []
    MAX_RETRIES = 2

    for filename, data in state["translations"].items():
        if data["status"] == "error":
            notes.append(f"⏭️  {filename} — skipped (translation error)")
            continue

        python_code = data["python_code"]
        is_valid, error_msg = validate_python_syntax(python_code)

        if is_valid:
            data["validation_status"] = "valid"
            data["correction_attempts"] = 0
            notes.append(f"✅ {filename} — syntax valid")
            continue

        # Self-correction loop
        corrected = python_code
        success = False
        attempts = 0

        for attempt in range(1, MAX_RETRIES + 1):
            attempts = attempt
            notes.append(f"🔧 {filename} — attempt {attempt}: {error_msg}")
            try:
                corrected = self_correct(corrected, error_msg, filename, attempt)
                is_valid, error_msg = validate_python_syntax(corrected)
                if is_valid:
                    success = True
                    break
                time.sleep(1)  # brief pause between retries
            except Exception as e:
                notes.append(f"   Correction API error: {e}")
                break

        if success:
            data["python_code"] = corrected
            data["validation_status"] = "corrected"
            data["correction_attempts"] = attempts
            notes.append(f"✅ {filename} — corrected after {attempts} attempt(s)")
        else:
            data["validation_status"] = "failed"
            data["correction_attempts"] = attempts
            notes.append(f"❌ {filename} — correction failed after {attempts} attempt(s): {error_msg}")

    state["validator_notes"] = notes
    return state
