import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        card: "hsl(var(--card))",
        border: "hsl(var(--border))",
        primary: "hsl(var(--primary))",
        success: "hsl(var(--success))",
        warning: "hsl(var(--warning))",
        danger: "hsl(var(--danger))",
        muted: "hsl(var(--muted))"
      },
      spacing: {
        18: "4.5rem"
      },
      borderRadius: {
        xl: "1rem"
      }
    }
  },
  plugins: []
} satisfies Config;
