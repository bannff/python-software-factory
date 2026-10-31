import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import ReleasesSettingsPanel from "../releases-settings-panel";

describe("ReleasesSettingsPanel (row 100, feature-map)", () => {
  it("shows the running version and build identifier", () => {
    render(<ReleasesSettingsPanel />);
    expect(screen.getByText("Dashboard version")).toBeTruthy();
    expect(screen.getByText("Build")).toBeTruthy();
  });

  it("honestly discloses there is no in-app update/release-channel service", () => {
    render(<ReleasesSettingsPanel />);
    expect(screen.getByText(/no in-app release channel, update check, or changelog/i)).toBeTruthy();
  });
});
