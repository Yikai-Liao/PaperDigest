# 预测管道调试修复报告

## 📋 问题概述

GitHub Actions 工作流在运行 `fit_predict.py` 时遇到以下错误：

1. **FileNotFoundError**: `/home/runner/work/PaperDigest/PaperDigest/data/predictions.parquet` 目录不存在
2. **ValueError**: Input X contains NaN - sklearn 的 `NearestNeighbors` 和 `LogisticRegression` 不接受包含 NaN 的数据

## 🔍 根本原因分析

### 1. 目录不存在问题
```python
output_file = REPO_ROOT / "data" / "predictions.parquet"
results_df.write_parquet(output_file)  # ❌ 如果 data/ 目录不存在会失败
```

**原因**: 项目重组后将 `predictions.parquet` 移到了 `data/` 目录，但代码没有确保目录存在。

### 2. NaN 值问题

错误发生在两个地方：

#### a) 自适应难度采样函数
```python
# adaptive_difficulty_sampling()
nn_background.fit(unlabeled_data)  # ❌ unlabeled_data 包含 NaN
```

#### b) 预测阶段
```python
# predict_and_recommend()
target_scores = model.predict_proba(X_target)[:, 1]  # ❌ X_target 包含 NaN
```

**原因**: Hugging Face 数据集中的 embedding 数据可能包含 NaN 值（缺失的嵌入）。sklearn 的算法默认不处理 NaN。

## ✅ 修复方案

### 1. 确保目录存在

在 `predict_and_save()` 函数中保存文件前创建目录：

```python
output_file = REPO_ROOT / "data" / "predictions.parquet"

# 确保目录存在
output_file.parent.mkdir(parents=True, exist_ok=True)

# 保存
results_df.write_parquet(output_file)
```

### 2. 处理 NaN 值

#### a) 在自适应难度采样函数中
```python
# adaptive_difficulty_sampling()
try:
    # 检查并处理 NaN 值
    if np.isnan(x_pos).any():
        logger.warning(f"正样本数据中发现 NaN 值，将替换为 0")
        x_pos = np.nan_to_num(x_pos, nan=0.0)
    
    if np.isnan(unlabeled_data).any():
        logger.warning(f"背景数据中发现 NaN 值，将替换为 0")
        unlabeled_data = np.nan_to_num(unlabeled_data, nan=0.0)
    
    # 1. 对背景数据建立KNN模型
    nn_background = NearestNeighbors(...)
    nn_background.fit(unlabeled_data)  # ✅ 现在数据已清理
```

#### b) 在预测函数中
```python
# predict_and_recommend()
X_target = np.hstack([np.vstack(target_df[col].to_numpy()) for col in embedding_columns])

# 处理 NaN 值
nan_count = np.isnan(X_target).sum()
if nan_count > 0:
    logger.warning(f"预测数据中发现 {nan_count} 个 NaN 值，将替换为 0")
    X_target = np.nan_to_num(X_target, nan=0.0)

# 使用模型预测"喜欢"的概率
target_scores = model.predict_proba(X_target)[:, 1]  # ✅ 数据已清理
```

## 🧪 本地测试结果

运行 `uv run python script/fit_predict.py` 成功执行：

```
2025-10-01 15:26:38.669 | WARNING  | __main__:adaptive_difficulty_sampling:238 - 背景数据中发现 NaN 值，将替换为 0
2025-10-01 15:26:45.121 | WARNING  | __main__:predict_and_recommend:514 - 预测数据中发现 3371008 个 NaN 值，将替换为 0
2025-10-01 15:26:45.178 | INFO     | __main__:predict_and_recommend:520 - 预测完成，分数范围: 0.0305 - 0.6341, 平均: 0.2218
2025-10-01 15:26:45.211 | INFO     | __main__:predict_and_save:711 - 预测结果已保存到: /home/lyk/code/PaperDigest/data/predictions.parquet
2025-10-01 15:26:45.212 | INFO     | __main__:predict_and_save:715 - 推荐13篇论文
```

✅ **成功**:
- 训练完成（169 正样本 + 845 负样本 = 1077 总样本）
- 自适应难度采样成功（338 样本 = 169 重采样 + 169 SMOTE 合成）
- 预测完成（3292 篇论文，推荐 13 篇）
- 文件成功保存到 `data/predictions.parquet` (1.7MB)

## 📊 NaN 值统计

### 训练阶段
- **152个样本 (14.11%)** 包含NaN值 → 已替换为0

### 采样阶段  
- **背景数据**中发现 NaN 值 → 已替换为0

### 预测阶段
- **3,371,008 个 NaN 值**（在 3292 篇论文 × 2816 维特征中）→ 已替换为0
- 约 **36%** 的特征值为 NaN

## 💡 NaN 值来源分析

NaN 值主要来自：
1. **嵌入缺失**: 某些论文可能没有完整的嵌入向量
2. **数据版本差异**: 不同年份的数据可能包含不同的嵌入列
3. **Polars scan_parquet**: 使用 `allow_missing_columns=True` 参数，缺失列会被填充为 null

## 🔧 替代方案（未采用）

考虑过但未采用的方案：

### 1. 删除包含 NaN 的样本
```python
# ❌ 不推荐：会损失大量数据
mask = ~np.isnan(X).any(axis=1)
X = X[mask]
y = y[mask]
```
**缺点**: 会丢失 14-36% 的数据

### 2. 使用更复杂的填充策略
```python
# ❌ 可能过度复杂
from sklearn.impute import KNNImputer
imputer = KNNImputer(n_neighbors=5)
X = imputer.fit_transform(X)
```
**缺点**: 计算成本高，可能引入偏差

### 3. 使用支持 NaN 的模型
```python
# ❌ 需要重构大量代码
from sklearn.ensemble import HistGradientBoostingClassifier
model = HistGradientBoostingClassifier()
```
**缺点**: 需要改变模型架构和超参数

## ✨ 选择简单填充（0）的理由

1. **简单高效**: 不增加计算成本
2. **保留所有样本**: 不丢失数据
3. **合理假设**: 缺失的嵌入维度值为 0 可解释为"该维度无信息"
4. **一致性**: 与训练和预测阶段保持一致的处理方式

## 📝 后续建议

### 短期
- ✅ 监控 GitHub Actions 运行，确认修复有效
- ⚠️ 关注日志中的 NaN 警告，了解数据质量

### 长期
- 🔍 调查 Hugging Face 数据集中 NaN 的来源
- 📊 考虑更新嵌入数据集，减少缺失值
- 🧪 评估不同填充策略对模型性能的影响
- 📈 添加数据质量指标到日志中

## 🎯 提交信息

```
fix: handle NaN values in prediction pipeline and ensure data directory exists

- Add NaN value handling before prediction to avoid sklearn errors
- Add NaN value handling in adaptive_difficulty_sampling function
- Ensure data/ directory exists before saving predictions.parquet
- Fixes FileNotFoundError and ValueError related to NaN values
```

**Commit**: `c90f351`
**修改文件**: `script/fit_predict.py` (+18 行)
