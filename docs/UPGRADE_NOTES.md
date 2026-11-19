# UPGRADE_NOTES.md — RC1 (draft, Lain)

## Loopback-bind migration note (RC1)

The RC1 compose patch binds db 5432 and app 8000 to 127.0.0.1 only. This closes the all-interface exposure present in f64 and in the S5 throwaway stack.

**Migration:** any client that previously reached the app or DB via the host LAN IP or `0.0.0.0`-published port must switch to loopback (`127.0.0.1:8000`, `127.0.0.1:5432`) on the Docker host, or reach the app through the approved tunnel path (outside RC1). Existing port-forward rules and any buyer/client instructions using the old host:port are invalid after RC1.

**Port-override rule:** do NOT set `POSTING_ENABLED` or alternate port bindings in RC1 to work around connectivity. The approved patch changes exactly two port lines and nothing else. If a different bind is needed, it is a new owner decision and a new patch hash — the current APPROVED is void. Verification: `docker port` and `netstat` show only 127.0.0.1 listeners for 5432 and 8000.

## Test override files (RC1)

Test override files are ALLOWED if they: (a) stay UNTRACKED, (b) are NEVER committed, (c) run with their OWN `-p` project, and (d) use `!override` ports. 
**Never run the RC1 compose on default ports on Eli's machine.** The approved patch binds 127.0.0.1; test overrides must use distinct ports and a distinct compose project so they cannot collide with or rebind the RC1 stack.
