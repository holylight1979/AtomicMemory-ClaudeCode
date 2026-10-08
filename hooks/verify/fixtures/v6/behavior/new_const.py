"""new_const.py: 新寫法 fixture（查表）。反例：常數改壞（3 的值從 B 變 A）。"""
LOG = []


def log(msg):
    LOG.append(msg)


_GRADE = {1: "D", 2: "C", 3: "A", 4: "A"}
_LOGS = {1: "grade:low", 4: "grade:top"}


def grade(score):
    if score in _LOGS:
        log(_LOGS[score])
    return _GRADE.get(score, "?")


def merit_order():
    return ["A", "B", "C", "D"]
