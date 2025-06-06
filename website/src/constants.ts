import IconMail from "@/assets/icons/IconMail.svg";
import IconGitHub from "@/assets/icons/IconGitHub.svg";
import IconBrandX from "@/assets/icons/IconBrandX.svg";
import IconWhatsapp from "@/assets/icons/IconWhatsapp.svg";
import IconFacebook from "@/assets/icons/IconFacebook.svg";
import IconTelegram from "@/assets/icons/IconTelegram.svg";
import IconPinterest from "@/assets/icons/IconPinterest.svg";
import { SITE } from "@/config";
import type { GiscusProps } from "@giscus/react"; // Add this import

export const SOCIALS = [
  {
    name: "Github",
    href: "https://github.com/Yikai-Liao/PaperDigest",
    linkTitle: ` ${SITE.title} on Github`,
    icon: IconGitHub,
  },
  {
    name: "X",
    href: "https://x.com/RealYikaiLiao",
    linkTitle: `${SITE.title} on X`,
    icon: IconBrandX,
  },
  {
    name: "Mail",
    href: "yikai003@e.ntu.edu.sg",
    linkTitle: `Send an email to ${SITE.title}`,
    icon: IconMail,
  },
] as const;

export const SHARE_LINKS = [
  {
    name: "WhatsApp",
    href: "https://wa.me/?text=",
    linkTitle: `Share this post via WhatsApp`,
    icon: IconWhatsapp,
  },
  {
    name: "Facebook",
    href: "https://www.facebook.com/sharer.php?u=",
    linkTitle: `Share this post on Facebook`,
    icon: IconFacebook,
  },
  {
    name: "X",
    href: "https://x.com/intent/post?url=",
    linkTitle: `Share this post on X`,
    icon: IconBrandX,
  },
  {
    name: "Telegram",
    href: "https://t.me/share/url?url=",
    linkTitle: `Share this post via Telegram`,
    icon: IconTelegram,
  },
  {
    name: "Pinterest",
    href: "https://pinterest.com/pin/create/button/?url=",
    linkTitle: `Share this post on Pinterest`,
    icon: IconPinterest,
  },
  {
    name: "Mail",
    href: "mailto:?subject=See%20this%20post&body=",
    linkTitle: `Share this post via email`,
    icon: IconMail,
  },
] as const;

// Add the GISCUS constant with your details
export const GISCUS: GiscusProps = {
  repo: "Yikai-Liao/PaperDigest",
  repoId: "R_kgDOOj034g",
  category: "Giscus",
  categoryId: "DIC_kwDOOj034s4Cpv41",
  mapping: "pathname",
  reactionsEnabled: "1",
  emitMetadata: "0",
  inputPosition: "bottom",
  lang: "zh-CN",
  loading: "eager", // 将 lazy 改为 eager
};
