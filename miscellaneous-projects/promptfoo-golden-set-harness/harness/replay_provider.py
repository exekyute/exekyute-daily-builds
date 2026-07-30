"""Offline promptfoo provider that replays written model behaviour.

Stands in for a hosted model so the harness runs end to end with no API key and no
network: the pipeline, the rubric, the four metrics, and the regression comparison are
all exercised, and the run is byte-for-byte repeatable. What it does not do is tell you
anything about a real model. For that, run promptfooconfig.yaml against Groq.

Each answer starts from the golden answer for the case, takes the deviations written in
fixtures/model-profiles.json for that model and prompt version, then gets rendered in
the model's own surface style. The styles differ on purpose. A JSON fence, "N/A" for an
absent value, a spaced container number, and "USD 18,450.00" all have to score the same
as the plain forms, and that only holds if normalization is doing its job.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scoring  # noqa: E402  (path has to be set before the import)

PROFILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "fixtures",
    "model-profiles.json",
)

_CACHE = {}


def load_profiles(path=PROFILE_PATH):
    if path not in _CACHE:
        with open(path, encoding="utf-8") as handle:
            _CACHE[path] = json.load(handle)["models"]
    return _CACHE[path]


def build_answer(expected, version_profile, case_id, repeat_index):
    """The golden answer with this model's written deviations applied."""
    answer = dict(expected)
    for field, value in (version_profile.get("errors") or {}).get(case_id, {}).items():
        answer[field] = value
    variants = (version_profile.get("unstable") or {}).get(case_id)
    if variants:
        for field, value in variants[repeat_index % len(variants)].items():
            answer[field] = value
    for field in (version_profile.get("omits") or {}).get(case_id, []):
        answer.pop(field, None)
    return answer


def spaced_container(value):
    """MRDU4419078 written the way it is stamped on the box: MRDU 441907-8."""
    text = str(value)
    if len(text) != 11:
        return text
    return "%s %s-%s" % (text[:4], text[4:10], text[10])


def render_answer(answer, style):
    """Turn an answer into the response text this model would return."""
    shaped = {}
    for name, value in answer.items():
        if value is None:
            shaped[name] = "N/A" if style.get("nulls") == "na_text" else None
        elif name == "declared_value_usd" and style.get("money") == "usd_commas":
            shaped[name] = "USD {:,.2f}".format(float(value))
        elif name == "container_id" and style.get("container") == "spaced":
            shaped[name] = spaced_container(value)
        else:
            shaped[name] = value
    text = json.dumps(shaped, indent=2)
    if style.get("fenced"):
        return "```json\n%s\n```" % text
    return text


def call_api(prompt, options, context):
    config = options.get("config") or {}
    model = config.get("model")
    profiles = load_profiles(config.get("profiles") or PROFILE_PATH)
    if model not in profiles:
        return {"error": "no replay profile for model %r" % (model,)}

    variables = context.get("vars") or {}
    expected = variables.get("expected") or {}
    case_id = variables.get("case_id")
    if not expected or not case_id:
        return {"error": "case %r is missing case_id or expected values" % (case_id,)}

    version = scoring.version_key((context.get("prompt") or {}).get("label"))
    profile = profiles[model]
    version_profile = (profile.get("versions") or {}).get(version)
    if version_profile is None:
        return {"error": "model %r has no profile for prompt version %r" % (model, version)}

    repeat_index = int(context.get("repeatIndex") or variables.get("__repeatIndex") or 0)
    answer = build_answer(expected, version_profile, case_id, repeat_index)
    return {"output": render_answer(answer, profile.get("style") or {})}
