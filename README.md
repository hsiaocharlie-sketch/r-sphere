# 数据格式

页面（`relation-sphere.html`）启动时读取 `data/index.json`，再按里面的 `files` 列表依次读取各数据文件并合并。
新增人物时，只需新增一个 JSON 文件，并把文件名加进 `index.json` 的 `files`。

```json
{ "start": "baoyu", "files": ["hongloumeng.json", "andylau.json"] }
```

`start` 是打开页面时默认的主角（人物 id）。网址末尾加 `#人物id`（如 `#andylau`）可直接打开某人。

## 数据文件

```json
{
  "meta": { "name": "说明用，可选", "src": {"title": "该文件里没写来源的关系，默认显示的来源"} },
  "people": [ ... ],
  "relations": [ ... ]
}
```

### people（人物）
| 字段 | 说明 |
|---|---|
| `id` | 唯一编号（英文/拼音），跨文件通用；不同文件里 id 相同就视为同一个人，别名会合并 |
| `name` | 显示名 |
| `alias` | 可选，别名、字号、外文名，用于搜索 |
| `note` | 可选，一句话简介 |
| `fictional` / `work` / `author` | 虚构人物用：`fictional:true`、出自作品、作者的人物 id（卡片上可点击跳到作者） |
| `wikidata` | 可选，Wikidata 的 Q 号。不同文件里 Q 号相同的人会自动合并成一个人（即使 id 不同） |

### relations（关系）
| 字段 | 说明 |
|---|---|
| `a`, `b` | 两个人物的 id |
| `type` | `kin` 亲属 · `spouse` 夫妻 · `love` 感情（前任、绯闻等）· `inlaw` 姻亲 · `servant` 主仆 · `other` 师友 · `work` 创作/合作（作者与笔下人物，也用于共事、合作、前后任、提携） |
| `aIs` | a 是 b 的什么人（如 "父亲"） |
| `bIs` | b 是 a 的什么人（如 "儿子"） |
| `status` | 可选：不写 = 确认的关系；`past` 已结束；`rumor` 传闻、未经证实；`denied` 传闻且当事人否认（后两者在球上画成虚线） |
| `from`, `to` | 可选，起止时间，如 `"2005"`、`"2005-06"`、`"2005-06-18"` |
| `events` | 可选，事件列表，每项 `{label, date, place, note, src}` |
| `src` | 可选，来源：字符串、`{title, url}`，或它们的数组 |

点击球上的关系线或关系文字，会弹出事件和来源；没有来源的事件会标"来源：未注明"。

### 例子
```json
{ "a": "andylau", "b": "carolchu", "type": "spouse", "aIs": "丈夫", "bIs": "妻子",
  "events": [ { "label": "结婚", "date": "2008-06", "place": "美国拉斯维加斯",
                "src": { "title": "维基百科：Carol Chu", "url": "https://en.wikipedia.org/wiki/Carol_Chu" } } ] }
```

### 收录原则
- 每条关系和事件都要有出处；没有可靠来源的内容不收。
- 传闻要标 `rumor` 或 `denied`，不要写成事实。
- 未成年人只收姓名和关系。

## 机器生成的文件
`wikidata.json` 由 `scripts/collect_wikidata.py` 自动生成（见 `collect/README.md`），每次整份覆盖，请勿手工修改。
手写数据文件应排在 `index.json` 的 `files` 里 `wikidata.json` 之前，这样人物简介以手写为准。

**同一个人出现两次怎么办**
- 手写数据里的人，最好都填上 `wikidata` 的 Q 号，这样一定会和自动采集的同一个人合并。
- 即使没填，页面也会再合并一轮：名字（或别名）相同、来自不同数据文件、并且有至少一个共同的关系人，就当作同一个人。同名但没有共同关系人的，不会合并。
- 如果名字写法完全不同（比如自动采集的只有英文名），页面认不出来，需要给手写数据补上 `wikidata`。采集报告里的“可能与手写数据重复的人物”会列出这类情况。
- 想检查合并了谁：在浏览器控制台输入 `relSphere.mergedLog`。
