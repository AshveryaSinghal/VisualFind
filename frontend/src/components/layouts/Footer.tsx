import { NavLink } from "react-router-dom";
import { ScanSearch } from "lucide-react";

export function Footer() {
  return (
    <footer className="border-t border-border/60">
      <div className="container flex flex-col items-center gap-4 py-10 text-sm text-muted-foreground sm:flex-row sm:justify-between">
        <div className="flex items-center gap-2">
          <ScanSearch className="h-4 w-4" />
          <span>VisualFind &copy; {new Date().getFullYear()}</span>
        </div>
        <div className="flex items-center gap-6">
          <NavLink to="/about" className="transition-colors hover:text-foreground">
            About
          </NavLink>
          <a
            href="https://github.com"
            target="_blank"
            rel="noreferrer"
            className="transition-colors hover:text-foreground"
          >
            GitHub
          </a>
          <span>Built with FastAPI &amp; React</span>
        </div>
      </div>
    </footer>
  );
}
