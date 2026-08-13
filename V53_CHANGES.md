# Investify Analytics v53

v53 is built directly from the supplied v52 codebase. Backend market-data, portfolio sync, options pricing/screening, AI, auth, Supabase, calendar, news, and other application logic are preserved.

## Mobile UI/UX redesign (<= 760px)

- Home
  - Tighter hero, search, typography, spacing, and buttons.
  - Major indexes remain three small tiles on one row.
  - Section titles stay left aligned with compact right-aligned action buttons.
  - AI market context and headlines are collapsible on phones.
- Markets
  - AI market brief is collapsible on phones.
  - Major benchmark cards are smaller.
  - Popular stocks/ETFs render as a compact table-like list instead of large tiles.
- Screener
  - Filters stack cleanly.
  - Results fit the phone width without horizontal scrolling by showing the five most useful columns on mobile.
- Portfolio
  - Summary cards are smaller 2x2 tiles.
  - Holdings use compact phone rows with price, today, total return, and expandable position details.
  - Desktop holdings table remains intact.
  - Allocation, AI review, watchlist, add-position, cash, and option-entry sections remain collapsible on mobile.
  - Options positions are tightened for mobile.
- Options Lab
  - Underlying stats become a compact one-line strip.
  - Candidate trades use narrow phone cards with no Analyze button; tapping the card opens analysis.
  - Selected Trade stays non-collapsible.
  - Trade Quality, Position Greeks, Contract Legs, and Payoff are collapsible.
  - Contract-leg data is denser and avoids wide horizontal scrolling.
  - Payoff chart is shorter on mobile.
- AI Search
  - Saved chats and AI context remain collapsible.
  - Conversation occupies the phone width.
  - Context chips and prompt chips wrap instead of horizontally scrolling.
  - Smaller chat controls, messages, and sticky input composer.
- Other pages
  - Smaller mobile buttons, tabs, headings, card padding, and chart heights.
  - Safer wrapping and viewport-width handling.

## Explicit desktop behavior changes requested

- Clicking anywhere on a Portfolio holding row opens that ticker's Research page (Edit/Remove buttons remain functional).
- Stock Research order is Key Metrics -> Your Position (if held) -> Price Chart -> Stock Signal -> remaining sections.
- Your Position is conditionally rendered only when shares > 0. With zero/no shares, the element is completely omitted from the DOM.
- Logged-in cloud portfolio data is authoritative for Your Position.
- Options Trade Analysis has collapsible Trade Quality, Position Greeks, Contract Legs, and Payoff sections; Selected Trade remains always visible.
- Stock and payoff chart heights are tightened to reduce unused whitespace.

## Cache

- PWA service-worker cache name bumped to `investify-v53-shell` so old cached v52 styling is cleared on update.
