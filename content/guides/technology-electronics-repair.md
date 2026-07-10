---
id: technology-electronics-repair
title: Repair small electronics and solder
category: technology
summary: Diagnose a dead wire, connector, or circuit with a multimeter and fix it with basic soldering — the general skill behind most technology repairs.
difficulty: 2
estimated_time: "An afternoon to learn, then as needed"
---

# Repair small electronics and solder

Most small electronics fail at the same few points: a broken wire, a
corroded connector, a blown fuse, a cracked solder joint. Learning to find
and fix these is the general skill underneath fixing a radio, a solar
controller's wiring, or a computer's internal cables — worth learning on
its own, not just when something breaks.

> **Risk:** Work on low-voltage, battery-powered electronics only — radios,
> LED circuits, connectors, small DC-powered devices. **Mains-voltage
> internals are out of scope here** and need a trained electrician: mains
> current can kill, and some components (capacitors in particular) can hold
> a dangerous charge even after a device is unplugged. Lithium batteries are
> also a puncture and fire hazard — never cut, crush, or short one.

## Get the basic tools

- **A multimeter** — the single most useful diagnostic tool; lets you test
  voltage, continuity, and whether a fuse or wire is actually broken before
  you start guessing.
- **A soldering iron and solder**, plus flux to help solder flow cleanly
  onto a joint.
- **Wire strippers, small pliers, and tweezers** for handling fine wires and
  components.
- **Good ventilation or a fan** while soldering — the fumes are unpleasant
  and best not breathed in directly.

## Diagnose before you open anything

1. **Test with the multimeter first.** Continuity mode tells you if a wire
   or fuse is actually broken; voltage mode tells you if power is reaching
   where it should.
2. **Look for the obvious:** a visibly snapped wire, a corroded or loose
   connector, a scorched component, a swollen battery.
3. **Isolate the fault** by testing at each connection point along the
   circuit, working from the power source outward, until the reading
   changes where it shouldn't.

> **Spec:** A healthy wire or fuse reads close to **0 ohms** (continuity) —
> no reading, or a very high resistance, means it's broken there.

## Solder a clean joint

```ascii
   iron tip touches BOTH the wire and the joint --v
                                                    \
        wire  ----+----  pad/terminal          [ iron ]
                   |
              (heat first, then feed solder to the JOINT, not the tip)
```

*Fig. 1: solder flows to heat, not the other way round — heat the joint,
then touch solder to the joint itself, never to the iron's tip directly*

1. **Clean and tin the iron's tip** with a small amount of fresh solder
   before starting.
2. **Heat the joint itself** (the wire and pad together) for a second or
   two before introducing solder.
3. **Feed solder to the joint, not the iron** — it should melt from the
   heat of the joint and flow smoothly around it.
4. **Hold still while it cools** — movement during cooling creates a dull,
   weak "cold joint" that fails again quickly.
5. **Inspect the result:** a good joint is shiny and smoothly shaped, not
   dull, grainy, or blobbed.

## Common fixes

- **A broken wire:** strip both ends back a little, twist the strands
  together, solder the joint, then insulate it with heat-shrink tubing or
  electrical tape.
- **A worn or corroded connector:** clean contacts gently with a
  pencil-eraser or fine abrasive, or replace the connector if it's cheap and
  available.
- **A blown fuse:** replace with the **same rating**, never a higher one —
  a fuse's rating is a safety limit, not an inconvenience.
- **A loose joint on a circuit board:** reheat the existing joint fully and
  let it re-flow, rather than just piling on more solder.

## Salvage before you discard

- **Strip working parts from anything otherwise dead:** connectors,
  switches, wire, and small components are all reusable.
- **Keep a small parts box** — salvaged pieces solve future repairs faster
  than sourcing something new each time.
- Repairing and reusing keeps working material out of landfill — see
  maintain and repair computers for the same principle applied to a whole
  machine.

## Where to go next

- Apply this to a specific machine: see maintain and repair computers.
- Fix antenna and connector issues on a radio setup: see set up two-way
  radio for your community.
- Give repaired hardware a real job: see turn an old PC into a local
  server.
