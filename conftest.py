"""
==============================================================================
파일: conftest.py
역할 및 목적:
    pytest 테스트 프레임워크 전역 설정 파일.
    프로젝트 루트를 sys.path에 선제 등록하여 모든 단위/통합 테스트에서 절대 경로 모듈 import를 보장합니다.
주요 구성 요소:
    - _project_root 등록 로직
상호 연관 관계 및 의존성:
    - Caller: pytest 러너
    - Callee: sys.path
수정 시 주의사항:
    - 테스트 실행 환경이 어떤 디렉토리에서 시작되든 항상 올바른 루트가 등록되도록 유지해야 합니다.
==============================================================================
"""
import sys
import os

# 프로젝트 루트를 sys.path에 추가
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
