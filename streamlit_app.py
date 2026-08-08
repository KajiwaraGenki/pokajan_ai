
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from pokajan_simulator_v24 import (
    AgentConfig,
    GROUPS,
    groups_are_compatible,
    make_member_number_map,
    build_manual_game_state,
    evaluate_manual_position,
    Card,
)

st.set_page_config(
    page_title="ポカじゃん打牌解析",
    page_icon="🀄",
    layout="wide",
)

COLOR_LABEL_TO_CODE = {
    "橙": "orange",
    "青": "blue",
    "桃": "pink",
}

GROUP_CODES = [
    "JP0", "JP1", "JP2", "GAMERS", "JP3", "JP4", "JP5",
    "HOLOX", "REGLOSS", "MYTH", "ADVENT", "PROMISE",
    "ID1", "ID2", "ID3",
]

DEFAULT_CONFIG_PATH = Path(__file__).with_name("pokajan_tuned_config.json")


def load_config():
    if DEFAULT_CONFIG_PATH.exists():
        data = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
        return AgentConfig(
            role_score_weight=float(data["role_score_weight"]),
            future_role_weight=float(data["future_role_weight"]),
            bonus_keep_weight=float(data["bonus_keep_weight"]),
            danger_weight=float(data["danger_weight"]),
        )

    st.error(
        "pokajan_tuned_config.json が見つかりません。"
        "学習済みJSONをこのアプリと同じフォルダに置いてください。"
    )
    st.stop()


def make_card(member: str, color_label: str, used_counts: dict):
    color = COLOR_LABEL_TO_CODE[color_label]
    key = (member, color)
    copy_no = used_counts.get(key, 0) + 1
    if copy_no > 3:
        raise ValueError(f"{member}の{color_label}は3枚までです。")
    used_counts[key] = copy_no
    return Card(member, color, copy_no)


def render_card_rows(title, members, count, prefix, used_counts):
    st.markdown(f"#### {title}")
    cards = []

    for i in range(count):
        c1, c2 = st.columns([3, 1])
        member = c1.selectbox(
            f"{title} {i+1} ホロメン",
            members,
            key=f"{prefix}_member_{i}",
            label_visibility="collapsed",
        )
        color = c2.selectbox(
            f"{title} {i+1} 色",
            ["橙", "青", "桃"],
            key=f"{prefix}_color_{i}",
            label_visibility="collapsed",
        )
        cards.append(make_card(member, color, used_counts))

    return cards


st.title("ポカじゃん 打牌解析")
st.caption("学習済みAI + 不完全情報モンテカルロで、平均最終コインが高い打牌を比較します。")

config = load_config()

with st.sidebar:
    st.header("解析設定")
    simulations = st.slider(
        "各打牌のシミュレーション回数",
        min_value=20,
        max_value=500,
        value=100,
        step=20,
    )
    st.caption("多いほど安定しますが、解析に時間がかかります。")

st.subheader("1. 登場グループ")

selected_groups = []
cols = st.columns(4)
for i in range(4):
    group = cols[i].selectbox(
        f"グループ{i+1}",
        GROUP_CODES,
        index=[4, 10, 11, 14][i],
        key=f"group_{i}",
    )
    selected_groups.append(group)

selected_groups = tuple(selected_groups)

if len(set(selected_groups)) != 4:
    st.warning("登場グループは4種類すべて別にしてください。")
    st.stop()

if not groups_are_compatible(selected_groups):
    st.warning("JP1とGAMERSは同時に登場できません。")
    st.stop()

number_to_member, _ = make_member_number_map(selected_groups)
members = list(number_to_member.values())

with st.expander("今回の登場ホロメン一覧", expanded=False):
    for n, member in number_to_member.items():
        st.write(f"{n}. {member}")

st.subheader("2. 基本情報")

c1, c2, c3 = st.columns(3)
bonus_member = c1.selectbox("ボーナスホロメン", members)
player_index = c2.selectbox(
    "自分の席",
    [0, 1, 2, 3],
    format_func=lambda x: f"P{x+1}",
)
deck_remaining = c3.number_input(
    "残り山札枚数",
    min_value=0,
    max_value=100,
    value=60,
    step=1,
)

