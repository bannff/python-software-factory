"""Documentation content for browser brick."""

DOCS = {
    "overview": """# Browser Component

Browser automation with pluggable protocol adapters.

## Adapters

- **cdp**: Chrome DevTools Protocol (direct WebSocket connection)
- **playwright**: Playwright automation library
- **mock**: Mock adapter for testing

## Usage

```python
from factory.browser.interface import Runtime, create_server
from factory.browser.runtime.adapters.mock import MockAdapter

adapter = MockAdapter()
runtime = Runtime(adapter)

session = await runtime.launch()
await runtime.navigate(session.session_id, "https://example.com")
content = await runtime.get_content(session.session_id)
await runtime.close(session.session_id)
```

## MCP Tools

- `browser.launch` - Start a browser session
- `browser.navigate` - Go to a URL
- `browser.click` - Click an element
- `browser.type_text` - Type into an input
- `browser.screenshot` - Capture the page
- `browser.evaluate` - Run JavaScript
""",

    "adapters": """# Browser Adapters

## CDP Adapter

Direct Chrome DevTools Protocol connection. Requires Chrome/Chromium.

```python
from factory.browser.runtime.adapters.cdp import CDPAdapter

adapter = CDPAdapter(chrome_path="/usr/bin/chromium", port=9222)
```

## Playwright Adapter

Uses Playwright library. Supports Chromium, Firefox, WebKit.

## Mock Adapter

For testing without a real browser.

```python
from factory.browser.runtime.adapters.mock import MockAdapter

adapter = MockAdapter()
```
""",

    "selectors": """# Selector Strategies

## CSS Selectors (default)

```python
await runtime.click(session_id, "button.submit")
await runtime.type_text(session_id, "input#email", "test@example.com")
```

## XPath

```python
await runtime.click(session_id, "//button[@type='submit']", selector_type="xpath")
```
""",
}
