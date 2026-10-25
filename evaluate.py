# evaluate.py
# the accuracy number for the pitch.
# a human writes an "answer key" csv (material, property, value) for a few papers,
# and we compare datum's table against it:
#   precision = of the rows datum extracted, how many were right
#   recall    = of the true values in the papers, how many datum found
#   caught    = of datum's WRONG rows, how many verification already marked review/flagged

from rapidfuzz import fuzz

from schema import STATUS_VERIFIED
from text_tools import normalize, to_number

# values count as equal if they are within 0.5% of each other
VALUE_TOLERANCE = 0.005


def same_material(a, b):
    a = normalize(a).replace(" ", "")
    b = normalize(b).replace(" ", "")
    if a == b:
        return True
    return fuzz.ratio(a, b) >= 90


def same_property(a, b):
    a = normalize(a)
    b = normalize(b)
    if a == "" or b == "":
        return False
    if fuzz.token_set_ratio(a, b) >= 80:
        return True
    return fuzz.partial_ratio(a, b) >= 85


def same_value(a, b):
    x = to_number(a)
    y = to_number(b)
    if x is None or y is None:
        return normalize(a) == normalize(b)
    if x == y:
        return True
    return abs(x - y) <= VALUE_TOLERANCE * max(abs(x), abs(y))


def read_answer_key(dataframe):
    # accept any capitalisation of the column names
    columns = {}
    for column in dataframe.columns:
        columns[str(column).strip().lower()] = column

    needed = ["material", "property", "value"]
    for name in needed:
        if name not in columns:
            raise ValueError("answer key needs columns: material, property, value")

    answers = []
    for _, line in dataframe.iterrows():
        answer = {}
        answer["material"] = str(line[columns["material"]])
        answer["property"] = str(line[columns["property"]])
        answer["value"] = str(line[columns["value"]])
        answers.append(answer)
    return answers


def evaluate(rows, answers):
    used = []           # answer-key lines already matched to a row
    results = []        # "correct" / "wrong" for each row, same order as rows
    correct = 0

    for row in rows:
        match_found = False
        for index in range(len(answers)):
            if index in used:
                continue
            answer = answers[index]
            if not same_material(row["material"], answer["material"]):
                continue
            if not same_property(row["property"], answer["property"]):
                continue
            if not same_value(row["value"], answer["value"]):
                continue
            used.append(index)
            match_found = True
            break

        if match_found:
            correct = correct + 1
            results.append("correct")
        else:
            results.append("wrong")

    wrong = len(rows) - correct
    caught = 0
    for index in range(len(rows)):
        if results[index] == "wrong" and rows[index]["status"] != STATUS_VERIFIED:
            caught = caught + 1

    missed = []
    for index in range(len(answers)):
        if index not in used:
            missed.append(answers[index])

    report = {}
    report["extracted"] = len(rows)
    report["correct"] = correct
    report["wrong"] = wrong
    report["wrong_caught"] = caught
    report["answer_key_size"] = len(answers)
    report["found"] = len(used)
    report["precision"] = correct / len(rows) if len(rows) > 0 else 0.0
    report["recall"] = len(used) / len(answers) if len(answers) > 0 else 0.0
    report["catch_rate"] = caught / wrong if wrong > 0 else 1.0
    report["row_results"] = results
    report["missed"] = missed
    return report
