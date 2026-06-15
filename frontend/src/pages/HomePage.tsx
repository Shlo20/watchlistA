import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ListChecks, Users, Inbox, LogOut } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import ContactsSection from "@/pages/ContactsSection";
import ListsSection from "@/pages/ListsSection";
import InboxSection from "@/pages/InboxSection";

type Section = "lists" | "contacts" | "inbox";

const NAV_ITEMS: {
  id: Section;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}[] = [
  { id: "lists", label: "Lists", icon: ListChecks },
  { id: "contacts", label: "Contacts", icon: Users },
  { id: "inbox", label: "Inbox", icon: Inbox },
];

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
      <header className="flex items-center justify-between px-4 sm:px-6 py-3 border-b">
        <span className="text-lg font-semibold">Watchlist</span>
        <div className="flex items-center gap-3">
          <span className="hidden sm:block text-sm text-muted-foreground">{user?.name}</span>
          <button
            onClick={handleSignOut}
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors min-h-[44px] px-2"
            aria-label="Sign out"
          >
            <LogOut className="size-4" />
            <span className="hidden sm:inline">Sign out</span>
          </button>
        </div>
      </header>

      <div className="flex h-[calc(100vh-57px)]">
        {/* Sidebar — desktop only */}
        <nav className="hidden sm:flex sm:flex-col w-48 border-r p-4 space-y-1 shrink-0">
          {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActive(id)}
              className={[
                "w-full flex items-center gap-2.5 text-left px-3 py-2.5 rounded-md text-sm transition-colors",
                active === id
                  ? "bg-accent text-accent-foreground font-medium"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent/50",
              ].join(" ")}
            >
              <Icon className="size-4 shrink-0" />
              {label}
            </button>
          ))}
        </nav>

        {/* Main content */}
        <main className="flex-1 overflow-auto pb-[72px] sm:pb-0">
          {active === "lists" && <ListsSection />}
          {active === "contacts" && <ContactsSection />}
          {active === "inbox" && <InboxSection />}
        </main>
      </div>

      {/* Bottom tab bar — mobile only */}
      <nav
        className="fixed bottom-0 left-0 right-0 sm:hidden bg-card border-t flex items-stretch justify-around z-10"
        style={{ paddingBottom: "max(0.5rem, env(safe-area-inset-bottom))" }}
      >
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActive(id)}
            className={[
              "flex flex-col items-center justify-center flex-1 pt-2 pb-1 gap-1 text-xs transition-colors",
              active === id ? "text-primary" : "text-muted-foreground",
            ].join(" ")}
          >
            <Icon className="size-5" />
            <span className="font-medium">{label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
