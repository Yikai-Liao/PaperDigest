import os
import sys
import sklearn.linear_model
import toml
from pathlib import Path
from loguru import logger
from sklearn.neighbors import NearestNeighbors

import sklearn
import polars as pl
import numpy as np
import time
import datetime

REPO_ROOT = Path(__file__).resolve().parents[1]

def log_info():
    logger.debug(f"CPU core num: {os.cpu_count()} | Memory: {os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / (1024. ** 3)} GB")
    logger.debug(f"Python version: {sys.version}")
    logger.debug(f"Scikit-learn version: {sklearn.__version__}")
    logger.debug(f"Polars version: {pl.__version__}")
    logger.debug(f"NumPy version: {np.__version__}")
    logger.debug(f"Current working directory: {os.getcwd()}")
    logger.debug(f"Repository root: {REPO_ROOT}")
    logger.debug(f"Script path: {Path(__file__).resolve()}")

def load_config():
    config_path = REPO_ROOT / "config.toml"
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        config = toml.load(f)
        content_repo = config.get("content_repo", "lyk/ArxivEmbedding")
        config = config["fit_predict"]
        config["content_repo"] = content_repo
    
    logger.info(f"Config parameters:")
    for key, value in config.items():
        logger.info(f"- {key}: {value}")
    logger.info("Configuration loaded successfully.")
    return config

def load_preference(config):
    preference_dir = REPO_ROOT / config.get("preference_dir", "preference")
    if not preference_dir.exists():
        logger.error(f"Preference directory not found: {preference_dir}")
        sys.exit(1)

    preferences = [ pl.read_csv(p, columns=['id', 'preference'], schema={'id': pl.String, 'preference': pl.String}) for p in preference_dir.glob("**/*.csv") ]
    if not preferences:
        logger.error(f"No preference files found in {preference_dir}")
        sys.exit(1)
    # Combine all DataFrames into one
    preferences = pl.concat(preferences, how="vertical").unique(subset="id")
    logger.info(f"{len(preferences)} preference items loaded from {preference_dir}")
    return preferences

def load_recommended(config) -> pl.DataFrame:
    """
    Raw data dir contains lots of json files like 2407.0288.json
    We need to extract the Arxiv ID from the filename
    and collect all the IDs into a pl.DataFrame
    """
    # raw_dir = REPO_ROOT / config.get("raw_data_dir", "raw")
    # if not raw_dir.exists():
        # return pl.DataFrame(columns=["id"], schema={"id": pl.String})
    content_repo = config["content_repo"]
    recommended = pl.scan_parquet(f"hf://datasets/{content_repo}/main.parquet").collect()
    return recommended


