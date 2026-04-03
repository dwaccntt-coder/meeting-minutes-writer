"""토스트 알림 모듈 — 화면 우측 하단 팝업."""

import customtkinter as ctk

_active_toasts = []

# 타입별 색상
_COLORS = {
    "info": "#0f3460",
    "success": "#00b894",
    "warning": "#fdcb6e",
    "error": "#d63031",
}


def show_toast(parent, message, duration_ms=3000, toast_type="info"):
    """우측 하단에 토스트 알림을 표시한다."""
    toast = ctk.CTkToplevel(parent)
    toast.overrideredirect(True)
    toast.attributes("-topmost", True)
    toast.configure(fg_color="#1a1a2e")

    color = _COLORS.get(toast_type, _COLORS["info"])

    # 좌측 색상 바 + 메시지
    frame = ctk.CTkFrame(toast, fg_color="#16213e", corner_radius=10, border_width=2, border_color=color)
    frame.pack(fill="both", expand=True, padx=2, pady=2)

    bar = ctk.CTkFrame(frame, width=4, fg_color=color, corner_radius=2)
    bar.pack(side="left", fill="y", padx=(6, 0), pady=6)

    lbl = ctk.CTkLabel(
        frame, text=message,
        font=ctk.CTkFont(family="맑은 고딕", size=11),
        text_color="#dfe6e9", wraplength=220, anchor="w", justify="left",
    )
    lbl.pack(side="left", fill="both", expand=True, padx=(6, 10), pady=6)

    # 위치 계산 (우측 하단, 활성 토스트 위로 쌓기)
    toast.update_idletasks()
    w = 260
    h = max(toast.winfo_reqheight(), 40)
    screen_w = parent.winfo_screenwidth()
    screen_h = parent.winfo_screenheight()

    offset_y = sum(t.winfo_height() + 8 for t in _active_toasts if t.winfo_exists())
    x = screen_w - w - 20
    y = screen_h - h - 60 - offset_y

    toast.geometry(f"{w}x{h}+{x}+{y}")

    _active_toasts.append(toast)

    def _fade_out(alpha=1.0):
        if not toast.winfo_exists():
            return
        alpha -= 0.1
        if alpha <= 0:
            if toast in _active_toasts:
                _active_toasts.remove(toast)
            toast.destroy()
            return
        toast.attributes("-alpha", alpha)
        toast.after(30, lambda: _fade_out(alpha))

    toast.after(duration_ms, _fade_out)
