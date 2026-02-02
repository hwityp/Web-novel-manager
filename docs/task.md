# WNAP v1.3.1 작업 목록

- [x] GUI 리팩토링: `run_with_existing_tasks`
- [x] `GoogleGenreExtractor` 수정: 서킷 브레이커 및 구문
- [x] 수정 사항 검증
- [x] 파이프라인 순서 리팩토링 (정규화 -> 검색)
- [x] 다이얼로그 UI 확정 (동적 높이)
- [x] WNAP v1.3.0 GUI 리팩토링
    - [x] `PipelineOrchestrator` 업데이트: 세분화된 실행 (Stage 1, 1.5, 2+3)
    - [x] `main_window.py` 업데이트: 구형 버튼 제거
    - [x] 5개 신규 버튼 추가 (폴더, 정규화, 장르, 일괄, 초기화)
    - [x] 상태 관리 로직 구현
    - [x] 편집 가능한 트리뷰 로직 구현
    - [x] 스마트 일괄 필터링 구현
    - [x] 엔드투엔드 워크플로우 검증 및 릴리스
- [x] WNAP v1.3.1 GUI 리팩토링 (UX 폴리싱)
    - [x] 편집을 위한 다이얼로그 데이터 미리 채우기
    - [x] 장르/실행 버튼 분리 (상태 머신)
    - [x] 테이블에서 `[미분류]` 태그 제거
    - [x] 진행 중 실시간 데이터 바인딩
    - [x] 다이얼로그 레이아웃 최적화 (자동 높이)
- [x] 로직 복구 및 로깅 (v1.3.1 핫픽스)
    - [x] NovelNet (ssn.so) 필터링 복구 (블랙리스트/화이트리스트)
    - [x] 날짜 기반 로깅 구현 (`wnap_YYYYMMDD.log`)
    - [x] 로그 인코딩 검증 (UTF-8)
- [x] WNAP v1.3.2 GUI 리팩토링 및 CLI 통합
    - [x] CLI 통합 (`--log-level`)
    - [x] GUI 리팩토링 (옵션, 레이아웃, 테이블, 버튼 제거/정리)
    - [x] 검증
- [x] WNAP v1.3.2 핫픽스
    - [x] 버튼 가시성 (밝은 텍스트)
    - [x] 테이블 조정 (컬럼 너비 1.5배)
- [x] WNAP v1.3.3 작업 목록
    - [x] 일괄 처리 실시간 업데이트
    - [x] 검증
- [x] WNAP v1.3.4 작업 목록
    - [x] 이원화된 로깅 시스템
    - [x] `wnap.log`: 간결한/단순 로그 (INFO 고정)
    - [x] `wnap_YYYYMMDD.log`: 상세 일일 로그 (DEBUG 고정, 터미널 상세 포착)
    - [x] `PipelineLogger`가 이중 핸들러를 사용하도록 업데이트
    - [x] 일일 로그에 `GenreClassifier` 터미널 출력 포착
    - [x] 터미널 출력 캡쳐 (재검증 및 포맷팅)
    - [x] 로그 vs 터미널의 링크 동기화 (NaverExtractor 계측됨)
- [x] WNAP v1.3.5 핫픽스
    - [x] 시작 시 충돌 수정 (AttributeError)
        - [x] `tag_configure`를 Treeview 초기화 이후로 이동
    - [x] 일괄 런타임 충돌 수정 (AttributeError)
        - [x] `_execute_batch`에서 `orchestrator` 로컬 인스턴스화

# WNAP v1.3.6 핫픽스 [현재]
- [x] NameError 수정 (formatter undefined)
    - [x] `PipelineLogger._setup_logger`에서 `formatter` 정의 복구
- [x] 코드 무결성 검사
    - [x] `main_window.py`의 import 및 변수 정의 검증
    - [x] `pipeline_orchestrator.py`의 import 및 변수 정의 검증
- [x] 마지막 사용 폴더 기억 구현
    - [x] `_on_closing`에서 종료 시 자동 config 저장
    - [x] `_update_config_from_ui`가 경로를 올바르게 캡처하는지 검증

