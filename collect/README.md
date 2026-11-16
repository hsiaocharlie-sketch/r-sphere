# 自动采集（Wikidata）

不需要任何付费接口或密钥。流程：改 `collect/seeds.json` → GitHub 自动运行脚本 → 生成一个 Pull Request → 你检查后点 Merge → 网页自动更新。

## 一次性设置
1. 仓库 **Settings → Actions → General**，下拉到 **Workflow permissions**：
   - 选 **Read and write permissions**
   - 勾选 **Allow GitHub Actions to create and approve pull requests**
   - 点 Save
2. 确认仓库里有这些文件（路径要一致）：
   - `scripts/collect_wikidata.py`
   - `.github/workflows/collect.yml`
   - `collect/seeds.json`

## 最省事的用法：直接填人名
1. 仓库的 **Actions** 页面，左侧选"从 Wikidata 采集人物关系"，点右边的 **Run workflow**。
2. 在 **要新增的人名** 框里填人名（可填多个，用逗号分隔，如 `李世民,杨贵妃`），点绿色的 Run workflow。
3. 程序会把名字追加进 `collect/seeds.json`，再去抓数据，并开一个 Pull Request。到 **Pull requests** 页面核对报告里"按名字匹配"的人物对不对，没问题就 Merge。

## 使用
1. 编辑 `collect/seeds.json`，在 `seeds` 里加人物，有三种写法：
   ```json
   "李世民"
   { "name": "李世民", "hint": "Tang" }
   { "qid": "Q9701", "expect": "Taizong of Tang" }
   ```
   - **只写人名**：程序会去 Wikidata 搜索，取最像的那个人物。同名的人很多时可能匹配错，所以采集报告会列出"其他同名候选"让你核对，并且**含有按名字匹配的人物时不会自动合并**。
   - **名字加 `hint`**：用来区分同名，比如朝代、职业、国家（中英文都行）。
   - **写 Q 号最稳**：到 wikidata.org 搜人名，打开条目，网址末尾的 `Q` 加数字就是编号。`expect` 是这个人的名字，编号和名字对不上时程序会停下，防止搞错人。确认按名字匹配对了以后，建议把写法改成 Q 号固定下来。
   - `depth`：1 = 只取这个人自己的关系；2 = 再取他的关系人的关系；每多一层人数大约翻几倍。
   - `max_people`：人数上限，防止越滚越多。
2. 提交修改，GitHub 会自动运行；也可以在 **Actions** 页面手动点 **Run workflow**。
3. 几分钟后到 **Pull requests** 页面，会有一个"自动采集：Wikidata 人物关系"。先看里面的报告，再到 **Files changed** 抽查几条关系（每条都带 Wikidata 来源链接），没问题就点 **Merge**。

## 全自动（可选）
- 默认流程：采集 → 生成 Pull Request → 你检查后点 Merge。
- 想省掉这一步：把 `collect/seeds.json` 里的 `"auto_merge"` 改成 `true`，采集结果会自动合并进主分支。注意这样就没有人工检查了，Wikidata 上的错误或恶意改动会直接出现在网页里，建议只在已经抽查过种子人物之后再打开。
- 想定期自动刷新：打开 `.github/workflows/collect.yml` 里 `schedule` 那两行的注释（去掉 `#`）。

## 注意
- `data/wikidata.json` 是机器生成的，每次整份覆盖，**不要手工改它**。手写的内容（感情传闻、合作关系、带出处的事件）放在别的文件，比如 `data/andylau.json`。
- 同一个人如果在手写数据里也有，会显示成两个人。给手写数据里的这个人加上 `"wikidata": "Q号"`，页面就会自动合并。采集报告里会列出疑似重复的人物。
- Wikidata 只有亲属、配偶、非婚伴侣这几类关系，而且并不完整，没有的不会凭空出现。
- 程序只请求 Wikidata，不会碰任何其他网站。
