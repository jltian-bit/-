"""
选剑演武 - 决策选择器
===================
基于21点变体的选剑演武游戏，提供实时决策建议。
"""

from functools import lru_cache
from typing import List, Tuple

# ============================================================
# 模块1: 游戏基础（牌库、奖励计算）
# ============================================================

# 牌库初始状态: 28张牌
INITIAL_DECK = (8, 5, 2, 5, 8)  # 点数为1,2,3,4,5的牌各有多少张
CARD_VALUES = (1, 2, 3, 4, 5)
MAX_DRAWS = 5


def get_reward_level(sum_val: int) -> int:
    """将手牌点数之和映射到奖励等级(0-10)"""
    if sum_val <= 10:
        return sum_val
    else:
        return (sum_val - 1) % 10


def get_reward_value(sum_val: int, reward_table: Tuple[float, ...]) -> float:
    """根据手牌点数之和和奖励表，返回实际奖励数值"""
    level = get_reward_level(sum_val)
    return reward_table[level]


# ============================================================
# 模块2: 单局最优策略（动态规划）
# ============================================================

@lru_cache(maxsize=None)
def optimal_value_and_action(
    c1: int, c2: int, c3: int, c4: int, c5: int,
    sum_val: int, draws: int,
    reward_table: Tuple[float, ...]
) -> Tuple[float, str]:
    """
    返回 (期望奖励值, 最优动作"stop"或"draw")
    假设本局结束后必定领取奖励（不考虑可选领取）
    """
    if draws == MAX_DRAWS:
        return get_reward_value(sum_val, reward_table), "stop"

    total = c1 + c2 + c3 + c4 + c5
    if total == 0:
        return get_reward_value(sum_val, reward_table), "stop"

    stop_value = get_reward_value(sum_val, reward_table)

    # 计算继续抽牌的期望值
    draw_value = 0.0
    if c1 > 0:
        draw_value += (c1 / total) * optimal_value_and_action(
            c1 - 1, c2, c3, c4, c5, sum_val + 1, draws + 1, reward_table
        )[0]
    if c2 > 0:
        draw_value += (c2 / total) * optimal_value_and_action(
            c1, c2 - 1, c3, c4, c5, sum_val + 2, draws + 1, reward_table
        )[0]
    if c3 > 0:
        draw_value += (c3 / total) * optimal_value_and_action(
            c1, c2, c3 - 1, c4, c5, sum_val + 3, draws + 1, reward_table
        )[0]
    if c4 > 0:
        draw_value += (c4 / total) * optimal_value_and_action(
            c1, c2, c3, c4 - 1, c5, sum_val + 4, draws + 1, reward_table
        )[0]
    if c5 > 0:
        draw_value += (c5 / total) * optimal_value_and_action(
            c1, c2, c3, c4, c5 - 1, sum_val + 5, draws + 1, reward_table
        )[0]

    if stop_value >= draw_value:
        return stop_value, "stop"
    else:
        return draw_value, "draw"


def get_recommendation(
    deck: Tuple[int, ...], sum_val: int, draws: int,
    reward_table: Tuple[float, ...]
) -> Tuple[str, float]:
    """
    返回当前状态下的建议和期望奖励
    返回: (建议"stop"或"draw", 本局期望奖励)
    """
    c1, c2, c3, c4, c5 = deck
    value, action = optimal_value_and_action(
        c1, c2, c3, c4, c5, sum_val, draws, reward_table
    )
    return action, value


# ============================================================
# 模块3: 单局奖励分布计算
# ============================================================

