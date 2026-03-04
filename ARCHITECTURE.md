# AI Agent Team 架构分析文档

> 最后更新：2026-03-04
> 用途：梳理系统架构和各 Agent 实现细节，为优化产出效果提供参考

---

## 一、系统目标与整体设计

### 设计目标
为 AI 社交方向产品经理提供一套近乎 24/7 自动运行的 AI 助手团队：
- 持续追踪行业动态（每 4 小时一次）
- 主动研究和沉淀 AI 社交方向认知（不断整合重写同一份文档）
- 产品创意生成、评审、决策辅助
- 产品 Demo 原型开发（用户批准后手动触发）

### 整体流水线

```
GitHub Actions（每4小时，UTC 0/4/8/12/16/20点）
         ↓
Agent 1：动态追踪员  → 追加写入飞书"AI动态追踪汇总"文档
         ↓（把抓取结果传给下一步）
Agent 2：产品经理    → 整合重写飞书"AI社交认知沉淀"文档
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
| LLM | **OpenRouter（优先）/ 火山引擎（备用）** | OpenAI 兼容格式；配置 `OPENROUTER_API_KEY` 即自动切换 |
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
│   ├── llm_client.py        # LLM 客户端（OpenRouter/火山引擎）+ 工具调用循环
│   ├── web_tools.py         # DuckDuckGo 搜索 + 网页抓取 + RSS/HN/Reddit
│   └── status_tracker.py   # status.json 读写工具函数
├── dashboard/index.html     # 可视化状态看板（GitHub Pages）
├── .github/workflows/
│   ├── daily_pipeline.yml   # 每4小时触发 Agent 1→2→3
│   └── build_demo.yml       # 手动触发 Agent 4
├── main.py                  # 主入口（串联所有 Agent）
├── status.json              # Agent 状态数据（自动维护）
├── config.json              # 飞书文档 ID 等配置（非密钥）
└── ARCHITECTURE.md          # 本文件
```

---

## 四、各 Agent 实现细节

### Agent 1：动态追踪员 (trend_tracker.py)

#### 工作流程
1. **读取飞书"AI动态追踪汇总"文档末尾 3000 字**（用于去重，避免重复记录相同事件）
2. **预先拉取信息源**（不消耗 LLM 工具调用次数）：
   - RSS 信息源（15 个，含 OpenAI/Hugging Face 博客、多个 AI Newsletter）
   - Hacker News（topstories + showstories，各 8 条）
   - Reddit（artificial / ChatGPT / singularity / MachineLearning，各 5 条）
3. 把"历史已记录内容 + 新信息源内容"全部塞进 user_prompt，LLM 分析并去重
4. LLM 还可以调用 `web_search` / `web_fetch` 工具补充搜索（最多 20 轮）
5. 结果**追加写入**飞书"AI动态追踪汇总"文档

#### 去重机制
- 在 user_prompt 里附上"飞书文档中已记录的最近动态（末尾3000字）"
- 明确要求 LLM：已出现过的信息跳过，只记录完全新的内容

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
1. 读取飞书"AI社交认知沉淀"文档（最新 8000 字，作为已有认知基础）
2. 从 `status.json` 的 `ideas_history` 字段读取所有历史创意标题（去重用）
3. **预先拉取信息源**（偏向产品策略视角，与 Agent 1 的源不同）：
   - 15 个 RSS 源（PM Newsletter + 研究员博客 + VC 思考 + 创业播客）
   - Hacker News Ask HN（用户真实提问）+ Show HN（新产品展示）
4. 结合认知文档 + 新动态 + Agent 1 的追踪结果，LLM 深度研究（最多 25 轮）
5. **整合重写认知沉淀文档**（非追加，调用 `replace_document_content` 全量替换）
6. **有产品机会时**创建独立的产品方案飞书文档

#### 认知沉淀文档结构（深度分析框架，Agent 2 负责维护）
```
## 一、社交需求的底层本质
（基于自我决定理论 + JTBD 三层分析：功能性/情感性/社会性工作）
（现实社交在哪些维度系统性失败，AI社交真正填补的缺口）

## 二、细分场景地图（每个场景 5 要素）
### 场景N：[名称]
- 触发时机：什么时候
- 用户心理状态：内心在感受什么
- 当前解法：用户现在怎么处理
- 当前解法的具体不足：为什么不够好
- AI社交的机会：AI能怎么做到真人做不到的

## 三、竞品深度解析
（Character.AI/Replika/Poe 等，核心策略假设 + 留存/流失真实原因）

## 四、产品机会矩阵
（各场景的市场空白、差异化空间、门槛分析）

## 五、从需求反推的产品设计逻辑
（每条原则必须有推导过程）

## 六、技术-场景匹配分析
（具体技术突破对应的具体场景，不是泛泛说"大模型能力提升"）

---
## 更新日志
```

