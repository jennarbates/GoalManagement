"""Local LLM client using MLX (mlx-lm) -- loaded and run in-process, the same
way as your dailyWorkbook script: load the model once, apply the tokenizer's
chat template, generate, and (for structured calls) robustly pull a JSON
object out of the raw text with a retry if it doesn't parse clean.
"""
import json

_MODEL = None
_TOKENIZER = None
_LOADED_MODEL_ID = None


class LLMError(Exception):
    pass


def _get_model(model_id, trust_remote_code=False):
    global _MODEL, _TOKENIZER, _LOADED_MODEL_ID
    if _MODEL is None or _LOADED_MODEL_ID != model_id:
        try:
            from mlx_lm import load
        except ImportError:
            raise LLMError(
                "mlx-lm isn't installed. Run: pip install mlx-lm huggingface_hub"
            )
        load_kwargs = {}
        if trust_remote_code:
            load_kwargs["tokenizer_config"] = {"trust_remote_code": True}
        try:
            print(f"⏳ Loading {model_id} (first call only)...")
            _MODEL, _TOKENIZER = load(model_id, **load_kwargs)
            print("✓ Model loaded")
        except Exception as e:
            raise LLMError(f"Couldn't load model '{model_id}': {e}")
        _LOADED_MODEL_ID = model_id
    return _MODEL, _TOKENIZER


def _format_prompt(tokenizer, messages):
    try:
        if getattr(tokenizer, "chat_template", None) is not None:
            return tokenizer.apply_chat_template(messages, add_generation_prompt=True)
    except Exception:
        pass
    # Fallback for tokenizers without a chat template
    lines = []
    for m in messages:
        lines.append(f"{m['role'].upper()}: {m['content']}")
    lines.append("ASSISTANT:")
    return "\n\n".join(lines)


def generate_text(messages, model_id, max_tokens=600, trust_remote_code=False):
    """messages: list of {"role": "system"/"user"/"assistant", "content": str}"""
    model, tokenizer = _get_model(model_id, trust_remote_code)
    prompt = _format_prompt(tokenizer, messages)
    try:
        from mlx_lm import generate
        text = generate(model, tokenizer, prompt=prompt, max_tokens=max_tokens, verbose=False)
    except Exception as e:
        raise LLMError(f"Generation failed: {e}")
    return text.strip()


# kept as `chat` too since memory.py calls it that way
def chat(messages, model_id, max_tokens=600, trust_remote_code=False, **_ignored):
    return generate_text(messages, model_id, max_tokens=max_tokens, trust_remote_code=trust_remote_code)


def extract_json_object(text: str) -> str:
    """Pull the first complete top-level {...} object out of raw model output,
    tolerating markdown fences and trailing prose."""
    text = text.strip().replace("```json", "").replace("```", "").strip()
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found.")
    depth, in_string, escape_next = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape_next:
                escape_next = False
            elif ch == "\\":
                escape_next = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise ValueError("Incomplete JSON object.")


def generate_json(prompt, model_id, required_keys, fallback, max_tokens=400,
                   max_retries=1, trust_remote_code=False):
    """Ask the model for a JSON object; retries once with a stricter nudge if
    parsing fails, then falls back to `fallback` rather than crashing a session."""
    retry_prompts = [
        prompt,
        prompt + "\n\nReturn ONLY one complete, valid JSON object. No markdown, no prose, no explanation.",
    ]
    for attempt_prompt in retry_prompts[:max_retries + 1]:
        raw = ""
        try:
            raw = generate_text(
                [{"role": "user", "content": attempt_prompt}],
                model_id, max_tokens=max_tokens, trust_remote_code=trust_remote_code,
            )
            data = json.loads(extract_json_object(raw))
            if not isinstance(data, dict):
                raise ValueError("Not a JSON object")
            for key in required_keys:
                if key not in data:
                    raise ValueError(f"Missing key: {key}")
            return data
        except Exception:
            continue
    return fallback
