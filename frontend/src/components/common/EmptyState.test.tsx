import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { PackageSearch } from "lucide-react";
import { EmptyState } from "@/components/common/EmptyState";

describe("EmptyState", () => {
  it("renders the title and description", () => {
    render(
      <EmptyState
        icon={PackageSearch}
        title="No trusted matches found"
        description="Try a clearer photo."
      />
    );

    expect(screen.getByText("No trusted matches found")).toBeInTheDocument();
    expect(screen.getByText("Try a clearer photo.")).toBeInTheDocument();
  });

  it("renders without a description", () => {
    render(<EmptyState icon={PackageSearch} title="Nothing here" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });

  it("renders optional action content", () => {
    render(
      <EmptyState
        icon={PackageSearch}
        title="Nothing here"
        action={<button>Retry</button>}
      />
    );
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
