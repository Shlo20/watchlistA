import { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import { Search, Flag, Plus, ChevronDown, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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

function defaultListTitle(): string {
  const d = new Date();
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `Restock — ${months[d.getMonth()]} ${d.getDate()}`;
}

export default function SearchSection() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Product[]>([]);
  const [lists, setLists] = useState<WatchList[]>([]);
  const [targetListId, setTargetListId] = useState<number | null>(() => {
    const saved = localStorage.getItem(LAST_LIST_KEY);
    return saved ? Number(saved) : null;
  });

  // Dropdown state
  const [pickerOpen, setPickerOpen] = useState(false);
  const [newListMode, setNewListMode] = useState(false);
  const [newListTitle, setNewListTitle] = useState("");
  const [savingNewList, setSavingNewList] = useState(false);

  // Add-item loading state
  const [addingProductIds, setAddingProductIds] = useState<Set<number>>(new Set());
  const [addingCustom, setAddingCustom] = useState(false);
  const [addingCatalog, setAddingCatalog] = useState(false);

  const selectorRef = useRef<HTMLDivElement>(null);
  const newListInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    listLists()
      .then(setLists)
      .catch(() => {});
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

  // Close picker on outside click — creates nothing
  useEffect(() => {
    if (!pickerOpen) return;
    function onMouseDown(e: MouseEvent) {
      if (selectorRef.current && !selectorRef.current.contains(e.target as Node)) {
        closeDropdown();
      }
    }
    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, [pickerOpen]);

  // Drop saved target if it no longer exists
  useEffect(() => {
    if (targetListId !== null && lists.length > 0 && !lists.find((l) => l.id === targetListId)) {
      setTargetListId(null);
      localStorage.removeItem(LAST_LIST_KEY);
    }
  }, [lists, targetListId]);

  // Focus the new-list input when it appears
  useEffect(() => {
    if (newListMode) {
      setTimeout(() => newListInputRef.current?.focus(), 0);
    }
  }, [newListMode]);

  const targetList = lists.find((l) => l.id === targetListId) ?? null;

  function closeDropdown() {
    setPickerOpen(false);
    setNewListMode(false);
    setNewListTitle("");
  }

  function selectList(list: WatchList) {
    setTargetListId(list.id);
    localStorage.setItem(LAST_LIST_KEY, String(list.id));
    closeDropdown();
  }

  function openNewListMode() {
    setNewListTitle(defaultListTitle());
    setNewListMode(true);
  }

  function cancelNewList() {
    // Go back to the list picker view; do NOT close the dropdown
    setNewListMode(false);
    setNewListTitle("");
  }

  async function confirmNewList() {
    if (savingNewList) return;
    setSavingNewList(true);
    try {
      const title = newListTitle.trim() || defaultListTitle();
      const created = await createList({ title, items: [] });
      setLists((prev) => [created, ...prev]);
      setTargetListId(created.id);
      localStorage.setItem(LAST_LIST_KEY, String(created.id));
      closeDropdown();
    } catch {
      toast.error("Couldn't create list. Try again.");
    } finally {
      setSavingNewList(false);
    }
  }

  // Returns the target list if one is selected, otherwise opens the picker and returns null.
  // Never creates anything silently.
  function resolveTarget(): WatchList | null {
    if (targetList) return targetList;
    setPickerOpen(true);
    return null;
  }

  async function handleAddProduct(product: Product) {
    if (addingProductIds.has(product.id)) return;
    const list = resolveTarget();
    if (!list) return;
    setAddingProductIds((prev) => new Set(prev).add(product.id));
    try {
      await addListItem(list.id, { product_id: product.id, quantity: 1 });
      if (list.has_been_sent) {
        toast.warning(`Added to "${list.title}" — this list was already sent`);
      } else {
        toast.success(`Added to "${list.title}"`);
      }
    } catch {
      toast.error("Couldn't add item. Try again.");
    } finally {
      setAddingProductIds((prev) => { const s = new Set(prev); s.delete(product.id); return s; });
    }
  }

  async function handleAddCustom() {
    const name = query.trim();
    if (!name || addingCustom) return;
    const list = resolveTarget();
    if (!list) return;
    setAddingCustom(true);
    try {
      await addListItem(list.id, { custom_product_name: name, quantity: 1 });
      if (list.has_been_sent) {
        toast.warning(`Added "${name}" to "${list.title}" — this list was already sent`);
      } else {
        toast.success(`Added "${name}" to "${list.title}"`);
      }
    } catch {
      toast.error("Couldn't add item. Try again.");
    } finally {
      setAddingCustom(false);
    }
  }

  async function handleAddToCatalog() {
    const name = query.trim();
    if (!name || addingCatalog) return;
    const list = resolveTarget();
    if (!list) return;
    setAddingCatalog(true);
    try {
      const newProduct = await createProduct({ name });
      await addListItem(list.id, { product_id: newProduct.id, quantity: 1 });
      if (list.has_been_sent) {
        toast.warning(`Added "${name}" to catalog and "${list.title}" — list was already sent`);
      } else {
        toast.success(`Added "${name}" to catalog and "${list.title}"`);
      }
      // Refresh results so the new product appears as a real catalog item with flag toggle
      const fresh = await searchProducts(name);
      setResults(fresh.slice(0, 8));
    } catch {
      toast.error("Couldn't add to catalog. Try again.");
    } finally {
      setAddingCatalog(false);
    }
  }

  async function toggleFlag(product: Product) {
    if (product.is_low) {
      await unflagLow(product.id).catch(() => toast.error("Couldn't unflag."));
      setResults((prev) => prev.map((p) => p.id === product.id ? { ...p, is_low: false } : p));
    } else {
      const updated = await flagLow(product.id).catch(() => null);
      if (updated) {
        setResults((prev) => prev.map((p) => p.id === product.id ? { ...p, is_low: true } : p));
        toast.success(`${product.name} flagged as running low`);
      }
    }
  }

  const hasQuery = query.trim().length > 0;

  return (
    <div className="px-4 py-6 mx-auto w-full max-w-[32rem] space-y-4">
      <h2 className="text-xl font-semibold">Search products</h2>

      {/* ── Target list selector ── */}
      <div ref={selectorRef} className="relative">
        <button
          type="button"
          onClick={() => (pickerOpen ? closeDropdown() : setPickerOpen(true))}
          className={cn(
            "w-full flex items-center gap-3 px-4 py-3 rounded-xl border text-sm transition-colors text-left",
            pickerOpen
              ? "border-primary bg-primary/5"
              : "border-border bg-card hover:border-muted-foreground/60"
          )}
        >
          <div className="flex-1 min-w-0 flex items-center gap-2 flex-wrap">
            {targetList ? (
              <>
                <span className="text-xs text-muted-foreground shrink-0">Adding to</span>
                <span className="font-medium truncate">{targetList.title}</span>
                {targetList.has_been_sent && (
                  <Badge variant="secondary" className="text-xs shrink-0">Sent</Badge>
                )}
              </>
            ) : (
              <span className="text-muted-foreground">Select a list to add items to…</span>
            )}
          </div>
          <ChevronDown
            className={cn(
              "size-4 text-muted-foreground shrink-0 transition-transform duration-150",
              pickerOpen && "rotate-180"
            )}
          />
        </button>

        {pickerOpen && (
          <div className="absolute top-full mt-1.5 left-0 right-0 z-30 rounded-xl border bg-popover shadow-lg overflow-hidden">
            {newListMode ? (
              /* ── Inline new-list naming form ── */
              <div className="p-3 space-y-2">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  Name your list
                </p>
                <Input
                  ref={newListInputRef}
                  value={newListTitle}
                  onChange={(e) => setNewListTitle(e.target.value)}
                  placeholder={defaultListTitle()}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") { e.preventDefault(); confirmNewList(); }
                    if (e.key === "Escape") { e.preventDefault(); cancelNewList(); }
                  }}
                  className="h-9 text-sm"
                />
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    className="flex-1 h-8"
                    disabled={savingNewList}
                    onClick={confirmNewList}
                  >
                    {savingNewList ? "Creating…" : "Confirm"}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-8 px-3"
                    disabled={savingNewList}
                    onClick={cancelNewList}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              /* ── List picker ── */
              <>
                {lists.length > 0 && (
                  <ul className="divide-y max-h-52 overflow-y-auto">
                    {lists.map((l) => {
                      const active = l.id === targetListId;
                      return (
                        <li key={l.id}>
                          <button
                            type="button"
                            onClick={() => selectList(l)}
                            className={cn(
                              "w-full flex items-center gap-3 px-4 py-3 text-sm text-left hover:bg-muted transition-colors",
                              active && "bg-primary/8 text-primary font-medium"
                            )}
                          >
                            <Check className={cn("size-3.5 shrink-0", active ? "opacity-100" : "opacity-0")} />
                            <span className="flex-1 truncate">{l.title}</span>
                            {l.has_been_sent && (
                              <Badge variant="secondary" className="text-xs shrink-0">Sent</Badge>
                            )}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                )}
                <button
                  type="button"
                  onClick={openNewListMode}
                  className={cn(
                    "w-full flex items-center gap-2 px-4 py-3 text-sm text-left text-primary hover:bg-muted transition-colors",
                    lists.length > 0 && "border-t"
                  )}
                >
                  <Plus className="size-3.5 shrink-0" />
                  New list
                </button>
              </>
            )}
          </div>
        )}
      </div>

      {/* ── Search input ── */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground pointer-events-none" />
        <Input
          className="pl-9"
          placeholder="Search by name, SKU, category…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
        />
      </div>

      {/* ── Results ── */}
      {hasQuery && (
        <div className="rounded-xl border divide-y overflow-hidden">
          {results.map((product) => (
            <div key={product.id} className="flex items-center gap-3 px-4 py-3.5 min-h-[56px]">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{product.name}</p>
                <Badge variant="secondary" className="capitalize text-xs mt-0.5">
                  {product.category.replace("_", " ")}
                </Badge>
              </div>

              <button
                type="button"
                onClick={() => toggleFlag(product)}
                className={cn(
                  "shrink-0 p-1.5 rounded transition-colors",
                  product.is_low
                    ? "text-amber-400 hover:text-amber-300"
                    : "text-muted-foreground hover:text-amber-400"
                )}
                aria-label={product.is_low ? "Unmark running low" : "Mark running low"}
                title={product.is_low ? "Running low — click to clear" : "Mark running low"}
              >
                <Flag className="size-3.5" />
              </button>

              <button
                type="button"
                disabled={addingProductIds.has(product.id)}
                onClick={() => handleAddProduct(product)}
                className="shrink-0 flex items-center justify-center size-8 rounded-lg border border-input text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-40 transition-colors"
                aria-label={`Add ${product.name}`}
              >
                <Plus className="size-4" />
              </button>
            </div>
          ))}

          {/* Custom item row — two actions */}
          <div className="px-4 py-3 bg-muted/25 space-y-2">
            <p className="text-sm text-muted-foreground">
              <span className="font-medium text-foreground">&ldquo;{query.trim()}&rdquo;</span>
              {results.length === 0 ? " — not in catalog" : ""}
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={addingCustom || addingCatalog}
                onClick={handleAddCustom}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-input text-xs text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-40 transition-colors"
              >
                <Plus className="size-3 shrink-0" />
                {addingCustom ? "Adding…" : "Add to list"}
                <span className="opacity-50">· one-off</span>
              </button>
              <button
                type="button"
                disabled={addingCatalog || addingCustom}
                onClick={handleAddToCatalog}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-primary/40 text-xs text-primary hover:bg-primary/10 disabled:opacity-40 transition-colors"
              >
                <Plus className="size-3 shrink-0" />
                {addingCatalog ? "Saving…" : "Add to catalog"}
                <span className="opacity-60">· save to stock</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!hasQuery && (
        <div className="flex flex-col items-center justify-center py-12 gap-4 text-center">
          <div className="flex items-center justify-center size-16 rounded-2xl bg-muted">
            <Search className="size-7 text-primary/60" />
          </div>
          <p className="text-sm text-muted-foreground max-w-[220px]">
            Search for products to add to a list or flag as running low.
          </p>
        </div>
      )}
    </div>
  );
}