@lru_cache(maxsize=None)
def compute_distribution(
    c1: int, c2: int, c3: int, c4: int, c5: int,
    sum_val: int, draws: int,
    reward_table: Tuple[float, ...]
) -> List[float]:
    """
    计算遵循最优策略下，本局最终奖励等级的概率分布
    返回长度为11的列表，索引i代表奖励等级i的概率
    """
    if draws == MAX_DRAWS:
        dist = [0.0] * 11
        level = get_reward_level(sum_val)
        dist[level] = 1.0
        return dist

    total = c1 + c2 + c3 + c4 + c5
    if total == 0:
        dist = [0.0] * 11
        level = get_reward_level(sum_val)
        dist[level] = 1.0
        return dist

    # 检查最优动作
    _, action = optimal_value_and_action(
        c1, c2, c3, c4, c5, sum_val, draws, reward_table
    )

    if action == "stop":
        dist = [0.0] * 11
        level = get_reward_level(sum_val)
        dist[level] = 1.0
        return dist

    # 继续抽牌: 按概率加权各分支的分布
    dist = [0.0] * 11
    counts = [c1, c2, c3, c4, c5]
    for i, (cv, val) in enumerate(zip(counts, CARD_VALUES)):
        if cv > 0:
            prob = cv / total
            new_counts = list((c1, c2, c3, c4, c5))
            new_counts[i] -= 1
            sub_dist = compute_distribution(
                *new_counts, sum_val + val, draws + 1, reward_table
            )
            for j in range(11):
                dist[j] += prob * sub_dist[j]

    return dist


# ============================================================
# 模块4: 每日资源优化（领取/翻倍/轮数决策）
# ============================================================

def compute_daily_value(
    max_claims: int, max_doubles: int, max_rounds: int,
    reward_table: Tuple[float, ...],
) -> List[List[List[float]]]:
    """
    计算每日DP值 V[R][D][N] = 剩余R次领取、D次翻倍、N轮时的期望总收益
    返回三维列表: (max_claims+1) x (max_doubles+1) x (max_rounds+1)
    """
    base_dist = compute_distribution(
        *INITIAL_DECK, 0, 0, reward_table
    )

    # V[r][d][n]
    V = [[[0.0] * (max_rounds + 1)
          for _ in range(max_doubles + 1)]
         for _ in range(max_claims + 1)]

    # V[r][d][0] = 0 (无剩余轮数)
    # V[0][d][n] = 0 (无领取次数)

    for n in range(1, max_rounds + 1):
        for r in range(1, max_claims + 1):
            for d in range(max_doubles + 1):
                expected = 0.0
                for level in range(11):
                    rv = reward_table[level]
                    choices = [V[r][d][n - 1]]  # 放弃领取（消耗一轮）
                    if r > 0:
                        choices.append(rv + V[r - 1][d][n - 1])
                    if r > 0 and d > 0:
                        choices.append(2 * rv + V[r - 1][d - 1][n - 1])
                    expected += base_dist[level] * max(choices)
                V[r][d][n] = expected

    return V


def get_claim_decision(
    reward_level: int, reward_table: Tuple[float, ...],
    V: List[List[List[float]]], r: int, d: int, n: int
) -> Tuple[str, bool]:
    """
    给定最终奖励等级和剩余资源(r=领取次数, d=翻倍次数, n=剩余轮数)，
    返回 (决策, 是否使用翻倍)
    决策: "claim"(领取), "pass"(放弃)
    """
    if n <= 0 or r <= 0:
        return "pass", False

    rv = reward_table[reward_level]

    pass_val = V[r][d][n - 1]  # 放弃，消耗一轮
    claim_val = rv + V[r - 1][d][n - 1]
    double_val = 2 * rv + V[r - 1][d - 1][n - 1] if d > 0 else -1

    best = max(pass_val, claim_val, double_val)

    if best <= pass_val + 1e-9:
        return "pass", False
    elif best == double_val:
        return "claim", True
    else:
        return "claim", False


