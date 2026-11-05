# 发布说明

## 仓库信息

- 仓库：`cuixianfeng/cxf-skill`（公开，默认分支 `main`）
- 描述（About）：崔先锋CXF Skill：让AI认识你的资料库 + 自媒体选题 + 口播写稿 + 发布前检查 + 防限流 + 内容抓取。国内外支持 Skill 的 Agent 都能用（WorkBuddy、Claude Code、Codex 等）。
- Topics：
  - agent-skills
  - claude-skills
  - ai-self-media
  - personal-knowledge-base
  - workbuddy
  - ima
  - interview
  - skill

说明：GitHub topics 只允许小写英文、数字和连字符，所以中文关键词（个人知识库、自媒体选题、资料库、内容抓取）写进仓库描述和 README，同样能被搜到。

## 仓库结构

- `skills/cxf/`：总入口，介绍三个板块并分流
- `skills/cxf-library/`：崔先锋资料库
- `skills/cxf-topic/`：崔先锋选题（读【我的档案】，最多 5 条）
- `skills/cxf-script/`：崔先锋写稿（按选题类型写完整口播稿，另附 2 个备选开头和画面建议）
- `skills/cxf-check/`：崔先锋检查（四项分开查：AI 味、防限流、逻辑连贯、看不懂）
- `skills/cxf-safe/`：崔先锋防限流（AI 自媒体专用：软件名、Logo、导流；限流判断与抢救）
- `skills/cxf-review/`：崔先锋复盘（发布后要截图和客资数，写进「数据复盘」文件夹，满 10 条再总结规律）
- `skills/cxf-fetch/`：崔先锋抓取（链接 / 对标账号 / 逐字稿）

## 发布步骤

1. 在 GitHub 新建公开仓库 `cuixianfeng/cxf-skill`，填上面的描述和 topics。
2. 在本地仓库目录执行：

```bash
git init
git add README.md LICENSE VERSION .gitignore docs skills
git commit -m "发布崔先锋 CXF Skill 1.0.0（cxf + cxf-library）"
git branch -M main
git remote add origin https://github.com/cuixianfeng/cxf-skill.git
git push -u origin main
```

3. 可选：打版本标签 `v1.0.0`，在 GitHub 上建一个 Release。
4. 验证安装：在一个空目录运行 `npx skills add cuixianfeng/cxf-skill --list`，应列出 `cxf`、`cxf-library`、`cxf-topic` 和 `cxf-fetch`。

## 发布前检查

- 仓库里没有真实用户的档案（`.gitignore` 已忽略 `我的档案*.md`）。
- 示例全部为虚构，并已标注。
- 没有密钥、个人路径、测试记录。

## 1.1.0（2026-11-03）

- 新增并发布 **崔先锋抓取** `cxf-fetch`：支持发链接 / 调研博主近半年点赞最高等内容，产出清单与逐字稿。
- 总入口 `cxf` 将抓取类请求直接分流到 `cxf-fetch`（不再写「另行发布」）。
- README 补抓取用法、依赖（Python、Chrome/Edge、首次语音模型约 230MB）与合规说明。
- 验证：`npx skills add cuixianfeng/cxf-skill --list` 应列出 `cxf`、`cxf-library`、`cxf-fetch`。

发布本版：

```bash
# 本地提交后推送到 main，再打标签
git tag v1.1.0
# 或在 GitHub 上创建 Release：标题「崔先锋 CXF Skill 1.1.0」，说明新增崔先锋抓取
```

## 1.2.0（2026-11-03）

- 新增并发布 **崔先锋选题** `cxf-topic`：自动找【我的档案】，有大致方向即可出题；一次最多 5 条（题干 + 依据 + 一句为什么适合你）；有产品优先转化/引流，无产品优先流量。
- 总入口 `cxf`：用户说「用 CXF 选题 Skill」「请用 CXF 选题 Skill 帮我做选题」「帮我选题」「今天拍什么」等，直接进入 `cxf-topic`。
- README 补选题用法；安装说明包含 `cxf-topic`。
- 验证：`npx skills add cuixianfeng/cxf-skill --list` 应列出 `cxf`、`cxf-library`、`cxf-topic`、`cxf-fetch`。

