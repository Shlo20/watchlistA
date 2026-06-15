import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Minus, Plus, X, Send, Trash2, ListChecks } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
  sendList,
  listContacts,
  searchProducts,
  type WatchList,
  type Contact,
  type Product,
  type SendRecipient,
} from "@/lib/api";

type View = "index" | "builder";

type DraftItem = {
  key: string;
  product_id?: number;
  custom_product_name?: string;
  quantity: number;
  displayName: string;
};

type ContactChannels = { inbox: boolean; whatsapp: boolean };

type SendResult = {
  label: string;
  waLink: string | null;
  deliveredToInbox: boolean;
};

export default function ListsSection() {
  // Index state
  const [view, setView] = useState<View>("index");
  const [lists, setLists] = useState<WatchList[]>([]);
  const [listsLoading, setListsLoading] = useState(true);

  // Builder state
  const [draftTitle, setDraftTitle] = useState("");
  const [draftItems, setDraftItems] = useState<DraftItem[]>([]);
  const [searchInput, setSearchInput] = useState("");
  const [suggestions, setSuggestions] = useState<Product[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [customText, setCustomText] = useState<string | null>(null);
  const [itemQty, setItemQty] = useState(1);
  const [saving, setSaving] = useState(false);

  // Send dialog state
  const [activeSendList, setActiveSendList] = useState<WatchList | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [contactsLoading, setContactsLoading] = useState(false);
  // Maps contact id → chosen channels; being in the map means the contact is selected
  const [contactChannels, setContactChannels] = useState<Map<number, ContactChannels>>(new Map());
  const [rawPhone, setRawPhone] = useState("");
  const [sending, setSending] = useState(false);
  const [sendResults, setSendResults] = useState<SendResult[] | null>(null);

  // ---- load lists on mount ----

  useEffect(() => {
    listLists()
      .then((data) =>
        setLists(
          [...data].sort(
            (a, b) =>
              new Date(b.created_at).getTime() -
              new Date(a.created_at).getTime()
          )
        )
      )
      .catch(() => toast.error("Couldn't load lists."))
      .finally(() => setListsLoading(false));
  }, []);

  // ---- load contacts when send dialog opens ----

  useEffect(() => {
    if (!activeSendList) return;
    setContactsLoading(true);
    listContacts()
      .then(setContacts)
      .catch(() => toast.error("Couldn't load contacts."))
      .finally(() => setContactsLoading(false));
  }, [activeSendList]);

  // ---- debounced product search ----

  useEffect(() => {
    if (!searchInput.trim() || selectedProduct !== null || customText !== null) {
      setSuggestions([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const results = await searchProducts(searchInput);
        setSuggestions(results.slice(0, 5));
      } catch {
        // silent — user can still use custom fallback
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [searchInput, selectedProduct, customText]);

  // ---- builder helpers ----

  const isItemSelected = selectedProduct !== null || customText !== null;
  const showSuggestions = searchInput.trim().length > 0 && !isItemSelected;

  function clearItemSelection() {
    setSelectedProduct(null);
    setCustomText(null);
    setSearchInput("");
    setSuggestions([]);
  }

  function resetBuilder() {
    setDraftTitle("");
    setDraftItems([]);
    clearItemSelection();
    setItemQty(1);
  }

  function addItemToDraft() {
    if (!isItemSelected) return;
    const key = `${Date.now()}-${Math.random()}`;
    const newItem: DraftItem = selectedProduct
      ? {
          key,
          product_id: selectedProduct.id,
          quantity: itemQty,
          displayName: selectedProduct.name,
        }
      : {
          key,
          custom_product_name: customText!,
          quantity: itemQty,
          displayName: customText!,
        };
    setDraftItems((prev) => [...prev, newItem]);
    clearItemSelection();
    setItemQty(1);
  }

  function removeDraftItem(key: string) {
    setDraftItems((prev) => prev.filter((i) => i.key !== key));
  }

  async function handleSaveList() {
    if (draftItems.length === 0) return;
    setSaving(true);
    try {
      const created = await createList({
        title: draftTitle.trim() || undefined,
        items: draftItems.map((item) => ({
          product_id: item.product_id,
          custom_product_name: item.custom_product_name,
          quantity: item.quantity,
        })),
      });
      setLists((prev) => [created, ...prev]);
      resetBuilder();
      setView("index");
      toast.success("List saved");
    } catch {
      toast.error("Couldn't save. Try again.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteList(id: number) {
    try {
      await deleteList(id);
      setLists((prev) => prev.filter((l) => l.id !== id));
      toast.success("List deleted");
    } catch {
      toast.error("Couldn't delete. Try again.");
    }
  }

  // ---- send dialog helpers ----

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
        // Registered: inbox on by default; unregistered: whatsapp only
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
    if (!activeSendList) return;

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
      const results = await sendList(
        activeSendList.id,
        recipientInputs.map((r) => r.payload)
      );

      const mapped: SendResult[] = results.map((r, i) => ({
        label: recipientInputs[i]?.label ?? `Recipient ${i + 1}`,
        waLink: r.wa_link,
        deliveredToInbox: r.deliver_to_inbox,
      }));
      setSendResults(mapped);

      const externals = mapped.filter((r) => r.waLink !== null);
      if (externals.length === 1 && externals[0].waLink) {
        window.open(externals[0].waLink, "_blank");
      }

      toast.success(
        `Sent to ${results.length} recipient${results.length === 1 ? "" : "s"}`
      );
    } catch {
      toast.error("Send failed. Try again.");
    } finally {
      setSending(false);
    }
  }

  // ---- render ----

  return (
    <>
      {/* Index view */}
      {view === "index" && (
        <div className="px-4 py-6 mx-auto w-full max-w-[32rem] space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold">Lists</h2>
            <Button size="sm" onClick={() => setView("builder")}>
              <Plus className="size-4 mr-1" />
              New list
            </Button>
          </div>

          <Card>
            <CardContent className="pt-4">
              {listsLoading ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  Loading…
                </p>
              ) : lists.length === 0 ? (
                <div className="flex flex-col items-center gap-3 py-10">
                  <div className="flex items-center justify-center size-16 rounded-2xl bg-muted">
                    <ListChecks className="size-7 text-primary/60" />
                  </div>
                  <p className="text-sm text-muted-foreground">
                    No lists yet. Create one above.
                  </p>
                </div>
              ) : (
                <ul className="divide-y">
                  {lists.map((list) => (
                    <li
                      key={list.id}
                      className="flex items-center gap-3 py-3 min-h-[52px]"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">
                          {list.title ?? "Untitled list"}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {list.items.length} item
                          {list.items.length === 1 ? "" : "s"}
                        </p>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => openSendDialog(list)}
                      >
                        <Send className="size-3 mr-1" />
                        Send
                      </Button>
                      <button
                        type="button"
                        onClick={() => handleDeleteList(list.id)}
                        className="shrink-0 text-muted-foreground hover:text-destructive transition-colors"
                        aria-label="Delete list"
                      >
                        <Trash2 className="size-4" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Builder view */}
      {view === "builder" && (
        <div className="px-4 py-6 mx-auto w-full max-w-[32rem] space-y-4">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => {
                resetBuilder();
                setView("index");
              }}
              className="text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              ← Back
            </button>
            <h2 className="text-xl font-semibold">New list</h2>
          </div>

          <Card>
            <CardContent className="pt-4">
              <div className="space-y-1.5">
                <Label htmlFor="list-title">Title (optional)</Label>
                <Input
                  id="list-title"
                  placeholder="e.g. Weekly restock"
                  value={draftTitle}
                  onChange={(e) => setDraftTitle(e.target.value)}
                />
              </div>
            </CardContent>
          </Card>

          {/* Item adder */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Add items</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="item-search">Search or type</Label>
                <Input
                  id="item-search"
                  placeholder="iPhone case, screen protector, …"
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  disabled={isItemSelected}
                  autoComplete="off"
                />
              </div>

              {showSuggestions && (
                <div className="rounded-lg border divide-y overflow-hidden">
                  {suggestions.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => {
                        setSelectedProduct(p);
                        setCustomText(null);
                        setSuggestions([]);
                      }}
                      className="w-full flex items-center justify-between gap-3 px-3 py-3 text-sm text-left hover:bg-muted transition-colors min-h-[44px]"
                    >
                      <span className="truncate">{p.name}</span>
                      <Badge
                        variant="secondary"
                        className="shrink-0 capitalize text-xs"
                      >
                        {p.category.replace("_", " ")}
                      </Badge>
                    </button>
                  ))}
                  <button
                    type="button"
                    onClick={() => {
                      setCustomText(searchInput.trim());
                      setSelectedProduct(null);
                      setSuggestions([]);
                    }}
                    className="w-full flex items-center px-3 py-3 text-sm text-left hover:bg-muted transition-colors text-muted-foreground min-h-[44px]"
                  >
                    + Add as new: &ldquo;{searchInput.trim()}&rdquo;
                  </button>
                </div>
              )}

              {isItemSelected && (
                <div className="flex items-center justify-between rounded-lg bg-muted px-3 py-2.5 text-sm">
                  <span className="text-muted-foreground">
                    Selected:{" "}
                    <span className="text-foreground font-medium">
                      {selectedProduct?.name ?? customText}
                    </span>
                  </span>
                  <button
                    type="button"
                    onClick={clearItemSelection}
                    className="ml-2 shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                    aria-label="Clear selection"
                  >
                    <X className="size-4" />
                  </button>
                </div>
              )}

              <div className="flex items-center justify-center gap-6">
                <button
                  type="button"
                  onClick={() => setItemQty((q) => Math.max(1, q - 1))}
                  className="flex items-center justify-center h-11 w-11 rounded-lg border border-input hover:bg-muted transition-colors"
                  aria-label="Decrease quantity"
                >
                  <Minus className="size-4" />
                </button>
                <span className="text-3xl font-semibold w-12 text-center tabular-nums select-none">
                  {itemQty}
                </span>
                <button
                  type="button"
                  onClick={() => setItemQty((q) => q + 1)}
                  className="flex items-center justify-center h-11 w-11 rounded-lg border border-input hover:bg-muted transition-colors"
                  aria-label="Increase quantity"
                >
                  <Plus className="size-4" />
                </button>
              </div>

              <Button
                className="w-full h-11"
                disabled={!isItemSelected}
                onClick={addItemToDraft}
              >
                Add to list
              </Button>
            </CardContent>
          </Card>

          {/* Draft items */}
          {draftItems.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  Items ({draftItems.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="divide-y">
                  {draftItems.map((item) => (
                    <li
                      key={item.key}
                      className="flex items-center gap-3 py-2.5 min-h-[44px]"
                    >
                      <span className="flex-1 text-sm">
                        {item.quantity}× {item.displayName}
                      </span>
                      <button
                        type="button"
                        onClick={() => removeDraftItem(item.key)}
                        className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                        aria-label={`Remove ${item.displayName}`}
                      >
                        <X className="size-4" />
                      </button>
                    </li>
                  ))}
                </ul>
                <Button
                  className="w-full mt-4"
                  disabled={saving}
                  onClick={handleSaveList}
                >
                  {saving ? "Saving…" : "Save list"}
                </Button>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Send dialog */}
      <Dialog
        open={activeSendList !== null}
        onOpenChange={(open) => {
          if (!open) closeSendDialog();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Send &ldquo;{activeSendList?.title ?? "Untitled list"}&rdquo;
            </DialogTitle>
          </DialogHeader>

          {sendResults !== null ? (
            <div className="space-y-3">
              <p className="text-sm font-medium">Results</p>
              <ul className="space-y-0 divide-y">
                {sendResults.map((r, i) => (
                  <li
                    key={i}
                    className="flex items-center justify-between gap-3 py-2.5"
                  >
                    <span className="text-sm truncate flex-1">{r.label}</span>
                    <div className="flex flex-col items-end gap-0.5 shrink-0">
                      {r.deliveredToInbox && (
                        <span className="text-xs text-muted-foreground">
                          Delivered to inbox
                        </span>
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
                <p className="text-sm text-muted-foreground">
                  Loading contacts…
                </p>
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
                              <span className="text-muted-foreground ml-2 text-xs">
                                {c.phone}
                              </span>
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
                                <span className="text-muted-foreground">
                                  WhatsApp only · not on app
                                </span>
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
                  <p className="text-xs text-muted-foreground">
                    WhatsApp only — unregistered number
                  </p>
                )}
              </div>

              <DialogFooter>
                <Button variant="outline" onClick={closeSendDialog}>
                  Cancel
                </Button>
                <Button
                  disabled={
                    sending ||
                    (contactChannels.size === 0 && !rawPhone.trim())
                  }
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
