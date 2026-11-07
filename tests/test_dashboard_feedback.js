"use strict";
// No browser dependencies: test the real custom card's refresh state changes.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const cardCode = fs.readFileSync(
  "custom_components/ok_el/frontend/ok-el-history-card.js", "utf8"
);
let Card;
class FakeElement {
  attachShadow() {
    const button = {
      textContent: "",
      disabled: false,
      classList: {
        values: new Set(),
        remove(...items) { items.forEach(x => this.values.delete(x)); },
        add(item) { this.values.add(item); },
        contains(item) { return this.values.has(item); },
      },
    };
    this.testButton = button;
    this.shadowRoot = { getElementById(name) {
      return name === "reload" ? button : null;
    }};
  }
}
vm.runInNewContext(cardCode, {
  HTMLElement: FakeElement, setTimeout, clearTimeout, console,
  customElements: {
    get() { return undefined; },
    define(name, clazz) { Card = clazz; },
  },
  window: { customCards: [] },
});

const pause = delay => new Promise(resolve => setTimeout(resolve, delay));

async function testClickFeedback() {
  const card = new Card();
  card.isConnected = true;
  card._render = () => {};
  card._renderStatus = () => {};
  let release;
  card._hass = {
    callWS: () => new Promise(resolve => { release = resolve; }),
  };
  const request = card._fetch(true);
  assert.equal(card.testButton.disabled, true);
  assert.equal(card.testButton.textContent, "↻ Opdaterer…");
  assert.equal(card.testButton.classList.contains("refreshing"), true);
  release({rows: [], coverage: {}, busy: false, progress: {}});
  await request;
  await pause(710);
  assert.equal(card.testButton.textContent, "✓ Opdateret");
  assert.equal(card.testButton.classList.contains("refreshed"), true);
  clearTimeout(card._refreshTimer);
}

async function testErrorFeedback() {
  const card = new Card();
  card.isConnected = true;
  card._render = () => {};
  card._renderStatus = () => {};
  card._hass = { callWS: () => Promise.reject(new Error("test error")) };
  await card._fetch(true);
  assert.equal(card.testButton.classList.contains("refreshing"), true);
  await pause(710);
  assert.equal(card.testButton.classList.contains("failed"), true);
  clearTimeout(card._refreshTimer);
}

async function main() {
  await testClickFeedback();
  await testErrorFeedback();
  console.log("OK El refresh button state transitions pass.");
}
main().catch(error => { console.error(error); process.exitCode = 1; });
