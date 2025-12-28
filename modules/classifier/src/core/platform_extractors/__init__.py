"""
플랫폼별 장르 추출기 모듈
"""

from modules.classifier.src.core.platform_extractors.base_extractor import BasePlatformExtractor
from modules.classifier.src.core.platform_extractors.ridibooks_extractor import RidibooksExtractor
from modules.classifier.src.core.platform_extractors.munpia_extractor import MunpiaExtractor
from modules.classifier.src.core.platform_extractors.novelpia_extractor import NovelpiaExtractor
from modules.classifier.src.core.platform_extractors.naver_series_extractor import NaverSeriesExtractor
from modules.classifier.src.core.platform_extractors.kakao_extractor import KakaoExtractor
from modules.classifier.src.core.platform_extractors.novelnet_mrblue_extractors import NovelnetExtractor, MrblueExtractor

__all__ = [
    'BasePlatformExtractor',
    'RidibooksExtractor',
    'MunpiaExtractor',
    'NovelpiaExtractor',
    'NaverSeriesExtractor',
    'KakaoExtractor',
    'NovelnetExtractor',
    'MrblueExtractor',
]
