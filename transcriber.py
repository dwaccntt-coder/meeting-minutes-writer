import time
import os
import tempfile
import numpy as np
import soundfile as sf
from google import genai

from config import GEMINI_API_KEY, GEMINI_MODEL, MAX_AUDIO_CHUNK_MB

# ── 클라이언트 초기화 (lazy) ─────────────────────────────────────
_client = None


def _get_client():
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError(
                "API 키가 설정되지 않았습니다.\n"
                ".env 파일에 GEMINI_API_KEY를 입력해 주세요."
            )
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


# ── API 호출 (재시도 포함) ───────────────────────────────────────
def _call_api(contents, max_retries=3):
    client = _get_client()
    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
            )
            return response.text or ""
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(2 ** (attempt + 1))
                continue
    raise RuntimeError(f"API 호출 실패 ({max_retries}회 시도): {last_error}")


# ── 오디오 청킹 ─────────────────────────────────────────────────
def _chunk_audio(audio_path):
    """20MB 초과 시 오디오를 분할하여 파일 경로 리스트 반환."""
    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    if file_size_mb <= MAX_AUDIO_CHUNK_MB:
        return [audio_path]

    data, sr = sf.read(audio_path)
    chunk_samples = int(sr * 60 * 9)  # 약 9분 단위
    overlap_samples = int(sr * 2)     # 2초 오버랩
    chunks = []
    start = 0

    while start < len(data):
        end = min(start + chunk_samples, len(data))
        chunk = data[start:end]
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(tmp.name, chunk, sr)
        chunks.append(tmp.name)
        if end >= len(data):
            break
        start = end - overlap_samples

    return chunks


# ── 언어별 전사 프롬프트 ─────────────────────────────────────────
TRANSCRIPTION_PROMPTS = {
    "ko": """\
당신은 전문 회의록 작성자입니다. 다음 오디오를 한국어로 정확하게 전사해 주세요.

## 규칙
1. 각 발화를 새 줄에 작성하세요.
2. 화자가 바뀔 때마다 "화자 A:", "화자 B:" 등으로 구분하세요.
   - 같은 화자가 연속 발화하면 화자 레이블을 반복하지 마세요.
3. 각 발화 블록 시작에 대략적인 타임스탬프를 [MM:SS] 형식으로 표기하세요.
4. 들리지 않거나 불명확한 부분은 [불명확]으로 표기하세요.
5. "음", "어", "그" 같은 필러는 제외하세요.
6. 말한 내용만 출력하세요. 설명, 주석, 인사말 없이 전사문만 작성하세요.

## 출력 형식 예시
[00:00] 화자 A: 오늘 회의 시작하겠습니다.
[00:05] 화자 B: 네, 지난주 액션 아이템부터 확인할까요?
""",
    "en": """\
You are a professional meeting transcriber. Transcribe the following audio accurately in English.

## Rules
1. Write each utterance on a new line.
2. Label speakers as "Speaker A:", "Speaker B:", etc.
   - Do not repeat the label if the same speaker continues.
3. Add approximate timestamps in [MM:SS] format at the start of each block.
4. Mark unclear parts as [unclear].
5. Remove fillers ("um", "uh", "like").
6. Output only the transcript, no explanations or comments.

## Output format example
[00:00] Speaker A: Let's start today's meeting.
[00:05] Speaker B: Sure, shall we check last week's action items?
""",
    "ja": """\
あなたはプロの議事録作成者です。以下の音声を日本語で正確に文字起こししてください。

## ルール
1. 各発話を新しい行に書いてください。
2. 話者が変わるたびに「話者A:」「話者B:」などで区別してください。
3. 各発話ブロックの先頭にタイムスタンプを[MM:SS]形式で記載してください。
4. 聞き取れない部分は[不明瞭]と記載してください。
5. 「えーと」「あの」などのフィラーは除外してください。
6. 発話内容のみを出力してください。

## 出力形式の例
[00:00] 話者A: 本日の会議を始めます。
[00:05] 話者B: はい、先週のアクションアイテムから確認しましょうか。
""",
}

