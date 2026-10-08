"""new_side.py: 新寫法 fixture（查表）。反例：副作用變異（grade:top 的守衛從 4 跑到 2）。"""
LOG = []


def log(msg):
    LOG.append(msg)


_GRADE = {1: "D", 2: "C", 3: "B", 4: "A"}
_LOGS = {1: "grade:low", 2: "grade:top"}


def grade(score):
    if score in _LOGS:
        log(_LOGS[score])
    return _GRADE.get(score, "?")


def merit_order():
    return ["A", "B", "C", "D"]