# WNAP v1.3.7 미션: 규칙 최적화 및 안정성
- [x] 장르 추론 최적화
    - [x] 기존 태그(예: `[선협]`) 감지 시 API 검색 건너뛰기
    - [x] `GenreClassifierAdapter`에 구현
- [x] 정규화 로직 개선
    - [x] 정규식에서 '외전', '에필로그' 키워드 보존
    - [x] 테스트 케이스: "회귀했더니 입대 전날 1-529 完 에필 및 외전 포함"
- [x] CSV 매핑 경로 수정
    - [x] 메인 프로그램 루트(`os.path.abspath`)에 저장 강제
- [x] 시스템 안정성 및 UI
    - [x] `pipeline_logger.py`의 `NameError` 재검증
    - [x] 실시간 테이블 다시 그리기 검증
- [x] 최종 검증
    - [x] CSV 위치 및 정규화 로그 리포트

# WNAP v1.3.7 핫픽스: 윈도우 경로 처리
- [x] `PipelineOrchestrator._move_file`의 `FileNotFoundError` 수정
    - [x] 후행 공백이 있는 파일명 처리 (예: `abc .txt`)
    - [x] Windows `shutil.copy2`를 위한 `\\?\` 접두사 로직 구현
    - [x] 수정 사항 검증

# WNAP v1.3.7: 코드 무결성 및 정규화 견고성
- [x] "외전(Side Story)" 누락 문제 해결 (cleanup을 전역 범위로 이동)
- [x] 깨지기 쉬운 `\b` 정규식을 명시적 경계로 대체
- [x] 글로벌 코드 무결성 검사 실행 (`check_integrity.py`)
    - [x] 구문 검증 (py_compile)
    - [x] NameError 검증 (`formatter`)
    - [x] 정규화 로직 검증
- [x] 작업 공간 정리 (임시 파일을 `_cleanup_temp`로 이동)
- [x] GitHub 커밋 및 푸시 (`20081c9`)

# WNAP v1.3.4: PyInstaller 빌드 시스템
- [x] 요구사항 확인 (`pyinstaller`, `requirements.txt`)
- [x] `build_exe.py` 구성
    - [x] 버전을 1.3.4로 업데이트
    - [x] `--onedir`로 전환
    - [x] `.env` 외부 복사 로직 추가
- [x] `main_gui.py`에서 `sys._MEIPASS` 로직 검증
- [x] 실행 파일 빌드 (`python build_exe.py`)
- [x] 최종 검증 (UI, 로그, 기능)

# WNAP v1.3.5: 정규화 개선 및 재빌드
- [x] 버전 1.3.5로 업데이트 (Core, Build Script, Changelog)
- [x] 실행 파일 재빌드 (`python build_exe.py --clean`)
- [x] 출력 확인 (`dist/WNAP_Manager_v1.3.5`)

# WNAP v1.3.6: 외전 확장 및 재빌드
- [x] 버전 1.3.6으로 업데이트 (Core, Build Script, Changelog)
- [x] 실행 파일 재빌드 (`python build_exe.py --clean`)
- [x] 출력 확인 (`dist/WNAP_Manager_v1.3.6`)

# WNAP v1.3.8: 정규화 및 폴더 정리
- [x] 정규화 로직 개선 (Hotfix)
    - [x] `TitleAnchorExtractor` 정규식 보강 (完+, 외포, 完 외전 등)
    - [x] 숫자+단위(예: 1920 2부) 파싱 로직 개선 (`single_number_pattern`)
- [x] 폴더 정리 기능 업데이트
    - [x] `flatten_folders` 구현: 서브폴더 평탄화(Root로 이동) + 원본 Temp 백업
    - [x] `FolderOrganizerAdapter`가 기본적으로 평탄화 로직 사용하도록 변경
    - [x] 정리 후 파일 목록 재스캔 (`Re-scan`) 로직 추가 (Pipeline 연계 보장)
- [x] 버전 1.3.8 업데이트 (`core/version.py`, `build_exe.py`)
- [x] 실행 파일 빌드 (`WNAP_Manager_v1.3.8.exe`)