def get_claim_thresholds(
    V: List[List[List[float]]], r: int, d: int, n: int
) -> Tuple[float, float]:
    """
    返回 (领取阈值, 翻倍阈值)
    - 当奖励值 >= 领取阈值时，建议领取
    - 当奖励值 >= 翻倍阈值时，建议领取并翻倍
    阈值基于剩余资源 r=领取次数, d=翻倍次数, n=剩余轮数
    """
    if n <= 0 or r <= 0:
        return float('inf'), float('inf')

    pass_val = V[r][d][n - 1]
    threshold_claim = pass_val - V[r - 1][d][n - 1]
    if d > 0:
        # 翻倍 vs 不翻倍: 2*rv + V[r-1][d-1][n-1] > rv + V[r-1][d][n-1]
        # => rv > V[r-1][d][n-1] - V[r-1][d-1][n-1]
        threshold_double_vs_claim = V[r - 1][d][n - 1] - V[r - 1][d - 1][n - 1]
        threshold_double = max(threshold_claim, threshold_double_vs_claim + 1e-9)
    else:
        threshold_double = float('inf')
    return threshold_claim, threshold_double


# ============================================================
# 模块5: 交互界面
# ============================================================

def print_separator(title: str = ""):
    """打印分隔线"""
    if title:
        print(f"\n{'=' * 50}")
        print(f"  {title}")
        print('=' * 50)
    else:
        print('-' * 50)


def input_reward_table() -> Tuple[float, ...]:
    """交互式输入奖励表（各点数0-10对应的奖励数值）"""
    print_separator("输入奖励数值")
    print("请输入点数0~10各自对应的奖励数值（可为小数）")
    rewards = []
    for i in range(11):
        while True:
            try:
                val = float(input(f"  点数{i:2d} 的奖励: "))
                rewards.append(val)
                break
            except ValueError:
                print("  请输入有效数字")
    return tuple(rewards)


def input_game_state() -> Tuple[Tuple[int, ...], int, int]:
    """交互式输入当前游戏状态"""
    from collections import Counter

    print_separator("输入当前牌局状态")
    print("请输入已抽到的牌（输入牌的点数1~5，用空格分隔）")
    print("例如抽到了 1, 1, 3 → 输入: 1 1 3")
    print("如果还没抽牌，直接按回车")

    while True:
        raw = input("  已抽到的牌: ").strip()
        if raw == "":
            cards = []
        else:
            try:
                cards = [int(x) for x in raw.split()]
            except ValueError:
                print("  请输入空格分隔的数字")
                continue

        valid = True
        for c in cards:
            if c not in (1, 2, 3, 4, 5):
                print(f"  点数 {c} 无效，只能是1~5")
                valid = False
                break
        if not valid:
            continue

        card_counts = Counter(cards)
        initial = dict(zip(CARD_VALUES, INITIAL_DECK))
        for val, cnt in card_counts.items():
            if cnt > initial[val]:
                print(f"  点数为{val}的牌只有{initial[val]}张，你输入了{cnt}张")
                valid = False
                break
        if not valid:
            continue

        if len(cards) > MAX_DRAWS:
            print(f"  最多抽{MAX_DRAWS}张牌")
            continue

        break

    card_counts = Counter(cards)
    deck = list(INITIAL_DECK)
    for i, val in enumerate(CARD_VALUES):
        deck[i] -= card_counts.get(val, 0)
    deck = tuple(deck)
    sum_val = sum(cards)
    draws = len(cards)

    return deck, sum_val, draws


def input_daily_resources() -> Tuple[int, int, int]:
    """输入每日剩余资源"""
    print_separator("输入每日剩余资源")
    while True:
        try:
            r = int(input("  剩余奖励领取次数: "))
            if r < 0:
                print("  请输入非负整数")
                continue
            break
        except ValueError:
            print("  请输入整数")
    while True:
        try:
            d = int(input("  剩余翻倍次数: "))
            if d < 0:
                print("  请输入非负整数")
                continue
            break
        except ValueError:
            print("  请输入整数")
    while True:
        try:
            n = int(input("  今日剩余可玩轮数: "))
            if n < 0:
                print("  请输入非负整数")
                continue
            break
        except ValueError:
            print("  请输入整数")
    return r, d, n


