export default {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "scope-enum": [
      2,
      "always",
      ["client", "server", "extension", "common", "docs", "brand", "ci", "infra", "deps", "repo"],
    ],
  },
};
