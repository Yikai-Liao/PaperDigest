# NaN 诊断功能使用指南

## 概述

已在 `fit_predict.py` 中添加了详细的 NaN 诊断日志,可以帮助精确定位 NaN 值的来源。

## 诊断点

### 1. **训练数据准备阶段** (Line ~390)
在 `train_model()` 函数中,`combined_df` 转换为 numpy 数组之前:

```
[NaN诊断] 开始检查 combined_df 中的 None/NaN 值
[NaN诊断] 列 'jasper_v1' 有 X 个 None 值 (X.XX%)
[NaN诊断] None 值的论文ID示例: ['2401.xxxxx', ...]
[NaN诊断] 开始逐列转换为 numpy 数组
[NaN诊断] 列 'jasper_v1' vstack后: shape=(N, 768), NaN数量=X
[NaN诊断] 列 'conan_v1' vstack后: shape=(N, 1024), NaN数量=X
[NaN诊断] hstack后: shape=(N, 1792)
[NaN诊断] 最终检测: X个样本 (X.XX%) 包含NaN值
```

### 2. **自适应难度采样阶段** (Line ~233)
在 `adaptive_difficulty_sampling()` 函数中:

```
[NaN诊断-ADS] x_pos shape: (N, 1792), unlabeled_data shape: (M, 1792)
[NaN诊断-ADS] ✅ 正样本数据没有 NaN
[NaN诊断-ADS] 背景数据中发现 X 个 NaN 值，将替换为 0
[NaN诊断-ADS] 背景数据中有 Y 行包含 NaN
```

### 3. **预测阶段** (Line ~555)
在 `predict_and_recommend()` 函数中:

```
[NaN诊断-预测] 开始检查预测数据中的 None/NaN 值
[NaN诊断-预测] 列 'jasper_v1' 有 X 个 None 值 (X.XX%)
[NaN诊断-预测] 列 'jasper_v1' vstack后有 X 个 NaN
[NaN诊断-预测] X_target shape: (N, 1792)
[NaN诊断-预测] 最终检测: 预测数据中发现 X 个 NaN 值 (X.XXXX%)，将替换为 0
[NaN诊断-预测] 有 Y 行包含 NaN
```

## 如何使用

### 运行脚本查看诊断信息

```bash
# 运行 fit_predict
python script/fit_predict.py

# 或者只查看 NaN 相关的日志
python script/fit_predict.py 2>&1 | grep "NaN诊断"
```

### 理解输出

1. **None 值检测**
   - 如果看到 `X 个 None 值`,说明数据源中某些论文的 embedding 字段为 None/null
   - 这是**数据质量问题**,应该在数据生产阶段修复

2. **vstack 后 NaN 检测**
   - 如果 None 值为 0 但 vstack 后有 NaN,可能是:
     - 向量长度不一致导致的填充
     - 数据类型转换问题
     - 某些特殊值 (Inf, -Inf) 被转换为 NaN

3. **行数统计**
   - `Y 行包含 NaN`: 告诉你有多少个样本受影响
   - 如果比例很小 (<1%),用 0 填充影响不大
   - 如果比例较大 (>5%),应该考虑数据清洗或修复

### 根据诊断结果采取行动

#### 场景 1: 发现大量 None 值
```
[NaN诊断] 列 'jasper_v1' 有 50 个 None 值 (10.00%)
[NaN诊断] None 值的论文ID示例: ['2401.12345', '2402.23456', ...]
```

**行动**: 
1. 检查这些论文ID在 `lyk/ArxivEmbedding` 数据集中的状态
2. 联系数据生产团队修复这些论文的 embedding
3. 临时解决: 在 `load_lazy_dataset()` 中过滤掉这些论文

```python
# 在 load_lazy_dataset 返回前添加
prefered_df = prefered_df.filter(
    pl.col("jasper_v1").is_not_null() & 
    pl.col("conan_v1").is_not_null()
)
remaining_df = remaining_df.filter(
    pl.col("jasper_v1").is_not_null() & 
    pl.col("conan_v1").is_not_null()
)
```

#### 场景 2: vstack 后出现 NaN (但没有 None 值)
```
[NaN诊断] 列 'jasper_v1' 有 0 个 None 值
[NaN诊断] 列 'jasper_v1' vstack后: shape=(500, 768), NaN数量=384
```

**行动**:
1. 检查向量维度是否一致
2. 检查数据类型 (应该都是 float32/float64)
3. 可能需要在数据加载后立即检查每个向量的有效性