coin_cols = st.columns(4)
coins = tuple(
    int(
        coin_cols[i].number_input(
            f"P{i+1} コイン",
            min_value=0,
            value=1000,
            step=10,
            key=f"coin_{i}",
        )
    )
    for i in range(4)
)

st.subheader("3. 自分の8枚手札")
used_counts = {}

hand = []
hand_cols = st.columns(4)
for i in range(8):
    with hand_cols[i % 4]:
        st.markdown(f"**{i+1}枚目**")
        member = st.selectbox(
            "ホロメン",
            members,
            key=f"hand_member_{i}",
            label_visibility="collapsed",
        )
        color = st.selectbox(
            "色",
            ["橙", "青", "桃"],
            key=f"hand_color_{i}",
            label_visibility="collapsed",
        )
        try:
            hand.append(make_card(member, color, used_counts))
        except ValueError as e:
            st.error(str(e))
            st.stop()

st.subheader("4. 捨て牌履歴")
st.caption("各プレイヤーの捨て牌枚数を指定し、その下にカードを入力します。")

player_discards = {}

for p in range(4):
    with st.expander(f"P{p+1} の捨て牌", expanded=False):
        n_discards = st.number_input(
            "枚数",
            min_value=0,
            max_value=30,
            value=0,
            step=1,
            key=f"discard_count_{p}",
        )
        cards = []
        for j in range(int(n_discards)):
            d1, d2 = st.columns([3, 1])
            member = d1.selectbox(
                f"P{p+1} 捨て牌{j+1} ホロメン",
                members,
                key=f"discard_member_{p}_{j}",
                label_visibility="collapsed",
            )
            color = d2.selectbox(
                f"P{p+1} 捨て牌{j+1} 色",
                ["橙", "青", "桃"],
                key=f"discard_color_{p}_{j}",
                label_visibility="collapsed",
            )
            try:
                cards.append(make_card(member, color, used_counts))
            except ValueError as e:
                st.error(str(e))
                st.stop()
        player_discards[p] = cards

with st.expander("既に役で消えた公開カード（任意）", expanded=False):
    removed_count = st.number_input(
        "枚数",
        min_value=0,
        max_value=50,
        value=0,
        step=1,
        key="removed_count",
    )
    public_removed_cards = []
    for j in range(int(removed_count)):
        r1, r2 = st.columns([3, 1])
        member = r1.selectbox(
            f"消えたカード{j+1} ホロメン",
            members,
            key=f"removed_member_{j}",
            label_visibility="collapsed",
        )
        color = r2.selectbox(
            f"消えたカード{j+1} 色",
            ["橙", "青", "桃"],
            key=f"removed_color_{j}",
            label_visibility="collapsed",
        )
        try:
            public_removed_cards.append(make_card(member, color, used_counts))
        except ValueError as e:
            st.error(str(e))
            st.stop()

st.divider()

if st.button("解析する", type="primary", use_container_width=True):
    try:
        game = build_manual_game_state(
            selected_groups=selected_groups,
            bonus_member=bonus_member,
            coins=coins,
            player_index=player_index,
            hand=hand,
            player_discards=player_discards,
            deck_remaining=int(deck_remaining),
            public_removed_cards=public_removed_cards,
            seed=17,
        )

        with st.spinner("シミュレーション中..."):
            rows = evaluate_manual_position(
                game,
                player_index,
                tuned_config=config,
                simulations_per_card=int(simulations),
                seed=999,
            )

        result_rows = []
        for rank, row in enumerate(rows, 1):
            result_rows.append(
                {
                    "順位": rank,
                    "打牌": row.card.short(),
                    "平均最終コイン": round(row.average_final_coins, 1),
                    "期待増減": round(row.expected_coin_change, 1),
                    "中央値": round(row.median_final_coins, 1),
                    "0点率": f"{row.zero_rate:.1%}",
                }
            )

        st.success(f"推奨打牌: {rows[0].card.short()}")
        st.dataframe(
            pd.DataFrame(result_rows),
            hide_index=True,
            use_container_width=True,
        )

        st.caption(
            "評価は順位ではなく、平均最終コインを最優先しています。"
            "試行回数が少ない場合は結果がぶれることがあります。"
        )

    except Exception as e:
        st.exception(e)