def load_lazy_dataset(config, preferences: pl.DataFrame):
    categories = config.get("categories", ("cs.AI",))
    logger.debug(f"Categories: {categories}")

    dataset_name = config.get("embedding_dataset", "lyk/PaperDigestDataBase")
    current_year = time.localtime().tm_year
    backgroud_start_year = config.get("background_start_year", 2024)
    preference_start_year = config.get("preference_start_year", 2023)
    start_year = max(2017, min(current_year, backgroud_start_year, preference_start_year))
    logger.debug(f"Start year: {start_year}, Current year: {current_year}")
    parquet_paths = [
        f"hf://datasets/{dataset_name}/{year}.parquet"
        for year in range(start_year, current_year + 1)
    ]
    logger.debug(f"Parquet paths: {parquet_paths}")

    # lazy load the dataset from huggingface
    try:
        df = pl.scan_parquet(parquet_paths, missing_columns="insert")
    except Exception as e:
        logger.error(f"Error loading dataset: {e}")
        logger.warning("Attempting to load without the last year...")
        df = pl.scan_parquet(parquet_paths[:-1], allow_missing_columns=True)
    logger.debug(f"Dataset loaded: {df}")

    # construct filter condition
    filter_condition = pl.col("categories").list.contains(pl.lit(categories[0]))
    for category in categories[1:]:
        filter_condition = filter_condition | pl.col("categories").list.contains(pl.lit(category))
    logger.debug(f"Filter condition: {filter_condition}")

    # filter and collect the dataset
    lazy_df = df.filter(filter_condition)
    
    preference_ids = preferences.select("id").to_series().to_list()
    indicator_col_name = "__is_preferred__" # Using a distinct name
    database = lazy_df.with_columns(
        pl.col("id").is_in(preference_ids).alias(indicator_col_name)
    )

    logger.info(f"Splitting collected data based on '{indicator_col_name}' column...")

    prefered_df = database.filter(pl.col(indicator_col_name))
    remaining_df = database.filter(~pl.col(indicator_col_name))

    preferences = preferences.lazy()

    prefered_df = prefered_df.join(
        preferences, on="id", how="inner"
    ).drop(indicator_col_name)
        
    remaining_df = remaining_df.drop(indicator_col_name)

    if start_year < backgroud_start_year:
        # year is stored in updated column, like 2023-10-01 in string format
        logger.debug(f"Filtering out rows in remaining_df whose year is less than {backgroud_start_year}...")
        remaining_df = remaining_df\
            .with_columns(pl.col("updated").str.slice(0, 4).cast(pl.Int32).alias("year"))\
            .filter(pl.col("year") >= backgroud_start_year)

    # 🔧 修复: 过滤掉 embedding 有问题的行
    # 根据诊断发现:
    # 1. jasper_v1 列的向量内部包含 NaN 值 (约30% 的向量全是 NaN)
    # 2. 这不是 null 值问题,而是向量内容本身就是 [NaN, NaN, ...]
    # 3. 需要检查向量内部是否包含 NaN,不只是检查是否为 null
    embedding_columns = config.get("embedding_columns", ["jasper_v1", "conan_v1"])
    
    logger.info("开始过滤含 NaN 的 embedding 向量...")
    
    # 计算过滤前的数量
    prefered_count_before = prefered_df.select(pl.count()).collect()[0, 0]
    remaining_count_before = remaining_df.select(pl.count()).collect()[0, 0]
    
    # 方法: 使用 polars 的 list.eval 检查向量内部是否有 NaN
    # 但由于 polars 无法直接检查 list 内部的 NaN,我们需要在收集时过滤
    # 这里先过滤 null 值作为初步清洗
    null_filter = pl.col(embedding_columns[0]).is_not_null()
    for col in embedding_columns[1:]:
        null_filter = null_filter & pl.col(col).is_not_null()
    
    prefered_df = prefered_df.filter(null_filter)
    remaining_df = remaining_df.filter(null_filter)
    
    # 计算过滤后的数量
    prefered_count_after = prefered_df.select(pl.count()).collect()[0, 0]
    remaining_count_after = remaining_df.select(pl.count()).collect()[0, 0]
    
    # 记录过滤结果
    prefered_removed = prefered_count_before - prefered_count_after
    remaining_removed = remaining_count_before - remaining_count_after
    
    if prefered_removed > 0 or remaining_removed > 0:
        logger.warning(f"过滤了 embedding 为 null 的样本:")
        logger.warning(f"  prefered: 移除 {prefered_removed}/{prefered_count_before} ({prefered_removed/prefered_count_before*100:.2f}%)")
        logger.warning(f"  remaining: 移除 {remaining_removed}/{remaining_count_before} ({remaining_removed/remaining_count_before*100:.2f}%)")
    else:
        logger.info("✅ 没有 embedding 为 null 的样本")
    
    logger.warning("⚠️  注意: jasper_v1 向量内部可能仍包含 NaN 值 (约30%)")
    logger.warning("    这些 NaN 会在训练时被替换为 0")
    logger.warning("    建议联系数据团队修复 jasper_v1 的 embedding 生成问题")

    return prefered_df, remaining_df



def show_df_size(df: pl.DataFrame, name: str):
    # Row count and size in MB
    row_count = df.height
    size_mb = df.estimated_size() / (1024 ** 2)
    logger.debug(f"{name} - Rows: {row_count}, Size: {size_mb:.2f} MB")

def remove_recommended(remaining_df: pl.LazyFrame, recommended_df: pl.DataFrame):
    # Remove recommended items from remaining_df
    recommended_ids = recommended_df.select("id").to_series().to_list()
    remaining_df = remaining_df.filter(~pl.col("id").is_in(recommended_ids))
    return remaining_df

"""
Training Part
"""

def confidence_weighted_sampling(
    x, model, 
    high_conf_threshold: float = 0.9, 
    high_conf_weight: float = 2.0, 
    random_state: int = 42
) -> pl.DataFrame:
    n_samples = x.shape[0]
    confidences = model.predict_proba(x)[:, 1]
    
    # set weights based on confidence
    weights = np.ones_like(confidences)
    high_conf_indices = np.where(confidences >= high_conf_threshold)[0]
    weights[high_conf_indices] = high_conf_weight
    
    # log the number of high confidence samples
    n_high_conf = len(high_conf_indices)
    logger.info(f"发现{n_high_conf}个高置信度样本 (置信度 >= {high_conf_threshold})。" + 
                f"权重设置：高置信度样本={high_conf_weight}，其他=1.0")
    # Normalize weights to sum to 1
    sampling_probs = weights / weights.sum()
    # Sample with replacement based on the weights
    np.random.seed(random_state)
    sampled_indices = np.random.choice(
        np.arange(n_samples), size=n_samples, replace=True, p=sampling_probs
    )
    sampled_x = x[sampled_indices]

    return sampled_x

