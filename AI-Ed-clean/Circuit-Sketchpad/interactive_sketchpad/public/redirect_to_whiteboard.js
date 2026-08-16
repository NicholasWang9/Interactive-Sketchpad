(function () {
  // The whiteboard page (interactive_canvas.py, port 8081) embeds this same
  // chat URL in an iframe so chat + canvas show together. Only redirect the
  // top-level window to the whiteboard -- never the iframe embed itself,
  // or every page load would bounce back and forth forever.
  if (window.self !== window.top) {
    // Embedded in the whiteboard page: relay Chainlit's own light/dark theme
    // choice to the parent (interactive_canvas.py) via postMessage instead of
    // redirecting, so both panes stay on the same theme. Chainlit toggles a
    // "dark"/"light" class on <html> itself when the student uses its own
    // theme switcher, so watching that class is enough -- no separate control
    // needed on the whiteboard side.
    var root = document.documentElement;
    function reportTheme() {
      window.parent.postMessage({ type: "sketchpad-theme", dark: root.classList.contains("dark") }, "*");
    }
    new MutationObserver(reportTheme).observe(root, { attributes: true, attributeFilter: ["class"] });
    reportTheme();
    return;
  }

  var target = window.location.protocol + "//" + window.location.hostname + ":8081/";

  // Give the chat a moment to connect and register this session with the
  // whiteboard server (chatbot.py's on_chat_start does this, and on first
  // ever load also has to spawn the whiteboard server itself) before
  // navigating away, so the whiteboard opens already pointed at this chat.
  setTimeout(function () {
    window.location.replace(target);
  }, 1500);
})();
