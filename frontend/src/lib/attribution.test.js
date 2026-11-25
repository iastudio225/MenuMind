import { normalizeSource, readSource } from "./attribution";

test("keeps whitelisted sources and lowercases them", () => {
  expect(normalizeSource("WA")).toBe("wa");
  expect(normalizeSource(" qr ")).toBe("qr");
  expect(normalizeSource("instagram")).toBe("other");
});

test("missing or blank source means a direct visit", () => {
  expect(normalizeSource("")).toBe("direct");
  expect(normalizeSource(null)).toBe("direct");
  expect(normalizeSource(undefined)).toBe("direct");
});

test("reads the source from the query string", () => {
  expect(readSource("?src=wa")).toBe("wa");
  expect(readSource("?foo=1&src=QR")).toBe("qr");
  expect(readSource("")).toBe("direct");
  expect(readSource("?src=spam")).toBe("other");
});
