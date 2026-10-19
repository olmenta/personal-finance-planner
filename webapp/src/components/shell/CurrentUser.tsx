"use client";

import React from "react";

/* The signed-in person (spec: authentication, "Who is signed in"), read
   once from the session in the app layout and shared with the shell. */
export interface CurrentUser {
  name: string;
  email: string | null;
  picture: string | null;
  /** False when auth is disabled (local/test): no logout. */
  canLogOut: boolean;
}

const DEVELOPMENT_USER: CurrentUser = { name: "Development user", email: null, picture: null, canLogOut: false };

const CurrentUserContext = React.createContext<CurrentUser>(DEVELOPMENT_USER);

export function CurrentUserProvider({ user, children }: Readonly<{ user: CurrentUser | null; children: React.ReactNode }>) {
  return <CurrentUserContext.Provider value={user ?? DEVELOPMENT_USER}>{children}</CurrentUserContext.Provider>;
}

export const useCurrentUser = () => React.useContext(CurrentUserContext);
