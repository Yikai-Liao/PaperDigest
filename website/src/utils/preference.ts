/**
 * 根据 preference 返回对应的 emoji
 * @param pref 文章的偏好评价 ("like"|"dislike"|"neutral"|"unknown")
 * @returns 对应的表情符号
 */
export const getPreferenceEmoji = (pref: string | undefined) => {
  switch (pref) {
    case "like":
      return "👍";
    case "dislike":
      return "👎";
    case "neutral":
      return "😐";
    case "unknown":
      return "🤔";
    default:
      return "";
  }
};

// 定义不同分数范围和主题下的颜色
export const SCORE_COLORS = {
  dark: {
    low: "rgba(220, 120, 120, 0.85)",    // 低分：柔和的红色（深色主题）
    medium: "rgba(220, 200, 100, 0.85)", // 中分：柔和的黄色/橙色（深色主题）
    high: "rgba(120, 200, 120, 0.85)",   // 高分：柔和的绿色（深色主题）
  },
  light: {
    low: "rgba(180, 60, 60, 0.9)",     // 低分：深红色（浅色主题）
    medium: "rgba(180, 140, 20, 0.9)", // 中分：深黄色/棕色（浅色主题）
    high: "rgba(40, 140, 40, 0.9)",    // 高分：深绿色（浅色主题）
  }
};

// 分数范围阈值
export const SCORE_THRESHOLDS = {
  low: 0.3,  // 低于0.3为低分
  high: 0.7, // 高于0.7为高分
};

/**
 * 根据分数和主题返回对应的颜色
 * @param score 分数值（0-1范围）
 * @param isDark 是否为深色主题
 * @returns 表示分数的 CSS 颜色值
 */
export const getScoreColor = (score: number | undefined, isDark = false): string => {
  if (score === undefined) return "";

  // 确保分数在0-1范围内
  const safeScore = Math.max(0, Math.min(1, score));
  
  // 根据分数范围和主题选择颜色
  const theme = isDark ? SCORE_COLORS.dark : SCORE_COLORS.light;
  
  if (safeScore < SCORE_THRESHOLDS.low) {
    return theme.low;
  } else if (safeScore < SCORE_THRESHOLDS.high) {
    return theme.medium;
  } else {
    return theme.high;
  }
};