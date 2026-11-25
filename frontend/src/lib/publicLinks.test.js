import { buildExperienceUrl, buildShareUrl } from "./publicLinks";

test("builds the chatbot URL from the application origin and restaurant public ID", () => {
  expect(buildExperienceUrl("https://app.menumind.example/", "rest_demo_chezawa"))
    .toBe("https://app.menumind.example/experience/rest_demo_chezawa");
});

test("does not invent a route when the restaurant has no public ID", () => {
  expect(buildExperienceUrl("https://app.menumind.example", "")).toBe("");
});

test("builds the short share URL with a source", () => {
  expect(buildShareUrl("https://app.menumind.example/", "rest_demo_chezawa", "wa"))
    .toBe("https://app.menumind.example/s/rest_demo_chezawa?src=wa");
});

test("omits the source parameter for direct visits", () => {
  expect(buildShareUrl("https://app.menumind.example", "rest_demo_chezawa"))
    .toBe("https://app.menumind.example/s/rest_demo_chezawa");
});

test("normalizes unknown sources and handles an empty public ID", () => {
  expect(buildShareUrl("https://app.menumind.example", "rest_demo_chezawa", "spam"))
    .toBe("https://app.menumind.example/s/rest_demo_chezawa?src=other");
  expect(buildShareUrl("https://app.menumind.example", "", "wa")).toBe("");
});
