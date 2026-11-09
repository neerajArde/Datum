# providers.py
# stage 3 helper: talk to the llms.
#
# every provider (gemini, claude, openai) is wrapped so it looks the same:
#     prompt text in  ->  answer text out
# the ROUTER then decides who to ask:
#   - ask the first provider (gemini)
#   - if it hasnt answered after HEDGE_SECONDS, ALSO ask the next provider and take
#     whichever answers first (a "race"). one slow provider can no longer stall a paper
#   - if one is busy (429 / 503 / timeout) it "cools down" for a bit and we hop to the next
#   - if one is broken (bad key, wrong model name) it is switched off for this run
# a provider only turns on if its api key exists, so adding claude later = just add the key.
#
# every call is timed and logged, so the app can show exactly where time went.

import json
import os
import re
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

# model names. you can override any of them with an environment variable
# (or streamlit secret) of the same name, without touching code.
DEFAULT_MODELS = {
    "CEREBRAS_MODEL": "gpt-oss-120b",
    "GEMINI_MODEL": "gemini-3.8-flash",
    "GROQ_MODEL": "openai/gpt-oss-120b",
    "CLAUDE_MODEL": "claude-haiku-5-5",
    "OPENAI_MODEL": "gpt-5-mini",
}

# cerebras and groq speak the same "language" as openai, just at a different address
CEREBRAS_URL = "https://api.cerebras.ai/v1"
GROQ_URL = "https://api.groq.com/openai/v1"

# healthy calls take 1-5 s, so anything past this is a stuck call
REQUEST_TIMEOUT_SECONDS = 45

# if the provider we asked hasnt answered after this long, start the next one too
# (healthy cerebras / groq calls take about 1 s)
HEDGE_SECONDS = 8

# how long a provider is skipped after a problem, depending on the problem.
# rate limits (429) on free tiers reset within seconds, so we only step aside briefly
COOLDOWN_SECONDS = 20          # timeouts and unknown problems
BUSY_COOLDOWN_SECONDS = 8      # 500 / 503 "overloaded"
RATE_LIMIT_COOLDOWN_SECONDS = 3  # 429, unless the provider tells us how long to wait
MAX_COOLDOWN_SECONDS = 30

# an engine that fails this many times in a row is switched off for the rest of the run
MAX_FAILS_IN_A_ROW = 4

# how many times we go around the whole provider list before giving up on a chunk
ROUNDS = 5

# http codes that mean "try again later" rather than "this will never work"
TEMPORARY_CODES = [408, 409, 425, 429, 500, 502, 503, 504, 529]
TEMPORARY_WORDS = [
    "unavailable", "overloaded", "resource_exhausted", "rate limit", "rate_limit",
    "timeout", "timed out", "connection", "high demand", "try again",
]


class TemporaryError(Exception):
    # provider is busy / rate limited / slow. worth trying again or hopping
    pass


class PermanentError(Exception):
    # bad key, wrong model name... retrying the same provider wont help
    pass


class BadOutputError(Exception):
    # .provider is filled in by the router, so the pipeline can ask a DIFFERENT engine next time
    # provider answered, but not with valid json (often: answer got cut off)
    pass


class AllProvidersFailed(Exception):
    pass


# ---------------------------------------------------------
# turning errors and answers into something we understand
# ---------------------------------------------------------
def classify_error(error):
    message = str(error)

    # each sdk stores the http code in a different place
    code = getattr(error, "status_code", None)
    if code is None:
        code = getattr(error, "code", None)

    if isinstance(code, int):
        if code in TEMPORARY_CODES:
            return TemporaryError(message[:300])
        return PermanentError(message[:300])

    lower = message.lower()
    for word in TEMPORARY_WORDS:
        if word in lower:
            return TemporaryError(message[:300])

    # unknown problem: treat it as temporary, the router will hop anyway
    return TemporaryError(message[:300])


def parse_rows(text):
    # the answer should be {"rows": [...]}, but models sometimes wrap it
    # in ```json fences or add a sentence, so we dig the json out
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()

    data = None
    try:
        data = json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise BadOutputError("no json in the answer, it started with: " + text[:80].replace("\n", " "))
        try:
            data = json.loads(text[start:end + 1])
        except Exception:
            raise BadOutputError("broken json, answer started with: " + text[:80].replace("\n", " "))

    rows = []
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        if "rows" in data:
            rows = data["rows"]
        elif "material" in data:
            rows = [data]

    if not isinstance(rows, list):
        raise BadOutputError("'rows' is not a list")

    clean = []
    for row in rows:
        if isinstance(row, dict):
            clean.append(row)
    return clean


# ---------------------------------------------------------
# the three providers. each make_* returns a function: prompt -> text
# sdks are imported inside, so a missing package only disables that provider
# ---------------------------------------------------------
def make_gemini(api_key, model):
    from google import genai
    from google.genai import types

    # attempts=1: no hidden retries inside the sdk, our router controls retrying
    options = types.HttpOptions(
        timeout=REQUEST_TIMEOUT_SECONDS * 1000,
        retry_options=types.HttpRetryOptions(attempts=1),
    )
    client = genai.Client(api_key=api_key, http_options=options)

    def call(prompt):
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return response.text or ""

    return call


