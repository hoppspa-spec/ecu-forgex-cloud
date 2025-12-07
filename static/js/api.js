import { getToken } from "./auth.js";
import { log } from "./ui.js";

const API_BASE = "https://ecu-forgex-cloud.onrender.com";

export async function apiAnalyzeBin(file) {
    const form = new FormData();
    form.append("file", file);

    try {
        const res = await fetch(`${API_BASE}/analyze_bin`, {
            method: "POST",
            headers: {
                Authorization: `Bearer ${getToken() || ""}`
            },
            body: form
        });

        if (!res.ok) {
            console.error("Error analyze_bin:", res.status);
            return null;
        }

        return await res.json();
    } catch (err) {
        console.error("ERR POST analyze_bin:", err);
        return null;
    }
}
