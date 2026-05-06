import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (typeof window !== "undefined") {
  // Visible diagnostic in the browser console
  console.log("[supabase] init", {
    url_present: !!url,
    url_preview: url?.slice(0, 30),
    anon_present: !!anon,
    anon_length: anon?.length,
  });
  if (!url || !anon) {
    console.error(
      "[supabase] MISSING ENV. Restart `npm run dev` after editing .env.local."
    );
  }
}

export const supabase = createClient(url ?? "", anon ?? "", {
  auth: { persistSession: false },
});
