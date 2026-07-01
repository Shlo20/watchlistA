import { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import { Minus, Plus, X, Send, Trash2, ListChecks, Pencil, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  listLists,
  createList,
  deleteList,
  updateList,
  updateListItem,
  removeListItem,
  sendList,
  listContacts,
  getListQuotes,
  getQuoteWaLink,
  centsToDollars,
  type WatchList,
  type ListItem,
  type Contact,
  type Quote,
  type SendRecipient,
} from "@/lib/api";

type ContactChannels = { inbox: boolean; whatsapp: boolean };

type SendResult = {
  label: string;
  waLink: string | null;
  deliveredToInbox: boolean;
};

export default function ListsSection() {
  const [lists, setLists] = useState<WatchList[]>([]);
  const [listsLoading, setListsLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const creatingRef = useRef(false);

  // Delete confirmation state — deleting a list requires an explicit second tap
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<number | null>(null);
  const [deletingIds, setDeletingIds] = useState<Set<number>>(new Set());

  // Rename state
  const [editingListId, setEditingListId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [savingTitleId, setSavingTitleId] = useState<number | null>(null);

  // Item update/remove loading state
  const [updatingItemIds, setUpdatingItemIds] = useState<Set<number>>(new Set());

  // Send dialog state
  const [activeSendList, setActiveSendList] = useState<WatchList | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [contactsLoading, setContactsLoading] = useState(false);
  const [contactChannels, setContactChannels] = useState<Map<number, ContactChannels>>(new Map());
  const [rawPhone, setRawPhone] = useState("");
  const [sending, setSending] = useState(false);
  const [sendResults, setSendResults] = useState<SendResult[] | null>(null);

  // Quotes state
  const [quotesMap, setQuotesMap] = useState<Map<number, Quote[]>>(new Map());

  useEffect(() => {
    listLists()
      .then((data) => {
        setLists(data);
        Promise.all(
          data.map((l) =>
            getListQuotes(l.id)
              .then((qs) => [l.id, qs] as [number, Quote[]])
              .catch(() => [l.id, []] as [number, Quote[]])
          )
        ).then((entries) => setQuotesMap(new Map(entries)));
      })
      .catch(() => toast.error("Couldn't load lists."))
      .finally(() => setListsLoading(false));
  }, []);

  useEffect(() => {
    if (!activeSendList) return;
    setContactsLoading(true);
    listContacts()
      .then(setContacts)
      .catch(() => toast.error("Couldn't load contacts."))
      .finally(() => setContactsLoading(false));
  }, [activeSendList]);

  // ── New list ─────────────────────────────────────────────────────────────

  async function handleNewList() {
    // Ref guard: a fast double-tap can fire twice before React re-renders
    // the disabled state, which would create two lists.
    if (creatingRef.current) return;
    creatingRef.current = true;
    setCreating(true);
    try {
      const created = await createList({ items: [] });
      setLists((prev) => [created, ...prev]);
      setQuotesMap((prev) => new Map(prev).set(created.id, []));
      // Start editing the title immediately after creation
      setEditingListId(created.id);
      setEditTitle(created.title ?? "");
    } catch {
      toast.error("Couldn't create list. Try again.");
    } finally {
      creatingRef.current = false;
      setCreating(false);
    }
  }

  async function handleDeleteList(id: number) {
    if (deletingIds.has(id)) return;
    setDeletingIds((prev) => new Set(prev).add(id));
    try {
      await deleteList(id);
      setLists((prev) => prev.filter((l) => l.id !== id));
      if (editingListId === id) cancelEdit();
      toast.success("List deleted");
    } catch {
      toast.error("Couldn't delete. Try again.");
    } finally {
      setConfirmingDeleteId((prev) => (prev === id ? null : prev));
      setDeletingIds((prev) => { const s = new Set(prev); s.delete(id); return s; });
    }
  }

  // ── Rename ───────────────────────────────────────────────────────────────

  function startEdit(list: WatchList) {
    setEditingListId(list.id);
    setEditTitle(list.title ?? "");
  }

  function cancelEdit() {
    setEditingListId(null);
    setEditTitle("");
  }

  async function confirmEdit(list: WatchList) {
    if (savingTitleId !== null) return; // Enter + button click can both fire
    const title = editTitle.trim();
    // If blank or unchanged, just close without saving
    if (!title || title === list.title) {
      cancelEdit();
      return;
    }
    setSavingTitleId(list.id);
    try {
      const updated = await updateList(list.id, { title });
      setLists((prev) => prev.map((l) => (l.id === list.id ? { ...l, title: updated.title } : l)));
      cancelEdit();
    } catch {
      toast.error("Couldn't rename. Try again.");
    } finally {
      setSavingTitleId(null);
    }
  }

  // ── Item editing ─────────────────────────────────────────────────────────

  function setItemBusy(itemId: number, busy: boolean) {
    setUpdatingItemIds((prev) => {
      const s = new Set(prev);
      busy ? s.add(itemId) : s.delete(itemId);
      return s;
    });
  }

  function updateItemInState(listId: number, updatedItem: ListItem) {
    setLists((prev) =>
      prev.map((l) =>
        l.id === listId
          ? { ...l, items: l.items.map((i) => (i.id === updatedItem.id ? updatedItem : i)) }
          : l
      )
    );
  }

  function removeItemFromState(listId: number, itemId: number) {
    setLists((prev) =>
      prev.map((l) =>
        l.id === listId ? { ...l, items: l.items.filter((i) => i.id !== itemId) } : l
      )
    );
  }

  async function handleQtyChange(listId: number, item: ListItem, delta: number) {
    const newQty = Math.max(1, item.quantity + delta);
    if (newQty === item.quantity || updatingItemIds.has(item.id)) return;
    setItemBusy(item.id, true);
    updateItemInState(listId, { ...item, quantity: newQty });
    try {
      const updated = await updateListItem(listId, item.id, { quantity: newQty });
      updateItemInState(listId, updated);
    } catch {
      updateItemInState(listId, item);
      toast.error("Couldn't update quantity.");
    } finally {
      setItemBusy(item.id, false);
    }
  }

  async function handleRemoveItem(listId: number, item: ListItem) {
    if (updatingItemIds.has(item.id)) return;
    setItemBusy(item.id, true);
    removeItemFromState(listId, item.id);
    try {
      await removeListItem(listId, item.id);
    } catch {
      setLists((prev) =>
        prev.map((l) =>
          l.id === listId
            ? { ...l, items: [...l.items, item].sort((a, b) => a.position - b.position) }
            : l
        )
      );
      toast.error("Couldn't remove item.");
    } finally {
      setItemBusy(item.id, false);
    }
  }

  // ── Send dialog ──────────────────────────────────────────────────────────

  function openSendDialog(list: WatchList) {
    setActiveSendList(list);
    setContactChannels(new Map());
    setRawPhone("");
    setSendResults(null);
  }

  function closeSendDialog() {
    setActiveSendList(null);
    setContactChannels(new Map());
    setRawPhone("");
    setSendResults(null);
    setSending(false);
  }

  function toggleContact(id: number, isRegistered: boolean) {
    setContactChannels((prev) => {
      const next = new Map(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.set(id, isRegistered ? { inbox: true, whatsapp: false } : { inbox: false, whatsapp: true });
      }
      return next;
    });
  }

  function toggleWhatsApp(contactId: number) {
    setContactChannels((prev) => {
      const next = new Map(prev);
      const ch = next.get(contactId);
      if (ch) next.set(contactId, { ...ch, whatsapp: !ch.whatsapp });
      return next;
    });
  }

  async function handleSend() {
    if (!activeSendList || sending) return;
    const recipientInputs: Array<{ label: string; payload: SendRecipient }> = [];
    for (const [id, channels] of contactChannels.entries()) {
      const contact = contacts.find((c) => c.id === id);
      recipientInputs.push({
        label: contact?.nickname ?? `Contact #${id}`,
        payload: { contact_id: id, to_inbox: channels.inbox, to_whatsapp: channels.whatsapp },
      });
    }
    if (rawPhone.trim()) {
      recipientInputs.push({
        label: rawPhone.trim(),
        payload: { phone: rawPhone.trim(), to_inbox: false, to_whatsapp: true },
      });
    }
    if (recipientInputs.length === 0) {
      toast.error("Pick at least one recipient.");
      return;
    }
    setSending(true);
    try {
      const results = await sendList(activeSendList.id, recipientInputs.map((r) => r.payload));
      const mapped: SendResult[] = results.map((r, i) => ({
        label: recipientInputs[i]?.label ?? `Recipient ${i + 1}`,
        waLink: r.wa_link,
        deliveredToInbox: r.deliver_to_inbox,
      }));
      setSendResults(mapped);
      setLists((prev) =>
        prev.map((l) => (l.id === activeSendList.id ? { ...l, has_been_sent: true } : l))
      );
      const externals = mapped.filter((r) => r.waLink !== null);
      if (externals.length === 1 && externals[0].waLink) window.open(externals[0].waLink, "_blank");
      toast.success(`Sent to ${results.length} recipient${results.length === 1 ? "" : "s"}`);
    } catch (err: unknown) {
      // Surface the backend's reason when it gives one (e.g. unregistered
      // recipient can't receive to inbox) instead of a generic failure.
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Send failed. Try again.");
    } finally {
      setSending(false);
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

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <>
      <div className="px-4 py-6 mx-auto w-full max-w-[32rem] space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Lists</h2>
          <Button size="sm" onClick={handleNewList} disabled={creating}>
            <Plus className="size-4 mr-1" />
            {creating ? "Creating…" : "New list"}
          </Button>
        </div>

        {listsLoading ? (
          <p className="text-sm text-muted-foreground text-center py-8">Loading…</p>
        ) : lists.length === 0 ? (
          <div className="flex flex-col items-center gap-4 py-16 text-center">
            <div className="flex items-center justify-center size-16 rounded-2xl bg-muted">
              <ListChecks className="size-7 text-primary/60" />
            </div>
            <p className="text-sm text-muted-foreground max-w-[220px]">
              No lists yet. Create one above, then add items from the Search tab.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {lists.map((list) => {
              const quotes = quotesMap.get(list.id) ?? [];
              const isEditing = editingListId === list.id;
              const isSavingTitle = savingTitleId === list.id;

              return (
                <Card key={list.id}>
                  <CardHeader className="pb-2 pt-4">
                    <div className="flex items-start justify-between gap-2">
                      {/* Title area */}
                      <div className="flex-1 min-w-0">
                        {isEditing ? (
                          <div className="flex items-center gap-1.5">
                            <Input
                              autoFocus
                              value={editTitle}
                              onChange={(e) => setEditTitle(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") { e.preventDefault(); confirmEdit(list); }
                                if (e.key === "Escape") { e.preventDefault(); cancelEdit(); }
                              }}
                              className="h-8 text-sm font-medium flex-1"
                              disabled={isSavingTitle}
                            />
                            <button
                              type="button"
                              onClick={() => confirmEdit(list)}
                              disabled={isSavingTitle}
                              className="shrink-0 flex items-center justify-center size-8 rounded-lg border border-input text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-40 transition-colors"
                              aria-label="Confirm rename"
                            >
                              <Check className="size-3.5" />
                            </button>
                            <button
                              type="button"
                              onClick={cancelEdit}
                              disabled={isSavingTitle}
                              className="shrink-0 flex items-center justify-center size-8 rounded-lg border border-input text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-40 transition-colors"
                              aria-label="Cancel rename"
                            >
                              <X className="size-3.5" />
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-center gap-1.5 min-w-0">
                            <p className="text-base font-semibold leading-snug truncate">
                              {list.title}
                            </p>
                            <button
                              type="button"
                              onClick={() => startEdit(list)}
                              className="shrink-0 p-1 text-muted-foreground hover:text-foreground transition-colors"
                              aria-label="Rename list"
                            >
                              <Pencil className="size-3" />
                            </button>
                          </div>
                        )}
                        {!isEditing && (
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {list.items.length} item{list.items.length === 1 ? "" : "s"}
                          </p>
                        )}
                      </div>

                      {/* Actions */}
                      {!isEditing && (
                        confirmingDeleteId === list.id ? (
                          <div className="flex items-center gap-2 shrink-0">
                            <span className="text-xs text-muted-foreground">Delete?</span>
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => handleDeleteList(list.id)}
                              disabled={deletingIds.has(list.id)}
                              className="h-7 px-2 text-xs"
                            >
                              {deletingIds.has(list.id) ? "Deleting…" : "Yes, delete"}
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setConfirmingDeleteId(null)}
                              disabled={deletingIds.has(list.id)}
                              className="h-7 px-2 text-xs"
                            >
                              Cancel
                            </Button>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2 shrink-0">
                            {list.has_been_sent && (
                              <Badge variant="secondary" className="text-xs">Sent</Badge>
                            )}
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => openSendDialog(list)}
                              disabled={list.items.length === 0}
                              title={list.items.length === 0 ? "Add items before sending" : undefined}
                              className="h-7 px-2 text-xs"
                            >
                              <Send className="size-3 mr-1" />
                              Send
                            </Button>
                            <button
                              type="button"
                              onClick={() => setConfirmingDeleteId(list.id)}
                              className="text-muted-foreground hover:text-destructive transition-colors p-1"
                              aria-label="Delete list"
                            >
                              <Trash2 className="size-4" />
                            </button>
                          </div>
                        )
                      )}
                    </div>
                  </CardHeader>

                  {list.items.length === 0 && (
                    <CardContent className="pt-0 pb-3">
                      <p className="text-xs text-muted-foreground">
                        Empty list — add items from the Search tab.
                      </p>
                    </CardContent>
                  )}

                  {list.items.length > 0 && (
                    <CardContent className="pt-0 pb-3">
                      <ul className="divide-y">
                        {list.items.map((item) => {
                          const displayName = item.product_name ?? item.custom_product_name ?? "Item";
                          const busy = updatingItemIds.has(item.id);
                          return (
                            <li key={item.id} className="flex items-center gap-2 py-2 min-h-[44px]">
                              <span className="flex-1 text-sm truncate">{displayName}</span>
                              <div className="flex items-center gap-1 shrink-0">
                                <button
                                  type="button"
                                  disabled={busy || item.quantity <= 1}
                                  onClick={() => handleQtyChange(list.id, item, -1)}
                                  className="flex items-center justify-center size-6 rounded border border-input text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-40 transition-colors"
                                  aria-label="Decrease quantity"
                                >
                                  <Minus className="size-3" />
                                </button>
                                <span className="w-7 text-center text-sm tabular-nums select-none">
                                  {item.quantity}
                                </span>
                                <button
                                  type="button"
                                  disabled={busy}
                                  onClick={() => handleQtyChange(list.id, item, 1)}
                                  className="flex items-center justify-center size-6 rounded border border-input text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-40 transition-colors"
                                  aria-label="Increase quantity"
                                >
                                  <Plus className="size-3" />
                                </button>
                              </div>
                              <button
                                type="button"
                                disabled={busy}
                                onClick={() => handleRemoveItem(list.id, item)}
                                className="text-muted-foreground hover:text-destructive transition-colors p-1 disabled:opacity-40"
                                aria-label={`Remove ${displayName}`}
                              >
                                <X className="size-3.5" />
                              </button>
                            </li>
                          );
                        })}
                      </ul>
                    </CardContent>
                  )}

                  {quotes.length > 0 && (
                    <CardContent className="pt-0 pb-3 border-t">
                      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mt-2 mb-1.5">
                        Quotes
                      </p>
                      <div className="space-y-1.5">
                        {quotes.map((q) => (
                          <div
                            key={q.send_id}
                            className="flex items-center justify-between gap-2 rounded-md bg-muted/50 px-3 py-2"
                          >
                            <div className="min-w-0">
                              <p className="text-sm font-medium truncate">
                                {q.supplier_name ?? "Supplier"}
                              </p>
                              {q.total_cents > 0 && (
                                <p className="text-xs text-muted-foreground">
                                  Total: ${centsToDollars(q.total_cents)}
                                </p>
                              )}
                            </div>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleShareQuoteWa(q.send_id)}
                              className="h-8 text-xs shrink-0 text-green-400 hover:text-green-300 hover:bg-green-500/10"
                            >
                              Share via WhatsApp
                            </Button>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Send dialog */}
      <Dialog
        open={activeSendList !== null}
        onOpenChange={(open) => { if (!open) closeSendDialog(); }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Send &ldquo;{activeSendList?.title}&rdquo;</DialogTitle>
          </DialogHeader>

          {sendResults !== null ? (
            <div className="space-y-3">
              <p className="text-sm font-medium">Results</p>
              <ul className="space-y-0 divide-y">
                {sendResults.map((r, i) => (
                  <li key={i} className="flex items-center justify-between gap-3 py-2.5">
                    <span className="text-sm truncate flex-1">{r.label}</span>
                    <div className="flex flex-col items-end gap-0.5 shrink-0">
                      {r.deliveredToInbox && (
                        <span className="text-xs text-muted-foreground">Delivered to inbox</span>
                      )}
                      {r.waLink && (
                        <a
                          href={r.waLink}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm font-medium text-green-400 hover:text-green-300 hover:underline"
                        >
                          Open WhatsApp
                        </a>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
              <DialogFooter>
                <Button onClick={closeSendDialog}>Done</Button>
              </DialogFooter>
            </div>
          ) : (
            <div className="space-y-4">
              {contactsLoading ? (
                <p className="text-sm text-muted-foreground">Loading contacts…</p>
              ) : contacts.length > 0 ? (
                <div>
                  <p className="text-sm font-medium mb-2">Contacts</p>
                  <ul className="space-y-0.5 max-h-52 overflow-y-auto">
                    {contacts.map((c) => {
                      const isRegistered = c.linked_user_id !== null;
                      const selected = contactChannels.has(c.id);
                      const channels = contactChannels.get(c.id);
                      return (
                        <li key={c.id}>
                          <div className="flex items-center gap-3 py-2 min-h-[40px]">
                            <Checkbox
                              id={`send-contact-${c.id}`}
                              checked={selected}
                              onCheckedChange={() => toggleContact(c.id, isRegistered)}
                            />
                            <label
                              htmlFor={`send-contact-${c.id}`}
                              className="flex-1 text-sm cursor-pointer select-none"
                            >
                              <span className="font-medium">{c.nickname}</span>
                              <span className="text-muted-foreground ml-2 text-xs">{c.phone}</span>
                            </label>
                          </div>
                          {selected && (
                            <div className="ml-8 mb-1.5 flex items-center gap-1.5 text-xs">
                              {isRegistered ? (
                                <>
                                  <span className="px-1.5 py-0.5 rounded bg-primary/15 text-primary font-medium">
                                    Inbox
                                  </span>
                                  <button
                                    type="button"
                                    onClick={() => toggleWhatsApp(c.id)}
                                    className={cn(
                                      "px-1.5 py-0.5 rounded border transition-colors",
                                      channels?.whatsapp
                                        ? "bg-green-500/15 border-green-500/30 text-green-400"
                                        : "border-border text-muted-foreground hover:text-foreground"
                                    )}
                                  >
                                    {channels?.whatsapp ? "WhatsApp ✓" : "+ WhatsApp"}
                                  </button>
                                </>
                              ) : (
                                <span className="text-muted-foreground">WhatsApp only · not on app</span>
                              )}
                            </div>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No contacts yet — you can still send to a number below.
                </p>
              )}

              <div className="space-y-1.5">
                <Label htmlFor="send-raw-phone">Or enter a phone number</Label>
                <Input
                  id="send-raw-phone"
                  type="tel"
                  placeholder="5555550100"
                  value={rawPhone}
                  onChange={(e) => setRawPhone(e.target.value)}
                />
                {rawPhone.trim() && (
                  <p className="text-xs text-muted-foreground">WhatsApp only — unregistered number</p>
                )}
              </div>

              <DialogFooter>
                <Button variant="outline" onClick={closeSendDialog}>Cancel</Button>
                <Button
                  disabled={sending || (contactChannels.size === 0 && !rawPhone.trim())}
                  onClick={handleSend}
                >
                  {sending ? "Sending…" : "Send"}
                </Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
