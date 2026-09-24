const { setTimeout: delay } = require("node:timers/promises");

// A successful publish can precede registry visibility by several minutes.
// Retry absence and channel propagation; conflicting bytes or stable tags fail.
async function waitForPublishedCandidate({ read, integrity, version, channel,
  previousLatest, attempts = 21, delayMs = 30_000, wait = delay }) {
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    const result = await read();
    if (result) {
      if (result.integrity !== integrity) throw new Error("Registry bytes differ from the tested candidate");
      if (channel === "next" && result.tags.latest !== previousLatest) {
        throw new Error("Stable latest unexpectedly changed");
      }
      if (result.tags[channel] === version) return result;
    }
    if (attempt < attempts) await wait(delayMs);
  }
  throw new Error("Registry visibility or release channel did not converge within the verification window; preserve the tag and archive and rerun verification");
}

module.exports = { waitForPublishedCandidate };
