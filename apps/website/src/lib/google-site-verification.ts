/** Google Search Console HTML-tag token. Empty unless the owner sets PUBLIC_GOOGLE_SITE_VERIFICATION. Never invent a value. */
export function googleSiteVerificationToken(
  raw: unknown = import.meta.env.PUBLIC_GOOGLE_SITE_VERIFICATION,
): string {
  if (typeof raw !== "string") {
    return "";
  }
  return raw.trim();
}