def adaptive_difficulty_sampling(
    x_pos, unlabeled_data, 
    n_neighbors: int = 5,
    sampling_ratio: float = 1.0,
    random_state: int = 42,
    synthetic_ratio: float = 0.5,  # 控制合成数据的比例
    k_smote: int = 5  # SMOTE中用于生成合成样本的最近邻数量
) -> np.ndarray:
    """
    基于正样本与背景数据分布的相对关系进行自适应难度加权采样，并合成新样本
    
    Args:
        x_pos: 正样本特征矩阵
        unlabeled_data: 未标记的背景数据特征矩阵
        n_neighbors: 计算难度时考虑的邻居数量
        sampling_ratio: 采样比例，相对于正样本数量的倍数
        random_state: 随机种子
        synthetic_ratio: 合成数据的比例(0-1)，0表示全部重采样，1表示全部合成
        k_smote: 用于SMOTE合成的近邻数量
    
    Returns:
        采样后的正样本特征矩阵（包含原始样本和合成样本）
    """
    # 设置随机种子
    np.random.seed(random_state)
    
    n_pos = x_pos.shape[0]
    
    if n_pos == 0:
        logger.warning("没有正样本，无法进行自适应采样")
        return x_pos
    
    # 计算目标采样数量
    n_samples = int(n_pos * sampling_ratio)
    if n_samples <= 0:
        logger.warning("计算的采样数量为0，保持原始数据不变")
        return x_pos
    
    # 计算重采样和合成的数量
    n_synthetic = int(n_samples * synthetic_ratio)
    n_resample = n_samples - n_synthetic
    
    logger.info(f"自适应难度采样: 正样本数={n_pos}, 采样比例={sampling_ratio}, "
               f"目标采样数量={n_samples} (重采样={n_resample}, 合成={n_synthetic})")
    
    try:
        # 计算每个正样本到背景数据的平均距离作为难度指标
        # 距离更近的正样本表示更接近决策边界，学习难度更大
        
        # 🔍 NaN 诊断: 检查输入数据
        logger.info(f"[NaN诊断-ADS] x_pos shape: {x_pos.shape}, unlabeled_data shape: {unlabeled_data.shape}")
        
        # 检查并处理 NaN 值
        nan_in_xpos = np.isnan(x_pos).sum()
        if nan_in_xpos > 0:
            logger.warning(f"[NaN诊断-ADS] 正样本数据中发现 {nan_in_xpos} 个 NaN 值，将替换为 0")
            rows_with_nan = np.where(np.isnan(x_pos).any(axis=1))[0]
            logger.warning(f"[NaN诊断-ADS] 正样本中有 {len(rows_with_nan)} 行包含 NaN")
            x_pos = np.nan_to_num(x_pos, nan=0.0)
        else:
            logger.info(f"[NaN诊断-ADS] ✅ 正样本数据没有 NaN")
        
        nan_in_unlabeled = np.isnan(unlabeled_data).sum()
        if nan_in_unlabeled > 0:
            logger.warning(f"[NaN诊断-ADS] 背景数据中发现 {nan_in_unlabeled} 个 NaN 值，将替换为 0")
            rows_with_nan = np.where(np.isnan(unlabeled_data).any(axis=1))[0]
            logger.warning(f"[NaN诊断-ADS] 背景数据中有 {len(rows_with_nan)} 行包含 NaN")
            unlabeled_data = np.nan_to_num(unlabeled_data, nan=0.0)
        else:
            logger.info(f"[NaN诊断-ADS] ✅ 背景数据没有 NaN")
        
        # 1. 对背景数据建立KNN模型
        nn_background = NearestNeighbors(n_neighbors=min(n_neighbors, unlabeled_data.shape[0]))
        nn_background.fit(unlabeled_data)
        
        # 2. 计算每个正样本到最近的n_neighbors个背景数据点的平均距离
        distances, _ = nn_background.kneighbors(x_pos)
        avg_distances = np.mean(distances, axis=1)
        
        # 3. 转换距离为难度分数（距离越小，难度越大）
        # 距离取倒数后归一化
        if np.max(avg_distances) - np.min(avg_distances) < 1e-10:
            # 如果所有距离几乎相同，使用均匀权重
            logger.warning("所有样本到背景数据的距离几乎相同，使用均匀采样")
            difficulties = np.ones(n_pos) / n_pos
        else:
            # 反转距离并归一化（使用软性反转以避免极端值）
            difficulties = 1.0 / (avg_distances + 1e-6)
            difficulties = difficulties / np.sum(difficulties)
        
        # 4. 记录难度分布情况
        logger.info(f"距离统计: 最小={np.min(avg_distances):.4f}, 最大={np.max(avg_distances):.4f}, "
                   f"平均={np.mean(avg_distances):.4f}, 标准差={np.std(avg_distances):.4f}")
        logger.info(f"难度分布: 最小={np.min(difficulties):.4f}, 最大={np.max(difficulties):.4f}, "
                   f"平均={np.mean(difficulties):.4f}, 标准差={np.std(difficulties):.4f}")
        
        # 5. 基于难度进行重采样
        if n_resample > 0:
            resampled_indices = np.random.choice(
                np.arange(n_pos), size=n_resample, replace=True, p=difficulties
            )
            resampled_x = x_pos[resampled_indices]
        else:
            resampled_x = np.empty((0, x_pos.shape[1]))
        
        # 6. 为每个正样本分配合成样本数量
        if n_synthetic > 0:
            # 根据难度分配每个样本需要合成的数量
            synthetic_per_sample = np.zeros(n_pos, dtype=int)
            
            # 计算每个样本应该生成多少合成样本
            for _ in range(n_synthetic):
                # 随机选择一个样本，概率与其难度成正比
                idx = np.random.choice(np.arange(n_pos), p=difficulties)
                synthetic_per_sample[idx] += 1
            
            # 7. 创建一个基于正样本的KNN模型，用于SMOTE合成
            k_nn = min(k_smote, n_pos - 1)  # 防止k大于样本数-1
            if k_nn <= 0:
                logger.warning(f"正样本数量过少({n_pos})，无法执行SMOTE合成，将只进行重采样")
                synthetic_x = np.empty((0, x_pos.shape[1]))
            else:
                nn_pos = NearestNeighbors(n_neighbors=k_nn+1).fit(x_pos)  # +1是因为包含自身
                
                # 用于存储合成样本
                synthetic_x = []
                
                # 8. 为每个正样本生成对应数量的合成样本
                for i in range(n_pos):
                    n_to_generate = synthetic_per_sample[i]
                    if n_to_generate == 0:
                        continue
                    
                    # 找到当前样本的k个最近邻
                    distances_i, indices_i = nn_pos.kneighbors([x_pos[i]])
                    # 排除自身
                    nn_indices = indices_i[0][1:]
                    
                    # 为当前样本生成指定数量的合成样本
                    for _ in range(n_to_generate):
                        # 随机选择一个近邻
                        nn_idx = np.random.choice(nn_indices)
                        # 生成一个0到1之间的随机数作为插值比例
                        alpha = np.random.random()
                        # 使用SMOTE方法生成合成样本
                        synthetic_sample = x_pos[i] + alpha * (x_pos[nn_idx] - x_pos[i])
                        synthetic_x.append(synthetic_sample)
                
                # 将合成样本列表转换为numpy数组
                if synthetic_x:
                    synthetic_x = np.array(synthetic_x)
                else:
                    synthetic_x = np.empty((0, x_pos.shape[1]))
        else:
            synthetic_x = np.empty((0, x_pos.shape[1]))
        
        # 9. 合并重采样样本和合成样本
        final_samples = np.vstack([resampled_x, synthetic_x]) if synthetic_x.size > 0 else resampled_x
        
        # 10. 记录采样和合成的统计信息
        if n_resample > 0:
            unique_indices, counts = np.unique(resampled_indices, return_counts=True)
            coverage = len(unique_indices) / n_pos * 100
            logger.info(f"重采样覆盖率: {coverage:.2f}% ({len(unique_indices)}/{n_pos})")
            logger.info(f"重采样频率: 最小={np.min(counts) if counts.size > 0 else 0}, "
                       f"最大={np.max(counts) if counts.size > 0 else 0}, "
                       f"平均={np.mean(counts) if counts.size > 0 else 0:.2f}")
        
        if n_synthetic > 0:
            # 统计合成样本数量
            synthetic_count = np.sum(synthetic_per_sample > 0)
            synthetic_coverage = synthetic_count / n_pos * 100
            logger.info(f"合成样本覆盖率: {synthetic_coverage:.2f}% ({synthetic_count}/{n_pos})")
            logger.info(f"合成样本数量: {synthetic_x.shape[0]}")
        
        logger.info(f"最终样本数量: {final_samples.shape[0]} = {resampled_x.shape[0]}(重采样) + {synthetic_x.shape[0]}(合成)")
        
        # 返回最终样本
        return final_samples
        
    except Exception as e:
        logger.error(f"自适应难度采样过程中发生错误: {e}")
        logger.exception("详细错误信息:")
        # 出错时返回简单随机采样的结果
        logger.warning("回退到简单随机采样")
        sampled_indices = np.random.choice(np.arange(n_pos), size=n_samples, replace=True)
        return x_pos[sampled_indices]

