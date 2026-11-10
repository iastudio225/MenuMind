import { buildExperienceUrl } from "./publicLinks";

test("builds the chatbot URL from the application origin and restaurant public ID", () => {
  expect(buildExperienceUrl("https://app.menumind.example/", "rest_demo_chezawa"))
    .toBe("https://app.menumind.example/experience/rest_demo_chezawa");
});

test("does not invent a route when the restaurant has no public ID", () => {
  expect(buildExperienceUrl("https://app.menumind.example", "")).toBe("");
});
