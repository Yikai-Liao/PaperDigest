# NaN 问题诊断报告

## 问题定位

根据代码分析,`fit_predict.py` 中的 NaN 检测在以下位置触发:

### 1. **Line 396** (主要检测点)
```python
x = np.hstack([np.vstack(combined_df[col].to_numpy()) for col in embedding_columns])
samples_with_nan = np.isnan(x).any(axis=1).sum()
logger.warning(f"{samples_with_nan}个样本 ({samples_with_nan/x.shape[0]*100:.2f}%) 包含NaN值")
```

### 2. **Line 233-239** (adaptive_difficulty_sampling)
```python
if np.isnan(x_pos).any():
    logger.warning(f"正样本数据中发现 NaN 值，将替换为 0")
if np.isnan(unlabeled_data).any():
    logger.warning(f"背景数据中发现 NaN 值，将替换为 0")
```

### 3. **Line 514** (预测阶段)
```python
nan_count = np.isnan(X_target).sum()
if nan_count > 0:
    logger.warning(f"预测数据中发现 {nan_count} 个 NaN 值，将替换为 0")
```

## 根本原因分析

你同事说 **`lyk/ArxivEmbedding` 数据集没有 NaN** 是正确的,但 NaN 可能在以下环节产生:

### 可能性 1: None 值转换 (最可能)
```python
# 当数据中有 None 时:
col_data = [vec1, vec2, None, vec3, ...]  # 某些论文的 embedding 为 None
arr = np.vstack(col_data)  # None 会被转换为 NaN
```

### 可能性 2: Join 操作产生缺失
```python
prefered_df = prefered_df.join(preferences, on="id", how="inner")
# 如果 join 后某些字段缺失,再用于 vstack 时会产生 NaN
```

### 可能性 3: 数据类型不匹配
```python
# 如果某些 embedding 的数据类型不一致 (float32 vs float64, list vs array)
# vstack 操作可能引入 NaN
```

### 可能性 4: 过滤后的空值
```python
# 某些过滤条件导致某些行的 embedding 列为空
remaining_df = remaining_df.filter(...)
# 过滤后可能产生空 embedding
```

## 解决方案

### 方案 1: 增强诊断 (推荐立即执行)

在 `fit_predict.py` 中添加详细的 NaN 来源追踪:

```python
# 在 train_model 函数 Line 390 之后添加:

# 🔍 诊断: 检查原始数据
logger.info(f"[NaN诊断] combined_df shape: {combined_df.shape}")
for col in embedding_columns:
    col_data = combined_df[col].to_list()
    none_count = sum(1 for x in col_data if x is None)
    if none_count > 0:
        logger.warning(f"[NaN诊断] 列 '{col}' 有 {none_count} 个 None 值")
        none_ids = [combined_df['id'][i] for i, x in enumerate(col_data) if x is None][:5]
        logger.warning(f"[NaN诊断] None 值的论文ID示例: {none_ids}")

# 🔍 诊断: 检查 vstack 每一步
arrays = []
for col in embedding_columns:
    col_arr = np.vstack(combined_df[col].to_numpy())
    nan_before = np.isnan(col_arr).sum()
    logger.info(f"[NaN诊断] 列 '{col}' vstack后: shape={col_arr.shape}, NaN={nan_before}")
    arrays.append(col_arr)

x = np.hstack(arrays)
nan_after = np.isnan(x).sum()
logger.info(f"[NaN诊断] hstack后: shape={x.shape}, NaN={nan_after}")
```

### 方案 2: 数据清洗 (根治方案)

如果确认是 None 值导致的,在数据加载后立即清洗:

```python
# 在 load_lazy_dataset 函数返回前添加:

def clean_none_embeddings(df: pl.DataFrame, embedding_columns: list) -> pl.DataFrame:
    """清除 embedding 为 None 的行"""
    original_size = df.height
    
    # 创建过滤条件: 所有 embedding 列都不为 None
    condition = pl.col(embedding_columns[0]).is_not_null()
    for col in embedding_columns[1:]:
        condition = condition & pl.col(col).is_not_null()
    
    df = df.filter(condition)
    
    removed = original_size - df.height
    if removed > 0:
        logger.warning(f"清除了 {removed} 个 embedding 为 None 的样本")
    
    return df

# 使用:
prefered_df = clean_none_embeddings(prefered_df, embedding_columns)
remaining_df = clean_none_embeddings(remaining_df, embedding_columns)
```

### 方案 3: 替换策略优化

当前代码使用 `np.nan_to_num(x, nan=0.0)` 简单替换为 0,但这可能影响模型性能。
更好的方案:

```python
# 方案 A: 移除含 NaN 的样本
nan_mask = np.isnan(x).any(axis=1)
x = x[~nan_mask]
y = y[~nan_mask]
logger.info(f"移除了 {nan_mask.sum()} 个含 NaN 的样本")

# 方案 B: 用该列的均值替换
for i, col in enumerate(embedding_columns):
    col_start = i * embedding_dim
    col_end = (i + 1) * embedding_dim
    col_data = x[:, col_start:col_end]
    col_mean = np.nanmean(col_data, axis=0)
    nan_mask = np.isnan(col_data)
    col_data[nan_mask] = np.take(col_mean, np.where(nan_mask)[1])
    x[:, col_start:col_end] = col_data
```

## 与同事反馈的协调

你同事说的 "ArxivEmbedding 上已经没有 NaN 和全 0 的 vector" 可能指:
1. **Parquet 文件本身存储时没有 NaN** - 这是对的
2. 但数据有 **None 值** (Python 的 None ≠ NumPy 的 NaN)
3. None 在 `np.vstack()` 转换时变成了 NaN

## 立即行动

请你同事执行以下 SQL 查询 (如果数据在数据库) 或 Python 检查:

```python
import polars as pl

# 检查 None 值
for year in [2023, 2024, 2025]:
    df = pl.scan_parquet(f"hf://datasets/lyk/ArxivEmbedding/{year}.parquet")
    
    for col in ["jasper_v1", "conan_v1"]:
        null_count = df.filter(pl.col(col).is_null()).count().collect()[0, 0]
        print(f"{year}.parquet - {col}: {null_count} null values")
```

如果有 null 值,那就是问题所在!

## 建议

1. **立即**: 在 `fit_predict.py` Line 390 后添加诊断代码 (方案1)
2. **短期**: 运行一次查看日志,确认是 None 还是其他原因
3. **长期**: 
   - 如果是 None 值: 使用方案2在数据加载时清洗
   - 如果是其他原因: 根据诊断日志进一步分析
   - 联系同事确认数据集中是否有 null 值(不只是 NaN)

## 测试方法

修改后运行:
```bash
python script/fit_predict.py
```

查看日志中的 `[NaN诊断]` 标记,就能精确知道:
1. 哪些论文的 embedding 是 None/NaN
2. 是在哪个步骤产生的
3. 影响了多少样本
