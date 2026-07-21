import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import HomePage from "./page";

describe("HomePage", () => {
  it("states the product boundary and supported languages", () => {
    render(<HomePage />);

    expect(screen.getByRole("heading", { name: /accountable clinical follow-up/i })).toBeInTheDocument();
    expect(screen.getByText(/English · Shona · Ndebele/i)).toBeInTheDocument();
    expect(screen.getByText(/does not diagnose conditions/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open clinician workspace/i })).toHaveAttribute(
      "href",
      "/clinician",
    );
  });
});
