---
id: technology-mesh-network
title: Build a resilient mesh network
category: technology
summary: Go beyond a simple Wi-Fi network to a true mesh — multi-hop and self-healing, with no single point of failure — using phones, LoRa nodes, or repurposed routers.
difficulty: 3
estimated_time: "A weekend to set up"
---

# Build a resilient mesh network

Build a local network without the internet covers getting a basic Wi-Fi
network or a first LoRa link working. This guide goes a step further: a true
**mesh** isn't just extended Wi-Fi coverage from one hub — it's a network
where every node can relay for its neighbours, has more than one path to
reach any other node, and keeps working even when one node drops out.

> **Note:** This inherits the same guardrails as horizon's other technology
> guides — community coordination, not surveillance; know your local radio
> rules; keep expectations realistic about range and bandwidth.

## What makes a network actually a mesh

```ascii
   hub-and-spoke (one failure breaks it):     true mesh (routes around failure):

        [ hub ]                                  [ A ]---[ B ]
       /   |   \                                   \  X  /
    [A]  [B]  [C]                                   [ C ]---[ D ]

   if the hub fails, everyone loses contact       if any one link or node fails,
                                                   traffic reroutes through another
```

*Fig. 1: hub-and-spoke networks (including most consumer "Wi-Fi mesh"
routers) still depend on one central point; a true mesh routes around a
failed node instead of losing the network*

- **Multi-hop:** a message can travel node to node to reach somewhere out of
  direct range — each device that relays it extends the network further.
- **Self-healing:** if one node goes offline, traffic automatically finds
  another path, rather than the whole network splitting.
- **No single point of failure:** unlike a hub-and-spoke Wi-Fi mesh, there's
  no one router whose loss takes everyone else down with it.

## Start with Bluetooth mesh on phones already owned

The lowest-effort mesh needs no new hardware at all:

- **A Bluetooth mesh messaging app** lets nearby phones relay short
  messages hop to hop, extending well beyond one phone's direct Bluetooth
  range, with no internet, account, or server involved. **BitChat** is one
  such app built for exactly this: open, decentralised, phone-to-phone.
- **If your group also runs neighbourgood** (horizon's sibling project for
  neighbourhood coordination), it ships its own lighter built-in Bluetooth
  mesh feature — worth checking before adding a separate app, since it may
  already cover this for a group that's using it anyway. horizon works
  fully on its own either way; this is just worth knowing if you already
  run both.
- **Good for:** short text messages and coordination across a crowd or
  neighbourhood where everyone already carries a phone — not for files or
  a shared local server, which still want the network in the guide above.

## Go longer-range with LoRa mesh nodes

For distance beyond what Bluetooth or Wi-Fi can cover:

- **Use open mesh firmware on LoRa nodes**, not a simple point-to-point
  link — this is what makes distant nodes able to relay for each other
  automatically rather than needing a direct line to every other node.
- **Place nodes for redundant paths, not just coverage.** Two nodes that can
  each reach a third by a different route survive one going down; a single
  chain of nodes doesn't. Think in terms of a mesh diagram, not a line on a
  map.
- **Add nodes gradually** and check the network still reroutes correctly
  when you temporarily power one down — a mesh you haven't tested for
  failure isn't confirmed to be one.
- **Power each node** from a small solar or battery setup (see the energy
  guides) since a mesh only stays resilient if its nodes stay powered.

## Make Wi-Fi self-healing too

A step up from the simple access-point mesh in the local-network guide:

- **Use open mesh routing firmware** on repurposed routers instead of a
  single vendor's proprietary mesh system — this lets any router relay for
  any other, rather than all routing through one designated hub.
- **Add at least one redundant link** between buildings where you can (a
  second router in range of two others, not just one) so a single router
  failure doesn't split the network in two.
- **Test failure on purpose:** unplug a router and confirm devices still
  reach the local server through another path before you trust it.

## Where to go next

- Get the basics working first if you haven't: see build a local network
  without the internet.
- Power nodes reliably: see set up a small low-tech solar system.
- Add voice alongside the mesh: see set up two-way radio for your
  community.
