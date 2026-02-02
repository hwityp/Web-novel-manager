# Changelog

이 프로젝트의 모든 주요 변경 사항을 기록합니다.

형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.0.0/)를 따르며,
버전 관리는 [Semantic Versioning](https://semver.org/lang/ko/)을 따릅니다.

## [1.3.8] - 2026-02-02

### ⚡ 개선 사항
- **폴더 정리 기능 (Folder Organizer)**:
  - **평탄화 및 백업 (Flatten & Backup)**: '폴더 정리' 실행 시 하위 폴더의 파일들을 최상위 폴더(Root)로 이동시키고, 원본 폴더 구조는 `Temp` 폴더로 안전하게 백업합니다.
  - **연계성 강화**: 폴더 정리 후 변경된 파일 위치를 자동으로 인식하여 다음 단계(장르 분석, 정규화)와의 파이프라인 연계를 보장합니다.
- **정규화 로직 (Normalization Logic)**:
  - **복합 완결 패턴 개선**: `完+ 외전` 같은 복합 패턴을 `(완) + 외전`으로 정확히 분리합니다.
  - **숫자+단위 파싱 개선**: `1920 2부`와 같이 숫자 뒤에 단위(부, 권, 화)가 붙을 때 숫자가 제목에 남는 오류를 수정했습니다.
  - **추가 외전/노이즈 태그**: `외포`(외전 포함) 키워드 인식 및 `(AI 번역)` 노이즈 제거 패턴을 보강했습니다.

## [1.3.6] - 2026-01-09

### ⚡ 개선 사항
- **정규화 로직 (Normalization Logic)**:
  - **새로운 외전 키워드**: '후일담' 및 '특외'를 외전 식별자로 추가 지원합니다.
    - 예시: `... 完 후일담.txt` → `... (완) + 후일담.txt`

## [1.3.5] - 2026-01-02

### ⚡ 개선 사항
- **정규화 로직 (Normalization Logic)**:
  - **(19N) 태그 보존**: 파일명에서 `(19N)` 태그가 더 이상 제거되지 않습니다.
  - **범위 정규화**: `001-242` 스타일의 범위를 `1-242`로 정규화합니다 (선행 0 제거).
  - **미분류 장르 처리**: 장르를 알 수 없는 경우 `[미분류]` 태그를 생략합니다 (예: `[미분류] Title.txt` 대신 `Title.txt`).

## [1.3.4] - 2026-01-02

### 🛠 수정 사항
- **외전 파싱 (Side Story Parsing)**:
  - `TitleAnchorExtractor`의 '외전' 및 '에필로그' 추출 로직 개선
  - 'Epilogue'가 'Side Story'를 가리는 문제 해결 (루프 추출 구현)
  - 감지 방해 요소인 연결어('및', '포함') 제거
- **GUI 안정성 (GUI Reliability)**:
  - 독립형 정규화 GUI에서 치명적인 import 오류 수정
  - `rename_normalize_gui.py`에서 상대 경로 import를 위한 `sys.path` 패치 적용
  - 오류를 숨기던 조용한 fallback 제거

## [1.2.0] - 2024-12-28 (Retroactive)
- 최근 개선 사항을 위한 기본 버전

## [1.0.0] - 2024-12-28

### 🎉 최초 릴리스

#### 추가 사항
- 3개 모듈 통합 파이프라인 완성
  - FolderOrganizer: 압축 해제 및 폴더 정리
  - GenreClassifier: 키워드 기반 장르 분류
  - FilenameNormalizer: 표준 파일명 생성
- Title Anchor Parsing 알고리즘 구현
  - 노이즈 제거 (저자명, 번역 정보, 플랫폼 태그)
  - 핵심 제목 추출 및 잔여 문자열 파싱
- 중국 소설 특수 처리
  - 선협(仙俠) 키워드 인식
  - 언정(言情) 키워드 인식
  - ~지(志), ~기(記) 패턴 감지
- GUI 대시보드 (CustomTkinter)
  - 폴더 선택 및 설정 패널
  - 실시간 진행 상황 표시
  - 장르 확인 다이얼로그 (Medium confidence)
  - 결과 테이블 및 로그 뷰어
- CLI 인터페이스
  - argparse 기반 옵션 파싱
  - --source, --target, --dry-run, --yes 옵션
- Dry-run 모드
  - 파일 시스템 변경 없이 미리보기
  - mapping_preview.csv 생성
- Fault Isolation (결함 격리)
  - 개별 파일 오류 시 해당 파일만 skip
  - 재시도 메커니즘 (max_retries 설정)
- 138개 테스트 통과
  - Unit Tests: 100+
  - Property-based Tests: 16 (Hypothesis)
  - Integration Tests: 10+
- PyInstaller EXE 패키징
  - 단일 실행 파일 생성
  - build_exe.py 빌드 스크립트

#### 아키텍처
- Adapter Pattern: 기존 모듈 무수정 래핑
- NovelTask 중심 설계: 통합 데이터 모델
- Pipeline Pattern: Stage 1 → 2 → 3 순서 보장
- Spec-Driven Development: 요구사항 → 설계 → 구현 → 테스트

---

## [Unreleased]

### 예정 사항
- 다중 플랫폼 지원 (macOS, Linux)
- 장르 분류 AI 모델 통합
- 배치 처리 성능 최적화
- 플러그인 시스템
