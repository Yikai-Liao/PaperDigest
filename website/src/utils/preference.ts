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