def train_model(prefered_df: pl.DataFrame, remaining_df: pl.DataFrame, config: dict):
    # Placeholder for training logic
    logger.info("Training model...")
    # Convert labels from string to int, where 'like' is 1 and 'dislike' is 0

    embedding_columns = config.get("embedding_columns")
    prefered_df = prefered_df.with_columns(
        pl.when(pl.col("preference") == "like").then(1).otherwise(0).alias("label")
    ).select("label", *embedding_columns)

    remaining_df = remaining_df.select(*embedding_columns)

    # calculate positive sample number(like)
    positive_sample_num = prefered_df.filter(pl.col("label") == 1).height
    logger.debug(f"Positive sample number: {positive_sample_num}")
    
    # sample negative background data with neg_sample_ratio * positive_sample_num
    neg_sample_ratio = config.get("neg_sample_ratio", 5.0)
    neg_sample_num = int(neg_sample_ratio * positive_sample_num)
    logger.debug(f"Negative sample number: {neg_sample_num}")
    
    # sample negative data
    pesudo_neg_df = remaining_df.sample(n=neg_sample_num, seed=42)
    pesudo_neg_df = pesudo_neg_df.with_columns(
        pl.lit(0).alias("label")
    ).select("label", *embedding_columns)

    # combine 
    combined_df = pl.concat([prefered_df, pesudo_neg_df], how="vertical")
    logger.info(f"Combined DataFrame size (before NaN filtering): {combined_df.height} rows")

    # 🔧 过滤向量内部包含 NaN 的样本
    # 策略: 先转换为 numpy 检查,然后过滤
    logger.info(f"开始过滤向量内部包含 NaN 的样本...")
    
    # 逐列检查 NaN
    nan_mask = np.zeros(combined_df.height, dtype=bool)
    for col in embedding_columns:
        col_data = combined_df[col].to_list()
        for i, vec in enumerate(col_data):
            if vec is None or (isinstance(vec, (list, np.ndarray)) and np.isnan(vec).any()):
                nan_mask[i] = True
    
    # 过滤保留有效行
    removed_count = nan_mask.sum()
    if removed_count > 0:
        logger.warning(f"过滤了 {removed_count}/{len(combined_df)} ({removed_count/len(combined_df)*100:.2f}%) 个含 NaN 的样本")
        # 使用 polars 的 filter 按行过滤
        combined_df = combined_df.with_row_index("__idx__")
        valid_indices = np.where(~nan_mask)[0]
        combined_df = combined_df.filter(pl.col("__idx__").is_in(valid_indices)).drop("__idx__")
        logger.info(f"Combined DataFrame size (after NaN filtering): {combined_df.height} rows")
    else:
        logger.info(f"✅ 没有向量内部包含 NaN 的样本")

    # 🔍 NaN 诊断: 检查原始数据中的 None 值
    logger.info(f"[NaN诊断] 开始检查过滤后的 combined_df")
    for col in embedding_columns:
        col_data = combined_df[col].to_list()
        none_count = sum(1 for x in col_data if x is None)
        if none_count > 0:
            logger.warning(f"[NaN诊断] 列 '{col}' 有 {none_count} 个 None 值 ({none_count/len(col_data)*100:.2f}%)")
            # 找出 None 值的论文 ID
            if 'id' in combined_df.columns:
                none_indices = [i for i, x in enumerate(col_data) if x is None][:5]
                none_ids = [combined_df['id'][i] for i in none_indices]
                logger.warning(f"[NaN诊断] None 值的论文ID示例: {none_ids}")

    # convert to numpy array, where x should be the concatenated embedding columns
    # and y should be the label column
    # 🔍 NaN 诊断: 逐列转换并检查
    logger.info(f"[NaN诊断] 开始逐列转换为 numpy 数组")
    arrays = []
    for col in embedding_columns:
        try:
            col_arr = np.vstack(combined_df[col].to_numpy())
            nan_count = np.isnan(col_arr).sum()
            logger.info(f"[NaN诊断] 列 '{col}' vstack后: shape={col_arr.shape}, NaN数量={nan_count}")
            if nan_count > 0:
                rows_with_nan = np.where(np.isnan(col_arr).any(axis=1))[0]
                logger.warning(f"[NaN诊断] 列 '{col}' 中有 {len(rows_with_nan)} 行包含 NaN")
                logger.warning(f"[NaN诊断] 前10个NaN行索引: {rows_with_nan[:10].tolist()}")
            arrays.append(col_arr)
        except Exception as e:
            logger.error(f"[NaN诊断] 列 '{col}' 转换失败: {e}")
            raise
    
    x = np.hstack(arrays)
    y = combined_df.select("label").to_numpy().ravel()
    logger.info(f"[NaN诊断] hstack后: shape={x.shape}")
    
    samples_with_nan = np.isnan(x).any(axis=1).sum()
    if samples_with_nan > 0:
        logger.warning(f"[NaN诊断] 最终检测: {samples_with_nan}个样本 ({samples_with_nan/x.shape[0]*100:.2f}%) 包含NaN值")
    else:
        logger.info(f"[NaN诊断] ✅ 最终检测: 没有NaN值!")
    
    # 方法1：用0填充NaN (简单方法)
    if samples_with_nan > 0:
        x = np.nan_to_num(x, nan=0.0)
        logger.info("已将所有NaN值替换为0")

    logger.info(f"x: {x.dtype} | {x.shape}, y shape: {y.dtype} | {y.shape}")
    lg_config = config.get("logistic_regression", {})
    cws_config = config.get("confidence_weighted_sampling", {'enable': False})

    if cws_config.get("enable", False):
        logger.info("Using confidence weighted sampling...")
        tmp_model = sklearn.linear_model.LogisticRegression(
            C=lg_config.get("C", 1.0),
            max_iter=lg_config.get("max_iter", 1000),
            random_state=config.get("seed", 42),
            class_weight="balanced",
        ).fit(x, y)
        new_positive_embedding = confidence_weighted_sampling(
            x[y == 1], tmp_model,
            high_conf_threshold=cws_config.get("high_conf_threshold", 0.9),
            high_conf_weight=cws_config.get("high_conf_weight", 2.0),
            random_state=config.get("seed", 42)
        )

        x = np.concatenate((x[y == 0], new_positive_embedding))
        y = np.concatenate((y[y == 0], np.ones(new_positive_embedding.shape[0])))
        logger.info(f"New x shape: {x.shape}, New y shape: {y.shape}")

    ads_config = config.get("adaptive_difficulty_sampling", {'enable': False})
    if ads_config.get("enable", False):
        # unlabeled_data = remaining_df.select(*embedding_columns).to_numpy()
        unlabeled_data = np.hstack([np.vstack(remaining_df[col].to_numpy()) for col in embedding_columns])
        x_pos = adaptive_difficulty_sampling(
            x[y == 1], unlabeled_data,
            n_neighbors=config.get("n_neighbors", 5),
            sampling_ratio=config.get("pos_sampling_ratio", 2.0),
            random_state=config.get("seed", 42),
            synthetic_ratio=config.get("synthetic_ratio", 0.5),  # 默认50%是合成的
            k_smote=config.get("k_smote", 16)  # SMOTE的k近邻参数
        )
        x = np.concatenate((x[y == 0], x_pos))
        y = np.concatenate((y[y == 0], np.ones(x_pos.shape[0])))

    # Train the final model
    final_model = sklearn.linear_model.LogisticRegression(
        C=lg_config.get("C", 1.0),
        max_iter=lg_config.get("max_iter", 1000),
        random_state=config.get("seed", 42),
        class_weight="balanced",
    ).fit(x, y)

    logger.info("Model training completed.")
    return final_model
    

