#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
==============================================================================
파일: tests/test_naver_api_hub_compatibility.py
역할 및 목적:
    NAVER API HUB (네이버 클라우드 플랫폼 NCP 신규 엔드포인트) 및
    레거시 네이버 오픈API와의 하이브리드 호환성, 헤더 인증 규격 및
    자동 교차 감지(Auto-Negotiation) 로직을 검증하는 단위 테스트.
==============================================================================
"""
import pytest
from unittest.mock import patch, MagicMock
from modules.classifier.src.core.naver_genre_extractor_v4 import NaverGenreExtractorV4
from modules.classifier.src.core.utils.search_strategy import SearchStrategy


class TestNaverApiHubCompatibility:
    """NAVER API HUB 및 레거시 네이버 검색 API 호환성 테스트"""

    def test_ncp_hub_headers_and_params(self):
        """NAVER API HUB 엔드포인트 지정 시 NCP 전용 헤더 및 format 파라미터 전송 검증"""
        conf = {
            'client_id': 'ncp_key_id_123',
            'client_secret': 'ncp_secret_456',
            'api_url': 'https://naverapihub.apigw.ntruss.com/search/v1/webkr'
        }
        extractor = NaverGenreExtractorV4(naver_api_config=conf)
        strategy = SearchStrategy('테스트 소설')

        with patch('requests.get') as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {'items': []}
            mock_get.return_value = mock_resp

            extractor._search_with_api('테스트 쿼리', '테스트 제목', strategy)

            assert mock_get.called
            args, kwargs = mock_get.call_args
            called_url = args[0]
            called_headers = kwargs.get('headers', {})
            called_params = kwargs.get('params', {})

            # 1. URL 검증
            assert 'naverapihub.apigw.ntruss.com' in called_url
            # 2. NCP 인증 헤더 검증
            assert called_headers.get('X-NCP-APIGW-API-KEY-ID') == 'ncp_key_id_123'
            assert called_headers.get('X-NCP-APIGW-API-KEY') == 'ncp_secret_456'
            assert 'X-Naver-Client-Id' not in called_headers
            # 3. format 파라미터 검증
            assert called_params.get('format') == 'json'
            assert called_params.get('query') == '테스트 쿼리'

    def test_legacy_naver_developer_headers(self):
        """레거시 개발자센터 엔드포인트일 때 기존 헤더 전송 검증"""
        conf = {
            'client_id': 'legacy_id_789',
            'client_secret': 'legacy_secret_abc',
            'api_url': 'https://openapi.naver.com/v1/search/webkr.json'
        }
        extractor = NaverGenreExtractorV4(naver_api_config=conf)
        strategy = SearchStrategy('테스트 소설')

        with patch('requests.get') as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {'items': []}
            mock_get.return_value = mock_resp

            extractor._search_with_api('테스트 쿼리', '테스트 제목', strategy)

            assert mock_get.called
            args, kwargs = mock_get.call_args
            called_url = args[0]
            called_headers = kwargs.get('headers', {})

            # 1. 레거시 URL 검증
            assert 'openapi.naver.com' in called_url
            # 2. 기존 인증 헤더 검증
            assert called_headers.get('X-Naver-Client-Id') == 'legacy_id_789'
            assert called_headers.get('X-Naver-Client-Secret') == 'legacy_secret_abc'
            assert 'X-NCP-APIGW-API-KEY-ID' not in called_headers

    def test_auto_negotiation_from_legacy_to_ncp(self):
        """레거시 시도 시 401 발생 시 NCP HUB로 자동 교차 시도 및 성공 검증"""
        conf = {
            'client_id': 'migrated_key_id',
            'client_secret': 'migrated_secret',
            # api_url 미지정 (기본값 openapi.naver.com)
        }
        extractor = NaverGenreExtractorV4(naver_api_config=conf)
        strategy = SearchStrategy('테스트 소설')

        # 첫 번째 호출(legacy)은 401, 두 번째 호출(ncp)은 200
        mock_resp_401 = MagicMock()
        mock_resp_401.status_code = 401
        mock_resp_401.json.return_value = {'errorMessage': 'Authentication failed'}

        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.json.return_value = {'items': []}

        with patch('requests.get', side_effect=[mock_resp_401, mock_resp_200]) as mock_get:
            extractor._search_with_api('쿼리', '제목', strategy)

            assert mock_get.call_count == 2
            # 1차 시도: 레거시
            first_call_args, first_call_kwargs = mock_get.call_args_list[0]
            assert 'openapi.naver.com' in first_call_args[0]

            # 2차 시도: NCP HUB로 교차 전환
            second_call_args, second_call_kwargs = mock_get.call_args_list[1]
            assert 'naverapihub.apigw.ntruss.com' in second_call_args[0]
            assert second_call_kwargs['headers']['X-NCP-APIGW-API-KEY-ID'] == 'migrated_key_id'
            # 이후 모드가 'ncp'로 저장됨
            assert extractor.api_mode == 'ncp'

    def test_modern_web_headers_configured(self):
        """웹 크롤링 시 모던 브라우저 헤더 및 세션 구성 검증"""
        extractor = NaverGenreExtractorV4()
        assert 'Sec-Ch-Ua' in extractor.headers
        assert 'Chrome/124' in extractor.headers['User-Agent']
        assert extractor.session is not None
        assert extractor.session.headers.get('Sec-Ch-Ua') is not None
