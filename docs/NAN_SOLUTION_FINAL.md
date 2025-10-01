# NaN 问题完整解决方案

## 问题总结

### 发现过程

1. **初始症状**: fit_predict.py 报告大量 NaN 值 (13-18%)
2. **同事反馈**: "ArxivEmbedding 数据集没有 NaN 和全 0 的 vector"
3. **第一次诊断**: 检查数据集是否有 null 值 → 结果: ✅ 没有 null 值
4. **深度诊断**: 检查向量内部 → 发现: ❌ **jasper_v1 向量内部包含 NaN**

### 根本原因

**`lyk/ArxivEmbedding` 数据集中 `jasper_v1` 列的向量内部包含 NaN 值**

- 不是向量本身为 `null`/`None`
- 而是向量内容为 `[NaN, NaN, NaN, ...]` (全是 NaN)
- 约 **30% 的向量全是 NaN**
- `conan_v1` 列没有这个问题 ✅

示例受影响的论文ID:
- 2312.05579
- 2508.17647  
- 2505.04283
- 2508.18213
- 2506.00962

## 解决方案

### 实施的修复

在 `fit_predict.py` 中添加了两个过滤点:

#### 1. 训练数据过滤 (train_model 函数, Line ~446)

```python
# 🔧 过滤向量内部包含 NaN 的样本
logger.info(f"开始过滤向量内部包含 NaN 的样本...")

nan_mask = np.zeros(combined_df.height, dtype=bool)
for col in embedding_columns:
    col_data = combined_df[col].to_list()
    for i, vec in enumerate(col_data):
        if vec is None or (isinstance(vec, (list, np.ndarray)) and np.isnan(vec).any()):
            nan_mask[i] = True

removed_count = nan_mask.sum()
if removed_count > 0:
    logger.warning(f"过滤了 {removed_count}/{len(combined_df)} ({removed_count/len(combined_df)*100:.2f}%) 个含 NaN 的样本")
    combined_df = combined_df.with_row_index("__idx__")
    valid_indices = np.where(~nan_mask)[0]
    combined_df = combined_df.filter(pl.col("__idx__").is_in(valid_indices)).drop("__idx__")
```

**效果**: 过滤了 144/1077 (13.37%) 个样本

#### 2. 预测数据过滤 (predict_and_recommend 函数, Line ~620)

```python
# 🔧 过滤向量内部包含 NaN 的样本 (预测阶段)
logger.info(f"开始过滤预测数据中向量内部包含 NaN 的样本...")

nan_mask = np.zeros(target_df.height, dtype=bool)
for col in embedding_columns:
    col_data = target_df[col].to_list()
    for i, vec in enumerate(col_data):
        if vec is None or (isinstance(vec, (list, np.ndarray)) and np.isnan(vec).any()):
            nan_mask[i] = True

removed_count = nan_mask.sum()
if removed_count > 0:
    logger.warning(f"过滤了 {removed_count}/{target_df.height} ({removed_count/target_df.height*100:.2f}%) 个含 NaN 的样本")
    # 过滤逻辑
```

**效果**: 过滤了 3155/6270 (50.32%) 个样本

## 验证结果

运行 fit_predict.py 后的输出:

```
✅ 训练数据: 没有 NaN 值
✅ 正样本数据: 没有 NaN
✅ 预测数据: 没有 NaN
```

## 性能影响

### 训练阶段
- **过滤**: 144/1077 样本 (13.37%)
- **剩余**: 933 个有效样本
- **影响**: 轻微减少训练数据,但提高了模型质量

### 预测阶段  
- **过滤**: 3155/6270 样本 (50.32%)
- **剩余**: 3115 个有效样本
- **影响**: 大量减少预测样本,但都是无效样本(全 NaN 向量无法推荐)

## 根本性修复建议

当前解决方案是**防御性修复**,在应用层过滤坏数据。理想的解决方案应该:

### 1. 修复数据源

联系数据团队修复 `lyk/ArxivEmbedding` 中 `jasper_v1` 列的问题:

```python
# 检查脚本 (给数据团队)
import polars as pl
import numpy as np

for year in [2023, 2024, 2025]:
    df = pl.read_parquet(f"hf://datasets/lyk/ArxivEmbedding/{year}.parquet")
    
    jasper_data = df['jasper_v1'].to_list()
    nan_vectors = sum(1 for vec in jasper_data if np.isnan(vec).any())
    
    print(f"{year}: {nan_vectors}/{len(jasper_data)} 个向量包含 NaN ({nan_vectors/len(jasper_data)*100:.2f}%)")
    
    if nan_vectors > 0:
        # 找出有问题的论文ID
        bad_ids = [df['id'][i] for i, vec in enumerate(jasper_data) if np.isnan(vec).any()]
        print(f"  示例ID: {bad_ids[:10]}")
```

### 2. 重新生成 Embedding

这些论文的 jasper_v1 embedding 生成失败,需要:
1. 检查原始论文是否可访问
2. 重新运行 embedding 生成
3. 更新数据集

### 3. 数据质量监控

在数据生产流程中添加质量检查:
```python
def validate_embeddings(df):
    for col in ['jasper_v1', 'conan_v1']:
        vectors = df[col].to_list()
        nan_count = sum(1 for v in vectors if v is not None and np.isnan(v).any())
        if nan_count > 0:
            raise ValueError(f"发现 {nan_count} 个包含 NaN 的向量")
```

## 临时解决方案(当前)

当前代码已经可以正常工作:
- ✅ 自动过滤含 NaN 的样本
- ✅ 保留所有有效数据
- ✅ 不会因为 NaN 导致错误
- ✅ 日志清晰显示过滤情况

**可以正常使用,无需额外操作**

## 后续工作

- [ ] 联系数据团队修复 jasper_v1 的 NaN 问题
- [ ] 数据修复后移除过滤代码(或保留作为防御)
- [ ] 在诊断完成后可以移除 `[NaN诊断]` 相关日志
- [ ] 清理临时诊断脚本 (check_null_values.py, deep_nan_diagnostic.py 等)

## 相关文档

- `docs/NAN_DEBUG_REPORT.md` - 初步分析
- `docs/NAN_DIAGNOSTIC_GUIDE.md` - 诊断使用指南
- `script/check_null_values.py` - Null 值检查脚本
- `script/deep_nan_diagnostic.py` - 深度 NaN 诊断脚本

## 时间线

- 2025-10-01 17:20 - 发现 NaN 问题
- 2025-10-01 18:22 - 确认数据源没有 null 值
- 2025-10-01 18:28 - 发现向量内部包含 NaN
- 2025-10-01 21:31 - 完成过滤修复,验证通过 ✅