发布本版：

```bash
git tag v1.2.0
# GitHub Release 标题：「v1.2.0 崔先锋选题 cxf-topic」
```

## 1.3.0（2026-11-04）

- 新增 **崔先锋写稿** `cxf-script`：读【我的档案】，把一条选题写成约 1 分钟的口播稿，只用真事和原话；另附 2 个备选开头；交稿后问要不要检查。
- 新增 **崔先锋检查** `cxf-check`：四项分开查（AI 味、防限流、逻辑连贯、看不懂），每处标必须改或建议改并给改法；问要不要按这几处改好。
- 新增 **崔先锋防限流** `cxf-safe`（AI 自媒体专用）：发布前按平台换掉软件名、Logo、网址和导流；发布后判断是否限流，按「先改文字 → 再换封面 → 最后改视频」抢救。
- **崔先锋选题** `cxf-topic` 1.1.0：交完题后问「挑哪条？回编号，我帮你写成口播稿」，回编号直接进入写稿；去掉选题结束后主动回写档案的流程。
- 总入口 `cxf` 1.3.0：介绍六个板块，写稿、检查、防限流类请求直接分流。
- 总名改为 **崔先锋 CXF Skill**；各板块名统一为「崔先锋资料库」「崔先锋检查」等，名称里一律带「崔」；口令不变（仍说「用 CXF 选题 Skill」等）。
- 说明从「国内 Agent 可用」改为「国内外支持 Skill 的 Agent 都能用」。
- 验证：`npx skills add cuixianfeng/cxf-skill --list` 应列出 `cxf`、`cxf-library`、`cxf-topic`、`cxf-script`、`cxf-check`、`cxf-safe`、`cxf-fetch`。

发布本版：

```bash
git tag v1.3.0
# GitHub Release 标题：「v1.3.0 崔先锋写稿 cxf-script + 崔先锋检查 cxf-check」
```

## 1.4.0（2026-11-04）

- 新增 **崔先锋复盘** `cxf-review`：视频发出 48～72 小时后，主动告诉用户截哪一页后台数据、问客资数；读数先复述确认，再写进知识库里的「数据复盘」文件夹（每条复盘记录含稿子原文 + 复盘汇总 + 规律），不写进【我的档案】。不到 10 条只记录和出复盘卡；满 10 条才总结，结论标「待验证」；同类 3 条以上对得上才成「规律」。
- **崔先锋选题** `cxf-topic` 1.2.0：出题前读「数据复盘」里的「规律」；定时任务交付末尾提醒复盘。
- **崔先锋写稿** `cxf-script` 1.1.0：写稿前读「规律」里和开头、写法有关的条目。
- 总入口 `cxf` 1.4.0：介绍七个板块，复盘类请求直接分流。
- 验证：`npx skills add cuixianfeng/cxf-skill --list` 应列出 `cxf`、`cxf-library`、`cxf-topic`、`cxf-script`、`cxf-check`、`cxf-safe`、`cxf-review`、`cxf-fetch`。

发布本版：

```bash
git tag v1.4.0
# GitHub Release 标题：「v1.4.0 崔先锋复盘 cxf-review」
```

## 1.5.0（2026-11-05）

- **崔先锋写稿** `cxf-script` 1.2.0：稿子从「约 1 分钟、250 字」改为按选题类型定长度和结构（拆解复盘、教程方法约 2 分钟，观点、故事约 1 分半），结构写在 `references/structures.md`；写之前对照「必备料」，缺关键细节先问（一次一个，最多 3 个）；开头 15 秒要有话题、钩子和为什么信你；正文要兑现选题，方法讲到能照着做，段落连成意思、不一句一段；交付加推进思路和画面建议。
- **崔先锋选题** `cxf-topic` 1.2.1：成功标准里不再写死「1 分钟口播」。

发布本版：

```bash
git tag v1.5.0
# GitHub Release 标题：「v1.5.0 崔先锋写稿升级：完整口播稿」
```
