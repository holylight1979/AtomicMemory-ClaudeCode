"""new_boundary.py: 新寫法 fixture（查表）。反例：邊界變異（未列值的預設從 ? 變 F）。"""
LOG = []


def log(msg):
    LOG.append(msg)


_GRADE = {1: "D", 2: "C", 3: "B", 4: "A"}
_LOGS = {1: "grade:low", 4: "grade:top"}


def grade(score):
    if score in _LOGS:
        log(_LOGS[score])
    return _GRADE.get(score, "F")


def merit_order():
    return ["A", "B", "C", "D"]
