---
id: technology-repurpose-old-pc
title: Turn an old PC into a local server
category: technology
summary: Give an old laptop or desktop a second life as a low-power local server for files, printing, or a shared library — no internet needed once it is set up.
difficulty: 3
estimated_time: "A weekend"
---

# Turn an old PC into a local server

An old laptop too slow for modern software still has plenty of life left as
a **local server** — a machine that quietly serves files, a shared library,
or other services to devices on your local network (see [[technology-local-network|build a local network without the internet]]). This keeps working hardware out of landfill
and gives your household or neighbourhood something genuinely useful to
reach over that network.

> **Tip:** Almost any machine from the last 15 years works fine as a local
> server — serving a handful of local devices needs far less power than
> running today's desktop software.

## Pick a candidate machine

- **Any working laptop or small desktop** with a working hard drive/SSD and
  power supply is enough — a dead battery doesn't matter if it stays
  plugged in. If the dead battery clips out, take it out and recycle it; if
  it is built in, check the case every month or so — a bulging base or a
  lifting trackpad means the battery is swelling: switch off, unplug, and
  see [[energy-everyday-batteries]].
- **Prefer lower power draw:** a laptop (built to run on a small battery)
  usually draws much less continuous power than an old desktop tower —
  worth choosing if you have a choice and expect to run it on solar.
- **Wipe personal data first** if the machine ever held someone's private
  files, then treat it as a blank machine.

## Install a lightweight operating system

Setting up needs the internet once; running the server afterwards does not.
For the setup day you need:

- The old PC and its charger or power lead
- A second, working computer with internet
- A USB stick of 8 GB or more (it will be wiped)
- A network cable to plug the old PC into your router

1. **Choose a lightweight Linux distribution** built for older hardware —
   these run comfortably on machines modern operating systems have left
   behind. **Debian** is a sound, long-lived choice.
2. **Make the installer stick:** on the working computer, download the
   installer and write it to the USB stick with an image-writing tool (the
   distribution's website explains how).
3. **Start the old PC from the stick** — usually by pressing F12, F2, or Esc
   just after switching on — and install. Choose a minimal/server install
   without a heavy graphical desktop if you're comfortable working from a
   command line; this saves both power and disk space.
4. **Install the software you want to host** (see below) while the machine
   is still connected to the internet.
5. **Set a fixed local address** for the machine, so other devices can find
   it at the same address every time. The simplest way is in your router's
   settings: reserve an address for the server (often called a "DHCP
   reservation" or "static lease").
6. **Stop a laptop sleeping when the lid is shut**, or the server vanishes
   every time someone closes it. On Debian, set `HandleLidSwitch=ignore` in
   `/etc/systemd/logind.conf` and restart.
7. **Enable automatic start on power-up:** look in the BIOS/firmware
   settings for "power on after AC loss" (or "AC recovery") and turn it on,
   so the server comes back after a power cut without anyone pressing a
   button. Most desktops have this setting; many home laptops don't. A
   laptop with a healthy battery rides through short cuts instead; one
   without needs someone to press the button — put that on the note you
   keep with the machine.

## Choose what to host

Pick one or two services to start — it's easy to add more later:

- **A file share:** a shared folder anyone on the local network can read
  from and write to, for documents, photos, or backups (Samba is the usual
  software).
- **A print server:** share one printer with every device on the network
  instead of needing a printer per household (CUPS does this).
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
- **Be careful with sleep:** a sleeping server looks switched off to
  everyone else unless it has been set up, and tested, to wake when a
  request arrives over its network cable — not every machine can. The
  simpler savings are letting the disks spin down and the screen switch off
  when idle, or running it only for agreed hours.
- **Size solar/battery power** to match its real draw — see [[energy-sizing-solar-battery|how big a solar+battery system do you need]], using the server's actual measured
  power use, not a guess.

## Maintain it simply

- **Keep a written note** of what the machine does, its address, and how to
  restart it — so someone other than the original builder can maintain it.
- **Check on it physically now and then:** dust out fans and vents, and
  confirm it's still reachable from another device.
- **Keep a spare machine or disk image** if you can, so a hardware failure
  is an inconvenience, not a disaster.

## Where to go next

- Build the network this server lives on: see [[technology-local-network|build a local network without the internet]].
- Keep it powered reliably: see [[energy-low-tech-solar|set up a small low-tech solar system]].
- Basic hardware troubleshooting: see [[technology-computer-maintenance|maintain and repair computers]].