def make_claude(api_key, model):
    import anthropic

    client = anthropic.Anthropic(api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=0)

    def call(prompt):
        message = client.messages.create(
            model=model,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = []
        for block in message.content:
            if getattr(block, "type", "") == "text":
                parts.append(block.text)
        return "".join(parts)

    return call


def make_openai_style(api_key, model, base_url, json_mode):
    # one function for every provider that uses the openai api format.
    # base_url None = openai itself, otherwise cerebras / groq
    import openai

    client = openai.OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=0,
    )

    def call(prompt):
        settings = {}
        settings["model"] = model
        settings["messages"] = [{"role": "user", "content": prompt}]
        # only openai itself is guaranteed to support json mode on every model.
        # for the others the prompt already demands json, and parse_rows cleans it up
        if json_mode:
            settings["response_format"] = {"type": "json_object"}
        response = client.chat.completions.create(**settings)
        return response.choices[0].message.content or ""

    return call


def make_openai(api_key, model):
    return make_openai_style(api_key, model, None, True)


def make_cerebras(api_key, model):
    return make_openai_style(api_key, model, CEREBRAS_URL, False)


def make_groq(api_key, model):
    return make_openai_style(api_key, model, GROQ_URL, False)


def build_providers(get_secret):
    # get_secret(name) -> the key/value or "" (so this file doesnt depend on streamlit)
    # returns (providers in priority order, notes about anything skipped)
    # priority order: fast free engines first, paid engines as backups
    # paid engines first (only used if their key exists): their rate limits are far higher
    # than free tiers. then the fast free engines. gemini last: its free tier is the least reliable
    recipes = [
        ("Claude", "ANTHROPIC_API_KEY", "CLAUDE_MODEL", make_claude),
        ("OpenAI", "OPENAI_API_KEY", "OPENAI_MODEL", make_openai),
        ("Cerebras", "CEREBRAS_API_KEY", "CEREBRAS_MODEL", make_cerebras),
        ("Groq", "GROQ_API_KEY", "GROQ_MODEL", make_groq),
        ("Gemini", "GEMINI_API_KEY", "GEMINI_MODEL", make_gemini),
    ]

    providers = []
    notes = []
    for name, key_name, model_name, maker in recipes:
        key = get_secret(key_name)
        if not key:
            notes.append(name + ": no " + key_name + " set")
            continue

        model = get_secret(model_name) or DEFAULT_MODELS[model_name]
        try:
            call = maker(key, model)
        except ImportError:
            notes.append(name + ": python package not installed")
            continue
        except Exception as error:
            notes.append(name + ": could not start (" + str(error)[:120] + ")")
            continue

        provider = {}
        provider["name"] = name
        provider["model"] = model
        provider["call"] = call
        providers.append(provider)

    return providers, notes


