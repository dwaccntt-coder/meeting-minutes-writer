# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI 회의록 작성기 (AI Meeting Minutes Writer) — Windows 데스크톱 앱으로, 마이크(+선택적 시스템 오디오)를 녹음하고 Google Gemini API로 전사/요약하여 회의록을 자동 생성한다.

- **언어**: Python (순수 Python, 빌드 시스템 없음)
- **GUI**: CustomTkinter (다크 테마)
- **AI**: Google Gemini API (`google-genai` SDK)
- **DB**: SQLite (`meetings.db`)
- **대상 플랫폼**: Windows (맑은 고딕 폰트, `.bat` 스크립트, `ms-settings:` URI 등 Windows 전용 코드 포함)

## Commands

```bash
# 의존성 설치
pip install -r requirements.txt

# 실행
python main.py

# Windows에서 실행 (WindowsApps Python 충돌 우회)
run.bat
```

테스트 프레임워크는 없음. `.env` 파일에 `GEMINI_API_KEY` 필요.

## Architecture

```
main.py          ← GUI 전체 (CustomTkinter). MeetingApp이 메인 윈도우.
                   MetadataDialog(회의 정보 입력), StatsDialog(통계 대시보드),
                   HistoryDialog 등 다이얼로그를 포함.
recorder.py      ← AudioRecorder: sounddevice로 마이크 녹음, soundcard로 시스템 오디오 캡처.
                   오디오 전처리(normalize, noise gate) 포함. snapshot()으로 실시간 청크 추출.
transcriber.py   ← Gemini API 호출. transcribe(전사), transcribe_realtime(실시간 전사),
                   summarize(요약, 3가지 모드: standard/brief/action), generate_title.
                   20MB 초과 시 자동 청킹. 3개 언어(ko/en/ja) 프롬프트.
storage.py       ← SQLite CRUD. meetings 테이블에 회의 저장/조회/검색/삭제/통계.
exporter.py      ← 내보내기: Excel(openpyxl), Word(python-docx), PDF(fpdf2), Markdown.
                   각각 scope 파라미터로 전체/요약만/기록만 선택 가능.
templates.py     ← 회의 유형별(스탠드업, 브레인스토밍, 리뷰 등) 요약 프롬프트 접두사.
models.py        ← MeetingMetadata dataclass.
config.py        ← .env 로드, settings.json 기반 사용자 설정(저장 폴더, 언어).
toast.py         ← 우측 하단 토스트 알림 위젯.
```

## Key Design Decisions

- **실시간 전사**: 녹음 중 주기적으로 `recorder.snapshot()` → `transcribe_realtime()`으로 라이브 텍스트 표시. 녹음 종료 시 전체 오디오로 최종 전사 수행.
- **다국어**: ko/en/ja 3개 언어. 전사/요약 프롬프트, 회의 템플릿 모두 언어별 분리. UI 텍스트는 main.py 내 하드코딩.
- **시스템 오디오 캡처**: `soundcard` 패키지(선택적 의존성). 마이크 0.6 + 시스템 0.4 비율로 믹싱.
- **내보내기 파일명**: `{제목}_{타임스탬프}.{확장자}` 형식, 저장 폴더는 settings.json에서 관리.
- **PDF 폰트**: Windows `malgun.ttf`/`malgunbd.ttf` 직접 참조. 없으면 `gulim.ttc` 폴백.
