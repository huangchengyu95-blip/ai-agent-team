# AI Agent Team 架构分析文档

> 最后更新：2026-03-04
> 用途：梳理系统架构和各 Agent 实现细节，为优化产出效果提供参考

---

## 一、系统目标与整体设计

### 设计目标
为 AI 社交方向产品经理提供一套近乎 24/7 自动运行的 AI 助手团队：
- 持续追踪行业动态（每 4 小时一次）
- 主动研究和沉淀 AI 社交方向认知（不断更新同一份文档）
- 产品创意生成、评审、决策辅助
- 产品 Demo 原型开发（用户批准后手动触发）

### 整体流水线

```
GitHub Actions（每4小时，UTC 0/4/8/12/16/20点）
         ↓
Agent 1：动态追踪员  → 写飞书"AI动态追踪汇总"文档
         ↓（把抓取结果传给下一步）
Agent 2：产品经理    → 更新飞书"AI社交认知沉淀"文档
                       ↓（有产品创意时）
                      创建产品方案飞书文档
         ↓（有产品创意时才触发）
Agent 3：评审员      → 追加评审到产品方案文档
                       + 发飞书消息通知用户决策
         ↓（用户手动在GitHub Actions触发）
Agent 4：工程师      → 生成HTML Demo，保存到 demos/ 目录
```

---

## 二、技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| LLM | 火山引擎（豆包） | OpenAI 兼容格式，base_url=ark.cn-beijing.volces.com |
| 调度 | GitHub Actions cron | 每4小时自动运行，免费额度充足 |
| 文档存储 | 飞书文档 API | REST API，用 App 身份 (tenant_access_token) |
| 消息通知 | 飞书 IM API | 用邮箱发送（避免 open_id cross-app 问题） |
| 看板 | GitHub Pages 静态网页 | 读 status.json，每 30 秒刷新 |
| 搜索 | DuckDuckGo（免费） | 无需 API Key，限最近一周结果 |
| RSS 抓取 | requests + BeautifulSoup | 支持 RSS/Atom/YouTube 播客 |
| HN/Reddit | 官方公开 JSON 接口 | 无需任何 API Key |

---

## 三、文件结构

```
AI agent team/
├── agents/
│   ├── trend_tracker.py     # Agent 1：动态追踪员
│   ├── product_manager.py   # Agent 2：产品经理
│   ├── product_reviewer.py  # Agent 3：评审员
│   └── engineer.py          # Agent 4：工程师（手动触发）
├── utils/
│   ├── feishu_client.py     # 飞书 API 封装（文档读写 + 发消息）
│   ├── llm_client.py        # 火山引擎 LLM + 工具调用循环
│   ├── web_tools.py         # DuckDuckGo 搜索 + 网页抓取 + RSS/HN/Reddit
│   └── status_tracker.py   # status.json 读写工具函数
├── dashboard/index.html     # 可视化状态看板（GitHub Pages）
├── .github/workflows/
│   ├── daily_pipeline.yml   # 每4小时触发 Agent 1→2→3
│   └── build_demo.yml       # 手动触发 Agent 4
├── main.py                  # 主入口（串联所有 Agent）
├── status.json              # Agent 状态数据（自动维护）
└── config.json              # 飞书文档 ID 等配置（非密钥）
```

---

## 四、各 Agent 实现细节

### Agent 1：动态追踪员 (trend_tracker.py)

#### 工作流程
1. **预先拉取信息源**（不消耗 LLM 工具调用次数）：
   - RSS 信息源（15 个，含 OpenAI/Hugging Face 博客、多个 AI Newsletter）
   - Hacker News（topstories + showstories，各 8 条）
   - Reddit（artificial / ChatGPT / singularity / MachineLearning，各 5 条）
2. 把全部内容塞进 user_prompt，让 LLM 分析
3. LLM 还可以调用 `web_search` / `web_fetch` 工具补充搜索（最多 20 轮）
4. 结果写入飞书"AI动态追踪汇总"文档（追加模式）

#### System Prompt 核心逻辑
- 角色：AI社交动态追踪员
- 关注方向：Character.AI/Replika/Poe、大厂AI社交动作、用户真实反馈、融资并购、Product Hunt新产品、KOL观点
- 筛选原则：**只保留对产品经理有决策价值的信息**
- 优先级：用户真实反馈 > 重要产品发布 > 行业思考观点 > 融资动态

