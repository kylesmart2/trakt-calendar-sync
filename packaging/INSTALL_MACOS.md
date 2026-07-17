# Opening Trakt Calendar Sync on macOS (unsigned build)

This app isn't signed with a paid Apple Developer certificate, so macOS's
Gatekeeper will block it the first time you try to open it - normal for any
unsigned app you didn't get from the App Store. You only need to do this
once; after that it opens normally.

## After downloading/copying the app to your Mac

1. Double-click **Trakt Calendar Sync.app**. You'll see a message like:

   > "Trakt Calendar Sync" can't be opened because Apple cannot check it
   > for malicious software.

   Click **Done** (not Move to Trash).

2. Open **System Settings → Privacy & Security**, scroll down to the
   **Security** section. You'll see a note that "Trakt Calendar Sync" was
   blocked, with an **Open Anyway** button next to it. Click it.

3. Confirm in the dialog that appears (enter your password or use Touch ID
   if asked).

4. From then on, double-clicking the app works like any other app.

## Alternative (if step 1 shows a simple Open option instead)

Some macOS versions - or apps transferred by AirDrop/local network instead
of downloaded from the web - skip straight to a dialog with an **Open**
button. Control-click (or right-click) the app, choose **Open** from the
menu, then click **Open** again in the confirmation dialog.

## For anyone comfortable with Terminal

The blocking is caused by a "quarantine" flag macOS adds to downloaded
files. Removing it skips all of the above:

```
xattr -cr "/path/to/Trakt Calendar Sync.app"
```
