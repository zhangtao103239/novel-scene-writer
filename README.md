# novel-scene-writer

**按一小段细纲，写一小段小说正文。**

用 [硅基流动](https://siliconflow.cn) 的 `Qwen/Qwen2.5-72B-Instruct`。零依赖（纯 Python 标准库），Windows / macOS / Linux 通用。

---

## 核心原则：分工

这是整个项目唯一重要的事。

| | 外部（你 / 上层 agent） | 模型 |
|---|---|---|
| **管什么** | **大局**：谁在场、发生什么、结束在哪、多少字、文风方向 | **全部细节**：动作、环境、感官、对话、节奏、句子 |
| **不管什么** | 不写细节 | 不改剧情走向 |

细纲**只写"人、事、物"，像新闻电讯**：

```text
✅ 新闻体（大局）
他醒在陌生床上，手和衣裳都不属于自己。
他下床照镜，镜中人他不认识。
平儿进屋，唤他"二爷"，他应下，把想问的话咽回。

❌ 抢了模型的活
他睁眼，先看帐顶绣纹，闻到甜腻熏香，躺着一动不动，
把眼睛转了一圈，抬起右手翻过来又翻过去看了两遍，
用这只手捏了一下自己的脸颊……
```

**为什么不能抢**：实测把这些细节写进细纲，模型只能逐条填，
产出变成「一句细纲换一句正文」的填表文。把细节还给模型，
它自己会补出烛台、挂帘、碗底磕桌面这些血肉。

### 细纲三忌

| 忌 | 例子 | 为什么 |
|---|---|---|
| 忌环境清单 | 「帐顶绣纹、铜帐钩、熏香、青砖地、琵琶扣、铜镜」 | **大忌**。环境是背景不是主角，罗列环境会让正文变成静物描写 |
| 忌表演指令 | 「把手翻过来又翻过去看了两遍」 | 这是模型的活，你写了它只能照演 |
| 忌抽象情绪 | 「他非常震惊」 | 它会用「心中涌起复杂的情感」这类套话糊过去 |

**字数也别给多**。一次给小段，一次出小段。给 800 字额度，它一定自己编内容填满。

---

## 快速开始

```powershell
# Windows 永久写入用户环境变量（设置后需重开终端）
powershell -NoProfile -Command "[Environment]::SetEnvironmentVariable('SILICONFLOW_API_KEY','sk-xxx','User')"
```
```bash
export SILICONFLOW_API_KEY=sk-xxx          # Linux / macOS，建议写进 ~/.bashrc
git clone https://github.com/zhangtao103239/novel-scene-writer.git
cd novel-scene-writer
python scripts/write_scene.py --check
```

## 用法

```bash
# 1. 写一小段（字数按节点数自动估，默认 150/节点，夹在 150~600）
python scripts/write_scene.py -r "他醒在陌生床上，手和衣裳都不属于自己。" --context 设定.md

# 2. 一次交付一整章：细纲一行一节点，自动逐个调用、去重、串接
python scripts/write_scene.py --per-node 细纲.txt --context 设定.md -o 成章.txt

# 3. 带文风参考（已确认的句子，让它照语气写）
python scripts/write_scene.py --per-node 细纲.txt --style-ref 文风.txt -o 成章.txt

# 4. 加你自己的文风描述
python scripts/write_scene.py -r "..." --style "白描，短句，不写心理活动"

# 5. 接着前文写
python scripts/write_scene.py -r "..." --continue-file 前文.txt

# 6. 某段太薄，原地写厚（只重写那一段，其他不动）
python scripts/write_scene.py --from-file 稿.txt --expand 1

# 7. 流式
python scripts/write_scene.py -r "..." --stream
```

### 参数

| 参数 | 说明 |
|---|---|
| `-r, --request` | 这一段要写什么（新闻体，原样传给模型） |
| `--request-file PATH` | 同上，写在文件里 |
| `--outline` / `--outline-file` | 细纲（与 `-r` 等价） |
| `--per-node PATH` | 逐节点模式：一行一节点，逐个调用并串接 |
| `--context PATH` | 设定：人物、世界观、前情 |
| `--continue-file PATH` | 紧接其后的已有正文 |
| `--style-ref PATH` | 文风参考：已确认的句子 |
| `--style` | 文风描述，你自己的话 |
| `--words` | 字数；不给则按节点数自动估 |
| `--pov` / `--notes` | 视角 / 其他补充 |
| `-o, --out` | 输出文件（UTF-8） |
| `--from-file PATH` | 载入已有正文，跳过生成（配合 `--expand`） |
| `--expand N` | 原地加厚：把最短的 N 段写得更厚 |
| `--temperature` / `--top-p` / `--top-k` | 0.85 / 0.9 / 50 |
| `--freq-penalty` | 0.3 |
| `--stop` / `--seed` / `--trace-id` | 停止串 / 复现 / 排查 |
| `--stream` | 流式输出 |
| `--check` | 只检查环境变量 + 鉴权 |

文件里 `#` 开头的行会被当注释丢掉，可以写备忘。

## 提示词有多短

```text
[system]
你是一名中文小说写手。按下面的要求写小说正文。只输出正文，不要标题、不要说明。

[user]
【设定】…      ← 可选，用来钉住人物名和关系
【文风参考】…  ← 可选
【上文】…      ← 可选
【要写的这一段】
他醒在陌生床上，手和衣裳都不属于自己。
【写法】约 150 字。     ← 可选
```

没有文风预设、没有一堆禁止项。早期版本有 7 条编号规则约 400 字，
结果模型把每条约束当成一格表格去填，产出僵扁。删掉就活了。

## 已知局限（实测）

| # | 现象 | 说明 |
|---|---|---|
| 1 | **它一定会自己往后跑** | 给一个节点，它顺带把后面几个也写了。逐节点模式已自动去重，但剧情层面重叠仍可能残留；单次模式必然超出结尾，**剪掉最后 1~2 句是正常工序** |
| 2 | **否定句基本无效** | 写了「写完就停，不要往下写任何情节」，仍产出 2100 字并自编花园、凉亭、一群年轻人 |
| 3 | **字数会超约 70%** | 估 150 字往往出 220~260 字 |
| 4 | **不给设定就会串人物** | 实测把贾琏写成「宝玉」、平儿写成「晴雯」。想要谁就把名字钉在 `--context` 里 |
| 5 | **会漏现代词** | 「现代生活」「速溶咖啡」「手机壳」都出现过 |
| 6 | **文风参考会被搬句子** | 喂原句当范文，它会直接复用（「碗底磕在桌面响了一声」整句出现过）。参考只给 3~5 句，且内容与正文无关；用完核对 |
| 7 | **关系容易写错** | 它自己推出「老太太就是您的母亲」（贾母是贾琏的祖母） |

所以实际用法是「**外部管大局，模型写细节，人剪接尾**」。

## 排错

| 现象 | 处理 |
|---|---|
| `环境变量 SILICONFLOW_API_KEY 未设置` | 见[快速开始](#快速开始)；**设置后必须重开终端** |
| `401 / code=20012` | Key 无效，去控制台重新生成 |
| `403 Forbidden` | 该模型需实名/充值，或不在可用列表内 |
| `429 TPM limit reached` | 限流，脚本自动退避重试 3 次 |
| `503 / code=50505` | 服务过载，自动重试；持续失败换 `Qwen/Qwen2.5-32B-Instruct` |
| 输出被截断 | 减少 `--words`，或拆段 |
| 中文乱码 | Windows 控制台默认 GBK，脚本已强制 UTF-8；仍乱码执行 `chcp 65001` |

## 作为 Agent Skill 使用

`SKILL.md` 是标准 Agent Skill 定义（带 `name` / `description` frontmatter），
可直接放进支持 Skills 的 agent（如 [pi](https://github.com/earendil-works/pi-coding-agent)）的 skills 配置。

## 官方 API 文档要点

<https://api-docs.siliconflow.cn/docs/api/chat-completions-post>

- 鉴权 `Authorization: Bearer <API Key>`；追踪头 `X-Trace-Id` / `traceparent`
- `max_tokens` **不包含**思维链；文档建议留约 10k buffer
- 流式以 `data: [DONE]` 结束
- 采样：`temperature`(0~2) / `top_p`(≤1) / `top_k`(≤100) / `frequency_penalty`(-2~2) / `min_p`(仅 Qwen3) / `stop`(≤4) / `n` / `response_format` / `seed`(文档未列)

## License

MIT
