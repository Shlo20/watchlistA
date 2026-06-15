import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Inbox, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  getInbox,
  updateSendItem,
  markAllReceived,
  dismissSend,
  clearInbox,
  submitQuote,
  getQuoteWaLink,
  centsToDollars,
  dollarsToCents,
  type InboxSend,
  type SendItemState,
} from "@/lib/api";

type DateGroup = "Today" | "Yesterday" | "This Week" | "Earlier";

function getDateGroup(dateStr: string): DateGroup {
  const diffDays = Math.floor((Date.now() - new Date(dateStr).getTime()) / 86_400_000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return "This Week";
  return "Earlier";
}

function groupSends(sends: InboxSend[]): Array<{ label: DateGroup; sends: InboxSend[] }> {
  const groups: Record<DateGroup, InboxSend[]> = {
    Today: [],
    Yesterday: [],
    "This Week": [],
    Earlier: [],
  };
  for (const s of sends) {
    groups[getDateGroup(s.created_at)].push(s);
  }
  const order: DateGroup[] = ["Today", "Yesterday", "This Week", "Earlier"];
  return order
    .filter((g) => groups[g].length > 0)
    .map((g) => ({ label: g, sends: groups[g] }));
}

function getItemState(itemStates: SendItemState[], listItemId: number): SendItemState {
  return (
    itemStates.find((s) => s.list_item_id === listItemId) ?? {
      list_item_id: listItemId,
      checked: false,
      received_quantity: 0,
      unit_price_cents: null,
    }
  );
}

function applyCheck(send: InboxSend, listItemId: number, checked: boolean): InboxSend {
  const itemStates = send.item_states ?? [];
  const exists = itemStates.some((s) => s.list_item_id === listItemId);
  return {
    ...send,
    item_states: exists
      ? itemStates.map((s) => (s.list_item_id === listItemId ? { ...s, checked } : s))
      : [...itemStates, { list_item_id: listItemId, checked, received_quantity: 0, unit_price_cents: null }],
  };
}

export default function InboxSection() {
  const [sends, setSends] = useState<InboxSend[]>([]);
  const [loading, setLoading] = useState(true);
  const [dismissingIds, setDismissingIds] = useState<Set<number>>(new Set());
  const [clearConfirming, setClearConfirming] = useState(false);
  const [clearing, setClearing] = useState(false);

  // Quote pricing state
  const [quotingIds, setQuotingIds] = useState<Set<number>>(new Set());
  const [priceInputs, setPriceInputs] = useState<Map<number, Map<number, string>>>(new Map());
  const [submittingIds, setSubmittingIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    getInbox()
      .then(setSends)
      .catch(() => toast.error("Couldn't load inbox."))
      .finally(() => setLoading(false));
  }, []);

  async function handleToggle(sendId: number, listItemId: number, newChecked: boolean) {
    setSends((prev) =>
      prev.map((s) => (s.id === sendId ? applyCheck(s, listItemId, newChecked) : s))
    );
    try {
      await updateSendItem(sendId, listItemId, { checked: newChecked });
    } catch {
      setSends((prev) =>
        prev.map((s) => (s.id === sendId ? applyCheck(s, listItemId, !newChecked) : s))
      );
      toast.error("Couldn't update. Try again.");
    }
  }

  async function handleMarkAll(sendId: number) {
    try {
      const updated = await markAllReceived(sendId);
      setSends((prev) => prev.map((s) => (s.id === sendId ? updated : s)));
      toast.success("All items marked received");
    } catch {
      toast.error("Couldn't update. Try again.");
    }
  }

  async function handleDismiss(sendId: number) {
    setDismissingIds((prev) => new Set(prev).add(sendId));
    try {
      await dismissSend(sendId);
      setTimeout(() => {
        setSends((prev) => prev.filter((s) => s.id !== sendId));
        setDismissingIds((prev) => {
          const next = new Set(prev);
          next.delete(sendId);
          return next;
        });
      }, 200);
    } catch {
      setDismissingIds((prev) => {
        const next = new Set(prev);
        next.delete(sendId);
        return next;
      });
      toast.error("Couldn't dismiss. Try again.");
    }
  }

  async function handleClearInbox() {
    setClearing(true);
    try {
      await clearInbox();
      setSends([]);
      setClearConfirming(false);
      toast.success("Inbox cleared");
    } catch {
      toast.error("Couldn't clear inbox. Try again.");
    } finally {
      setClearing(false);
    }
  }

  function startQuoting(sendId: number) {
    setQuotingIds((prev) => new Set(prev).add(sendId));
    setPriceInputs((prev) => {
      const next = new Map(prev);
      if (!next.has(sendId)) next.set(sendId, new Map());
      return next;
    });
  }

  function cancelQuoting(sendId: number) {
    setQuotingIds((prev) => {
      const next = new Set(prev);
      next.delete(sendId);
      return next;
    });
  }

  function setPriceInput(sendId: number, listItemId: number, value: string) {
    setPriceInputs((prev) => {
      const next = new Map(prev);
      const inner = new Map(next.get(sendId) ?? []);
      inner.set(listItemId, value);
      next.set(sendId, inner);
      return next;
    });
  }

  async function handleSubmitQuote(send: InboxSend) {
    const inputs = priceInputs.get(send.id) ?? new Map<number, string>();

    // Save prices
    const patches = send.items.map(async (item) => {
      const raw = inputs.get(item.id) ?? "";
      const cents = raw.trim() !== "" ? dollarsToCents(raw) : null;
      if (cents !== null || raw.trim() !== "") {
        await updateSendItem(send.id, item.id, { unit_price_cents: cents });
      }
    });
    setSubmittingIds((prev) => new Set(prev).add(send.id));
    try {
      await Promise.all(patches);
      const updated = await submitQuote(send.id);
      setSends((prev) => prev.map((s) => (s.id === send.id ? updated : s)));
      cancelQuoting(send.id);
      toast.success("Quote submitted");
    } catch {
      toast.error("Couldn't submit quote. Try again.");
    } finally {
      setSubmittingIds((prev) => {
        const next = new Set(prev);
        next.delete(send.id);
        return next;
      });
    }
  }

  async function handleShareQuoteWa(sendId: number) {
    try {
      const link = await getQuoteWaLink(sendId);
      window.open(link, "_blank");
    } catch {
      toast.error("Couldn't get WhatsApp link.");
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (sends.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-5 text-center px-8">
        <div className="flex items-center justify-center size-20 rounded-2xl bg-muted">
          <Inbox className="size-9 text-primary/70" />
        </div>
        <div className="space-y-1.5">
          <p className="text-lg font-semibold">Inbox is clear</p>
          <p className="text-sm text-muted-foreground max-w-[220px]">
            Lists sent to you will appear here.
          </p>
        </div>
      </div>
    );
  }

  const groups = groupSends(sends);

  return (
    <div className="px-4 py-6 mx-auto w-full max-w-[32rem] space-y-6">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Inbox</h2>
        {clearConfirming ? (
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Clear all?</span>
            <Button
              size="sm"
              variant="destructive"
              onClick={handleClearInbox}
              disabled={clearing}
              className="h-8 text-xs"
            >
              {clearing ? "Clearing…" : "Yes, clear"}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setClearConfirming(false)}
              className="h-8 text-xs"
            >
              Cancel
            </Button>
          </div>
        ) : (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setClearConfirming(true)}
            className="h-8 text-xs text-muted-foreground hover:text-foreground"
          >
            Clear inbox
          </Button>
        )}
      </div>

      {/* Date groups */}
      {groups.map(({ label, sends: groupSends }) => (
        <section key={label} className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground px-1">
            {label}
          </h3>

          {groupSends.map((send) => {
            const items = send.items ?? [];
            const itemStates = send.item_states ?? [];
            const checkedCount = itemStates.filter((s) => s.checked).length;
            const total = items.length;
            const progress = total > 0 ? (checkedCount / total) * 100 : 0;
            const allDone = total > 0 && checkedCount === total;
            const dismissing = dismissingIds.has(send.id);
            const isQuoting = quotingIds.has(send.id);
            const isSubmitting = submittingIds.has(send.id);
            const alreadyQuoted = send.quoted_at !== null;
            const inputs = priceInputs.get(send.id) ?? new Map<number, string>();

            // Running total from current inputs
            let runningCents = 0;
            let hasAnyPrice = false;
            if (isQuoting) {
              for (const item of items) {
                const raw = inputs.get(item.id) ?? "";
                if (raw.trim() !== "") {
                  const c = dollarsToCents(raw);
                  if (c !== null) {
                    runningCents += c * item.quantity;
                    hasAnyPrice = true;
                  }
                }
              }
            }

            // Already-submitted quote total from server state
            let submittedTotal = 0;
            if (alreadyQuoted) {
              for (const state of itemStates) {
                if (state.unit_price_cents !== null) {
                  const item = items.find((i) => i.id === state.list_item_id);
                  if (item) submittedTotal += state.unit_price_cents * item.quantity;
                }
              }
            }

            return (
              <div
                key={send.id}
                className={[
                  "transition-all duration-150",
                  dismissing
                    ? "opacity-0 scale-95 pointer-events-none"
                    : "opacity-100 scale-100",
                ].join(" ")}
              >
                <Card>
                  <CardHeader className="pb-2">
                    <div className="flex items-start gap-2">
                      <div className="min-w-0 flex-1">
                        <CardTitle className="text-base truncate">
                          {send.list_title ?? "Restock list"}
                        </CardTitle>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {send.sender_name ? `From ${send.sender_name}` : "Received list"}
                        </p>
                      </div>
                      <div className="flex items-center gap-1 shrink-0 mt-0.5">
                        <Badge variant={allDone ? "default" : "secondary"} className="text-xs">
                          {checkedCount}/{total}
                        </Badge>
                        <button
                          type="button"
                          onClick={() => handleDismiss(send.id)}
                          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors flex items-center justify-center min-w-[32px] min-h-[32px]"
                          aria-label="Dismiss"
                        >
                          <X className="size-3.5" />
                        </button>
                      </div>
                    </div>
                    {/* Progress bar */}
                    <div className="h-1 bg-muted rounded-full mt-2 overflow-hidden">
                      <div
                        className="h-full bg-primary rounded-full transition-all duration-300"
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                  </CardHeader>

                  <CardContent className="pt-0 pb-3">
                    {items.length === 0 ? (
                      <p className="text-sm text-muted-foreground py-2">No items.</p>
                    ) : isQuoting ? (
                      /* ── Pricing mode ── */
                      <div className="space-y-2">
                        <ul className="space-y-1">
                          {items.map((item) => {
                            const name = item.product_name ?? item.custom_product_name ?? "Item";
                            return (
                              <li key={item.id} className="flex items-center gap-2 px-1">
                                <span className="text-sm flex-1 min-w-0 truncate">
                                  {item.quantity}× {name}
                                </span>
                                <div className="relative w-24 shrink-0">
                                  <span className="absolute left-2 top-1/2 -translate-y-1/2 text-sm text-muted-foreground pointer-events-none">
                                    $
                                  </span>
                                  <Input
                                    type="number"
                                    min="0"
                                    step="0.01"
                                    placeholder="0.00"
                                    value={inputs.get(item.id) ?? ""}
                                    onChange={(e) => setPriceInput(send.id, item.id, e.target.value)}
                                    className="pl-6 h-8 text-sm"
                                  />
                                </div>
                              </li>
                            );
                          })}
                        </ul>
                        {hasAnyPrice && (
                          <p className="text-sm font-semibold text-right px-1">
                            Total: ${centsToDollars(runningCents)}
                          </p>
                        )}
                        <div className="flex gap-2 pt-1 border-t border-border/50">
                          <Button
                            size="sm"
                            onClick={() => handleSubmitQuote(send)}
                            disabled={isSubmitting}
                            className="h-8 text-xs flex-1"
                          >
                            {isSubmitting ? "Submitting…" : "Submit quote"}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => cancelQuoting(send.id)}
                            disabled={isSubmitting}
                            className="h-8 text-xs"
                          >
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : (
                      /* ── Normal / submitted mode ── */
                      <>
                        <ul className="space-y-0.5">
                          {items.map((item) => {
                            const state = getItemState(itemStates, item.id);
                            const name =
                              item.product_name ?? item.custom_product_name ?? "Item";
                            const label = `${item.quantity}× ${name}`;
                            return (
                              <li key={item.id}>
                                <button
                                  type="button"
                                  onClick={() =>
                                    handleToggle(send.id, item.id, !state.checked)
                                  }
                                  className="w-full flex items-center gap-3 rounded-lg px-3 min-h-[44px] hover:bg-muted/60 transition-colors text-left"
                                  aria-label={`Toggle ${label}`}
                                >
                                  <Checkbox
                                    checked={state.checked}
                                    onCheckedChange={(checked) =>
                                      handleToggle(send.id, item.id, !!checked)
                                    }
                                    aria-hidden
                                    tabIndex={-1}
                                    onClick={(e) => e.stopPropagation()}
                                  />
                                  <span
                                    className={[
                                      "text-sm font-medium transition-colors flex-1 min-w-0 truncate",
                                      state.checked
                                        ? "line-through text-muted-foreground"
                                        : "",
                                    ].join(" ")}
                                  >
                                    {label}
                                  </span>
                                  {state.unit_price_cents !== null && (
                                    <span className="text-xs text-muted-foreground shrink-0">
                                      ${centsToDollars(state.unit_price_cents)} ea
                                    </span>
                                  )}
                                </button>
                              </li>
                            );
                          })}
                        </ul>

                        {alreadyQuoted ? (
                          /* Submitted quote banner */
                          <div className="pt-2 border-t border-border/50 mt-2 space-y-2">
                            <div className="flex items-center justify-between px-1">
                              <span className="text-xs text-muted-foreground">Quote sent</span>
                              {submittedTotal > 0 && (
                                <span className="text-sm font-semibold">
                                  ${centsToDollars(submittedTotal)}
                                </span>
                              )}
                            </div>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleShareQuoteWa(send.id)}
                              className="h-8 text-xs w-full"
                            >
                              Send via WhatsApp
                            </Button>
                          </div>
                        ) : (
                          <div className="pt-2 border-t border-border/50 mt-2 flex gap-2">
                            {!allDone && (
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => handleMarkAll(send.id)}
                                className="h-8 text-xs text-muted-foreground hover:text-foreground flex-1"
                              >
                                Mark all received
                              </Button>
                            )}
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => startQuoting(send.id)}
                              className="h-8 text-xs text-muted-foreground hover:text-foreground flex-1"
                            >
                              Create quote
                            </Button>
                          </div>
                        )}
                      </>
                    )}
                  </CardContent>
                </Card>
              </div>
            );
          })}
        </section>
      ))}
    </div>
  );
}
