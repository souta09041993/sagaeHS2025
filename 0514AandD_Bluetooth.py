import flet as ft
import pandas as pd
import random
import os
import asyncio
import subprocess
from datetime import datetime
import re

# ──────────────────────────────
#  マスタ読み込み
# ──────────────────────────────
master_df = pd.read_excel("25_0418HS仮マスタ.xlsx",
                          sheet_name=["長さ", "重さ", "作業者一覧"])
length_master  = master_df["長さ"]
weight_master  = master_df["重さ"]
worker_master  = master_df["作業者一覧"]


def write_skip_flag(enabled: bool):
    with open("skip_flag.txt", "w", encoding="utf-8") as f:
        f.write("1" if enabled else "0")

def write_measurement_type(measurement_type: str):
    with open("測定種別.txt", "w", encoding="utf-8") as f:
        f.write(measurement_type)




def parse_ad_value(raw: str) -> float | None:
    raw = raw.strip()
    if not raw:
        return None
    if raw[0] in ("0", "1") and re.fullmatch(r"\d{5,}", raw[1:]):
        return int(raw[1:]) / 1000.0
    try:
        return float(raw)
    except ValueError:
        return None


# ──────────────────────────────
#  充填機パネル生成
# ──────────────────────────────
def build_filler_panels(filler_name, get_current_tab_name, dummy_focus):

    state = {
        "standard_value": None,
        "upper_limit": None,
        "lower_limit": None,
        "current_product_code": None,
        "measurement_count": 0,
        "measurements": [],
        "selected_worker": None,
        "measurement_type": "長さ",
        # 🆕 差分モード用の初期値追加
        "mode": "normal",       # "normal"（通常） or "diff"（差分）
        "last_value": None      # 前回値（差分計算用）
    }

    # ---------- UI パーツ ----------
    latest_measurement_text = ft.Text("", size=60, weight="bold", text_align="center")
    average_text            = ft.Text("", size=40, weight="bold", text_align="center",
                                      color="red")
    measurement_list        = ft.Column()

    latest_container = ft.Container(
        content       = latest_measurement_text,
        padding       = 20,
        bgcolor       = "#F7F7F7",
        border_radius = 10,
        expand        = True,
        alignment     = ft.alignment.center
    )

    product_info    = ft.Column([], spacing=5)

    product_dropdown = ft.Dropdown(
        label       = "製品を選択",
        options     = [ft.dropdown.Option(f"{r['製品コード']} - {r['製品名']}")
                       for _, r in length_master.iterrows()],
        width       = 400,
        text_style  = ft.TextStyle(size=18, color="black")
    )

    # ---------- CSV 保存 ----------
    def save_measurement(code, value, result, worker,
                            measurement_no, measurement_type):

        today_date = datetime.now().strftime("%Y%m%d")
        subfolder  = "サイズ" if measurement_type == "長さ" else "重量"
        base_dir   = os.path.join("./測定データ", str(code), subfolder, today_date)
        os.makedirs(base_dir, exist_ok=True)

        filename   = f"{worker}_{code}_{today_date}.csv"
        file_path  = os.path.join(base_dir, filename)
        unit       = "mm" if measurement_type == "長さ" else "g"
        mode_str   = "差分" if state["mode"] == "diff" else "通常"

        file_exists = os.path.exists(file_path)
        with open(file_path, "a", encoding="utf-8-sig") as f:
            if not file_exists:
                f.write("日時,作業者,充填機,測定番号,測定値,判定,記録モード\n")
            f.write(
                f"{datetime.now():%Y-%m-%d %H:%M:%S},"
                f"{worker},{filler_name},{measurement_no},"
                f"{value:.3f} {unit},{result},{mode_str}\n"
                )


    # ---------- 製品呼び出し ----------
    def call_product_info():
        current_master = length_master if state["measurement_type"] == "長さ" else weight_master
        unit           = "mm" if state["measurement_type"] == "長さ" else "g"

        if not state["selected_worker"]:
            product_info.controls = [ft.Text("⚠ 作業者を選択してください！", color="red", size=28)]
            return
        if not product_dropdown.value:
            product_info.controls = [ft.Text("⚠ 製品を選択してください！", color="red", size=28)]
            return

        code_str = product_dropdown.value.split(" - ")[0]
        match    = current_master[current_master['製品コード'] == int(code_str)]

        if not match.empty:
            state["measurements"].clear()
            state["measurement_count"] = 0
            latest_measurement_text.value = ""
            latest_container.bgcolor      = "#F7F7F7"
            measurement_list.controls.clear()
            average_text.value = ""

            state["standard_value"]      = float(match.iloc[0]['基準'])
            state["upper_limit"]         = pd.to_numeric(match.iloc[0]['上限値'], errors="coerce")
            state["lower_limit"]         = pd.to_numeric(match.iloc[0]['下限値'], errors="coerce")
            state["current_product_code"]= int(code_str)

            product_info.controls = [
                ft.Text(f"✅ 呼び出し成功！（{filler_name}）", size=32, weight="bold",
                        color="green"),
                ft.Text(f"基準: {state['standard_value']:.3f} {unit}",
                        size=32, weight="bold"),
                ft.Row([
                    ft.Text(f"上限値: {state['upper_limit']:.3f} {unit}",
                            size=28, color="red"),
                    ft.Text("｜", size=28),
                    ft.Text(f"下限値: {state['lower_limit']:.3f} {unit}",
                            size=28, color="blue"),
                ], spacing=30),
                ft.Text(f"注意事項: {match.iloc[0]['注意事項']}", size=24)
            ]
        else:
            product_info.controls = [ft.Text("⚠ 該当する製品コードがありません",
                                             color="red", size=28)]

    product_dropdown.on_change = lambda e: (call_product_info(), e.page.update())

    measurement_tab = ft.Tabs(
        tabs=[ft.Tab(text="長さ測定"), ft.Tab(text="重さ測定")],
        selected_index=0,
        on_change=lambda e: (
            state.__setitem__("measurement_type", "長さ" if e.control.selected_index == 0 else "重さ"),
            write_skip_flag(e.control.selected_index == 0),
            write_measurement_type("長さ" if e.control.selected_index == 0 else "重さ"),
            container_mode_selector.__setattr__("visible", e.control.selected_index == 1),  # ✅ ←これ！
            call_product_info(),
            e.page.update()
        )
    )




    # ---------- 自動測定ボタン ----------
    def add_measurement(e):
        if get_current_tab_name() != filler_name:
            product_info.controls = [ft.Text("⚠ タブを正しい充填機に切り替えてください！",
                                             color="orange", size=24)]
            e.page.update()
            return

        if not state["current_product_code"] or not state["standard_value"]:
            product_info.controls = [ft.Text("⚠ 製品情報を呼び出してください！",
                                             color="red", size=28)]
            e.page.update()
            return

        measure = round(random.uniform(state["lower_limit"] - 0.05,
                                       state["upper_limit"] + 0.05), 3)
        state["measurements"].append(measure)
        state["measurement_count"] += 1
        if len(state["measurements"]) > 5:
            state["measurements"].pop(0)

        unit   = "mm" if state["measurement_type"] == "長さ" else "g"
        result = ("合格"
                  if state["lower_limit"] <= measure <= state["upper_limit"]
                  else "不合格")

        latest_container.bgcolor   = "#ccffcc" if result == "合格" else "#ffcccc"
        latest_measurement_text.value = f"{measure:.3f} {unit} ({result})"

        measurement_list.controls.clear()
        for i, v in enumerate(state["measurements"]):
            judge = ("合格"
                     if state["lower_limit"] <= v <= state["upper_limit"]
                     else "不合格")
            color = "green" if judge == "合格" else "red"
            measurement_list.controls.append(
                ft.Row([
                    ft.Text(f"{i+1}", width=60, size=28),
                    ft.Text(f"{v:.3f} {unit}", width=200, size=28),
                    ft.Text(judge, color=color, size=28)
                ])
            )

        avg = sum(state["measurements"]) / len(state["measurements"])
        average_text.value = f"直近5個の平均: {avg:.3f} {unit}"

        save_measurement(state["current_product_code"], measure, result,
                         state["selected_worker"], state["measurement_count"],
                         state["measurement_type"])
        e.page.update()

    # ---------- 手動入力 ----------
    manual_input = ft.TextField(label="手動測定値を入力", width=200)

    def on_manual_submit(e):
        val = manual_input.value.strip()
        try:
            measure = float(val)
            unit = "mm" if state["measurement_type"] == "長さ" else "g"

            # 🆕 差分モード処理
            if state["mode"] == "diff":
                if state["last_value"] is None:
                    state["last_value"] = measure  # 初回値を保存
                    manual_input.value = ""

                    # ✅ 初回値をUIに表示（色は灰色など）
                    state["latest_measurement_text"].value = f"{measure:.3f} {unit}（初回）"
                    state["latest_container"].bgcolor = "#eeeeee"  # グレー系

                    product_info.controls = [ft.Text("初回値を記録しました。次回から差分を取ります。", color="green", size=24)]
                    e.page.update()
                    return


                diff = state["last_value"] - measure
                state["last_value"] = measure

                if diff <= 0:
                    product_info.controls = [ft.Text("⚠ 差分が無効です（負値または0）", color="red", size=24)]
                    manual_input.value = ""
                    e.page.update()
                    return

                measure = diff  # 差分値を記録値として使う

            # 🧠 共通：記録・更新
            result = ("合格"
                    if state["lower_limit"] <= measure <= state["upper_limit"]
                    else "不合格")

            state["measurements"].append(measure)
            state["measurement_count"] += 1
            if len(state["measurements"]) > 5:
                state["measurements"].pop(0)

            state["save_measurement"](state["current_product_code"], measure, result,
                                    state["selected_worker"], state["measurement_count"],
                                    state["measurement_type"])

            state["latest_container"].bgcolor = "#ccffcc" if result == "合格" else "#ffcccc"
            state["latest_measurement_text"].value = f"{measure:.3f} {unit} ({result})"

            state["measurement_list"].controls.clear()
            for i, v in enumerate(state["measurements"]):
                judge = ("合格"
                        if state["lower_limit"] <= v <= state["upper_limit"]
                        else "不合格")
                color = "green" if judge == "合格" else "red"
                state["measurement_list"].controls.append(
                    ft.Row([
                        ft.Text(f"{i+1}", width=60, size=28),
                        ft.Text(f"{v:.3f} {unit}", width=200, size=28),
                        ft.Text(judge, color=color, size=28)
                    ])
                )

            avg = sum(state["measurements"]) / len(state["measurements"])
            state["average_text"].value = f"直近5個の平均: {avg:.3f} {unit}"

            manual_input.value = ""
            e.page.update()

        except ValueError:
            product_info.controls = [ft.Text("⚠ 数値を正しく入力してください", color="red", size=24)]
            e.page.update()

        # ---------- モード切替（通常／差分） ----------
    mode_selector = ft.RadioGroup(
        value="normal",
        on_change=lambda e: (
            state.__setitem__("mode", e.control.value),
            state.__setitem__("last_value", None),
            print(f"[DEBUG] モード変更: {e.control.value}")
        ),
        content=ft.Row([
            ft.Radio(value="normal", label="通常モード"),
            ft.Radio(value="diff", label="差分モード")
        ])
    )

    container_mode_selector = ft.Container(content=mode_selector, visible=False)



    # ② 既存の left_panel に組み込む（← 追加）
    left_panel = ft.Column([
        product_dropdown,
        measurement_tab,
        container_mode_selector,
        manual_input,
        ft.ElevatedButton("保存（手動測定）", on_click=on_manual_submit,
                        bgcolor="#cceeff"),
        product_info
    ], spacing=20)


    right_panel = ft.Column([
        latest_container,
        average_text,
        ft.Text("【直近5個の測定値】", size=28, weight="bold"),
        measurement_list
    ], spacing=20)

    # ---------- state へ関数登録 ----------
    state["save_measurement"]        = save_measurement
    state["latest_measurement_text"] = latest_measurement_text
    state["latest_container"]        = latest_container
    state["average_text"]            = average_text
    state["measurement_list"]        = measurement_list
    state["add_measurement"]         = add_measurement

    return left_panel, right_panel, state

