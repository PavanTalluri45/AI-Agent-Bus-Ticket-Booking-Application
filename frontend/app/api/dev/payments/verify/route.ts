import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createClient } from "@/utils/supabase/server";

const FASTAPI_BACKEND_URL = process.env.FASTAPI_BACKEND_URL;

export async function POST(request: Request) {
  if (!FASTAPI_BACKEND_URL) {
    return NextResponse.json(
      { error: "Backend configuration is missing." },
      { status: 500 }
    );
  }

  const cookieStore = await cookies();
  const supabase = createClient(cookieStore);

  // Verify the authenticated user
  const {
    data: { user },
    error: userError,
  } = await supabase.auth.getUser();

  if (userError || !user) {
    return NextResponse.json(
      { error: "Unauthenticated." },
      { status: 401 }
    );
  }

  // Get the current Supabase session
  const {
    data: { session },
    error: sessionError,
  } = await supabase.auth.getSession();

  if (sessionError || !session?.access_token) {
    return NextResponse.json(
      { error: "No active authentication session." },
      { status: 401 }
    );
  }

  const body = await request.json();

  let backendResponse: Response;

  try {
    backendResponse = await fetch(
      `${FASTAPI_BACKEND_URL}/api/v1/dev/payments/verify`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
        cache: "no-store",
      }
    );
  } catch {
    return NextResponse.json(
      { error: "Backend unavailable." },
      { status: 503 }
    );
  }

  const responseBody = await backendResponse.json();

  return NextResponse.json(responseBody, {
    status: backendResponse.status,
  });
}