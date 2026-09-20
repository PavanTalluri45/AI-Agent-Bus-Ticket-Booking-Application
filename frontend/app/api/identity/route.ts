import { NextResponse } from "next/server";
import { cookies } from "next/headers";

import { createClient } from "@/utils/supabase/server";


const FASTAPI_BACKEND_URL =
  process.env.FASTAPI_BACKEND_URL;


export async function GET() {
  if (!FASTAPI_BACKEND_URL) {
    return NextResponse.json(
      {
        error: "Backend configuration is missing.",
      },
      {
        status: 500,
      },
    );
  }


  const cookieStore = await cookies();

  const supabase = createClient(
    cookieStore,
  );


  /*
   * First verify the authenticated user
   * through Supabase.
   */
  const {
    data: { user },
    error: userError,
  } = await supabase.auth.getUser();


  if (userError || !user) {
    return NextResponse.json(
      {
        error: "Unauthenticated.",
      },
      {
        status: 401,
      },
    );
  }


  /*
   * Then retrieve the current session so we can
   * obtain the Supabase access token.
   */
  const {
    data: { session },
    error: sessionError,
  } = await supabase.auth.getSession();


  if (
    sessionError ||
    !session?.access_token
  ) {
    return NextResponse.json(
      {
        error:
          "No active authentication session.",
      },
      {
        status: 401,
      },
    );
  }


  /*
   * Send the Supabase access token to FastAPI.
   */
  let backendResponse: Response;


  try {
    backendResponse = await fetch(
      `${FASTAPI_BACKEND_URL}/api/v1/auth/me`,
      {
        method: "GET",

        headers: {
          Authorization:
            `Bearer ${session.access_token}`,
        },

        cache: "no-store",
      },
    );
  } catch {
    return NextResponse.json(
      {
        error: "Backend unavailable.",
      },
      {
        status: 503,
      },
    );
  }


  if (!backendResponse.ok) {
    return NextResponse.json(
      {
        error:
          "Backend authentication failed.",
      },
      {
        status: backendResponse.status,
      },
    );
  }


  const identity =
    await backendResponse.json();


  return NextResponse.json(identity);
}