def run_interactive():
    """主交互流程"""
    print("=" * 50)
    print("    选剑演武 - 决策选择器")
    print("=" * 50)

    reward_table = input_reward_table()
    remaining_claims, remaining_doubles, remaining_rounds = input_daily_resources()

    print("\n正在计算每日最优策略...")
    V = compute_daily_value(
        remaining_claims, remaining_doubles, remaining_rounds, reward_table
    )
    print("计算完成。")

    while True:
        deck, sum_val, draws = input_game_state()

        if draws == MAX_DRAWS:
            print("\n>>> 已达最大抽牌数(5张)，必须停止。")
            action = "stop"
        elif sum(deck) == 0:
            print("\n>>> 牌库已空，必须停止。")
            action = "stop"
        else:
            action, _ = get_recommendation(deck, sum_val, draws, reward_table)

        current_level = get_reward_level(sum_val)
        current_reward = reward_table[current_level]

        expected_this_round, _ = optimal_value_and_action(
            *deck, sum_val, draws, reward_table
        )

        dist = compute_distribution(*deck, sum_val, draws, reward_table)

        r, d, n = remaining_claims, remaining_doubles, remaining_rounds
        daily_expected = V[r][d][n]

        # 计算领取/翻倍阈值
        threshold_claim, threshold_double = get_claim_thresholds(V, r, d, n)

        print_separator("决策建议")
        print(f"  当前手牌点数之和: {sum_val}")
        print(f"  当前奖励等级: {current_level}")
        print(f"  当前奖励数值: {current_reward:.2f}")
        print(f"  已抽牌数: {draws}/{MAX_DRAWS}")
        print(f"  剩余: 领取{r}次  翻倍{d}次  轮数{n}")
        print()

        if threshold_claim < float('inf'):
            print(f"  领取阈值: 奖励值 >= {threshold_claim:.2f} 时建议领取")
        if threshold_double < float('inf'):
            print(f"  翻倍阈值: 奖励值 >= {threshold_double:.2f} 时建议翻倍")
        print()

        if action == "stop":
            print(f"  >>> 建议: 停止抽牌 <<<")
        else:
            print(f"  >>> 建议: 继续抽牌 <<<")

        if action == "stop" or draws == MAX_DRAWS:
            if remaining_claims > 0 and remaining_rounds > 0:
                claim_decision, use_double = get_claim_decision(
                    current_level, reward_table, V, r, d, n
                )
                if claim_decision == "claim":
                    if use_double:
                        print(f"  >>> 建议: 领取奖励并【使用翻倍】(获得 {2 * current_reward:.2f})")
                    else:
                        print(f"  >>> 建议: 领取奖励（不使用翻倍）(获得 {current_reward:.2f})")
                else:
                    print(f"  >>> 建议: 放弃本次领取（保留领取次数等待更好的机会）")
            elif remaining_claims <= 0:
                print(f"  >>> 无剩余领取次数，无法领取奖励")
            else:
                print(f"  >>> 无剩余轮数，无法继续游戏")
        else:
            print(f"  （仍在抽牌中，领取/翻倍建议在停止后给出）")

        print()
        print(f"  本局期望奖励: {expected_this_round:.2f}")
        print(f"  当日全局期望（含当前局）: {daily_expected:.2f}")
        print()

        print(f"  按此建议，本局最终点数概率分布:")
        print(f"  {'等级':>5}  {'概率':>8}  {'奖励值':>8}  {'柱状图'}")
        max_prob = max(dist) if max(dist) > 0 else 1
        for level in range(11):
            prob = dist[level]
            bar_len = int(prob / max_prob * 30)
            bar = '█' * bar_len
            marker = ' ← 当前' if level == current_level and action == 'stop' else ''
            print(f"  {level:3d}  |  {prob:.4f}  |  {reward_table[level]:8.2f}  |  {bar}{marker}")

        print()

        again = input("是否继续咨询下一局？(y/n，默认y): ").strip().lower()
        if again == 'n':
            print("再见！")
            break
        print()


if __name__ == "__main__":
    run_interactive()
