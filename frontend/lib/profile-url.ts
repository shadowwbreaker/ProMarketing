export type Platform = "tiktok" | "youtube" | "instagram";

export function validateProfileUrl(platform: Platform, url: string): string | null {
  let u = url.trim();
  try {
    u = decodeURI(u); // handles copied from the address bar may be percent-encoded (Cyrillic handles)
  } catch {
    /* keep as is */
  }
  if (platform === "youtube" && !/^https?:\/\/(www\.|m\.)?youtube\.com\/@[\p{L}\p{N}_.\-·]{3,30}\/shorts\/?$/u.test(u))
    return "Нужна ссылка на страницу Shorts канала, например https://www.youtube.com/@канал/shorts";
  if (platform === "tiktok" && !/^https?:\/\/(www\.|m\.)?tiktok\.com\/@[A-Za-z0-9_.]{2,24}\/?$/.test(u))
    return "Нужна ссылка на профиль, например https://www.tiktok.com/@ваш_ник";
  return null;
}