"""
Prediction Part
"""

def predict_and_recommend(model, remaining_df: pl.LazyFrame, recommended_df: pl.DataFrame, config: dict) -> pl.DataFrame:
    """根据训练好的模型对剩余数据进行预测并推荐论文。
    Args:
        model: 训练好的模型
        remaining_df: 剩余数据
        recommended_df: 已推荐的数据
        config: 配置参数
    
    Returns:
        带有推荐标记的DataFrame
    """
    logger.info("开始预测和推荐阶段...")
    
    # 1. 从剩余数据中排除已推荐的论文
    target_df = remove_recommended(remaining_df, recommended_df)
    
    # 2. 根据配置选择目标时间段的数据
    predict_config = config.get("predict", {})
    
    # 解析日期相关配置
    last_n_days = predict_config.get("last_n_days", 7)
    start_date = predict_config.get("start_date", "")
    end_date = predict_config.get("end_date", "")
    
    # 如果指定了起止日期，使用日期范围筛选
    if start_date and end_date:
        logger.info(f"使用指定的日期范围: {start_date} 到 {end_date}")
        target_df = target_df.filter(
            (pl.col("updated") >= start_date) & (pl.col("updated") <= end_date)
        )
    # 否则使用最近N天
    else:
        # 计算最近N天的日期
        today = datetime.datetime.now()
        n_days_ago = (today - datetime.timedelta(days=last_n_days)).strftime("%Y-%m-%d")
        logger.info(f"使用最近{last_n_days}天的数据: {n_days_ago} 到 {today.strftime('%Y-%m-%d')}")
        
        target_df = target_df.filter(pl.col("updated") >= n_days_ago)
    
    # 3. 收集目标数据
    logger.info("收集目标数据...")
    embedding_columns = config.get("embedding_columns")
    
    # 如果没有目标数据，提前返回
    if target_df.is_empty():
        logger.warning("没有满足条件的目标数据可供推荐")
        return target_df
    
    logger.info(f"目标数据收集完成，共 {target_df.height} 条记录")
    
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
        target_df = target_df.with_row_index("__idx__")
        valid_indices = np.where(~nan_mask)[0]
        target_df = target_df.filter(pl.col("__idx__").is_in(valid_indices)).drop("__idx__")
        logger.info(f"目标数据过滤后: {target_df.height} 条记录")
    else:
        logger.info(f"✅ 预测数据没有向量内部包含 NaN 的样本")
    
    # 4. 提取特征和预测
    logger.info("提取特征并进行预测...")
    
    # 🔍 NaN 诊断: 检查预测数据
    logger.info(f"[NaN诊断-预测] 开始检查过滤后的预测数据")
    for col in embedding_columns:
        col_data = target_df[col].to_list()
        none_count = sum(1 for x in col_data if x is None)
        if none_count > 0:
            logger.warning(f"[NaN诊断-预测] 列 '{col}' 有 {none_count} 个 None 值 ({none_count/len(col_data)*100:.2f}%)")
    
    # X_target = target_df.select(*embedding_columns).to_numpy()
    arrays = []
    for col in embedding_columns:
        col_arr = np.vstack(target_df[col].to_numpy())
        nan_count = np.isnan(col_arr).sum()
        if nan_count > 0:
            logger.warning(f"[NaN诊断-预测] 列 '{col}' vstack后有 {nan_count} 个 NaN")
        arrays.append(col_arr)
    
    X_target = np.hstack(arrays)
    logger.info(f"[NaN诊断-预测] X_target shape: {X_target.shape}")
    
    # 处理 NaN 值
    nan_count = np.isnan(X_target).sum()
    if nan_count > 0:
        logger.warning(f"[NaN诊断-预测] 最终检测: 预测数据中发现 {nan_count} 个 NaN 值 ({nan_count/X_target.size*100:.4f}%)，将替换为 0")
        rows_with_nan = np.where(np.isnan(X_target).any(axis=1))[0]
        logger.warning(f"[NaN诊断-预测] 有 {len(rows_with_nan)} 行包含 NaN")
        X_target = np.nan_to_num(X_target, nan=0.0)
    else:
        logger.info(f"[NaN诊断-预测] ✅ 预测数据没有 NaN")
    
    # 使用模型预测"喜欢"的概率
    try:
        target_scores = model.predict_proba(X_target)[:, 1]
        logger.info(f"预测完成，分数范围: {np.min(target_scores):.4f} - {np.max(target_scores):.4f}, 平均: {np.mean(target_scores):.4f}")
    except Exception as e:
        logger.error(f"预测过程出错: {e}")
        logger.exception("详细错误信息:")
        # 如果预测失败，返回随机分数
        logger.warning("预测失败，生成随机分数")
        np.random.seed(config.get("seed", 42))
        target_scores = np.random.random(target_df.height)
    
    # 5. 添加预测分数到DataFrame
    target_df = target_df.with_columns(pl.lit(target_scores).alias("score"))
    
    # 6. 执行自适应采样决定推荐
    logger.info("执行自适应采样确定推荐...")
    
    high_threshold = predict_config.get("high_threshold", 0.95)
    boundary_threshold = predict_config.get("boundary_threshold", 0.5)
    sample_rate = predict_config.get("sample_rate", 0.15)
    
    show_flags = adaptive_sample(
        target_scores, 
        target_sample_rate=sample_rate,
        high_threshold=high_threshold,
        boundary_threshold=boundary_threshold,
        random_state=config.get("seed", 42)
    )
    
    # 7. 添加推荐标记到DataFrame
    target_df = target_df.with_columns(pl.lit(show_flags.astype(np.int8)).alias("show"))
    
    # 8. 统计和记录结果
    recommended_count = np.sum(show_flags)
    logger.info(f"推荐完成: 总计 {target_df.height} 篇论文中推荐 {recommended_count} 篇 ({recommended_count/target_df.height*100:.2f}%)")
    
    # 统计不同分数区间的推荐比例
    score_intervals = [(0.0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.0)]
    for low, high in score_intervals:
        interval_mask = (target_scores >= low) & (target_scores < high)
        if np.sum(interval_mask) > 0:
            interval_show = np.sum(show_flags & interval_mask)
            interval_total = np.sum(interval_mask)
            logger.info(f"分数 {low:.1f}-{high:.1f}: {interval_show}/{interval_total} ({interval_show/interval_total*100:.2f}%)")
    
    # 9. 返回结果DataFrame
    return target_df


