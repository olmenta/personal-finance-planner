import { NextResponse, type NextRequest } from "next/server";
import { auth0 } from "./lib/auth0";

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

/* Without Auth0 everyone is the development user, so only this machine may
   reach the app: a tunnel (dev.olmenta.com) must never expose it. */
function isLocalRequest(request: NextRequest): boolean {
  const hosts = [request.headers.get("host"), request.headers.get("x-forwarded-host")];
  return hosts.every((value) => {
    if (!value) return true;
    const host = value.split(",")[0].trim().replace(/:\d+$/, "");
    return LOCAL_HOSTS.has(host);
  });
}

/* Every page and BFF route needs a session (spec: authentication). The SDK
   handles /auth/*; pages without a session go to login and come back;
   /api/* answers 401 so the client can send the person to sign in. */
export async function middleware(request: NextRequest) {
  if (!auth0) {
    // local/test without Auth0
    if (isLocalRequest(request)) return NextResponse.next();
    return new NextResponse("Sign-in isn't configured on this server.", { status: 403 });
  }
  const authResponse = await auth0.middleware(request);
  const { pathname, search } = request.nextUrl;
  if (pathname.startsWith("/auth")) return authResponse;
  const session = await auth0.getSession(request);
  if (!session) {
    if (pathname.startsWith("/api/")) {
      return NextResponse.json({ code: "unauthenticated" }, { status: 401 });
    }
    const login = new URL("/auth/login", request.url);
    login.searchParams.set("returnTo", `${pathname}${search}`);
    return NextResponse.redirect(login);
  }
  return authResponse;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|brand/|.*\\.(?:svg|png|jpg|jpeg|gif|ico|webp)$).*)"],
};
