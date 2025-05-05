// 常量定义
const SCORE_COLORS = {
  "dark": {
    "low": "rgba(220, 120, 120, 0.85)",
    "medium": "rgba(220, 200, 100, 0.85)",
    "high": "rgba(120, 200, 120, 0.85)"
  },
  "light": {
    "low": "rgba(180, 60, 60, 0.9)",
    "medium": "rgba(180, 140, 20, 0.9)",
    "high": "rgba(40, 140, 40, 0.9)"
  }
};
const SCORE_THRESHOLDS = { "low": 0.3, "high": 0.7 };

// 菜单开关功能
function setupMenuToggle() {
  const menuBtn = document.querySelector("#menu-btn");
  const menuItems = document.querySelector("#menu-items");
  const menuIcon = document.querySelector("#menu-icon");
  const closeIcon = document.querySelector("#close-icon");

  if (!menuBtn || !menuItems || !menuIcon || !closeIcon) return;

  menuBtn.addEventListener("click", () => {
    const isExpanded = menuBtn.getAttribute("aria-expanded") === "true";
    menuBtn.setAttribute("aria-expanded", isExpanded ? "false" : "true");
    menuBtn.setAttribute("aria-label", isExpanded ? "Open Menu" : "Close Menu");
    menuItems.classList.toggle("hidden");
    menuIcon.classList.toggle("hidden");
    closeIcon.classList.toggle("hidden");
  });
}

// 分数颜色更新功能
function updateScoreColors() {
  const isDarkTheme = document.documentElement.classList.contains('dark');
  document.querySelectorAll('.score-value').forEach(el => {
    const scoreText = el.textContent;
    if (scoreText) {
      const score = parseFloat(scoreText) / 100; // 转换回0-1范围
      
      // 根据分数和当前主题设置颜色
      const theme = isDarkTheme ? SCORE_COLORS.dark : SCORE_COLORS.light;
      
      if (score < SCORE_THRESHOLDS.low) {
        el.style.color = theme.low;
      } else if (score < SCORE_THRESHOLDS.high) {
        el.style.color = theme.medium;
      } else {
        el.style.color = theme.high;
      }
    }
  });
}

// 文章页面的功能
function setupPostDetailsPage() {
  /** Create a progress indicator at the top */
  function createProgressBar() {
    // 如果已存在进度条，则不再创建
    if (document.querySelector('.progress-container')) return;
    
    // Create the main container div
    const progressContainer = document.createElement("div");
    progressContainer.className =
      "progress-container fixed top-0 z-10 h-1 w-full bg-background";

    // Create the progress bar div
    const progressBar = document.createElement("div");
    progressBar.className = "progress-bar h-1 w-0 bg-accent";
    progressBar.id = "myBar";

    // Append the progress bar to the progress container
    progressContainer.appendChild(progressBar);

    // Append the progress container to the document body
    document.body.appendChild(progressContainer);
  }

  /** Update the progress bar when user scrolls */
  function updateScrollProgress() {
    document.addEventListener("scroll", () => {
      const winScroll =
        document.body.scrollTop || document.documentElement.scrollTop;
      const height =
        document.documentElement.scrollHeight -
        document.documentElement.clientHeight;
      const scrolled = (winScroll / height) * 100;
      if (document) {
        const myBar = document.getElementById("myBar");
        if (myBar) {
          myBar.style.width = scrolled + "%";
        }
      }
    });
  }

  /** Attaches links to headings in the document */
  function addHeadingLinks() {
    const headings = Array.from(
      document.querySelectorAll("h2, h3, h4, h5, h6")
    );
    for (const heading of headings) {
      heading.classList.add("group");
      const link = document.createElement("a");
      link.className =
        "heading-link ml-2 opacity-0 group-hover:opacity-100 focus:opacity-100";
      link.href = "#" + heading.id;

      const span = document.createElement("span");
      span.ariaHidden = "true";
      span.innerText = "#";
      link.appendChild(span);
      heading.appendChild(link);
    }
  }

  /** Attaches copy buttons to code blocks */
  function attachCopyButtons() {
    const copyButtonLabel = "Copy";
    const codeBlocks = Array.from(document.querySelectorAll("pre"));

    for (const codeBlock of codeBlocks) {
      // 避免重复添加
      if (codeBlock.querySelector('.copy-code')) continue;
      
      const wrapper = document.createElement("div");
      wrapper.style.position = "relative";

      const copyButton = document.createElement("button");
      copyButton.className =
        "copy-code absolute right-3 -top-3 rounded bg-muted px-2 py-1 text-xs leading-4 text-foreground font-medium";
      copyButton.innerHTML = copyButtonLabel;
      codeBlock.setAttribute("tabindex", "0");
      codeBlock.appendChild(copyButton);

      // wrap codebock with relative parent element
      codeBlock?.parentNode?.insertBefore(wrapper, codeBlock);
      wrapper.appendChild(codeBlock);

      copyButton.addEventListener("click", async () => {
        await copyCode(codeBlock, copyButton);
      });
    }

    async function copyCode(block, button) {
      const code = block.querySelector("code");
      const text = code?.innerText;

      await navigator.clipboard.writeText(text ?? "");

      // visual feedback that task is completed
      button.innerText = "Copied";

      setTimeout(() => {
        button.innerText = copyButtonLabel;
      }, 700);
    }
  }

  /** Back to Top button functionality */
  function backToTop() {
    document.querySelector("#back-to-top")?.addEventListener("click", () => {
      document.body.scrollTop = 0; // For Safari
      document.documentElement.scrollTop = 0; // For Chrome, Firefox, IE and Opera
    });
  }

  // 只在文章详情页执行
  if (document.querySelector("#article")) {
    createProgressBar();
    updateScrollProgress();
    addHeadingLinks();
    attachCopyButtons();
    backToTop();
  }
}

// 保存当前页面的 backUrl 信息
function saveBackUrl() {
  const mainContent = document.querySelector("#main-content");
  const backUrl = mainContent?.dataset?.backurl;
  if (backUrl) {
    sessionStorage.setItem("backUrl", backUrl);
  }
}

// 初始化和页面加载事件处理
document.addEventListener("astro:page-load", () => {
  // 菜单开关
  setupMenuToggle();
  
  // 分数颜色更新
  updateScoreColors();
  
  // 文章页面功能
  setupPostDetailsPage();
  
  // 保存 backUrl
  saveBackUrl();
  
  // 监听主题变化，更新分数颜色
  const themeBtn = document.querySelector('#theme-btn');
  themeBtn?.addEventListener('click', () => {
    // 延迟执行，等待主题切换完成
    setTimeout(updateScoreColors, 0);
  });
});

// 为首次加载也执行一次（不通过 Astro view transitions 加载的页面）
document.addEventListener("DOMContentLoaded", () => {
  setupMenuToggle();
  updateScoreColors();
  setupPostDetailsPage();
  saveBackUrl();
});

// 页面切换后滚动到顶部
document.addEventListener("astro:after-swap", () => {
  window.scrollTo({ left: 0, top: 0, behavior: "instant" });
  
  // 确保切换页面后菜单仍然正常工作
  setupMenuToggle();
});