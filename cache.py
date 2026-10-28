# cache.py
# remembers the llm's answers for a paper, so running the same paper again
# is instant and costs zero api calls. this is also our demo insurance:
# run the demo papers once before judging, and the live demo can't be
# slowed down (or broken) by a busy api.
#
# we store the RAW llm rows, not the verified table. verification is cheap and
# always re-runs, so if we improve verify.py, old cached papers get the new checks.

import hashlib
import json
import os
import uuid

from schema import PROMPT_VERSION
from text_tools import normalize

# folder where cached answers live (ignored by git)
CACHE_DIR = os.environ.get("DATUM_CACHE_DIR", ".datum_cache")


def cache_key(paper_fingerprint, target_properties, filter_pages):
    # the answer depends on: which paper, which properties, the prompt version,
    # and whether we scanned every page. change any of those = new key
    recipe = ""
    recipe = recipe + paper_fingerprint + "|"
    recipe = recipe + normalize(target_properties) + "|"
    recipe = recipe + PROMPT_VERSION + "|"
    recipe = recipe + str(filter_pages)
    return hashlib.sha256(recipe.encode("utf-8")).hexdigest()[:24]


def load(key):
    path = os.path.join(CACHE_DIR, key + ".json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        # a broken cache file just means "not cached"
        return None


def save(key, rows):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, key + ".json")
    # unique temp name: two threads saving the same paper at once must not share a temp file
    temp_path = path + "." + uuid.uuid4().hex[:8] + ".tmp"
    # write to a temp file first, then swap it in, so a crash never leaves half a file
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(rows, file, ensure_ascii=False)
    os.replace(temp_path, path)
