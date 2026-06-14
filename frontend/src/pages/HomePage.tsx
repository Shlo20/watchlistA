import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import ContactsSection from "@/pages/ContactsSection";
import ListsSection from "@/pages/ListsSection";

type Section = "lists" | "contacts" | "inbox";

export default function HomePage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [active, setActive] = useState<Section>("lists");

  function handleSignOut() {
    logout();
    navigate("/login");
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="flex items-center justify-between px-6 py-4 border-b">
        <span className="text-lg font-semibold">Watchlist</span>
        <div className="flex items-center gap-4">
          <span className="text-sm text-muted-foreground">{user?.name}</span>
          <button
            onClick={handleSignOut}
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Sign out
          </button>
        </div>
      </header>

      <div className="flex h-[calc(100vh-65px)]">
        <nav className="w-48 border-r p-4 space-y-1 shrink-0">
          {(["lists", "contacts", "inbox"] as Section[]).map((s) => (
            <button
              key={s}
              onClick={() => setActive(s)}
              className={[
                "w-full text-left px-3 py-2 rounded-md text-sm capitalize transition-colors",
                active === s
                  ? "bg-accent text-accent-foreground font-medium"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent/50",
              ].join(" ")}
            >
              {s}
            </button>
          ))}
        </nav>

        <main className="flex-1 overflow-auto">
          {active === "lists" && <ListsSection />}
          {active === "contacts" && <ContactsSection />}
          {active === "inbox" && (
            <div className="flex items-center justify-center h-full">
              <p className="text-muted-foreground">Inbox — coming soon</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