write_skip_flag(True)  # 初期状態：ノギス用（スキップ有効）

def main(page: ft.Page):
    receiver_proc = subprocess.Popen(["python", "テキスト出力用.py"])

    page.title               = "ノギス連携版（自動測定）"
    page.scroll              = ft.ScrollMode.AUTO
    page.vertical_alignment  = ft.MainAxisAlignment.START

    dummy_focus = ft.TextField(visible=False, autofocus=True)
    page.add(dummy_focus)

    current_tab_name = "充填機A"
    get_tab_name     = lambda: current_tab_name

    worker_dropdown = ft.Dropdown(
        label   = "作業者を選択",
        options = [ft.dropdown.Option(n) for n in worker_master["作業者名"].dropna()],
        width   = 300
    )

    panels, states = {}, {}
    for name in ["充填機A", "充填機B", "充填機C"]:
        left, right, state = build_filler_panels(name, get_tab_name, dummy_focus)
        panels[name]  = {"left": left, "right": right}
        states[name]  = state

    selected_left_panel  = ft.Container(content=panels["充填機A"]["left"],  expand=True)
    selected_right_panel = ft.Container(content=panels["充填機A"]["right"], expand=True)

    def on_tab_change(e):
        nonlocal current_tab_name
        current_tab_name = e.control.tabs[e.control.selected_index].text
        selected_left_panel.content = panels[current_tab_name]["left"]
        selected_right_panel.content = panels[current_tab_name]["right"]

        # ✅ 履歴描画を復元
        st = states[current_tab_name]
        unit = "mm" if st["measurement_type"] == "長さ" else "g"

        st["measurement_list"].controls.clear()
        for i, v in enumerate(st["measurements"]):
            judge = "合格" if st["lower_limit"] <= v <= st["upper_limit"] else "不合格"
            color = "green" if judge == "合格" else "red"
            st["measurement_list"].controls.append(
                ft.Row([
                    ft.Text(f"{i+1}", width=60, size=28),
                    ft.Text(f"{v:.3f} {unit}", width=200, size=28),
                    ft.Text(judge, color=color, size=28)
                ])
            )

        if st["measurements"]:
            avg = sum(st["measurements"]) / len(st["measurements"])
            st["average_text"].value = f"直近5個の平均: {avg:.3f} {unit}"
        else:
            st["average_text"].value = ""

        page.update()


    worker_dropdown.on_change = lambda e: [
        st.__setitem__("selected_worker", worker_dropdown.value) for st in states.values()
    ]

    tabview = ft.Tabs(
        tabs           = [ft.Tab(text=n) for n in panels],
        selected_index = 0,
        on_change      = on_tab_change
    )



    # ---------- ノギス自動受信タスク ----------
    async def check_for_measurement():
        filepath = "shared_measurement.txt"
        while True:
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    raw = f.read().strip()

                value = parse_ad_value(raw)
                if value is None:
                    open(filepath, "w", encoding="utf-8").write("")
                    await asyncio.sleep(1)
                    continue

                st = states[current_tab_name]

                # ────────────────────────
                # 差分モード処理（差分をとって記録）
                # ────────────────────────
                if st["mode"] == "diff":
                    if st["last_value"] is None:
                        st["last_value"] = value

                        # ✅ 初回値をUIに表示（灰色系）
                        st["latest_measurement_text"].value = f"{value:.3f} {unit}（初回）"
                        st["latest_container"].bgcolor = "#eeeeee"

                        open(filepath, "w", encoding="utf-8").write("")
                        page.update()
                        await asyncio.sleep(1)
                        continue


                    diff = st["last_value"] - value
                    st["last_value"] = value  # 更新

                    if diff <= 0:
                        st["latest_measurement_text"].value = "⚠ 差分が無効です"
                        st["latest_container"].bgcolor = "#ffcccc"
                        open(filepath, "w", encoding="utf-8").write("")
                        page.update()
                        await asyncio.sleep(1)
                        continue

                    value = diff  # 差分を記録用の値とする

                # ────────────────────────
                # 通常モード処理（または差分値）
                # ────────────────────────
                if all(st[k] is not None for k in
                    ("standard_value", "lower_limit", "upper_limit",
                        "current_product_code", "selected_worker")):

                    st["measurements"].append(value)
                    st["measurement_count"] += 1
                    if len(st["measurements"]) > 5:
                        st["measurements"].pop(0)

                    result = ("合格"
                            if st["lower_limit"] <= value <= st["upper_limit"]
                            else "不合格")
                    unit = "mm" if st["measurement_type"] == "長さ" else "g"

                    st["save_measurement"](
                        st["current_product_code"], value, result,
                        st["selected_worker"], st["measurement_count"],
                        st["measurement_type"]
                    )

                    st["latest_measurement_text"].value = f"{value:.3f} {unit} ({result})"
                    st["latest_container"].bgcolor = (
                        "#ccffcc" if result == "合格" else "#ffcccc"
                    )

                    st["measurement_list"].controls.clear()
                    for i, v in enumerate(st["measurements"]):
                        judge = ("合格"
                                if st["lower_limit"] <= v <= st["upper_limit"]
                                else "不合格")
                        color = "green" if judge == "合格" else "red"
                        st["measurement_list"].controls.append(
                            ft.Row([
                                ft.Text(f"{i+1}", width=60, size=28),
                                ft.Text(f"{v:.3f} {unit}", width=200, size=28),
                                ft.Text(judge, color=color, size=28)
                            ])
                        )

                    avg = sum(st["measurements"]) / len(st["measurements"])
                    st["average_text"].value = f"直近5個の平均: {avg:.3f} {unit}"

                    open(filepath, "w", encoding="utf-8").write("")
                    page.update()

            await asyncio.sleep(1)

    # ---------- 終了ボタン ----------
    exit_button = ft.ElevatedButton("アプリ終了", bgcolor="red", color="white",
                                    on_click=lambda e: (
                                        receiver_proc.terminate()
                                        if receiver_proc.poll() is None else None,
                                        os._exit(0)
                                    ))

    page.add(
        ft.Row([
            ft.Container(
                content = ft.Column([
                    ft.Text("作業者を選択", size=28),
                    worker_dropdown,
                    tabview,
                    selected_left_panel,
                    exit_button
                ], spacing=20),
                padding = 20,
                bgcolor = "#F0F8FF",
                expand  = True
            ),
            selected_right_panel
        ], expand=True)
    )

    page.run_task(check_for_measurement)

ft.app(target=main)
