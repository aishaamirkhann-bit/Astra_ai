"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { MessageSquare, X } from "lucide-react";
import ChatThread from "@/components/messaging/ChatThread";
import { openSellerConversation } from "@/lib/api";
import { showToast } from "@/lib/toast";
import type { DirectConversation } from "@/lib/types";

/** Right-side drawer that lets the buyer talk to the seller of a listing. */
export default function SellerChatDrawer({
  open,
  productId,
  productName,
  sellerName,
  onClose,
}: {
  open: boolean;
  productId: string;
  productName: string;
  sellerName: string;
  onClose: () => void;
}) {
  const [conversation, setConversation] = useState<DirectConversation | null>(null);
  const [opening, setOpening] = useState(false);

  useEffect(() => {
    if (!open || conversation) return;
    setOpening(true);
    openSellerConversation(productId)
      .then(setConversation)
      .catch((requestError: Error) => {
        showToast(requestError.message || "Could not open a chat with this seller.", "error");
        onClose();
      })
      .finally(() => setOpening(false));
  }, [open, conversation, productId, onClose]);

  useEffect(() => {
    if (!open) setConversation(null);
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[80] flex justify-end bg-slate-950/70 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) onClose();
          }}
        >
          <motion.aside
            className="flex h-full w-full max-w-md flex-col border-l border-base-600 bg-base-950 p-5"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 28 }}
          >
            <div className="mb-4 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.2em] text-violet-400">
                  <MessageSquare className="h-3 w-3" /> Seller chat
                </p>
                <h3 className="mt-1 truncate font-display text-base font-bold text-ink-100">{sellerName}</h3>
                <p className="truncate text-[11px] text-ink-500">About: {productName}</p>
              </div>
              <button onClick={onClose} aria-label="Close seller chat" className="rounded-full bg-base-800 p-2 text-ink-300 hover:text-ink-100">
                <X className="h-4 w-4" />
              </button>
            </div>

            {opening || !conversation ? (
              <p className="m-auto text-xs text-ink-700">Connecting to {sellerName}…</p>
            ) : (
              <ChatThread conversationId={conversation.id} />
            )}
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
