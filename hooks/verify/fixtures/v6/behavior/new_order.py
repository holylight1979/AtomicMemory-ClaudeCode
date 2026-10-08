"""new_order.py: 新寫法 fixture（查表）。反例：順序變異（merit_order 的 B、C 對調）。"""
LOG = []


def log(msg):
    LOG.append(msg)


_GRADE = {1: "D", 2: "C", 3: "B", 4: "A"}
_LOGS = {1: "grade:low", 4: "grade:top"}


def grade(score):
    if score in _LOGS:
        log(_LOGS[score])
    return _GRADE.get(score, "?")


def merit_order():
    return ["A", "C", "B", "D"]
