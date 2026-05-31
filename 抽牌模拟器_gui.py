"""
选剑演武 - 决策选择器 - 图形化界面
==============================
基于 tkinter/ttk 的美观 GUI，调用抽牌模拟器核心逻辑。
"""

import tkinter as tk
from tkinter import ttk, messagebox
from collections import Counter
from typing import Tuple

# 导入核心逻辑
from 抽牌模拟器 import (
    INITIAL_DECK, CARD_VALUES, MAX_DRAWS,
    get_reward_level, get_recommendation,
    optimal_value_and_action, compute_distribution,
    compute_daily_value, get_claim_decision, get_claim_thresholds,
)

# ============================================================
# 颜色与样式常量
# ============================================================
COLOR_BG = "#f0f2f5"
COLOR_CARD = "#ffffff"
COLOR_PRIMARY = "#4a90d9"
COLOR_SUCCESS = "#27ae60"
COLOR_WARNING = "#e67e22"
COLOR_DANGER = "#e74c3c"
COLOR_TEXT = "#2c3e50"
COLOR_TEXT_SECONDARY = "#7f8c8d"
COLOR_ACCENT = "#8e44ad"
COLOR_GOLD = "#f39c12"
COLOR_BAR = "#3498db"
COLOR_BAR_CURRENT = "#e74c3c"

FONT_TITLE = ("Microsoft YaHei UI", 16, "bold")
FONT_HEADING = ("Microsoft YaHei UI", 12, "bold")
FONT_BODY = ("Microsoft YaHei UI", 10)
FONT_MONO = ("Consolas", 10)
FONT_BIG = ("Microsoft YaHei UI", 18, "bold")
FONT_RESULT = ("Microsoft YaHei UI", 14, "bold")


class CardDecisionApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("选剑演武 - 决策选择器")
        self.root.geometry("960x680")
        self.root.minsize(860, 600)
        self.root.configure(bg=COLOR_BG)

        # 状态变量
        self.reward_vars = [tk.StringVar(value=str(v)) for v in
                            (0, 5, 15, 30, 50, 80, 120, 180, 250, 350, 500)]
        self.claims_var = tk.StringVar(value="5")
        self.doubles_var = tk.StringVar(value="2")
        self.rounds_var = tk.StringVar(value="10")

        self.hand_cards = []  # 当前手牌列表
        self.V = None  # 每日DP表
        self.reward_table = None
        self._strategy_dirty = False  # 参数是否变更过

        # 设置样式
        self._setup_styles()
        # 构建界面
        self._build_ui()
        # 初始计算
        self._on_update_strategy()

    # ----- 样式设置 -----
    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Title.TLabel", font=FONT_TITLE, background=COLOR_BG,
                        foreground=COLOR_TEXT)
        style.configure("Heading.TLabel", font=FONT_HEADING, background=COLOR_BG,
                        foreground=COLOR_TEXT)
        style.configure("Body.TLabel", font=FONT_BODY, background=COLOR_BG,
                        foreground=COLOR_TEXT)
        style.configure("Mono.TLabel", font=FONT_MONO, background=COLOR_BG)
        style.configure("Big.TLabel", font=FONT_BIG, background=COLOR_BG)
        style.configure("Result.TLabel", font=FONT_RESULT, background=COLOR_BG)

        style.configure("Card.TButton", font=FONT_BODY, padding=6)
        style.configure("Primary.TButton", font=FONT_BODY)
        style.configure("Success.TButton", font=FONT_BODY)

        style.configure("Panel.TFrame", background=COLOR_CARD, relief="solid",
                        borderwidth=1)
        style.configure("BG.TFrame", background=COLOR_BG)

        # Entry 样式
        style.configure("TEntry", font=FONT_BODY, padding=4)

    # ----- 界面构建 -----
    def _build_ui(self):
        # 顶部标题栏
        header = ttk.Frame(self.root, style="BG.TFrame")
        header.pack(fill=tk.X, padx=20, pady=(15, 5))
        ttk.Label(header, text="⚔  选剑演武 - 决策选择器", style="Title.TLabel").pack(
            side=tk.LEFT)

        # 主容器：左右面板
        main = ttk.Frame(self.root, style="BG.TFrame")
        main.pack(fill=tk.BOTH, expand=True, padx=15, pady=(5, 15))
        main.columnconfigure(0, weight=0)  # 左面板固定宽度
        main.columnconfigure(1, weight=1)  # 右面板扩展
        main.rowconfigure(0, weight=1)

        # 左侧面板
        left = ttk.Frame(main, style="Panel.TFrame", padding=15)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 8))
        self._build_left_panel(left)

        # 右侧面板
        right = ttk.Frame(main, style="Panel.TFrame", padding=15)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=0)
        right.rowconfigure(1, weight=1)
        self._build_right_panel(right)

    def _build_left_panel(self, parent: ttk.Frame):
        """左侧：参数设置"""
        ttk.Label(parent, text="⚙  参数设置", style="Heading.TLabel").pack(
            anchor=tk.W, pady=(0, 10))

        # ---- 奖励数值 ----
        reward_frame = ttk.LabelFrame(parent, text="奖励数值（点数 → 奖励）", padding=10)
        reward_frame.pack(fill=tk.X, pady=(0, 10))

        grid = ttk.Frame(reward_frame)
        grid.pack()
        for i in range(11):
            row, col = divmod(i, 4)
            cell = ttk.Frame(grid)
            cell.grid(row=row, column=col, padx=4, pady=3, sticky="w")
            ttk.Label(cell, text=f"点数{i:2d}", style="Body.TLabel",
                      width=5).pack(side=tk.LEFT)
            entry = ttk.Entry(cell, textvariable=self.reward_vars[i],
                              width=8, font=FONT_BODY)
            entry.pack(side=tk.LEFT, padx=(3, 0))

            # 实时更新
            self.reward_vars[i].trace_add("write",
                                          lambda *a: self._on_reward_change())

        # ---- 每日资源 ----
        res_frame = ttk.LabelFrame(parent, text="每日资源", padding=10)
        res_frame.pack(fill=tk.X, pady=(0, 10))

        fields = [
            ("剩余领取次数:", self.claims_var),
            ("剩余翻倍次数:", self.doubles_var),
            ("剩余可玩轮数:", self.rounds_var),
        ]
        for i, (label, var) in enumerate(fields):
            row = ttk.Frame(res_frame)
            row.pack(fill=tk.X, pady=3)
            ttk.Label(row, text=label, style="Body.TLabel", width=14).pack(
                side=tk.LEFT)
            spin = ttk.Spinbox(row, textvariable=var, from_=0, to=999,
                               width=8, font=FONT_BODY)
            spin.pack(side=tk.LEFT)
            var.trace_add("write", lambda *a: self._on_reward_change())

        # 更新按钮
        self.update_btn = ttk.Button(parent, text="🔄 更新策略计算",
                                     style="Primary.TButton",
                                     command=self._on_update_strategy)
        self.update_btn.pack(fill=tk.X, pady=(5, 0))

        # 阈值显示
        self.threshold_label = ttk.Label(parent, text="", style="Body.TLabel",
                                         foreground=COLOR_TEXT_SECONDARY)
        self.threshold_label.pack(fill=tk.X, pady=(10, 0))

    def _build_right_panel(self, parent: ttk.Frame):
        """右侧：手牌输入 + 决策结果"""
        # ---- 手牌输入区 ----
        hand_frame = ttk.LabelFrame(parent, text="🎯 当前手牌", padding=10)
        hand_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        # 上方：按钮 + 状态
        top_row = ttk.Frame(hand_frame)
        top_row.pack(fill=tk.X)

        # 牌按钮 1-5
        btn_frame = ttk.Frame(top_row)
        btn_frame.pack(side=tk.LEFT)
        ttk.Label(btn_frame, text="添加牌:", style="Body.TLabel").pack(
            side=tk.LEFT, padx=(0, 5))
        for val in CARD_VALUES:
            btn = ttk.Button(btn_frame, text=str(val), style="Card.TButton",
                             width=3,
                             command=lambda v=val: self._add_card(v))
            btn.pack(side=tk.LEFT, padx=2)

        ttk.Button(top_row, text="✕ 清空", width=6,
                   command=self._clear_hand).pack(side=tk.LEFT, padx=(8, 15))

        ttk.Button(top_row, text="↩ 撤销", width=6,
                   command=self._undo_card).pack(side=tk.LEFT)

        # 手牌显示
        self.hand_display = ttk.Label(top_row, text="手牌: (空)",
                                      style="Result.TLabel",
                                      foreground=COLOR_PRIMARY)
        self.hand_display.pack(side=tk.LEFT, padx=(20, 0))

        # 当前状态行
        self.state_frame = ttk.Frame(hand_frame)
        self.state_frame.pack(fill=tk.X, pady=(8, 0))
        self.state_label = ttk.Label(self.state_frame, text="",
                                     style="Body.TLabel")
        self.state_label.pack()

        # ---- 建议区 ----
        rec_frame = ttk.LabelFrame(parent, text="💡 决策建议", padding=10)
        rec_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        rec_frame.columnconfigure(0, weight=1)

        self.rec_draw_label = ttk.Label(rec_frame, text="", style="Big.TLabel",
                                        anchor=tk.CENTER)
        self.rec_draw_label.grid(row=0, column=0, sticky="ew", pady=(0, 5))

        self.rec_claim_label = ttk.Label(rec_frame, text="", style="Result.TLabel",
                                         anchor=tk.CENTER)
        self.rec_claim_label.grid(row=1, column=0, sticky="ew")

        # ---- 数值区 ----
        value_frame = ttk.Frame(parent)
        value_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        value_frame.columnconfigure(0, weight=1)
        value_frame.columnconfigure(1, weight=1)

        round_frame = ttk.Frame(value_frame)
        round_frame.grid(row=0, column=0, sticky="w")
        ttk.Label(round_frame, text="本局期望奖励:", style="Body.TLabel",
                  foreground=COLOR_TEXT_SECONDARY).pack(side=tk.LEFT)
        self.expected_round_label = ttk.Label(
            round_frame, text="--", style="Result.TLabel", foreground=COLOR_PRIMARY)
        self.expected_round_label.pack(side=tk.LEFT, padx=(5, 0))

        daily_frame = ttk.Frame(value_frame)
        daily_frame.grid(row=0, column=1, sticky="e")
        ttk.Label(daily_frame, text="当日全局期望:", style="Body.TLabel",
                  foreground=COLOR_TEXT_SECONDARY).pack(side=tk.LEFT)
        self.expected_daily_label = ttk.Label(
            daily_frame, text="--", style="Result.TLabel", foreground=COLOR_ACCENT)
        self.expected_daily_label.pack(side=tk.LEFT, padx=(5, 0))

        # ---- 概率分布图 ----
        dist_frame = ttk.LabelFrame(parent, text="📊 本局最终点数概率分布", padding=10)
        dist_frame.grid(row=3, column=0, sticky="nsew")
        dist_frame.rowconfigure(0, weight=1)
        dist_frame.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)

        self.dist_canvas = tk.Canvas(dist_frame, height=230, bg=COLOR_CARD,
                                     highlightthickness=0)
        self.dist_canvas.grid(row=0, column=0, sticky="nsew")
        # 绑定resize事件
        self.dist_canvas.bind("<Configure>", lambda e: self._draw_distribution())

    # ----- 事件处理 -----
    def _add_card(self, val: int):
        if len(self.hand_cards) >= MAX_DRAWS:
            messagebox.showinfo("提示", f"最多只能抽 {MAX_DRAWS} 张牌")
            return
        # 检查牌库上限
        cnt = Counter(self.hand_cards)
        initial = dict(zip(CARD_VALUES, INITIAL_DECK))
        if cnt.get(val, 0) >= initial[val]:
            messagebox.showinfo("提示", f"点数为 {val} 的牌只有 {initial[val]} 张")
            return
        self.hand_cards.append(val)
        self._refresh_hand()

    def _undo_card(self):
        if self.hand_cards:
            self.hand_cards.pop()
            self._refresh_hand()

    def _clear_hand(self):
        self.hand_cards.clear()
        self._refresh_hand()

    def _refresh_hand(self):
        """更新手牌显示和决策"""
        if not self.hand_cards:
            self.hand_display.config(text="手牌: (空)", foreground=COLOR_PRIMARY)
        else:
            cards_str = " + ".join(str(c) for c in self.hand_cards)
            self.hand_display.config(
                text=f"手牌: {cards_str}",
                foreground=COLOR_PRIMARY)

        # 计算状态
        deck = list(INITIAL_DECK)
        cnt = Counter(self.hand_cards)
        for i, v in enumerate(CARD_VALUES):
            deck[i] -= cnt.get(v, 0)
        deck = tuple(deck)
        sum_val = sum(self.hand_cards)
        draws = len(self.hand_cards)

        level = get_reward_level(sum_val)
        if self.reward_table:
            current_reward = self.reward_table[level]
        else:
            current_reward = 0

        self.state_label.config(
            text=f"点数之和: {sum_val}   |   奖励等级: Lv.{level}   |   当前奖励: {current_reward:.0f}   |   已抽: {draws}/{MAX_DRAWS}")

        # 更新决策
        self._update_decisions(deck, sum_val, draws)

    def _on_reward_change(self):
        """奖励表或资源变化时标记需要重新计算"""
        if not self._strategy_dirty:
            self._strategy_dirty = True
            self.update_btn.config(text="🔄 更新策略计算 ◀ 需更新")

    def _on_update_strategy(self):
        """重新计算每日策略"""
        try:
            self.reward_table = tuple(
                float(v.get()) for v in self.reward_vars)
            r = int(self.claims_var.get())
            d = int(self.doubles_var.get())
            n = int(self.rounds_var.get())
        except ValueError:
            messagebox.showerror("输入错误", "请确保所有输入都是有效数字")
            return

        if r < 0 or d < 0 or n < 0:
            messagebox.showerror("输入错误", "资源数量不能为负")
            return

        self.V = compute_daily_value(r, d, n, self.reward_table)
        self._strategy_dirty = False
        self.update_btn.config(text="🔄 更新策略计算")

        # 更新阈值显示
        tc, td = get_claim_thresholds(self.V, r, d, n)
        lines = []
        if tc < float('inf'):
            lines.append(f"领取阈值: 奖励值 ≥ {tc:.1f}")
        if td < float('inf'):
            lines.append(f"翻倍阈值: 奖励值 ≥ {td:.1f}")
        self.threshold_label.config(text="\n".join(lines))

        # 刷新当前手牌决策
        self._refresh_hand()

    def _update_decisions(self, deck: Tuple[int, ...], sum_val: int,
                          draws: int):
        """根据当前状态更新所有决策显示"""
        if self.V is None or self.reward_table is None:
            return

        r = int(self.claims_var.get())
        d = int(self.doubles_var.get())
        n = int(self.rounds_var.get())

        # --- 抽牌建议 ---
        if draws >= MAX_DRAWS:
            action = "stop"
        elif sum(deck) == 0:
            action = "stop"
        else:
            action, _ = get_recommendation(deck, sum_val, draws,
                                           self.reward_table)

        # --- 本局期望 ---
        exp_val, _ = optimal_value_and_action(
            *deck, sum_val, draws, self.reward_table)

        # --- 每日全局期望 ---
        daily_exp = self.V[r][d][n]

        # --- 概率分布 ---
        self._current_dist = compute_distribution(
            *deck, sum_val, draws, self.reward_table)
        self._current_level = get_reward_level(sum_val)
        self._current_action = action

        # --- 显示抽牌建议 ---
        if action == "stop":
            self.rec_draw_label.config(
                text="✋  建议：停止抽牌", foreground=COLOR_DANGER)
        else:
            self.rec_draw_label.config(
                text="👉  建议：继续抽牌", foreground=COLOR_SUCCESS)

        # --- 显示领取/翻倍建议 ---
        if action == "stop" or draws >= MAX_DRAWS:
            level = self._current_level
            if r > 0 and n > 0:
                dec, use_double = get_claim_decision(
                    level, self.reward_table, self.V, r, d, n)
                if dec == "claim":
                    reward = self.reward_table[level]
                    if use_double:
                        self.rec_claim_label.config(
                            text=f"🎁 领取奖励并【翻倍】→ 获得 {2 * reward:.0f}",
                            foreground=COLOR_GOLD)
                    else:
                        self.rec_claim_label.config(
                            text=f"🎁 领取奖励 → 获得 {reward:.0f}",
                            foreground=COLOR_SUCCESS)
                else:
                    self.rec_claim_label.config(
                        text="⏭  建议放弃，等待更好的机会",
                        foreground=COLOR_TEXT_SECONDARY)
            elif r <= 0:
                self.rec_claim_label.config(
                    text="❌ 无剩余领取次数", foreground=COLOR_DANGER)
            else:
                self.rec_claim_label.config(
                    text="❌ 无剩余轮数", foreground=COLOR_DANGER)
        else:
            self.rec_claim_label.config(
                text="（停止抽牌后显示领取建议）",
                foreground=COLOR_TEXT_SECONDARY)

        # --- 期望值 ---
        self.expected_round_label.config(text=f"{exp_val:.1f}")
        self.expected_daily_label.config(text=f"{daily_exp:.1f}")

        # --- 分布图 ---
        self._draw_distribution()

    def _draw_distribution(self):
        """在Canvas上绘制概率分布柱状图"""
        canvas = self.dist_canvas
        canvas.delete("all")

        if not hasattr(self, '_current_dist') or self._current_dist is None:
            return

        dist = self._current_dist
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 50 or h < 50:
            return

        # 布局参数
        margin_left = 45
        margin_right = 80
        margin_top = 15
        margin_bottom = 25
        bar_area_w = w - margin_left - margin_right
        bar_area_h = h - margin_top - margin_bottom
        n_bars = 11
        bar_gap = 4
        bar_w = (bar_area_w - bar_gap * (n_bars + 1)) / n_bars

        max_prob = max(dist) if max(dist) > 0 else 1

        # 奖励表（用于标注）
        rt = self.reward_table if self.reward_table else tuple(
            range(11))

        for i in range(11):
            x0 = margin_left + bar_gap + i * (bar_w + bar_gap)
            x1 = x0 + bar_w

            prob = dist[i]
            bar_h = (prob / max_prob) * bar_area_h if max_prob > 0 else 0

            y0 = margin_top + bar_area_h - bar_h
            y1 = margin_top + bar_area_h

            # 颜色
            is_current = (hasattr(self, '_current_level') and
                          i == self._current_level and
                          hasattr(self, '_current_action') and
                          self._current_action == "stop")
            color = COLOR_BAR_CURRENT if is_current else COLOR_BAR

            # 绘制柱状
            canvas.create_rectangle(x0, y0, x1, y1, fill=color,
                                    outline="", width=0,
                                    tags=("bar",))

            # 概率标签
            canvas.create_text((x0 + x1) / 2, y0 - 8,
                               text=f"{prob:.1%}" if prob >= 0.05 else "",
                               font=("Consolas", 8), fill=COLOR_TEXT,
                               anchor=tk.S)

            # X轴标签（等级）
            canvas.create_text((x0 + x1) / 2, y1 + 12,
                               text=f"L{i}", font=("Consolas", 8),
                               fill=COLOR_TEXT_SECONDARY, anchor=tk.N)

            # 奖励值标注（在柱状右侧显示前几名的奖励值）
            if prob > 0.02:
                canvas.create_text(x1 + 5, (y0 + y1) / 2,
                                   text=f"{rt[i]:.0f}",
                                   font=("Consolas", 8),
                                   fill=COLOR_TEXT_SECONDARY,
                                   anchor=tk.W)

            # 如果当前等级高亮，画星标
            if is_current and prob > 0:
                canvas.create_text((x0 + x1) / 2, y0 - 18,
                                   text="▼", font=("Consolas", 10),
                                   fill=COLOR_BAR_CURRENT, anchor=tk.S)

        # 底座线
        canvas.create_line(margin_left, margin_top + bar_area_h,
                           margin_left + bar_area_w, margin_top + bar_area_h,
                           fill=COLOR_TEXT_SECONDARY, width=1)


def main():
    root = tk.Tk()
    app = CardDecisionApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
