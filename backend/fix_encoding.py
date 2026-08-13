"""一次性脚本：修复 stock / fund_holding 表中被错误编码的中文名

问题：抓取时把 UTF-8 字节当 Latin-1 解读后又写回 DB，导致 mojibake
修复：db_text → encode latin-1 → decode utf-8
"""
import sqlite3
import sys

DB = "data/fund_analyzer.db"


def fix_text(s: str) -> str:
    if not s:
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    fixed = 0

    # stock.name
    cur.execute("SELECT code, name FROM stock")
    for code, name in cur.fetchall():
        new = fix_text(name)
        if new != name:
            cur.execute("UPDATE stock SET name=? WHERE code=?", (new, code))
            fixed += 1

    # fund_holding.stock_name
    cur.execute("SELECT id, stock_name FROM fund_holding WHERE stock_name IS NOT NULL")
    for hid, sname in cur.fetchall():
        new = fix_text(sname)
        if new != sname:
            cur.execute("UPDATE fund_holding SET stock_name=? WHERE id=?", (new, hid))
            fixed += 1

    # fund.name
    cur.execute("SELECT code, name FROM fund")
    for code, name in cur.fetchall():
        new = fix_text(name)
        if new != name:
            cur.execute("UPDATE fund SET name=? WHERE code=?", (new, code))
            fixed += 1

    conn.commit()
    conn.close()
    print(f"修复 {fixed} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