REALTIME_PROMPTS = {
    "ko": "다음 오디오를 한국어로 전사해 주세요. 화자 구분하고, 말한 내용만 출력하세요. 필러(\"음\",\"어\",\"그\")는 제외하세요. 설명 없이 전사문만 작성하세요.",
    "en": "Transcribe the following audio in English. Distinguish speakers. Output only the transcript without fillers or explanations.",
    "ja": "以下の音声を日本語で文字起こししてください。話者を区別し、発話内容のみを出力してください。フィラーは除外してください。",
}

# ── 요약 프롬프트 (3가지 형식 x 3개 언어) ────────────────────────
SUMMARY_PROMPTS = {
    "ko": {
        "standard": """\
당신은 숙련된 비서입니다. 다음 회의 전사본을 분석하여 아래 형식으로 정리해 주세요.

## 회의 개요
- 참석자: (전사본에서 식별된 화자 목록)
- 주요 주제: (1줄 요약)
- 화자별 발언 비율: (각 화자의 대략적 발언 비율을 백분율로 표시)

## 핵심 논의 사항
(번호를 매겨 3~7개 핵심 포인트를 정리)

## 결정 사항
(회의에서 확정된 결정만 나열. 없으면 "결정 사항 없음")

## 액션 아이템
(담당자 | 내용 | 기한 형식으로 정리. 없으면 "액션 아이템 없음")

## 다음 단계
(후속 회의, 보류 사항 등)

전사본:
{text}""",

        "brief": """\
다음 회의 내용을 3문장 이내로 요약해 주세요.
가장 중요한 결정과 액션 아이템만 포함하세요.

{text}""",

        "action": """\
다음 회의 전사본에서 액션 아이템만 추출해 주세요.

형식:
- [ ] [담당자] 내용 (기한: YYYY-MM-DD 또는 "미정")

담당자가 불명확하면 "미정"으로 표기하세요.

{text}""",
    },
    "en": {
        "standard": """\
You are a skilled assistant. Analyze the following meeting transcript and summarize in the format below.

## Meeting Overview
- Attendees: (list of speakers identified)
- Main Topic: (1-line summary)
- Speaker participation ratio: (approximate percentage for each speaker)

## Key Discussion Points
(Number 3-7 key points)

## Decisions
(List confirmed decisions only. If none, state "No decisions made")

## Action Items
(Format: Assignee | Task | Deadline. If none, state "No action items")

## Next Steps
(Follow-up meetings, pending items, etc.)

Transcript:
{text}""",

        "brief": """\
Summarize the following meeting in 3 sentences or less.
Include only the most important decisions and action items.

{text}""",

        "action": """\
Extract only the action items from the following meeting transcript.

Format:
- [ ] [Assignee] Task (Deadline: YYYY-MM-DD or "TBD")

If the assignee is unclear, mark as "TBD".

{text}""",
    },
    "ja": {
        "standard": """\
あなたは熟練した秘書です。以下の会議議事録を分析し、下記の形式で整理してください。

## 会議概要
- 参加者: (議事録から特定された話者リスト)
- 主要議題: (1行要約)
- 話者別発言比率: (各話者のおおよその発言比率をパーセンテージで表示)

## 主要討議事項
(3〜7個の要点を番号付きで整理)

## 決定事項
(会議で確定した決定のみ列挙。なければ「決定事項なし」)

## アクションアイテム
(担当者 | 内容 | 期限の形式で整理。なければ「アクションアイテムなし」)

## 次のステップ
(フォローアップ会議、保留事項など)

議事録:
{text}""",

        "brief": """\
以下の会議内容を3文以内で要約してください。
最も重要な決定とアクションアイテムのみ含めてください。

{text}""",

        "action": """\
以下の会議議事録からアクションアイテムのみを抽出してください。

形式:
- [ ] [担当者] 内容 (期限: YYYY-MM-DD または「未定」)

担当者が不明な場合は「未定」と記載してください。

{text}""",
    },
}

