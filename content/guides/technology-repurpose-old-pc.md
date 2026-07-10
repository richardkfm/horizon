---
id: technology-repurpose-old-pc
title: Turn an old PC into a local server
category: technology
summary: Give an old laptop or desktop a second life as a low-power local server for files, printing, or a shared library — no internet required.
difficulty: 3
estimated_time: "A weekend"
---

# Turn an old PC into a local server

An old laptop too slow for modern software still has plenty of life left as
a **local server** — a machine that quietly serves files, a shared library,
or other services to devices on your local network (see build a local
network without the internet). This keeps working hardware out of landfill
and gives your household or neighbourhood something genuinely useful to
reach over that network.

> **Tip:** Almost any machine from the last 15 years works fine as a local
> server — serving a handful of local devices needs far less power than
> running today's desktop software.

## Pick a candidate machine

- **Any working laptop or small desktop** with a working hard drive/SSD and
  power supply is enough — a dead battery doesn't matter if it stays
  plugged in.
- **Prefer lower power draw:** a laptop (built to run on a small battery)
  usually draws much less continuous power than an old desktop tower —
  worth choosing if you have a choice and expect to run it on solar.
- **Wipe personal data first** if the machine ever held someone's private
  files, then treat it as a blank machine.

## Install a lightweight operating system

1. **Choose a lightweight Linux distribution** built for older hardware —
   these run comfortably on machines modern operating systems have left
   behind.
2. **Install it from a USB drive**, choosing a minimal/server install
   without a heavy graphical desktop if you're comfortable working from a
   command line — this saves both power and disk space.
3. **Set a fixed local address** for the machine on your network, so other
   devices can find it at the same address every time.
4. **Enable automatic start on power-up** so the server comes back after a
   power cut without anyone needing to press a button.

## Choose what to host

Pick one or two services to start — it's easy to add more later:

- **A file share:** a shared folder anyone on the local network can read
  from and write to, for documents, photos, or backups.
- **A print server:** share one printer with every device on the network
  instead of needing a printer per household.
- **A local library or wiki:** serve guides, reference material, or a
  community wiki page over the local network — reachable with just a web
  browser, no internet needed.
- **A backup target:** a place other households' devices can copy their
  important files to, so no single device is a single point of failure.

> **Risk:** A server holding shared files is also a single point of
> failure for whatever it stores — keep an occasional backup copy on a
> separate drive, not just on the server itself.

## Keep power use low

- **Turn off what you don't use:** disable the screen, Wi-Fi radio, or
  unused ports on a machine that only needs a wired network connection.
- **Let it sleep between requests** where the software supports it, waking
  on network activity rather than idling at full power.
- **Size solar/battery power** to match its real draw — see how big a
  solar+battery system do you need, using the server's actual measured
  power use, not a guess.

## Maintain it simply

- **Keep a written note** of what the machine does, its address, and how to
  restart it — so someone other than the original builder can maintain it.
- **Check on it physically now and then:** dust out fans and vents, and
  confirm it's still reachable from another device.
- **Keep a spare machine or disk image** if you can, so a hardware failure
  is an inconvenience, not a disaster.

## Where to go next

- Build the network this server lives on: see build a local network
  without the internet.
- Keep it powered reliably: see set up a small low-tech solar system.
- Basic hardware troubleshooting: see maintain and repair computers.
