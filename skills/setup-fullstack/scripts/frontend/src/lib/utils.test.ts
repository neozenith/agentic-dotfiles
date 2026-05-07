import { describe, expect, it } from "vitest";
import { cn } from "./utils";

describe("cn", () => {
  it("joins truthy class names", () => {
    expect(cn("a", "b")).toBe("a b");
  });

  it("filters falsy values", () => {
    expect(cn("a", false, undefined, null, "b")).toBe("a b");
  });

  it("dedupes conflicting Tailwind utilities (last wins)", () => {
    // tailwind-merge collapses conflicting utilities; this test pins that
    // behaviour so a future swap of cn()'s implementation is caught.
    expect(cn("p-2", "p-4")).toBe("p-4");
  });
});
