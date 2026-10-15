"use client";

import React from "react";

/* What widgets inside messages can ask of the conversation: send a message
   on the user's behalf ("See other options"), and remember which previews
   replaced a stale one so they can say "Needs updating". */
export interface ConversationActions {
  ask: (text: string) => void;
  markStale: (replacementId: string) => void;
  isStaleReplacement: (actionId: string) => boolean;
}

export const ConversationContext = React.createContext<ConversationActions>({
  ask: () => {},
  markStale: () => {},
  isStaleReplacement: () => false,
});

export const useConversationActions = () => React.useContext(ConversationContext);
