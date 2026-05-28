#!/usr/bin/env python
# box.py — 精确对齐的框线表格
# 用法: printf "列1\t列2\n值1\t值2\n" | python .claude/skills/rpg-dm/scripts/tools/box.py
#       从 stdin 读取 TSV，输出像素级对齐的框线表

import sys
import unicodedata


def char_width(c):
    """返回字符的显示列数。中文/全角=2，其余=1。"""
    w = unicodedata.east_asian_width(c)
    return 2 if w in ("W", "F") else 1


def str_width(s):
    return sum(char_width(c) for c in s)


def pad(s, width):
    """补空格到 width 列宽。s 已确保 <= width。"""
    need = width - str_width(s)
    if need < 0:
        need = 0
    return s + " " * need


def box(rows, header=True):
    """
    rows: [["约束", "机制"], ["隐性反馈", "..."], ...]
    header: 第一行是否加分隔线
    """
    if not rows:
        return ""

    ncols = len(rows[0])
    # 保证所有行列数一致
    for row in rows:
        if len(row) != ncols:
            raise ValueError(f"列数不一致: 期望 {ncols}, 得到 {len(row)}: {row}")

    # 计算每列宽度（内容 + 两侧各留 1 格）
    col_widths = [0] * ncols
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], str_width(cell) + 2)

    def hline(left, mid, right, fill):
        parts = [fill * w for w in col_widths]
        return left + mid.join(parts) + right

    lines = []
    lines.append(hline("┌", "┬", "┐", "─"))  # ┌┬┐
    for ri, row in enumerate(rows):
        cells = ""
        for i, cell in enumerate(row):
            cells += "│" + pad(" " + cell, col_widths[i])  # │ cell
        cells += "│"
        lines.append(cells)
        if header and ri == 0:
            lines.append(hline("├", "┼", "┤", "─"))  # ├┼┤
    lines.append(hline("└", "┴", "┘", "─"))  # └┴┘
    return "\n".join(lines)


if __name__ == "__main__":
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")

    # 从 stdin 读 TSV
    text = sys.stdin.read()
    if not text.strip():
        print("用法: printf '列1\\t列2\\n值1\\t值2\\n' | python .claude/skills/rpg-dm/scripts/tools/box.py", file=sys.stderr)
        sys.exit(1)

    rows = [line.split("\t") for line in text.strip().splitlines()]
    print(box(rows))
