export const SITE = {
  website: "https://digest.lyk-ai.com", // replace this with your deployed domain
  author: "Yikai Liao",
  profile: "https://yikai-liao.github.io/academicpages/",
  desc: "An AI based and personalized paper recommendation & summarization system",
  title: "Paper Digest",
  ogImage: "ai_reading.webp",
  lightAndDarkMode: true,
  postPerIndex: 10,
  postPerPage: 10,
  scheduledPostMargin: 15 * 60 * 1000, // 15 minutes
  showArchives: true,
  showBackButton: true, // show back button in post detail
  editPost: {
    enabled: false,
    text: "Suggest Changes",
    url: "",
  },
  dynamicOgImage: true,
  lang: "zh-CN", // html lang code. Set this empty and default will be "en"
  timezone: "Asia/Shanghai", // Default global timezone (IANA format) https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
} as const;
