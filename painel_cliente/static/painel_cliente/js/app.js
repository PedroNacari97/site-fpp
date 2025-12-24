import { initLoginFocus } from "./modules/login.js";
import { initTableEnhancements } from "./modules/tables.js";

document.addEventListener("DOMContentLoaded", () => {
  initLoginFocus();
  initTableEnhancements();
});
