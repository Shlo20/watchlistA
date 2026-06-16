import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Package, Trash2, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getAllProducts, deleteProduct, restoreProduct, type Product } from "@/lib/api";

export default function CatalogSection() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    getAllProducts()
      .then(setProducts)
      .catch(() => toast.error("Couldn't load catalog."))
      .finally(() => setLoading(false));
  }, []);

  const visible = filter.trim()
    ? products.filter((p) => p.name.toLowerCase().includes(filter.trim().toLowerCase()))
    : products;

  async function handleDelete(product: Product) {
    setProducts((prev) => prev.filter((p) => p.id !== product.id));

    try {
      await deleteProduct(product.id);
    } catch {
      setProducts((prev) =>
        [...prev, product].sort((a, b) => a.name.localeCompare(b.name))
      );
      toast.error(`Couldn't remove "${product.name}".`);
      return;
    }

    toast(`Removed "${product.name}"`, {
      action: {
        label: "Undo",
        onClick: async () => {
          try {
            const restored = await restoreProduct(product.id);
            setProducts((prev) =>
              [...prev, restored].sort((a, b) => a.name.localeCompare(b.name))
            );
          } catch {
            toast.error(`Couldn't restore "${product.name}".`);
          }
        },
      },
    });
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (products.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-5 text-center px-8">
        <div className="flex items-center justify-center size-20 rounded-2xl bg-muted">
          <Package className="size-9 text-primary/50" />
        </div>
        <div className="space-y-1.5">
          <p className="text-lg font-semibold">Catalog is empty</p>
          <p className="text-sm text-muted-foreground max-w-[240px]">
            Search for a product and add it to your catalog to see it here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="px-4 py-6 mx-auto w-full max-w-[32rem] space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <Package className="size-5 text-primary/70" />
          Catalog
        </h2>
        <span className="text-xs text-muted-foreground">
          {products.length} item{products.length !== 1 ? "s" : ""}
        </span>
      </div>

      {products.length > 5 && (
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground pointer-events-none" />
          <Input
            className="pl-9"
            placeholder="Filter catalog…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
      )}

      {visible.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-8">
          No matches for &ldquo;{filter}&rdquo;
        </p>
      ) : (
        <Card>
          <CardContent className="pt-4 pb-2">
            <ul className="divide-y">
              {visible.map((product) => (
                <li key={product.id} className="flex items-center gap-3 py-3 min-h-[52px]">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <p className="text-sm font-medium truncate">{product.name}</p>
                      {product.is_low && (
                        <Badge
                          variant="outline"
                          className="text-[10px] px-1.5 py-px border-amber-500/40 text-amber-400 shrink-0"
                        >
                          low
                        </Badge>
                      )}
                    </div>
                    {product.category !== "other" && (
                      <Badge variant="secondary" className="capitalize text-xs mt-0.5">
                        {product.category.replace("_", " ")}
                      </Badge>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDelete(product)}
                    className="shrink-0 text-muted-foreground/35 hover:text-destructive transition-colors p-1.5 rounded"
                    aria-label={`Remove ${product.name} from catalog`}
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
