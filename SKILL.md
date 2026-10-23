---
name: novel-scene-writer
description: 按提示词写小说正文。硅基流动 Qwen/Qwen2.5-72B-Instruct。长度由 max_tokens 硬控，不靠提示词劝。外部只管大局（谁在场、发生什么），细节（动作、环境、感官、对话）全部交给模型。
license: MIT
compatibility: Windows / macOS / Linux，Python >= 3.9（纯标准库，零依赖）
---

# Novel Scene Writer

给一段提示词，出一段正文。就这一个用法。

模型：`Qwen/Qwen2.5-72B-Instruct`（硅基流动）

---

## 分工

| 外部（你） | 模型 |
|---|---|
| **大局**：谁在场、发生什么、多少字 | **全部细节**：动作、环境、感官、对话、节奏、句子 |

提示词写成**新闻电讯**——一句一事，只写"人、事、物"：

```text
✅ 他醒在陌生床上，手和衣裳都不属于自己。
   他下床走到镜前，看见一张不认识的脸。

❌ 他睁眼，先看帐顶绣纹，闻到甜腻熏香，躺着一动不动，
   把眼睛转了一圈，抬起右手翻过来又翻过去看了两遍……
```

**三忌**：忌环境清单（会让正文变静物描写）、忌表演指令（那是模型的活）、忌抽象情绪（「他非常震惊」→ 它会用套话糊过去）。

## 长度：靠 max_tokens，不靠提示词

`max_tokens = 目标字数 / 1.3`（中文约 1.3 字/token）。到顶就是服务端硬截断，
再把半句砍掉、回退到最后一个完整句号结尾。

实测目标 200 字 → `completion=153`（=max_tokens）→ 回退后 204 字，正好收在「。」上。

提示词里不写任何字数要求。写「约 150 字」它一律写 250 字，这个模型不听劝。

## 用法

```bash
# 设置 Key（只从环境变量读）
export SILICONFLOW_API_KEY=sk-xxx          # Linux/macOS，建议写进 ~/.bashrc
```
```powershell
powershell -NoProfile -Command "[Environment]::SetEnvironmentVariable('SILICONFLOW_API_KEY','sk-xxx','User')"
```

```bash
python scripts/write_scene.py --check                       # 自检

python scripts/write_scene.py "他醒在陌生床上，手和衣裳都不属于自己。"
python scripts/write_scene.py "..." -w 400                  # 目标 400 字
python scripts/write_scene.py "..." --style-ref 文风.txt     # 加文风参考
python scripts/write_scene.py examples/prompt.txt -w 300    # 提示词写在文件里，传路径
python scripts/write_scene.py "..." -o 段落.txt
```

### 参数（就这些）

| 参数 | 说明 |
|---|---|
| `prompt` | 提示词（位置参数）。传文件路径时自动读取文件内容 |
| `--style-ref PATH` | 文风参考（可选） |
| `-w, --words` | 目标字数，默认 200 → 换算成 max_tokens |
| `-o, --out PATH` | 输出文件（UTF-8） |
| `--check` | 只检查环境变量 + 鉴权 |

文件里 `#` 开头的行会被当注释丢掉。

## 已知局限

| 现象 | 说明 |
|---|---|
| **一定会自己往后跑** | 给一个节点它会顺带写后面几个。靠 max_tokens 截断兜住，剪掉最后半句是常规 |
| **否定句无效** | 写「不要往下写任何情节」，它照样产出 2100 字并自编花园、凉亭、一群人 |
| **不给设定就会串人物** | 实测把贾琏写成「宝玉」、平儿写成「晴雯」。要把名字和关系写进提示词 |
| **会漏现代词** | 「现代生活」「速溶咖啡」「手机壳」都出现过 |
| **文风参考会带偏长度** | 范文短，产出也会变短（实测 250 字目标只出 33 字）。要长度就调 `-w` |
| **关系容易写错** | 它自己推出「老太太就是您的母亲」（贾母是贾琏的祖母） |

## 文件

```
novel-scene-writer/
├── SKILL.md
├── README.md
├── examples/
│   ├── prompt.txt        提示词样例（新闻体）
│   ├── style_ref.txt     文风参考样例
│   └── setting.md        设定样例
└── scripts/
    ├── sf_client.py      硅基流动客户端（纯标准库）
    └── write_scene.py    主程序（约 130 行）
```

## 官方 API 文档要点

<https://api-docs.siliconflow.cn/docs/api/chat-completions-post>

鉴权 `Authorization: Bearer <API Key>`；`max_tokens` 不含思维链；流式以 `data: [DONE]` 结束。
`sf_client.py` 内含 429/503 自动退避、`X-Trace-Id` 追踪头、官方错误码翻译。
