import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
export default defineConfig({
    base: "/rsudp",
    plugins: [react(), tailwindcss()],
    define: {
        "import.meta.env.VITE_BUILD_DATE": JSON.stringify(new Date().toISOString()),
    },
    server: {
        proxy: {
            "/rsudp/api/screenshot": {
                target: "http://localhost:5000",
                changeOrigin: true,
            },
        },
    },
});
