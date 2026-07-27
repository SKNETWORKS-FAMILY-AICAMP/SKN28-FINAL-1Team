"""[호환 shim] 태깅 기능은 collector/util/tagging 패키지로 이동했다.

기존 임포트 경로를 유지하기 위한 재수출만 남긴다. 새 코드는 util.tagging을 직접 쓴다:

    from util.tagging import get_sync_tagger, merge_tags
"""

import config  # noqa: F401  (sys.path에 collector/ 추가 부수효과)

from util.tagging import get_sync_tagger, merge_tags  # noqa: F401
from util.tagging.base import (  # noqa: F401
    LAYER_ROLES,
    SEASONS,
    STYLES,
    SYSTEM_PROMPT,
    build_openai_messages as build_messages,
    openai_response_format as response_format,
)
from util.tagging.openai_tagger import OpenAITagger as LLMTagger  # noqa: F401
