# Implementation Plan: GUI UX Overhaul

## Overview

WNAP GUI의 전면적인 UX 고도화를 위한 구현 계획입니다. 로그 시스템 개편, 색상 대비 개선, 사용자 편의 기능 추가를 단계별로 구현합니다.

## Tasks

- [ ] 1. 유틸리티 클래스 구현
  - [x] 1.1 WindowStateManager 클래스 구현 (gui/utils/state_manager.py)
    - JSON 파일 저장/복원 로직
    - 화면 범위 검증 로직
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_
  - [x] 1.2 TooltipManager 클래스 구현 (gui/utils/tooltip_manager.py)
    - 500ms 지연 표시
    - 비차단 팝업 시스템
    - _Requirements: 6.2, 6.3, 6.5_
  - [x] 1.3 gui/utils/__init__.py 생성
    - 모듈 export 설정

- [ ] 2. PipelineLogger 수정
  - [x] 2.1 logs/wnap.log 파일 로깅 설정
    - 기본 로그 파일명을 wnap.log로 변경
    - GUI 모드에서 콘솔 출력 비활성화 옵션 추가
    - _Requirements: 1.2_

- [ ] 3. 테마 및 스타일 상수 업데이트
  - [x] 3.1 THEME 딕셔너리 정의 (gui/main_window.py)
    - 배경색 #2b2b2b, 텍스트 #FFFFFF/#E0E0E0
    - 프로그레스 바 색상 (하늘색/초록색)
    - 테이블 색상 (헤더, 홀수/짝수 행)
    - _Requirements: 2.1, 2.2, 5.1, 5.2_

- [ ] 4. 메인 윈도우 레이아웃 개편
  - [x] 4.1 로그 섹션 제거 및 레이아웃 재구성
    - _create_log_section 메서드 제거
    - grid row 구성 변경 (Treeview weight 5)
    - 프로그레스 바를 결과 테이블 섹션으로 이동
    - _Requirements: 1.1, 1.3, 1.4, 1.5_
  - [x] 4.2 색상 및 스타일 적용
    - 메인 윈도우 배경색 변경
    - 카드 배경색 및 텍스트 색상 변경
    - _Requirements: 2.1, 2.2, 2.5_
  - [x] 4.3 Treeview 스타일 개선
    - 헤더 스타일 (배경색, 볼드 텍스트)
    - 행 구분 (홀수/짝수 색상)
    - 32px 행 높이
    - _Requirements: 2.3, 2.4_

- [ ] 5. 인터랙션 기능 구현
  - [x] 5.1 Treeview 더블클릭 핸들러 구현
    - 이벤트 바인딩 (<Double-1>)
    - OS별 폴더 열기 로직 (Windows: explorer /select, macOS: open -R)
    - 오류 처리 (경로 없음, 폴더 없음)
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  - [x] 5.2 동적 프로그레스 바 색상 구현
    - _update_progress_bar_color 메서드 추가
    - 실행 시작 시 색상 변경 호출
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  - [x] 5.3 도움말 툴팁 연결
    - 설정 섹션에 (?) 아이콘 추가
    - TooltipManager 연결
    - TOOLTIP_TEXTS 정의
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 6. 윈도우 상태 관리 통합
  - [x] 6.1 WindowStateManager 통합
    - 앱 시작 시 상태 복원
    - 앱 종료 시 상태 저장 (WM_DELETE_WINDOW 프로토콜)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 7. 장르 다이얼로그 개선
  - [x] 7.1 폰트 크기 및 간격 조정 (gui/genre_confirm_dialog.py)
    - 폰트 크기 10-20% 증가
    - 컴포넌트 간 수직 간격 확대
    - 강조 박스 색상 대비 향상
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 8. Checkpoint - 기능 검증
  - 모든 UI 변경사항 시각적 확인
  - 더블클릭, 툴팁, 프로그레스 바 동작 확인

- [ ]* 9. 테스트 작성
  - [ ]* 9.1 WindowStateManager 단위 테스트
    - **Property 7: Window State Round-Trip**
    - **Property 8: Window Position Bounds Validation**
    - **Validates: Requirements 7.1, 7.2, 7.4**
  - [ ]* 9.2 테마 및 색상 테스트
    - **Property 2: Text Color Consistency**
    - **Property 5: Progress Bar Mode Color**
    - **Validates: Requirements 2.2, 5.1, 5.2**

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- 구현 순서: 유틸리티 → 테마 → 레이아웃 → 인터랙션 → 통합
- 각 단계 완료 후 시각적 확인 권장
