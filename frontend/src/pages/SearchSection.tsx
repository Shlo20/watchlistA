import { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import { Search, Flag, Plus, ChevronDown, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  searchProducts,
  createProduct,
  listLists,
  addListItem,
  createList,
  flagLow,
  unflagLow,
  type Product,
  type WatchList,
} from "@/lib/api";

const LAST_LIST_KEY = "watchlist_last_list_id";

function autoListTitle(): string {
  const d = new Date();
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return `Restock — ${months[d.getMonth()]} ${d.getDate()}`;
}

export default function SearchSection() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Product[]>([]);
  const [lists, setLists] = useState<WatchList[]>([]);
  const [defaultListId, setDefaultListId] = useState<number | null>(() => {
    const saved = localStorage.getItem(LAST_LIST_KEY);
    return saved ? Number(saved) : null;
  });

  // Per-row list picker
  const [openPickerProductId, setOpenPickerProductId] = useState<number | null>(null);
  const [pickerBusy, setPickerBusy] = useState(false);
  const pickerRef = useRef<HTMLDivElement>(null);

  // Loading states
  const [addingProductIds, setAddingProductIds] = useState<Set<number>>(new Set());
  const [newItemBusy, setNewItemBusy] = useState<"idle" | "low" | "list" | "only">("idle");

  // Synchronous in-flight guards — state updates are async, so a fast double-tap
  // can slip past a state-based check before React re-renders. Refs close that gap.
  const addingRef = useRef<Set<number>>(new Set());
  const pickerBusyRef = useRef(false);
  const flagBusyRef = useRef<Set<number>>(new Set());
  const newItemBusyRef = useRef(false);

  useEffect(() => {
    listLists().then(setLists).catch(() => {});
  }, []);

  // Debounced search
  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) { setResults([]); return; }
    const timer = setTimeout(() => {
      searchProducts(trimmed)
        .then((data) => setResults(data.slice(0, 8)))
        .catch(() => {});
    }, 250);
    return () => clearTimeout(timer);
  }, [query]);

  // Close per-row picker on outside tap/click. Dismissing the picker is always
  // a pure UI action — it never creates or modifies anything.
  useEffect(() => {
    if (!openPickerProductId) return;
    function onPointerDown(e: Event) {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        setOpenPickerProductId(null);
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("touchstart", onPointerDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("touchstart", onPointerDown);
    };
  }, [openPickerProductId]);

  // Keep defaultListId valid when lists change
  useEffect(() => {
    if (defaultListId === null || lists.length === 0) return;
    if (!lists.find((l) => l.id === defaultListId)) {
      const fallback = lists[0]?.id ?? null;
      setDefaultListId(fallback);
      if (fallback) localStorage.setItem(LAST_LIST_KEY, String(fallback));
      else localStorage.removeItem(LAST_LIST_KEY);
    }
  }, [lists, defaultListId]);

  const defaultList = lists.find((l) => l.id === defaultListId) ?? lists[0] ?? null;

  function rememberList(list: WatchList) {
    setDefaultListId(list.id);
    localStorage.setItem(LAST_LIST_KEY, String(list.id));
  }

  async function refreshSearch() {
    const trimmed = query.trim();
    if (!trimmed) return;
    const fresh = await searchProducts(trimmed).catch(() => null);
    if (fresh) setResults(fresh.slice(0, 8));
  }

  // ── Shared add-to-list helper ────────────────────────────────────────────

  async function addProductToList(product: Product, list: WatchList) {
    if (addingRef.current.has(product.id)) return;
    addingRef.current.add(product.id);
    setAddingProductIds((prev) => new Set(prev).add(product.id));
    try {
      const { alreadyInList } = await addListItem(list.id, {
        product_id: product.id,
        quantity: 1,
      });
      rememberList(list);
      if (alreadyInList) {
        toast.info(`"${product.name}" is already in "${list.title}"`);
      } else if (list.has_been_sent) {
        toast.warning(`Added to "${list.title}" — list was already sent`);
      } else {
        toast.success(`Added to "${list.title}"`);
      }
    } catch {
      toast.error("Couldn't add item. Try again.");
    } finally {
      addingRef.current.delete(product.id);
      setAddingProductIds((prev) => { const s = new Set(prev); s.delete(product.id); return s; });
    }
  }

  // ── Catalog row: main Add ────────────────────────────────────────────────

  async function handleAddToDefault(product: Product) {
    if (!defaultList) {
      // No lists yet — never create one implicitly. Open the picker so the
      // user explicitly confirms "New list" (or picks nothing and dismisses).
      setOpenPickerProductId(product.id);
      return;
    }
    await addProductToList(product, defaultList);
  }

  // ── Catalog row: picker selection ────────────────────────────────────────

  async function handlePickerSelectList(product: Product, list: WatchList) {
    setOpenPickerProductId(null);
    await addProductToList(product, list);
  }

  async function handlePickerNewList(product: Product) {
    // Explicit "New list" tap — the only place Search creates a list.
    if (pickerBusyRef.current || addingRef.current.has(product.id)) return;
    pickerBusyRef.current = true;
    setOpenPickerProductId(null);
    setPickerBusy(true);
    addingRef.current.add(product.id);
    setAddingProductIds((prev) => new Set(prev).add(product.id));
    try {
      const created = await createList({ title: autoListTitle(), items: [] });
      setLists((prev) => [created, ...prev]);
      rememberList(created);
      await addListItem(created.id, { product_id: product.id, quantity: 1 });
      toast.success(`Added to "${created.title}"`);
    } catch {
      toast.error("Couldn't create list. Try again.");
    } finally {
      pickerBusyRef.current = false;
      setPickerBusy(false);
      addingRef.current.delete(product.id);
      setAddingProductIds((prev) => { const s = new Set(prev); s.delete(product.id); return s; });
    }
  }

  // ── Flag toggle ──────────────────────────────────────────────────────────

  async function toggleFlag(product: Product) {
    if (flagBusyRef.current.has(product.id)) return;
    flagBusyRef.current.add(product.id);
    try {
      if (product.is_low) {
        // Only update the UI once the server confirms — otherwise the flag
        // would silently vanish locally while still set on the server.
        try {
          await unflagLow(product.id);
          setResults((prev) => prev.map((p) => p.id === product.id ? { ...p, is_low: false } : p));
        } catch {
          toast.error("Couldn't unflag. Try again.");
        }
      } else {
        try {
          await flagLow(product.id);
          setResults((prev) => prev.map((p) => p.id === product.id ? { ...p, is_low: true } : p));
          toast.success(`${product.name} flagged as running low`);
        } catch {
          toast.error("Couldn't flag. Try again.");
        }
      }
    } finally {
      flagBusyRef.current.delete(product.id);
    }
  }

  // ── "Not in catalog" card actions ────────────────────────────────────────

  async function handleCatalogLow() {
    const name = query.trim();
    if (!name || newItemBusy !== "idle" || newItemBusyRef.current) return;
    newItemBusyRef.current = true;
    setNewItemBusy("low");
    try {
      const product = await createProduct({ name });
      await flagLow(product.id);
      toast.success(`Added "${name}" to catalog, marked low`);
      await refreshSearch();
    } catch {
      toast.error("Couldn't save. Try again.");
    } finally {
      newItemBusyRef.current = false;
      setNewItemBusy("idle");
    }
  }

  async function handleCatalogAndList() {
    const name = query.trim();
    if (!name || newItemBusy !== "idle" || newItemBusyRef.current) return;
    newItemBusyRef.current = true;
    setNewItemBusy("list");
    try {
      // The button's description states exactly which list will be used — or
      // that a new one will be created — so this is an explicit, informed action.
      let list = defaultList;
      if (!list) {
        const created = await createList({ title: autoListTitle(), items: [] });
        setLists((prev) => [created, ...prev]);
        rememberList(created);
        list = created;
      }
      const product = await createProduct({ name });
      const { alreadyInList } = await addListItem(list.id, { product_id: product.id, quantity: 1 });
      if (alreadyInList) {
        toast.info(`"${product.name}" is already in "${list.title}"`);
      } else if (list.has_been_sent) {
        toast.warning(`Added "${name}" to catalog and "${list.title}" — list was already sent`);
      } else {
        toast.success(`Added "${name}" to catalog and "${list.title}"`);
      }
      await refreshSearch();
    } catch {
      toast.error("Couldn't save. Try again.");
    } finally {
      newItemBusyRef.current = false;
      setNewItemBusy("idle");
    }
  }

  async function handleCatalogOnly() {
    const name = query.trim();
    if (!name || newItemBusy !== "idle" || newItemBusyRef.current) return;
    newItemBusyRef.current = true;
    setNewItemBusy("only");
    try {
      await createProduct({ name });
      toast.success(`Added "${name}" to catalog`);
      await refreshSearch();
    } catch {
      toast.error("Couldn't save. Try again.");
    } finally {
      newItemBusyRef.current = false;
      setNewItemBusy("idle");
    }
  }

  const hasQuery = query.trim().length > 0;
  const exactMatchExists =
    hasQuery &&
    results.some(
      (p) => p.name.trim().toLowerCase() === query.trim().toLowerCase()
    );

  return (
    <div className="px-4 py-6 mx-auto w-full max-w-[32rem] space-y-5">
      <h2 className="text-xl font-semibold">Search</h2>

      {/* Search box — only thing above results */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground pointer-events-none" />
        <Input
          className="pl-9"
          placeholder="Search products…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
        />
      </div>

      {/* Empty state */}
      {!hasQuery && (
        <div className="flex flex-col items-center justify-center py-14 gap-4 text-center">
          <div className="flex items-center justify-center size-16 rounded-2xl bg-muted">
            <Search className="size-7 text-primary/60" />
          </div>
          <p className="text-sm text-muted-foreground max-w-[200px]">
            Search the catalog to add items to a list or flag them as running low.
          </p>
        </div>
      )}

      {hasQuery && (
        <div className="space-y-5">

          {/* ── Section: In your catalog ── */}
          {results.length > 0 && (
            <section className="space-y-1.5">
              <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider px-0.5">
                In your catalog
              </p>
              <div className="rounded-xl border divide-y overflow-visible">
                {results.map((product) => (
                  <div key={product.id} className="relative flex items-center gap-2 px-4 py-3.5 min-h-[56px]">
                    {/* Name + low badge */}
                    <div className="flex-1 min-w-0 flex items-center gap-1.5 flex-wrap">
                      <span className="text-sm font-medium">{product.name}</span>
                      {product.is_low && (
                        <Badge
                          variant="outline"
                          className="text-[10px] px-1.5 py-px border-amber-500/40 text-amber-400 shrink-0"
                        >
                          low
                        </Badge>
                      )}
                    </div>

                    {/* Flag toggle — quiet when not low */}
                    <button
                      type="button"
                      onClick={() => toggleFlag(product)}
                      className={cn(
                        "shrink-0 p-1.5 rounded transition-colors",
                        product.is_low
                          ? "text-amber-400 hover:text-amber-300"
                          : "text-muted-foreground/35 hover:text-amber-400"
                      )}
                      aria-label={product.is_low ? "Unmark running low" : "Mark running low"}
                    >
                      <Flag className="size-3.5" />
                    </button>

                    {/* Add split button */}
                    <div className="flex items-stretch shrink-0">
                      <button
                        type="button"
                        disabled={addingProductIds.has(product.id) || pickerBusy}
                        onClick={() => handleAddToDefault(product)}
                        className="flex items-center gap-1 pl-2.5 pr-2 h-8 rounded-l-lg border border-input text-xs text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-40 transition-colors"
                      >
                        <Plus className="size-3.5 shrink-0" />
                        Add
                      </button>
                      <button
                        type="button"
                        disabled={addingProductIds.has(product.id) || pickerBusy}
                        onClick={() =>
                          setOpenPickerProductId(
                            openPickerProductId === product.id ? null : product.id
                          )
                        }
                        className="flex items-center justify-center w-6 h-8 rounded-r-lg border border-l-0 border-input text-muted-foreground/50 hover:text-foreground hover:bg-muted disabled:opacity-40 transition-colors"
                        aria-label="Choose list"
                      >
                        <ChevronDown
                          className={cn(
                            "size-3 transition-transform duration-150",
                            openPickerProductId === product.id && "rotate-180"
                          )}
                        />
                      </button>
                    </div>

                    {/* Per-row list picker */}
                    {openPickerProductId === product.id && (
                      <div
                        ref={pickerRef}
                        className="absolute right-0 top-full mt-1.5 z-30 w-56 rounded-xl border bg-popover shadow-lg overflow-hidden"
                      >
                        {lists.length > 0 && (
                          <ul className="divide-y max-h-48 overflow-y-auto">
                            {lists.map((l) => {
                              const isDefault = l.id === defaultList?.id;
                              return (
                                <li key={l.id}>
                                  <button
                                    type="button"
                                    onClick={() => handlePickerSelectList(product, l)}
                                    className="w-full flex items-center gap-2.5 px-3 py-2.5 text-sm text-left hover:bg-muted transition-colors"
                                  >
                                    <Check
                                      className={cn(
                                        "size-3.5 shrink-0 text-primary transition-opacity",
                                        isDefault ? "opacity-100" : "opacity-0"
                                      )}
                                    />
                                    <span className={cn("flex-1 truncate", isDefault && "font-medium")}>
                                      {l.title}
                                    </span>
                                    {l.has_been_sent && (
                                      <Badge variant="secondary" className="text-xs shrink-0">
                                        Sent
                                      </Badge>
                                    )}
                                  </button>
                                </li>
                              );
                            })}
                          </ul>
                        )}
                        <button
                          type="button"
                          disabled={pickerBusy}
                          onClick={() => handlePickerNewList(product)}
                          className={cn(
                            "w-full flex items-center gap-2.5 px-3 py-2.5 text-sm text-left text-primary hover:bg-muted transition-colors disabled:opacity-50",
                            lists.length > 0 && "border-t"
                          )}
                        >
                          <Plus className="size-3.5 shrink-0" />
                          {pickerBusy ? "Creating…" : "New list"}
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* ── Section: Not in catalog yet / exact-match note ── */}
          {exactMatchExists ? (
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground px-0.5 pt-1">
              <Check className="size-3.5 text-primary shrink-0" />
              Already in your catalog — use the item above to flag it or add it to a list.
            </p>
          ) : (
            <section className="space-y-1.5">
              <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider px-0.5">
                Not in catalog yet
              </p>
              <Card>
                <CardContent className="pt-4 pb-3 space-y-3">
                  <p className="text-sm font-medium truncate">
                    &ldquo;{query.trim()}&rdquo;
                  </p>
                  <div className="space-y-2">
                    {/* Action 1: Catalog + mark low — amber/warning, most prominent */}
                    <button
                      type="button"
                      disabled={newItemBusy !== "idle"}
                      onClick={handleCatalogLow}
                      className="w-full flex items-center gap-3 px-3.5 py-3 rounded-xl bg-amber-500/10 border border-amber-500/25 text-left hover:bg-amber-500/15 disabled:opacity-50 transition-colors"
                    >
                      <Flag className="size-4 text-amber-400 shrink-0" />
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-amber-300 leading-tight">
                          {newItemBusy === "low" ? "Saving…" : "Catalog + mark low"}
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Add to stock catalog and flag running low
                        </p>
                      </div>
                    </button>

                    {/* Action 2: Catalog + add to list — primary */}
                    <button
                      type="button"
                      disabled={newItemBusy !== "idle"}
                      onClick={handleCatalogAndList}
                      className="w-full flex items-center gap-3 px-3.5 py-3 rounded-xl bg-primary/8 border border-primary/25 text-left hover:bg-primary/12 disabled:opacity-50 transition-colors"
                    >
                      <Plus className="size-4 text-primary shrink-0" />
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-primary leading-tight">
                          {newItemBusy === "list" ? "Saving…" : "Catalog + add to list"}
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {defaultList ? (
                            <>
                              Save to catalog and add to{" "}
                              <span className="text-foreground/70">&ldquo;{defaultList.title}&rdquo;</span>
                            </>
                          ) : (
                            <>
                              Save to catalog and create list{" "}
                              <span className="text-foreground/70">&ldquo;{autoListTitle()}&rdquo;</span>
                            </>
                          )}
                        </p>
                      </div>
                    </button>

                    {/* Action 3: Catalog only — muted */}
                    <button
                      type="button"
                      disabled={newItemBusy !== "idle"}
                      onClick={handleCatalogOnly}
                      className="w-full flex items-center gap-3 px-3.5 py-3 rounded-xl border border-border text-left hover:bg-muted disabled:opacity-50 transition-colors"
                    >
                      <Plus className="size-4 text-muted-foreground shrink-0" />
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-foreground leading-tight">
                          {newItemBusy === "only" ? "Saving…" : "Add to catalog"}
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Save to stock catalog only — no list, no flag
                        </p>
                      </div>
                    </button>
                  </div>
                </CardContent>
              </Card>
            </section>
          )}

        </div>
      )}
    </div>
  );
}