def adaptive_sample(scores, target_sample_rate=0.15, high_threshold=0.95, boundary_threshold=0.5, random_state=42):
    """自适应采样算法，根据分数决定哪些样本应该被推荐。
    
    策略:
    1. 所有高于high_threshold的样本被优先推荐
    2. 如果高分样本数量超过目标数量，随机抽取一部分
    3. 如果高分样本不足，从boundary_threshold到high_threshold之间的分数中按权重采样
    
    Args:
        scores: 每个样本的预测分数
        target_sample_rate: 目标推荐比例
        high_threshold: 高置信度阈值
        boundary_threshold: 边界阈值
        random_state: 随机种子
    
    Returns:
        布尔数组，标记哪些样本被推荐
    """
    np.random.seed(random_state)
    n_samples = len(scores)
    target_count = int(n_samples * target_sample_rate)
    
    if target_count <= 0:
        # 至少推荐一个
        target_count = 1
    
    # 初始化推荐标记数组
    show_flags = np.zeros(n_samples, dtype=bool)
    
    # 找出所有高分样本
    high_score_mask = scores >= high_threshold
    high_score_indices = np.where(high_score_mask)[0]
    high_score_count = len(high_score_indices)
    
    logger.info(f"目标推荐数量: {target_count} / {n_samples} ({target_sample_rate*100:.2f}%)")
    logger.info(f"高分样本(>={high_threshold:.4f})数量: {high_score_count} ({high_score_count/n_samples*100:.2f}%)")
    
    # 情况A: 高分样本足够或超过目标数量
    if high_score_count >= target_count:
        # 如果高分样本超过了目标数量，随机选择一部分
        if high_score_count > target_count:
            selected_indices = np.random.choice(high_score_indices, target_count, replace=False)
            show_flags[selected_indices] = True
            logger.info(f"高分样本超过目标数量，随机选择了{target_count}个")
        else:
            # 高分样本数量刚好等于目标数量
            show_flags[high_score_indices] = True
            logger.info(f"高分样本数量恰好等于目标数量")
        
        return show_flags
    
    # 情况B: 高分样本不足，需要从中等分数样本中补充
    # 先标记所有高分样本
    show_flags[high_score_indices] = True
    remaining_count = target_count - high_score_count
    
    # 找出边界区域的样本
    boundary_mask = (scores >= boundary_threshold) & (scores < high_threshold)
    boundary_indices = np.where(boundary_mask)[0]
    boundary_count = len(boundary_indices)
    
    logger.info(f"边界样本({boundary_threshold:.4f}-{high_threshold:.4f})数量: {boundary_count} ({boundary_count/n_samples*100:.2f}%)")
    
    if boundary_count == 0:
        # 如果没有边界样本，从所有剩余样本中随机选择
        remaining_indices = np.where(~high_score_mask)[0]
        if len(remaining_indices) > 0:
            if len(remaining_indices) > remaining_count:
                # 随机选择一部分
                selected_indices = np.random.choice(remaining_indices, remaining_count, replace=False)
            else:
                # 全部选择
                selected_indices = remaining_indices
            
            show_flags[selected_indices] = True
            logger.info(f"无边界样本，从所有剩余样本中随机选择了{len(selected_indices)}个")
    else:
        # 从边界区域按权重采样
        # 计算边界区域样本的权重（分数越高权重越大）
        boundary_scores = scores[boundary_indices]
        # 归一化到[0,1]区间，提高对比度
        min_score = boundary_threshold
        max_score = high_threshold
        normalized_scores = (boundary_scores - min_score) / (max_score - min_score)
        # 使用指数函数增强差异 (可选)
        weights = np.exp(normalized_scores * 2)  # 乘以2是为了增加对比度
        weights = weights / np.sum(weights)
        
        # 加权采样
        sample_size = min(remaining_count, boundary_count)
        selected_indices = np.random.choice(
            boundary_indices, sample_size, replace=False, p=weights
        )
        show_flags[selected_indices] = True
        
        logger.info(f"从边界区域加权采样了{len(selected_indices)}个样本")
        
        # 如果边界区域样本数量仍不足，从低分区域随机采样补足
        if sample_size < remaining_count:
            still_remaining = remaining_count - sample_size
            low_score_mask = scores < boundary_threshold
            low_score_indices = np.where(low_score_mask)[0]
            
            if len(low_score_indices) > 0:
                sample_size_low = min(still_remaining, len(low_score_indices))
                selected_indices_low = np.random.choice(low_score_indices, sample_size_low, replace=False)
                show_flags[selected_indices_low] = True
                logger.info(f"从低分区域({boundary_threshold:.4f}以下)随机采样了{len(selected_indices_low)}个样本")
    
    return show_flags


