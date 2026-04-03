import customtkinter as ctk
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
import threading
import os
import glob
import shutil
import numpy as np
from datetime import datetime

from recorder import AudioRecorder
from transcriber import transcribe, transcribe_realtime, summarize, generate_title
from models import MeetingMetadata
from templates import get_template_prefix
from config import get_save_folder, set_save_folder, get_language, set_language

# ── 테마 설정 ──
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── 색상 팔레트 ──
C = {
    "bg": "#1a1a2e",
    "surface": "#16213e",
    "card": "#0f3460",
    "accent": "#e94560",
    "accent2": "#533483",
    "green": "#00b894",
    "orange": "#fdcb6e",
    "red": "#d63031",
    "text": "#dfe6e9",
    "text2": "#b2bec3",
    "border": "#2d3436",
}

# ── 키워드 하이라이트 설정 (#3) ──
HIGHLIGHT_KEYWORDS = {
    "kw_decision": ["결정", "결론", "확정", "합의", "승인", "decided", "approved", "決定"],
    "kw_action": ["액션", "해야", "담당", "진행", "조치", "action", "assign", "アクション"],
    "kw_deadline": ["마감", "기한", "데드라인", "까지", "deadline", "due", "期限"],
    "kw_important": ["중요", "핵심", "필수", "반드시", "critical", "important", "重要"],
}

HIGHLIGHT_COLORS = {
    "kw_decision": "#00b894",
    "kw_action": "#fdcb6e",
    "kw_deadline": "#d63031",
    "kw_important": "#e94560",
}

# ── 언어 매핑 (#8) ──
LANG_MAP = {"한국어": "ko", "English": "en", "日本語": "ja"}
LANG_DISPLAY = {"ko": "한국어", "en": "English", "ja": "日本語"}


class StatsDialog(ctk.CTkToplevel):
    """회의 통계 대시보드 다이얼로그 (#7)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("회의 통계")
        self.geometry("520x500")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self._build_ui()
        self.after(10, self._center)

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        from storage import get_meeting_stats
        stats = get_meeting_stats()

        ctk.CTkLabel(
            self, text="회의 통계 대시보드",
            font=ctk.CTkFont(family="맑은 고딕", size=18, weight="bold"),
            text_color=C["accent"],
        ).pack(pady=(15, 5))

        ctk.CTkLabel(
            self, text=f"총 회의 수: {stats['total']}회",
            font=ctk.CTkFont(size=14), text_color=C["text"],
        ).pack(pady=(0, 10))

        ctk.CTkLabel(
            self, text="월별 회의 횟수",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=C["text2"],
        ).pack(anchor="w", padx=20, pady=(5, 2))

        monthly_frame = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=8)
        monthly_frame.pack(fill="x", padx=20, pady=(0, 10))

        if stats["monthly"]:
            max_count = max(c for _, c in stats["monthly"])
            for month, count in stats["monthly"]:
                row = ctk.CTkFrame(monthly_frame, fg_color="transparent")
                row.pack(fill="x", padx=10, pady=2)
                ctk.CTkLabel(row, text=month, width=80, anchor="w",
                             font=ctk.CTkFont(size=11), text_color=C["text2"]).pack(side="left")
                bar_pct = count / max_count if max_count > 0 else 0
                bar = ctk.CTkProgressBar(row, width=250, height=14)
                bar.pack(side="left", padx=(4, 8))
                bar.set(bar_pct)
                ctk.CTkLabel(row, text=f"{count}회", width=40,
                             font=ctk.CTkFont(size=11), text_color=C["text"]).pack(side="left")
        else:
            ctk.CTkLabel(monthly_frame, text="데이터 없음",
                         font=ctk.CTkFont(size=11), text_color=C["text2"]).pack(pady=10)

        ctk.CTkLabel(
            self, text="빈출 키워드 TOP 15",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=C["text2"],
        ).pack(anchor="w", padx=20, pady=(10, 2))

        kw_frame = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=8)
        kw_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        if stats["top_keywords"]:
            flow_frame = ctk.CTkFrame(kw_frame, fg_color="transparent")
            flow_frame.pack(fill="both", expand=True, padx=10, pady=10)
            max_freq = stats["top_keywords"][0][1]
            colors = [C["accent"], C["green"], C["orange"], C["accent2"], "#74b9ff"]
            for i, (word, freq) in enumerate(stats["top_keywords"][:15]):
                size = max(10, int(10 + (freq / max_freq) * 12))
                color = colors[i % len(colors)]
                ctk.CTkLabel(
                    flow_frame, text=f"{word}({freq})",
                    font=ctk.CTkFont(size=size, weight="bold"),
                    text_color=color,
                ).pack(side="left", padx=4, pady=2)
        else:
            ctk.CTkLabel(kw_frame, text="데이터 없음",
                         font=ctk.CTkFont(size=11), text_color=C["text2"]).pack(pady=10)

        ctk.CTkButton(
            self, text="닫기", width=100, height=32,
            fg_color=C["border"], hover_color="#636e72",
            command=self.destroy,
        ).pack(pady=(0, 12))


class MetadataDialog(ctk.CTkToplevel):
    """회의 정보 입력 다이얼로그."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("새 회의")
        self.geometry("480x520")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.result = None
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.after(10, self._center)

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        ctk.CTkLabel(
            self, text="회의 정보를 입력하세요",
            font=ctk.CTkFont(family="맑은 고딕", size=18, weight="bold"),
        ).pack(pady=(25, 20))

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="x", padx=30)

        fields = [
            ("회의 제목", "회의"),
            ("날짜", datetime.now().strftime("%Y-%m-%d")),
            ("참석자", ""),
            ("장소", ""),
            ("참석자 수", ""),
        ]
        self.entries = {}
        for label_text, default in fields:
            row = ctk.CTkFrame(form, fg_color="transparent")
            row.pack(fill="x", pady=5)
            ctk.CTkLabel(row, text=label_text, width=80, anchor="w",
                         font=ctk.CTkFont(size=13)).pack(side="left")
            entry = ctk.CTkEntry(row, placeholder_text=label_text, height=36,
                                 font=ctk.CTkFont(size=13))
            entry.pack(side="left", fill="x", expand=True, padx=(8, 0))
            if default:
                entry.insert(0, default)
            self.entries[label_text] = entry

        type_row = ctk.CTkFrame(form, fg_color="transparent")
        type_row.pack(fill="x", pady=5)
        ctk.CTkLabel(type_row, text="회의 유형", width=80, anchor="w",
                     font=ctk.CTkFont(size=13)).pack(side="left")
        self.combo_type = ctk.CTkComboBox(
            type_row, values=MeetingMetadata.MEETING_TYPES,
            height=36, font=ctk.CTkFont(size=13), state="readonly",
        )
        self.combo_type.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self.combo_type.set("일반 회의")

        # 시스템 오디오 캡처 (#5)
        self.capture_system_var = tk.BooleanVar(value=False)
        sys_audio_row = ctk.CTkFrame(form, fg_color="transparent")
        sys_audio_row.pack(fill="x", pady=(10, 0))
        self.chk_system_audio = ctk.CTkCheckBox(
            sys_audio_row, text="시스템 오디오 포함 (온라인 회의용)",
            variable=self.capture_system_var,
            font=ctk.CTkFont(size=12),
        )
        self.chk_system_audio.pack(anchor="w")
        if not AudioRecorder.can_capture_system():
            self.chk_system_audio.configure(state="disabled")
            ctk.CTkLabel(
                sys_audio_row, text="(soundcard 패키지 필요)",
                font=ctk.CTkFont(size=10), text_color=C["text2"],
            ).pack(anchor="w", padx=(24, 0))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=25)
        ctk.CTkButton(
            btn_frame, text="회의 시작", width=140, height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=C["green"], hover_color="#00a884",
            command=self._on_ok,
        ).pack(side="left", padx=10)
        ctk.CTkButton(
            btn_frame, text="건너뛰기", width=140, height=42,
            font=ctk.CTkFont(size=14),
            fg_color=C["border"], hover_color="#636e72",
            command=self._on_skip,
        ).pack(side="left", padx=10)

    def _on_ok(self):
        num_str = self.entries["참석자 수"].get().strip()
        num_speakers = int(num_str) if num_str.isdigit() else 0
        self.result = MeetingMetadata(
            title=self.entries["회의 제목"].get().strip() or "회의",
            date=self.entries["날짜"].get().strip(),
            attendees=self.entries["참석자"].get().strip(),
            meeting_type=self.combo_type.get(),
            location=self.entries["장소"].get().strip(),
            num_speakers=num_speakers,
            capture_system_audio=self.capture_system_var.get(),
        )
        self.destroy()

    def _on_skip(self):
        self.result = MeetingMetadata()
        self.destroy()

    def _on_cancel(self):
        self.result = MeetingMetadata()
        self.destroy()


class MeetingApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AI 회의록 작성기")
        self.geometry("900x720")
        self.minsize(800, 600)

        # 둥근 모서리 적용 (Windows 11)
        try:
            import ctypes
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            preference = ctypes.c_int(2)  # ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(preference), ctypes.sizeof(preference),
            )
        except Exception:
            pass

        self.recorder = AudioRecorder()
        self.all_text = ""
        self.recording = False
        self._paused = False
        self.session_count = 0
        self.metadata = None
        self.summary_mode = "standard"
        self._current_lang = get_language()

        self._record_seconds = 0
        self._timer_id = None
        self._level_id = None

        # 실시간 전사
        self._realtime_id = None
        self._realtime_text = ""
        self._realtime_busy = False
        self._REALTIME_INTERVAL = 5000  # 5초 (#1)
        self._recognizing_anim_id = None
        self._recognizing_idx = 0

        # 편집 모드 (#4)
        self._editing_full = False
        self._editing_summary = False
        self._loaded_meeting_id = None

        self._build_ui()
        self._bind_shortcuts()
        self.after(200, self._show_metadata_dialog)

    def _show_metadata_dialog(self):
        dialog = MetadataDialog(self)
        self.wait_window(dialog)
        self.metadata = dialog.result or MeetingMetadata()
        title = self.metadata.title or "회의"
        self.title(f"AI 회의록 작성기 — {title}")

    def _bind_shortcuts(self):
        """단축키 (#6)."""
        self.bind_all("<Control-r>", lambda e: self._toggle_record())
        self.bind_all("<Control-p>", lambda e: self._toggle_pause())
        self.bind_all("<Control-e>", lambda e: self._export("excel"))
        self.bind_all("<Control-s>", lambda e: self._save_to_db_manual())
        self.bind_all("<Control-q>", lambda e: self._on_quit())

    # ══════════════════════════════════════════════════════════
    # UI 빌드
    # ══════════════════════════════════════════════════════════
    def _build_ui(self):
        # ── 사이드바 ──
        sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=C["surface"])
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        logo_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=16, pady=(20, 10))
        ctk.CTkLabel(logo_frame, text="AI 회의록",
                     font=ctk.CTkFont(family="맑은 고딕", size=22, weight="bold"),
                     text_color="#ffffff").pack(anchor="w")
        ctk.CTkLabel(logo_frame, text="Meeting Minutes Writer",
                     font=ctk.CTkFont(size=11), text_color=C["text2"]).pack(anchor="w")

        ctk.CTkFrame(sidebar, height=1, fg_color=C["border"]).pack(fill="x", padx=16, pady=10)

        # 녹음 버튼 (세련된 원형)
        rec_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        rec_frame.pack(fill="x", padx=16, pady=(10, 0))

        # 외곽 링 (그라데이션 효과)
        self.rec_ring = ctk.CTkFrame(
            rec_frame, width=90, height=90,
            corner_radius=45, fg_color="#0a4d3a",
            border_width=3, border_color=C["green"],
        )
        self.rec_ring.pack(pady=(4, 0))
        self.rec_ring.pack_propagate(False)

        self.btn_record = ctk.CTkButton(
            self.rec_ring, text="", width=70, height=70,
            font=ctk.CTkFont(size=1),
            fg_color=C["green"], hover_color="#00a884", corner_radius=35,
            text_color="#ffffff",
            command=self._toggle_record,
        )
        self.btn_record.place(relx=0.5, rely=0.5, anchor="center")

        # 녹음 아이콘 (Canvas로 원 그리기)
        self.rec_icon = tk.Canvas(
            self.btn_record, width=24, height=24,
            bg=C["green"], highlightthickness=0, bd=0,
        )
        self.rec_icon.place(relx=0.5, rely=0.5, anchor="center")
        self.rec_icon.create_oval(2, 2, 22, 22, fill="#ff4757", outline="#ff6b81", width=2)

        self.lbl_record_text = ctk.CTkLabel(
            rec_frame, text="REC (Ctrl+R)",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"), text_color=C["green"],
        )
        self.lbl_record_text.pack(pady=(4, 0))

        # 일시정지 버튼 (#9) - 녹음 시작 시에만 표시
        self.btn_pause = ctk.CTkButton(
            sidebar, text="  일시정지  (Ctrl+P)", width=188, height=36,
            font=ctk.CTkFont(family="맑은 고딕", size=12),
            fg_color=C["orange"], hover_color="#e17055", corner_radius=8,
            command=self._toggle_pause,
        )

        # 타이머
        self.lbl_timer = ctk.CTkLabel(
            sidebar, text="00:00",
            font=ctk.CTkFont(family="Consolas", size=28, weight="bold"),
            text_color=C["text2"],
        )
        self.lbl_timer.pack(pady=(2, 6))

        # 레벨 미터
        self.level_canvas = tk.Canvas(sidebar, height=6, bg=C["surface"], highlightthickness=0, bd=0)
        self.level_canvas.pack(fill="x", padx=20, pady=(0, 12))
        self.level_bar = self.level_canvas.create_rectangle(0, 0, 0, 6, fill=C["green"])

        ctk.CTkFrame(sidebar, height=1, fg_color=C["border"]).pack(fill="x", padx=16, pady=6)

        # 요약 형식
        ctk.CTkLabel(sidebar, text="요약 형식",
                     font=ctk.CTkFont(size=12, weight="bold"), text_color=C["text2"]).pack(padx=16, anchor="w", pady=(8, 4))
        self.combo_summary = ctk.CTkComboBox(
            sidebar, values=["표준 요약", "간단 요약", "액션 아이템"],
            width=188, height=34, state="readonly", font=ctk.CTkFont(size=12),
            command=self._on_summary_mode_change,
        )
        self.combo_summary.pack(padx=16)
        self.combo_summary.set("표준 요약")

        # 내보내기
        ctk.CTkFrame(sidebar, height=1, fg_color=C["border"]).pack(fill="x", padx=16, pady=10)
        ctk.CTkLabel(sidebar, text="내보내기",
                     font=ctk.CTkFont(size=12, weight="bold"), text_color=C["text2"]).pack(padx=16, anchor="w", pady=(0, 4))

        self.combo_export_scope = ctk.CTkComboBox(
            sidebar, values=["전체 (요약+기록)", "요약만", "전체 기록만"],
            width=188, height=30, state="readonly", font=ctk.CTkFont(size=11),
        )
        self.combo_export_scope.pack(padx=16, pady=(0, 6))
        self.combo_export_scope.set("전체 (요약+기록)")

        export_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        export_frame.pack(fill="x", padx=16)
        for label, fmt, color in [("Excel", "excel", "#27ae60"), ("Word", "word", "#2980b9"),
                                   ("PDF", "pdf", "#8e44ad")]:
            ctk.CTkButton(
                export_frame, text=label, width=58, height=32,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color=color, hover_color=C["border"], corner_radius=8,
                command=lambda f=fmt: self._export(f),
            ).pack(side="left", padx=2, expand=True)

        # 언어 선택 (#8)
        ctk.CTkFrame(sidebar, height=1, fg_color=C["border"]).pack(fill="x", padx=16, pady=10)
        ctk.CTkLabel(sidebar, text="언어 / Language",
                     font=ctk.CTkFont(size=12, weight="bold"), text_color=C["text2"]).pack(padx=16, anchor="w", pady=(0, 4))
        self.combo_lang = ctk.CTkComboBox(
            sidebar, values=["한국어", "English", "日本語"],
            width=188, height=30, state="readonly", font=ctk.CTkFont(size=11),
            command=self._on_lang_change,
        )
        self.combo_lang.pack(padx=16)
        self.combo_lang.set(LANG_DISPLAY.get(self._current_lang, "한국어"))

        # 저장폴더
        ctk.CTkFrame(sidebar, height=1, fg_color=C["border"]).pack(fill="x", padx=16, pady=10)
        ctk.CTkLabel(sidebar, text="저장 폴더",
                     font=ctk.CTkFont(size=12, weight="bold"), text_color=C["text2"]).pack(padx=16, anchor="w", pady=(0, 4))
        self.lbl_save_folder = ctk.CTkLabel(
            sidebar, text=self._short_path(get_save_folder()),
            font=ctk.CTkFont(size=10), text_color=C["text2"], wraplength=180, anchor="w",
        )
        self.lbl_save_folder.pack(padx=16, anchor="w")
        ctk.CTkButton(
            sidebar, text="폴더 변경", width=188, height=30,
            font=ctk.CTkFont(size=11), fg_color=C["border"], hover_color="#636e72", corner_radius=8,
            command=self._change_save_folder,
        ).pack(padx=16, pady=(4, 6))

        # 종료
        ctk.CTkFrame(sidebar, fg_color="transparent").pack(fill="both", expand=True)
        ctk.CTkButton(
            sidebar, text="종료  (Ctrl+Q)", width=188, height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=C["red"], hover_color="#c0392b", corner_radius=10,
            command=self._on_quit,
        ).pack(padx=16, pady=(0, 20))

        # ── 메인 영역 ──
        main_area = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        main_area.pack(side="right", fill="both", expand=True)

        self.status_var = tk.StringVar(value="준비 완료  —  녹음 버튼을 눌러 시작하세요")
        ctk.CTkLabel(
            main_area, textvariable=self.status_var,
            font=ctk.CTkFont(size=12), text_color=C["text2"], anchor="w", height=32,
        ).pack(fill="x", padx=16, pady=(12, 4))

        self.tabview = ctk.CTkTabview(
            main_area, fg_color=C["surface"],
            segmented_button_fg_color=C["card"],
            segmented_button_selected_color=C["accent"],
            segmented_button_unselected_color=C["card"], corner_radius=12,
        )
        self.tabview.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        tab_full = self.tabview.add("전체 기록")
        tab_summary = self.tabview.add("요약")
        tab_files = self.tabview.add("파일 목록")
        tab_history = self.tabview.add("히스토리")

        # 전체 기록 탭 (#3 하이라이트 + #4 편집)
        full_toolbar = ctk.CTkFrame(tab_full, fg_color="transparent", height=32)
        full_toolbar.pack(fill="x", padx=4, pady=(4, 0))
        self.btn_edit_full = ctk.CTkButton(
            full_toolbar, text="편집", width=60, height=28,
            font=ctk.CTkFont(size=11), fg_color=C["card"], hover_color=C["accent2"],
            command=self._toggle_edit_full,
        )
        self.btn_edit_full.pack(side="right", padx=4)

        self.txt_full = scrolledtext.ScrolledText(
            tab_full, wrap=tk.WORD, font=("Consolas", 11),
            bg="#0d1117", fg="#c9d1d9", insertbackground="#c9d1d9",
            selectbackground=C["accent"], relief="flat", bd=0, padx=12, pady=10,
            state=tk.DISABLED,
        )
        self.txt_full.pack(fill="both", expand=True, padx=4, pady=4)
        for tag, color in HIGHLIGHT_COLORS.items():
            self.txt_full.tag_configure(tag, foreground=color, font=("Consolas", 11, "bold"))

        # 요약 탭 (#4 편집)
        summary_toolbar = ctk.CTkFrame(tab_summary, fg_color="transparent", height=32)
        summary_toolbar.pack(fill="x", padx=4, pady=(4, 0))
        self.btn_edit_summary = ctk.CTkButton(
            summary_toolbar, text="편집", width=60, height=28,
            font=ctk.CTkFont(size=11), fg_color=C["card"], hover_color=C["accent2"],
            command=self._toggle_edit_summary,
        )
        self.btn_edit_summary.pack(side="right", padx=4)

        self.txt_summary = scrolledtext.ScrolledText(
            tab_summary, wrap=tk.WORD, font=("맑은 고딕", 11),
            bg="#0d1117", fg="#c9d1d9", insertbackground="#c9d1d9",
            selectbackground=C["accent"], relief="flat", bd=0, padx=12, pady=10,
            state=tk.DISABLED,
        )
        self.txt_summary.pack(fill="both", expand=True, padx=4, pady=4)

        # 파일 목록 탭
        files_top = ctk.CTkFrame(tab_files, fg_color="transparent")
        files_top.pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkButton(files_top, text="새로고침", width=90, height=30, font=ctk.CTkFont(size=11),
                      fg_color=C["card"], hover_color=C["accent2"],
                      command=self._refresh_file_list).pack(side="left", padx=4)
        ctk.CTkButton(files_top, text="폴더 열기", width=90, height=30, font=ctk.CTkFont(size=11),
                      fg_color=C["card"], hover_color=C["accent2"],
                      command=self._open_save_folder).pack(side="left", padx=4)

        self._setup_treeview_style()
        columns = ("filename", "type", "size", "date")
        self.tree_files = tk.ttk.Treeview(tab_files, columns=columns, show="headings", height=12, style="Dark.Treeview")
        self.tree_files.heading("filename", text="파일명")
        self.tree_files.heading("type", text="형식")
        self.tree_files.heading("size", text="크기")
        self.tree_files.heading("date", text="수정일")
        self.tree_files.column("filename", width=280)
        self.tree_files.column("type", width=60, anchor="center")
        self.tree_files.column("size", width=80, anchor="center")
        self.tree_files.column("date", width=140, anchor="center")
        file_scroll = tk.ttk.Scrollbar(tab_files, orient="vertical", command=self.tree_files.yview)
        self.tree_files.configure(yscrollcommand=file_scroll.set)
        self.tree_files.pack(fill="both", expand=True, padx=8, pady=(0, 8), side="left")
        file_scroll.pack(fill="y", side="right", pady=(0, 8))
        self.tree_files.bind("<Delete>", lambda e: self._delete_selected_file())

        # 히스토리 탭 (#7 통계)
        hist_top = ctk.CTkFrame(tab_history, fg_color="transparent")
        hist_top.pack(fill="x", padx=8, pady=(8, 4))
        self.entry_search = ctk.CTkEntry(hist_top, placeholder_text="검색어 입력...",
                                          width=200, height=32, font=ctk.CTkFont(size=12))
        self.entry_search.pack(side="left", padx=4)
        ctk.CTkButton(hist_top, text="검색", width=60, height=32, font=ctk.CTkFont(size=11),
                      fg_color=C["card"], hover_color=C["accent2"],
                      command=self._search_history).pack(side="left", padx=4)
        ctk.CTkButton(hist_top, text="전체", width=60, height=32, font=ctk.CTkFont(size=11),
                      fg_color=C["card"], hover_color=C["accent2"],
                      command=self._load_history).pack(side="left", padx=4)
        ctk.CTkButton(hist_top, text="통계", width=60, height=32,
                      font=ctk.CTkFont(size=11, weight="bold"),
                      fg_color=C["accent2"], hover_color="#6c5ce7",
                      command=self._show_stats).pack(side="left", padx=4)
        ctk.CTkButton(hist_top, text="불러오기", width=80, height=32,
                      font=ctk.CTkFont(size=11, weight="bold"),
                      fg_color=C["accent"], hover_color="#c0392b",
                      command=self._load_selected_meeting).pack(side="right", padx=4)

        hist_columns = ("id", "title", "date", "type")
        self.tree_history = tk.ttk.Treeview(tab_history, columns=hist_columns, show="headings", height=10, style="Dark.Treeview")
        self.tree_history.heading("id", text="ID")
        self.tree_history.heading("title", text="제목")
        self.tree_history.heading("date", text="날짜")
        self.tree_history.heading("type", text="유형")
        self.tree_history.column("id", width=40, anchor="center")
        self.tree_history.column("title", width=240)
        self.tree_history.column("date", width=100, anchor="center")
        self.tree_history.column("type", width=100, anchor="center")
        hist_scroll = tk.ttk.Scrollbar(tab_history, orient="vertical", command=self.tree_history.yview)
        self.tree_history.configure(yscrollcommand=hist_scroll.set)
        self.tree_history.pack(fill="both", expand=True, padx=8, pady=(0, 8), side="left")
        hist_scroll.pack(fill="y", side="right", pady=(0, 8))

        self.after(500, self._load_history)
        self.after(600, self._refresh_file_list)

    def _setup_treeview_style(self):
        style = tk.ttk.Style()
        style.theme_use("default")
        style.configure("Dark.Treeview", background="#0d1117", foreground="#c9d1d9",
                        fieldbackground="#0d1117", borderwidth=0, font=("맑은 고딕", 10), rowheight=28)
        style.configure("Dark.Treeview.Heading", background=C["card"], foreground="#ffffff",
                        font=("맑은 고딕", 10, "bold"), borderwidth=0)
        style.map("Dark.Treeview", background=[("selected", C["accent"])], foreground=[("selected", "#ffffff")])
        style.map("Dark.Treeview.Heading", background=[("active", C["accent2"])])

    @staticmethod
    def _short_path(path, max_len=30):
        if len(path) <= max_len:
            return path
        return "..." + path[-(max_len - 3):]

    # ══════════════════════════════════════════════════════════
    # 편집 모드 (#4)
    # ══════════════════════════════════════════════════════════
    def _toggle_edit_full(self):
        if not self._editing_full:
            self._editing_full = True
            self.txt_full.config(state=tk.NORMAL)
            self.btn_edit_full.configure(text="저장", fg_color=C["green"])
        else:
            self._editing_full = False
            self.all_text = self.txt_full.get("1.0", tk.END).strip()
            self.txt_full.config(state=tk.DISABLED)
            self.btn_edit_full.configure(text="편집", fg_color=C["card"])
            self._apply_highlights()
            if self._loaded_meeting_id:
                from storage import update_meeting
                update_meeting(self._loaded_meeting_id, full_text=self.all_text)

    def _toggle_edit_summary(self):
        if not self._editing_summary:
            self._editing_summary = True
            self.txt_summary.config(state=tk.NORMAL)
            self.btn_edit_summary.configure(text="저장", fg_color=C["green"])
        else:
            self._editing_summary = False
            summary = self.txt_summary.get("1.0", tk.END).strip()
            self.txt_summary.config(state=tk.DISABLED)
            self.btn_edit_summary.configure(text="편집", fg_color=C["card"])
            if self._loaded_meeting_id:
                from storage import update_meeting
                update_meeting(self._loaded_meeting_id, summary=summary)

    # ══════════════════════════════════════════════════════════
    # 키워드 하이라이트 (#3)
    # ══════════════════════════════════════════════════════════
    def _apply_highlights(self):
        was_disabled = str(self.txt_full.cget("state")) == "disabled"
        if was_disabled:
            self.txt_full.config(state=tk.NORMAL)
        for tag in HIGHLIGHT_KEYWORDS:
            self.txt_full.tag_remove(tag, "1.0", tk.END)
        for tag, words in HIGHLIGHT_KEYWORDS.items():
            for word in words:
                start = "1.0"
                while True:
                    pos = self.txt_full.search(word, start, tk.END, nocase=True)
                    if not pos:
                        break
                    end = f"{pos}+{len(word)}c"
                    self.txt_full.tag_add(tag, pos, end)
                    start = end
        if was_disabled:
            self.txt_full.config(state=tk.DISABLED)

    # ══════════════════════════════════════════════════════════
    # 언어 변경 (#8)
    # ══════════════════════════════════════════════════════════
    def _on_lang_change(self, choice=None):
        lang = LANG_MAP.get(self.combo_lang.get(), "ko")
        self._current_lang = lang
        set_language(lang)

    def _show_stats(self):
        StatsDialog(self)

    # ══════════════════════════════════════════════════════════
    # 저장폴더 / 파일 목록
    # ══════════════════════════════════════════════════════════
    def _change_save_folder(self):
        folder = filedialog.askdirectory(title="저장 폴더 선택", initialdir=get_save_folder())
        if folder:
            set_save_folder(folder)
            self.lbl_save_folder.configure(text=self._short_path(folder))
            self.status_var.set(f"저장 폴더 변경: {folder}")
            self._refresh_file_list()

    def _open_save_folder(self):
        os.startfile(get_save_folder())

    def _refresh_file_list(self):
        for item in self.tree_files.get_children():
            self.tree_files.delete(item)
        folder = get_save_folder()
        patterns = ["*.xlsx", "*.docx", "*.pdf", "*.txt", "*.wav", "*.md"]
        files = []
        for pat in patterns:
            files.extend(glob.glob(os.path.join(folder, pat)))
        files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
        for fpath in files:
            name = os.path.basename(fpath)
            ext = os.path.splitext(name)[1].upper().replace(".", "")
            size_bytes = os.path.getsize(fpath)
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            else:
                size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M")
            self.tree_files.insert("", tk.END, values=(name, ext, size_str, mtime))

    def _delete_selected_file(self):
        """파일 목록에서 선택된 파일 삭제 (Delete 키)."""
        sel = self.tree_files.selection()
        if not sel:
            return
        filename = self.tree_files.item(sel[0])["values"][0]
        folder = get_save_folder()
        filepath = os.path.join(folder, filename)
        if not os.path.exists(filepath):
            return
        confirm = messagebox.askyesno("파일 삭제", f"정말 삭제할까요?\n\n{filename}")
        if confirm:
            try:
                os.remove(filepath)
                self._refresh_file_list()
                show_toast(self, f"삭제됨: {filename}", toast_type="info")
            except Exception as e:
                messagebox.showerror("오류", f"삭제 실패: {e}")

    def _on_summary_mode_change(self, choice=None):
        mode_map = {"표준 요약": "standard", "간단 요약": "brief", "액션 아이템": "action"}
        self.summary_mode = mode_map.get(self.combo_summary.get(), "standard")

    # ══════════════════════════════════════════════════════════
    # 타이머 / 레벨 미터
    # ══════════════════════════════════════════════════════════
    def _start_timer(self):
        self._record_seconds = 0
        self.lbl_timer.configure(text_color=C["red"])
        self._tick_timer()

    def _tick_timer(self):
        if self._paused:
            self._timer_id = self.after(1000, self._tick_timer)
            return
        mins, secs = divmod(self._record_seconds, 60)
        self.lbl_timer.configure(text=f"{mins:02d}:{secs:02d}")
        self._record_seconds += 1
        self._timer_id = self.after(1000, self._tick_timer)

    def _stop_timer(self):
        if self._timer_id:
            self.after_cancel(self._timer_id)
            self._timer_id = None
        self.lbl_timer.configure(text_color=C["text2"])

    def _start_level_meter(self):
        self._update_level()

    def _update_level(self):
        if self.recording and self.recorder.frames and not self._paused:
            try:
                last_frame = self.recorder.frames[-1]
                rms = float(np.sqrt(np.mean(last_frame ** 2)))
                level = min(int(rms * 5000), 100)
            except Exception:
                level = 0
            canvas_w = self.level_canvas.winfo_width()
            bar_w = int(canvas_w * level / 100)
            color = C["green"] if level < 60 else C["orange"] if level < 85 else C["red"]
            self.level_canvas.coords(self.level_bar, 0, 0, bar_w, 6)
            self.level_canvas.itemconfig(self.level_bar, fill=color)
        else:
            self.level_canvas.coords(self.level_bar, 0, 0, 0, 6)
        self._level_id = self.after(100, self._update_level)

    def _stop_level_meter(self):
        if self._level_id:
            self.after_cancel(self._level_id)
            self._level_id = None
        self.level_canvas.coords(self.level_bar, 0, 0, 0, 6)

    # ══════════════════════════════════════════════════════════
    # "인식 중..." 애니메이션 (#1)
    # ══════════════════════════════════════════════════════════
    def _start_recognizing_anim(self):
        self._recognizing_idx = 0
        self._animate_recognizing()

    def _animate_recognizing(self):
        dots = ["인식 중", "인식 중.", "인식 중..", "인식 중..."]
        if self._realtime_busy:
            self.status_var.set(f"녹음 중...  {dots[self._recognizing_idx % 4]}")
            self._recognizing_idx += 1
            self._recognizing_anim_id = self.after(400, self._animate_recognizing)
        else:
            self._stop_recognizing_anim()

    def _stop_recognizing_anim(self):
        if self._recognizing_anim_id:
            self.after_cancel(self._recognizing_anim_id)
            self._recognizing_anim_id = None
        if self.recording:
            self.status_var.set(f"녹음 중...  (세션 {self.session_count})")

    # ══════════════════════════════════════════════════════════
    # 실시간 전사 (#1: 5초 간격 + 애니메이션)
    # ══════════════════════════════════════════════════════════
    def _start_realtime_transcription(self):
        self._realtime_text = ""
        self._realtime_busy = False
        folder = get_save_folder()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        title = (self.metadata.title if self.metadata else "회의록").replace(" ", "_")
        self._autosave_path = os.path.join(folder, f"{title}_{timestamp}_실시간.txt")
        with open(self._autosave_path, "w", encoding="utf-8") as f:
            f.write(f"[실시간 기록] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"회의: {self.metadata.title if self.metadata else '회의'}\n")
            f.write("=" * 40 + "\n\n")
        self._realtime_tick()

    def _realtime_tick(self):
        if not self.recording:
            return
        if self._paused:
            self._realtime_id = self.after(self._REALTIME_INTERVAL, self._realtime_tick)
            return
        if not self._realtime_busy:
            snapshot_path = self.recorder.snapshot()
            if snapshot_path:
                self._realtime_busy = True
                self._start_recognizing_anim()
                threading.Thread(target=self._realtime_worker, args=(snapshot_path,), daemon=True).start()
        self._realtime_id = self.after(self._REALTIME_INTERVAL, self._realtime_tick)

    def _realtime_worker(self, audio_path):
        try:
            text = transcribe_realtime(audio_path, lang=self._current_lang)
            if text and text.strip():
                new_text = text.strip() + "\n"
                self._realtime_text += new_text
                self._autosave_append(new_text)
                self.after(0, self._update_realtime_ui)
        except Exception:
            pass
        finally:
            self._realtime_busy = False
            self.after(0, self._stop_recognizing_anim)
            try:
                os.remove(audio_path)
            except OSError:
                pass

    def _autosave_append(self, text):
        try:
            with open(self._autosave_path, "a", encoding="utf-8") as f:
                f.write(text)
        except Exception:
            pass

    def _update_realtime_ui(self):
        display = self.all_text
        if self._realtime_text:
            display += f"\n[세션 {self.session_count} - 실시간]\n{self._realtime_text}"
        self.txt_full.config(state=tk.NORMAL)
        self.txt_full.delete("1.0", tk.END)
        self.txt_full.insert("1.0", display)
        self.txt_full.config(state=tk.DISABLED)
        self.txt_full.see(tk.END)
        self._apply_highlights()
        if self.recording:
            self.status_var.set(f"녹음 중...  (세션 {self.session_count})")

    def _stop_realtime_transcription(self):
        if self._realtime_id:
            self.after_cancel(self._realtime_id)
            self._realtime_id = None
        self._stop_recognizing_anim()

    # ══════════════════════════════════════════════════════════
    # 일시정지 (#9)
    # ══════════════════════════════════════════════════════════
    def _toggle_pause(self):
        if not self.recording:
            return
        if not self._paused:
            self._paused = True
            self.recorder.pause()
            self.btn_pause.configure(text="  계속  (Ctrl+P)", fg_color=C["green"], hover_color="#00a884")
            self.status_var.set("일시정지 중...")
            self.lbl_timer.configure(text_color=C["orange"])
        else:
            self._paused = False
            self.recorder.resume()
            self.btn_pause.configure(text="  일시정지  (Ctrl+P)", fg_color=C["orange"], hover_color="#e17055")
            self.status_var.set(f"녹음 중...  (세션 {self.session_count})")
            self.lbl_timer.configure(text_color=C["red"])

    # ══════════════════════════════════════════════════════════
    # 녹음 토글
    # ══════════════════════════════════════════════════════════
    def _toggle_record(self):
        if not self.recording:
            self.status_var.set("마이크 확인 중...")
            self.btn_record.configure(state="disabled")
            self.update_idletasks()

            ok, msg = AudioRecorder.check_microphone()
            if not ok:
                self.btn_record.configure(state="normal")
                result = messagebox.askyesnocancel(
                    "마이크 오류",
                    f"{msg}\n\nWindows 마이크 설정을 열까요?\n\n예 = 마이크 권한 설정\n아니오 = 사운드 장치 설정",
                )
                if result is True:
                    AudioRecorder.open_microphone_settings()
                elif result is False:
                    AudioRecorder.open_sound_settings()
                self.status_var.set("마이크를 활성화한 후 다시 시도하세요")
                return

            self.recording = True
            self._paused = False
            self.session_count += 1
            self.all_text = ""
            self._realtime_text = ""
            capture_sys = self.metadata.capture_system_audio if self.metadata else False
            self.recorder.start(capture_system=capture_sys)

            self.btn_record.configure(fg_color=C["red"], hover_color="#c0392b", state="normal")
            self.rec_ring.configure(fg_color="#4d0a0a", border_color=C["red"])
            self.rec_icon.configure(bg=C["red"])
            self.rec_icon.delete("all")
            self.rec_icon.create_rectangle(4, 4, 20, 20, fill="#ffffff", outline="#ffffff", width=0)
            self.lbl_record_text.configure(text="STOP", text_color=C["red"])
            self.btn_pause.pack(padx=16, pady=(0, 4), after=self.btn_record)

            self.status_var.set(f"녹음 중...  (세션 {self.session_count})  [{msg}]")
            self._start_timer()
            self._start_level_meter()
            self._start_realtime_transcription()
        else:
            self.recording = False
            self._paused = False
            audio_path = self.recorder.stop()
            self._stop_timer()
            self._stop_level_meter()
            self._stop_realtime_transcription()
            self.btn_pause.pack_forget()

            self.btn_record.configure(fg_color=C["green"], hover_color="#00a884", state="disabled")
            self.rec_ring.configure(fg_color="#0a4d3a", border_color=C["green"])
            self.rec_icon.configure(bg=C["green"])
            self.rec_icon.delete("all")
            self.rec_icon.create_oval(2, 2, 22, 22, fill="#ff4757", outline="#ff6b81", width=2)
            self.lbl_record_text.configure(text="REC (Ctrl+R)", text_color=C["green"])
            self.status_var.set("최종 전사 + 요약 생성 중...  잠시 기다려 주세요")

            if audio_path:
                threading.Thread(target=self._transcribe_worker, args=(audio_path,), daemon=True).start()
            else:
                self.status_var.set("녹음된 내용이 없습니다")
                self.btn_record.configure(state="normal")

    def _transcribe_worker(self, audio_path):
        try:
            num_speakers = self.metadata.num_speakers if self.metadata else 0
            text = transcribe(audio_path, lang=self._current_lang, num_speakers=num_speakers)
            self.all_text = text

            template_prefix = ""
            if self.metadata:
                template_prefix = get_template_prefix(self.metadata.meeting_type, lang=self._current_lang)

            full_for_summary = template_prefix + self.all_text if template_prefix else self.all_text
            summary = summarize(full_for_summary, mode=self.summary_mode, lang=self._current_lang)

            # 자동 제목 생성 (#10)
            if self.metadata and (not self.metadata.title or self.metadata.title == "회의"):
                try:
                    auto_title = generate_title(self.all_text, lang=self._current_lang)
                    if auto_title:
                        self.metadata.title = auto_title
                        self.after(0, lambda: self.title(f"AI 회의록 작성기 — {auto_title}"))
                except Exception:
                    pass

            # 오디오 파일을 저장폴더에 보존
            try:
                folder = get_save_folder()
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                title = (self.metadata.title if self.metadata else "회의록").replace(" ", "_")
                wav_save_path = os.path.join(folder, f"{title}_{timestamp}.wav")
                shutil.copy2(audio_path, wav_save_path)
            except Exception:
                pass

            self._autosave_final(text, summary)
            self.after(0, self._update_ui, self.all_text, summary)
        except Exception as e:
            self.after(0, self._on_error, str(e))

    def _autosave_final(self, final_text, summary):
        try:
            with open(self._autosave_path, "w", encoding="utf-8") as f:
                f.write(f"[최종 기록] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                title = self.metadata.title if self.metadata else "회의록"
                f.write(f"회의: {title}\n")
                if self.metadata and self.metadata.attendees:
                    f.write(f"참석자: {self.metadata.attendees}\n")
                f.write("=" * 40 + "\n\n")
                f.write(summary)
                f.write("\n\n" + "-" * 40 + "\n[전체 기록]\n" + "-" * 40 + "\n")
                f.write(self.all_text)
        except Exception:
            pass

    def _on_error(self, msg):
        self.status_var.set(f"오류: {msg}")
        self.btn_record.configure(state="normal")

    def _update_ui(self, full_text, summary):
        self.txt_full.config(state=tk.NORMAL)
        self.txt_full.delete("1.0", tk.END)
        self.txt_full.insert("1.0", full_text)
        self.txt_full.config(state=tk.DISABLED)
        self.txt_full.see(tk.END)
        self._apply_highlights()

        self.txt_summary.config(state=tk.NORMAL)
        self.txt_summary.delete("1.0", tk.END)
        self.txt_summary.insert("1.0", summary)
        self.txt_summary.config(state=tk.DISABLED)

        self.status_var.set("대기 중  —  녹음 버튼을 눌러 계속하세요")
        self.btn_record.configure(state="normal")

    # ══════════════════════════════════════════════════════════
    # 내보내기 (#12 마크다운)
    # ══════════════════════════════════════════════════════════
    def _export(self, fmt):
        if not self.all_text.strip():
            messagebox.showwarning("알림", "저장할 내용이 없습니다.")
            return

        fmt_name = {"excel": "Excel", "word": "Word", "pdf": "PDF"}.get(fmt, fmt)
        if not messagebox.askyesno("저장 확인", f"{fmt_name} 파일로 저장할까요?"):
            return

        scope = self.combo_export_scope.get()
        scope_map = {"전체 (요약+기록)": "full", "요약만": "summary_only", "전체 기록만": "transcript_only"}
        export_scope = scope_map.get(scope, "full")
        try:
            from exporter import save_excel, save_word, save_pdf
            summary = self.txt_summary.get("1.0", tk.END).strip() or "(요약 없음)"
            meta = self.metadata or MeetingMetadata()
            if fmt == "excel":
                path = save_excel(self.all_text, summary, meta, scope=export_scope)
            elif fmt == "word":
                path = save_word(self.all_text, summary, meta, scope=export_scope)
            else:
                path = save_pdf(self.all_text, summary, meta, scope=export_scope)
            self.status_var.set(f"저장 완료: {os.path.basename(path)}")
            messagebox.showinfo("저장 완료", f"저장됨:\n{path}")
            self._refresh_file_list()
        except ImportError as e:
            messagebox.showerror("오류", f"라이브러리 설치 필요:\n{e}\n\ninstall.bat을 다시 실행하세요.")
        except Exception as e:
            messagebox.showerror("오류", str(e))

    # ══════════════════════════════════════════════════════════
    # 히스토리
    # ══════════════════════════════════════════════════════════
    def _load_history(self):
        from storage import list_meetings
        self._populate_history(list_meetings())

    def _search_history(self):
        query = self.entry_search.get().strip()
        if not query:
            self._load_history()
            return
        from storage import search_meetings
        self._populate_history(search_meetings(query))

    def _populate_history(self, meetings):
        for item in self.tree_history.get_children():
            self.tree_history.delete(item)
        for m in meetings:
            self.tree_history.insert("", tk.END, values=(m["id"], m["title"], m["date"], m["meeting_type"]))

    def _load_selected_meeting(self):
        sel = self.tree_history.selection()
        if not sel:
            messagebox.showinfo("알림", "회의를 선택해 주세요.")
            return
        meeting_id = self.tree_history.item(sel[0])["values"][0]
        from storage import get_meeting
        m = get_meeting(meeting_id)
        if not m:
            messagebox.showerror("오류", "회의를 찾을 수 없습니다.")
            return

        self._loaded_meeting_id = meeting_id
        self.txt_full.config(state=tk.NORMAL)
        self.txt_full.delete("1.0", tk.END)
        self.txt_full.insert("1.0", m["full_text"])
        self.txt_full.config(state=tk.DISABLED)
        self._apply_highlights()

        self.txt_summary.config(state=tk.NORMAL)
        self.txt_summary.delete("1.0", tk.END)
        self.txt_summary.insert("1.0", m["summary"])
        self.txt_summary.config(state=tk.DISABLED)

        self.all_text = m["full_text"]
        self.tabview.set("전체 기록")
        self.status_var.set(f"불러옴: {m['title']} ({m['date']})")

    # ══════════════════════════════════════════════════════════
    # DB 저장
    # ══════════════════════════════════════════════════════════
    def _save_to_db_manual(self):
        if not self.all_text.strip():
            return
        self._save_to_db()

    def _save_to_db(self):
        if not self.all_text.strip():
            return
        try:
            from storage import save_meeting
            summary = self.txt_summary.get("1.0", tk.END).strip() or "(요약 없음)"
            meta = self.metadata or MeetingMetadata()
            save_meeting(
                title=meta.title, date=meta.date, attendees=meta.attendees,
                meeting_type=meta.meeting_type, location=meta.location,
                full_text=self.all_text, summary=summary,
            )
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════
    # 종료
    # ══════════════════════════════════════════════════════════
    def _on_quit(self):
        if self.recording:
            self.recording = False
            self._paused = False
            self._stop_timer()
            self._stop_level_meter()
            self._stop_realtime_transcription()
            self.recorder.stop()
        if self.all_text.strip():
            self._save_to_db()
            save = messagebox.askyesno("저장 확인", "회의록을 텍스트 파일로도 저장할까요?")
            if save:
                self._save_to_file()
        self.recorder.cleanup()
        self.destroy()

    def _save_to_file(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        title = (self.metadata.title if self.metadata else "회의록").replace(" ", "_")
        folder = get_save_folder()
        filename = os.path.join(folder, f"{title}_{timestamp}.txt")
        summary = summarize(self.all_text, mode=self.summary_mode, lang=self._current_lang)
        with open(filename, "w", encoding="utf-8") as f:
            f.write("=" * 50 + "\n")
            f.write(f"          {self.metadata.title if self.metadata else '회의록'}\n")
            f.write(f"    {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            if self.metadata and self.metadata.attendees:
                f.write(f"    참석자: {self.metadata.attendees}\n")
            f.write("=" * 50 + "\n\n")
            f.write(summary)
            f.write("\n\n" + "-" * 50 + "\n[ 전체 기록 ]\n" + "-" * 50 + "\n")
            f.write(self.all_text)
        self.status_var.set(f"저장됨: {filename}")


if __name__ == "__main__":
    app = MeetingApp()
    app.mainloop()
