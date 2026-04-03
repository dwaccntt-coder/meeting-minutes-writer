import tempfile
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf

# 시스템 오디오 캡처용 (선택적 의존성)
try:
    import soundcard as sc
    HAS_SOUNDCARD = True
except ImportError:
    HAS_SOUNDCARD = False


# ── 오디오 전처리 함수 ───────────────────────────────────────────
def normalize_audio(audio, target_db=-3.0):
    """오디오를 target_db 수준으로 자동 증폭 (Normalize).
    작은 소리도 적절한 볼륨으로 키워줌."""
    if len(audio) == 0:
        return audio

    peak = np.max(np.abs(audio))
    if peak < 1e-6:  # 완전 무음
        return audio

    target_amplitude = 10 ** (target_db / 20.0)
    gain = target_amplitude / peak
    # 과도한 증폭 방지 (최대 30배)
    gain = min(gain, 30.0)
    return (audio * gain).astype(audio.dtype)


def noise_gate(audio, threshold_db=-55.0, samplerate=16000, frame_ms=30):
    """노이즈 게이트: threshold_db 이하 구간을 무음 처리.
    말소리 구간만 살리고 배경 소음 제거."""
    if len(audio) == 0:
        return audio

    frame_size = int(samplerate * frame_ms / 1000)
    threshold = 10 ** (threshold_db / 20.0)
    result = audio.copy()

    for i in range(0, len(audio), frame_size):
        frame = audio[i:i + frame_size]
        rms = np.sqrt(np.mean(frame ** 2))
        if rms < threshold:
            result[i:i + frame_size] = 0.0

    return result


def has_speech(audio, threshold_db=-60.0):
    """오디오에 말소리가 있는지 간단 판별 (무음 스냅샷 방지).
    -60dB = 매우 민감 (아주 작은 소리도 감지)."""
    if len(audio) == 0:
        return False
    rms = np.sqrt(np.mean(audio ** 2))
    threshold = 10 ** (threshold_db / 20.0)
    return rms > threshold


def process_audio(audio, samplerate=16000):
    """전처리 파이프라인: 노이즈 게이트 → 노멀라이즈.
    순서: 먼저 증폭해서 작은 소리를 키운 뒤, 노이즈 게이트로 무음 구간 제거."""
    amplified = normalize_audio(audio, target_db=-3.0)
    cleaned = noise_gate(amplified, threshold_db=-55.0, samplerate=samplerate)
    return cleaned


