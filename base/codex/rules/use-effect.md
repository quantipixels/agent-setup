# React `useEffect` Usage Standards

These rules govern when and how React's `useEffect` hook is used in React components.

## When useEffect Is Appropriate

Use `useEffect` only when lifecycle cleanup is the actual job:

- Subscriptions (WebSocket, EventEmitter, observable)
- Timers (`setTimeout`, `setInterval`) that must be cleared on unmount
- DOM event listeners that must be removed on unmount
- Direct DOM manipulation required outside React's control
- Third-party library setup and teardown (e.g. maps, charts, media players)

The presence of a cleanup return is a strong signal the effect belongs here.

## When NOT to Use useEffect

Do not reach for `useEffect` when the value or action can be expressed more directly:

- Deriving a value from props or state — compute it inline or use `useMemo`
- Responding to a user event — put the logic in the event handler
- Synchronising two state values where one is a transformation of the other
- Fetching data that can be initiated at component mount with a library (React Query, SWR, `use`)
- Resetting state when a prop changes — restructure with a `key` or derive from the prop directly

## Common Antipatterns

**Deriving state**
```tsx
// Bad
useEffect(() => {
  setFiltered(items.filter(i => i.active));
}, [items]);

// Good
const filtered = useMemo(() => items.filter(i => i.active), [items]);
// or inline: const filtered = items.filter(i => i.active);
```

**Event-driven side effects**
```tsx
// Bad
useEffect(() => {
  if (submitted) sendForm(data);
}, [submitted]);

// Good
function handleSubmit() {
  sendForm(data);
}
```

**Unnecessary synchronisation**
```tsx
// Bad
useEffect(() => {
  setDisplayName(formatName(firstName, lastName));
}, [firstName, lastName]);

// Good
const displayName = formatName(firstName, lastName);
```

## Scope and Size

If an effect does more than one thing, split it into separate `useEffect` calls. Each effect must have a single, named purpose. A long effect body is a design smell.

## Cleanup Requirement

If an effect has no cleanup function and no async operation, question whether it belongs in `useEffect` at all. The absence of cleanup is a signal that the logic may belong in an event handler, a derived value, or component initialisation.

## Default

When unsure, ask: does this code need to run on mount and undo something on unmount? If not, it does not belong in `useEffect`.
