# Changelog

이 프로젝트의 모든 주요 변경 사항을 기록합니다.

형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.0.0/)를 따르며,
버전 관리는 [Semantic Versioning](https://semver.org/lang/ko/)을 따릅니다.

## [1.0.0] - 2024-12-28

### 🎉 최초 릴리스

#### Added (추가)
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

#### Architecture (아키텍처)
- Adapter Pattern: 기존 모듈 무수정 래핑
- NovelTask 중심 설계: 통합 데이터 모델
- Pipeline Pattern: Stage 1 → 2 → 3 순서 보장
- Spec-Driven Development: 요구사항 → 설계 → 구현 → 테스트

---

## [Unreleased]

### Planned (예정)
- 다중 플랫폼 지원 (macOS, Linux)
- 장르 분류 AI 모델 통합
- 배치 처리 성능 최적화
- 플러그인 시스템
