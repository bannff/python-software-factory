import { describe, expect, it } from "vitest";
import { validateCrewForm, type CrewFormValues } from "../crew-validation";

const valid: CrewFormValues = {
  id: "redteam", name: "Red Team", persona_id: "redteam", project: "/work/app",
  memory_scope: "redteam", model: "", description: "", workspace: "", triggers: "",
};

describe("validateCrewForm", () => {
  it("accepts a fully specified crew", () => {
    expect(validateCrewForm(valid, true)).toEqual({});
  });

  it("names every required field that is blank", () => {
    const errors = validateCrewForm({ ...valid, id: "", name: "", persona_id: "", project: "", memory_scope: "" }, true);
    expect(Object.keys(errors).sort()).toEqual(["id", "memory_scope", "name", "persona_id", "project"]);
  });

  it("rejects ids and scopes outside the backend grammar", () => {
    const errors = validateCrewForm({ ...valid, id: "Red Team", memory_scope: "-x" }, true);
    expect(errors.id).toMatch(/lowercase/i);
    expect(errors.memory_scope).toMatch(/lowercase/i);
  });

  it("does not validate the immutable id when editing", () => {
    expect(validateCrewForm({ ...valid, id: "" }, false)).toEqual({});
  });

  it("rejects more than 32 triggers", () => {
    const triggers = Array.from({ length: 33 }, (_, i) => `t${i}`).join(",");
    expect(validateCrewForm({ ...valid, triggers }, true).triggers).toMatch(/32/);
  });
});
