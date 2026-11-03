# 发布说明

## 仓库信息

- 仓库：`cuixianfeng/cxf-skill`（公开，默认分支 `main`）
- 描述（About）：先锋CXF Skill：让AI认识你的资料库 + 自媒体选题 + 内容抓取。国内Agent（WorkBuddy等）可用。
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
- 先锋选题 `cxf-topic`、先锋抓取 `cxf-fetch` 发布时，各放进 `skills/` 下一个同名文件夹

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
4. 验证安装：在一个空目录运行 `npx skills add cuixianfeng/cxf-skill --list`，应列出 `cxf` 和 `cxf-library`。

## 发布前检查

- 仓库里没有真实用户的档案（`.gitignore` 已忽略 `我的档案*.md`）。
- 示例全部为虚构，并已标注。
- 没有密钥、个人路径、测试记录。
