import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://devmind.warishlabs.in";
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: [
          "/api/",
          "/dashboard",
          "/dashboard/",
          "/projects",
          "/projects/",
          "/settings",
          "/settings/",
          "/sign-in",
          "/sign-in/",
          "/sign-up",
          "/sign-up/",
          "/invitations",
          "/invitations/",
          "/onboarding",
          "/onboarding/",
        ],
      },
    ],
    sitemap: `${siteUrl}/sitemap.xml`,
  };
}