#### 输出格式（JSON）
```json
{
  "has_updates": true/false,
  "content": "Markdown格式，追加到飞书文档的正文",
  "summary": "一句话摘要（显示在看板）",
  "highlights": ["最重要的1-2条，用于飞书通知"]
}
```

#### 关键参数
- `max_iterations=20`（最多20轮工具调用）
- RSS 每个源取 3 条，HN 每类 8 条，Reddit 每版块 5 条

---

### Agent 2：产品经理 (product_manager.py)

#### 工作流程
1. 读取飞书"AI社交认知沉淀"文档（作为已有认知基础）
2. **预先拉取信息源**（偏向产品策略视角，与 Agent 1 的源不同）：
   - 15 个 RSS 源（PM Newsletter + 研究员博客 + VC 思考 + 创业播客）
   - Hacker News Ask HN（用户真实提问）+ Show HN（新产品展示）
3. 结合认知文档 + 新动态 + Agent 1 的追踪结果，LLM 深度研究（最多 25 轮）
4. 更新认知沉淀文档（追加模式）
5. **有产品机会时**创建独立的产品方案飞书文档

#### 认知沉淀文档结构（Agent 2 负责维护）
```
## 一、AI社交的本质与趋势
## 二、核心用户需求分析
## 三、现有产品格局
## 四、未被满足的需求（机会所在）
## 五、产品设计原则
## 六、技术-产品结合点
---
## 更新日志
```

#### 产品创意生成门槛（4个条件必须同时满足）
1. 用户痛点明确且真实（有用户证据）
2. 现有解决方案不够好（有明显改进空间）
3. 当前 AI 能力可以支撑（技术可行）
4. 时机合适（现在是好时机）

#### 产品创意输出字段
```json
{
  "title": "产品名称",
  "user_pain": "用户痛点（具体）",
  "solution": "解决思路",
  "mvp_features": ["核心功能1", "核心功能2"],
  "key_interactions": "主要用户流程（类原型描述）",
  "key_assumptions": ["最需验证的假设"],
  "reference_products": ["参考竞品"],
  "full_content": "完整Markdown文档"
}
```

#### 关键参数
- `max_iterations=25`（产品经理需要大量研究，是所有 Agent 中最高的）
- 认知文档只传前 3000 字给 LLM（避免 context 太长）

---

### Agent 3：评审员 (product_reviewer.py)

#### 触发条件
**仅当 Agent 2 输出了产品创意时才运行**（pm_result.has_product_idea == True）

#### 评审框架（7个维度）
1. 用户需求真实性（权重最高）
2. 现有解决方案分析
3. 产品差异化
4. 技术可行性
5. 市场时机
6. 风险分析
7. 综合评级

#### 评级标准
- ⭐⭐⭐⭐⭐ 强烈推荐
- ⭐⭐⭐⭐ 建议做（过去10次平均到这个级别）
- ⭐⭐⭐ 有潜力待验证
- ⭐⭐ 暂不建议

#### 评审后的操作
1. 把评审报告**追加**到产品方案飞书文档（在原文档底部加 `---` 分隔）
2. 发飞书消息给用户，格式：
   - 评级 + 核心亮点（≤3条）+ 主要风险（≤2条）+ 建议
3. 更新 status.json（状态变为 waiting，等待用户决策）

#### 关键参数
- `max_iterations=15`（评审不需要太多搜索）
- 发消息用**邮箱**而非 open_id（避免 cross-app 问题）

---

### Agent 4：工程师 (engineer.py)

#### 触发方式
**纯手动触发**，通过 GitHub Actions `build_demo.yml` 或命令行：
```bash
python agents/engineer.py --doc-id <飞书文档ID>
```

#### 工作流程
1. 读取飞书产品方案文档（含评审报告）
2. 传给 LLM 生成 HTML Demo（只取文档前 5000 字）
3. 保存到 `demos/<产品名>_<时间戳>/index.html`
4. 发飞书消息通知用户

#### Demo 构建标准（Hard Requirements）
- **单 HTML 文件**（直接双击可用，无需服务器）
- **移动端优先**（375px 基准，触控友好）
- **真实感假数据**（无占位符）
- **核心流程可交互**（Happy Path 完整演示）
- **纯原生 HTML/CSS/JS**（无外部依赖，离线可用）

#### 关键参数
- `use_tools=False`（工程师只写代码，不搜索）
- `max_iterations=3`（通常一次生成就够）

