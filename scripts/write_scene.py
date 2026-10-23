"""按你给的一小段细纲，写一小段正文。

设计原则：
  - 一次调用 = 一个节点 = 一小段。不要让它一次写一整场。
  - 字数按细纲节点数自动估算（可 --words 覆盖），不给它注水的空间。
  - 文风可以用 --style-ref 指一份已确认的句子，让它照着语气写。
  - 工具本身不加预设约束。

用法:
  python write_scene.py --check
  python write_scene.py -r "他醒来，发现自己睡在一个陌生的地方，手和衣裳都不是自己的"
  python write_scene.py -r 节点.txt --context 设定.md --style-ref 文风参考.txt -o s1.txt
  python write_scene.py --per-node 细纲.txt --context 设定.md --style-ref 文风参考.txt -o 全章.txt
  python write_scene.py --from-file 稿.txt --expand 1
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sf_client  # noqa: E402

DEFAULT_MODEL = "Qwen/Qwen2.5-72B-Instruct"

SYSTEM_PROMPT = "你是一名中文小说写手。按下面的要求写小说正文。只输出正文，不要标题、不要说明。"

# 每个细纲节点大致对应的字数。宁可写短，也别给它注水的余地。
WORDS_PER_BEAT = 150
WORDS_MIN, WORDS_MAX = 150, 600


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load(text=None, path=None):
    if path:
        return read(path)
    return text or ""


def clean(text):
    """去掉 `#` 开头的注释行。"""
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    return "\n".join(lines).strip()


def strip_wrapping(text):
    t = (text or "").strip()
    t = re.sub(r"^```[a-zA-Z]*\s*\n", "", t)
    t = re.sub(r"\n```\s*$", "", t)
    return t.strip()


def char_count(text):
    return len(re.sub(r"\s", "", text))


def trim_dup(seg, prev):
    """逐节点串写时，砍掉开头那些已经在上文出现过的句子。"""
    if not prev:
        return seg
    sents = [x for x in re.split(r"(?<=[。！？…])", seg)]
    i = 0
    while i < len(sents):
        s = sents[i].strip()
        if not s:
            i += 1
            continue
        if len(s) >= 6 and s[:10] in prev:
            i += 1
            continue
        break
    out = "".join(sents[i:]).strip()
    return out or seg


def split_nodes(text):
    """把细纲拆成节点：优先按行，退而按句号。"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) <= 1:
        lines = [s.strip() for s in re.split(r"[。！？；]", text) if s.strip()]
    return lines


def estimate_words(text):
    """按节点数估算这一小段该多长。"""
    n = max(1, len(split_nodes(text)))
    return max(WORDS_MIN, min(WORDS_MAX, n * WORDS_PER_BEAT))


def build_messages(args, node_text, prev_text=""):
    parts = []

    if args.context_text:
        parts.append("【设定】\n" + args.context_text.strip())
    if args.style_ref_text:
        parts.append(
            "【文风参考：下面这些句子的语气、句长和描写密度，就是我要的感觉。"
            "照着写，不要抄它的内容】\n" + args.style_ref_text.strip()
        )
    if prev_text and prev_text.strip():
        tail = prev_text.strip()
        if len(tail) > 1200:
            tail = "……" + tail[-1200:]
        parts.append("【上文，接着往下写，不要重复】\n" + tail)
    if node_text.strip():
        parts.append("【要写的这一段】\n" + node_text.strip())

    how = []
    if args.style:
        how.append(args.style)
    if args.words:
        how.append(f"约 {args.words} 字")
    if args.pov:
        how.append(args.pov)
    if args.notes:
        how.append(args.notes)
    if how:
        parts.append("【写法】" + "。".join(how))

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def cmd_check():
    sf_client.reconfigure_stdout()
    key = os.environ.get("SILICONFLOW_API_KEY", "")
    print("环境变量 SILICONFLOW_API_KEY:", "已设置" if key else "未设置")
    if not key:
        print(sf_client.get_api_key.__doc__ or "请先设置 SILICONFLOW_API_KEY")
        return 1
    try:
        models = sf_client.list_models()
    except sf_client.ApiError as e:
        print("鉴权失败:", e)
        return 1
    print(f"鉴权成功，可用 chat 模型 {len(models)} 个")
    print(f"默认模型 {DEFAULT_MODEL}:", "在列表中" if DEFAULT_MODEL in models else "不在列表中")
    return 0


