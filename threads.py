# threads.py
# saves threads to disk so they survive a page refresh (or a crash mid-demo).
#
# one thread = one folder:
#   .datum_threads/<thread id>/thread.json   <- title, papers, every run and its results
#   .datum_threads/<thread id>/<paper>.pdf   <- the uploaded pdfs
# the folder is ignored by git, so papers and results never end up on github.

import json
import os
import re
import shutil
import time
import uuid

THREADS_DIR = os.environ.get("DATUM_THREADS_DIR", ".datum_threads")


def thread_folder(thread_id):
    return os.path.join(THREADS_DIR, thread_id)


def safe_file_name(name):
    # keep letters, numbers, dots, dashes, underscores - nothing that could escape the folder
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", os.path.basename(str(name)))
    if cleaned == "" or cleaned.startswith("."):
        cleaned = "paper_" + cleaned
    return cleaned


def new_thread():
    thread = {}
    thread["id"] = uuid.uuid4().hex[:12]
    thread["title"] = "New thread"
    thread["created"] = time.time()
    thread["updated"] = time.time()
    thread["auto_title"] = True   # title follows the file names until the researcher renames it
    thread["properties"] = ""     # what to extract, kept per thread
    thread["papers"] = []   # list of {"name": original name, "file": saved file name, "size": bytes}
    thread["runs"] = []     # list of {"properties", "papers", "result", "created"}
    os.makedirs(thread_folder(thread["id"]), exist_ok=True)
    save(thread)
    return thread


def save(thread):
    thread["updated"] = time.time()
    folder = thread_folder(thread["id"])
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "thread.json")
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(thread, file, ensure_ascii=False)
    os.replace(temp_path, path)


def load(thread_id):
    path = os.path.join(thread_folder(thread_id), "thread.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return None


def list_threads():
    # newest first
    threads = []
    if not os.path.isdir(THREADS_DIR):
        return threads
    for thread_id in os.listdir(THREADS_DIR):
        thread = load(thread_id)
        if thread is not None:
            threads.append(thread)
    threads.sort(key=lambda item: item.get("updated", 0), reverse=True)
    return threads


def add_paper(thread, name, pdf_bytes):
    # same name uploaded again = replace it, so a thread never holds two copies
    file_name = safe_file_name(name)
    with open(os.path.join(thread_folder(thread["id"]), file_name), "wb") as file:
        file.write(pdf_bytes)
    for paper in thread["papers"]:
        if paper["name"] == name:
            paper["file"] = file_name
            paper["size"] = len(pdf_bytes)
            return
    paper = {}
    paper["name"] = name
    paper["file"] = file_name
    paper["size"] = len(pdf_bytes)
    thread["papers"].append(paper)
    update_auto_title(thread)


def remove_paper(thread, name):
    kept = []
    for paper in thread["papers"]:
        if paper["name"] == name:
            path = os.path.join(thread_folder(thread["id"]), paper["file"])
            if os.path.exists(path):
                os.remove(path)
        else:
            kept.append(paper)
    thread["papers"] = kept
    update_auto_title(thread)


def update_auto_title(thread):
    # default name = the file names the researcher uploaded
    if not thread.get("auto_title", True):
        return
    names = []
    for paper in thread["papers"]:
        names.append(os.path.splitext(paper["name"])[0])
    if len(names) == 0:
        thread["title"] = "New thread"
    elif len(names) == 1:
        thread["title"] = names[0]
    else:
        thread["title"] = names[0] + " + " + str(len(names) - 1) + " more"


def delete(thread_id):
    folder = thread_folder(thread_id)
    # only ever delete folders inside our own threads folder
    if os.path.abspath(folder).startswith(os.path.abspath(THREADS_DIR) + os.sep) and os.path.isdir(folder):
        shutil.rmtree(folder)


def paper_bytes(thread):
    # {original name: pdf bytes} for every paper in the thread
    found = {}
    for paper in thread["papers"]:
        path = os.path.join(thread_folder(thread["id"]), paper["file"])
        if os.path.exists(path):
            with open(path, "rb") as file:
                found[paper["name"]] = file.read()
    return found


def add_run(thread, properties, paper_names, result):
    run = {}
    run["properties"] = properties
    run["papers"] = list(paper_names)
    run["result"] = result
    run["created"] = time.time()
    thread["runs"].append(run)


def make_title(paper_names, properties):
    first = ""
    if len(paper_names) > 0:
        first = os.path.splitext(paper_names[0])[0].replace("_", " ")
        if len(first) > 22:
            first = first[:21] + "…"
        if len(paper_names) > 1:
            first = first + " +" + str(len(paper_names) - 1)
    props = properties.strip()
    if len(props) > 26:
        props = props[:25] + "…"
    if first and props:
        return first + " · " + props
    return first or props or "New thread"


def rename(thread, title):
    title = title.strip()
    if title != "":
        thread["title"] = title[:60]
        thread["auto_title"] = False