class AudioRecorder:
    def __init__(self, samplerate=16000, channels=1):
        self.samplerate = samplerate
        self.channels = channels
        self.is_recording = False
        self.is_paused = False
        self.frames = []
        self.stream = None
        self._temp_files = []
        self._last_snapshot_idx = 0
        # 시스템 오디오
        self._capture_system = False
        self._loopback_frames = []
        self._loopback_thread = None
        self._loopback_stop = False

    @staticmethod
    def check_microphone():
        """마이크 사용 가능 여부 확인."""
        try:
            default_input = sd.query_devices(kind="input")
            if default_input is None:
                return False, "입력 장치가 없습니다"

            test_stream = sd.InputStream(
                samplerate=16000, channels=1, blocksize=1024,
            )
            test_stream.start()
            import time
            time.sleep(0.2)
            test_stream.stop()
            test_stream.close()

            device_name = default_input.get("name", "알 수 없는 장치")
            return True, device_name

        except sd.PortAudioError as e:
            err = str(e)
            if "unanticipated host error" in err.lower() or "invalid" in err.lower():
                return False, "마이크가 비활성화되어 있거나 접근 권한이 없습니다"
            return False, f"오디오 장치 오류: {err}"
        except Exception as e:
            return False, f"마이크 확인 실패: {e}"

    @staticmethod
    def can_capture_system():
        """시스템 오디오 캡처 가능 여부."""
        return HAS_SOUNDCARD

    @staticmethod
    def open_microphone_settings():
        import subprocess
        subprocess.Popen("start ms-settings:privacy-microphone", shell=True)

    @staticmethod
    def open_sound_settings():
        import subprocess
        subprocess.Popen("start ms-settings:sound", shell=True)

    def _callback(self, indata, frames, time, status):
        if self.is_recording and not self.is_paused:
            self.frames.append(indata.copy())

    def _loopback_worker(self):
        """시스템 오디오(스피커 출력)를 별도 스레드에서 캡처."""
        try:
            loopback = sc.default_speaker()
            with loopback.recorder(samplerate=self.samplerate, channels=1) as mic:
                while not self._loopback_stop:
                    if self.is_paused:
                        import time
                        time.sleep(0.1)
                        continue
                    data = mic.record(numframes=int(self.samplerate * 0.5))
                    self._loopback_frames.append(data)
        except Exception:
            pass  # 시스템 오디오 캡처 실패해도 마이크 녹음 계속

    def start(self, capture_system=False):
        self.frames = []
        self._loopback_frames = []
        self._last_snapshot_idx = 0
        self.is_recording = True
        self.is_paused = False
        self._capture_system = capture_system

        self.stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            callback=self._callback,
        )
        self.stream.start()

        # 시스템 오디오 캡처 시작
        if capture_system and HAS_SOUNDCARD:
            self._loopback_stop = False
            self._loopback_thread = threading.Thread(
                target=self._loopback_worker, daemon=True,
            )
            self._loopback_thread.start()

    def pause(self):
        """녹음 일시정지."""
        self.is_paused = True

    def resume(self):
        """녹음 재개."""
        self.is_paused = False

    def stop(self):
        self.is_recording = False
        self.is_paused = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        # 시스템 오디오 캡처 중지
        self._loopback_stop = True
        if self._loopback_thread:
            self._loopback_thread.join(timeout=2)
            self._loopback_thread = None

        if not self.frames:
            return None

        mic_audio = np.concatenate(self.frames, axis=0).flatten()

        # 시스템 오디오와 믹싱
        if self._capture_system and self._loopback_frames:
            try:
                sys_audio = np.concatenate(self._loopback_frames, axis=0).flatten()
                # 길이 맞추기 (짧은 쪽을 0으로 패딩)
                max_len = max(len(mic_audio), len(sys_audio))
                mic_padded = np.pad(mic_audio, (0, max_len - len(mic_audio)))
                sys_padded = np.pad(sys_audio, (0, max_len - len(sys_audio)))
                mixed = mic_padded * 0.6 + sys_padded * 0.4
                audio = mixed.astype(np.float32)
            except Exception:
                audio = mic_audio.astype(np.float32)
        else:
            audio = mic_audio.astype(np.float32)

        # 전처리 적용
        audio = process_audio(audio, self.samplerate)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(tmp.name, audio, self.samplerate)
        self._temp_files.append(tmp.name)
        return tmp.name

    def snapshot(self):
        """녹음 중 새로 쌓인 오디오만 전처리 후 임시 파일로 저장."""
        if not self.frames or not self.is_recording:
            return None

        current_idx = len(self.frames)
        if current_idx <= self._last_snapshot_idx:
            return None

        new_frames = self.frames[self._last_snapshot_idx:current_idx]
        self._last_snapshot_idx = current_idx

        audio = np.concatenate(new_frames, axis=0)

        # 2초 미만이면 롤백
        if len(audio) < self.samplerate * 2:
            self._last_snapshot_idx -= len(new_frames)
            return None

        # 말소리가 없으면 스킵 (무음 구간 전사 방지)
        if not has_speech(audio):
            return None

        # 전처리 적용
        audio = process_audio(audio, self.samplerate)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(tmp.name, audio, self.samplerate)
        self._temp_files.append(tmp.name)
        return tmp.name

    def cleanup(self):
        import os
        for f in self._temp_files:
            try:
                os.remove(f)
            except OSError:
                pass
        self._temp_files.clear()
