# novel-scene-writer

**把细纲变成小说正文的 Agent Skill。**

用 [硅基流动](https://siliconflow.cn) 的 `Qwen/Qwen2.5-72B-Instruct`，把已经写定的详细剧情细纲，扩写成有质感的小说段落。

零依赖（纯 Python 标准库），Windows / macOS / Linux 通用。

> ⚠️ **这个工具只做"描写"，不做"规划"。**
> 它只能把已确定的剧情写出来。**禁止**用它生成大纲、推演因果、设计伏笔/反转/人物动机。
> 详见下方[铁律](#铁律)。

---

## 为什么要有这个 skill

写作流程里，"想"和"写"该用不同的模型：

```
主控模型（你，或上层 agent）  →  写细纲、定因果、定人物动机、查一致性
        ↓  细纲（已定稿）
Qwen2.5-72B                  →  只负责"写出来"：感官、动作、环境、节奏、对话语气
        ↓  成稿段落
主控模型                      →  复核：偷加情节？OOC？注水？
```

72B 的描写能力确实好，但它的结构规划能力是弱项——让它规划剧情，它会给你表面通顺、实际因果跳跃的东西，还会选最俗最安全的走向。所以这里把它锁死在"笔"的角色上。

## 快速开始

```bash
git clone https://github.com/<你的用户名>/novel-scene-writer.git
cd novel-scene-writer

# 1. 设置 API Key（只从环境变量读，永不出现在命令行里）
export SILICONFLOW_API_KEY=sk-xxx          # Linux / macOS，建议写进 ~/.bashrc
```
```powershell
# Windows 永久写入用户环境变量（设置后需重开终端）
powershell -NoProfile -Command "[Environment]::SetEnvironmentVariable('SILICONFLOW_API_KEY','sk-xxx','User')"
```

```bash
# 2. 自检
python scripts/write_scene.py --check

# 3. 跑一个场景：细纲 + 设定 + 文风
python scripts/write_scene.py \
  --outline-file examples/scene_outline.txt \
  --context examples/setting.md \
  --style 冷峻 \
  --words 700 \
  -o scene.txt
```

## 铁律

**唯一允许的用法**：已经有写清楚的细纲（谁 / 在哪 / 做了什么 / 结果如何 / 视角是谁），要把它变成小说正文。

| 禁止 | 原因 |
|---|---|
| 生成剧情大纲 / 分章结构 | 结构规划与因果推演是它的弱项，产出表面通顺实际因果跳跃 |
| 决定"接下来该发生什么" | 它倾向选最顺、最俗、最安全的走向，等于把故事写成平均值 |
| 设计伏笔 / 反转 / 人物动机 | 它会把反转写成解释，把动机写成标签 |
| 设定世界观 / 力量体系 / 人物小传 | 具体细节会自我矛盾，后续章节无法自洽 |

**判断标准**：如果你调用前还需要在 prompt 里写"请你想想主角应该怎么办"，那就不该调用它——先把细纲补完整。

## 用法

```bash
cd novel-scene-writer

# 最短用法
python scripts/write_scene.py --outline "她把信烧了。火光照亮她的脸。她没有哭。" --words 600

# 细纲 + 设定文件 + 文风 + 输出文件
python scripts/write_scene.py --outline-file 细纲/s3.txt --context 设定.md \
  --style 冷峻 --words 1200 -o 成稿/s3.txt

# 接住前文语气（只取前文尾部 3000 字做锚点）
python scripts/write_scene.py --outline-file 细纲/s4.txt --continue-file 成稿/s3.txt --style 冷峻

# 嫌某段太薄，原地把它写厚（不动结构、不动结尾）
python scripts/write_scene.py --outline-file 细纲/s3.txt --style 冷峻 --expand 2

# 流式预览
python scripts/write_scene.py --outline "..." --words 800 --stream

# 加约束
python scripts/write_scene.py --outline-file s5.txt --style 悬疑 --pov "第三人称限知，跟随林昭" \
  --avoid "阳光、笑声" --notes "插入两段内心独白，不要出现直接对话" -o out.txt
```

### 主要参数

| 参数 | 说明 |
|---|---|
| `--outline` / `--outline-file` | 细纲（二选一，必填） |
| `--context` | 设定文件：人物、世界观、前情 |
| `--continue-file` | 紧接其后的已有正文 |
| `--style` | 文风预设或自由描述，见下 |
| `--words` | 参考篇幅，默认 800（**只是提示，不是验收指标**） |
| `--pov` | 视角说明 |
| `--avoid` | 禁止出现的词 / 桥段 |
| `--notes` | 其他约束 |
| `--expand N` | 原地加厚：把最短的 N 段重写得更厚（默认 0 = 不改动） |
| `-o, --out` | 输出文件（UTF-8） |
| `--temperature` | 0~2，默认 0.85 |
| `--top-p` / `--top-k` | 默认 0.9 / 50 |
| `--freq-penalty` | -2~2，默认 0.3（压制逐字重复） |
| `--stop` | 停止串，多个用 `\|` 分隔（服务端最多 4 个） |
| `--seed` | 随机种子（官方文档未列此参数） |
| `--trace-id` | 自定义 `X-Trace-Id`，排查问题用 |
| `--stream` | 流式输出 |
| `--check` | 只做环境变量 + 鉴权检查 |

### 文风预设

`default` 细腻写实 · `细腻` 感官与微表情 · `冷峻` 短句克制留白 · `古风` 古典白话 ·
`热烈` 高张力韵律 · `悬疑` 不可靠细节 · `温柔` 暖调日常 · `暴力` 粗粝直给 ·
`对话` 潜台词驱动 · `动作` 快门式节奏

`--style` 也可以直接写自由描述，比如 `--style "海明威式的短句，大量对话，不写心理"`。

## 细纲怎么写（决定成败的 80%）

这个模型是"笔"，不是"脑"。细纲写多细，成稿就多细。

```text
✅ 好的细纲
林昭（28岁，法医）在凌晨两点回到拆迁到一半的旧居院中。
她拨开墙缝的杂草，取出母亲留下的铁盒。
盒内只有一把生锈的钥匙和半张照片。
她用双手把泥土一点点捧回去，把盒子埋回原处，跪下按实，起身离开，没有回头。
视角：第三人称限知，全程跟随林昭。

❌ 坏的细纲
林昭回家发现了什么，然后她很伤心，最后决定离开。
```

坏细纲的问题：没有"发现什么"、没有"为什么伤心"、没有"离开去哪"——模型会自己补上，而它补的通常俗套且与后文冲突。

**三条实操经验**

1. **必须包含 5 项**：谁 / 在哪 / 做什么 / 结果如何 / 视角归属
2. **动作方式也要写**。实测：细纲写「她把盒子埋回原处」→ 成稿凭空出现「拾起一把铲子」；改成「她用双手把泥土一点点捧回去」→ 不出现任何工具，细节还更狠。**缺什么它补什么**：缺天气它下雨，缺光线它开路灯，缺情绪它抒情。不想让它补的，就在细纲或 `--avoid` 里堵死。
3. **一次调用 = 一个连续场景**，500~1500 字。超 2000 字拆段，跨场景分次调用（否则模型会自己写过渡，写成流水账）。

## 为什么"字数不够"不自动补

这个项目踩过三个坑，最后的选择是：**默认只生成一次，只报告，不动手。**

| 做法 | 问题 |
|---|---|
| 字数不够就重生成 | 把字数当验收标准 = **奖励注水**；重写版是随机新产出，可能更差，却把首版写好的句子全扔了 |
| 字数不够就追加补写 | **实测必然断裂**。正文已写「她离开，没有回头」，补写又接「她站起身，跪回铁桶边」。只喂最后一段做锚点、明确写"不要重写上文"，照样倒回去 |
| 字数不够就自动检测漏节点 | 用字面 bigram 匹配，中文改写会系统性误报（「回到拆迁到一半的旧居」vs「回到旧居」被判成没写到） |

根因：**这个模型写完一场就会收尾，任何往后追加都跟结尾打架。**

所以：

```bash
$ python scripts/write_scene.py --outline-file scene.txt --words 700
[篇幅] 408 字 / 参考 700 字
[节点] 细纲 4 个，字面可对上 4 个
```

- 字数短但节点齐 → **正确产出**，不修
- 确实要更长 → **把细纲拆得更细（加节点）**，而不是调大 `--words`
- 确实嫌某段太薄 → `--expand N` 原地把那几段写厚

### `--expand` 为什么不会断裂

它挑字数最少的那 N 段，**只重写那一段**，其他段落一字不动。事件、顺序、结尾位置全不变，只把动作分解和感官细节写厚。

脚本自带几道自动保险：

- 清掉中英混写夹进来的外语单词（实测模型往中文里塞过 `underneath`）
- 重写版把下一段开头吞进来了 → 自动截掉（也是实测撞出来的）
- 重写版没变长（<1.1 倍）或长得离谱（>3 倍，疑似把全文吐回来）→ 丢弃不用
- 与相邻段落有 10 字以上重复 → 只报 `[注意]`，不自动删（删错句子比重复更伤）

## 生成后的人工复核

模型最高频的 3 个问题：

1. **偷加情节 / 偷加道具** —— 检查是否出现细纲里没有的人物、物件、转折、结局
2. **提前收尾 / 注水** —— 是否用「就这样过去了」「不知道未来如何」这类概括句凑字数
3. **语气漂移** —— 与前文相比是否突然变文艺/变口语，人物说话方式变了

发现偷加情节时：不要在原 prompt 上纠缠，**把细纲改得更明确**（补一句「止于此动作，不得继续」）再重跑。

## 排错

| 现象 | 处理 |
|---|---|
| `环境变量 SILICONFLOW_API_KEY 未设置` | 见[快速开始](#快速开始)；**设置后必须重开终端** |
| `401 / code=20012` | Key 无效或已失效，去控制台重新生成 |
| `403 Forbidden` | 该模型需实名/充值，或不在你的可用模型列表内 |
| `429 TPM limit reached` | 限流。脚本自动退避重试 3 次；仍失败则降低并发 |
| `503 / code=50505` Model service overloaded | 服务过载，脚本自动重试；持续失败可换 `Qwen/Qwen2.5-32B-Instruct` |
| 输出被截断（`finish_reason=length`） | `--words` 超过 ~3000 时的正常现象，拆段 |
| 中文乱码 | Windows 控制台默认 GBK，脚本已强制 UTF-8；仍乱码执行 `chcp 65001` |

## 作为 Agent Skill 使用

`SKILL.md` 是标准的 Agent Skill 定义（带 `name` / `description` frontmatter），可直接放进支持 Skills 的 agent（如 [pi](https://github.com/earendil-works/pi-coding-agent)）的 skills 目录或配置里，让 agent 在写小说时自动调用。

## 官方 API 文档要点

来源：<https://api-docs.siliconflow.cn/docs/api/chat-completions-post>

- 鉴权 `Authorization: Bearer <API Key>`；追踪头 `X-Trace-Id` / `traceparent`，响应头 `x-siliconcloud-trace-id`
- `max_tokens` **不包含**思维链部分；文档建议不要设到窗口上限，为输入留约 10k buffer
- 流式以 `data: [DONE]` 结束
- 采样参数：`temperature`(0~2) / `top_p`(≤1) / `top_k`(≤100) / `frequency_penalty`(-2~2) / `min_p`(仅 Qwen3) / `stop`(最多 4 条) / `n` / `response_format` / `seed`(文档未列)
- 推理模型：`enable_thinking` / `thinking_budget`(128~32768) / `reasoning_effort`(high\|max)
- 推理内容在 `message.reasoning_content`，用量在 `usage.completion_tokens_details.reasoning_tokens`

## License

MIT
