# ez-redirect

ez-redirect is a lightweight redirect service that runs locally on your network.  
You can access it from any device on your LAN, or port-forward it to allow external traffic to route through it.

This lets you point NFC tags, QR codes, print materials, or shortlinks to a single URL that you can update instantly without reprinting anything.

---

## Features

- **Local redirect server**  
  Runs on your LAN and handles `/redirect` requests.

- **Preset management**  
  Add, edit, reorder, and switch between saved URLs.

- **Temporary redirects**  
  Set a timer so the redirect automatically changes back after a specified duration.

- **Auto-starts on boot**  
  Installs as a `systemd` service and restarts if the machine reboots.

---

## Installation

Run the installer script:

```bash
curl -sL https://raw.githubusercontent.com/notandrewjones/ez-redirect/main/install.sh | sudo bash
