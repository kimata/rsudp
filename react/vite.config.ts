import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
    base: "/rsudp",
    plugins: [react()],
    server: {
        proxy: {
            "/rsudp/api/screenshot": {
                target: "http://localhost:5000",
                changeOrigin: true,
            },
        },
    },
});