添加额外诊断:
```python
# 在 combined_df 创建后
for col in embedding_columns:
    col_data = combined_df[col].to_list()
    # 检查向量长度
    lengths = [len(x) if x is not None else 0 for x in col_data]
    unique_lengths = set(lengths)
    if len(unique_lengths) > 1:
        logger.warning(f"列 {col} 向量长度不一致: {unique_lengths}")
    
    # 检查数据类型
    dtypes = [type(x).__name__ if x is not None else 'None' for x in col_data[:10]]
    logger.info(f"列 {col} 前10个数据类型: {dtypes}")
```

#### 场景 3: 没有 NaN 检测到
```
[NaN诊断] ✅ 最终检测: 没有NaN值!
[NaN诊断-ADS] ✅ 正样本数据没有 NaN
[NaN诊断-预测] ✅ 预测数据没有 NaN
```

**行动**:
- 太好了! 数据质量没问题
- 可以考虑移除 `np.nan_to_num()` 调用以提高性能
- 或者保留它作为防御性编程

## 性能优化

如果确认没有 NaN 问题,可以:

1. **移除诊断代码** (生产环境)
   ```python
   # 注释掉所有 [NaN诊断] 相关的代码块
   ```

2. **简化 NaN 检测**
   ```python
   # 从详细检测改为快速检测
   if np.isnan(x).any():
       logger.warning("检测到NaN值")
       x = np.nan_to_num(x, nan=0.0)
   ```

3. **在数据加载阶段就过滤**
   ```python
   # 在 load_lazy_dataset 中预先过滤
   lazy_df = lazy_df.filter(
       pl.col("jasper_v1").is_not_null() & 
       pl.col("conan_v1").is_not_null()
   )
   ```

## 与同事协作

### 给数据生产团队的报告模板

```
发现数据质量问题:

数据集: lyk/ArxivEmbedding
年份: 2024, 2025
问题: 以下论文的 embedding 为 None/null

受影响的论文ID:
- 2401.12345 (jasper_v1 为 null)
- 2402.23456 (conan_v1 为 null)
- ...

影响范围: 总共 X 个论文 (占比 Y%)

请检查这些论文的 embedding 生成过程,并修复数据集。

诊断日志:
[附上 fit_predict.py 的诊断输出]
```

### 验证修复

数据修复后,重新运行脚本:
```bash
python script/fit_predict.py 2>&1 | grep "NaN诊断"
```

应该看到:
```
[NaN诊断] ✅ 最终检测: 没有NaN值!
[NaN诊断-ADS] ✅ 正样本数据没有 NaN
[NaN诊断-ADS] ✅ 背景数据没有 NaN
[NaN诊断-预测] ✅ 预测数据没有 NaN
```

## FAQ

**Q: 为什么同事说没有 NaN,但脚本还是检测到?**

A: 
1. 同事可能检查的是原始 parquet 文件中的向量数据 (存储的二进制格式没有 NaN)
2. 但数据中有 `null` 值 (不是 NaN,是缺失值)
3. Python 的 `None` 在转换为 numpy 数组时变成了 `NaN`
4. 所以源头问题是 **数据缺失** (null),不是 **数据错误** (NaN)

**Q: 用 0 填充 NaN 会影响模型性能吗?**

A:
- 如果 NaN 比例 < 1%: 影响很小
- 如果 NaN 比例 1-5%: 有一定影响,但可接受
- 如果 NaN 比例 > 5%: 严重影响,必须修复数据源

更好的策略:
1. **过滤**: 直接移除含 NaN 的样本 (推荐)
2. **插值**: 用列均值填充
3. **特殊标记**: 用一个特殊向量 (如全 -1) 标记缺失

**Q: 如何验证数据集中是否真的有 null 值?**

A: 让同事运行:
```python
import polars as pl

for year in [2023, 2024, 2025]:
    df = pl.scan_parquet(f"hf://datasets/lyk/ArxivEmbedding/{year}.parquet")
    
    for col in ["jasper_v1", "conan_v1"]:
        null_count = df.filter(pl.col(col).is_null()).count().collect()[0, 0]
        total = df.count().collect()[0, 0]
        print(f"{year} - {col}: {null_count}/{total} null values ({null_count/total*100:.2f}%)")
```

## 后续行动清单

- [ ] 运行 fit_predict.py 查看诊断日志
- [ ] 识别 NaN 来源 (None 值 vs 转换问题)
- [ ] 如果有 None 值,收集受影响的论文ID
- [ ] 联系数据团队修复源数据
- [ ] 临时方案: 在 load_lazy_dataset 中过滤 null 值
- [ ] 验证修复后没有 NaN
- [ ] (可选) 移除诊断代码以优化性能