---

## 五、共享工具层

### LLM 客户端 (llm_client.py)

**工具调用循环机制：**
```
1. 发请求给 LLM（system_prompt + user_prompt）
2. LLM 决定是否调用工具（web_search / web_fetch）
3. 执行工具，把结果作为新消息追加
4. 重复直到 LLM 不再调用工具，返回最终答案
5. 达到 max_iterations 时强制返回最后一条答案
```

**两个可用工具：**
- `web_search(query)` → DuckDuckGo 搜索，限最近一周，返回 8 条
- `web_fetch(url)` → 抓取网页，清除 nav/footer/script，返回前 4000 字

**LLM 未配置时的 mock 机制：**
- 根据 system_prompt 内容判断是哪个 Agent
- 返回固定格式的 JSON 测试数据
- 其他功能（飞书、状态更新）可继续正常测试

### Web 工具 (web_tools.py)

| 函数 | 来源 | 限制 |
|------|------|------|
| `web_search` | DuckDuckGo | 最近一周，max 8 条 |
| `web_fetch` | requests + BS4 | 超时 15s，截取前 4000 字 |
| `fetch_rss_feed` | RSS/Atom XML | 超时 10s，每源取 5 条 |
| `fetch_hn_posts` | HN 官方 API | 每类取 8 条 |
| `fetch_reddit_posts` | Reddit 公开 JSON | 每版块 5 条 |

### 飞书客户端 (feishu_client.py)

核心功能：
- `create_document(title, folder_token)` → 创建文档（App 身份）
- `append_to_document(doc_id, content)` → 追加内容到文档
- `get_document_content(doc_id)` → 读取文档全文
- `send_message_to_user(user_id, content, receive_id_type)` → 发消息
- `send_rich_message(...)` → 发带标题+链接的格式化消息
- `create_folder(name)` → 在云盘创建文件夹

**重要约定：**
- 用 `tenant_access_token`（App 身份），不用 user token
- 发消息用 `email` 类型（避免 open_id cross-app 限制）
- 写文档只能写 App 自己创建的文档（外部共享的文档写入会 Forbidden）

---

## 六、当前运行状态

截至 2026-03-04：
- 流水线已运行 **11 次**
- 已生成产品创意 **10 个**（均为 ⭐⭐⭐-⭐⭐⭐⭐ 级别）
- 已构建 Demo：**0 个**（工程师从未被触发）
- 飞书文档：刚完成 App 切换，文档 ID 已清空，下次运行会重建

近期产品创意列表（时间倒序）：
1. 秒伴 - 9.9元/月的低延迟AI语音陪伴产品 ⭐⭐⭐⭐
2. AgentMate：专属AI社交代理人平台 ⭐⭐⭐⭐
3. 轻伴 - 普惠级低延迟语音AI伴侣 ⭐⭐⭐⭐
4. 「轻语」低延迟自然语音AI伴侣 ⭐⭐⭐
5. 声伴 - 400ms延迟的专属AI语音伴侣 ⭐⭐⭐⭐
6. VoiceMate - 低延迟语音AI陪伴社交Agent ⭐⭐⭐⭐
7. MemBox（AI记忆保险箱）⭐⭐⭐
8. 密语 - 端侧隐私优先AI语音伴侣 ⭐⭐⭐⭐
9. 语境感知跨社群多语言翻译插件「译聊」⭐⭐⭐⭐
10. （更早期作品）

---

## 七、问题诊断与优化空间

### 问题 1：产品创意同质化严重（核心问题）

**现象：** 10 个创意中有 6-7 个都是"低延迟语音 AI 陪伴"，方向高度重叠。

**根本原因：**
- Agent 2 的 system prompt 要求 **每次运行都生成创意**（实际执行中）
- 认知文档虽然在积累，但产品创意没有做**去重/差异化检查**
- LLM 倾向于选择"最近信息流行的话题"（低延迟语音在近期频繁出现）

**优化方向：**
1. 在产品创意生成前，让 Agent 2 先读已有创意列表，要求**明确说明差异化**
2. system prompt 加约束：如果方向与近期 3 个创意高度重叠，跳过不生成
3. 引入"创意多样性"维度的考核（不同方向轮换：陪伴/代理/工具/社交/记忆等）

---

### 问题 2：Agent 2 每次运行都会输出创意（即使不值得）

