# Cloud session check

This public repository must not contain credentials, cookies, or private FPL team responses.

FPL authentication requires a browser session cookie. Password-based unattended login is not currently implemented.

Add the browser session Cookie header value to the GitHub Actions repository secret named FPL_SESSION_COOKIE (without the Cookie: prefix). Never post the value in chat or source control.

Run Actions > Verify private FPL session (read-only) > Run workflow. The check validates account entry 1580840 and the shape of the private response. It only logs success or failure, not private data.

Sessions expire. Future private snapshots require a separate private storage destination and a secure renewal strategy. Keep account two-factor authentication enabled.
