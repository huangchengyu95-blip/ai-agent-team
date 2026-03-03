# 🤖 AI Agent Team - 产品经理助手系统

一个每4小时自动运行的AI Agent团队，专门为AI社交方向的产品经理服务。

## 📋 目录
1. [系统功能](#功能)
2. [配置步骤（约30-45分钟）](#配置步骤)
3. [日常使用方式](#日常使用)
4. [状态看板](#状态看板)
5. [常见问题](#常见问题)

---

## 功能

| Agent | 运行方式 | 工作内容 |
|-------|---------|---------|
| 🔍 动态追踪员 | 每4小时自动运行 | 搜索AI社交方向最新动态，追加到飞书文档 |
| 💡 产品经理 | 每4小时自动运行 | 主动研究，更新认知沉淀文档，发现产品机会 |
| 🔬 评审员 | 有产品创意时自动触发 | 评审产品方案，发飞书消息征求你的决策 |
| 🔧 工程师 | 你批准后手动触发 | 构建HTML/CSS/JS可交互Demo原型 |

## ✅ 已自动完成的部分

以下内容已由系统自动完成，**不需要你手动操作**：

- 📡 **AI动态追踪汇总** 文档已创建 → [点击打开](https://bytedance.larkoffice.com/docx/G1nad89GBoI5MhxSCkicdB64nNc)
- 🧠 **AI社交认知沉淀** 文档已创建 → [点击打开](https://bytedance.larkoffice.com/docx/Pjr4dJIoZowMuHxJPwGc7ZlJnHc)
- 🪪 你的飞书 Open ID 已配置：`ou_6ca6e7a1f6d0a871fbad36c4750271a5`

---

## 配置步骤

总共需要做 **4件事**，预计30-45分钟。

---

### 第一步：注册 GitHub 并上传代码

**GitHub 是什么？** 免费的代码存储平台，也提供免费的定时任务运行服务。

1. 打开 [github.com](https://github.com) 注册账号
2. 点击右上角 **+** → **New repository**（新建仓库）
3. 填写：
   - 仓库名：`ai-agent-team`
   - 选择 **Public**（公开，这样看板免费无限制）
4. 点击 **Create repository**

**上传代码到GitHub：**
1. 进入新建的仓库页面，点击 **uploading an existing file**
2. 把本项目的**所有文件和文件夹**拖进去
3. 点击 **Commit changes** 完成上传

---

### 第二步：创建飞书应用

**为什么需要飞书应用？** Agent团队在GitHub Actions云端运行时，需要一个"飞书工作账号"来读写文档、发消息给你。

1. 打开 [飞书开放平台](https://open.feishu.cn/)，用你的飞书账号登录
2. 点击 **创建应用** → **自建应用**，填写：
   - 应用名称：`AI Agent Team`
   - 描述：随便填
3. 点击 **创建**

**获取 App ID 和 App Secret：**
- 进入应用的 **凭证与基础信息** 页面
- 找到 **App ID** 和 **App Secret**，复制保存（等一下要填进GitHub）

**给应用开通权限：**
1. 点击左侧 **权限管理**
2. 搜索并开通以下权限（搜索关键词后点"申请"）：
   - `docx:document` — 读写文档
   - `im:message:send_as_bot` — 发送消息
3. 权限申请后，点击 **版本管理与发布** → **创建版本** → **申请发布**

> 💡 如果是企业飞书，发布需要管理员审批；如果是个人飞书，直接发布即可

---

### 第三步：把两个文档的编辑权限共享给你的飞书应用

两个文档已自动创建好了，但你的新飞书应用还不能访问它们，需要手动共享一次：

**对「AI动态追踪汇总」文档操作：**
1. 打开文档：[AI动态追踪汇总](https://bytedance.larkoffice.com/docx/G1nad89GBoI5MhxSCkicdB64nNc)
2. 点击右上角 **分享**
3. 在搜索框输入 `AI Agent Team`（你创建的应用名）
4. 找到后选择权限为 **可编辑**，点击确认

**对「AI社交认知沉淀」文档操作（同上）：**
1. 打开文档：[AI社交认知沉淀](https://bytedance.larkoffice.com/docx/Pjr4dJIoZowMuHxJPwGc7ZlJnHc)
2. 同样步骤共享给你的 `AI Agent Team` 应用

---

### 第四步：在 GitHub 配置密钥

**密钥是什么？** API Key等敏感信息不能直接写在代码文件里，需要存在GitHub的加密保险箱（Secrets）中。

1. 进入你的GitHub仓库页面
2. 点击 **Settings**（设置） → **Secrets and variables** → **Actions**
3. 点击 **New repository secret** 逐一添加以下密钥：

| 密钥名称 | 填写内容 | 备注 |
|---------|---------|------|
| `FEISHU_APP_ID` | 第二步获取的App ID | 必填 |
| `FEISHU_APP_SECRET` | 第二步获取的App Secret | 必填 |
| `VOLCENGINE_API_KEY` | 火山引擎API Key | **暂时不填**，等其他部分测试OK后再加 |
| `VOLCENGINE_MODEL_ID` | 豆包模型ID | **暂时不填** |

> 💡 **只需要2个必填密钥！** 飞书文档ID和你的Open ID已经预先写入了 `config.json`，不需要重复配置。

---

### 第五步：开启状态看板（GitHub Pages）

1. 在GitHub仓库页面，点击 **Settings** → **Pages**
2. **Source** 选择：`Deploy from a branch`
3. **Branch** 选择：`main`，**Folder** 选择：`/(root)`
4. 点击 **Save**

几分钟后，你的看板就可以访问了：
```
https://[你的GitHub用户名].github.io/ai-agent-team/dashboard/
```

---

### 第六步：测试验证

**阶段一：测试飞书连接（不需要火山引擎API Key）**

1. 进入 GitHub 仓库 → **Actions** 标签页
2. 点击左侧 **AI Agent Team - 每4小时自动运行**
3. 点击 **Run workflow** → `是否是测试模式` 选 **true** → 点击 **Run workflow**
4. 等1-2分钟，点开运行记录查看日志
5. 验证：
   - ✅ 是否收到飞书测试消息
   - ✅ 飞书文档是否有内容写入
   - ✅ GitHub Pages看板是否正常

**阶段二：配置火山引擎（完成全部功能）**

1. 登录 [火山引擎控制台](https://console.volcengine.com/)
2. 进入 **方舟（ARK）** → **API Key 管理** → 新建 API Key
3. 进入 **在线推理** → 创建接入点，选豆包模型（如 `doubao-pro-32k`），复制接入点ID
4. 回到 GitHub Secrets，添加：
   - `VOLCENGINE_API_KEY`：API Key
   - `VOLCENGINE_MODEL_ID`：接入点ID
5. 重新手动触发一次（测试模式 false），观察完整流程

---

## 日常使用

**正常情况（每4小时自动运行，不需要你做任何事）**

你只需要：
- 随时打开看板，了解Agent工作状态
- 收到飞书通知时，做决策

**收到产品评审通知时：**

```
【产品评审通知】《AI语音伴侣》

评级：建议做 ⭐⭐⭐⭐

✅ 亮点：用户痛点真实，技术可行
⚠️ 风险：用户粘性难保证

查看完整报告：[飞书链接]

是否同意立项构建Demo？
```

- 如果同意：按下面步骤触发工程师
- 如果不同意：不需要操作，系统继续工作

**让工程师构建 Demo：**

1. 打开飞书通知中的链接，从URL复制文档ID（`docx/` 后面那串字符）
2. GitHub仓库 → **Actions** → **工程师 - 构建产品Demo**
3. 点击 **Run workflow**，填入文档ID和产品名称，点击运行
4. 等5-10分钟，收到飞书通知后，去仓库 `demos/` 目录下载 `index.html` 双击预览

---

## 状态看板

看板地址：`https://[你的GitHub用户名].github.io/ai-agent-team/dashboard/`

看板显示：
- 🔍💡🔬🔧 四个Agent的当前状态（运行中/空闲/等待）
- 最新活动日志（最近20条工作记录）
- 统计数字（总运行次数、产品创意数、Demo数量）
- 飞书文档快捷入口（一键打开三个核心文档）

**每30秒自动刷新**，不需要手动刷新。

---

## 常见问题

**Q：GitHub Actions报错找不到模块？**
A：确认上传代码时包含了所有文件夹（agents/、utils/、dashboard/等）

**Q：飞书消息收不到？**
A：
1. 确认 `FEISHU_USER_OPEN_ID` 已正确填入（值为 `ou_6ca6e7a1f6d0a871fbad36c4750271a5`）
2. 确认飞书应用已发布（不是"草稿"状态）
3. 确认应用有 `im:message:send_as_bot` 权限

**Q：飞书文档无法写入？**
A：
1. 确认第三步中已把两个文档共享给你的 `AI Agent Team` 应用
2. 共享时权限要选 **可编辑**，不能只是"可阅读"

**Q：看板是空白/加载失败？**
A：
1. 确认GitHub Pages已开启，等待5-10分钟让GitHub部署
2. 确认仓库是Public（公开）
3. 用 `Ctrl+Shift+R` 强制刷新浏览器

**Q：火山引擎哪里找豆包模型的接入点ID？**
A：进入火山引擎控制台 → 方舟 → 在线推理 → 点你创建的接入点 → 复制"接入点ID"，格式通常是 `ep-xxxxxxxx-xxxxx`

**Q：每月费用大概多少？**
A：每天6次，大模型费用约0.1-0.3元/次，月费约30-50元（火山引擎豆包较便宜）。GitHub Actions公开仓库免费无限制。

---

## 文件结构

```
ai-agent-team/
├── agents/              ← 4个Agent代码
│   ├── trend_tracker.py    🔍 动态追踪员
│   ├── product_manager.py  💡 产品经理
│   ├── product_reviewer.py 🔬 评审员
│   └── engineer.py         🔧 工程师
├── utils/               ← 底层工具（不需要修改）
│   ├── feishu_client.py    飞书API读写
│   ├── llm_client.py       火山引擎LLM调用
│   ├── web_tools.py        网络搜索+抓取
│   └── status_tracker.py   状态数据维护
├── dashboard/index.html ← 状态看板
├── demos/               ← 工程师生成的Demo
├── .github/workflows/   ← 定时任务配置
├── main.py              ← 主入口
├── config.json          ← 配置（文档ID等，已预填）
├── status.json          ← 运行状态（自动维护）
└── requirements.txt     ← Python依赖
```
