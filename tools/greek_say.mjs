// Prints the app's Erasmian respelling (js/sound.js greekSay) for each line of Greek on stdin, one per line.
// Used by tools/check_lessons.py so hand-written "say" strings agree with what the app shows for other words.
import { greekSay } from "../js/sound.js";
import { readFileSync } from "fs";
const lines = readFileSync(0, "utf8").split("\n");
process.stdout.write(lines.map((l) => greekSay(l)).join("\n"));
