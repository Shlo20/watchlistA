import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ListChecks, Users, Inbox, LogOut, Settings } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import ContactsSection from "@/pages/ContactsSection";
import ListsSection from "@/pages/ListsSection";
import InboxSection from "@/pages/InboxSection";
import SettingsSection from "@/pages/SettingsSection";

type Section = "lists" | "contacts" | "inbox" | "settings";

const NAV_ITEMS: {
  id: Section;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}[] = [
  { id: "lists", label: "Lists", icon: ListChecks },
  { id: "contacts", label: "Contacts", icon: Users },
  { id: "inbox", label: "Inbox", icon: Inbox },
  { id: "settings", label: "Settings", icon: Settings },
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
      {/* Header — glass card surface, blurs content behind on scroll */}
      <header className="flex items-center justify-between px-4 sm:px-6 py-3 border-b border-border/60 bg-card/95 backdrop-blur-sm">
        <div className="flex flex-col leading-tight">
          <span className="text-base font-bold tracking-tight text-foreground">
            Watch<span className="text-primary">list</span>
          </span>
          {user?.business_name && (
            <span className="text-xs text-muted-foreground">{user.business_name}</span>
          )}
        </div>
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
        <nav className="hidden sm:flex sm:flex-col w-52 border-r border-border/60 p-3 space-y-0.5 shrink-0 bg-card/30">
          {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActive(id)}
              className={[
                "w-full flex items-center gap-2.5 text-left px-3 py-2.5 rounded-lg text-sm transition-all duration-150",
                active === id
                  ? "bg-primary/12 text-primary font-semibold shadow-sm"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/60",
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
          {active === "settings" && <SettingsSection />}
        </main>
      </div>

      {/* Bottom tab bar — mobile only */}
      <nav
        className="fixed bottom-0 left-0 right-0 sm:hidden bg-card/95 backdrop-blur-sm border-t border-border/60 flex items-stretch justify-around z-20"
        style={{ paddingBottom: "max(0.5rem, env(safe-area-inset-bottom))" }}
      >
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActive(id)}
            className={[
              "flex flex-col items-center justify-center flex-1 pt-2 pb-1 gap-1 text-xs transition-colors relative",
              active === id ? "text-primary" : "text-muted-foreground",
            ].join(" ")}
          >
            {active === id && (
              <span className="absolute top-0 left-1/2 -translate-x-1/2 w-7 h-[3px] bg-primary rounded-full" />
            )}
            <Icon className="size-5 mt-0.5" />
            <span className="font-medium">{label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
