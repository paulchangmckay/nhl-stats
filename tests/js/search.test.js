const test = require("node:test");
const assert = require("node:assert/strict");
const { tokenize, playerSearchText, matchesQuery } = require("../../static/js/search.js");

const mackinnon = {
  first_name: "Nathan",
  last_name: "MacKinnon",
  team_name: "Avalanche",
  team_abbrev: "COL",
  team_place_name: "Colorado",
};

test("tokenize lowercases, trims, splits on whitespace, and drops empties", () => {
  assert.deepEqual(tokenize("  Nathan   MacKinnon "), ["nathan", "mackinnon"]);
  assert.deepEqual(tokenize(""), []);
  assert.deepEqual(tokenize(undefined), []);
});

test("playerSearchText concatenates name and team fields, lowercased", () => {
  assert.equal(
    playerSearchText(mackinnon),
    "nathan mackinnon avalanche col colorado"
  );
});

test("playerSearchText skips missing fields without leaving gaps", () => {
  assert.equal(
    playerSearchText({ first_name: "Nathan", last_name: "MacKinnon" }),
    "nathan mackinnon"
  );
});

test("matchesQuery matches on last name alone", () => {
  assert.equal(matchesQuery(mackinnon, "MacKinnon"), true);
});

test("matchesQuery matches full name in forward order", () => {
  assert.equal(matchesQuery(mackinnon, "Nathan MacKinnon"), true);
});

test("matchesQuery matches full name in reversed order", () => {
  assert.equal(matchesQuery(mackinnon, "MacKinnon Nathan"), true);
});

test("matchesQuery returns false for a non-matching query", () => {
  assert.equal(matchesQuery(mackinnon, "Connor McDavid"), false);
});

test("matchesQuery returns false for an empty query", () => {
  assert.equal(matchesQuery(mackinnon, ""), false);
});

test("matchesQuery matches team short name", () => {
  assert.equal(matchesQuery(mackinnon, "Avalanche"), true);
});

test("matchesQuery matches team abbreviation", () => {
  assert.equal(matchesQuery(mackinnon, "COL"), true);
});

test("matchesQuery matches team place name", () => {
  assert.equal(matchesQuery(mackinnon, "Colorado"), true);
});

test("matchesQuery matches multi-token team name", () => {
  assert.equal(matchesQuery(mackinnon, "Colorado Avalanche"), true);
});

test("matchesQuery does not cross-match a name token against an unrelated team", () => {
  const otherTeamPlayer = {
    first_name: "Connor",
    last_name: "McDavid",
    team_name: "Oilers",
    team_abbrev: "EDM",
    team_place_name: "Edmonton",
  };
  assert.equal(matchesQuery(otherTeamPlayer, "Colorado Avalanche"), false);
});
