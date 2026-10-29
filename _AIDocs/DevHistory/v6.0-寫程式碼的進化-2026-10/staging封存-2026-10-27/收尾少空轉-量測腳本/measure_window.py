"""用 stop_measure 同一套口徑量指定時間窗（UTC）。
跑法：python -X utf8 measure_window.py <起 ISO> <迄 ISO>
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stop_measure as sm

sm.W0, sm.W1 = sys.argv[1], sys.argv[2]
sm.main()
