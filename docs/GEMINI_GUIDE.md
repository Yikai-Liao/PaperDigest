# Gemini API Integration Guide

本文档说明如何在 PaperDigest 项目中使用 Google Gemini API 进行论文摘要生成。

## 特性

### ✨ 主要功能

1. **自动模型检测**: 当配置文件中的模型名称以 `gemini` 开头时，自动使用 Google genai SDK
2. **双模式支持**:
   - **Direct API**: 即时生成结果，标准定价
   - **Batch API**: 24小时内完成，价格为标准价格的 50%
3. **完整的结构化输出**: 使用 Pydantic 模型确保输出格式一致
4. **错误处理和重试**: 内置错误处理机制

### 💰 成本优势

使用 Gemini 2.5 Flash + Batch API 可以显著降低成本：

| 模式 | 输入价格 | 输出价格 | 相对成本 |
|------|---------|---------|---------|
| Direct API | $0.075/1M tokens | $0.30/1M tokens | 100% |
| **Batch API** | **$0.0375/1M tokens** | **$0.15/1M tokens** | **50%** |

对于大规模处理（如每日推荐），使用 Batch API 可节省约 50% 的 API 费用。

## 配置

### 1. 获取 API Key

1. 访问 [Google AI Studio](https://aistudio.google.com/)
2. 创建或选择一个项目
3. 获取 API Key

### 2. 设置环境变量

```bash
export SUMMARY_API_KEY='your-gemini-api-key-here'
```

或者在 `config.toml` 中直接配置（不推荐用于生产环境）：

```toml
[summary]
api_key = "your-api-key"  # 不推荐
```

### 3. 配置文件设置

编辑 `config.toml`:

```toml
[summary]
api_key = "env"  # 从环境变量读取
base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"  # Gemini 不需要此设置，但保留兼容性
model = "gemini-2.5-flash"  # 或 "gemini-2.5-pro"
temperature = 0.1
top_p = 0.8
num_workers = 2  # Direct API 模式下的并行数

# Batch API 设置
use_batch_api = false  # true: Batch API (50% 折扣, 24h), false: Direct API (即时)
```

## 使用方法

### 方式一: 使用 Direct API (推荐用于测试)

适用于：
- 快速测试和验证
- 少量论文（<10篇）
- 需要即时结果

```bash
# 1. 运行预测模型
uv run python script/fit_predict.py

# 2. 下载 PDF
uv run python script/download_pdf.py

# 3. 提取文本
mkdir -p extracted_mds
uv run marker pdfs --disable_image_extraction --output_dir ./extracted_mds --workers 2

# 4. 生成摘要 (Direct API)
# 确保 config.toml 中 use_batch_api = false
uv run python script/summarize.py ./extracted_mds --lang zh
```

### 方式二: 使用 Batch API (推荐用于生产)

适用于：
- 大规模处理（>10篇论文）
- 成本敏感场景
- 不需要即时结果

```bash
# 1-3 步骤同上

# 4. 修改配置启用 Batch API
# 在 config.toml 中设置:
# use_batch_api = true

# 5. 生成摘要 (Batch API)
uv run python script/summarize.py ./extracted_mds --lang zh

# 6. 等待批处理完成
# Batch API 会自动轮询状态，目标在 24 小时内完成
# 通常会更快完成，具体取决于批次大小和系统负载
```

### 测试脚本

项目提供了测试脚本来验证配置：

```bash
# 完整的 pipeline 测试（包括 API 调用）
uv run python script/test_gemini_pipeline.py
```

## 架构说明

### 文件结构

```
script/
├── gemini_handler.py      # Gemini API 处理模块（新增）
├── summarize.py           # 摘要生成主脚本（已修改）
├── test_gemini_pipeline.py  # 测试脚本（新增）
└── ...
```

### 核心组件

#### 1. `gemini_handler.py`

独立的 Gemini API 处理模块，提供：

- `GeminiHandler` 类: 封装所有 Gemini API 交互
- `summarize_single()`: 单个论文的直接 API 调用
- `summarize_batch()`: 批量处理，支持 Batch API
- `prepare_batch_request()`: 准备批处理请求
- `create_batch_job()`: 创建批处理作业
- `wait_for_batch_completion()`: 轮询批处理状态
- `retrieve_batch_results()`: 获取批处理结果

#### 2. `summarize.py` 的修改

- 自动检测模型名称
- 当模型以 `gemini` 开头时，使用 `GeminiHandler`
- 其他模型仍使用原有的 OpenAI 兼容接口
- 支持通过配置文件切换 Direct/Batch API

### 工作流程

#### Direct API 模式

```
Paper (MD) → GeminiHandler.summarize_single() → API Call → JSON Result
```

#### Batch API 模式

```
Papers (MD) → GeminiHandler.prepare_batch_request() 
            → Create JSONL file
            → Upload to Gemini
            → Create Batch Job
            → Poll Status (30s interval)
            → Job Complete
            → Download Results
            → Parse JSONL
            → JSON Results
```

## 性能和成本对比

### 示例场景: 每日 13 篇论文

| 指标 | Direct API | Batch API |
|------|-----------|-----------|
| 处理时间 | ~26 分钟* | 24 小时内（通常 < 4 小时） |
| 估算成本 | ~$0.12 | ~$0.06 |
| 年度成本 | ~$44 | ~$22 |
| 适用场景 | 即时需求 | 定时任务 |

*假设并行度为 2，每篇约 2 分钟

### 优化建议

1. **开发/测试**: 使用 Direct API，小批量测试
2. **生产环境**: 使用 Batch API，定时任务（如每日凌晨运行）
3. **混合模式**: 
   - 紧急论文: Direct API
   - 常规批次: Batch API

## 错误处理

### 常见问题

1. **API Key 未设置**
   ```
   ValueError: Please provide a valid API key
   ```
   解决: `export SUMMARY_API_KEY='your-key'`

2. **模型未正确识别**
   - 检查 `config.toml` 中 `model` 是否以 `gemini` 开头
   - 当前支持: `gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-2.0-flash-exp` 等

3. **Batch API 超时**
   - 默认超时: 24 小时
   - 如果超时，检查 Google AI Studio 中的作业状态
   - 可以重新提交或拆分为更小的批次

### 日志和调试

脚本使用 `loguru` 进行日志记录：

```python
# 查看详细日志
export LOGURU_LEVEL=DEBUG
uv run python script/summarize.py ...
```

## CI/CD 集成

### GitHub Actions 工作流

Batch API 特别适合 CI/CD 环境：

```yaml
# .github/workflows/recommend.yaml
jobs:
  process_pdfs:
    steps:
      - name: AI 摘要
        env:
          SUMMARY_API_KEY: ${{ secrets.SUMMARY_API_KEY }}
        run: |
          # Batch API 会在 workflow 中等待完成
          python script/summarize.py ./extracted_mds/ --lang zh
```

由于 GitHub Actions 有 6 小时的超时限制，如果使用 Batch API:

1. **选项 1**: 拆分为多个较小的批次（推荐）
2. **选项 2**: 使用 Direct API（成本更高但不会超时）
3. **选项 3**: 将 Batch API 作业提交后保存作业 ID，后续步骤中检索结果

## 最佳实践

### 1. 成本控制

- 启用 Batch API 可节省 50% 成本
- 使用 `num_workers` 控制并发，避免速率限制
- 定期清理和复用缓存

### 2. 性能优化

- PDF 提取使用 `--disable_image_extraction` 加快处理
- 合理设置 `num_workers`（推荐 2-4）
- 使用 Batch API 处理大批量

### 3. 质量控制

- 设置合适的 `temperature`（推荐 0.1-0.3）
- 使用结构化输出确保格式一致
- 定期人工审核摘要质量

## 参考资源

- [Gemini API 文档](https://ai.google.dev/gemini-api/docs)
- [Batch API 指南](https://ai.google.dev/gemini-api/docs/batch-api?hl=zh-cn)
- [定价信息](https://ai.google.dev/gemini-api/docs/pricing?hl=zh-cn)
- [速率限制](https://ai.google.dev/gemini-api/docs/rate-limits?hl=zh-cn)

## 故障排除

如果遇到问题，运行测试脚本进行诊断：

```bash
uv run python script/test_gemini_pipeline.py
```

该脚本会检查：
- ✓ 配置文件
- ✓ API Key
- ✓ 预测结果
- ✓ PDF 文件
- ✓ 提取的文本
- ✓ API 连接
- ✓ 成本估算

## 更新日志

### 2025-10-01

- ✨ 新增 Gemini API 支持
- ✨ 新增 Batch API 模式（50% 成本节省）
- 🔧 重构 `summarize.py` 以支持多种 API
- 📝 新增 `gemini_handler.py` 模块
- 📝 新增测试和文档