def predict_and_save(model, remaining_df, recommended_df, config):
    """预测、推荐并保存结果。
    
    Args:
        model: 训练好的模型
        remaining_df: 剩余数据
        recommended_df: 已推荐的数据
        config: 配置参数
    
    Returns:
        推荐的DataFrame
    """
    # 执行预测和推荐
    results_df = predict_and_recommend(model, remaining_df, recommended_df, config)
    
    # 如果结果为空，提前返回
    if results_df.is_empty():
        logger.warning("没有推荐结果可保存")
        return results_df
    
    # 移除embedding列以减小文件大小
    embedding_columns = config.get("embedding_columns", [])
    if embedding_columns:
        results_df = results_df.drop(*embedding_columns)
    # 保存结果到CSV
    output_file = REPO_ROOT / "data" / "predictions.parquet"
    
    # 确保目录存在
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 保存
    results_df.write_parquet(output_file)
    logger.info(f"预测结果已保存到: {output_file}")
    
    # 提取并返回推荐的论文
    recommended_results = results_df.filter(pl.col("show") == 1)
    logger.info(f"推荐{recommended_results.height}篇论文")
    show_df = recommended_results.select("id", "title", "abstract", "score")
    logger.debug(f"{show_df}")
    
    return recommended_results

if __name__ == "__main__":
    log_info()

    config = load_config()
    preferences = load_preference(config)
    recommended = load_recommended(config)

    prefered_df, remaining_df = load_lazy_dataset(config, preferences)
    remaining_df = remove_recommended(remaining_df, recommended)

    prefered_df = prefered_df.collect()
    remaining_df = remaining_df.collect()

    model = train_model(prefered_df, remaining_df, config)
    logger.info("模型训练完成")

    predict_and_save(model, remaining_df, recommended, config)
    