#### 文档质量标准
- ❌ 不合格：「用户需要情感陪伴 → AI可以提供」（空洞）
- ✅ 合格：「独居用户深夜情绪低落（触发），想倾诉但不想麻烦朋友（心理），当前刷短视频（解法），没有被真正理解的感觉（不足），AI可提供不评判+记住上下文的倾听（差异化）」

#### 认知文档写入机制
- 使用 `replace_document_content`（清空旧内容 + 写入新内容），不追加
- 确保每次都是完整的 6 章结构，无"新增内容："等增量标记

#### 产品创意生成门槛（5个条件必须同时满足）
1. 有具体的细分场景支撑（能对应到第二章某个场景）
2. 竞品在该场景有明确可证明的不足（有证据）
3. 当前 AI 能力可以支撑（技术可行）
4. 时机有优势（原因清晰）
5. 方向与 `ideas_history` 中历史创意明显不同

**目标触发率：约 30-50%（宁可不生成，也不要低质量/雷同创意）**

#### 产品创意输出字段
```json
{
  "title": "产品名称",
  "target_scenario": "对应第二章哪个细分场景",
  "user_pain": "When-Then格式的具体痛点描述",
  "solution": "核心价值主张（说明与竞品本质差异）",
  "mvp_features": ["功能1（对应哪个需求）", "功能2"],
  "key_interactions": "具体交互步骤（有场景感）",
  "key_assumptions": ["能推翻整个方案的关键假设"],
  "reference_products": ["学什么+避什么"],
  "full_content": "完整Markdown文档"
}
```

#### 关键参数
- `max_iterations=25`（产品经理需要大量研究，是所有 Agent 中最高的）
- 认知文档传入 LLM 时取最新 8000 字

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
- ⭐⭐⭐⭐ 建议做（过去已生成产品平均到这个级别）
- ⭐⭐⭐ 有潜力待验证
- ⭐⭐ 暂不建议

#### 评审后的操作
1. 把评审报告**追加**到产品方案飞书文档（在原文档底部加 `---` 分隔）
2. 发飞书消息给用户，格式：评级 + 核心亮点（≤3条）+ 主要风险（≤2条）+ 建议
3. 调用 `add_idea_to_history(title, summary)` 永久保存创意标题到 `ideas_history`
4. 更新 status.json（状态变为 waiting，等待用户决策）

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

**多提供商支持（优先级顺序）：**
1. **OpenRouter**：检测到 `OPENROUTER_API_KEY` 时使用，base_url=`https://openrouter.ai/api/v1`，默认模型 `anthropic/claude-sonnet-4-5`
2. **火山引擎**：检测到 `VOLCENGINE_API_KEY` 时使用，base_url=`https://ark.cn-beijing.volces.com/api/v3`
3. **Mock 模式**：两者都未配置时，返回固定格式 JSON 测试数据（其他功能可继续测试）

配置方式：在 GitHub Secrets 中设置对应环境变量即可，代码无需改动。

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

---

### Web 工具 (web_tools.py)

| 函数 | 来源 | 限制 |
|------|------|------|
| `web_search` | DuckDuckGo | 最近一周，max 8 条 |
| `web_fetch` | requests + BS4 | 超时 15s，截取前 4000 字 |
| `fetch_rss_feed` | RSS/Atom XML | 超时 10s，每源取 5 条 |
| `fetch_hn_posts` | HN 官方 API | 每类取 8 条 |
| `fetch_reddit_posts` | Reddit 公开 JSON | 每版块 5 条 |

---

### 飞书客户端 (feishu_client.py)

核心功能：
- `create_document(title, folder_token)` → 创建文档（App 身份）
- `append_to_document(doc_id, content)` → 追加内容到文档（动态追踪文档使用）
- **`replace_document_content(doc_id, content)`** → 清空旧内容后写入新内容（认知沉淀文档使用）
- `get_document_content(doc_id)` → 读取文档全文
- `send_message_to_user(user_id, content, receive_id_type)` → 发消息
- `send_rich_message(...)` → 发带标题+链接的格式化消息
- `create_folder(name)` → 在云盘创建文件夹

**`replace_document_content` 实现细节：**
1. 分页循环调用 `GET /docx/v1/documents/{id}/blocks`（每页500条）获取所有块
2. 统计根块的直接子块数量
3. `DELETE /docx/v1/documents/{id}/blocks/{root_id}/children/batch_delete` 删除所有子块
4. 调用 `append_to_document` 写入新内容

**`_request` 支持的 HTTP 方法：** GET / POST / PATCH / DELETE

