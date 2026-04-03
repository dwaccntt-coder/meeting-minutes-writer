"""회의 유형별 요약 프롬프트 템플릿 (다국어 지원)."""

MEETING_TEMPLATES = {
    "ko": {
        "일반 회의": {"description": "일반적인 회의 요약", "summary_prefix": ""},
        "스탠드업": {
            "description": "데일리 스탠드업 미팅",
            "summary_prefix": (
                "이 회의는 데일리 스탠드업 미팅입니다. "
                "각 참석자별로 다음 항목을 정리해 주세요:\n"
                "- 어제 한 일\n- 오늘 할 일\n- 블로커/장애 사항\n\n"
            ),
        },
        "브레인스토밍": {
            "description": "아이디어 발산 회의",
            "summary_prefix": (
                "이 회의는 브레인스토밍 세션입니다. "
                "다음 형식으로 정리해 주세요:\n"
                "1. 제안된 아이디어를 테마별로 그룹핑\n"
                "2. 각 아이디어의 장단점\n"
                "3. 가장 많이 지지받은 아이디어 TOP 3\n\n"
            ),
        },
        "리뷰": {
            "description": "코드/스프린트/성과 리뷰",
            "summary_prefix": (
                "이 회의는 리뷰 미팅입니다. "
                "다음 형식으로 정리해 주세요:\n"
                "1. 리뷰 대상 항목\n2. 승인된 사항\n"
                "3. 거절/수정 요청 사항\n4. 후속 조치 필요 항목\n\n"
            ),
        },
        "기타": {"description": "사용자 정의 회의", "summary_prefix": ""},
    },
    "en": {
        "일반 회의": {"description": "General meeting", "summary_prefix": ""},
        "스탠드업": {
            "description": "Daily standup",
            "summary_prefix": (
                "This is a daily standup meeting. "
                "Organize by each attendee:\n"
                "- What they did yesterday\n- What they'll do today\n- Blockers\n\n"
            ),
        },
        "브레인스토밍": {
            "description": "Brainstorming session",
            "summary_prefix": (
                "This is a brainstorming session. Organize as follows:\n"
                "1. Group proposed ideas by theme\n"
                "2. Pros and cons of each idea\n"
                "3. Top 3 most supported ideas\n\n"
            ),
        },
        "리뷰": {
            "description": "Review meeting",
            "summary_prefix": (
                "This is a review meeting. Organize as follows:\n"
                "1. Items reviewed\n2. Approved items\n"
                "3. Rejected/revision requests\n4. Follow-up items\n\n"
            ),
        },
        "기타": {"description": "Custom meeting", "summary_prefix": ""},
    },
    "ja": {
        "일반 회의": {"description": "一般会議", "summary_prefix": ""},
        "스탠드업": {
            "description": "デイリースタンドアップ",
            "summary_prefix": (
                "これはデイリースタンドアップミーティングです。"
                "各参加者について以下の項目を整理してください:\n"
                "- 昨日やったこと\n- 今日やること\n- ブロッカー/障害\n\n"
            ),
        },
        "브레인스토밍": {
            "description": "ブレインストーミング",
            "summary_prefix": (
                "これはブレインストーミングセッションです。"
                "以下の形式で整理してください:\n"
                "1. 提案されたアイデアをテーマ別にグルーピング\n"
                "2. 各アイデアの長所と短所\n"
                "3. 最も支持されたアイデアTOP 3\n\n"
            ),
        },
        "리뷰": {
            "description": "レビュー会議",
            "summary_prefix": (
                "これはレビューミーティングです。"
                "以下の形式で整理してください:\n"
                "1. レビュー対象項目\n2. 承認された事項\n"
                "3. 却下/修正要求事項\n4. フォローアップ必要項目\n\n"
            ),
        },
        "기타": {"description": "カスタム会議", "summary_prefix": ""},
    },
}


def get_template_prefix(meeting_type, lang="ko"):
    """회의 유형에 맞는 요약 프롬프트 접두사 반환."""
    lang_templates = MEETING_TEMPLATES.get(lang, MEETING_TEMPLATES["ko"])
    template = lang_templates.get(meeting_type, lang_templates.get("일반 회의", {"summary_prefix": ""}))
    return template["summary_prefix"]
