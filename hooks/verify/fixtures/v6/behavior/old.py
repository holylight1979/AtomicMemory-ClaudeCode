"""old.py: 舊寫法 fixture（if/elif 鏈＋散落副作用）。只給 preserve-check 用 regex 解析成預期表，不被 import。"""
LOG = []


def log(msg):
    LOG.append(msg)


def grade(score):
    if score == 1:
        log("grade:low")
        return "D"
    elif score == 2:
        return "C"
    elif score == 3:
        return "B"
    elif score == 4:
        log("grade:top")
        return "A"
    else:
        return "?"


def merit_order():
    return ["A", "B", "C", "D"]
