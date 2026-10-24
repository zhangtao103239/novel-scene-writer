"""按提示词写小说正文。

长度由 HTTP 请求的 max_tokens 硬控（不是靠提示词劝它）：
达到上限就被服务端截断，再回退到最后一个完整句子结尾。

用法:
  python write_scene.py --check
  python write_scene.py "他醒在陌生床上，手和衣裳都不属于自己。"
  python write_scene.py "..." --style-ref 文风.txt
  python write_scene.py "..." -w 300 -o 段落.txt
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sf_client  # noqa: E402

MODEL = "Qwen/Qwen2.5-72B-Instruct"
WORDS_DEFAULT = 200

SYSTEM_PROMPT = "你是一名中文小说写手。按下面的要求写小说正文。只输出正文，不要标题、不要说明。"

# 中文大约 1.3 字 / token（Qwen 分词器实测）
CHARS_PER_TOKEN = 1.3


def tokens_for(words):
    """把目标字数换算成 max_tokens，服务端据此硬截断。"""
    return max(64, int(words / CHARS_PER_TOKEN))


def cut_to_sentence(text):
    """被截断时，回退到最后一个完整句子，不留半句。"""
    t = text.rstrip()
    ends = list(re.finditer(r"[。！？…”」』]", t))
    if not ends:
        return t
    return t[: ends[-1].end()]


def strip_fence(text):
    t = (text or "").strip()
    t = re.sub(r"^```[a-zA-Z]*\s*\n", "", t)
    t = re.sub(r"\n```\s*$", "", t)
    return t.strip()


def char_count(text):
    return len(re.sub(r"\s", "", text))


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln for ln in f.read().splitlines() if not ln.lstrip().startswith("#")]
    return "\n".join(lines).strip()


def build_messages(prompt, style_ref):
    parts = ["【要求】\n" + prompt.strip()]
    if style_ref:
        parts.append(
            "【文风参考：只学句子的语气和节奏，不要用里面的内容】\n" + style_ref
        )
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
    print(f"模型 {MODEL}:", "在列表中" if MODEL in models else "不在列表中")
    return 0


def main():
    sf_client.reconfigure_stdout()
    p = argparse.ArgumentParser(description="按提示词写小说正文。长度由 max_tokens 硬控。")
    p.add_argument("prompt", nargs="?", help="要写什么")
    p.add_argument("--style-ref", dest="style_ref", metavar="PATH", help="文风参考文件（可选）")
    p.add_argument("-w", "--words", type=int, default=WORDS_DEFAULT,
                   help=f"目标字数，默认 {WORDS_DEFAULT}")
    p.add_argument("-o", "--out", metavar="PATH", help="输出文件（UTF-8）")
    p.add_argument("--model", default=MODEL, help=f"模型，默认 {MODEL}")
    p.add_argument("--check", action="store_true", help="只检查环境变量与鉴权")
    args = p.parse_args()

    if args.check:
        return cmd_check()
    if not args.prompt:
        p.error("请给出提示词，例如：write_scene.py \"他醒在陌生床上……\"")

    prompt = args.prompt
    if os.path.isfile(prompt):          # 提示词太长时写成文件，直接传路径
        prompt = read(prompt)

    max_tokens = tokens_for(args.words)
    messages = build_messages(prompt, read(args.style_ref) if args.style_ref else "")

    try:
        kw = {}
        # 只有 Qwen3 原生对话模型才关思维链；R1 蒸馏版（名字里带 Qwen3）是推理模型，必须开着
        if args.model.split("/")[-1].startswith("Qwen3"):
            kw["enable_thinking"] = False
        text, finish, usage = sf_client.chat(
            messages=messages,
            model=args.model,
            max_tokens=max_tokens,
            temperature=0.85,
            top_p=0.9,
            **kw,
        )
    except sf_client.ApiError as e:
        print("API 错误:", e, file=sys.stderr)
        return 1

    text = strip_fence(text)
    if finish == "length":
        before = char_count(text)
        text = cut_to_sentence(text)
        print(f"[截断] max_tokens={max_tokens} 到顶，回退到完整句尾 "
              f"{before} → {char_count(text)} 字", file=sys.stderr)

    if usage:
        rt = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
        print(f"[用量] prompt={usage.get('prompt_tokens')} "
              f"completion={usage.get('completion_tokens')}"
              + (f" reasoning={rt}" if rt else "")
              + f" ({char_count(text)} 字)", file=sys.stderr)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"[已写入] {args.out}", file=sys.stderr)
    else:
        print(text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
