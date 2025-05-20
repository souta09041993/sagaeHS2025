import keyboard, time, re
from datetime import datetime

FILEPATH = "shared_measurement.txt"
buffer = ""
skip_first_digit = True       # ★ 次の計測で最初に来る数値を無視する

print("🔍 ノギス入力を監視中（Enter で確定）")

SKIP_FLAG_PATH = "skip_flag.txt"

def read_skip_flag():
    try:
        with open(SKIP_FLAG_PATH, "r", encoding="utf-8") as f:
            return f.read().strip() == "1"
    except FileNotFoundError:
        return True  # デフォルトはスキップON（ノギス前提）
    
def get_current_measurement_type():
    try:
        with open("測定種別.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "長さ"  # デフォルト（安全にノギス前提）



def on_key(event):
    global buffer

    if event.event_type != keyboard.KEY_DOWN:
        return

    k = event.name

    # ─── 抑止したいキー ───
    if k in {"left", "right", "up", "down", "tab"}:
        event.suppress = True
        return


    if len(k) == 1 and (k.isdigit() or k == "."):
        event.suppress = True
        if read_skip_flag():
            # スキップした後、スキップ状態をOFFにする
            with open(SKIP_FLAG_PATH, "w", encoding="utf-8") as f:
                f.write("0")
            return
        buffer += k
        return


    # ─── バックスペース ───
    if k == "backspace":
        event.suppress = True
        buffer = buffer[:-1]
        return

    # ─── Enter: 計測確定 ───
    if k in {"enter", "return"}:
        event.suppress = True
        candidate = buffer.strip()
        buffer = ""

        # ★ 測定種別が「長さ」のときだけ、次回スキップONに戻す
        if get_current_measurement_type() == "長さ":
            with open(SKIP_FLAG_PATH, "w", encoding="utf-8") as f:
                f.write("1")

        # 数値判定
        if re.fullmatch(r"-?\d+(?:\.\d+)?", candidate):
            with open(FILEPATH, "w", encoding="utf-8") as f:
                f.write(candidate)
            print(f"[{datetime.now():%H:%M:%S}] 受信 → {candidate}")
        else:
            print(f"⚠ 無効形式: {candidate}")



keyboard.hook(on_key)
keyboard.wait()    # Ctrl‑C で終了