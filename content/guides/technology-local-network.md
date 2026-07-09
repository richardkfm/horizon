---
id: technology-local-network
title: Build a local network without the internet
category: technology
summary: Connect nearby households with Wi-Fi or a long-range mesh so you can share files, messages, and local services with no internet uplink.
difficulty: 3
estimated_time: "A weekend to set up"
---

# Build a local network without the internet

A "local network" just means devices that can talk to each other directly —
it needs no internet connection at all. A neighbourhood with its own local
network can share files, send messages, and reach local services (like a
shared library or a horizon node) even when the wider internet is down or
was never connected in the first place.

> **Note:** Build this for sharing by consent, not for watching or tracking
> anyone. A local network is a shared, common resource for the group that
> sets it up.

## Pick a range and bandwidth

| Option | Range | Bandwidth | Good for |
| --- | --- | --- | --- |
| **Wi-Fi access point** | One building, ~30-50 m | High | Fast file transfer, browsing a local server |
| **Wi-Fi mesh (several routers)** | A few buildings | High | Extending Wi-Fi across a small site without new cabling |
| **LoRa mesh** | 1-5+ km, hops further node to node | Very low (text only) | Status updates and short messages across a wider area |

> **Pick this if:** you mainly want to reach a shared local server (files,
> guides, a local wiki) from nearby homes — a plain Wi-Fi access point or
> small mesh is simpler and faster than LoRa for this.

> **Avoid if:** you need to cover real distance with only text-level
> messages — that's exactly what LoRa mesh is for; don't try to stretch
> Wi-Fi mesh across distances it wasn't built for.

## Set up a basic offline Wi-Fi network

A router doesn't need an internet uplink to create a working local network:

1. **Take any Wi-Fi router** (new or repurposed) and set it up as normal,
   but leave its internet ("WAN") port unconnected.
2. **Give the network a clear name** your neighbours will recognise, and a
   shared password everyone in the group knows.
3. **Connect a local server** (see turn an old PC into a local server) to
   the router by cable for the most reliable link, so anyone on the Wi-Fi
   can reach it by typing its address.
4. **Extend coverage** by adding more access points in mesh mode, or by
   running a cable to a second router in another building.

```ascii
   [ house A ]         [ house B ]          [ house C ]
   Wi-Fi AP  ------------ Wi-Fi AP ------------ Wi-Fi AP
       |         (mesh or cabled link)             |
   [ local server ]                          [ any device ]
   (files, guides, etc.)                     connects to nearest AP
```

*Fig. 1: a small Wi-Fi mesh — each access point covers one building, linked
to the next so devices anywhere in range reach the same local server*

## Set up a long-range LoRa mesh

For distances plain Wi-Fi can't reach:

1. **Get a handful of LoRa mesh devices** — small, low-power radios designed
   to relay short text messages node to node.
2. **Place nodes to cover gaps**, not just distance — a node partway between
   two distant points often does more for coverage than one more powerful
   node.
3. **Set expectations:** LoRa mesh carries short text and location pings
   well, not files or voice — pair it with Wi-Fi for anything bandwidth-
   heavy.
4. **Power each node** from a small solar or battery setup (see the energy
   guides) since nodes need to run continuously to relay for others.

## Keep it fair and simple

- **Agree who can join** and how new households get the password or a node.
- **Keep the network open to consent-based sharing only** — no
  device-tracking, no snooping on neighbours' traffic.
- **Label and document it** simply enough that someone other than the
  original builder can maintain it later.

## Where to go next

- Give the network something worth reaching: see turn an old PC into a
  local server.
- Pair it with voice: see set up two-way radio for your community.
- Power nodes and access points reliably: see set up a small low-tech solar
  system.
