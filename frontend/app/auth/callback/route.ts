import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { type NextRequest, NextResponse } from "next/server";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!;

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");

  if (code) {
    const cookieStore = await cookies();

    const supabase = createServerClient(supabaseUrl, supabaseKey, {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            );
          } catch {
            // Called from a Server Component — safe to ignore.
          }
        },
      },
    });

    const { data, error } = await supabase.auth.exchangeCodeForSession(code);

    if (!error) {
      const identities = data?.user?.identities ?? [];
      const googleIdentity = identities.find((i) => i.provider === "google");
      const emailIdentity = identities.find((i) => i.provider === "email");

      const justAutoLinked =
        !!googleIdentity?.created_at &&
        !!emailIdentity?.created_at &&
        new Date(googleIdentity.created_at).getTime() -
          new Date(emailIdentity.created_at).getTime() >
          0 &&
        Date.now() - new Date(googleIdentity.created_at).getTime() < 60_000;

      if (justAutoLinked) {
        await supabase.auth.signOut();
        return NextResponse.redirect(
          `${origin}/login?error=google_account_exists`
        );
      }

      return NextResponse.redirect(`${origin}/dashboard`);
    }
  }

  // Something went wrong — redirect to login with an error hint
  return NextResponse.redirect(`${origin}/login?error=verification_failed`);
}