"""把【细纲】扩写成完整的【小说段落】—— 只做"描写"，不做剧情规划。

模型固定为 Qwen/Qwen2.5-72B-Instruct（描写能力强，但不会规划剧情，
所以必须在已有细纲的前提下使用）。

示例:
  python write_scene.py --check
  python write_scene.py --outline "她把信烧了。火光照亮她的脸。她没有哭。" --words 800
  python write_scene.py --outline-file scene3.txt --context 设定.md --style 冷峻 --words 1200 -o out.txt
  python write_scene.py --outline-file scene3.txt --continue-file 前文.txt --style 细腻 --stream
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sf_client  # noqa: E402

DEFAULT_MODEL = "Qwen/Qwen2.5-72B-Instruct"

STYLES = {
    "default": "细腻写实，有质感，多用具体物件与动作承载情绪，避免形容词堆砌",
    "细腻": "极细腻，重视感官细节（触感、气味、光线、温度）与人物微表情，节奏放缓",
    "冷峻": "克制、冷硬、短句为主，不解释情绪，只呈现动作与物象，留白多",
    "古风": "中文古典白话笔法，用词典雅不堆砌，画面感强，避免现代语汇",
    "热烈": "情绪浓度高，语言有张力与韵律，长句与短句交错，适合高潮/爆发场面",
    "悬疑": "阴冷、压抑，善用不可靠细节与环境噪音，信息给一半留一半",
    "温柔": "柔软缓慢，暖色光线，日常细节放大，适合情感/治愈桥段",
    "暴力": "直接、粗粝、短促、血腥但不猎奇，强调身体感受与失序感",
    "对话": "以对话推进，对话有潜台词与打断，动作提示简短，不写长段抒情",
    "动作": "快门式节奏，短句、动词密集，空间关系清晰，强调身体的重量与惯性",
}

SYSTEM_PROMPT = """你是一名顶尖的中文小说写手，唯一的工作是【把已有的细纲扩写成成稿段落】。

