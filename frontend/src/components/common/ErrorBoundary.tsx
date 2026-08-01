import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertOctagon, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {

    console.error("Unhandled UI error:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-6 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-destructive/10 text-destructive">
            <AlertOctagon className="h-7 w-7" />
          </div>
          <h1 className="text-xl font-semibold text-foreground">Something broke on our end</h1>
          <p className="max-w-md text-sm text-muted-foreground">
            An unexpected error occurred while rendering this page. Reloading usually fixes it.
          </p>
          <Button onClick={() => window.location.reload()}>
            <RefreshCw className="h-4 w-4" />
            Reload the page
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}
