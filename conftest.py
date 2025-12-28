"""
Pytest Configuration

프로젝트 루트를 sys.path에 추가하여 절대 import를 지원합니다.
"""
import sys
import os

# 프로젝트 루트를 sys.path에 추가
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