def main():
    sf_client.reconfigure_stdout()
    p = argparse.ArgumentParser(
        description="按一小段细纲写一小段正文。字数按节点数自动估算。"
    )

    src = p.add_argument_group("写什么（给一项）")
    src.add_argument("-r", "--request", nargs="?", const="", metavar="TEXT",
                     help="这一段要写什么；不带值时读 --request-file")
    src.add_argument("--request-file", dest="request_file", metavar="PATH")
    src.add_argument("--outline", nargs="?", const="", metavar="TEXT",
                     help="细纲（少量，一个节点最好）")
    src.add_argument("--outline-file", dest="outline_file", metavar="PATH")
    src.add_argument("--per-node", dest="per_node", metavar="PATH",
                     help="逐节点模式：把细纲文件一行一个节点，逐个调用、逐段串起来")

    ctx = p.add_argument_group("上下文（可选）")
    ctx.add_argument("--context", metavar="PATH", help="设定文件：人物 / 世界观 / 前情")
    ctx.add_argument("--continue-file", dest="continue_file", metavar="PATH",
                     help="紧接其后的已有正文")
    ctx.add_argument("--style-ref", dest="style_ref", metavar="PATH",
                     help="文风参考：已确认的句子，让它照着语气写")

    how = p.add_argument_group("写法（可选，原样透传）")
    how.add_argument("--style", help="文风描述，你自己的话")
    how.add_argument("--words", type=int, help="字数；不给则按节点数自动估算")
    how.add_argument("--pov", help="视角")
    how.add_argument("--notes", help="其他补充")

    out = p.add_argument_group("输出")
    out.add_argument("-o", "--out", metavar="PATH", help="输出文件（UTF-8）")
    out.add_argument("--stream", action="store_true", help="流式输出（逐节点模式不支持）")
    out.add_argument("--from-file", dest="from_file", metavar="PATH",
                     help="载入已有正文，跳过生成（配合 --expand）")
    out.add_argument("--expand", type=int, default=0, metavar="N",
                     help="原地加厚：把最短的 N 段写得更厚")

    mdl = p.add_argument_group("模型参数")
    mdl.add_argument("--model", default=DEFAULT_MODEL)
    mdl.add_argument("--temperature", type=float, default=0.85)
    mdl.add_argument("--top-p", dest="top_p", type=float, default=0.9)
    mdl.add_argument("--top-k", dest="top_k", type=int, default=50)
    mdl.add_argument("--freq-penalty", dest="freq_penalty", type=float, default=0.3)
    mdl.add_argument("--stop", help="停止串，多个用 | 分隔")
    mdl.add_argument("--seed", type=int)
    mdl.add_argument("--trace-id", dest="trace_id")
    mdl.add_argument("--check", action="store_true", help="只检查环境变量与鉴权")

    args = p.parse_args()

    if args.check:
        return cmd_check()

    args.request_text = clean(load(args.request, args.request_file))
    args.outline_text = clean(load(args.outline, args.outline_file))
    args.context_text = clean(load(None, args.context)) if args.context else ""
    args.style_ref_text = clean(load(None, args.style_ref)) if args.style_ref else ""
    args.prev_start = load(None, args.continue_file) if args.continue_file else ""

    if not any([args.request_text, args.outline_text, args.per_node, args.from_file]):
        p.error("至少要给 -r / --outline / --per-node / --from-file 之一")

    node_text = args.request_text or args.outline_text
    if not args.words:
        args.words = estimate_words(node_text or "一句话")
        print(f"[篇幅] 按 {len(split_nodes(node_text or 'x'))} 个节点估 {args.words} 字"
              f"（--words 可覆盖）", file=sys.stderr)

    base_kwargs = dict(
        model=args.model,
        temperature=args.temperature,
        top_p=args.top_p,
        max_tokens=max(600, int(args.words * 2.4) + 300),
        frequency_penalty=args.freq_penalty,
        top_k=args.top_k,
        stop=[s for s in args.stop.split("|") if s] if args.stop else None,
        trace_id=args.trace_id,
    )
    if args.seed is not None:
        base_kwargs["seed"] = args.seed

    # ---------- 载入已有稿 / 逐节点 / 单次 ----------
    if args.from_file:
        text = strip_wrapping(read(args.from_file))
        print(f"[载入] {args.from_file}（{char_count(text)} 字），跳过生成", file=sys.stderr)

    elif args.per_node:
        nodes = split_nodes(clean(read(args.per_node)))
        print(f"[逐节点] 共 {len(nodes)} 个节点，逐个调用", file=sys.stderr)
        written = args.prev_start
        chunks = []
        for i, node in enumerate(nodes, 1):
            w = args.words if args.words else max(WORDS_MIN, WORDS_PER_BEAT)
            kw = dict(base_kwargs, max_tokens=max(600, int(w * 2.4) + 300))
            print(f"  [{i}/{len(nodes)}] {node[:36]}…  约 {w} 字", file=sys.stderr)
            try:
                seg, _fin, _u = sf_client.chat(
                    messages=build_messages(args, node, written), **kw)
            except sf_client.ApiError as e:
                print(f"  节点 {i} 失败，中止：", e, file=sys.stderr)
                break
            seg = strip_wrapping(seg)
            raw = char_count(seg)
            seg = trim_dup(seg, written)
            if not seg:
                print("      → 整段与上文重复，丢弃", file=sys.stderr)
                continue
            if raw - char_count(seg) > 20:
                print(f"      → 去掉重复开头 {raw - char_count(seg)} 字", file=sys.stderr)
            chunks.append(seg)
            written = written.rstrip() + "\n\n" + seg if written else seg
            print(f"      → {char_count(seg)} 字", file=sys.stderr)
        text = "\n\n".join(chunks)
        if not text.strip():
            print("没有产出", file=sys.stderr)
            return 1

    else:
        try:
            if args.stream:
                buf = []
                for delta in sf_client.chat_stream(messages=build_messages(
                        args, node_text, args.prev_start), **base_kwargs):
                    buf.append(delta)
                    sys.stdout.write(delta)
                    sys.stdout.flush()
                sys.stdout.write("\n")
                text = strip_wrapping("".join(buf))
            else:
                text, finish, usage = sf_client.chat(
                    messages=build_messages(args, node_text, args.prev_start), **base_kwargs)
                text = strip_wrapping(text)
                if not args.out:
                    print(text)
                if finish == "length":
                    print("[注意] 被 max_tokens 截断，减少 --words", file=sys.stderr)
                if usage:
                    print(f"[用量] prompt={usage.get('prompt_tokens')} "
                          f"completion={usage.get('completion_tokens')}", file=sys.stderr)
        except sf_client.ApiError as e:
            print("API 错误:", e, file=sys.stderr)
            return 1

    # ---------- 原地加厚：只重写某几段 ----------
    if args.expand:
        paras = [p for p in text.split("\n\n") if p.strip()]
        order = sorted(range(len(paras)), key=lambda i: char_count(paras[i]))
        targets = [i for i in order if char_count(paras[i]) >= 40][: args.expand]
        for n, idx in enumerate(targets, 1):
            orig = paras[idx]
            want = int(char_count(orig) * 1.5)
            print(f"[加厚 {n}/{len(targets)}] 第 {idx + 1} 段 "
                  f"{char_count(orig)} → 约 {want} 字", file=sys.stderr)
            msgs = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": (
                    f"【全文】\n{text}\n\n【要重写的段落】\n<<<\n{orig}\n>>>\n\n"
                    f"把 <<< >>> 这一段写得更厚，约 {want} 字。"
                    "事件、顺序、结尾位置不变，不把下一段内容写进来。"
                    "其他段落不要输出。"
                )},
            ]
            try:
                new_p, _f, _u = sf_client.chat(messages=msgs, **base_kwargs)
            except sf_client.ApiError as e:
                print("  加厚失败，保留原段:", e, file=sys.stderr)
                break
            new_p = strip_wrapping(new_p).replace("<<<", "").replace(">>>", "").strip()
            new_p = re.sub(r"\s*[A-Za-z][A-Za-z']*\s*", "", new_p)
            if idx + 1 < len(paras):
                head = paras[idx + 1].strip()[:10]
                pos = new_p.find(head) if head else -1
                if pos > len(new_p) * 0.3:
                    cut = new_p[:pos].rstrip("，,、 \n")
                    if cut and cut[-1] not in "。！？…'\"”：；":
                        cut += "。"
                    print("  去重：截掉吞进来的下一段开头", file=sys.stderr)
                    new_p = cut
            n_new, n_old = char_count(new_p), char_count(orig)
            if n_new < n_old * 1.1:
                print(f"  丢弃：只有 {n_new} 字，没比原段长", file=sys.stderr)
                continue
            if n_new > n_old * 3.0:
                print(f"  丢弃：{n_new} 字，疑似把全文吐回来了", file=sys.stderr)
                continue
            paras[idx] = new_p
            text = "\n\n".join(paras)
            print(f"  采用：{n_old} → {n_new} 字（全文 {char_count(text)} 字）", file=sys.stderr)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"[已写入] {args.out}  ({char_count(text)} 字)", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