职责边界（必须严格遵守）：
1. 细纲里已经写明的剧情、人物、动作、因果、结局，全部保留，不得改写、不得增删剧情走向。
2. 细纲没写的东西，你只能补充**感官细节、动作过程、环境氛围、人物生理反应、对话的语气与停顿**。
3. 严禁新增：新的情节转折、新的人物、新的线索、新的因果解释、新的决策与动机。如果细纲到这里就结束，你就停在细纲结束的地方，可以停在意象或动作上，不许自己"往前推剧情"。
4. 严禁输出大纲、分章、剧情建议、"可以这样改"之类的分析。只输出小说正文。
5. 人称与称谓严格跟随【上下文】；上下文未给出时默认第三人称限知视角。
6. 不写"总结""本章讲述""（未完待续）"这类元话语；不写标题（除非明确要求）。
7. 直接输出正文，不要任何前言、解释、Markdown 代码块围栏。"""


def length_brief(words):
    """篇幅只是一个参考提示，不作为验收标准。"""
    if not words:
        return []
    paras = max(2, round(words / 170))
    return [
        f"- 参考篇幅：约 {words} 字（约 {paras} 个自然段）。这是参考不是指标："
        "写完细纲就停，**不得为了凑字数而重复、拉长或加无意义的抒情**。",
    ]


def build_messages(args, outline, context, continue_text):
    style_desc = STYLES.get(args.style, args.style)
    parts = []

    if context:
        parts.append("【上下文 / 世界观与人物设定】\n" + context.strip())
    if continue_text:
        # 长文只取尾部，控制 token 开销
        tail = continue_text.strip()
        if len(tail) > 3000:
            tail = "……" + tail[-3000:]
        parts.append(
            "【紧接在前面的原文（不要重复它，直接往下续写，保持同一语气与视角）】\n" + tail
        )

    parts.append("【细纲（唯一剧情依据，不可改动走向）】\n" + outline.strip())

    brief = ["【写作要求】", f"- 文风：{style_desc}"]
    brief += length_brief(args.words)
    if args.pov:
        brief.append(f"- 视角：{args.pov}")
    if args.avoid:
        brief.append(f"- 禁止出现：{args.avoid}")
    if args.notes:
        brief.append(f"- 额外约束：{args.notes}")
    brief.append("- 输出：只输出小说正文段落，不要标题、不要解释。")
    parts.append("\n".join(brief))

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def strip_wrapping(text):
    """去掉模型偶尔加的代码块围栏、开头多余空行。"""
    t = (text or "").strip()
    t = re.sub(r"^```[a-zA-Z]*\s*\n", "", t)
    t = re.sub(r"\n```\s*$", "", t)
    return t.strip()


def char_count(text):
    return len(re.sub(r"\s", "", text))


# ---------- 细纲节点覆盖率 ----------
# 判定“还该不该补写”的依据是【细纲节点有没有写到】，不是字数。
# 字数不足但节点写尽 → 这是正确产出，不动它；动了就是注水。

_CJK = re.compile(r"[\u4e00-\u9fff]")


def clean_outline(text):
    """去掉 `#` 开头的注释行（方便在细纲文件里写备忘）。"""
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    return "\n".join(lines).strip()


def split_beats(outline):
    """把细纲拆成独立节点。括号里的元指令（如“止于此，不得续写”）不计入节点。"""
    text = re.sub(r"[（(][^）)]*[）)]", "\n", outline)
    text = re.sub(r"^\s*[-*·•\d]+[.、)）]?\s*", "", text, flags=re.M)
    parts = re.split(r"[\n。；;！？]", text)
    beats = []
    for p in parts:
        b = p.strip(" \t，,、——…·")
        if len(_CJK.findall(b)) >= 4:      # 太短的碎片不算节点
            beats.append(b)
    return beats[:16]


def _bigrams(s):
    chars = _CJK.findall(s)
    return {chars[i] + chars[i + 1] for i in range(len(chars) - 1)}


def beat_coverage(beats, prose):
    """用汉字 bigram 召回率近似判断每个节点是否被写到。返回 (已覆盖列表, 遗漏列表)。"""
    hay = _bigrams(prose)
    if not hay:
        return [], list(beats)
    covered, missing = [], []
    for b in beats:
        grams = _bigrams(b)
        if not grams:
            continue
        ratio = len(grams & hay) / len(grams)
        (covered if ratio >= 0.5 else missing).append(b)
    return covered, missing


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


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
    print(f"目标模型 {DEFAULT_MODEL}:", "在列表中" if DEFAULT_MODEL in models else "不在列表中")
    return 0


def main():
    sf_client.reconfigure_stdout()
    p = argparse.ArgumentParser(
        description="用 Qwen2.5-72B 把细纲扩写成小说段落（只描写，不规划剧情）"
    )
    p.add_argument("--outline", help="细纲正文（短的话直接命令行给）")
    p.add_argument("--outline-file", help="细纲文件路径 (UTF-8)")
    p.add_argument("--context", help="设定文件：人物/世界观/前情 (UTF-8)")
    p.add_argument("--continue-file", dest="continue_file", help="紧接其后的已有正文 (UTF-8)")
    p.add_argument("--style", default="default",
                   help="文风：" + " / ".join(STYLES.keys()) + "，也可直接写自由描述")
    p.add_argument("--words", type=int, default=800, help="目标字数，默认 800")
    p.add_argument("--pov", help="视角，如 '第三人称限知，跟随林昭'")
    p.add_argument("--avoid", help="禁止出现的词/桥段，如 '不要出现阳光'")
    p.add_argument("--notes", help="额外约束，如 '插入两段内心独白'")
    p.add_argument("-o", "--out", help="输出文件；不给则打印到标准输出")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"默认 {DEFAULT_MODEL}")
    p.add_argument("--temperature", type=float, default=0.85, help="0~2，默认 0.85")
    p.add_argument("--top-p", dest="top_p", type=float, default=0.9)
    p.add_argument("--top-k", dest="top_k", type=int, default=50, help="0<k<=100，默认 50")
    p.add_argument("--freq-penalty", dest="freq_penalty", type=float, default=0.3,
                   help="-2~2，防逐字重复，默认 0.3")
    p.add_argument("--stop", help="停止串（最多 4 个，用 | 分隔）")
    p.add_argument("--seed", type=int, help="随机种子（同种子结果更稳定；文档未列，部分模型可能忽略）")
    p.add_argument("--trace-id", dest="trace_id", help="自定义 X-Trace-Id，便于排查")
    p.add_argument("--stream", action="store_true", help="流式输出")
    p.add_argument("--expand", type=int, default=0, metavar="N",
                   help="原地加厚：把最短的 N 段重写得更厚（默认 0=不改动）")
    p.add_argument("--check", action="store_true", help="只检查环境变量与鉴权")
    args = p.parse_args()

    if args.check:
        return cmd_check()

    outline = args.outline or ""
    if args.outline_file:
        outline = read(args.outline_file)
    outline = clean_outline(outline)
    if not outline.strip():
        p.error("必须提供 --outline 或 --outline-file")

    context = read(args.context) if args.context else ""
    continue_text = read(args.continue_file) if args.continue_file else ""

    # 字数 -> max_tokens 粗估（中文约 1 字 ≈ 1.5~2 token，留余量；文档建议给上下文留缓冲）
    max_tokens = max(1024, min(8192, int(args.words * 2.2) + 512))

    messages = build_messages(args, outline, context, continue_text)

    finish = None

    def generate(msgs, out_text):
        """一次完整生成，返回 (text, finish_reason)。"""
        try:
            if args.stream:
                buf = []
                for delta in sf_client.chat_stream(messages=msgs, **base_kwargs):
                    buf.append(delta)
                    sys.stdout.write(delta)
                    sys.stdout.flush()
                sys.stdout.write("\n")
                return strip_wrapping("".join(buf)), None
            t, fin, usage = sf_client.chat(messages=msgs, **base_kwargs)
            t = strip_wrapping(t)
            if out_text:
                print(t)
            if fin == "length":
                print(f"[警告] 输出被 max_tokens({max_tokens}) 截断，建议调大 --words 或拆段",
                      file=sys.stderr)
            if usage:
                rt = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
                print(
                    f"[用量] prompt={usage.get('prompt_tokens')} "
                    f"completion={usage.get('completion_tokens')} "
                    f"total={usage.get('total_tokens')}" + (f" reasoning={rt}" if rt else ""),
                    file=sys.stderr,
                )
            return t, fin
        except sf_client.ApiError:
            raise

    base_kwargs = dict(
        model=args.model,
        temperature=args.temperature,
        top_p=args.top_p,
        max_tokens=max_tokens,
        frequency_penalty=args.freq_penalty,
        top_k=args.top_k,
        stop=[s for s in args.stop.split("|") if s] if args.stop else None,
        trace_id=args.trace_id,
    )
    if args.seed is not None:
        base_kwargs["seed"] = args.seed

    try:
        text, finish = generate(messages, out_text=not args.out)
    except sf_client.ApiError as e:
        print("API 错误:", e, file=sys.stderr)
        return 1

    # ---- 只报告，不自动补 ----
    # 字数不够不是缺陷：细纲写尽了就该停，硬凑就是注水。
    # 节点覆盖用字面 bigram 近似，中文改写会误判成“未写”，所以仅作为【提示】，不触发任何动作。
    beats = split_beats(outline)
    n = char_count(text)
    covered, suspect = beat_coverage(beats, text)

    if args.words:
        print(f"[篇幅] {n} 字 / 参考 {args.words} 字", file=sys.stderr)
    else:
        print(f"[篇幅] {n} 字", file=sys.stderr)
    print(f"[节点] 细纲 {len(beats)} 个，字面可对上 {len(covered)} 个", file=sys.stderr)
    if suspect:
        print("       以下节点未在成稿中找到字面对应（可能是改写，也可能真漏了，需人工看一眼）：",
              file=sys.stderr)
        for m in suspect:
            print(f"         · {m}", file=sys.stderr)
        print("       确认漏写 → 用 --expand 把相关段落原地写厚，不要追加或重生成", file=sys.stderr)

    # ---- 原地加厚（默认不开启）----
    # 为什么不追加/重生成：
    #   追加 → 模型写完一场就会收尾，再往后接必然与结尾打架（人已经走了又回来）
    #   重生成 → 丢掉已经写好的好句子，且结果随机
    # 原地重写某一段 → 结构、顺序、结尾都不动，代价最小且不会断裂
    if args.expand and finish != "length":
        paras = [p for p in text.split("\n\n") if p.strip()]
        order = sorted(range(len(paras)), key=lambda i: char_count(paras[i]))
        targets = [i for i in order if char_count(paras[i]) >= 40][: args.expand]
        if not targets:
            print("[加厚] 找不到适合加厚的段落（都太短），跳过", file=sys.stderr)
        for _round, idx in enumerate(targets, 1):
            orig = paras[idx]
            want = int(char_count(orig) * 1.6)
            print(
                f"[加厚 {_round}/{len(targets)}] 第 {idx + 1} 段 "
                f"{char_count(orig)} 字 → 约 {want} 字",
                file=sys.stderr,
            )
            exp_msgs = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "下面是完整的一节正文，我要你把其中**第 "
                        f"{idx + 1} 段**（用 <<< >>> 标出）重写得更厚。\n\n"
                        f"【全文】\n{text}\n\n"
                        f"【要重写的段落】\n<<<\n{orig}\n>>>\n\n"
                        "要求：\n"
                        "1. 只重写这一段，**其他段落一个字都不要动、不要输出**。\n"
                        "2. 这一段原有的事件、顺序、结尾位置全部不变，只把细节写厚："
                        f"动作分解、感官（触/嗅/温/声）、环境与光线的变化，扩到约 {want} 字。\n"
                        "3. 不新增人物、不新增物件、不推进时间、不把后面的情节提前写。\n"
                        "4. **重写版的结尾必须与原段结尾落在同一位置**：原段停在哪里，重写版就停在哪里，"
                        "不得把下一段的内容吸进来。\n"
                        "5. **只用中文书写**，严禁夹任何外语单词或拼音。\n"
                        f"6. 文风保持：{STYLES.get(args.style, args.style)}。\n"
                        "7. 只输出重写后的这一段正文，不要 <<< >>> 标记、不要任何说明。"
                    ),
                },
            ]
            try:
                new_p, _f, _u = sf_client.chat(messages=exp_msgs, **base_kwargs)
            except sf_client.ApiError as e:
                print("  加厚失败，保留原段:", e, file=sys.stderr)
                break
            new_p = strip_wrapping(new_p).replace("<<<", "").replace(">>>", "").strip()
            # 去掉夹带的外语单词（模型偶尔会中英混写）
            new_p = re.sub(r"\s*[A-Za-z][A-Za-z']*\s*", "", new_p)
            new_p = re.sub(r"\s{2,}", "", new_p).strip()
            # 防止把下一段开头吸进来（会造成相邻两段重复同一句）
            if idx + 1 < len(paras):
                head = paras[idx + 1].strip()[:10]
                if head:
                    pos = new_p.find(head)
                    if pos != -1 and pos > len(new_p) * 0.3:
                        cut = new_p[:pos].rstrip("，,、 \n")
                        if cut and cut[-1] not in "。！？…\"”：；":
                            cut += "。"
                        print(f"  去重：截掉吞进来的下一段开头 {len(new_p) - len(cut)} 字",
                              file=sys.stderr)
                        new_p = cut
            n_new, n_old = char_count(new_p), char_count(orig)
            # 模型失控（把整篇吐回来 / 没写长）就丢弃，不污染正文
            if n_new < n_old * 1.1:
                print(f"  丢弃：重写版只有 {n_new} 字，没比原段长", file=sys.stderr)
                continue
            if n_new > n_old * 3.0:
                print(f"  丢弃：重写版 {n_new} 字，超出原段 3 倍，疑似把全文吐回来了",
                      file=sys.stderr)
                continue
            paras[idx] = new_p
            text = "\n\n".join(paras)
            print(f"  采用：{n_old} → {n_new} 字（全文 {char_count(text)} 字）", file=sys.stderr)
            # 跨段重复检测（只提醒，不自动改：删错句子比重复更伤）
            grams_new = {new_p[k:k + 10] for k in range(len(new_p) - 9)}
            if grams_new:
                for j, p in enumerate(paras):
                    if j == idx:
                        continue
                    dup = grams_new & {p[k:k + 10] for k in range(len(p) - 9)}
                    if dup:
                        sample = sorted(dup, key=len, reverse=True)[0]
                        print(f"  [注意] 与第 {j + 1} 段有重复片段：\"{sample}\"",
                              file=sys.stderr)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"[已写入] {args.out}  ({char_count(text)} 字)", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