**重要约定：**
- 用 `tenant_access_token`（App 身份），不用 user token
- 发消息用 `email` 类型（避免 open_id cross-app 限制）
- 写文档只能写 App 自己创建的文档（外部共享的文档写入会 Forbidden）

---

### 状态追踪 (status_tracker.py)

`status.json` 中的关键数据结构：

| 字段 | 说明 | 大小限制 |
|------|------|---------|
| `agents` | 各 Agent 当前状态 | 无限制 |
| `activity_log` | 最近活动日志 | **最多50条**（MAX_LOG_ENTRIES=50） |
| **`ideas_history`** | 所有历史产品创意标题 | **无限制**（永久保存） |
| `feishu_links` | 飞书文档快捷链接 | 固定3个 |
| `stats` | 统计数据 | 固定字段 |

**`ideas_history` 说明：**
- 由 `product_reviewer` 在完成每次评审后写入（`add_idea_to_history`）
- `product_manager` 读取用于去重（`get_ideas_history`），不再依赖截断的 `activity_log`
- 避免重复记录同名创意（按 title 去重）

---

## 六、当前运行状态

截至 2026-03-04：
- 流水线已运行 **15+ 次**
- 已生成产品创意 **7+ 个**（均已保存在 `ideas_history`）
- 已构建 Demo：**0 个**（工程师从未被触发）
- LLM：待切换至 OpenRouter（配置 `OPENROUTER_API_KEY` 后生效）

已评审的产品创意（时间倒序）：
1. 「轻伴」分级定价AI语音伴侣 ⭐⭐⭐⭐
2. 秒伴 - 9.9元/月的低延迟AI语音陪伴产品 ⭐⭐⭐⭐
3. AgentMate：专属AI社交代理人平台 ⭐⭐⭐⭐
4. 轻伴 - 普惠级低延迟语音AI伴侣 ⭐⭐⭐⭐
5. 「轻语」低延迟自然语音AI伴侣 ⭐⭐⭐
6. 声伴 - 400ms延迟的专属AI语音伴侣 ⭐⭐⭐⭐
7. VoiceMate - 低延迟语音AI陪伴社交Agent ⭐⭐⭐⭐

---

## 七、已修复问题记录

| 问题 | 根因 | 修复方案 | 状态 |
|------|------|---------|------|
| 认知沉淀文档内容混乱（多次内容叠加） | `_request` 不支持 DELETE → replace 失败 → 实际只追加 | 新增 DELETE 支持；blocks 分页循环获取 | ✅ 已修复 |
| 认知文档只写增量片段而非完整6章 | LLM prompt 约束不足，用"新增内容："前缀写局部 | 加强 prompt 禁止增量标记，强制6章完整输出 | ✅ 已修复 |
| 产品创意同质化（多次产出"低延迟语音陪伴"） | `activity_log` 截断至50条，历史创意标题丢失 | 新增 `ideas_history` 永久列表；评审完成后写入 | ✅ 已修复 |
| 动态追踪文档重复记录相同事件 | trend_tracker 不读取已有文档内容 | 每次运行前读取文档末尾3000字传给LLM去重 | ✅ 已修复 |
| 认知文档分析深度不够（大而空） | 文档框架过于宏观，无强制深度约束 | 重构文档结构引入 JTBD + 场景5要素 + 竞品深层分析 | ✅ 已修复 |
| LLM 质量不足（豆包产出质量低） | 火山引擎豆包模型能力有限 | 支持 OpenRouter（Claude/GPT-4o），配置密钥即切换 | ✅ 代码已就绪，待配置密钥 |

---

## 八、已知待优化项

| 优先级 | 优化项 | 说明 |
|--------|--------|------|
| P1 | 配置 OpenRouter API Key | 切换到更强的模型（Claude Sonnet 推荐）|
| P2 | 搜索时间窗改为 1 天 | DuckDuckGo `timelimit='d'`，减少重复内容 |
| P3 | 工程师触发流程优化 | 在飞书通知里直接说明触发步骤，降低操作门槛 |

---

## 九、快速查阅：各 Agent 关键参数对比

| Agent | max_iterations | use_tools | 文档写入方式 | 触发条件 |
|-------|--------------|-----------|------------|---------|
| 动态追踪员 | 20 | ✅ | **追加**（append）到动态汇总文档 | 每次流水线 |
| 产品经理 | 25 | ✅ | **整合重写**（replace）认知沉淀文档 | 每次流水线 |
| 评审员 | 15 | ✅ | **追加**（append）到产品创意文档 | 有产品创意时 |
| 工程师 | 3 | ❌ | **新建**`demos/xxx/index.html` | 手动触发 |