**现象：** 11 次运行，10 次都生成了创意。门槛形同虚设。

**根本原因：**
- System prompt 里"4个条件"的判断由 LLM 自己评估，LLM 倾向于乐观
- 认知文档每次更新都有新信息涌入，LLM 容易被新信息驱动"找机会"

**优化方向：**
1. 提高生成门槛的描述强度（加 "**宁可不生成，也不要低质量创意**"）
2. 把"每次运行是否生成"的概率目标设为约 30-50%（每两三次生成一次才是正常频率）
3. 加一个"创意质量评分"前置过滤：只有自评 8 分以上才写入创意

---

### 问题 3：认知文档只追加，越来越冗余

**现象：** 认知沉淀文档持续追加，但没有整合/精简/去重机制，文档越来越长。

**根本原因：**
- Agent 2 只做 append，不做重组
- 每次"更新日志"中的信息实际上覆盖了更早的章节内容，但两者并存

**优化方向：**
1. 每运行 5 次，触发一次"认知重整"：读全文，输出重新整理后的最新版本（覆盖写入）
2. 认知文档的上限设为 5000 字，超过时自动压缩旧内容

---

### 问题 4：动态追踪搜索时间窗口太短

**现象：** DuckDuckGo 设定 `timelimit='w'`（最近一周），但系统每4小时运行，等于每次只搜"最近一周内"的内容。

**根本原因：**
- DuckDuckGo 的 `timelimit='d'`（一天）更精准，但 `'w'`（一周）可能导致重复内容

**优化方向：**
1. 改为 `timelimit='d'`，搜最近 24 小时，避免大量重复信息
2. 在 prompt 中加"今天日期"和"上次搜索时间"，让 LLM 只关注新内容

---

### 问题 5：工程师从未被触发（0 个 Demo）

**现象：** 已有 10 个产品创意，0 个 Demo。用户没有批准任何一个。

**可能原因：**
- 创意同质化让用户对评审通知失去新鲜感
- 飞书通知可能没有有效送达（早期有 cross-app 问题）
- 用户触发工程师的流程不够顺畅（需要手动去 GitHub Actions 操作）

**优化方向：**
1. 先解决创意质量问题（差异化 + 高评分），提升用户批准意愿
2. 优化飞书通知的表达，让用户更容易做决策（直接在消息里说明触发步骤）
3. 考虑低门槛的 Demo 触发方式（如回复飞书消息"做"就触发）

---

### 问题 6：Agent 2 的认知文档读取被截断

**现象：** 代码里 `current_knowledge[:3000]`，只传前 3000 字给 LLM，其余内容不可见。

**优化方向：**
1. 适当扩大到 6000-8000 字
2. 改为"读最后 N 字"（更新日志在末尾，更新时最应该读末尾）

---

## 八、优先优化建议（排序）

| 优先级 | 优化项 | 预期效果 | 改动成本 |
|--------|--------|---------|---------|
| P0 | 解决创意同质化：生成前先读已有创意，要求差异化 | 创意质量和多样性显著提升 | 中（修改 system prompt） |
| P1 | 降低创意生成频率：提高门槛描述，目标 30-50% 触发率 | 减少低质创意噪音 | 低（修改 system prompt） |
| P2 | 搜索时间窗改为 1 天：`timelimit='d'` | 减少重复内容，信息更新鲜 | 低（改一行代码） |
| P3 | 认知文档读取扩大：从 3000 字扩到 8000 字，读末尾内容 | Agent 2 有更多上下文，判断更准 | 低（改一行代码） |
| P4 | 增加创意去重检查：把历史 10 条创意标题传给 Agent 2 | 自动避免重复方向 | 中（需要读 status.json） |
| P5 | 认知文档定期重整：每 5 次运行整合一次 | 文档保持简洁，认知框架更清晰 | 高（需要新逻辑） |

---

## 九、快速查阅：各 Agent 关键参数对比

| Agent | max_iterations | use_tools | 输出文档 | 触发条件 |
|-------|--------------|-----------|---------|---------|
| 动态追踪员 | 20 | ✅ | 追加动态汇总文档 | 每次流水线 |
| 产品经理 | 25 | ✅ | 更新认知文档 + 新建创意文档 | 每次流水线 |
| 评审员 | 15 | ✅ | 追加到创意文档 | 有产品创意时 |
| 工程师 | 3 | ❌ | 新建 demos/xxx/index.html | 手动触发 |
