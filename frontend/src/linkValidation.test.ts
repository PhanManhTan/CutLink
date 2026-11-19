import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  validateCustomCode,
  validateDestination,
  validateName,
} from "./linkValidation.ts";

describe("destination URL feedback", () => {
  for (const value of [
    "",
    "example.com",
    "not a link",
    "ftp://example.com",
    "javascript:alert(1)",
    "https:/example.com",
    "https://exa mple.com",
    "https://example.com:99999",
    "https://user:password@example.com",
    "https://example.com/a\nb",
  ]) {
    it(`explains invalid input ${JSON.stringify(value)}`, () =>
      assert.notEqual(validateDestination(value), ""));
  }
  for (const value of [
    "https://example.com",
    "HTTP://LOCALHOST:8000/path?q=1#section",
    " https://example.com/path ",
    "https://example.com/a%20b",
  ]) {
    it(`accepts HTTP/HTTPS URL ${value}`, () =>
      assert.equal(validateDestination(value), ""));
  }
});

describe("custom endings", () => {
  for (const value of ["", "  ", "my-link", "My_link", "a".repeat(64)]) {
    it(`accepts blank or valid ending ${JSON.stringify(value)}`, () =>
      assert.equal(validateCustomCode(value), ""));
  }
  for (const value of ["ab", "_start", "my/link", "my link", "a".repeat(65)]) {
    it(`explains invalid ending ${value}`, () =>
      assert.notEqual(validateCustomCode(value), ""));
  }
  it("rejects a blank name", () => assert.notEqual(validateName("  "), ""));
});
