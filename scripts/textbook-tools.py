#!/usr/bin/env python3
"""课本 PDF → 知识库原料的工具。配套 SKILL.md「扩充知识库」一节。

三个子命令：

  toc    <课本.pdf>
        打印前几页里有"单元"字样的页面，用来定位单元结构。

  text   <课本.pdf> <输出目录>
        逐页抽文字层，写入 <输出目录>/<文件名>.txt，每页标记成
        ===== PDF页 N | 印刷页 M =====（M 取自页脚，识别不到写 ?）。
        末尾报告印刷页码的真跳变——那是夹进来的广告插页，也是
        「PDF 页码 = 印刷页 + 几」会变的地方。

  render <课本.pdf> <输出目录> [dpi]
        逐页导出 PNG，默认 110dpi（够认字；核对生僻字再单独放大）。
        已存在的页会跳过，中断后可以直接重跑。

例：
  python textbook-tools.py text   "D:/ds/道法/道法/最新【人教版】8年级道法课本•上册.pdf" D:/tmp/kb
  python textbook-tools.py render "D:/ds/道法/道法/最新【人教版】8年级道法课本•上册.pdf" D:/tmp/kb/pages

注意：文字层只能拿来取原句。栏目归属（哪句话在"相关链接"里、哪句是"探究与分享"的设问）
必须打开页面图核对——文字层会把栏目名和内容的顺序打乱。
"""
import re
import sys
import pathlib

import fitz  # PyMuPDF


def _num_from_footer(txt):
    """页脚里那一行形如「6 道德与法治 七年级 上册」或「第一单元 少年有梦 15」，
    页码可能在开头也可能在末尾，两种都要认。"""
    t = ' '.join(txt.split())
    m = re.match(r'^(\d{1,3})\s', t)          # 页码在开头
    if m:
        return int(m.group(1))
    m = re.search(r'(\d{1,3})$', t)           # 页码在末尾
    if m:
        return int(m.group(1))
    return None


def printed_page(page):
    """页脚的印刷页码：取页面底部区域里最靠下的那个文字块。识别不到返回 None。"""
    h = page.rect.height
    blocks = [b for b in page.get_text('blocks')
              if b[6] == 0 and b[4].strip() and b[1] > h * 0.85]
    for b in sorted(blocks, key=lambda b: -b[1]):
        n = _num_from_footer(b[4])
        if n is not None:
            return n
    tail = page.get_text().strip().split('\n')
    tail = [l for l in tail if l.strip()]
    if tail:
        last = tail[-1]
        if '道德与法治' in last or re.match(r'^第[一二三四五六七八九十]+单元', last.strip()):
            return _num_from_footer(last)
    return None


def cmd_toc(pdf):
    d = fitz.open(pdf)
    for i in range(min(8, d.page_count)):
        t = d[i].get_text()
        if '单元' in t and re.search(r'\d', t):
            print(f'--- PDF 第 {i} 页 ---')
            print(t.strip()[:1500])
    d.close()


def cmd_text(pdf, outdir):
    out = pathlib.Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    d = fitz.open(pdf)
    lines = [f'# 课本：{pathlib.Path(pdf).name}',
             '# 每页标题 ===== PDF页 N | 印刷页 M =====；引用句子的页码一律用「印刷页」。',
             '# 页脚识别不到的页写 印刷页 ?（封面/目录/单元页/广告插页）。', '']
    seq = []
    for i in range(d.page_count):
        t = d[i].get_text().strip()
        pp = printed_page(d[i])
        seq.append((i, pp))
        lines.append(f'\n===== PDF页 {i} | 印刷页 {pp if pp else "?"} =====')
        lines.append(t)
    d.close()
    dst = out / (pathlib.Path(pdf).stem + '.txt')
    dst.write_text('\n'.join(lines), encoding='utf-8')
    print(f'写入 {dst}（{len(seq)} 页）')

    # 真跳变：印刷页码的变化量 != PDF 页数差（中间没识别出页码的页不算跳变）
    # 跳过前 6 页（封面和目录，目录里也印着一堆数字，会误报）
    known = [(i, p) for i, p in seq if p is not None and i >= 6]
    for (i1, p1), (i2, p2) in zip(known, known[1:]):
        if p2 - p1 != i2 - i1:
            print(f'  页码跳变：PDF {i1}=印刷页 {p1}，PDF {i2}=印刷页 {p2}'
                  f'（中间 {i2 - i1 - 1} 页）—— 多半夹了广告插页，'
                  f'「PDF 页码 = 印刷页 + k」的 k 从这里往后会变。')
    miss = [i for i, p in seq if p is None]
    if miss:
        print(f'  {len(miss)} 页没有识别到页脚页码（封面/目录/单元页/广告页/空白页）：{miss[:20]}')


def cmd_render(pdf, outdir, dpi=110):
    out = pathlib.Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    d = fitz.open(pdf)
    n = 0
    for i in range(d.page_count):
        p = out / f'p{i:03d}.png'
        if p.exists():
            continue
        d[i].get_pixmap(dpi=int(dpi)).save(p)
        n += 1
    total = d.page_count
    d.close()
    print(f'导出 {n} 张 PNG 到 {out}（本册共 {total} 页）')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    cmd, rest = sys.argv[1], sys.argv[2:]
    if cmd == 'toc':
        cmd_toc(rest[0])
    elif cmd == 'text':
        cmd_text(rest[0], rest[1])
    elif cmd == 'render':
        cmd_render(rest[0], rest[1], rest[2] if len(rest) > 2 else 110)
    else:
        print(__doc__)
        sys.exit(1)
