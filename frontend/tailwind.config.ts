import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        chatBg: "#171717",
        chatSidebar: "#111111",
        chatCard: "#1f1f1f",
        chatBorder: "#2e2e2e",
        chatGreen: "#10a37f",
        chatGreenHover: "#0e8c6d",
        chatUserBubble: "#2b2b2b",
        chatBotBubble: "#1e1e1e",
      },
    },
  },
  plugins: [],
};
export default config;