def retry_after_seconds(error):
    # providers often say how long to wait: a "retry-after" header,
    # or google's "retryDelay": "7s" inside the message
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None)
    if headers is not None:
        try:
            value = headers.get("retry-after")
            if value:
                return float(value)
        except Exception:
            pass
    match = re.search(r"retry[^0-9]{0,30}?(\d+(?:\.\d+)?)\s*s", str(error), re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None


def cooldown_for(error):
    reason = short_reason(error)
    if reason.startswith("rate limited"):
        wait_seconds = retry_after_seconds(error)
        if wait_seconds is None:
            wait_seconds = RATE_LIMIT_COOLDOWN_SECONDS
        return min(MAX_COOLDOWN_SECONDS, max(1.0, wait_seconds))
    if reason.startswith("busy"):
        return BUSY_COOLDOWN_SECONDS
    return COOLDOWN_SECONDS


# ---------------------------------------------------------
# the router
# ---------------------------------------------------------
def new_router(providers):
    # one router per run. it is shared by all the parallel workers,
    # so every change to it happens inside the lock
    router = {}
    router["providers"] = providers
    router["lock"] = threading.Lock()
    router["cooldown_until"] = {}   # provider name -> time it can be used again
    router["disabled"] = {}         # provider name -> why it was switched off
    router["calls"] = {}            # provider name -> answers we actually used
    router["log"] = []              # one entry per call: who, how long, what happened
    router["in_flight"] = {}        # provider name -> calls running right now
    router["fail_streak"] = {}      # provider name -> failures in a row
    for provider in providers:
        router["calls"][provider["name"]] = 0
        router["in_flight"][provider["name"]] = 0
    return router


def short_reason(error):
    # turn a long sdk error into a few words for the engine report
    message = str(error).lower()
    code = getattr(error, "status_code", None)
    if code is None:
        code = getattr(error, "code", None)
    if code == 429 or "resource_exhausted" in message or "rate" in message:
        return "rate limited (429)"
    if code in [500, 502, 503, 529] or "unavailable" in message or "overloaded" in message:
        return "busy (" + str(code) + ")"
    if code in [408, 504] or "timeout" in message or "timed out" in message or "deadline" in message:
        return "timed out"
    if isinstance(code, int):
        return "error (" + str(code) + ")"
    return "error"


def write_log(router, name, seconds, outcome):
    entry = {}
    entry["provider"] = name
    entry["seconds"] = seconds
    entry["outcome"] = outcome
    with router["lock"]:
        router["log"].append(entry)


def ready_providers(router, skip=None):
    # providers that are not switched off and not cooling down.
    # the least busy engine goes first (priority order breaks ties), so 4 parallel
    # chunks spread over cerebras + groq + ... instead of all hitting cerebras
    # at once and getting rate limited
    candidates = []
    now = time.time()
    with router["lock"]:
        position = 0
        for provider in router["providers"]:
            name = provider["name"]
            position = position + 1
            if name in router["disabled"]:
                continue
            if skip is not None and name in skip:
                continue
            if router["cooldown_until"].get(name, 0) > now:
                continue
            candidates.append((router["in_flight"][name], position, provider))
    candidates.sort(key=lambda item: (item[0], item[1]))
    ready = []
    for item in candidates:
        ready.append(item[2])
    return ready


def everyone_disabled(router):
    with router["lock"]:
        return len(router["disabled"]) == len(router["providers"])


def seconds_until_someone_is_ready(router):
    now = time.time()
    shortest = COOLDOWN_SECONDS
    with router["lock"]:
        for provider in router["providers"]:
            name = provider["name"]
            if name in router["disabled"]:
                continue
            ready_at = router["cooldown_until"].get(name, 0)
            shortest = min(shortest, max(0, ready_at - now))
    return max(1, shortest)


def timed_call(router, provider, prompt):
    # runs in a background thread. never raises: returns what happened + how long it took
    name = provider["name"]
    start = time.time()
    try:
        result = ("ok", provider["call"](prompt))
    except Exception as error:
        result = ("error", error)
    finally:
        with router["lock"]:
            router["in_flight"][name] = router["in_flight"][name] - 1
    seconds = round(time.time() - start, 1)
    return result, seconds


def race(router, prompt, skip=None):
    # one round: ask the first ready provider; if it is slow, also ask the next one.
    # returns (rows, name) for the first good answer, or None if everyone failed.
    # raises BadOutputError the moment any engine gives an unreadable answer.
    queue = ready_providers(router, skip)
    if len(queue) == 0:
        return None, []

    errors = []
    pool = ThreadPoolExecutor(max_workers=len(queue))
    running = {}

    def start_next():
        if len(queue) > 0:
            provider = queue.pop(0)
            with router["lock"]:
                router["in_flight"][provider["name"]] = router["in_flight"][provider["name"]] + 1
            running[pool.submit(timed_call, router, provider, prompt)] = provider

    start_next()
    try:
        while len(running) > 0:
            done, _ = wait(list(running), timeout=HEDGE_SECONDS, return_when=FIRST_COMPLETED)

            if len(done) == 0:
                # nobody answered in time: start a backup provider and race them
                start_next()
                continue

            for future in done:
                provider = running.pop(future)
                name = provider["name"]
                (kind, payload), seconds = future.result()

                if kind == "error":
                    problem = classify_error(payload)
                    with router["lock"]:
                        streak = router["fail_streak"].get(name, 0) + 1
                        router["fail_streak"][name] = streak
                        if isinstance(problem, PermanentError):
                            router["disabled"][name] = str(problem)
                        elif streak >= MAX_FAILS_IN_A_ROW:
                            # this engine is struggling right now: stop wasting time on it this run
                            router["disabled"][name] = "failed " + str(streak) + " times in a row (" + short_reason(payload) + ")"
                        else:
                            router["cooldown_until"][name] = time.time() + cooldown_for(payload)
                    write_log(router, name, seconds, short_reason(payload))
                    errors.append(name + ": " + str(problem)[:200])
                    start_next()
                    continue

                try:
                    rows = parse_rows(payload)
                except BadOutputError as error:
                    # an unreadable answer usually means the chunk was too big.
                    # dont sit waiting for slower engines: hand it straight back so the
                    # pipeline splits the chunk and races the smaller pieces
                    write_log(router, name, seconds, "unreadable answer")
                    error.provider = name
                    raise error

                write_log(router, name, seconds, "answered")
                with router["lock"]:
                    router["fail_streak"][name] = 0
                    router["calls"][name] = router["calls"][name] + 1
                return (rows, name), errors
    finally:
        # dont wait for slower providers still running, we already have an answer
        pool.shutdown(wait=False)

    return None, errors


def ask(router, prompt, skip=None):
    # skip: engines NOT to use for this prompt (e.g. one that already gave an unreadable answer)
    # returns (rows, provider name). raises BadOutputError or AllProvidersFailed
    errors = []

    for round_number in range(ROUNDS):
        answer, round_errors = race(router, prompt, skip)
        errors = errors + round_errors
        if answer is not None:
            return answer

        if everyone_disabled(router):
            break
        if round_number < ROUNDS - 1:
            time.sleep(seconds_until_someone_is_ready(router))

    if len(errors) == 0:
        errors.append("no provider available")
    raise AllProvidersFailed(" | ".join(errors[-3:]))
