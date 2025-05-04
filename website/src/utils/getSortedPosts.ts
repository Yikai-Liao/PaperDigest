import type { CollectionEntry } from "astro:content";
import postFilter from "./postFilter";

// 定义排序类型
export enum SortType {
  // 按发布/修改日期排序（最新的在前）
  DATE_DESC = "date_desc",
  // 按发布/修改日期排序（最旧的在前）
  DATE_ASC = "date_asc",
  // 按论文发布日期排序（最新的在前）
  PAPER_DATE_DESC = "paper_date_desc",
  // 按偏好分数排序（高分在前）
  SCORE_DESC = "score_desc",
  // 按照偏好状态排序（喜欢的在前）
  PREFERENCE = "preference",
  // 智能混合排序（考虑多个因素）
  SMART = "smart"
}

// 默认排序类型
export const DEFAULT_SORT_TYPE = SortType.SMART;

/**
 * 计算文章的"智能分数"，用于智能混合排序
 * 综合考虑：新鲜度、质量分数、阅读状态、偏好
 */
const getSmartScore = (post: CollectionEntry<"blog">) => {
  const now = new Date();
  const { pubDatetime, modDatetime, score, preference } = post.data;
  
  // 计算文章发布/更新距今的天数
  const publishDate = new Date(modDatetime ?? pubDatetime);
  const daysSincePublish = Math.floor((now.getTime() - publishDate.getTime()) / (1000 * 60 * 60 * 24));
  
  // 新鲜度分数：最近发布的文章得分高，随时间衰减
  // 7天内发布的文章保持最高新鲜度，之后逐渐衰减
  const freshnessScore = Math.max(0, 1 - Math.max(0, daysSincePublish - 7) / 30);
  
  // 质量分数：直接使用文章的score字段，如果没有则默认为0.5
  const qualityScore = score ?? 0.5;
  
  // 偏好因子：根据preference调整最终排序
  let preferenceMultiplier = 1.0;
  if (preference) {
    switch (preference) {
      case "unknown": // 未读/未评价的文章优先级提高
        preferenceMultiplier = 1.5;
        break;
      case "like": // 喜欢的文章次优先
        preferenceMultiplier = 0.8;
        break;
      case "neutral": // 中性评价的文章降低优先级
        preferenceMultiplier = 0.4;
        break;
      case "dislike": // 不喜欢的文章最低优先级
        preferenceMultiplier = 0.2;
        break;
    }
  } else {
    // 没有preference字段，说明可能是新文章，提高优先级
    preferenceMultiplier = 1.5;
  }
  
  // 计算最终的智能分数：新鲜度(40%) + 质量(60%)，再乘以偏好因子
  const smartScore = (freshnessScore * 0.4 + qualityScore * 0.6) * preferenceMultiplier;
  
  return smartScore;
};

const getSortedPosts = (
  posts: CollectionEntry<"blog">[],
  sortType: SortType = DEFAULT_SORT_TYPE
) => {
  const filteredPosts = posts.filter(postFilter);
  
  switch (sortType) {
    case SortType.DATE_DESC:
      return filteredPosts.sort(
        (a, b) =>
          Math.floor(
            new Date(b.data.modDatetime ?? b.data.pubDatetime).getTime() / 1000
          ) -
          Math.floor(
            new Date(a.data.modDatetime ?? a.data.pubDatetime).getTime() / 1000
          )
      );
      
    case SortType.DATE_ASC:
      return filteredPosts.sort(
        (a, b) =>
          Math.floor(
            new Date(a.data.modDatetime ?? a.data.pubDatetime).getTime() / 1000
          ) -
          Math.floor(
            new Date(b.data.modDatetime ?? b.data.pubDatetime).getTime() / 1000
          )
      );
      
    case SortType.PAPER_DATE_DESC:
      // 假设论文发布日期存储在 paperDate 字段中
      return filteredPosts.sort(
        (a, b) => {
          const aPaperDate = a.data.paperDate ? new Date(a.data.paperDate).getTime() : 0;
          const bPaperDate = b.data.paperDate ? new Date(b.data.paperDate).getTime() : 0;
          return bPaperDate - aPaperDate;
        }
      );
      
    case SortType.SCORE_DESC:
      // 按分数排序（无分数的排在后面）
      return filteredPosts.sort(
        (a, b) => {
          const aScore = a.data.score ?? -1;
          const bScore = b.data.score ?? -1;
          return bScore - aScore;
        }
      );
      
    case SortType.PREFERENCE:
      // 按偏好状态排序：喜欢 > 中性 > 不喜欢 > 未知
      return filteredPosts.sort(
        (a, b) => {
          const prefOrder = { "like": 3, "neutral": 2, "dislike": 1, "unknown": 0, undefined: -1 };
          const aPref = prefOrder[a.data.preference as keyof typeof prefOrder] ?? -1;
          const bPref = prefOrder[b.data.preference as keyof typeof prefOrder] ?? -1;
          
          if (aPref !== bPref) {
            return bPref - aPref;
          }
          
          // 如果偏好相同，则按日期排序
          return Math.floor(
            new Date(b.data.modDatetime ?? b.data.pubDatetime).getTime() / 1000
          ) -
          Math.floor(
            new Date(a.data.modDatetime ?? a.data.pubDatetime).getTime() / 1000
          );
        }
      );
      
    case SortType.SMART:
      // 智能混合排序：综合考虑新鲜度、质量分数、阅读状态和偏好
      return filteredPosts.sort((a, b) => {
        const aSmartScore = getSmartScore(a);
        const bSmartScore = getSmartScore(b);
        return bSmartScore - aSmartScore;
      });
      
    default:
      return filteredPosts;
  }
};

export default getSortedPosts;