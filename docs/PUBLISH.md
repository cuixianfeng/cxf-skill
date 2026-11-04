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
- `skills/cxf-library/`：先锋资料库
- `skills/cxf-topic/`：先锋选题（读【我的档案】，最多 5 条）
- `skills/cxf-script/`：先锋写稿（把选题写成口播稿，另附 2 个备选开头）
- `skills/cxf-check/`：先锋检查（风险词、AI 味、顺不顺）
- `skills/cxf-safe/`：先锋防限流（AI 自媒体专用：软件名、Logo、导流；限流判断与抢救）
- `skills/cxf-fetch/`：先锋抓取（链接 / 对标账号 / 逐字稿）

## 发布步骤

1. 在 GitHub 新建公开仓库 `cuixianfeng/cxf-skill`，填上面的描述和 topics。
2. 在本地仓库目录执行：

```bash
git init
git add README.md LICENSE VERSION .gitignore docs skills
git commit -m "发布先锋 CXF Skill 1.0.0（cxf + cxf-library）"
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

- 新增并发布 **先锋抓取** `cxf-fetch`：支持发链接 / 调研博主近半年点赞最高等内容，产出清单与逐字稿。
- 总入口 `cxf` 将抓取类请求直接分流到 `cxf-fetch`（不再写「另行发布」）。
- README 补抓取用法、依赖（Python、Chrome/Edge、首次语音模型约 230MB）与合规说明。
- 验证：`npx skills add cuixianfeng/cxf-skill --list` 应列出 `cxf`、`cxf-library`、`cxf-fetch`。

发布本版：

```bash
# 本地提交后推送到 main，再打标签
git tag v1.1.0
# 或在 GitHub 上创建 Release：标题「先锋 CXF Skill 1.1.0」，说明新增先锋抓取
```

## 1.2.0（2026-11-03）

- 新增并发布 **先锋选题** `cxf-topic`：自动找【我的档案】，有大致方向即可出题；一次最多 5 条（题干 + 依据 + 一句为什么适合你）；有产品优先转化/引流，无产品优先流量。
- 总入口 `cxf`：用户说「用 CXF 选题 Skill」「请用 CXF 选题 Skill 帮我做选题」「帮我选题」「今天拍什么」等，直接进入 `cxf-topic`。
- README 补选题用法；安装说明包含 `cxf-topic`。
- 验证：`npx skills add cuixianfeng/cxf-skill --list` 应列出 `cxf`、`cxf-library`、`cxf-topic`、`cxf-fetch`。

发布本版：

```bash
git tag v1.2.0
# GitHub Release 标题：「v1.2.0 先锋选题 cxf-topic」
```

## 1.3.0（2026-11-04）

- 新增 **先锋写稿** `cxf-script`：读【我的档案】，把一条选题写成约 1 分钟的口播稿，只用真事和原话；另附 2 个备选开头；交稿后问要不要检查。
- 新增 **先锋检查** `cxf-check`：查风险词、AI 味、顺不顺，最多列 3 处必须改的并给改法；问要不要按这几处改好。
- 新增 **先锋防限流** `cxf-safe`（AI 自媒体专用）：发布前按平台换掉软件名、Logo、网址和导流；发布后判断是否限流，按「先改文字 → 再换封面 → 最后改视频」抢救。思路参考咕噜奇（@hmq1048762）公开分享的经验，重新整理。
- **先锋选题** `cxf-topic` 1.1.0：交完题后问「挑哪条？回编号，我帮你写成口播稿」，回编号直接进入写稿；去掉选题结束后主动回写档案的流程。
- 总入口 `cxf` 1.3.0：介绍六个板块，写稿、检查、防限流类请求直接分流。
- 总名改为 **崔先锋 CXF Skill**；各板块名和口令不变（仍说「用 CXF 选题 Skill」等）。
- 说明从「国内 Agent 可用」改为「国内外支持 Skill 的 Agent 都能用」。
- 验证：`npx skills add cuixianfeng/cxf-skill --list` 应列出 `cxf`、`cxf-library`、`cxf-topic`、`cxf-script`、`cxf-check`、`cxf-safe`、`cxf-fetch`。

发布本版：

```bash
git tag v1.3.0
# GitHub Release 标题：「v1.3.0 先锋写稿 cxf-script + 先锋检查 cxf-check」
```