# 하위 호환성을 위한 기본 프롬프트
TRANSCRIPTION_PROMPT = TRANSCRIPTION_PROMPTS["ko"]
REALTIME_PROMPT = REALTIME_PROMPTS["ko"]


# ── 공개 API ─────────────────────────────────────────────────────
def transcribe(audio_path, lang="ko", num_speakers=0):
    """오디오 파일을 전사하여 텍스트 반환. 긴 파일은 자동 분할."""
    chunks = _chunk_audio(audio_path)
    results = []

    prompt = TRANSCRIPTION_PROMPTS.get(lang, TRANSCRIPTION_PROMPTS["ko"])
    if num_speakers > 0:
        speaker_hint = {
            "ko": f"\n참고: 이 회의에는 {num_speakers}명이 참석했습니다. 화자를 {num_speakers}명으로 구분해 주세요.\n",
            "en": f"\nNote: There are {num_speakers} participants. Please distinguish {num_speakers} speakers.\n",
            "ja": f"\n参考: この会議には{num_speakers}名が参加しています。話者を{num_speakers}名で区別してください。\n",
        }
        prompt += speaker_hint.get(lang, speaker_hint["ko"])

    for chunk_path in chunks:
        with open(chunk_path, "rb") as f:
            audio_data = f.read()

        text = _call_api([
            prompt,
            genai.types.Part.from_bytes(data=audio_data, mime_type="audio/wav"),
        ])
        results.append(text)

        if chunk_path != audio_path:
            try:
                os.remove(chunk_path)
            except OSError:
                pass

    return "\n".join(results)


def transcribe_realtime(audio_path, lang="ko"):
    """실시간용 간략 전사 (빠른 응답 우선)."""
    with open(audio_path, "rb") as f:
        audio_data = f.read()

    prompt = REALTIME_PROMPTS.get(lang, REALTIME_PROMPTS["ko"])
    return _call_api([
        prompt,
        genai.types.Part.from_bytes(data=audio_data, mime_type="audio/wav"),
    ])


def summarize(full_text, mode="standard", lang="ko"):
    """회의 텍스트를 요약. mode: 'standard', 'brief', 'action'"""
    if not full_text.strip():
        return "(내용 없음)"

    time.sleep(1)

    lang_prompts = SUMMARY_PROMPTS.get(lang, SUMMARY_PROMPTS["ko"])
    prompt_template = lang_prompts.get(mode, lang_prompts["standard"])
    prompt = prompt_template.format(text=full_text)
    result = _call_api(prompt)

    titles = {
        "ko": {"standard": "[ 회의 요약 ]", "brief": "[ 간단 요약 ]", "action": "[ 액션 아이템 ]"},
        "en": {"standard": "[ Meeting Summary ]", "brief": "[ Brief Summary ]", "action": "[ Action Items ]"},
        "ja": {"standard": "[ 会議要約 ]", "brief": "[ 簡単要約 ]", "action": "[ アクションアイテム ]"},
    }
    lang_titles = titles.get(lang, titles["ko"])
    title = lang_titles.get(mode, lang_titles["standard"])
    return f"{title}\n\n{result}"


def generate_title(text, lang="ko"):
    """회의 내용을 기반으로 간결한 제목을 자동 생성한다."""
    prompts = {
        "ko": "다음 회의 내용을 기반으로 간결한 한국어 제목(10자 이내)을 하나만 생성하세요. 제목만 출력하세요.\n\n",
        "en": "Generate a concise English title (under 8 words) for the following meeting. Output only the title.\n\n",
        "ja": "以下の会議内容に基づいて、簡潔な日本語のタイトル（10文字以内）を1つだけ生成してください。タイトルのみ出力してください。\n\n",
    }
    prompt = prompts.get(lang, prompts["ko"]) + text[:500]
    result = _call_api(prompt)
    # 따옴표 제거 등 정리
    return result.strip().strip('"').strip("'").strip()
