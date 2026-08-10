import js from "@eslint/js"
import { defineConfig, globalIgnores } from "eslint/config"
import globals from "globals"
import reactHooks from "eslint-plugin-react-hooks"
import reactRefresh from "eslint-plugin-react-refresh"
import tseslint from "typescript-eslint"

export default defineConfig([
  globalIgnores(["dist/**", "node_modules/**"]),
  {
    files: ["src/**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "no-empty": ["error", { allowEmptyCatch: true }],
      "react-refresh/only-export-components": "off",
    },
  },
])
