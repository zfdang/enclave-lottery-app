# Frontend Architecture (Vite React)

Implements the real-time UI consuming websocket events from the passive backend. Direct user interaction with the smart contract occurs via wallet (MetaMask) — backend does not proxy user bets.

## Tech Stack
| Layer | Details |
|-------|---------|
| Build | Vite + TypeScript |
| UI    | React functional components + hooks |
| State | Local component state; event-driven updates (no global store yet) |
| Wallet| Window.ethereum (MetaMask) / EIP-1193 provider |
| Network | WebSocket (`/ws`) + optional read-only REST (`/status`) |

## Directory Structure (excerpt)
```
enclave/frontend/
  package.json
  vite.config.js
  index.html
  src/
    main.tsx
    App.tsx
    components/
      GameIntro.tsx        # modal with game explanation
      ActivityFeed/...      # (future) feed UI
      Participants/...      # participant list & CTA highlight
    services/
      (future) contract.ts # placeholder for direct chain helpers
    utils/
      websocket.ts         # (potential) reconnection logic (if added)
```

## Data Flow
1. `App.tsx` opens a single websocket connection.
2. On each inbound JSON message, dispatch by `type` and update local state slices (round, participants, history, config).
3. Components subscribe to the relevant slice via props or context (context introduction TBD once complexity increases).
4. User clicks (e.g. "Place Bet") trigger direct contract interaction through the wallet provider (future dedicated service wrapper may consolidate this logic).

## Environment Variables (Vite)
Expose at build time using `VITE_` prefix.

| Variable | Purpose | Example |
|----------|---------|---------|
| `VITE_API_URL` | REST base (fallback for status) | `http://localhost:6080` |
| `VITE_WS_URL` | WebSocket endpoint | `ws://localhost:6080/ws` |
| `VITE_CHAIN_ID` | Expected chain ID (for UI validation) | `31337` |
| `VITE_EXPLORER_BASE` | Block explorer base URL | `https://basescan.org` |
| `VITE_CONTRACT_ADDRESS` | Display & deep link contract address | `0x...` |

Access in code: `import.meta.env.VITE_API_URL`.

## Build & Run
Development:
```bash
cd enclave/frontend
npm install
npm run dev
```
Production build (static assets):
```bash
npm run build
# Outputs dist/ which can be copied into backend image
```

Preview built assets:
```bash
npm run preview
```

## WebSocket Handling
Simple approach (pseudo):
```ts
const ws = new WebSocket(import.meta.env.VITE_WS_URL);
ws.onmessage = (evt) => {
  const msg = JSON.parse(evt.data);
  switch(msg.type){
    case 'round_update': setRound(msg.round); break;
    case 'participants_update': setParticipants(msg.participants); break;
    case 'history_update': setHistory(msg.rounds); break;
    case 'config_update': setConfig(msg.contract); break;
  }
};
```

Potential improvements:
* Reconnection with backoff
* Heartbeat / ping if server introduces `heartbeat` messages
* Schema version negotiation (see `EVENTS.md` future section)

## Contract Interaction (Planned Abstraction)
Currently minimal inline usage. Plan:
* `services/contract.ts` exporting helper functions (e.g., `placeBet(amount)`)
* Automatic chain ID validation before send
* Gas estimation + user feedback

## UI/UX Notes
* Game Intro chip + modal for onboarding context
* Activity feed surfaces notable events (bet placed, round complete)
* Participant panel highlights CTA when list empty (“Be the first to bet!”)
* Contract address displayed with hyperlink to explorer base (if configured)

## Testing Strategy (Recommended)
| Layer | Approach |
|-------|----------|
| Components | React Testing Library snapshot + interaction tests |
| WebSocket | Mock server that replays fixture events |
| Contract integration | E2E (Playwright) hitting local Anvil + test wallet |

## Performance Considerations
Current event payload sizes are small; if participant counts grow large consider:
* Delta events instead of full list
* Virtualized list rendering (react-window) for participant list

## Security & Validation
* Frontend displays data from events; does not trust for irreversible actions—on-chain is source of truth
* Chain ID mismatch should display an alert (add small hook `useChainIdValidation`)
* Avoid exposing private keys or mnemonic anywhere (all signing in wallet)

## Future Enhancements
* Light global state container (Zustand or Redux Toolkit) if complexity rises
* i18n support (currently English only per repo guidance)
* Theming system (Tailwind / CSS variables)
* Wallet abstraction supporting WalletConnect

---
Updated: 2025-10-03