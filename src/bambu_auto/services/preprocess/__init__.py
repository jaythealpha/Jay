"""이미지 전처리: 3D 생성기에 적합한 형태로 입력을 정규화·평가.

- normalize: 결정적 정규화(배경 정리·정사각 캔버스·표준 해상도·대비 보정)
- vision_assess: Claude vision으로 3D 생성 적합도 평가·프롬프트 강화
"""

from bambu_auto.services.preprocess.normalize import NormalizeResult, normalize_image
from bambu_auto.services.preprocess.vision_assess import Assessment, assess_image

__all__ = ["NormalizeResult", "normalize_image", "Assessment", "assess_image"]
